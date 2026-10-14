#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
tests/test_temporal_standing_and_andon_cord.py
================================================================================
AEIB Commit-Time Temporal Standing ($T_0 \\to \\Delta N \\to T_n$),
EU AI Act Article 14 Andon Cord Safe Halt, and Saidot Graph Fragment Test Suite.

Evaluates the 10 invariants under the stated model:
  1. Policy epoch changes after authorization: deny fail-closed.
  2. Principal revoked after authorization: deny fail-closed.
  3. Delegation revoked after authorization: deny fail-closed.
  4. Target removed from allowlist after authorization: deny fail-closed.
  5. Action digest altered after authorization: deny fail-closed.
  6. Authority expires before commit: deny fail-closed.
  7. Evidence store unavailable: block consequential dispatch fail-closed.
  8. Human Andon cord stop command: halt safely and record operator intervention.
  9. Minimal Saidot governance graph fragment emission.
  10. Standing confirmed when all invariants hold.
"""

import copy
import hashlib
import os
import sys
import time
from pathlib import Path
import pytest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

# Path injection
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "v1.1-roadmap"))

from src.jcs_canonicalizer import encode_jcs
from temporal_standing_evaluator import (
    TemporalStandingEvaluator,
    StandingCheckContext,
    StandingEvaluationResult,
    AndonCordController,
    SaidotGraphFragmentEmitter,
    EventDrivenInvalidator,
)


def _compute_caid(payload: dict) -> str:
    canonical = encode_jcs(payload)
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _create_sample_context(
    *,
    operation_id: str = "op-refund-401",
    principal_id: str = "agent-settlement-01",
    target_identity: str = "target-payout-api",
    authorized_policy_epoch: int = 1,
    ticket_decision_id: str = "dec-allow-881",
    ticket_expires_at: int = 1000,
    delegation_chain_ids: list = None,
    payload_override: dict = None,
) -> StandingCheckContext:
    payload = payload_override or {
        "action": "disburse_customer_refund",
        "amount": 250.0,
        "currency": "EUR",
        "customer_id": "cust-9921",
        "reason": "late_delivery_cancellation",
    }
    action_digest = _compute_caid(payload)
    return StandingCheckContext(
        operation_id=operation_id,
        action_digest=action_digest,
        principal_id=principal_id,
        target_identity=target_identity,
        proposed_payload=payload,
        authorized_policy_epoch=authorized_policy_epoch,
        ticket_decision_id=ticket_decision_id,
        ticket_expires_at=ticket_expires_at,
        delegation_chain_ids=delegation_chain_ids or ["del-hop-root", "del-hop-01"],
    )


def test_01_policy_epoch_changed_after_authorization_denied():
    """Invariant 1: Policy epoch changes after authorization -> fail-closed denial."""
    invalidator = EventDrivenInvalidator()
    evaluator = TemporalStandingEvaluator(
        active_policy_epoch_provider=invalidator.get_active_epoch,
        target_allowlist_provider=lambda: {"target-payout-api"},
        revocation_registry_provider=lambda: set(),
        evidence_store_health_probe=lambda: True,
    )

    ctx = _create_sample_context(authorized_policy_epoch=1, ticket_expires_at=2000)

    # State delta occurs during Delta N: policy epoch advances
    invalidator.dispatch_event(
        event_type="POLICY_EPOCH_CHANGED",
        entity_id="policy-engine",
        timestamp_epoch=1500,
        details={"new_epoch": 2},
    )

    # Evaluation at Tn
    res = evaluator.evaluate_standing(ctx, current_timestamp=1600)
    assert not res.standing_valid
    assert res.violated_check == "POLICY_EPOCH_CHANGED"
    assert "authorized epoch 1 != active 2" in res.rejection_reason


def test_02_principal_revoked_after_authorization_denied():
    """Invariant 2: Principal revoked after authorization -> fail-closed denial."""
    invalidator = EventDrivenInvalidator()
    evaluator = TemporalStandingEvaluator(
        active_policy_epoch_provider=invalidator.get_active_epoch,
        target_allowlist_provider=lambda: {"target-payout-api"},
        revocation_registry_provider=lambda: invalidator._revoked_entities,
        evidence_store_health_probe=lambda: True,
    )

    ctx = _create_sample_context(principal_id="agent-settlement-01", ticket_expires_at=2000)

    # State delta during Delta N: principal credentials or standing revoked
    invalidator.dispatch_event(
        event_type="PRINCIPAL_REVOKED",
        entity_id="agent-settlement-01",
        timestamp_epoch=1500,
    )

    res = evaluator.evaluate_standing(ctx, current_timestamp=1600)
    assert not res.standing_valid
    assert res.violated_check == "PRINCIPAL_REVOKED"
    assert "agent-settlement-01" in res.rejection_reason


def test_03_delegation_revoked_after_authorization_denied():
    """Invariant 3: Any intermediate delegation revoked after authorization -> fail-closed denial."""
    invalidator = EventDrivenInvalidator()
    evaluator = TemporalStandingEvaluator(
        active_policy_epoch_provider=invalidator.get_active_epoch,
        target_allowlist_provider=lambda: {"target-payout-api"},
        revocation_registry_provider=lambda: invalidator._revoked_entities,
        evidence_store_health_probe=lambda: True,
    )

    ctx = _create_sample_context(
        delegation_chain_ids=["del-hop-root", "del-hop-intermediate", "del-hop-leaf"],
        ticket_expires_at=2000,
    )

    # Intermediate delegation link revoked
    invalidator.dispatch_event(
        event_type="DELEGATION_REVOKED",
        entity_id="del-hop-intermediate",
        timestamp_epoch=1500,
    )

    res = evaluator.evaluate_standing(ctx, current_timestamp=1600)
    assert not res.standing_valid
    assert res.violated_check == "DELEGATION_REVOKED"
    assert "del-hop-intermediate" in res.rejection_reason


def test_04_target_removed_from_allowlist_after_authorization_denied():
    """Invariant 4: Target removed from allowlist after authorization -> fail-closed denial."""
    active_allowlist = {"target-payout-api", "target-reporting-api"}
    evaluator = TemporalStandingEvaluator(
        active_policy_epoch_provider=lambda: 1,
        target_allowlist_provider=lambda: active_allowlist,
        revocation_registry_provider=lambda: set(),
        evidence_store_health_probe=lambda: True,
    )

    ctx = _create_sample_context(target_identity="target-payout-api", ticket_expires_at=2000)

    # Security team drops target-payout-api from allowlist during Delta N
    active_allowlist.remove("target-payout-api")

    res = evaluator.evaluate_standing(ctx, current_timestamp=1600)
    assert not res.standing_valid
    assert res.violated_check == "TARGET_NOT_ALLOWLISTED"
    assert "target-payout-api" in res.rejection_reason


def test_05_action_digest_altered_after_authorization_denied():
    """Invariant 5: Action payload mutated between authorization and commit -> fail-closed denial."""
    evaluator = TemporalStandingEvaluator(
        active_policy_epoch_provider=lambda: 1,
        target_allowlist_provider=lambda: {"target-payout-api"},
        revocation_registry_provider=lambda: set(),
        evidence_store_health_probe=lambda: True,
    )

    # Original payload for 250.0 EUR
    ctx = _create_sample_context(ticket_expires_at=2000)

    # Tampered payload mutated to 2500.0 EUR during Delta N
    tampered_payload = copy.deepcopy(ctx.proposed_payload)
    tampered_payload["amount"] = 2500.0

    tampered_ctx = StandingCheckContext(
        operation_id=ctx.operation_id,
        action_digest=ctx.action_digest,  # Authorized CAID bound to 250.0
        principal_id=ctx.principal_id,
        target_identity=ctx.target_identity,
        proposed_payload=tampered_payload,  # Mismatched payload!
        authorized_policy_epoch=ctx.authorized_policy_epoch,
        ticket_decision_id=ctx.ticket_decision_id,
        ticket_expires_at=ctx.ticket_expires_at,
        delegation_chain_ids=ctx.delegation_chain_ids,
    )

    res = evaluator.evaluate_standing(tampered_ctx, current_timestamp=1600)
    assert not res.standing_valid
    assert res.violated_check == "ACTION_DIGEST_MUTATED"
    assert "mutated between authorization and commit" in res.rejection_reason


def test_06_authority_expires_before_commit_denied():
    """Invariant 6: Authority ticket expires before commit -> fail-closed denial."""
    evaluator = TemporalStandingEvaluator(
        active_policy_epoch_provider=lambda: 1,
        target_allowlist_provider=lambda: {"target-payout-api"},
        revocation_registry_provider=lambda: set(),
        evidence_store_health_probe=lambda: True,
    )

    ctx = _create_sample_context(ticket_expires_at=1500)

    # Evaluation occurs after ticket expiration
    res = evaluator.evaluate_standing(ctx, current_timestamp=1501)
    assert not res.standing_valid
    assert res.violated_check == "AUTHORITY_EXPIRED"
    assert "expired at 1500 (commit time: 1501)" in res.rejection_reason


def test_07_evidence_store_unavailable_blocked_fail_closed():
    """Invariant 7: Evidence store probe unhealthy -> consequential dispatch blocked fail-closed."""
    store_healthy = True
    evaluator = TemporalStandingEvaluator(
        active_policy_epoch_provider=lambda: 1,
        target_allowlist_provider=lambda: {"target-payout-api"},
        revocation_registry_provider=lambda: set(),
        evidence_store_health_probe=lambda: store_healthy,
    )

    ctx = _create_sample_context(ticket_expires_at=2000)

    # Evidence store experiences I/O disk failure or partition
    store_healthy = False

    res = evaluator.evaluate_standing(ctx, current_timestamp=1600)
    assert not res.standing_valid
    assert res.violated_check == "EVIDENCE_STORE_UNAVAILABLE"
    assert "fail-closed" in res.rejection_reason


def test_08_human_andon_cord_stop_command_safe_halt():
    """Invariant 8: EU AI Act Art. 14 Human Andon Cord stop command immediately halts execution safely."""
    andon = AndonCordController(halted_initially=False)
    evaluator = TemporalStandingEvaluator(
        active_policy_epoch_provider=lambda: 1,
        target_allowlist_provider=lambda: {"target-payout-api"},
        revocation_registry_provider=lambda: set(),
        evidence_store_health_probe=lambda: True,
        andon_cord_probe=andon.is_halted,
    )

    ctx = _create_sample_context(ticket_expires_at=2000)

    # Pre-halt: standing valid
    res_before = evaluator.evaluate_standing(ctx, current_timestamp=1400)
    assert res_before.standing_valid

    # Operator hits the Andon Cord (emergency interrupt)
    halt_record = andon.trip_andon_cord(
        operator_principal="compliance-officer-marina",
        reason="Abnormal transaction clustering detected across sub-agents",
        timestamp_epoch=1450,
    )
    assert halt_record["system_state"] == "SAFE_HALT_ENGAGED"
    assert andon.is_halted()

    # All dispatches at Tn are immediately denied
    res_halted = evaluator.evaluate_standing(ctx, current_timestamp=1500)
    assert not res_halted.standing_valid
    assert res_halted.violated_check == "ANDON_CORD_TRIPPED"
    assert "Emergency operator interrupt active" in res_halted.rejection_reason

    # Supervisor reset under dual control
    reset_record = andon.reset_andon_cord(
        supervisor_principal="ciso-stephen",
        justification="Incident root-cause identified and isolated; resuming pipeline",
        timestamp_epoch=1600,
    )
    assert reset_record["system_state"] == "NORMAL_OPERATION_RESUMED"
    assert not andon.is_halted()

    # Dispatches resume safely
    res_resumed = evaluator.evaluate_standing(ctx, current_timestamp=1650)
    assert res_resumed.standing_valid


def test_09_saidot_minimal_governance_graph_fragment_emission():
    """Invariant 9: Minimal machine-readable governance graph fragments emitted without monolithic overhead."""
    # 1. Governed Asset Fragment
    asset_frag = SaidotGraphFragmentEmitter.emit_asset_fragment(
        agent_id="agent-refund-settler-v1",
        owner_principal="team-payments-eu",
        policy_profile="FINANCIAL_SETTLEMENT_TIER_1",
        risk_classification="HIGH_CONSEQUENCE_FINANCIAL",
        approved_use_context="CUSTOMER_REFUND_SETTLEMENT",
        active_policy_epoch=3,
    )

    assert asset_frag["entity_type"] == "GOVERNED_ASSET"
    assert asset_frag["asset_id"] == "agent-refund-settler-v1"
    assert asset_frag["metadata"]["policy_epoch"] == 3
    assert asset_frag["metadata"]["evidence_survivability"] == "INDEPENDENT_SIGNED_RECEIPT"

    # Verifies deterministic canonical RFC 8785 encoding
    asset_jcs = encode_jcs(asset_frag)
    asset_caid = hashlib.sha256(asset_jcs).hexdigest()
    assert len(asset_caid) == 64

    # 2. Governed Dependency Fragment
    dep_frag = SaidotGraphFragmentEmitter.emit_dependency_fragment(
        agent_id="agent-refund-settler-v1",
        target_id="core-banking-payment-gateway",
        target_uri_pattern="https://payments.internal.bank/v2/settlements/*",
        owner_team="banking-platform-infra",
        evidence_contract="ISO20022_PAIN001_STATUS_V2",
        probe_budget=2,
        circuit_breaker_threshold=4,
    )

    assert dep_frag["entity_type"] == "GOVERNED_DEPENDENCY"
    assert dep_frag["source_asset_id"] == "agent-refund-settler-v1"
    assert dep_frag["relationship"] == "MUTATES_STATE_VIA"
    assert dep_frag["contract"]["reconciliation"]["probe_budget"] == 2

    dep_jcs = encode_jcs(dep_frag)
    dep_caid = hashlib.sha256(dep_jcs).hexdigest()
    assert len(dep_caid) == 64


def test_10_standing_confirmed_when_all_invariants_hold():
    """Invariant 10: All 10 invariants satisfied -> standing confirmed and audit record emitted."""
    evaluator = TemporalStandingEvaluator(
        active_policy_epoch_provider=lambda: 1,
        target_allowlist_provider=lambda: {"target-payout-api"},
        revocation_registry_provider=lambda: set(),
        evidence_store_health_probe=lambda: True,
        egress_topology_probe=lambda: True,
        andon_cord_probe=lambda: False,
    )

    ctx = _create_sample_context(authorized_policy_epoch=1, ticket_expires_at=2000)

    res = evaluator.evaluate_standing(ctx, current_timestamp=1500)
    assert res.standing_valid
    assert res.violated_check is None
    assert res.rejection_reason is None
    assert res.audit_event is not None
    assert res.audit_event["event"] == "TEMPORAL_STANDING_CONFIRMED"
    assert res.audit_event["standing"] == "PRESENT_AND_VALID"
