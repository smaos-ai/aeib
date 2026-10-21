"""
tests/test_runtime_boundary_and_state_machine.py
================================================================================
Test suite for AEIB Track A: Runtime Boundary & 8-State Effect Machine.
"""
import os
import sys
import tempfile
from pathlib import Path
from typing import Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from src.runtime_boundary.runtime_execution_boundary import (
    EffectState,
    PermissionEpoch,
    PersistentAgentIdentity,
    RuntimeExecutionBoundary,
    canonical_json_bytes,
)


def _generate_test_agent() -> Tuple[PersistentAgentIdentity, Ed25519PrivateKey]:
    priv = Ed25519PrivateKey.generate()
    pub_pem = priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    agent = PersistentAgentIdentity(
        agent_id="agent-prod-001",
        principal_id="user-corp-99",
        public_key_pem=pub_pem,
        created_at=1767225600,
        status="ACTIVE",
    )
    return agent, priv


def _sign_act_envelope(
    priv: Ed25519PrivateKey,
    act_core: dict,
) -> dict:
    canonical = canonical_json_bytes(act_core)
    sig_bytes = priv.sign(canonical)
    return {
        "act_core": act_core,
        "signature": {"alg": "Ed25519", "value": sig_bytes.hex()},
    }


def test_runtime_boundary_nominal_and_consequential_flow() -> None:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
        db_path = tmp.name

    try:
        boundary = RuntimeExecutionBoundary(db_path)
        agent, priv = _generate_test_agent()
        boundary.register_agent(agent)

        cap = PermissionEpoch(
            capability_id="cap-refund-01",
            agent_id=agent.agent_id,
            scope="refund.create",
            max_per_call_minor=200_00,
            daily_ceiling_minor=500_00,
            policy_epoch="2026-Q4",
            issued_at=1767225600,
            expires_at=1769817600,
            status="ACTIVE",
        )
        boundary.register_capability(cap)

        # 1. Nominal Act authorization
        act = {
            "operation_id": "op-101",
            "agent_id": agent.agent_id,
            "capability_id": cap.capability_id,
            "action_type": "refund.create",
            "target": "iban:DE89370400440532013000",
            "amount_minor": 150_00,
        }
        res = boundary.authorize_and_persist_intent(_sign_act_envelope(priv, act), current_time=1767230000)
        assert res["disposition"] == "AUTHORIZED_AND_INTENT_PERSISTED"
        assert res["state"] == EffectState.INTENT_PERSISTED

        # 2. Advance to DISPATCHED
        boundary.mark_dispatched("op-101", current_time=1767230001)

        # 3. HTTP 200 outcome -> CONFIRMED
        outcome = boundary.record_effect_outcome("op-101", http_status=200, current_time=1767230002)
        assert outcome["disposition"] == "CONFIRMED"
        assert outcome["state"] == EffectState.CONFIRMED

        # Check exposure: 150_00 settled, 0 reserved
        exp = boundary.get_budget_exposure(agent.agent_id)
        assert exp["settled_minor"] == 150_00
        assert exp["reserved_minor"] == 0

    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_runtime_boundary_falsifications_and_uncertainty_latch() -> None:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
        db_path = tmp.name

    try:
        boundary = RuntimeExecutionBoundary(db_path)
        agent, priv = _generate_test_agent()
        boundary.register_agent(agent)

        cap = PermissionEpoch(
            capability_id="cap-refund-02",
            agent_id=agent.agent_id,
            scope="refund.create",
            max_per_call_minor=100_00,
            daily_ceiling_minor=200_00,
            policy_epoch="2026-Q4",
            issued_at=1767225600,
            expires_at=1769817600,
            status="ACTIVE",
        )
        boundary.register_capability(cap)

        # Falsification 1: Exceeds per-call cap (150 > 100)
        act_overcap = {
            "operation_id": "op-overcap",
            "agent_id": agent.agent_id,
            "capability_id": cap.capability_id,
            "action_type": "refund.create",
            "target": "iban:DE89370400440532013000",
            "amount_minor": 150_00,
        }
        r_over = boundary.authorize_and_persist_intent(_sign_act_envelope(priv, act_overcap), current_time=1767230000)
        assert r_over["disposition"] == "NOT_DISPATCHED"
        assert r_over["code"] == "ERR_AMOUNT_EXCEEDS_PER_CALL_CAP"

        # Falsification 2: Expired policy epoch
        r_exp = boundary.authorize_and_persist_intent(_sign_act_envelope(priv, {
            "operation_id": "op-expired",
            "agent_id": agent.agent_id,
            "capability_id": cap.capability_id,
            "action_type": "refund.create",
            "target": "iban:DE89370400440532013000",
            "amount_minor": 50_00,
        }), current_time=1770000000)  # > 1769817600
        assert r_exp["disposition"] == "NOT_DISPATCHED"
        assert r_exp["code"] == "ERR_POLICY_EPOCH_EXPIRED"

        # Falsification 3: Uncertainty Latch & Blind Retry Prevention
        act_drop = {
            "operation_id": "op-504",
            "agent_id": agent.agent_id,
            "capability_id": cap.capability_id,
            "action_type": "refund.create",
            "target": "iban:DE89370400440532013000",
            "amount_minor": 80_00,
        }
        r_drop = boundary.authorize_and_persist_intent(_sign_act_envelope(priv, act_drop), current_time=1767230000)
        assert r_drop["disposition"] == "AUTHORIZED_AND_INTENT_PERSISTED"
        boundary.mark_dispatched("op-504", current_time=1767230001)

        # Transport drop: HTTP 504 -> EFFECT_INDETERMINATE
        out_drop = boundary.record_effect_outcome("op-504", http_status=504, current_time=1767230002)
        assert out_drop["disposition"] == "LATCHED_UNCERTAINTY"
        assert out_drop["state"] == EffectState.EFFECT_INDETERMINATE

        # Blind retry with identical operation_id must FAIL CLOSED
        r_retry = boundary.authorize_and_persist_intent(_sign_act_envelope(priv, act_drop), current_time=1767230003)
        assert r_retry["disposition"] == "NOT_DISPATCHED"
        assert r_retry["code"] == "HALT_BLIND_RETRY_PROHIBITED_UNDER_UNCERTAINTY"

        # Authoritative reconciliation settles the uncertainty
        rec_outcome = boundary.record_effect_outcome(
            "op-504", http_status=None, current_time=1767230010, authoritative_reconciliation="CONFIRMED"
        )
        assert rec_outcome["disposition"] == "RECONCILED"
        assert rec_outcome["state"] == EffectState.CONFIRMED

        # Circuit Breaker Halt
        boundary.trigger_halt("HONEYPOT_DETECTED")
        r_halted = boundary.authorize_and_persist_intent(_sign_act_envelope(priv, {
            "operation_id": "op-blocked",
            "agent_id": agent.agent_id,
            "capability_id": cap.capability_id,
            "action_type": "refund.create",
            "target": "iban:DE89370400440532013000",
            "amount_minor": 10_00,
        }), current_time=1767230020)
        assert r_halted["disposition"] == "NOT_DISPATCHED"
        assert "HALT_CIRCUIT_BREAKER_ACTIVE" in r_halted["code"]

    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


if __name__ == "__main__":
    test_runtime_boundary_nominal_and_consequential_flow()
    test_runtime_boundary_falsifications_and_uncertainty_latch()
    print("TRACK A RUNTIME BOUNDARY TESTS PASSED.")
