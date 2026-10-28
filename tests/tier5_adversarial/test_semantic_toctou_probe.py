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

r"""
test_semantic_toctou_probe.py — Acceptance Test AT52 (Semantic TOCTOU Probe Defense)
Evaluates out-of-band probe verification: when a transport drop occurs and a
compensating transaction or rollback reverses state behind the scenes, a probe
checking केवल record existence misses the rollback. The probe must query authoritative
terminal business state (e.g. balance or status == COMPLETED) and latch to
RECONCILIATION_CONFLICT if semantic mismatch is detected.
"""

import pytest
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.aeib_v040_engine import (
    AEIB040Pipeline,
    Layer7bProbeResult,
)


class TestSemanticTOCTOUProbeAT52:
    def setup_method(self):
        self.pipeline = AEIB040Pipeline()
        self.noun = "Ledger"
        self.verb = "Transfer"
        self.payload = {"transfer_id": "TX-9901", "amount": 1000.0, "currency": "EUR"}

    def test_semantic_mismatch_after_504_latches_conflict(self):
        # Scenario: HTTP 504 occurs. A record exists, but the payload hash doesn't match
        # because the remote system executed a compensating rollback or partial mutation.
        expected_hash = "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        rolled_back_hash = "sha256:fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"

        event = self.pipeline.execute_flow(
            noun=self.noun,
            verb=self.verb,
            payload=self.payload,
            transport_observation="http_504_gateway_timeout",
            transport_status_code=504,
            probe_authority_scope="provider_primary",
            probe_consistency_model="strong_read",
            probe_query_status="PAYLOAD_MISMATCH",
            probe_matched_record_id="TX-9901",
            probe_matched_payload_hash=rolled_back_hash,
            tycho_verdict="VERIFIED",
        )

        attrs = event["attributes"]
        assert attrs["aeib.disposition"] == "RECONCILIATION_CONFLICT"
        assert attrs["aeib.retry_safe"] is False
        assert attrs["aeib.latch_engaged"] is True

    def test_authoritative_commit_match_reconciles_cleanly(self):
        # Scenario: Record found, and payload matches exactly
        event = self.pipeline.execute_flow(
            noun=self.noun,
            verb=self.verb,
            payload=self.payload,
            transport_observation="http_504_gateway_timeout",
            transport_status_code=504,
            probe_authority_scope="provider_primary",
            probe_consistency_model="strong_read",
            probe_query_status="RECORD_FOUND",
            probe_matched_record_id="TX-9901",
            probe_matched_payload_hash="matched",
            tycho_verdict="VERIFIED",
        )

        attrs = event["attributes"]
        assert attrs["aeib.disposition"] in ("OUTCOME_VERIFIED", "CONFIRMED")
        assert attrs["aeib.retry_safe"] is False  # Cannot retry an already confirmed action!
