#!/usr/bin/env python3
"""
test_dora_annex_ii_prefill.py — Test Suite for DORA RTS 2025/301 Annex II Pre-Fill Generator
Sovereign Multi-Agent OS (SMAOS) / AEIB Category Wedge (P2 / P3)
"""

import os
import sys
import json
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.dora_annex_ii_prefill import (
    DORAAnnexIIPreFillGenerator,
    DORAAnnexIIInitialNotification,
    StatutoryDeadlineEngine,
    validate_lei_mod97,
    SEVERITY_PENDING
)


class TestDORAAnnexIIPreFill(unittest.TestCase):

    def setUp(self):
        self.generator = DORAAnnexIIPreFillGenerator(
            default_entity_name="Test Bank AG",
            default_lei="5493000IBP32UQZ0KL24",
            default_entity_type="CREDIT_INSTITUTION",
            default_authority="Czech National Bank (ČNB)"
        )

        self.sample_receipt = {
            "action_id": "mcp://sess-001/step-02/rpc-101/swift.settle_payment",
            "idempotency_key": "c3a4f89d-7214-5b68-b3de-7a8e52ef1a09",
            "actor": "5493000IBP32UQZ0KL24",
            "dispatched_at": "2026-09-28T14:00:00+00:00",
            "tool_name": "swift.settle_payment",
            "transport_fault_detected": "HTTP_504_GATEWAY_TIMEOUT",
            "disposition": "DISPATCHED_UNCONFIRMED",
            "discrepancy_detected": True,
            "ed25519_signature": "d98f7e2a4b1c3d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e"
        }

    def test_01_mandatory_pending_human_review_invariant(self):
        """Invariant: Impact/Severity Rating must NEVER be auto-classified; must be PENDING_HUMAN_REVIEW."""
        dossier = self.generator.generate_from_receipt(self.sample_receipt)
        self.assertEqual(dossier.impact_severity_rating, SEVERITY_PENDING)
        self.assertTrue(dossier.human_sign_off_required)
        self.assertEqual(dossier.human_sign_off_status, "AWAITING_INCIDENT_COMMANDER")
        self.assertIsNone(dossier.reviewed_by)
        self.assertIsNone(dossier.review_timestamp_utc)

    def test_02_field_mapping_completeness(self):
        """Verifies all mandatory Annex II initial notification fields are populated."""
        dossier = self.generator.generate_from_receipt(self.sample_receipt)
        
        self.assertEqual(dossier.incident_identifier, "DORA-INC-C3A4F89D")
        self.assertEqual(dossier.idempotency_key, "c3a4f89d-7214-5b68-b3de-7a8e52ef1a09")
        self.assertEqual(dossier.reporting_entity_name, "Test Bank AG")
        self.assertEqual(dossier.legal_entity_identifier_lei, "5493000IBP32UQZ0KL24")
        self.assertEqual(dossier.transport_disruption_type, "HTTP_504_GATEWAY_TIMEOUT")
        self.assertEqual(dossier.downstream_reconciliation_status, "DISPATCHED_UNCONFIRMED")
        self.assertTrue(dossier.quarantine_enforced)
        self.assertIn("CRITICAL_OR_IMPORTANT_FUNCTION_IMPACTED", dossier.potential_materiality_triggers)
        self.assertIn("TRANSPORT_DISRUPTION_HTTP_504_GATEWAY_TIMEOUT", dossier.potential_materiality_triggers)
        self.assertEqual(dossier.classification_timestamp_utc, dossier.statutory_deadlines["classification_time_utc"])
        self.assertEqual(dossier.detection_timestamp_utc, dossier.statutory_deadlines["awareness_time_utc"])

    def test_03_statutory_deadlines_dual_threshold(self):
        """Verifies DORA Art. 19(4)(a) min(T_class + 4h, T_aware + 24h) and RTS 2025/301 Art. 4(2) non-adjustment."""
        aware_time = datetime(2026, 9, 28, 10, 0, 0, tzinfo=timezone.utc)
        class_time = datetime(2026, 9, 28, 12, 0, 0, tzinfo=timezone.utc)

        deadlines = StatutoryDeadlineEngine.calculate_deadlines(
            awareness_time=aware_time,
            classification_time=class_time,
            entity_type="CREDIT_INSTITUTION"
        )

        # T_class + 4h = 16:00, T_aware + 24h = next day 10:00. Earliest is 16:00.
        expected_initial = class_time + timedelta(hours=4)
        expected_intermediate = class_time + timedelta(hours=72)

        self.assertEqual(deadlines["initial_notification_deadline_utc"], expected_initial.isoformat())
        self.assertEqual(deadlines["intermediate_report_deadline_utc"], expected_intermediate.isoformat())
        self.assertTrue(deadlines["rts_2025_301_art4_2_non_adjustment"])

    def test_04_statutory_deadlines_awareness_threshold_binds(self):
        """Verifies that when classification is delayed, awareness + 24h binds if earlier than class + 4h."""
        aware_time = datetime(2026, 9, 28, 0, 0, 0, tzinfo=timezone.utc)
        class_time = datetime(2026, 9, 28, 22, 0, 0, tzinfo=timezone.utc)

        deadlines = StatutoryDeadlineEngine.calculate_deadlines(
            awareness_time=aware_time,
            classification_time=class_time,
            entity_type="CREDIT_INSTITUTION"
        )

        # T_aware + 24h = Sept 29 00:00
        # T_class + 4h  = Sept 29 02:00
        # Earliest is T_aware + 24h (Sept 29 00:00)
        expected_initial = aware_time + timedelta(hours=24)
        self.assertEqual(deadlines["initial_notification_deadline_utc"], expected_initial.isoformat())

    def test_05_human_sign_off_workflow(self):
        """Verifies human sign-off transitions status and preserves incident commander notes."""
        dossier = self.generator.generate_from_receipt(self.sample_receipt)
        
        updated = self.generator.sign_human_review(
            dossier=dossier,
            reviewer_name="Dr. Elena Rossi, Lead ICT Risk Officer",
            assigned_severity="MAJOR",
            notes="Cross-border core payment settlement stalled. Fail-closed quarantine prevented phantom replay."
        )

        self.assertEqual(updated.impact_severity_rating, "MAJOR")
        self.assertEqual(updated.human_sign_off_status, "SIGNED_OFF")
        self.assertEqual(updated.reviewed_by, "Dr. Elena Rossi, Lead ICT Risk Officer")
        self.assertIsNotNone(updated.review_timestamp_utc)
        self.assertIn("Fail-closed quarantine", updated.reviewer_verdict_notes)

    def test_06_human_sign_off_invalid_rating_rejected(self):
        """Verifies that invalid severity ratings are strictly rejected with ValueError."""
        dossier = self.generator.generate_from_receipt(self.sample_receipt)
        
        with self.assertRaises(ValueError):
            self.generator.sign_human_review(
                dossier=dossier,
                reviewer_name="Incident Commander",
                assigned_severity="LOW_NOT_A_DORA_RATING",
                notes="Invalid rating should fail"
            )

    def test_07_iso_17442_lei_mod97_validation(self):
        """Tests ISO 17442 Mod-97 checksum validation logic."""
        # Valid LEI (UniCredit S.p.A. LEI)
        self.assertTrue(validate_lei_mod97("5493000IBP32UQZ0KL24"))
        # Invalid checksum
        self.assertFalse(validate_lei_mod97("5493000IBP32UQZ0KL25"))
        # Invalid length
        self.assertFalse(validate_lei_mod97("SHORT_LEI"))
        # Empty string
        self.assertFalse(validate_lei_mod97(""))

    def test_08_markdown_rendering(self):
        """Verifies Markdown rendering contains mandatory statutory disclaimers and tables."""
        dossier = self.generator.generate_from_receipt(self.sample_receipt)
        md = self.generator.render_markdown(dossier)
        
        self.assertIn("DORA RTS 2025/301 Annex II", md)
        self.assertIn("PENDING HUMAN REVIEW", md)
        self.assertIn("5493000IBP32UQZ0KL24", md)
        self.assertIn("swift.settle_payment", md)
        self.assertIn("HTTP_504_GATEWAY_TIMEOUT", md)
        self.assertIn("DORA Art. 19(4)(a)", md)


if __name__ == "__main__":
    unittest.main(verbosity=2)
