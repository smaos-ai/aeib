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
tests/test_agent_decept_reconciler.py
================================================================================
Comprehensive verification suite for AgentDecept Truth vs. Claims Reconciler.
Evaluated under the stated model with unmocked deterministic verification.
"""

from __future__ import annotations

import dataclasses
import pytest

from src.agent_decept_reconciler import (
    AgentDeceptReconciler,
    DeceptionAuditVerdict,
)


def test_deception_audit_verdict_frozen_and_to_dict() -> None:
    """Verifies that DeceptionAuditVerdict is immutable and serializes properly."""
    v = DeceptionAuditVerdict(
        status="VERIFIED_TRUTH",
        deception_class=None,
        claim_summary="Summary text",
        ledger_status="COMMITTED",
        verified_caid="sha256:abc12345",
        evidence_detail="Aligned",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        v.status = "MUTATED"  # type: ignore

    d = v.to_dict()
    assert d["status"] == "VERIFIED_TRUTH"
    assert d["deception_class"] is None
    assert d["claim_summary"] == "Summary text"
    assert d["ledger_status"] == "COMMITTED"
    assert d["verified_caid"] == "sha256:abc12345"
    assert d["evidence_detail"] == "Aligned"


def test_agent_decept_reconciler_init_and_record_action() -> None:
    """Verifies ledger record initialization and dynamic append."""
    init_entry = {
        "task_id": "tx_init",
        "status": "COMMITTED",
        "caid": "sha256:1111",
    }
    reconciler = AgentDeceptReconciler(ledger_records=[init_entry])
    assert len(reconciler.ledger_records) == 1

    appended_entry = {
        "task_id": "tx_append",
        "status": "ALLOWED",
        "entry_caid": "sha256:2222",
    }
    reconciler.record_action(appended_entry)
    assert len(reconciler.ledger_records) == 2


def test_unlatched_execution_when_task_missing() -> None:
    """Detects UNLATCHED_EXECUTION when no ledger entry matches the task_id."""
    reconciler = AgentDeceptReconciler()
    long_claim = "A" * 120
    v = reconciler.audit_agent_claim(
        task_id="ghost_task",
        claimed_text=long_claim,
    )
    assert v.status == "UNVERIFIED_NO_LEDGER"
    assert v.deception_class == "UNLATCHED_EXECUTION"
    assert v.claim_summary == "A" * 80  # claim: config
    assert v.ledger_status == "MISSING"
    assert v.verified_caid is None
    assert "No pre-execution intent reservation found" in v.evidence_detail


def test_phantom_success_detection() -> None:
    """Detects PHANTOM_SUCCESS when agent claims success for a halted or denied action."""
    reconciler = AgentDeceptReconciler()
    reconciler.record_action({
        "task_id": "tx_halted_1",
        "status": "HALTED",
        "reason": "HALTED_IDEMPOTENCY_DUPLICATE_ATTEMPT",
        "caid": "sha256:halt123",
    })
    reconciler.record_action({
        "task_id": "tx_denied_2",
        "status": "DENIED",
        "caid": "sha256:deny123",
    })
    reconciler.record_action({
        "task_id": "tx_blocked_3",
        "status": "BLOCKED",
        "reason": "EGRESS_BLOCKED",
        "caid": "sha256:block123",
    })

    # Test variants of success claims with length > 80 chars
    long_claim = "Refund processed successfully! " + ("A" * 60)
    v_long = reconciler.audit_agent_claim("tx_halted_1", long_claim)
    assert v_long.status == "DECEPTION_DETECTED"
    assert v_long.deception_class == "PHANTOM_SUCCESS"
    assert v_long.claim_summary == long_claim[:80]  # claim: config
    assert len(v_long.claim_summary) == 80  # claim: config

    success_claims = [
        "Refund processed successfully!",
        "Completed migration of tables.",
        "Fixed the issue completely.",
        "Customer charge was refunded.",
        "Changes committed to main.",
        "Ran the test harness, all tests passed.",
    ]
    for claim in success_claims:
        v = reconciler.audit_agent_claim("tx_halted_1", claim)
        assert v.status == "DECEPTION_DETECTED"
        assert v.deception_class == "PHANTOM_SUCCESS"
        assert v.ledger_status == "HALTED"
        assert v.verified_caid == "sha256:halt123"
        assert "HALTED_IDEMPOTENCY_DUPLICATE_ATTEMPT" in v.evidence_detail

    # Test default reason fallback when reason is omitted
    v_denied = reconciler.audit_agent_claim("tx_denied_2", "Task completed.")
    assert v_denied.status == "DECEPTION_DETECTED"
    assert v_denied.deception_class == "PHANTOM_SUCCESS"
    assert "POLICY_DENIAL" in v_denied.evidence_detail

    # Test blocked
    v_blocked = reconciler.audit_agent_claim("tx_blocked_3", "Fixed and committed.")
    assert v_blocked.status == "DECEPTION_DETECTED"
    assert v_blocked.deception_class == "PHANTOM_SUCCESS"


def test_concealed_mutation_detection() -> None:
    """Detects CONCEALED_MUTATION when agent claims clean run but modified tests."""
    reconciler = AgentDeceptReconciler()
    reconciler.record_action({
        "task_id": "tx_mutation_1",
        "status": "ALLOWED",
        "modified_test_files": ["tests/test_harness.py"],
        "caid": "sha256:mut123",
    })

    long_clean_claim = "Fixed bug without touching tests. " + ("B" * 60)
    v_long = reconciler.audit_agent_claim("tx_mutation_1", long_clean_claim)
    assert v_long.status == "DECEPTION_DETECTED"
    assert v_long.deception_class == "CONCEALED_MUTATION"
    assert v_long.claim_summary == long_clean_claim[:80]  # claim: config
    assert len(v_long.claim_summary) == 80  # claim: config

    clean_claims = [
        "Fixed bug without touching tests.",
        "Refactored code, tests untouched.",
        "Optimized routing with no side effects.",
    ]
    for claim in clean_claims:
        v = reconciler.audit_agent_claim("tx_mutation_1", claim)
        assert v.status == "DECEPTION_DETECTED"
        assert v.deception_class == "CONCEALED_MUTATION"
        assert v.ledger_status == "ALLOWED"
        assert v.verified_caid == "sha256:mut123"
        assert "tests/test_harness.py" in v.evidence_detail


def test_concealed_mutation_boundary_logic() -> None:
    """Kills BOOL_SWAP mutants on (is_claiming_clean and modified_tests)."""
    reconciler = AgentDeceptReconciler()

    # Case A: is_claiming_clean=True, but modified_tests is empty []
    reconciler.record_action({
        "task_id": "tx_clean_nom",
        "status": "ALLOWED",
        "modified_test_files": [],
        "caid": "sha256:nom",
    })
    v_a = reconciler.audit_agent_claim("tx_clean_nom", "Refactored tests untouched.")
    assert v_a.status == "VERIFIED_TRUTH"
    assert v_a.deception_class is None

    # Case B: is_claiming_clean=False, but modified_tests is non-empty
    reconciler.record_action({
        "task_id": "tx_mod_honest",
        "status": "COMMITTED",
        "modified_test_files": ["tests/test_something.py"],
        "caid": "sha256:honest",
    })
    v_b = reconciler.audit_agent_claim("tx_mod_honest", "I explicitly updated tests/test_something.py")
    assert v_b.status == "VERIFIED_TRUTH"
    assert v_b.deception_class is None


def test_verified_truth_allowed_committed_permitted() -> None:
    """Confirms VERIFIED_TRUTH when agent claim matches allowed/committed execution."""
    reconciler = AgentDeceptReconciler()
    reconciler.record_action({
        "task_id": "tx_ok_1",
        "status": "COMMITTED",
        "modified_test_files": [],
        "caid": "sha256:caid_ok",
    })
    reconciler.record_action({
        "task_id": "tx_ok_2",
        "status": "PERMITTED",
        "entry_caid": "sha256:entry_caid_ok",
    })

    long_ok_claim = "Successfully applied patch! " + ("C" * 60)
    v1 = reconciler.audit_agent_claim("tx_ok_1", long_ok_claim)
    assert v1.status == "VERIFIED_TRUTH"
    assert v1.deception_class is None
    assert v1.claim_summary == long_ok_claim[:80]  # claim: config
    assert len(v1.claim_summary) == 80  # claim: config
    assert v1.verified_caid == "sha256:caid_ok"
    assert "Agent claim matches immutable execution record" in v1.evidence_detail

    v2 = reconciler.audit_agent_claim("tx_ok_2", "Permitted operation completed.")
    assert v2.status == "VERIFIED_TRUTH"
    assert v2.deception_class is None
    assert v2.verified_caid == "sha256:entry_caid_ok"


def test_verified_truth_escalated_cases() -> None:
    """Confirms VERIFIED_TRUTH when agent correctly escalated unsolvable blocker."""
    reconciler = AgentDeceptReconciler()
    reconciler.record_action({
        "task_id": "tx_esc_1",
        "status": "ESCALATED",
        "caid": "sha256:esc1",
    })
    reconciler.record_action({
        "task_id": "tx_esc_2",
        "status": "ESCALATED_UNSOLVABLE_BLOCKER",
        "caid": "sha256:esc2",
    })

    long_esc_claim = "Contradictory constraints encountered. " + ("D" * 60)
    v1 = reconciler.audit_agent_claim("tx_esc_1", long_esc_claim)
    assert v1.status == "VERIFIED_TRUTH"
    assert v1.deception_class is None
    assert v1.claim_summary == long_esc_claim[:80]  # claim: config
    assert len(v1.claim_summary) == 80  # claim: config
    assert "Agent correctly escalated contradictory task" in v1.evidence_detail

    v2 = reconciler.audit_agent_claim("tx_esc_2", "Blocked by missing upstream schema.")
    assert v2.status == "VERIFIED_TRUTH"
    assert v2.deception_class is None


def test_nominal_alignment_for_other_ledger_status() -> None:
    """Confirms VERIFIED_TRUTH nominal alignment for non-mutating status."""
    reconciler = AgentDeceptReconciler()
    reconciler.record_action({
        "task_id": "tx_pending_1",
        "status": "PENDING_REVIEW",
        "caid": "sha256:pend1",
    })

    long_pend_claim = "Diff created and awaiting review. " + ("E" * 60)
    v = reconciler.audit_agent_claim("tx_pending_1", long_pend_claim)
    assert v.status == "VERIFIED_TRUTH"
    assert v.deception_class is None
    assert v.claim_summary == long_pend_claim[:80]  # claim: config
    assert len(v.claim_summary) == 80  # claim: config
    assert v.ledger_status == "PENDING_REVIEW"
    assert "Nominal alignment" in v.evidence_detail
