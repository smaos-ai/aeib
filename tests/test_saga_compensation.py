#!/usr/bin/env python3
r"""
test_saga_compensation.py — Claim C4 Verification Suite
Sovereign Multi-Agent OS (SMAOS) / Agent Execution Integrity Benchmark (AEIB)

Formal Claim C4 Assertion:
"Ambiguous 504 transport severance transitions through two-phase outbox saga into
compensated terminal state when authoritative probe indicates missing downstream persistence."

Verifies:
  1. Trapping of ambiguous HTTP 504 at DISPATCHED_UNCONFIRMED.
  2. Downstream probe resolution returning RECONCILIATION_NOT_FOUND.
  3. Automatic idempotent compensating transaction enqueued with deterministic CAID.
  4. Mathematical preservation of the Net Ledger Invariant: \sum \Delta_{net} = 0.00.
  5. Dual-control escalation on SLA timeout or cryptographic state conflict.
"""

import os
import sys
import time
import hashlib
import unittest
from typing import Dict, Any

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import SagaReconciler from ocr-audit-engine or fallback
try:
    from ocr_audit.saga_reconciler import SagaReconciler
except ImportError:
    try:
        from src.ocr_audit.saga_reconciler import SagaReconciler
    except ImportError:
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../ocr-audit-engine/src")))
        from ocr_audit.saga_reconciler import SagaReconciler


class TestSagaCompensationClaimC4(unittest.TestCase):
    """Deterministic validation of Claim C4 (Saga Compensation & Net Ledger Invariant)."""

    def setUp(self):
        self.reconciler = SagaReconciler(sla_timeout_sec=5.0)
        self.caid_original = "caid-7a9c8f12b"
        self.idem_key = "idem-7a9c8f12b0000000"
        self.sample_amount = 5000.00

        # Construct ambiguous receipt trapped at DISPATCHED_UNCONFIRMED on 504
        self.ambiguous_receipt = {
            "receipt_id": "rcpt-504-wire-drop-001",
            "disposition": "DISPATCHED_UNCONFIRMED",
            "transport_fault": "HTTP_504_GATEWAY_TIMEOUT",
            "retry_permitted": False,
            "capsule": {
                "txid": self.caid_original,
                "idempotency_key": self.idem_key,
                "amount": self.sample_amount,
                "timestamp": time.time(),
                "action": "TRANSFER",
                "beneficiary": "SK4811000000002949524312"
            }
        }

    def test_01_claim_c4_504_wire_drop_compensates_to_net_zero(self):
        r"""
        Claim C4 Invariant: When downstream probe indicates missing commit
        (RECONCILIATION_NOT_FOUND), the reconciler executes COMPENSATED_ROLLBACK
        and zeroes out the ledger state (\sum \Delta_net = 0.00).
        """
        # Downstream probe proof indicating uncommitted state
        wire_proof_missing = {
            "target_committed": False,
            "valid_time_confirmed": False,
            "conflict_detected": False,
            "probe_disposition": "RECONCILIATION_NOT_FOUND"
        }

        status, resolution = self.reconciler.reconcile_receipt(
            self.ambiguous_receipt,
            wire_proof_missing
        )

        self.assertEqual(status, "COMPENSATED_ROLLBACK")
        self.assertEqual(resolution["status"], "COMPENSATED_ROLLBACK")
        self.assertEqual(resolution["original_txid"], self.caid_original)
        self.assertTrue(resolution["compensation_txid"].startswith("revert-"))
        self.assertEqual(resolution["delta_net"], 0.00)

        # Invariant Verification: Ledger state for txid must be strictly 0.00
        self.assertEqual(self.reconciler.ledger_state[self.caid_original], 0.00)
        net_ledger_sum = sum(self.reconciler.ledger_state.values())
        self.assertEqual(net_ledger_sum, 0.00)

    def test_02_authoritative_probe_confirmed(self):
        """When downstream probe confirms commit, transaction transitions to CONFIRMED."""
        wire_proof_committed = {
            "target_committed": True,
            "valid_time_confirmed": True,
            "conflict_detected": False
        }

        status, resolution = self.reconciler.reconcile_receipt(
            self.ambiguous_receipt,
            wire_proof_committed
        )

        self.assertEqual(status, "CONFIRMED")
        self.assertEqual(resolution["status"], "CONFIRMED")
        self.assertEqual(self.reconciler.ledger_state[self.caid_original], self.sample_amount)

    def test_03_sla_timeout_escalates_to_dual_control(self):
        """Transactions exceeding SLA timeout without resolution require MANUAL_ESCALATION."""
        stale_receipt = dict(self.ambiguous_receipt)
        stale_receipt["capsule"] = dict(self.ambiguous_receipt["capsule"])
        stale_receipt["capsule"]["timestamp"] = time.time() - 10.0  # Expired (> 5s SLA)

        wire_proof = {
            "target_committed": False,
            "valid_time_confirmed": False
        }

        status, resolution = self.reconciler.reconcile_receipt(stale_receipt, wire_proof)

        self.assertEqual(status, "MANUAL_ESCALATION")
        self.assertTrue(resolution["requires_dual_control_signoff"])

    def test_04_cryptographic_conflict_escalation(self):
        """Conflicting downstream records force immediate MANUAL_ESCALATION."""
        wire_proof_conflict = {
            "target_committed": False,
            "valid_time_confirmed": False,
            "conflict_detected": True
        }

        status, resolution = self.reconciler.reconcile_receipt(
            self.ambiguous_receipt,
            wire_proof_conflict
        )

        self.assertEqual(status, "MANUAL_ESCALATION")
        self.assertIn("cryptographic state conflict", resolution["reason"])

    def test_05_idempotent_compensation_determinism(self):
        """Repeated reconciliation calls generate identical compensation txids without drift."""
        wire_proof_missing = {
            "target_committed": False,
            "valid_time_confirmed": False
        }

        _, res1 = self.reconciler.reconcile_receipt(self.ambiguous_receipt, wire_proof_missing)
        _, res2 = self.reconciler.reconcile_receipt(self.ambiguous_receipt, wire_proof_missing)

        self.assertEqual(res1["compensation_txid"], res2["compensation_txid"])


if __name__ == "__main__":
    unittest.main()
