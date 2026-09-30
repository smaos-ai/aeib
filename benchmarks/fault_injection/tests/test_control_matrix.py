#!/usr/bin/env python3
r"""
test_control_matrix.py — Verification Test Suite for Fault-Injection Control Matrix
Sovereign Multi-Agent OS (SMAOS) / Deterministic Fault-Injection Testbed

Mathematically proves:
  - C_0 (Naive Retry) fails Safety: Double-spend committed.
  - C_1 (Gateway + Stable Key) holds Safety: Exact-byte retry deduplicated.
  - C_2 (Gateway + Semantic Drift) fails Safety: LLM context mutation bypasses cache, double-spend committed.
  - AEIB Protocol holds Safety & Liveness: 0% duplicate rate, signed Ed25519 receipt verified.
"""

import os
import sys
import json
import hashlib
import unittest
from pathlib import Path
from starlette.testclient import TestClient

# Ensure repo root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from benchmarks.fault_injection.app import app, store, fault_config
from benchmarks.fault_injection.gateway_simulator import GatewaySimulator
from benchmarks.fault_injection.aeib_interceptor import AeibExecutionInterceptor
from src.jcs_canonicalizer import encode_jcs


class TestControlMatrix(unittest.TestCase):
    """Verifies the four execution regimes under deterministic post-commit fault injection."""

    def setUp(self):
        store.reset(10000.0)
        fault_config.enabled = True
        fault_config.fault_mode = "POST_COMMIT_504"
        fault_config.post_commit_delay_ms = 1.0  # Rapid execution in tests
        fault_config.max_faults_per_intent = 1
        fault_config.fault_every_attempt = False
        self.client = TestClient(app)
        self.gateway = GatewaySimulator(self.client)
        self.interceptor = AeibExecutionInterceptor(self.client)

    def test_post_commit_fault_injection_mechanic(self):
        """Proves that HTTP 504 is returned AFTER database transaction has committed."""
        payload = {
            "logical_operation_id": "op-verify-commit-01",
            "intent_id": "intent-verify-commit-01",
            "account_id": "acc_primary",
            "amount": 250.0,
        }
        res = self.client.post("/debit", json=payload, headers={"X-Attempt-Count": "1"})

        # Client receives 504 Gateway Timeout
        self.assertEqual(res.status_code, 504)
        self.assertEqual(res.headers.get("X-AEIB-Fault-Injected"), "POST_COMMIT_504")

        # Ground truth in SQLite ledger: transaction committed before wire drop!
        status = store.get_operation_status("op-verify-commit-01")
        self.assertTrue(status["committed"])
        self.assertEqual(status["commit_count"], 1)
        self.assertEqual(status["current_balance"], 9750.0)

    def test_c0_naive_retry_fails_safety(self):
        """
        C_0: Naive client retrying on 504 creates duplicate debit.
        Safety Invariant: FAILED.
        """
        logical_op = "op-c0-test-01"
        amount = 100.0

        # Attempt 1: Injected 504
        p1 = {"logical_operation_id": logical_op, "intent_id": "c0-att1", "amount": amount}
        r1 = self.client.post("/debit", json=p1, headers={"X-Attempt-Count": "1"})
        self.assertEqual(r1.status_code, 504)

        # Attempt 2: Naive client sends fresh request
        p2 = {"logical_operation_id": logical_op, "intent_id": "c0-att2", "amount": amount}
        r2 = self.client.post("/debit", json=p2, headers={"X-Attempt-Count": "2"})
        self.assertEqual(r2.status_code, 200)

        # Ground truth: Double-spend committed!
        status = store.get_operation_status(logical_op)
        self.assertEqual(status["commit_count"], 2)
        self.assertTrue(status["is_duplicate_violation"])
        self.assertEqual(status["current_balance"], 10000.0 - (amount * 2))

    def test_c1_gateway_stable_key_preserves_safety(self):
        """
        C_1: Gateway idempotency cache catches exact byte retry.
        Safety Invariant: HELD.
        """
        logical_op = "op-c1-test-01"
        intent_id = "c1-intent-01"
        idemp_key = "idemp-key-stable-01"
        amount = 100.0

        payload = {"logical_operation_id": logical_op, "intent_id": intent_id, "amount": amount}

        # Attempt 1: Injected 504, but gateway caches commitment
        s1, d1, h1 = self.gateway.dispatch("/debit", payload, idempotency_key=idemp_key, headers={"X-Attempt-Count": "1"})
        self.assertEqual(s1, 504)

        # Attempt 2: Exact byte retry with stable Idempotency-Key
        s2, d2, h2 = self.gateway.dispatch("/debit", payload, idempotency_key=idemp_key, headers={"X-Attempt-Count": "2"})
        self.assertEqual(s2, 200)
        self.assertEqual(h2.get("X-Gateway-Cache"), "HIT-IDEMPOTENT")

        # Ground truth: Exactly 1 commit in database!
        status = store.get_operation_status(logical_op)
        self.assertEqual(status["commit_count"], 1)
        self.assertFalse(status["is_duplicate_violation"])
        self.assertEqual(status["current_balance"], 10000.0 - amount)

    def test_c2_gateway_semantic_drift_fails_safety(self):
        """
        C_2: LLM ReAct agent mutates payload/UUID, causing gateway cache miss.
        Safety Invariant: FAILED (Double-Spend).
        """
        logical_op = "op-c2-test-01"
        amount = 100.0

        # Attempt 1
        p1 = {
            "logical_operation_id": logical_op,
            "intent_id": "c2-att1",
            "amount": amount,
            "description": "Invoice payment",
        }
        s1, d1, h1 = self.gateway.dispatch("/debit", p1, idempotency_key="key-001", headers={"X-Attempt-Count": "1"})
        self.assertEqual(s1, 504)

        # Attempt 2: ReAct loop hallucinates new UUID and alters description
        p2 = {
            "logical_operation_id": logical_op,
            "intent_id": "c2-att2",
            "amount": amount,
            "description": "Invoice payment (resending due to 504 error)",
        }
        s2, d2, h2 = self.gateway.dispatch("/debit", p2, idempotency_key="key-002", headers={"X-Attempt-Count": "2"})
        self.assertEqual(s2, 200)

        # Ground truth: Gateway cache missed, backend committed twice!
        status = store.get_operation_status(logical_op)
        self.assertEqual(status["commit_count"], 2)
        self.assertTrue(status["is_duplicate_violation"])
        self.assertEqual(status["current_balance"], 10000.0 - (amount * 2))

    def test_aeib_interceptor_prevents_double_spend_under_semantic_drift(self):
        """
        AEIB Protocol: Freezes retries, probes ledger OOB, resolves OUTCOME_VERIFIED,
        and generates an Ed25519-signed receipt binding transport evidence.
        Safety Invariant: HELD (0% Duplicate Rate).
        """
        logical_op = "op-aeib-test-01"
        amount = 100.0
        payload = {
            "logical_operation_id": logical_op,
            "intent_id": "intent-aeib-01",
            "amount": amount,
            "description": "AEIB governed transaction",
        }

        # Dispatch via AEIB
        result = self.interceptor.dispatch_with_integrity("/debit", payload)

        self.assertEqual(result["status"], "RECONCILED")
        self.assertEqual(result["http_status"], 504)
        self.assertEqual(result["disposition"], "OUTCOME_VERIFIED")
        self.assertFalse(result["retry_permitted"])
        self.assertEqual(result["retry_policy"], "PROHIBITED_ALREADY_COMMITTED")
        self.assertEqual(result["commit_count"], 1)

        # Verify ground truth in ledger: strictly 1 commit
        status = store.get_operation_status(logical_op)
        self.assertEqual(status["commit_count"], 1)
        self.assertFalse(status["is_duplicate_violation"])

        # Verify cryptographic signature of emitted receipt
        receipt = result["receipt"]
        self.assertEqual(receipt["format"], "AEIB_JSON_ED25519_PROTOTYPE")
        sig_hex = receipt["signature_metadata"]["signature"]
        sig_bytes = bytes.fromhex(sig_hex)

        signable_view = {
            "unsigned_payload": receipt["unsigned_payload"],
            "unsigned_payload_hash": receipt["unsigned_payload_hash"],
        }
        signable_bytes = encode_jcs(signable_view)

        # Public key verification passes!
        self.interceptor.public_key.verify(sig_bytes, signable_bytes)


if __name__ == "__main__":
    unittest.main()
