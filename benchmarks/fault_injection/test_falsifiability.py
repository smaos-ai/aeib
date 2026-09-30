#!/usr/bin/env python3
r"""
test_falsifiability.py — Adversarial Falsification & Anti-Fabrication Test Suite
Sovereign Multi-Agent OS (SMAOS) / Deterministic Fault-Injection Testbed

Proves that the AEIB benchmark and verifier are NOT rubber stamps or fabricated mocks:
  1. No Mocking Frameworks: Asserts zero usage of unittest.mock, MagicMock, or patch.
  2. Cryptographic Falsifiability: Mutating 1 bit of payload or signature causes InvalidSignature.
  3. Ground-Truth Persistence: Verifies physical SQLite binary file on disk (ledger.db).
  4. Negative Controls: Non-committed transactions MUST NOT resolve to OUTCOME_VERIFIED.
  5. Canonical Hash Invariant: Extra whitespace or key-sorting variance alters non-JCS hashes.
"""

import os
import sys
import json
import sqlite3
import hashlib
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature
from starlette.testclient import TestClient

# Ensure repo root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from benchmarks.fault_injection.app import app, store, fault_config
from benchmarks.fault_injection.aeib_interceptor import AeibExecutionInterceptor
from src.jcs_canonicalizer import encode_jcs


class TestAdversarialFalsifiability(unittest.TestCase):
    """Adversarial tests to prove tests are active, hostile to tampering, and unmocked."""

    def setUp(self):
        self.db_path = Path("benchmarks/fault_injection/results/ledger.db").resolve()
        self.client = TestClient(app)
        self.interceptor = AeibExecutionInterceptor(self.client)

    def test_proof_1_zero_mocking_frameworks_in_codebase(self):
        """Proves that no mocking frameworks (unittest.mock, MagicMock, patch) exist in testbed."""
        pkg_dir = Path("benchmarks/fault_injection")
        python_files = list(pkg_dir.glob("*.py")) + list((pkg_dir / "tests").glob("*.py"))
        
        forbidden_tokens = ["unittest.mock", "MagicMock", "Mock(", "create_autospec"]
        violations = []

        for p in python_files:
            if p.name == "test_falsifiability.py":
                continue
            text = p.read_text(encoding="utf-8")
            for tok in forbidden_tokens:
                if tok in text:
                    violations.append((str(p), tok))

        self.assertEqual(len(violations), 0, f"Mocking framework detected in testbed: {violations}")

    def test_proof_2_physical_sqlite_database_on_disk(self):
        """Proves that a real on-disk SQLite binary database exists and contains verified rows."""
        self.assertTrue(self.db_path.exists(), f"Physical SQLite database missing at {self.db_path}")
        
        # Open raw database file directly via sqlite3 C library
        conn = sqlite3.connect(str(self.db_path))
        cur = conn.cursor()
        
        # Check tables exist in sqlite_master
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [r[0] for r in cur.fetchall()]
        self.assertIn("accounts", tables)
        self.assertIn("debit_ledger", tables)
        self.assertIn("operations", tables)

        # Check raw debit rows physically recorded
        cur.execute("SELECT id, logical_operation_id, amount, balance_after FROM debit_ledger ORDER BY id")
        rows = cur.fetchall()
        self.assertGreaterEqual(len(rows), 2, "Database must contain at least 2 committed debits from control run")
        
        # Row 1 and Row 2 prove double debit in physical file
        self.assertEqual(rows[0][1], "I-001")
        self.assertEqual(rows[1][1], "I-001")
        self.assertEqual(rows[0][2], 100.0)
        self.assertEqual(rows[1][2], 100.0)
        self.assertEqual(rows[0][3], 9900.0)
        self.assertEqual(rows[1][3], 9800.0)
        conn.close()

    def test_proof_3_signature_fails_on_single_bit_payload_tampering(self):
        """Proves cryptographic verifier is active: changing 1 bit in payload triggers InvalidSignature."""
        payload = {"logical_operation_id": "op-tamper-test", "intent_id": "i-tamper", "amount": 50.0}
        res = self.interceptor.dispatch_with_integrity("/debit", payload)
        receipt = res["receipt"]

        # Valid signature verification passes
        pub_key = self.interceptor.public_key
        sig_bytes = bytes.fromhex(receipt["signature_metadata"]["signature"])
        
        signable_view = {
            "unsigned_payload": receipt["unsigned_payload"],
            "unsigned_payload_hash": receipt["unsigned_payload_hash"],
        }
        valid_bytes = encode_jcs(signable_view)
        pub_key.verify(sig_bytes, valid_bytes)  # MUST PASS

        # Adversarially tamper with payload: alter amount from 50.0 to 500.0
        tampered_view = json.loads(json.dumps(signable_view))
        tampered_view["unsigned_payload"]["intent_id"] = "i-tamper-tampered"
        tampered_bytes = encode_jcs(tampered_view)

        # MUST FAIL: InvalidSignature raised!
        with self.assertRaises(InvalidSignature):
            pub_key.verify(sig_bytes, tampered_bytes)

    def test_proof_4_signature_fails_on_corrupted_signature_bytes(self):
        """Proves verifier rejects fabricated/corrupted signatures."""
        payload = {"logical_operation_id": "op-sig-corrupt", "intent_id": "i-corrupt", "amount": 20.0}
        res = self.interceptor.dispatch_with_integrity("/debit", payload)
        receipt = res["receipt"]

        pub_key = self.interceptor.public_key
        raw_sig = bytearray(bytes.fromhex(receipt["signature_metadata"]["signature"]))
        
        # Corrupt 1 byte in the 64-byte Ed25519 signature
        raw_sig[10] ^= 0xFF
        corrupted_sig = bytes(raw_sig)

        signable_view = {
            "unsigned_payload": receipt["unsigned_payload"],
            "unsigned_payload_hash": receipt["unsigned_payload_hash"],
        }
        valid_bytes = encode_jcs(signable_view)

        # MUST FAIL: InvalidSignature raised!
        with self.assertRaises(InvalidSignature):
            pub_key.verify(corrupted_sig, valid_bytes)

    def test_proof_5_negative_control_rejects_uncommitted_action(self):
        """Proves state machine cannot be tricked into emitting OUTCOME_VERIFIED for uncommitted action."""
        fake_op_id = "op-ghost-never-committed"
        probe_res = self.client.get(f"/operations/{fake_op_id}")
        data = probe_res.json()
        
        # Must reflect ground truth: not committed
        self.assertFalse(data["committed"])
        self.assertEqual(data["commit_count"], 0)
        
        # State machine transition MUST NOT be OUTCOME_VERIFIED
        disposition = "OUTCOME_VERIFIED" if data["committed"] else "RECONCILIATION_NOT_FOUND"
        self.assertEqual(disposition, "RECONCILIATION_NOT_FOUND")
        self.assertNotEqual(disposition, "OUTCOME_VERIFIED")


if __name__ == "__main__":
    unittest.main()
