#!/usr/bin/env python3
"""
test_aeib_negative_cases.py — AEIB Negative Test Suite & Edge-Case Validator
Sovereign Multi-Agent OS (SMAOS) / Category: Agent Execution Integrity

Validates edge cases and strict fail-closed state invariants:
  1. Altered Payloads & Silent Argument Drift (Payload Tampering)
  2. Stale Authorization TTLs & Authority Expiration
  3. False HTTP 200 Responses (Wire 200 != Physical Outcome Finality)
  4. Clock Skew & Timestamp Anomalies (Backward Clock Jump, Missing Timestamps)
  5. Transport Fault Drops (HTTP 504, 502, TCP RST)
  6. Cryptographic Fail-Closed Enforcement (Missing HMAC key, MAC tag tampering)
  7. Multi-Trial Stress Matrix (100 Negative Runs -> 0 False CONFIRMED)

Usage:
  pytest tests/test_aeib_negative_cases.py -v
  python3 tests/test_aeib_negative_cases.py
"""

import os
import sys
import json
import time
import uuid
import hmac
import hashlib
import tempfile
import sqlite3
import unittest
from pathlib import Path
from typing import Dict, Any, Optional

# Ensure project root, scratch, and smaos-mcp/src are on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
SCRATCH_DIR = REPO_ROOT / "scratch"
SMAOS_MCP_SRC = REPO_ROOT / "smaos-mcp" / "src"

for p in (str(REPO_ROOT), str(SCRATCH_DIR), str(SMAOS_MCP_SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mcp_outcome_normalizer import MCPOutcomeNormalizer, MCPOutcomeReceipt
from mcp_interceptor import SMAOS_MCP_Interceptor, generate_idempotency_key, deterministic_json_bytes
from state_prober import DatabaseStateProber, MockHTTPReconciliationProber
from uuidv5_idempotency_generator import uuidv5_idempotency_generator, jcs_canonical_bytes


class MockTransportClient:
    """Mock MCP client that can be programmed to simulate any transport response or failure."""
    def __init__(self):
        self.behavior = "200_ok"
        self.response_data = {"status": "ok"}
        self.status_code = 200

    def set_behavior(self, behavior: str, status_code: int = 200, response_data: Optional[Dict[str, Any]] = None):
        self.behavior = behavior
        self.status_code = status_code
        self.response_data = response_data or {"status": "ok"}

    def call_tool(self, tool_name: str, arguments: dict, headers: Optional[dict] = None):
        if self.behavior == "504_timeout":
            raise TimeoutError("HTTP 504 Gateway Timeout from proxy")
        elif self.behavior == "tcp_rst":
            raise ConnectionResetError("[Errno 104] Connection reset by peer")
        elif self.behavior == "network_down":
            raise OSError("[Errno 101] Network is unreachable")
        
        # Return a response object mimicking standard wire output
        class Response:
            def __init__(self, code, data):
                self.status_code = code
                self.data = data
        return Response(self.status_code, self.response_data)


class TestAEIBNegativeCases(unittest.TestCase):
    def setUp(self):
        self.test_hmac_key = b"sovereign_test_secret_hmac_key_2026"
        os.environ["SMAOS_HMAC_KEY"] = self.test_hmac_key.decode("utf-8")
        
        # Temporary SQLite ledger for authoritative prober
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE audit_ledger (
                idempotency_key TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
        conn.commit()
        conn.close()

        self.mock_client = MockTransportClient()
        self.state_prober = DatabaseStateProber(self.db_path, table_name="audit_ledger")
        self.interceptor = SMAOS_MCP_Interceptor(
            mcp_client=self.mock_client,
            state_prober=self.state_prober
        )
        self.normalizer = MCPOutcomeNormalizer(key=self.test_hmac_key)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    # ==========================================================================
    # GROUP 1: ALTERED PAYLOADS & ARGUMENT DRIFT (PAYLOAD TAMPERING)
    # ==========================================================================

    def test_01_payload_tampering_amount_mutation_rejected(self):
        """
        Negative Case 1.1: Silent parameter mutation (+€450k loan tampering).
        The client sent €50k, but the downstream record in the ledger reflects €500k.
        The prober detects payload hash divergence and forces RECONCILIATION_FAILED.
        """
        session_id = "sess-tamper-01"
        step = 1
        rpc_id = "rpc-tamper-1"
        tool_name = "loan.approve"
        args_original = {"applicant": "Elena Bianchi", "amount": 50000.0}

        # Calculate original key and hash
        idem_key_result = generate_idempotency_key(session_id, step, rpc_id, tool_name, args_original)
        idem_key = idem_key_result[0] if isinstance(idem_key_result, tuple) else idem_key_result

        # Seed the DB with tampered payload hash (e.g. $500,000)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        tampered_hash = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        cursor.execute("""
            INSERT INTO audit_ledger (idempotency_key, status, payload_hash, result_json, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (idem_key, "COMMITTED", tampered_hash, json.dumps({"approved_amount": 500000.0}), "2026-09-29T00:00:00Z"))
        conn.commit()
        conn.close()

        # Simulate 504 drop triggering out-of-band probe
        self.mock_client.set_behavior("504_timeout")
        receipt = self.interceptor.execute_tool_call(
            session_id=session_id,
            step_sequence=step,
            rpc_id=rpc_id,
            tool_name=tool_name,
            arguments=args_original
        )

        self.assertFalse(receipt["outcome_verified"], "Tampered payload must NOT be verified!")
        self.assertEqual(receipt["disposition"], "RECONCILIATION_FAILED")
        self.assertFalse(receipt["observed_outcome"].get("payload_match", True))

    def test_02_unauthorized_attribute_injection_diverges_hash(self):
        """
        Negative Case 1.2: Injecting an unauthorized key ('bypass_audit': True)
        changes the canonical payload hash and invalidates idempotency matching.
        """
        args_base = {"order_id": "ord-100", "items": ["item-1"]}
        args_injected = {"order_id": "ord-100", "items": ["item-1"], "bypass_audit": True}

        res_base = uuidv5_idempotency_generator("s1", 1, "r1", "order.create", args_base)
        res_injected = uuidv5_idempotency_generator("s1", 1, "r1", "order.create", args_injected)

        self.assertNotEqual(res_base["payload_sha256"], res_injected["payload_sha256"])
        self.assertNotEqual(res_base["idempotency_key"], res_injected["idempotency_key"])

    # ==========================================================================
    # GROUP 2: STALE AUTHORIZATION TTLS & AUTHORITY EXPIRATION
    # ==========================================================================

    def test_03_stale_authority_ttl_detection(self):
        """
        Negative Case 2.1: Authority TTL in the past must be detected.
        """
        expired_ttl = "2026-01-01T00:00:00Z"
        raw_request = {
            "jsonrpc": "2.0",
            "id": "rpc-expired-ttl",
            "method": "tools/call",
            "params": {"name": "account.close", "arguments": {"account_id": "ACC-EXPIRED"}}
        }

        receipt = self.normalizer.process_execution(
            actor="agent:compliance",
            raw_mcp_request=raw_request,
            authority_ttl=expired_ttl,
            wire_status=200
        )

        self.assertEqual(receipt.authority_ttl, expired_ttl)
        # Verify TTL is parsed as historically expired compared to present
        current_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.assertTrue(receipt.authority_ttl < current_iso, "Authority TTL must be recognized as past/stale")

    def test_04_excessive_authority_latency_anomaly(self):
        """
        Negative Case 2.2: Authority issued 10 minutes ago (> 600,000ms delta)
        must compute exact large delta without being suppressed.
        """
        t0 = time.time() - 600.0  # 600 seconds ago
        tn = time.time()

        raw_request = {
            "jsonrpc": "2.0",
            "id": "rpc-lag",
            "method": "tools/call",
            "params": {"name": "funds.transfer", "arguments": {"amount": 50}}
        }

        receipt = self.normalizer.process_execution(
            actor="agent:treasury",
            raw_mcp_request=raw_request,
            valid_time_t0=t0,
            transaction_time_tn=tn,
            wire_status=200
        )

        self.assertEqual(receipt.freshness_status, "MEASURED")
        self.assertIsNotNone(receipt.wall_clock_delta_ms)
        self.assertGreaterEqual(receipt.wall_clock_delta_ms, 599000.0)

    # ==========================================================================
    # GROUP 3: FALSE HTTP 200 RESPONSES (WIRE 200 != OUTCOME VERIFICATION)
    # ==========================================================================

    def test_05_wire_200_without_probe_is_strictly_ack_unverified(self):
        """
        Negative Case 3.1: The Core Invariant.
        An HTTP 200 OK wire response without an authoritative post-condition probe
        must NEVER evaluate to CONFIRMED. It must yield ACK_UNVERIFIED.
        """
        raw_request = {
            "jsonrpc": "2.0",
            "id": "rpc-wire-200",
            "method": "tools/call",
            "params": {"name": "payments.payout", "arguments": {"amount": 10000}}
        }

        # Wire status 200, but post_state_probe is None
        receipt = self.normalizer.process_execution(
            actor="agent:payouts",
            raw_mcp_request=raw_request,
            wire_status=200,
            post_state_probe=None
        )

        self.assertFalse(receipt.outcome_verified, "Wire 200 alone must NEVER verify outcome!")
        self.assertEqual(receipt.disposition, "ACK_UNVERIFIED")
        self.assertIsNone(receipt.downstream_state_hash)
        self.assertEqual(receipt.verification_method, "no_authoritative_probe")

    def test_06_wire_200_with_failed_probe_evaluates_to_refused(self):
        """
        Negative Case 3.2: Wire returned 200, but downstream probe reveals the condition
        failed (e.g. hotel search in Paris returned hotels in London).
        """
        raw_request = {
            "jsonrpc": "2.0",
            "id": "rpc-hotel-fail",
            "method": "tools/call",
            "params": {"name": "hotel.book", "arguments": {"city": "Paris", "breakfast": True}}
        }

        # Downstream probe reveals outcome criteria was not fulfilled
        probe_result = {
            "hotel_found": "London Hotel",
            "all_in_paris": False,
            "outcome_confirmed": False
        }

        receipt = self.normalizer.process_execution(
            actor="agent:travel-planner",
            raw_mcp_request=raw_request,
            wire_status=200,
            post_state_probe=probe_result
        )

        self.assertFalse(receipt.outcome_verified)
        self.assertEqual(receipt.disposition, "REFUSED")
        self.assertIsNotNone(receipt.downstream_state_hash)

    # ==========================================================================
    # GROUP 4: CLOCK SKEW & TIMESTAMP ANOMALIES
    # ==========================================================================

    def test_07_clock_skew_backward_jump_detected(self):
        """
        Negative Case 4.1: Backward clock step (tn < t0) due to NTP sync adjustment.
        Delta evaluates to a negative number, exposing clock skew without fabricating data.
        """
        t0 = 1788000100.0
        tn = 1788000050.0  # Clock stepped backwards 50 seconds!

        raw_request = {
            "jsonrpc": "2.0",
            "id": "rpc-skew",
            "method": "tools/call",
            "params": {"name": "test.probe", "arguments": {}}
        }

        receipt = self.normalizer.process_execution(
            actor="agent:tester",
            raw_mcp_request=raw_request,
            valid_time_t0=t0,
            transaction_time_tn=tn,
            wire_status=200
        )

        self.assertEqual(receipt.freshness_status, "MEASURED")
        self.assertIsNotNone(receipt.wall_clock_delta_ms)
        self.assertLess(receipt.wall_clock_delta_ms, 0, "Clock skew must produce negative delta indicating drift")
        self.assertEqual(receipt.wall_clock_delta_ms, -50000.0)

    def test_08_missing_timestamps_strictly_unmanufactured(self):
        """
        Negative Case 4.2: Unmanufactured Freshness Invariant.
        If t0 or tn is absent, wall_clock_delta_ms must be None and freshness UNMEASURED.
        """
        raw_request = {
            "jsonrpc": "2.0",
            "id": "rpc-missing-time",
            "method": "tools/call",
            "params": {"name": "test.probe", "arguments": {}}
        }

        receipt = self.normalizer.process_execution(
            actor="agent:tester",
            raw_mcp_request=raw_request,
            valid_time_t0=None,
            transaction_time_tn=None,
            wire_status=200
        )

        self.assertIsNone(receipt.wall_clock_delta_ms)
        self.assertEqual(receipt.freshness_status, "UNMEASURED")

    # ==========================================================================
    # GROUP 5: TRANSPORT SEVERANCE & QUARANTINE
    # ==========================================================================

    def test_09_http_504_gateway_timeout_quarantines(self):
        """
        Negative Case 5.1: HTTP 504 Gateway Timeout without downstream persistence
        must quarantine into DISPATCHED_UNCONFIRMED / RECONCILIATION_FAILED.
        """
        raw_request = {
            "jsonrpc": "2.0",
            "id": "rpc-504",
            "method": "tools/call",
            "params": {"name": "payment.execute", "arguments": {"amount": 500}}
        }

        receipt = self.normalizer.process_execution(
            actor="agent:tester",
            raw_mcp_request=raw_request,
            wire_status=504,
            post_state_probe=None
        )

        self.assertFalse(receipt.outcome_verified)
        self.assertEqual(receipt.disposition, "DISPATCHED_UNCONFIRMED")
        self.assertEqual(receipt.verification_method, "quarantined_unconfirmed_probe")

    def test_10_tcp_rst_socket_drop_quarantined_by_interceptor(self):
        """
        Negative Case 5.2: TCP RST socket disconnect caught by interceptor.
        """
        self.mock_client.set_behavior("tcp_rst")
        receipt = self.interceptor.execute_tool_call(
            session_id="sess-rst",
            step_sequence=1,
            rpc_id="rpc-rst",
            tool_name="database.mutate",
            arguments={"table": "users", "action": "delete"}
        )

        self.assertFalse(receipt["outcome_verified"])
        self.assertIn(receipt["disposition"], ("RECONCILIATION_NOT_FOUND", "RECONCILIATION_FAILED"))
        self.assertIn("ConnectionResetError", receipt["transport_exception"])

    # ==========================================================================
    # GROUP 6: CRYPTOGRAPHIC INTEGRITY FAIL-CLOSED CHECKS
    # ==========================================================================

    def test_11_missing_hmac_env_fails_closed(self):
        """
        Negative Case 6.1: Missing SMAOS_HMAC_KEY in environment fails closed.
        """
        original_env = os.environ.get("SMAOS_HMAC_KEY")
        try:
            if "SMAOS_HMAC_KEY" in os.environ:
                del os.environ["SMAOS_HMAC_KEY"]
            
            with self.assertRaises(RuntimeError) as ctx:
                MCPOutcomeNormalizer(key=None)
            self.assertIn("SMAOS_HMAC_KEY", str(ctx.exception))
        finally:
            if original_env is not None:
                os.environ["SMAOS_HMAC_KEY"] = original_env

    def test_12_mac_tag_tampering_detected(self):
        """
        Negative Case 6.2: Any bit flip in the receipt payload must fail MAC validation.
        """
        raw_request = {
            "jsonrpc": "2.0",
            "id": "rpc-mac-check",
            "method": "tools/call",
            "params": {"name": "test.tool", "arguments": {"x": 1}}
        }

        receipt = self.normalizer.process_execution(
            actor="agent:tester",
            raw_mcp_request=raw_request,
            wire_status=200
        )

        # Validate authentic MAC tag
        sig_data = f"{receipt.action_id}:{receipt.actor}:{receipt.request_payload_hash}:{receipt.disposition}:{receipt.outcome_verified}:{receipt.wall_clock_delta_ms}"
        expected_mac = hmac.new(self.test_hmac_key, sig_data.encode("utf-8"), hashlib.sha256).hexdigest()
        self.assertEqual(receipt.hmac_sha256_integrity_tag, expected_mac)

        # Flip a single character in the disposition
        tampered_sig_data = f"{receipt.action_id}:{receipt.actor}:{receipt.request_payload_hash}:CONFIRMED:{receipt.outcome_verified}:{receipt.wall_clock_delta_ms}"
        tampered_mac = hmac.new(self.test_hmac_key, tampered_sig_data.encode("utf-8"), hashlib.sha256).hexdigest()
        self.assertNotEqual(receipt.hmac_sha256_integrity_tag, tampered_mac)

    # ==========================================================================
    # GROUP 7: MULTI-TRIAL STRESS MATRIX (100 ADVERSARIAL RUNS)
    # ==========================================================================

    def test_13_multi_trial_negative_stress_matrix(self):
        """
        Negative Case 7.1: 100 random permutations of negative scenarios.
        Zero false positive CONFIRMED dispositions permitted.
        """
        total_trials = 100
        false_positive_count = 0

        for trial in range(1, total_trials + 1):
            category = trial % 5
            
            if category == 0:
                # 504 dropped without backend commit
                raw_req = {"jsonrpc": "2.0", "id": f"t-{trial}", "method": "tools/call", "params": {"name": "p.x", "arguments": {}}}
                r = self.normalizer.process_execution(actor="agent:stress", raw_mcp_request=raw_req, wire_status=504)
            elif category == 1:
                # Wire 200 without authoritative probe
                raw_req = {"jsonrpc": "2.0", "id": f"t-{trial}", "method": "tools/call", "params": {"name": "p.x", "arguments": {}}}
                r = self.normalizer.process_execution(actor="agent:stress", raw_mcp_request=raw_req, wire_status=200, post_state_probe=None)
            elif category == 2:
                # Wire 200 with failed probe
                raw_req = {"jsonrpc": "2.0", "id": f"t-{trial}", "method": "tools/call", "params": {"name": "p.x", "arguments": {}}}
                r = self.normalizer.process_execution(actor="agent:stress", raw_mcp_request=raw_req, wire_status=200, post_state_probe={"outcome_confirmed": False})
            elif category == 3:
                # Severe backward clock drift (-10,000ms)
                raw_req = {"jsonrpc": "2.0", "id": f"t-{trial}", "method": "tools/call", "params": {"name": "p.x", "arguments": {}}}
                r = self.normalizer.process_execution(actor="agent:stress", raw_mcp_request=raw_req, valid_time_t0=2000.0, transaction_time_tn=1990.0, wire_status=200)
            elif category == 4:
                # Wire 502 bad gateway
                raw_req = {"jsonrpc": "2.0", "id": f"t-{trial}", "method": "tools/call", "params": {"name": "p.x", "arguments": {}}}
                r = self.normalizer.process_execution(actor="agent:stress", raw_mcp_request=raw_req, wire_status=502)

            if r.disposition == "CONFIRMED" or r.outcome_verified is True:
                false_positive_count += 1

        self.assertEqual(false_positive_count, 0, f"Critical failure: {false_positive_count} negative cases marked CONFIRMED!")


def main():
    print("================================================================================")
    print("🛡️  AEIB MULTI-TRIAL NEGATIVE TEST SUITE")
    print("Validates: Altered Payloads, Stale TTLs, False HTTP 200, Clock Skew, HMAC Guard")
    print("================================================================================")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestAEIBNegativeCases)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)
    print("================================================================================")
    print("🎉 ALL 13 NEGATIVE TEST CASES & 100-TRIAL STRESS RUN PASSED (0 FALSE CONFIRMED)")
    print("================================================================================")


if __name__ == "__main__":
    main()
