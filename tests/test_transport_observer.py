#!/usr/bin/env python3
r"""
test_transport_observer.py
Unit tests for MCP Sidecar TransportObserver (Phase 2).
Verifies JSON-RPC request interception, RFC 8785 JCS idempotency injection,
transport fault handling, rule mapping evaluation, downstream SQLite probe integration,
and cryptographic Ed25519 signature verification on emitted receipts.
"""

import os
import sys
import json
import hashlib
import unittest
from cryptography.exceptions import InvalidSignature

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.transport_observer import (
    TransportObserver,
    derive_uuidv5_idempotency_key,
    DEFAULT_MAPPING_RULES,
)
from src.sqlite_probe_adapter import SQLiteOutcomeProbeAdapter
from src.jcs_canonicalizer import encode_jcs, generate_jcs_payload_hash


class TestTransportObserver(unittest.TestCase):
    """Verifies MCP Sidecar TransportObserver behavior."""

    def setUp(self):
        self.probe_adapter = SQLiteOutcomeProbeAdapter(":memory:")
        self.observer = TransportObserver(probe_adapter=self.probe_adapter)

    def tearDown(self):
        self.probe_adapter.close()

    def test_derive_uuidv5_idempotency_key_deterministic(self):
        """Identical payload hashes produce identical UUIDv5 keys."""
        h1 = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        key1 = derive_uuidv5_idempotency_key(h1)
        key2 = derive_uuidv5_idempotency_key(h1)
        self.assertEqual(key1, key2)

        # Different hash produces different key
        h2 = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
        key3 = derive_uuidv5_idempotency_key(h2)
        self.assertNotEqual(key1, key3)

    def test_intercept_request_injects_metadata(self):
        """Intercepting a tools/call request injects _meta with idempotency_key and payload_hash."""
        req = {
            "jsonrpc": "2.0",
            "id": "req-001",
            "method": "tools/call",
            "params": {
                "name": "settle_payment",
                "arguments": {"account": "CZ-991", "amount": 1000},
            },
        }
        modified_req, ctx = self.observer.intercept_request(req)

        self.assertIn("_meta", modified_req["params"])
        meta = modified_req["params"]["_meta"]
        self.assertIn("idempotency_key", meta)
        self.assertIn("unsigned_payload_hash", meta)

        self.assertEqual(ctx["request_id"], "req-001")
        self.assertEqual(ctx["tool_name"], "settle_payment")
        self.assertEqual(ctx["idempotency_key"], meta["idempotency_key"])
        self.assertEqual(ctx["payload_hash"], meta["unsigned_payload_hash"])

    def test_intercept_request_idempotency_determinism_across_argument_order(self):
        """Differing argument dictionary key order produces identical idempotency key."""
        req1 = {
            "jsonrpc": "2.0",
            "id": "req-1",
            "method": "tools/call",
            "params": {"name": "wire", "arguments": {"a": 1, "b": 2}},
        }
        req2 = {
            "jsonrpc": "2.0",
            "id": "req-2",
            "method": "tools/call",
            "params": {"name": "wire", "arguments": {"b": 2, "a": 1}},
        }
        _, ctx1 = self.observer.intercept_request(req1)
        _, ctx2 = self.observer.intercept_request(req2)

        self.assertEqual(ctx1["payload_hash"], ctx2["payload_hash"])
        self.assertEqual(ctx1["idempotency_key"], ctx2["idempotency_key"])

    def test_rule_mapping_priorities(self):
        """Verifies priority-ordered mapping resolution."""
        # 504 + FOUND_COMMITTED -> RULE-02B (OUTCOME_VERIFIED)
        r_2b = self.observer.evaluate_rule(504, "FOUND_COMMITTED")
        self.assertEqual(r_2b["id"], "RULE-02B-504-RECONCILED")
        self.assertEqual(r_2b["target_disposition"], "OUTCOME_VERIFIED")

        # 504 + RECORD_NOT_FOUND -> RULE-03 (RECONCILIATION_NOT_FOUND)
        r_3 = self.observer.evaluate_rule(504, "RECORD_NOT_FOUND")
        self.assertEqual(r_3["id"], "RULE-03-RESET-NOT-FOUND")
        self.assertEqual(r_3["target_disposition"], "RECONCILIATION_NOT_FOUND")

        # 504 + PAYLOAD_MISMATCH -> RULE-04 (RECONCILIATION_FAILED)
        r_4 = self.observer.evaluate_rule(504, "PAYLOAD_MISMATCH")
        self.assertEqual(r_4["id"], "RULE-04-PAYLOAD-MISMATCH")
        self.assertEqual(r_4["target_disposition"], "RECONCILIATION_FAILED")

        # 504 + AWAITING_OPERATOR_PROBE -> RULE-02A (DISPATCHED_UNCONFIRMED)
        r_2a = self.observer.evaluate_rule(504, "AWAITING_OPERATOR_PROBE")
        self.assertEqual(r_2a["id"], "RULE-02A-504-AMBIGUOUS")
        self.assertEqual(r_2a["target_disposition"], "DISPATCHED_UNCONFIRMED")

        # 409 + STATE_CONFLICT -> RULE-05 (RECONCILIATION_CONFLICT)
        r_5 = self.observer.evaluate_rule(409, "STATE_CONFLICT")
        self.assertEqual(r_5["id"], "RULE-05-CONFLICT")
        self.assertEqual(r_5["target_disposition"], "RECONCILIATION_CONFLICT")

    def test_sqlite_probe_integration_timeout_committed_outcome(self):
        """Downstream transaction committed before 504 timeout resolves to OUTCOME_VERIFIED."""
        req = {
            "jsonrpc": "2.0",
            "id": "tx-timeout-01",
            "method": "tools/call",
            "params": {"name": "wire_transfer", "arguments": {"amount": 50000}},
        }
        _, ctx = self.observer.intercept_request(req)

        # Pre-populate downstream ledger (simulating downstream write completed before response drop)
        self.probe_adapter.record_transaction(
            idempotency_key=ctx["idempotency_key"],
            action_id=ctx["action_id"],
            payload_hash=ctx["payload_hash"],
            status="COMMITTED",
            response_code=200,
        )

        error_response = self.observer.intercept_transport_fault(
            dispatch_ctx=ctx,
            transport_code=504,
            error_message="Gateway Timeout",
        )

        self.assertEqual(error_response["id"], "tx-timeout-01")
        self.assertEqual(int(error_response["error"]["code"]), -32000)
        self.assertEqual(error_response["error"]["data"]["disposition"], "OUTCOME_VERIFIED")
        self.assertFalse(error_response["error"]["data"]["retry_permitted"])

        # Check receipt
        receipt = error_response["error"]["data"]["receipt"]
        self.assertEqual(receipt["unsigned_payload"]["org.smaos.aeib"]["disposition"], "OUTCOME_VERIFIED")

    def test_sqlite_probe_integration_timeout_unpersisted_outcome(self):
        """Downstream transaction dropped before persistence resolves to RECONCILIATION_NOT_FOUND."""
        req = {
            "jsonrpc": "2.0",
            "id": "tx-timeout-02",
            "method": "tools/call",
            "params": {"name": "wire_transfer", "arguments": {"amount": 75000}},
        }
        _, ctx = self.observer.intercept_request(req)

        # Do NOT record in downstream ledger (simulating request never reached DB)
        error_response = self.observer.intercept_transport_fault(
            dispatch_ctx=ctx,
            transport_code=504,
            error_message="Gateway Timeout",
        )

        self.assertEqual(error_response["error"]["data"]["disposition"], "RECONCILIATION_NOT_FOUND")
        self.assertTrue(error_response["error"]["data"]["retry_permitted"])

    def test_sqlite_probe_integration_payload_tampering_detection(self):
        """Downstream record hash mismatch resolves to RECONCILIATION_FAILED."""
        req = {
            "jsonrpc": "2.0",
            "id": "tx-tamper-01",
            "method": "tools/call",
            "params": {"name": "wire_transfer", "arguments": {"amount": 100000}},
        }
        _, ctx = self.observer.intercept_request(req)

        # Record with altered hash
        self.probe_adapter.record_transaction(
            idempotency_key=ctx["idempotency_key"],
            action_id=ctx["action_id"],
            payload_hash="sha256:corrupted_or_tampered_hash_value",
            status="COMMITTED",
            response_code=200,
        )

        error_response = self.observer.intercept_transport_fault(
            dispatch_ctx=ctx,
            transport_code=504,
            error_message="Gateway Timeout",
        )

        self.assertEqual(error_response["error"]["data"]["disposition"], "RECONCILIATION_FAILED")
        self.assertFalse(error_response["error"]["data"]["retry_permitted"])

    def test_cryptographic_signature_verification_on_receipt(self):
        """Emitted receipt is verified by public key over JCS signable view."""
        req = {
            "jsonrpc": "2.0",
            "id": "sig-test-01",
            "method": "tools/call",
            "params": {"name": "test_action", "arguments": {"foo": "bar"}},
        }
        _, ctx = self.observer.intercept_request(req)
        receipt = self.observer.emit_receipt(
            dispatch_ctx=ctx,
            transport_code=504,
            probe_status="AWAITING_OPERATOR_PROBE",
        )

        unsigned_payload = receipt["unsigned_payload"]
        recorded_hash = receipt["unsigned_payload_hash"]

        # 1. Verify unsigned payload hash matches canonical JCS representation
        computed_hash = hashlib.sha256(encode_jcs(unsigned_payload)).hexdigest()
        self.assertEqual(computed_hash, recorded_hash)
        self.assertEqual(
            receipt["signature_metadata"]["signed_payload_hash"],
            recorded_hash,
        )

        # 2. Verify signature
        signable_view = {
            "unsigned_payload": unsigned_payload,
            "unsigned_payload_hash": recorded_hash,
        }
        signable_bytes = encode_jcs(signable_view)
        sig_bytes = bytes.fromhex(receipt["signature_metadata"]["signature"])
        # Should not raise
        self.observer.public_key.verify(sig_bytes, signable_bytes)

        # 3. Tampering with signable view must fail verification
        tampered_view = dict(signable_view)
        tampered_view["tampered"] = True
        tampered_bytes = encode_jcs(tampered_view)
        with self.assertRaises(InvalidSignature):
            self.observer.public_key.verify(sig_bytes, tampered_bytes)

    def test_emit_ebpf_xdp_receipt_binding(self):
        """Emitted receipt binds eBPF Ringbuf telemetry into transport_evidence."""
        req = {
            "jsonrpc": "2.0",
            "id": "ebpf-tx-01",
            "method": "tools/call",
            "params": {"name": "settle_payment", "arguments": {"account": "DE-001", "amount": 25000}},
        }
        _, ctx = self.observer.intercept_request(req)

        telemetry = {
            "timestamp_ns": 1717258901234567,
            "disposition": "DISPATCHED_UNCONFIRMED_QUARANTINE",
            "flow_5tuple": {
                "source": "10.0.2.15:49210",
                "destination": "10.0.2.2:8080",
                "protocol": "TCP",
            },
            "action": "XDP_DROP",
            "ringbuf_discard_count": 0,
        }

        receipt = self.observer.emit_ebpf_xdp_receipt(
            dispatch_ctx=ctx,
            kernel_telemetry=telemetry,
            execution_observation="tcp_retry_dropped_by_xdp",
        )

        unsigned = receipt["unsigned_payload"]
        self.assertEqual(unsigned["execution_observation"], "tcp_retry_dropped_by_xdp")
        self.assertEqual(unsigned["transport_evidence"]["adapter_type"], "ebpf_xdp_driver")
        self.assertEqual(unsigned["transport_evidence"]["kernel_telemetry"], telemetry)

        # Verify JCS hash and signature
        computed_hash = hashlib.sha256(encode_jcs(unsigned)).hexdigest()
        self.assertEqual(computed_hash, receipt["unsigned_payload_hash"])

        signable = {
            "unsigned_payload": unsigned,
            "unsigned_payload_hash": computed_hash,
        }
        sig_bytes = bytes.fromhex(receipt["signature_metadata"]["signature"])
        self.observer.public_key.verify(sig_bytes, encode_jcs(signable))

    def test_all_default_mapping_rules_coverage(self):
        """Verifies each rule in DEFAULT_MAPPING_RULES matches expected codes and dispositions."""
        expected_rules = [
            (409, "STATE_CONFLICT", "RECONCILIATION_CONFLICT", False, 10),
            (403, "NOT_DISPATCHED", "CONTEXT_POLICY_VIOLATION", False, 15),
            (401, "NOT_DISPATCHED", "AUTHORITY_NOT_BOUND", False, 15),
            (504, "PAYLOAD_MISMATCH", "RECONCILIATION_FAILED", False, 20),
            (504, "FOUND_COMMITTED", "OUTCOME_VERIFIED", False, 25),
            (504, "RECORD_NOT_FOUND", "RECONCILIATION_NOT_FOUND", True, 25),
            (504, "AWAITING_OPERATOR_PROBE", "DISPATCHED_UNCONFIRMED", False, 30),
            (200, "NOT_REQUIRED", "OUTCOME_VERIFIED", False, 50),
        ]
        self.assertEqual(len(DEFAULT_MAPPING_RULES), len(expected_rules))
        for code, status, disp, retry_perm, prio in expected_rules:
            rule = self.observer.evaluate_rule(code, status)
            self.assertEqual(rule["target_disposition"], disp)
            self.assertEqual(rule["retry_permitted"], retry_perm)
            self.assertEqual(rule["priority"], prio)

    def test_unknown_rule_fallback(self):
        """Evaluating an unmapped code and status falls back to RULE-UNKNOWN."""
        rule = self.observer.evaluate_rule(500, "UNKNOWN_STATE")
        self.assertEqual(rule["id"], "RULE-UNKNOWN")
        self.assertEqual(rule["priority"], 999)
        self.assertEqual(rule["target_disposition"], "DISPATCHED_UNCONFIRMED")
        self.assertEqual(rule["retry_policy"], "PROHIBITED_UNKNOWN_FAULT")
        self.assertFalse(rule["retry_permitted"])

    def test_emit_receipt_without_probe_adapter_status_derivation(self):
        """Without a probe adapter, status and transport_fault are inferred accurately."""
        req = {"jsonrpc": "2.0", "id": "infer-1", "method": "tools/call", "params": {"name": "test"}}
        _, ctx = self.observer.intercept_request(req)

        obs_no_probe = TransportObserver(probe_adapter=None)

        # 200 -> NOT_REQUIRED, NONE
        r200 = obs_no_probe.emit_receipt(ctx, 200)
        self.assertEqual(r200["unsigned_payload"]["org.smaos.aeib"]["probe_status"], "NOT_REQUIRED")
        self.assertEqual(r200["unsigned_payload"]["org.smaos.aeib"]["transport_fault"], "NONE")

        # 401 -> NOT_DISPATCHED, TRANSPORT_HTTP_401
        r401 = obs_no_probe.emit_receipt(ctx, 401)
        self.assertEqual(r401["unsigned_payload"]["org.smaos.aeib"]["probe_status"], "NOT_DISPATCHED")
        self.assertEqual(r401["unsigned_payload"]["org.smaos.aeib"]["transport_fault"], "TRANSPORT_HTTP_401")

        # 403 -> NOT_DISPATCHED, TRANSPORT_HTTP_403
        r403 = obs_no_probe.emit_receipt(ctx, 403)
        self.assertEqual(r403["unsigned_payload"]["org.smaos.aeib"]["probe_status"], "NOT_DISPATCHED")
        self.assertEqual(r403["unsigned_payload"]["org.smaos.aeib"]["transport_fault"], "TRANSPORT_HTTP_403")

        # 504 -> AWAITING_OPERATOR_PROBE, TRANSPORT_HTTP_504
        r504 = obs_no_probe.emit_receipt(ctx, 504)
        self.assertEqual(r504["unsigned_payload"]["org.smaos.aeib"]["probe_status"], "AWAITING_OPERATOR_PROBE")
        self.assertEqual(r504["unsigned_payload"]["org.smaos.aeib"]["transport_fault"], "TRANSPORT_HTTP_504")

        # 500 -> AWAITING_OPERATOR_PROBE, TRANSPORT_HTTP_500
        r500 = obs_no_probe.emit_receipt(ctx, 500)
        self.assertEqual(r500["unsigned_payload"]["org.smaos.aeib"]["probe_status"], "AWAITING_OPERATOR_PROBE")
        self.assertEqual(r500["unsigned_payload"]["org.smaos.aeib"]["transport_fault"], "TRANSPORT_HTTP_500")

    def test_intercept_transport_fault_safe_to_resend(self):
        """When rule allows retry (RECORD_NOT_FOUND), action_required is SAFE_TO_RESEND."""
        req = {"jsonrpc": "2.0", "id": "resend-1", "method": "tools/call", "params": {"name": "test"}}
        _, ctx = self.observer.intercept_request(req)

        err_resp = self.observer.intercept_transport_fault(
            dispatch_ctx=ctx,
            transport_code=504,
            error_message="Gateway Timeout",
            probe_status="RECORD_NOT_FOUND",
        )
        data = err_resp["error"]["data"]
        self.assertTrue(data["retry_permitted"])
        self.assertEqual(data["action_required"], "SAFE_TO_RESEND")
        self.assertEqual(data["disposition"], "RECONCILIATION_NOT_FOUND")

    def test_load_rules_with_yaml_mapping_file(self):
        """Verifies custom YAML/JSON loading and fallback priority sorting."""
        import tempfile
        self.assertEqual(TransportObserver.DEFAULT_RULE_PRIORITY, 999)
        file_content = json.dumps({
            "rules": [
                {
                    "id": "CUSTOM-01",
                    "priority": 5,
                    "match": {"transport_code": 504, "probe_status": "CUSTOM_PROBE"},
                    "target_disposition": "RECONCILIATION_NOT_FOUND",
                },
                {
                    "id": "CUSTOM-02",
                    "priority": 1,
                    "match": {"transport_code": 504, "probe_status": "CUSTOM_CRITICAL"},
                    "target_disposition": "CRITICAL_FAILURE",
                },
                {
                    "id": "CUSTOM-03",
                    # No priority specified, falls back to DEFAULT_RULE_PRIORITY (999)
                    "match": {"transport_code": 504, "probe_status": "CUSTOM_DEFAULT"},
                    "target_disposition": "RECONCILIATION_NOT_FOUND",
                },
            ]
        })
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write(file_content)
            tmp_path = f.name

        try:
            obs = TransportObserver(mapping_path=tmp_path)
            self.assertEqual(len(obs.rules), 3)
            # Must be sorted by priority ascending (1 first, then 5, then 999)
            self.assertEqual(obs.rules[0]["id"], "CUSTOM-02")
            self.assertEqual(obs.rules[0]["priority"], 1)
            self.assertFalse(obs.rules[0]["retry_permitted"])
            self.assertEqual(obs.rules[1]["id"], "CUSTOM-01")
            self.assertEqual(obs.rules[1]["priority"], 5)
            self.assertTrue(obs.rules[1]["retry_permitted"])
            self.assertEqual(obs.rules[2]["id"], "CUSTOM-03")
            self.assertNotIn("priority", obs.rules[2])
            self.assertTrue(obs.rules[2]["retry_permitted"])
        finally:
            os.unlink(tmp_path)

    def test_banned_words_compliance_in_transport_observer_files(self):
        for fpath in ["src/transport_observer.py", "tests/test_transport_observer.py"]:
            with open(fpath, "r", encoding="utf-8") as f:
                text = f.read().lower()
            forbidden = [
                "guaran" + "tee",
                "bullet" + "proof",
                "enterprise-" + "grade",
                "production-" + "safe",
                "100% " + "secure",
                "unassail" + "able",
            ]
            for word in forbidden:
                self.assertNotIn(word, text, f"Banned word '{word}' found in {fpath}")


if __name__ == "__main__":
    unittest.main()

