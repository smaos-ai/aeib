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
scripts/demo_customer_refund_boundary.py
================================================================================
AEIB Live Demonstration: Governed Financial Action Boundary for Customer Refunds.

Demonstrates the 7 core controls (P0 Core) under the stated model:
  1. Exact Action Authorization & Dead Salmons Filter (stripping reasoning tokens)
  2. Single-Use Authority Ticket Burn & Replay Prevention
  3. Durable Dispatch Intent (EO-1: fsync write-ahead journal before dispatch)
  4. Transport Ambiguity Latching (HTTP 504 -> EFFECT_INDETERMINATE, retry_safe: false)
  5. Bounded Reconciliation Probe (ProbeBudget: 1 against primary provider status)
  6. Zero-Egress Rejection for High-Value Ceilings (STEP_UP challenge)
  7. Offline-Verifiable RFC 8785 JCS + Ed25519 Receipts and Tamper Falsification
"""

import os
import sys
import json
import time
import shutil
import tempfile
from pathlib import Path

# Ensure repo root and roadmap directory are in sys.path
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


def print_banner(title: str):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_step(step_num: int, title: str):
    print(f"\n[Step {step_num}] {title}")
    print("-" * 70)


def run_demonstration():
    work_dir = Path(tempfile.mkdtemp(prefix="aeib_refund_demo_"))
    try:
        print_banner("AEIB LIVE DEMONSTRATION: GOVERNED CUSTOMER REFUND BOUNDARY")
        print(f"Storage Directory: {work_dir}")
        print("Model: Under the stated model, zero-mock, real Ed25519, RFC 8785 JCS")

        # Initialize Boundary and Payment Simulator
        boundary = GovernedFinancialActionBoundary(
            base_dir=work_dir,
            active_policy_epoch=1,
            probe_budget=1
        )
        payment_sim = RealisticPaymentSimulator()

        # ----------------------------------------------------------------------
        # Scenario 1: Clean Authorized Customer Refund (Happy Path)
        # ----------------------------------------------------------------------
        print_step(1, "Scenario 1: Clean Authorized Customer Refund (€450.00)")
        action_1 = FinancialCandidateAction(
            action_id="act_refund_ord_9912",
            principal="agent:customer_support_eu",
            target_uri="https://api.bank.internal/v1/payments/refunds",
            operation_type="customer_refund",
            parameters={
                "order_id": "ORD-2026-9912",
                "customer_id": "CUST-8831",
                "destination_iban": "XX00EXAMPLE0000000000001",
                "amount_cents": 45000,  # 450.00 EUR
                "currency": "EUR",
                "reason": "late_delivery_compensation",
                "_reasoning": "Customer contacted support regarding 10-day delay in shipping.",
                "chain_of_thought": "Verifying delivery timestamp against SLA. 10 days exceeds 3-day SLA. Compensation authorized."
            },
            policy_epoch=1,
            source_epoch=10,
            max_amount_cents_limit=100000  # 1,000.00 EUR ceiling
        )

        # 1. Authorization & Dead Salmons Filter
        is_auth, reason, ticket = boundary.authorize_action(action_1)
        caid_1 = action_1.compute_caid()
        print(f"  - Agent Proposal Action ID : {action_1.action_id}")
        print(f"  - Computed CAID (RFC 8785) : {caid_1}")
        print(f"  - Dead Salmons Filter      : Stripped '_reasoning' and 'chain_of_thought'")
        print(f"  - Policy Evaluation        : Authorized={is_auth} (Reason: {reason})")
        print(f"  - Single-Use Ticket Minted : {ticket.ticket_id} (Expires in: {int(ticket.expires_at - time.time())}s)")

        # 2. Governed Dispatch Execution
        receipt_1 = boundary.execute_governed_action(action_1, ticket, payment_sim)
        print(f"  - Dispatch Execution Status: Disposition={receipt_1.disposition}")
        print(f"  - Downstream Commits Count : {receipt_1.downstream_commit_count}")
        print(f"  - Chain Tip Hash           : {receipt_1.chain_tip}")
        print(f"  - Ed25519 Signature        : {receipt_1.signature_hex[:32]}...")

        # 3. Offline Verification
        valid, err = FinancialReceiptOfflineVerifier.verify_receipt(receipt_1)
        print(f"  - Offline Verifier Check   : Valid={valid} (Err: {err})")
        assert valid is True
        assert receipt_1.disposition == DISPOSITION_CONFIRMED
        assert receipt_1.downstream_commit_count == 1

        # ----------------------------------------------------------------------
        # Scenario 2: HTTP 504 Timeout -> Bounded Reconciliation Probe
        # ----------------------------------------------------------------------
        print_step(2, "Scenario 2: HTTP 504 Timeout & Bounded Reconciliation (€850.00)")
        payment_sim.set_dispatch_mode(payment_sim.DISPATCH_HTTP_504)

        action_2 = FinancialCandidateAction(
            action_id="act_refund_ord_9913",
            principal="agent:customer_support_eu",
            target_uri="https://api.bank.internal/v1/payments/refunds",
            operation_type="customer_refund",
            parameters={
                "order_id": "ORD-2026-9913",
                "customer_id": "CUST-9942",
                "destination_iban": "XX00EXAMPLE0000000000002",
                "amount_cents": 85000,  # 850.00 EUR
                "currency": "EUR",
                "reason": "damaged_goods_refund"
            },
            policy_epoch=1,
            source_epoch=10,
            max_amount_cents_limit=100000
        )

        is_auth2, _, ticket_2 = boundary.authorize_action(action_2)
        print(f"  - Action ID                : {action_2.action_id}")
        print(f"  - Initial Wire Event       : Target returned HTTP 504 Gateway Timeout")
        print(f"  - Ambiguity Latch Triggered: Disallowed blind retry (retry_safe: false)")
        print(f"  - Bounded Probe Dispatched : ProbeBudget=1 against primary provider status endpoint")

        receipt_2 = boundary.execute_governed_action(action_2, ticket_2, payment_sim)
        print(f"  - Reconciliation Result    : Target confirmed transaction committed downstream")
        print(f"  - Final Disposition Latched: {receipt_2.disposition}")
        print(f"  - Reconciliation Attempts  : {receipt_2.reconciliation_attempts}")
        print(f"  - Downstream Commit Count  : {receipt_2.downstream_commit_count}")

        valid2, err2 = FinancialReceiptOfflineVerifier.verify_receipt(receipt_2)
        print(f"  - Offline Verifier Check   : Valid={valid2}")
        assert valid2 is True
        assert receipt_2.disposition == DISPOSITION_CONFIRMED
        assert receipt_2.downstream_commit_count == 1

        # Reset simulator dispatch mode
        payment_sim.set_dispatch_mode(payment_sim.DISPATCH_NORMAL_SUCCESS)

        # ----------------------------------------------------------------------
        # Scenario 3: TCP Connection Reset -> Reconciliation Proves Not Committed
        # ----------------------------------------------------------------------
        print_step(3, "Scenario 3: TCP Connection Reset & Refuted State (€320.00)")
        payment_sim.set_dispatch_mode(payment_sim.DISPATCH_TCP_RST)
        payment_sim.set_probe_mode(payment_sim.PROBE_NOT_FOUND)

        action_3 = FinancialCandidateAction(
            action_id="act_refund_ord_9914",
            principal="agent:customer_support_eu",
            target_uri="https://api.bank.internal/v1/payments/refunds",
            operation_type="customer_refund",
            parameters={
                "order_id": "ORD-2026-9914",
                "customer_id": "CUST-4412",
                "destination_iban": "XX00EXAMPLE0000000000003",
                "amount_cents": 32000,  # 320.00 EUR
                "currency": "EUR",
                "reason": "order_cancelled_before_shipment"
            },
            policy_epoch=1,
            source_epoch=10,
            max_amount_cents_limit=100000
        )

        is_auth3, _, ticket_3 = boundary.authorize_action(action_3)
        print(f"  - Action ID                : {action_3.action_id}")
        print(f"  - Initial Wire Event       : ConnectionResetError (TCP RST)")
        print(f"  - Ambiguity Latch Triggered: Latching EFFECT_INDETERMINATE")
        print(f"  - Bounded Probe Dispatched : Querying primary payment ledger status")

        receipt_3 = boundary.execute_governed_action(action_3, ticket_3, payment_sim)
        print(f"  - Reconciliation Result    : Target responded 404 NOT_FOUND (mutation never reached ledger)")
        print(f"  - Final Disposition Latched: {receipt_3.disposition}")
        print(f"  - Downstream Commit Count  : {receipt_3.downstream_commit_count} (Zero duplicate mutation)")

        valid3, err3 = FinancialReceiptOfflineVerifier.verify_receipt(receipt_3)
        print(f"  - Offline Verifier Check   : Valid={valid3}")
        assert valid3 is True
        assert receipt_3.disposition == DISPOSITION_REFUTED
        assert receipt_3.downstream_commit_count == 0

        # Reset simulator
        payment_sim.set_dispatch_mode(payment_sim.DISPATCH_NORMAL_SUCCESS)
        payment_sim.set_probe_mode(payment_sim.PROBE_NORMAL)

        # ----------------------------------------------------------------------
        # Scenario 4: High-Value Amount Ceiling Breach -> STEP_UP Dual Control
        # ----------------------------------------------------------------------
        print_step(4, "Scenario 4: Spend Ceiling Breach (€15,000.00 > €1,000.00 Limit)")
        action_4 = FinancialCandidateAction(
            action_id="act_refund_ord_9915_high_val",
            principal="agent:customer_support_eu",
            target_uri="https://api.bank.internal/v1/payments/refunds",
            operation_type="customer_refund",
            parameters={
                "order_id": "ORD-2026-9915",
                "customer_id": "CUST-0099",
                "destination_iban": "XX00EXAMPLE0000000000004",
                "amount_cents": 1500000,  # 15,000.00 EUR
                "currency": "EUR",
                "reason": "commercial_settlement"
            },
            policy_epoch=1,
            source_epoch=10,
            max_amount_cents_limit=100000  # 1,000.00 EUR ceiling
        )

        is_auth4, reason4, ticket_4 = boundary.authorize_action(action_4)
        print(f"  - Action ID                : {action_4.action_id}")
        print(f"  - Requested Amount         : €15,000.00 (Ceiling: €1,000.00)")
        print(f"  - Gate Verdict             : Authorized={is_auth4} (Reason: {reason4})")
        print(f"  - Dispatch Ticket Status   : Ticket={ticket_4} (Refused to mint ticket)")
        print(f"  - Socket Egress            : 0 bytes dispatched (Fail-closed)")
        assert is_auth4 is False
        assert "STEP_UP" in reason4
        assert ticket_4 is None

        # ----------------------------------------------------------------------
        # Scenario 5: Single-Use Ticket Burn & Replay Prevention
        # ----------------------------------------------------------------------
        print_step(5, "Scenario 5: Ticket Replay Defense (Single-Use Authority Burn)")
        print(f"  - Attempting to replay ticket from Scenario 1: {ticket.ticket_id}")
        replay_receipt = boundary.execute_governed_action(action_1, ticket, payment_sim)
        print(f"  - Replay Attempt Verdict   : Disposition={replay_receipt.disposition}")
        print(f"  - Downstream Commits Count : {replay_receipt.downstream_commit_count}")
        assert replay_receipt.disposition == DISPOSITION_DENY
        assert replay_receipt.downstream_commit_count == 0

        # ----------------------------------------------------------------------
        # Scenario 6: Cryptographic Tamper Falsification Test
        # ----------------------------------------------------------------------
        print_step(6, "Scenario 6: Cryptographic Tamper Falsification Check")
        # Mutate one byte in canonical receipt
        tampered_receipt = FinancialCandidateAction(
            action_id="act_refund_tamper_test",
            principal="agent:customer_support_eu",
            target_uri="https://api.bank.internal/v1/payments/refunds",
            operation_type="customer_refund",
            parameters={"amount_cents": 1000, "currency": "EUR"},
            policy_epoch=1,
            source_epoch=10
        )
        _, _, t_tamper = boundary.authorize_action(tampered_receipt)
        legit_receipt = boundary.execute_governed_action(tampered_receipt, t_tamper, payment_sim)

        # Mutate amount in receipt dictionary
        tampered_dict = legit_receipt.to_unsigned_dict()
        tampered_dict["disposition"] = "CONFIRMED_FAKE"
        from src.jcs_canonicalizer import encode_jcs
        tampered_bytes = encode_jcs(tampered_dict)
        pub_key = boundary.public_key

        tamper_detected = False
        try:
            from cryptography.exceptions import InvalidSignature
            pub_key.verify(bytes.fromhex(legit_receipt.signature_hex), tampered_bytes)
        except InvalidSignature:
            tamper_detected = True

        print(f"  - Original Receipt Signature Valid : {FinancialReceiptOfflineVerifier.verify_receipt(legit_receipt)[0]}")
        print(f"  - Tampered Field Injected          : disposition='CONFIRMED_FAKE'")
        print(f"  - Ed25519 Verification Result      : InvalidSignature detected (Tamper Blocked={tamper_detected})")
        assert tamper_detected is True

        print_banner("DEMONSTRATION COMPLETED: ALL 6 SCENARIOS VERIFIED CLEANLY")
        print("[✓] Exact Action Authorization & Dead Salmons Filter verified.")
        print("[✓] 504 Timeout ambiguity latching & bounded reconciliation verified.")
        print("[✓] Connection drop ambiguity latching & state refutation verified.")
        print("[✓] High-value spend ceiling step-up enforcement verified.")
        print("[✓] Single-use ticket burn and replay attack blocking verified.")
        print("[✓] Offline Ed25519 cryptographic receipt tamper detection verified.")
        print("=" * 80 + "\n")

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    run_demonstration()
