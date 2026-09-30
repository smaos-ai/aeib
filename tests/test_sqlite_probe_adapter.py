#!/usr/bin/env python3
r"""
test_sqlite_probe_adapter.py
Unit tests for SQLiteOutcomeProbeAdapter.
Verifies out-of-band state reconciliation: OUTCOME_VERIFIED, RECONCILIATION_NOT_FOUND,
and RECONCILIATION_FAILED on payload hash tampering or non-committed statuses.
"""

import os
import sys
import tempfile
import unittest

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.sqlite_probe_adapter import SQLiteOutcomeProbeAdapter
from src.jcs_canonicalizer import generate_jcs_payload_hash


class TestSQLiteOutcomeProbeAdapter(unittest.TestCase):
    """Verifies SQLite out-of-band ledger probe adapter behavior."""

    def setUp(self):
        self.adapter = SQLiteOutcomeProbeAdapter(":memory:")

    def tearDown(self):
        self.adapter.close()

    def test_probe_not_found_on_unrecorded_key(self):
        """Unrecorded idempotency key returns RECONCILIATION_NOT_FOUND."""
        res = self.adapter.probe("nonexistent-uuidv5-key")
        self.assertEqual(res, "RECONCILIATION_NOT_FOUND")

    def test_probe_outcome_verified_on_committed_transaction(self):
        """Committed 200 transaction returns OUTCOME_VERIFIED."""
        idem_key = "idem-tx-001"
        self.adapter.record_transaction(
            idempotency_key=idem_key,
            action_id="payment.settle_payment",
            payload_hash="sha256:1111111111111111111111111111111111111111111111111111111111111111",
            status="COMMITTED",
            response_code=200,
        )
        res = self.adapter.probe(idem_key)
        self.assertEqual(res, "OUTCOME_VERIFIED")

    def test_probe_with_matching_expected_payload_hash(self):
        """Matching expected payload hash succeeds with OUTCOME_VERIFIED."""
        idem_key = "idem-tx-002"
        payload_hash = "sha256:2222222222222222222222222222222222222222222222222222222222222222"
        self.adapter.record_transaction(
            idempotency_key=idem_key,
            action_id="wire.dispatch",
            payload_hash=payload_hash,
            status="COMMITTED",
            response_code=200,
        )
        res = self.adapter.probe(idem_key, expected_payload_hash=payload_hash)
        self.assertEqual(res, "OUTCOME_VERIFIED")

    def test_probe_detects_payload_hash_tampering(self):
        """Mismatched payload hash returns RECONCILIATION_FAILED."""
        idem_key = "idem-tx-003"
        original_hash = "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        tampered_hash = "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

        self.adapter.record_transaction(
            idempotency_key=idem_key,
            action_id="wire.dispatch",
            payload_hash=original_hash,
            status="COMMITTED",
            response_code=200,
        )
        res = self.adapter.probe(idem_key, expected_payload_hash=tampered_hash)
        self.assertEqual(res, "RECONCILIATION_FAILED")

    def test_probe_failed_or_error_status_downstream(self):
        """Downstream transaction in non-committed or error state returns RECONCILIATION_FAILED."""
        idem_key_failed = "idem-tx-fail"
        self.adapter.record_transaction(
            idempotency_key=idem_key_failed,
            action_id="wire.dispatch",
            payload_hash="sha256:f1",
            status="FAILED",
            response_code=500,
        )
        self.assertEqual(self.adapter.probe(idem_key_failed), "RECONCILIATION_FAILED")

        idem_key_in_progress = "idem-tx-prog"
        self.adapter.record_transaction(
            idempotency_key=idem_key_in_progress,
            action_id="wire.dispatch",
            payload_hash="sha256:f2",
            status="IN_PROGRESS",
            response_code=200,
        )
        self.assertEqual(self.adapter.probe(idem_key_in_progress), "RECONCILIATION_FAILED")

    def test_probe_detailed_on_committed_record(self):
        """Detailed probe returns full metadata record and outcome_verified=True."""
        idem_key = "idem-tx-det-01"
        p_hash = "sha256:detailed-hash"
        self.adapter.record_transaction(
            idempotency_key=idem_key,
            action_id="action-detailed",
            payload_hash=p_hash,
            status="COMMITTED",
            response_code=201,
        )
        detailed = self.adapter.probe_detailed(idem_key, expected_payload_hash=p_hash)
        self.assertEqual(detailed["disposition"], "OUTCOME_VERIFIED")
        self.assertTrue(detailed["outcome_verified"])
        self.assertIsNotNone(detailed["record"])
        self.assertEqual(detailed["record"]["idempotency_key"], idem_key)
        self.assertEqual(detailed["record"]["action_id"], "action-detailed")
        self.assertEqual(detailed["record"]["payload_hash"], p_hash)
        self.assertEqual(detailed["record"]["status"], "COMMITTED")
        self.assertEqual(detailed["record"]["response_code"], 201)
        self.assertIn("created_at_utc", detailed["record"])

    def test_probe_detailed_on_absent_record(self):
        """Detailed probe on absent record returns None record and outcome_verified=False."""
        detailed = self.adapter.probe_detailed("missing-key")
        self.assertEqual(detailed["disposition"], "RECONCILIATION_NOT_FOUND")
        self.assertFalse(detailed["outcome_verified"])
        self.assertIsNone(detailed["record"])

    def test_on_disk_persistence(self):
        """Verifies persistence and query across independent adapter instances on file DB."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            db_path = tf.name

        try:
            adapter1 = SQLiteOutcomeProbeAdapter(db_path)
            adapter1.record_transaction(
                idempotency_key="persist-key-01",
                action_id="persist-action",
                payload_hash="sha256:persist-hash",
                status="COMMITTED",
                response_code=200,
            )
            adapter1.close()

            # Second instance queries the same file DB
            adapter2 = SQLiteOutcomeProbeAdapter(db_path)
            res = adapter2.probe("persist-key-01", expected_payload_hash="sha256:persist-hash")
            self.assertEqual(res, "OUTCOME_VERIFIED")
            adapter2.close()
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)

    def test_end_to_end_jcs_payload_probe_integration(self):
        """End-to-end integration: hash with RFC 8785 JCS, record downstream, probe state."""
        payload = {
            "source_account": "CZ-99120",
            "destination_account": "DE-44102",
            "amount": 250000.0,
            "currency": "EUR",
            "reference": "INTER-BANK-SETTLEMENT-Q3",
        }
        # Canonical JCS hash
        jcs_hash = f"sha256:{generate_jcs_payload_hash(payload)}"
        idem_key = "idem-jcs-e2e-001"

        # Simulate downstream execution and recording
        self.adapter.record_transaction(
            idempotency_key=idem_key,
            action_id="treasury.disburse_funds",
            payload_hash=jcs_hash,
            status="COMMITTED",
            response_code=200,
        )

        # Agent experiences transport timeout (e.g. HTTP 504) and triggers OOB probe
        # 1. Probing with identical payload succeeds
        probe_res = self.adapter.probe(idem_key, expected_payload_hash=jcs_hash)
        self.assertEqual(probe_res, "OUTCOME_VERIFIED")

        # 2. Probing with semantically mutated payload (e.g. double-spend retry) fails
        mutated_payload = dict(payload)
        mutated_payload["amount"] = 250001.0
        mutated_hash = f"sha256:{generate_jcs_payload_hash(mutated_payload)}"
        tamper_res = self.adapter.probe(idem_key, expected_payload_hash=mutated_hash)
        self.assertEqual(tamper_res, "RECONCILIATION_FAILED")


if __name__ == "__main__":
    unittest.main()
