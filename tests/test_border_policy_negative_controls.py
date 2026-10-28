#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
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
tests/test_border_policy_negative_controls.py
================================================================================
Mandatory Negative Controls NC-1 through NC-4 for AEIB Border Policy.

Verifies:
- NC-1: Nonce burning survives process restart; replaying burned nonce is blocked fail-closed.
- NC-2: SIGKILL / transport drop mid-call persists DISPATCHED_UNCONFIRMED on disk across
        process restart; blind retries are blocked fail-closed.
- NC-3: Tainted draft_payment is blocked under Bell-LaPadula lattice; payment parameter
        limits apply uniformly to draft_payment.
- NC-4: Static AST claim integrity checks catch mock imports and trivial verifier evasions.
"""

import ast
from pathlib import Path
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.border_policy import (
    BorderVerdict,
    CancelledAtState,
    PolicyManifest,
    SignedHumanActionWarrant,
    TaintTier,
    TaskEscortState,
    compute_action_caid,
    evaluate_action_admissibility,
    issue_human_warrant,
)
from src.durable_border_enforcer import DurableBorderEnforcer
from compliance.claim_integrity_gate import ClaimIntegrityGate, ModuleAnalyzer


@pytest.fixture
def border_policy() -> PolicyManifest:
    return PolicyManifest(
        policy_version="aeib_border_policy_v1",
        tenant_id="tenant-nc-enforcement",
        agent_id="agent-nc-worker",
        allowed=frozenset({"read_invoice", "classify_invoice", "draft_payment"}),
        forbidden_without_human=frozenset({"execute_payment", "delete_record"}),
        forbidden_always=frozenset({"self_modify_policy", "bypass_approval"}),
        max_amount_minor_units=100_000,
        allowed_currencies=frozenset({"EUR", "PLN", "UAH"}),
        pinned_recipients=frozenset({"ukrpost_clearing", "poczta_polska_hub"}),
    )


@pytest.fixture
def human_keypair() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    priv = Ed25519PrivateKey.generate()
    return priv, priv.public_key()


def test_nc1_nonce_replay_survives_restart(
    tmp_path: Path,
    border_policy: PolicyManifest,
    human_keypair: tuple[Ed25519PrivateKey, Ed25519PublicKey],
) -> None:
    """NC-1: Nonce burn is written to WAL; replaying the same nonce in a fresh instance is blocked."""
    priv, pub = human_keypair
    ledger_dir = tmp_path / "nc1_ledger"
    now_ns = 1_000_000_000

    pay_args = {"amount_minor": 15_000, "currency": "EUR", "recipient_id": "ukrpost_clearing"}
    caid = compute_action_caid("execute_payment", pay_args, border_policy.tenant_id, border_policy.agent_id)

    warrant = issue_human_warrant(
        warrant_id="mandate-nc1",
        nonce="single-use-nonce-101",
        tenant_id=border_policy.tenant_id,
        action_name="execute_payment",
        action_caid=caid,
        expires_at_ns=now_ns + 10_000_000_000,
        human_priv_key=priv,
    )

    # Instance 1: executes once and burns nonce to disk
    e1 = DurableBorderEnforcer(border_policy, ledger_dir, pub)
    v1 = e1.evaluate_and_escort("execute_payment", pay_args, now_ns, lambda: {"status": "ok"}, warrant=warrant)
    assert v1.allowed is True
    assert v1.escort_state == TaskEscortState.COMMITTED

    # Instance 2: fresh process/instance on same ledger directory
    e2 = DurableBorderEnforcer(border_policy, ledger_dir, pub)

    # Attempt replay with same warrant/nonce on different args (different CAID)
    diff_args = {"amount_minor": 12_000, "currency": "EUR", "recipient_id": "ukrpost_clearing"}
    diff_caid = compute_action_caid("execute_payment", diff_args, border_policy.tenant_id, border_policy.agent_id)
    warrant_replay = issue_human_warrant(
        warrant_id="mandate-nc1-replay",
        nonce="single-use-nonce-101",  # Same burned nonce!
        tenant_id=border_policy.tenant_id,
        action_name="execute_payment",
        action_caid=diff_caid,
        expires_at_ns=now_ns + 10_000_000_000,
        human_priv_key=priv,
    )

    v2 = e2.evaluate_and_escort("execute_payment", diff_args, now_ns + 100, lambda: {"status": "dup"}, warrant=warrant_replay)
    assert v2.allowed is False
    assert "HALT_WARRANT_NONCE_ALREADY_BURNED" in v2.reason_code


def test_nc2_sigkill_after_dispatch_preserves_escrow(
    tmp_path: Path,
    border_policy: PolicyManifest,
    human_keypair: tuple[Ed25519PrivateKey, Ed25519PublicKey],
) -> None:
    """NC-2: Transport drop mid-flight sets DISPATCHED_UNCONFIRMED; fresh process blocks blind retry."""
    priv, pub = human_keypair
    ledger_dir = tmp_path / "nc2_ledger"
    now_ns = 2_000_000_000

    pay_args = {"amount_minor": 25_000, "currency": "PLN", "recipient_id": "poczta_polska_hub"}
    caid = compute_action_caid("execute_payment", pay_args, border_policy.tenant_id, border_policy.agent_id)

    warrant = issue_human_warrant(
        warrant_id="mandate-nc2",
        nonce="nonce-nc2-001",
        tenant_id=border_policy.tenant_id,
        action_name="execute_payment",
        action_caid=caid,
        expires_at_ns=now_ns + 10_000_000_000,
        human_priv_key=priv,
    )

    def failing_dispatch() -> dict:
        raise ConnectionResetError("HTTP 504 Gateway Timeout or TCP RST mid-socket")

    # Instance 1: encounters wire drop mid-dispatch
    e1 = DurableBorderEnforcer(border_policy, ledger_dir, pub)
    v1 = e1.evaluate_and_escort("execute_payment", pay_args, now_ns, failing_dispatch, warrant=warrant)
    assert v1.allowed is False
    assert v1.escort_state == TaskEscortState.DISPATCHED_UNCONFIRMED
    assert "HALT_TRANSPORT_DROP" in v1.reason_code

    # Instance 2: fresh process on same ledger
    e2 = DurableBorderEnforcer(border_policy, ledger_dir, pub)

    # Fresh warrant on the same CAID (attempted blind retry)
    warrant2 = issue_human_warrant(
        warrant_id="mandate-nc2-retry",
        nonce="nonce-nc2-002",
        tenant_id=border_policy.tenant_id,
        action_name="execute_payment",
        action_caid=caid,
        expires_at_ns=now_ns + 10_000_000_000,
        human_priv_key=priv,
    )

    v2 = e2.evaluate_and_escort("execute_payment", pay_args, now_ns + 100, lambda: {"status": "retry"}, warrant=warrant2)
    assert v2.allowed is False
    assert v2.escort_state == TaskEscortState.DISPATCHED_UNCONFIRMED
    assert "HALT_A2A_DISPATCHED_UNCONFIRMED_NO_BLIND_RETRY" in v2.reason_code


def test_nc3_tainted_draft_payment_blocked(border_policy: PolicyManifest) -> None:
    """NC-3: Untrusted context (TIER_2) attempting to draft payment is blocked by Bell-LaPadula."""
    now_ns = 3_000_000_000

    # 1. Attacker injects a draft payment command inside external RAG snippet
    attacker_args = {
        "amount_minor": 99_999_999,
        "currency": "XXX",
        "recipient_id": "malicious_actor",
    }
    v_tainted = evaluate_action_admissibility(
        "draft_payment",
        attacker_args,
        border_policy,
        now_ns,
        taint_tier=TaintTier.TIER_2_UNTRUSTED_EXTERNAL,
    )
    assert v_tainted.allowed is False
    assert v_tainted.reason_code == "HALT_UNTRUSTED_CONTEXT_CANNOT_AUTHORIZE_MUTATION"

    # 2. Even under TIER_0_SYSTEM, illegal payment limits on draft_payment are caught
    v_limits = evaluate_action_admissibility(
        "draft_payment",
        attacker_args,
        border_policy,
        now_ns,
        taint_tier=TaintTier.TIER_0_SYSTEM,
    )
    assert v_limits.allowed is False
    assert v_limits.reason_code == "HALT_PAYMENT_AMOUNT_OUT_OF_BOUNDS"


@pytest.mark.parametrize(
    "src,expected_rule",
    [
        ("def is_valid_sig(sig):\n    return True\n", "CI003"),
        ("def verify_authorization():\n    t = 1\n    return True\n", "CI003"),
        ("async def verify_signature(data):\n    return True\n", "CI003"),
        ("def check_warrant(w):\n    return {'status': 'simulated', 'valid': True}\n", "CI006"),
    ],
)
def test_nc4_ast_gate_catches_trivial_verifiers_and_simulated_markers(
    src: str,
    expected_rule: str,
) -> None:
    """NC-4: Claim-integrity AST analyzer flags constant-accept verifiers and simulated markers."""
    gate = ClaimIntegrityGate(root=Path("."))
    tree = ast.parse(src)
    analyzer = ModuleAnalyzer(
        gate=gate,
        rel="src/test_evasion.py",
        source=src,
        tree=tree,
        rules=frozenset({"CI003", "CI006"}),
    )
    findings = analyzer.run()
    flagged_rules = {f.rule for f in findings}
    assert expected_rule in flagged_rules, f"Expected {expected_rule} for snippet:\n{src}"
