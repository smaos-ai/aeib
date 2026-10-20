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
tests/test_predictive_trajectory_drift_latch.py
================================================================================
Test Suite for Predictive Trajectory Drift Latch & Chaos Fuzzer.

Evaluated under the stated model. Strict zero-mock cryptographic purity enforced.
Validates:
1. Nominal progressive trajectories within velocity and entropy bounds succeed.
2. Injected excessive domain shift velocity triggers HALT_PREDICTIVE_TRAJECTORY_DRIFT.
3. Injected homoglyph JSON key substitutions trigger HALT_HOMOGLYPH_KEY_INJECTION.
4. Injected zero-width and covert token smuggling trigger HALT_TOKEN_SMUGGLING_DETECTED.
5. Injected out-of-order execution steps trigger HALT_OUT_OF_ORDER_EXECUTION.
6. Authorized Ed25519 supervisor step-up warrant resets the tripped latch properly.
7. Multi-vector chaos fuzzer campaign runs and catches 100% of perturbations.
8. CLI self-test execution runs cleanly.
9. Banned promotional word scan over all owned files.
================================================================================
"""

from __future__ import annotations

import base64
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict

from cryptography.hazmat.primitives.asymmetric import ed25519
import pytest

from src.jcs_canonicalizer import encode_jcs
from src.predictive_trajectory_drift_latch import (
    HALT_HOMOGLYPH_KEY_INJECTION,
    HALT_LATCH_ALREADY_TRIPPED,
    HALT_OUT_OF_ORDER_EXECUTION,
    HALT_PREDICTIVE_TRAJECTORY_DRIFT,
    HALT_STEP_UP_WARRANT_INVALID,
    HALT_TOKEN_SMUGGLING_DETECTED,
    AdversarialTrajectoryChaosFuzzer,
    CapabilityDomain,
    HomoglyphKeyInjectionError,
    LatchTrippedError,
    OutOfOrderExecutionError,
    PredictiveTrajectoryDriftError,
    PredictiveTrajectoryDriftLatch,
    StepUpWarrantInvalidError,
    TokenSmugglingDetectedError,
    ToolCallProposal,
    run_self_test,
)


@pytest.fixture
def supervisor_keys():
    """Generates real Ed25519 supervisor key pair."""
    priv = ed25519.Ed25519PrivateKey.generate()
    pub = priv.public_key()
    return priv, pub


@pytest.fixture
def configured_latch(supervisor_keys):
    """Provides a fresh PredictiveTrajectoryDriftLatch instance."""
    _, pub = supervisor_keys
    return PredictiveTrajectoryDriftLatch(
        agent_id="agent-test-orch-01",
        max_velocity_threshold=2.0,
        max_step_jump=2.0,
        max_entropy_acceleration=1.5,
        max_curvature_threshold=1.85,
        supervisor_public_keys={"supervisor-root": pub},
    )


@pytest.fixture
def fuzzer():
    """Provides AdversarialTrajectoryChaosFuzzer instance."""
    return AdversarialTrajectoryChaosFuzzer()


# ==============================================================================
# 1. Nominal Multi-Step Trajectories
# ==============================================================================

def test_nominal_multistep_trajectory(configured_latch):
    """
    Evaluates nominal multi-step progression:
    READ_ONLY -> CONFIG_PROBE -> FINANCIAL_DISPATCH.
    Verifies all steps are admitted with valid receipts and metrics.
    """
    sess = "session-test-nominal"

    # Step 1: Read-only inspection (Domain 0)
    p1 = ToolCallProposal(
        tool_name="lookup_balance",
        arguments={"account_id": "acct_source_100"},
        session_id=sess,
        step_index=1,
    )
    r1 = configured_latch.evaluate_proposal(p1)
    assert r1.admitted is True
    assert r1.latch_tripped is False
    assert r1.metrics.domain_level == CapabilityDomain.READ_ONLY
    assert r1.metrics.domain_velocity == 0.0

    # Step 2: Diagnostic verification (Domain 1)
    p2 = ToolCallProposal(
        tool_name="inspect_logs",
        arguments={"query": "recent_transfers"},
        session_id=sess,
        step_index=2,
    )
    r2 = configured_latch.evaluate_proposal(p2)
    assert r2.admitted is True
    assert r2.metrics.domain_level == CapabilityDomain.DIAGNOSTIC
    assert r2.metrics.domain_step_jump == 1.0

    # Step 3: Staged preparation (Domain 2)
    p3 = ToolCallProposal(
        tool_name="staged_escrow",
        arguments={"amount": 25000, "destination": "acct_dest_200"},
        session_id=sess,
        step_index=3,
    )
    r3 = configured_latch.evaluate_proposal(p3)
    assert r3.admitted is True
    assert r3.metrics.domain_level == CapabilityDomain.CONFIG_PROBE

    # Step 4: Financial dispatch execution (Domain 4)
    p4 = ToolCallProposal(
        tool_name="wire_dispatch",
        arguments={"amount": 25000, "destination": "acct_dest_200"},
        session_id=sess,
        step_index=4,
    )
    r4 = configured_latch.evaluate_proposal(p4)
    assert r4.admitted is True
    assert r4.metrics.domain_level == CapabilityDomain.FINANCIAL_DISPATCH
    assert configured_latch.is_tripped is False


# ==============================================================================
# 2. Excessive Domain Shift Velocity & Latch Tripping
# ==============================================================================

def test_excessive_domain_velocity_drift(configured_latch):
    """
    Evaluates direct capability leap from Domain 0 (READ_ONLY) to Domain 4 (FINANCIAL_DISPATCH).
    Verifies that HALT_PREDICTIVE_TRAJECTORY_DRIFT is triggered and latch transitions to tripped.
    """
    sess = "session-test-velocity-drift"

    p1 = ToolCallProposal(
        tool_name="lookup_balance",
        arguments={"account_id": "acct_001"},
        session_id=sess,
        step_index=1,
    )
    configured_latch.evaluate_proposal(p1)

    # Satisfy prerequisite out-of-band to specifically isolate velocity evaluation
    configured_latch.completed_actions_by_session[sess] = {"staged_escrow"}

    # Attempt leap from 0 directly to 4 (step jump = 4.0 > max_step_jump 2.0)
    p2 = ToolCallProposal(
        tool_name="wire_dispatch",
        arguments={"amount": 500000, "destination": "acct_dest_999"},
        session_id=sess,
        step_index=2,
    )

    with pytest.raises(PredictiveTrajectoryDriftError) as exc_info:
        configured_latch.evaluate_proposal(p2)

    assert exc_info.value.error_code == HALT_PREDICTIVE_TRAJECTORY_DRIFT
    assert configured_latch.is_tripped is True
    assert configured_latch.trip_reason["velocity_breach"] is True


def test_tripped_latch_rejects_all_subsequent_proposals(configured_latch):
    """
    Verifies fail-closed behavior: once tripped, any subsequent proposal is
    immediately rejected with HALT_LATCH_ALREADY_TRIPPED before dispatch.
    """
    configured_latch.is_tripped = True
    configured_latch.trip_reason = {"reason": "Evaluated synthetic trip"}

    prop = ToolCallProposal(
        tool_name="lookup_balance",
        arguments={"account_id": "acct_any"},
        session_id="session-subsequent",
        step_index=1,
    )

    with pytest.raises(LatchTrippedError) as exc_info:
        configured_latch.evaluate_proposal(prop)

    assert exc_info.value.error_code == HALT_LATCH_ALREADY_TRIPPED


# ==============================================================================
# 3. Homoglyph JSON Key Substitution Rejections
# ==============================================================================

def test_homoglyph_key_injection_rejection(configured_latch, fuzzer):
    """
    Evaluates rejection of JSON dictionary keys containing confusable
    Cyrillic characters (e.g. Cyrillic small 'а' in 'amount').
    """
    prop = ToolCallProposal(
        tool_name="lookup_balance",
        arguments={"account": "acct_test", "amount": 1000},
        session_id="session-homoglyph",
        step_index=1,
    )
    fuzzed = fuzzer.fuzz_proposal_homoglyph(prop, "amount")

    with pytest.raises(HomoglyphKeyInjectionError) as exc_info:
        configured_latch.evaluate_proposal(fuzzed)

    assert exc_info.value.error_code == HALT_HOMOGLYPH_KEY_INJECTION


def test_nested_homoglyph_key_injection(configured_latch):
    """Verifies that nested dictionary keys with homoglyphs are also caught."""
    # Key 'recipient' with Cyrillic small 'е' (\u0435)
    confusable_key = "r\u0435cipient"
    prop = ToolCallProposal(
        tool_name="staged_escrow",
        arguments={
            "transfer_meta": {
                confusable_key: "acct_target_555",
            },
            "amount": 100,
        },
        session_id="session-nested-homoglyph",
        step_index=1,
    )

    with pytest.raises(HomoglyphKeyInjectionError) as exc_info:
        configured_latch.evaluate_proposal(prop)

    assert exc_info.value.error_code == HALT_HOMOGLYPH_KEY_INJECTION


# ==============================================================================
# 4. Token Smuggling Ingress Filtering
# ==============================================================================

def test_zero_width_token_smuggling_rejection(configured_latch, fuzzer):
    """Evaluates rejection of invisible zero-width whitespace injected into string arguments."""
    prop = ToolCallProposal(
        tool_name="query_catalog",
        arguments={"query": "valid_search_string"},
        session_id="session-smuggle-zw",
        step_index=1,
    )
    fuzzed = fuzzer.fuzz_proposal_token_smuggling(prop, "zero_width")

    with pytest.raises(TokenSmugglingDetectedError) as exc_info:
        configured_latch.evaluate_proposal(fuzzed)

    assert exc_info.value.error_code == HALT_TOKEN_SMUGGLING_DETECTED


def test_unicode_tags_token_smuggling_rejection(configured_latch, fuzzer):
    """Evaluates rejection of Unicode Language Tag characters (U+E0001 - U+E007F)."""
    prop = ToolCallProposal(
        tool_name="search_knowledge",
        arguments={"term": "financial_policy"},
        session_id="session-smuggle-tags",
        step_index=1,
    )
    fuzzed = fuzzer.fuzz_proposal_token_smuggling(prop, "unicode_tags")

    with pytest.raises(TokenSmugglingDetectedError) as exc_info:
        configured_latch.evaluate_proposal(fuzzed)

    assert exc_info.value.error_code == HALT_TOKEN_SMUGGLING_DETECTED


def test_covert_base64_payload_smuggling_rejection(configured_latch, fuzzer):
    """Evaluates rejection of embedded covert base64 chunks hiding prohibited command keywords."""
    prop = ToolCallProposal(
        tool_name="read_file",
        arguments={"filepath": "/var/data/report.txt"},
        session_id="session-smuggle-b64",
        step_index=1,
    )
    fuzzed = fuzzer.fuzz_proposal_token_smuggling(prop, "base64_hidden")

    with pytest.raises(TokenSmugglingDetectedError) as exc_info:
        configured_latch.evaluate_proposal(fuzzed)

    assert exc_info.value.error_code == HALT_TOKEN_SMUGGLING_DETECTED


# ==============================================================================
# 5. Out-of-Order Execution Step Injections
# ==============================================================================

def test_out_of_order_execution_rejection(configured_latch, fuzzer):
    """
    Evaluates rejection when attempting wire_dispatch without staged_escrow
    completed in the session history.
    """
    ooo_prop = fuzzer.fuzz_proposal_out_of_order(
        tool_name="wire_dispatch", session_id="session-test-ooo"
    )

    with pytest.raises(OutOfOrderExecutionError) as exc_info:
        configured_latch.evaluate_proposal(ooo_prop)

    assert exc_info.value.error_code == HALT_OUT_OF_ORDER_EXECUTION


# ==============================================================================
# 6. Permission Entropy Acceleration Drift
# ==============================================================================

def test_permission_entropy_acceleration_drift():
    """
    Evaluates anomalous expansion across disjoint resource permissions.
    A sudden multi-permission spike causes entropy acceleration to exceed threshold.
    """
    latch = PredictiveTrajectoryDriftLatch(
        agent_id="agent-entropy-test",
        max_velocity_threshold=10.0,  # Isolate entropy check
        max_step_jump=10.0,
        max_entropy_acceleration=1.0,
    )
    sess = "session-entropy-spike"

    # Step 1: Baseline permission
    p1 = ToolCallProposal(
        tool_name="lookup_balance",
        arguments={"acct": "1"},
        session_id=sess,
        step_index=1,
        required_permissions={"account:read"},
    )
    latch.evaluate_proposal(p1)

    # Step 2: Another baseline permission
    p2 = ToolCallProposal(
        tool_name="lookup_balance",
        arguments={"acct": "2"},
        session_id=sess,
        step_index=2,
        required_permissions={"account:read"},
    )
    latch.evaluate_proposal(p2)

    # Step 3: Massive privilege scattering across 8 new disjoint domains
    disjoint_perms = {
        "pqc:rotate", "kernel:write", "firewall:write", "filesystem:write",
        "database:write", "sim:execute", "health:read", "code:read",
    }
    p3 = ToolCallProposal(
        tool_name="staged_escrow",
        arguments={"amount": 10},
        session_id=sess,
        step_index=3,
        required_permissions=disjoint_perms,
    )

    with pytest.raises(PredictiveTrajectoryDriftError) as exc_info:
        latch.evaluate_proposal(p3)

    assert exc_info.value.error_code == HALT_PREDICTIVE_TRAJECTORY_DRIFT
    assert latch.is_tripped is True
    assert latch.trip_reason["entropy_breach"] is True


# ==============================================================================
# 7. Supervisor Ed25519 Step-Up Warrant Reset Protocol
# ==============================================================================

def test_supervisor_step_up_warrant_reset(configured_latch, supervisor_keys):
    """
    Evaluates tripping the latch and successfully re-arming it using an
    authorized Ed25519 supervisor warrant under RFC 8785 JCS.
    """
    supervisor_priv, supervisor_pub = supervisor_keys

    # Trip latch deliberately
    configured_latch.is_tripped = True
    configured_latch.trip_reason = {"reason": "Evaluated manual trip for reset test"}

    now = int(time.time())
    warrant = {
        "action": "RESET_PREDICTIVE_TRAJECTORY_DRIFT",
        "created_at": now,
        "expires_at": now + 3600,
        "nonce": "nonce-warrant-8822",
        "reason": "Supervisor tested re-alignment",
        "supervisor_id": "supervisor-root",
        "target_agent_id": configured_latch.agent_id,
        "warrant_id": "warrant-stepup-42",
    }

    # Sign RFC 8785 canonical bytes
    canonical_bytes = encode_jcs(warrant)
    raw_sig = supervisor_priv.sign(canonical_bytes)
    warrant["signature"] = base64.b64encode(raw_sig).decode("ascii")

    # Reset latch
    res = configured_latch.reset_with_step_up_warrant(warrant, supervisor_pub)
    assert res is True
    assert configured_latch.is_tripped is False
    assert configured_latch.trip_reason is None

    # Verify subsequent nominal proposal is now admitted
    p = ToolCallProposal(
        tool_name="lookup_balance",
        arguments={"account_id": "acct_reset_ok"},
        session_id="session-post-reset",
        step_index=1,
    )
    rec = configured_latch.evaluate_proposal(p)
    assert rec.admitted is True


def test_supervisor_step_up_warrant_signature_tamper_fails(configured_latch, supervisor_keys):
    """Verifies that forged or tampered warrant signatures are rejected."""
    _, supervisor_pub = supervisor_keys
    configured_latch.is_tripped = True

    now = int(time.time())
    # Create warrant signed by unauthorized private key
    attacker_priv = ed25519.Ed25519PrivateKey.generate()
    warrant = {
        "action": "RESET_PREDICTIVE_TRAJECTORY_DRIFT",
        "created_at": now,
        "expires_at": now + 3600,
        "nonce": "nonce-forged-9999",
        "reason": "Attacker unauthorized bypass attempt",
        "supervisor_id": "supervisor-root",
        "target_agent_id": configured_latch.agent_id,
        "warrant_id": "warrant-forged-01",
    }
    canonical_bytes = encode_jcs(warrant)
    raw_sig = attacker_priv.sign(canonical_bytes)
    warrant["signature"] = base64.b64encode(raw_sig).decode("ascii")

    with pytest.raises(StepUpWarrantInvalidError) as exc_info:
        configured_latch.reset_with_step_up_warrant(warrant, supervisor_pub)

    assert exc_info.value.error_code == HALT_STEP_UP_WARRANT_INVALID
    assert configured_latch.is_tripped is True


def test_supervisor_step_up_warrant_expiration_fails(configured_latch, supervisor_keys):
    """Verifies that expired warrants fail closed."""
    supervisor_priv, supervisor_pub = supervisor_keys
    configured_latch.is_tripped = True

    now = int(time.time())
    warrant = {
        "action": "RESET_PREDICTIVE_TRAJECTORY_DRIFT",
        "created_at": now - 7200,
        "expires_at": now - 100,  # In the past
        "nonce": "nonce-expired-1111",
        "reason": "Old warrant replayed",
        "supervisor_id": "supervisor-root",
        "target_agent_id": configured_latch.agent_id,
        "warrant_id": "warrant-expired-01",
    }
    canonical_bytes = encode_jcs(warrant)
    raw_sig = supervisor_priv.sign(canonical_bytes)
    warrant["signature"] = base64.b64encode(raw_sig).decode("ascii")

    with pytest.raises(StepUpWarrantInvalidError) as exc_info:
        configured_latch.reset_with_step_up_warrant(warrant, supervisor_pub, now_ts=now)

    assert exc_info.value.error_code == HALT_STEP_UP_WARRANT_INVALID


# ==============================================================================
# 8. Multi-Vector Chaos Fuzzer Campaign
# ==============================================================================

def test_adversarial_chaos_fuzzer_campaign(configured_latch, fuzzer):
    """
    Executes multi-round fuzzing campaign across all perturbation vectors.
    Verifies that all injected adversarial variants are trapped fail-closed.
    """
    rounds = 15
    results = fuzzer.run_fuzz_campaign(configured_latch, rounds=rounds)
    catches = results["catches"]

    assert catches[HALT_HOMOGLYPH_KEY_INJECTION] == rounds
    assert catches[HALT_TOKEN_SMUGGLING_DETECTED] == rounds
    assert catches[HALT_OUT_OF_ORDER_EXECUTION] == rounds
    assert catches[HALT_PREDICTIVE_TRAJECTORY_DRIFT] == rounds
    assert results["total_adversarial_evaluations"] == rounds * 4


# ==============================================================================
# 9. CLI Self-Test Execution
# ==============================================================================

def test_cli_self_test():
    """Verifies that the module-level run_self_test and CLI execute cleanly."""
    res = run_self_test()
    assert res is True

    # Execute as subprocess to verify CLI exit code
    script_path = str(Path(__file__).resolve().parent.parent / "src" / "predictive_trajectory_drift_latch.py")
    cmd = [sys.executable, script_path, "--self-test"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0
    assert "Self-test completed" in proc.stdout


# ==============================================================================
# 10. Strict Banned-Word Compliance Audit
# ==============================================================================

def test_banned_words_audit_on_owned_files():
    """
    Scans all owned files for forbidden promotional terms per AGENTS.md.
    Uses runtime string concatenation for search targets to avoid false matches.
    """
    repo_root = Path(__file__).resolve().parent.parent
    owned_files = [
        repo_root / "src" / "predictive_trajectory_drift_latch.py",
        repo_root / "tests" / "test_predictive_trajectory_drift_latch.py",
        repo_root / "docs" / "architecture" / "PREDICTIVE_TRAJECTORY_DRIFT_AND_CHAOS_FUZZER.md",
    ]

    # Dynamically constructed forbidden terms
    forbidden = [
        "guaran" + "tee",
        "guaran" + "teed",
        "guaran" + "tees",
        "guaran" + "teeing",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "unassail" + "able",
        "im" + "mune",
        "unhack" + "able",
        "bank-" + "grade",
        "production-" + "ready",
        "proven universal" + "ly",
    ]

    violations: Dict[str, list[str]] = {}

    for file_path in owned_files:
        assert file_path.is_file(), f"Expected owned file {file_path} exists"
        content = file_path.read_text(encoding="utf-8").lower()
        file_violations = []
        for term in forbidden:
            # Check for term as whole word or phrase, ignoring the test definition itself
            if term in content:
                # If checking this test file, ignore occurrences in this audit test
                if file_path.name == "test_predictive_trajectory_drift_latch.py":
                    # Count occurrences outside the forbidden list definition
                    lines = [line for line in content.splitlines() if "guaran" not in line and "bullet" not in line]
                    if any(term in line for line in lines):
                        file_violations.append(term)
                else:
                    file_violations.append(term)

        if file_violations:
            violations[str(file_path)] = file_violations

    assert not violations, f"Banned word violations detected: {violations}"
