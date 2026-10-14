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
tests/test_governed_financial_action_boundary.py
================================================================================
Comprehensive unit & integration test suite for the AEIB Governed Financial Action Boundary.
Evaluates the 7 Core Controls (P0 Core) under positive, negative, and fault-injection cases.
"""

import sys
import json
import pytest
from pathlib import Path

# Add project root and roadmap to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "v1.1-roadmap"))

from governed_financial_action_boundary import (
    FinancialCandidateAction,
    GovernedFinancialActionBoundary,
    RealisticPaymentSimulator,
    FinancialReceiptOfflineVerifier,
    DISPOSITION_ALLOW,
    DISPOSITION_DENY,
    DISPOSITION_STEP_UP,
    DISPOSITION_CONFIRMED,
    DISPOSITION_REFUTED,
    DISPOSITION_EFFECT_INDETERMINATE,
    DISPOSITION_RECONCILIATION_CONFLICT,
    DISPOSITION_PRESERVED_UNCERTAINTY
)


@pytest.fixture
def boundary_setup(tmp_path):
    storage_dir = tmp_path / "financial_boundary_storage"
    boundary = GovernedFinancialActionBoundary(
        base_dir=storage_dir,
        active_policy_epoch=1,
        probe_budget=1
    )
    payment_sim = RealisticPaymentSimulator()
    return boundary, payment_sim, storage_dir


def test_01_exact_action_authorization_valid(boundary_setup):
    boundary, _, _ = boundary_setup

    candidate = FinancialCandidateAction(
        action_id="act_refund_001",
        principal="did:key:z6MkpTHRexample",
        target_uri="https://api.bank.internal/v1/payments/refunds",
        operation_type="customer_refund",
        parameters={
            "customer_id": "cust_101",
            "payment_id": "pay_505",
            "amount_cents": 15000,  # 150.00 EUR
            "currency": "EUR",
            "reason": "customer_return",
            "_reasoning": "The customer requested a refund because the item was late."
        },
        policy_epoch=1,
        source_epoch=10
    )

    is_auth, reason, ticket = boundary.authorize_action(candidate)
    assert is_auth is True
    assert reason == "AUTHORIZED"
    assert ticket is not None
    assert ticket.ticket_id.startswith("ticket_auth_")
    assert ticket.consumed is False
    assert len(ticket.signature_hex) > 0


def test_02_dead_salmons_filter_removes_ephemeral_thoughts(boundary_setup):
    boundary, _, _ = boundary_setup

    candidate_with_thoughts = FinancialCandidateAction(
        action_id="act_refund_002",
        principal="agent:support_bot",
        target_uri="https://api.bank.internal/v1/payments/refunds",
        operation_type="customer_refund",
        parameters={
            "amount_cents": 5000,
            "currency": "EUR",
            "_reasoning": "Step 1: check balance. Step 2: approve refund.",
            "chain_of_thought": "Thinking about whether this violates policy...",
            "rationale": "High priority client"
        },
        policy_epoch=1,
        source_epoch=10
    )

    canonical_payload = candidate_with_thoughts.extract_canonical_payload()
    assert "_reasoning" not in canonical_payload["parameters"]
    assert "chain_of_thought" not in canonical_payload["parameters"]
    assert "rationale" not in canonical_payload["parameters"]
    assert canonical_payload["parameters"]["amount_cents"] == 5000


def test_03_stale_policy_epoch_rejected_fail_closed(boundary_setup):
    boundary, _, _ = boundary_setup

    candidate = FinancialCandidateAction(
        action_id="act_refund_stale",
        principal="agent:support_bot",
        target_uri="https://api.bank.internal/v1/payments/refunds",
        operation_type="customer_refund",
        parameters={"amount_cents": 2000, "currency": "EUR"},
        policy_epoch=0,  # Stale: active epoch is 1
        source_epoch=10
    )

    is_auth, reason, ticket = boundary.authorize_action(candidate)
    assert is_auth is False
    assert "STALE_POLICY_EPOCH" in reason
    assert ticket is None


def test_04_target_allowlist_violation_rejected(boundary_setup):
    boundary, _, _ = boundary_setup

    candidate = FinancialCandidateAction(
        action_id="act_refund_unauthorized_target",
        principal="agent:support_bot",
        target_uri="https://unauthorized.evil.target/refund",
        operation_type="customer_refund",
        parameters={"amount_cents": 2000, "currency": "EUR"},
        policy_epoch=1,
        source_epoch=10
    )

    is_auth, reason, ticket = boundary.authorize_action(candidate)
    assert is_auth is False
    assert "TARGET_NOT_ALLOWED" in reason
    assert ticket is None


def test_05_amount_ceiling_triggers_step_up_dual_control(boundary_setup):
    boundary, _, _ = boundary_setup

    candidate = FinancialCandidateAction(
        action_id="act_refund_high_value",
        principal="agent:support_bot",
        target_uri="https://api.bank.internal/v1/payments/refunds",
        operation_type="customer_refund",
        parameters={"amount_cents": 1000000, "currency": "EUR"},  # 10,000 EUR > 5,000 EUR ceiling
        policy_epoch=1,
        source_epoch=10,
        max_amount_cents_limit=500000
    )

    is_auth, reason, ticket = boundary.authorize_action(candidate)
    assert is_auth is False
    assert "STEP_UP" in reason
    assert ticket is None


def test_06_single_use_authority_burn_and_replay_prevention(boundary_setup):
    boundary, payment_sim, _ = boundary_setup

    candidate = FinancialCandidateAction(
        action_id="act_refund_single_use",
        principal="agent:support_bot",
        target_uri="https://api.bank.internal/v1/payments/refunds",
        operation_type="customer_refund",
        parameters={"amount_cents": 2000, "currency": "EUR"},
        policy_epoch=1,
        source_epoch=10
    )

    _, _, ticket = boundary.authorize_action(candidate)

    # First dispatch: burns ticket and completes cleanly
    receipt1 = boundary.execute_governed_action(candidate, ticket, payment_sim)
    assert receipt1.disposition == DISPOSITION_CONFIRMED

    # Second dispatch with identical ticket: rejected as already burned
    receipt2 = boundary.execute_governed_action(candidate, ticket, payment_sim)
    assert receipt2.disposition == DISPOSITION_DENY
    assert receipt2.downstream_commit_count == 0


def test_07_normal_target_rejection_no_commit(boundary_setup):
    boundary, payment_sim, _ = boundary_setup
    payment_sim.set_dispatch_mode(payment_sim.DISPATCH_NORMAL_REJECTION)

    candidate = FinancialCandidateAction(
        action_id="act_refund_target_rejected",
        principal="agent:support_bot",
        target_uri="https://api.bank.internal/v1/payments/refunds",
        operation_type="customer_refund",
        parameters={"amount_cents": 2000, "currency": "EUR"},
        policy_epoch=1,
        source_epoch=10
    )

    _, _, ticket = boundary.authorize_action(candidate)
    receipt = boundary.execute_governed_action(candidate, ticket, payment_sim)

    assert receipt.disposition == DISPOSITION_DENY
    assert receipt.downstream_commit_count == 0
    assert payment_sim.ledger.get_commit_count("act_refund_target_rejected") == 0


def test_08_http_504_reconciles_to_confirmed_under_probe_budget_1(boundary_setup):
    boundary, payment_sim, _ = boundary_setup
    payment_sim.set_dispatch_mode(payment_sim.DISPATCH_HTTP_504)
    payment_sim.set_probe_mode(payment_sim.PROBE_NORMAL)

    candidate = FinancialCandidateAction(
        action_id="act_refund_504_reconciled",
        principal="agent:support_bot",
        target_uri="https://api.bank.internal/v1/payments/refunds",
        operation_type="customer_refund",
        parameters={"amount_cents": 4500, "currency": "EUR"},
        policy_epoch=1,
        source_epoch=10
    )

    _, _, ticket = boundary.authorize_action(candidate)
    receipt = boundary.execute_governed_action(candidate, ticket, payment_sim)

    # Wire dropped, but probe reconciled to CONFIRMED
    assert receipt.disposition == DISPOSITION_CONFIRMED
    assert receipt.retry_safe is False
    assert receipt.reconciliation_attempts == 1
    assert receipt.downstream_commit_count == 1
    assert payment_sim.ledger.get_commit_count("act_refund_504_reconciled") == 1


def test_09_tcp_rst_reconciles_to_confirmed(boundary_setup):
    boundary, payment_sim, _ = boundary_setup
    payment_sim.set_dispatch_mode(payment_sim.DISPATCH_TCP_RST)
    payment_sim.set_probe_mode(payment_sim.PROBE_NORMAL)

    candidate = FinancialCandidateAction(
        action_id="act_refund_tcp_rst",
        principal="agent:support_bot",
        target_uri="https://api.bank.internal/v1/payments/refunds",
        operation_type="customer_refund",
        parameters={"amount_cents": 7500, "currency": "EUR"},
        policy_epoch=1,
        source_epoch=10
    )

    _, _, ticket = boundary.authorize_action(candidate)
    receipt = boundary.execute_governed_action(candidate, ticket, payment_sim)

    assert receipt.disposition == DISPOSITION_CONFIRMED
    assert receipt.reconciliation_attempts == 1
    assert receipt.downstream_commit_count == 1


def test_10_target_status_outage_preserves_uncertainty_no_blind_retry(boundary_setup):
    boundary, payment_sim, _ = boundary_setup
    payment_sim.set_dispatch_mode(payment_sim.DISPATCH_HTTP_504)
    payment_sim.set_probe_mode(payment_sim.PROBE_OUTAGE)

    candidate = FinancialCandidateAction(
        action_id="act_refund_oracle_outage",
        principal="agent:support_bot",
        target_uri="https://api.bank.internal/v1/payments/refunds",
        operation_type="customer_refund",
        parameters={"amount_cents": 1200, "currency": "EUR"},
        policy_epoch=1,
        source_epoch=10
    )

    _, _, ticket = boundary.authorize_action(candidate)
    receipt = boundary.execute_governed_action(candidate, ticket, payment_sim)

    # Uncertainty MUST be preserved fail-closed; retry must NEVER be marked safe
    assert receipt.disposition == DISPOSITION_PRESERVED_UNCERTAINTY
    assert receipt.retry_safe is False
    assert receipt.reconciliation_attempts == 1


def test_11_conflicting_target_status_yields_reconciliation_conflict(boundary_setup):
    boundary, payment_sim, _ = boundary_setup
    payment_sim.set_dispatch_mode(payment_sim.DISPATCH_HTTP_504)
    payment_sim.set_probe_mode(payment_sim.PROBE_CONFLICT)

    candidate = FinancialCandidateAction(
        action_id="act_refund_conflict",
        principal="agent:support_bot",
        target_uri="https://api.bank.internal/v1/payments/refunds",
        operation_type="customer_refund",
        parameters={"amount_cents": 3300, "currency": "EUR"},
        policy_epoch=1,
        source_epoch=10
    )

    _, _, ticket = boundary.authorize_action(candidate)
    receipt = boundary.execute_governed_action(candidate, ticket, payment_sim)

    # Contradictory evidence detected on target -> RECONCILIATION_CONFLICT
    assert receipt.disposition == DISPOSITION_RECONCILIATION_CONFLICT
    assert receipt.retry_safe is False


def test_12_verifiable_operation_bound_receipt_offline_verification(boundary_setup):
    boundary, payment_sim, _ = boundary_setup

    candidate = FinancialCandidateAction(
        action_id="act_refund_receipt_verify",
        principal="agent:support_bot",
        target_uri="https://api.bank.internal/v1/payments/refunds",
        operation_type="customer_refund",
        parameters={"amount_cents": 9900, "currency": "EUR"},
        policy_epoch=1,
        source_epoch=10
    )

    _, _, ticket = boundary.authorize_action(candidate)
    receipt = boundary.execute_governed_action(candidate, ticket, payment_sim)

    # 1. Verify authentic receipt
    is_valid, err = FinancialReceiptOfflineVerifier.verify_receipt(receipt)
    assert is_valid is True
    assert err is None

    # 2. Tamper with receipt payload -> verification fails
    receipt.disposition = "TAMPERED_DISPOSITION"
    is_valid_tampered, err_tampered = FinancialReceiptOfflineVerifier.verify_receipt(receipt)
    assert is_valid_tampered is False
    assert "VERIFICATION_FAILED" in err_tampered


def test_13_crash_recovery_resynchronization(boundary_setup):
    boundary, payment_sim, _ = boundary_setup

    candidate = FinancialCandidateAction(
        action_id="act_refund_crash_recovery",
        principal="agent:support_bot",
        target_uri="https://api.bank.internal/v1/payments/refunds",
        operation_type="customer_refund",
        parameters={"amount_cents": 6200, "currency": "EUR"},
        policy_epoch=1,
        source_epoch=10
    )

    _, _, ticket = boundary.authorize_action(candidate)

    # Simulate process crash during dispatch
    with pytest.raises(SystemExit):
        boundary.execute_governed_action(candidate, ticket, payment_sim, crash_point="DURING_DISPATCH")

    # Restart boundary from persistent journal
    resolutions = boundary.recover_from_crash(payment_sim)
    assert len(resolutions) == 1
    assert resolutions[0]["action_id"] == "act_refund_crash_recovery"
    assert resolutions[0]["status"] == "RECOVERED"
    assert resolutions[0]["disposition"] == DISPOSITION_CONFIRMED
    assert resolutions[0]["downstream_commit_count"] == 1
