#!/usr/bin/env python3
r"""
test_server_idempotency_and_killswitch.py
Unit and integration tests for ServerIdempotencyAdapter and OperationalSafetyController.
Pillars: 2 (End-to-End Idempotency), 5 (Probe Outcomes), 6 (Operational Safety & Kill-Switch), 8 (Independent Validation).
"""

import os
import sys
import time
import json
import unittest
from datetime import datetime, timezone

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.server_idempotency_adapter import ServerIdempotencyAdapter, compute_payload_hash
from src.diagnostic_normalizer import (
    DiagnosticExecutionNormalizer,
    OperationalSafetyController,
    COSESign1Engine,
    COSE_ALG_EDDSA
)
from cryptography.hazmat.primitives.asymmetric import ed25519


class TestServerIdempotencyAdapter(unittest.TestCase):
    """Verifies the downstream server-side idempotency contract."""

    def setUp(self):
        self.adapter = ServerIdempotencyAdapter(db_path=":memory:")
        self.call_count = 0

    def dummy_handler(self, payload):
        self.call_count += 1
        return 200, {"transaction_id": f"TX-{self.call_count}", "settled": True, "account": payload.get("account")}

    def test_first_execution_and_cached_replay(self):
        idem_key = "idem-test-uuid-001"
        action_id = "mcp://sess-01/1/rpc-1/payment.settle_payment"
        payload = {"account": "IBAN-CZ-001", "amount": 5000}

        # First execution: handler called
        code1, res1, cached1 = self.adapter.execute_idempotent(idem_key, action_id, payload, self.dummy_handler)
        self.assertEqual(code1, 200)
        self.assertFalse(cached1)
        self.assertEqual(self.call_count, 1)
        self.assertEqual(res1["transaction_id"], "TX-1")

        # Second execution with identical payload: cached hit, handler NOT called
        code2, res2, cached2 = self.adapter.execute_idempotent(idem_key, action_id, payload, self.dummy_handler)
        self.assertEqual(code2, 200)
        self.assertTrue(cached2)
        self.assertEqual(self.call_count, 1)  # Still 1!
        self.assertEqual(res2["transaction_id"], "TX-1")

    def test_payload_tamper_rejection_422(self):
        idem_key = "idem-test-uuid-002"
        action_id = "mcp://sess-01/1/rpc-2/payment.settle_payment"
        payload_orig = {"account": "IBAN-CZ-002", "amount": 100}
        payload_tampered = {"account": "IBAN-CZ-002", "amount": 999999}

        # Commit original
        self.adapter.execute_idempotent(idem_key, action_id, payload_orig, self.dummy_handler)

        # Attempt replay with tampered payload
        code, err_resp, cached = self.adapter.execute_idempotent(
            idem_key, action_id, payload_tampered, self.dummy_handler
        )
        self.assertEqual(code, 422)
        self.assertFalse(cached)
        self.assertEqual(err_resp["error"], "IDEMPOTENCY_PAYLOAD_MISMATCH")
        self.assertEqual(self.call_count, 1)

    def test_concurrency_lock_409(self):
        idem_key = "idem-test-uuid-003"
        action_id = "mcp://sess-01/1/rpc-3/payment.settle_payment"
        payload = {"account": "IBAN-CZ-003", "amount": 250}

        # Simulate state stuck in IN_PROGRESS
        now_iso = datetime.now(timezone.utc).isoformat()
        payload_hash = compute_payload_hash(payload)
        self.adapter.conn.execute(
            "INSERT INTO server_idempotency_ledger (idempotency_key, action_id, payload_hash, status, created_at_utc, updated_at_utc) VALUES (?, ?, ?, ?, ?, ?)",
            (idem_key, action_id, payload_hash, "IN_PROGRESS", now_iso, now_iso)
        )
        self.adapter.conn.commit()

        # Attempt dispatch while IN_PROGRESS
        code, err_resp, cached = self.adapter.execute_idempotent(idem_key, action_id, payload, self.dummy_handler)
        self.assertEqual(code, 409)
        self.assertFalse(cached)
        self.assertEqual(err_resp["error"], "CONCURRENT_REQUEST_IN_FLIGHT")
        self.assertEqual(self.call_count, 0)

    def test_out_of_band_probe_states(self):
        idem_key = "idem-test-uuid-004"
        action_id = "mcp://sess-01/1/rpc-4/payment.settle_payment"
        payload = {"account": "IBAN-CZ-004", "amount": 1200}
        p_hash = compute_payload_hash(payload)

        # Probe before insert -> RECONCILIATION_NOT_FOUND
        probe1 = self.adapter.probe_state(idem_key, p_hash)
        self.assertEqual(probe1["disposition"], "RECONCILIATION_NOT_FOUND")
        self.assertFalse(probe1["outcome_verified"])

        # Execute and commit
        self.adapter.execute_idempotent(idem_key, action_id, payload, self.dummy_handler)

        # Probe with correct hash -> OUTCOME_VERIFIED
        probe2 = self.adapter.probe_state(idem_key, p_hash)
        self.assertEqual(probe2["disposition"], "OUTCOME_VERIFIED")
        self.assertTrue(probe2["outcome_verified"])

        # Probe with wrong hash -> RECONCILIATION_FAILED
        probe3 = self.adapter.probe_state(idem_key, "sha256:wronghash")
        self.assertEqual(probe3["disposition"], "RECONCILIATION_FAILED")
        self.assertFalse(probe3["outcome_verified"])


class TestOperationalSafetyAndKillSwitch(unittest.TestCase):
    """Verifies operational safety circuit breaker, forced reconciliation, and signed receipts."""

    def setUp(self):
        self.operator_key = ed25519.Ed25519PrivateKey.generate()
        self.safety_controller = OperationalSafetyController(
            signing_key=self.operator_key,
            key_id="key:smaos-operator-test"
        )
        self.normalizer = DiagnosticExecutionNormalizer(
            safety_controller=self.safety_controller
        )

    def test_kill_switch_tripped_rejects_mutating_dispatch(self):
        rpc = {
            "jsonrpc": "2.0",
            "id": "rpc-trip-01",
            "method": "tools/call",
            "params": {"name": "payment.settle_payment", "arguments": {"amount": 100}}
        }

        # Trip kill-switch
        receipt = self.safety_controller.trip_kill_switch(
            reason="Downstream gateway latency spike > 5000ms",
            operator_id="operator:security-officer-99"
        )
        self.assertTrue(self.safety_controller.kill_switch_active)
        self.assertEqual(receipt.action_type, "KILL_SWITCH_TRIP")

        # Attempt execution: must be REFUSED immediately
        exec_receipt = self.normalizer.execute_lifecycle(
            raw_mcp_request=rpc,
            actor="agent:treasury-bot"
        )
        self.assertEqual(exec_receipt.disposition, "REFUSED")
        self.assertFalse(exec_receipt.outcome_verified)
        self.assertEqual(exec_receipt.verification_method, "operational_safety_gate")
        self.assertIn("KILL_SWITCH_ACTIVE", exec_receipt.observed_outcome["refusal_reason"])

    def test_kill_switch_resume_permits_dispatch(self):
        rpc = {
            "jsonrpc": "2.0",
            "id": "rpc-resume-01",
            "method": "tools/call",
            "params": {"name": "payment.settle_payment", "arguments": {"amount": 100}}
        }

        self.safety_controller.trip_kill_switch("Incident #404", "operator:sre-1")
        self.safety_controller.resume_operations("Incident resolved", "operator:sre-1")

        exec_receipt = self.normalizer.execute_lifecycle(
            raw_mcp_request=rpc,
            actor="agent:treasury-bot",
            manual_probe_result={"outcome_confirmed": True}
        )
        self.assertEqual(exec_receipt.disposition, "OUTCOME_VERIFIED")
        self.assertTrue(exec_receipt.outcome_verified)

    def test_forced_reconciliation_mode_halts_new_dispatches(self):
        rpc = {
            "jsonrpc": "2.0",
            "id": "rpc-fr-01",
            "method": "tools/call",
            "params": {"name": "core.update_ledger", "arguments": {"val": 42}}
        }

        self.safety_controller.enable_forced_reconciliation("Reconciling 504 backlog", "operator:compliance-lead")
        exec_receipt = self.normalizer.execute_lifecycle(
            raw_mcp_request=rpc,
            actor="agent:ledger-bot"
        )
        self.assertEqual(exec_receipt.disposition, "REFUSED")
        self.assertIn("FORCED_RECONCILIATION_MODE", exec_receipt.observed_outcome["refusal_reason"])

    def test_high_risk_tool_approval_token_gate(self):
        self.safety_controller.register_high_risk_tools(["payment.wire_transfer_large"])

        rpc = {
            "jsonrpc": "2.0",
            "id": "rpc-hr-01",
            "method": "tools/call",
            "params": {"name": "payment.wire_transfer_large", "arguments": {"amount": 1000000}}
        }

        # 1. Execution without approval token: REFUSED
        r1 = self.normalizer.execute_lifecycle(raw_mcp_request=rpc, actor="agent:fin-bot")
        self.assertEqual(r1.disposition, "REFUSED")
        self.assertIn("HIGH_RISK_TOOL_REQUIRES_OPERATOR_APPROVAL", r1.observed_outcome["refusal_reason"])

        # 2. Issue valid token
        token = self.safety_controller.issue_approval_token(
            tool_name="payment.wire_transfer_large",
            operator_id="operator:ciso-desk",
            ttl_seconds=120.0
        )

        # 3. Execution with valid token: ALLOWED
        r2 = self.normalizer.execute_lifecycle(
            raw_mcp_request=rpc,
            actor="agent:fin-bot",
            approval_token=token,
            manual_probe_result={"outcome_confirmed": True}
        )
        self.assertEqual(r2.disposition, "OUTCOME_VERIFIED")

        # 4. Expired token check
        expired_token = self.safety_controller.issue_approval_token(
            tool_name="payment.wire_transfer_large",
            operator_id="operator:ciso-desk",
            ttl_seconds=-1.0  # Already expired
        )
        r3 = self.normalizer.execute_lifecycle(
            raw_mcp_request=rpc,
            actor="agent:fin-bot",
            approval_token=expired_token
        )
        self.assertEqual(r3.disposition, "REFUSED")
        self.assertIn("EXPIRED_APPROVAL_TOKEN", r3.observed_outcome["refusal_reason"])

    def test_operator_action_receipt_cose_cryptographic_verification(self):
        """Verifies that operator actions emit standard RFC 9052 COSE_Sign1 envelopes."""
        receipt = self.safety_controller.trip_kill_switch(
            reason="Emergency circuit breaker",
            operator_id="operator:risk-committee"
        )
        self.assertEqual(receipt.cose_alg, COSE_ALG_EDDSA)
        self.assertEqual(receipt.cose_kid, "key:smaos-operator-test")

        # Verify envelope using operator's public key
        env_bytes = bytes.fromhex(receipt.cose_envelope_hex)
        is_valid, payload, meta = COSESign1Engine.verify_envelope(
            env_bytes, self.operator_key.public_key()
        )
        self.assertTrue(is_valid)
        self.assertEqual(meta.get("cose_kid") or meta.get("kid"), "key:smaos-operator-test")
        self.assertEqual(meta.get("cose_alg") or meta.get("alg"), COSE_ALG_EDDSA)

        # Decode payload and check contents
        payload_data = json.loads(payload.decode("utf-8"))
        self.assertEqual(payload_data["action_type"], "KILL_SWITCH_TRIP")
        self.assertEqual(payload_data["operator_id"], "operator:risk-committee")


if __name__ == "__main__":
    unittest.main()
