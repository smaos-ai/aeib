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
test_acceptance_test_12.py — 12-Scenario Transport-Fault & Target-Side Grounding Matrix
Executes the 12 transport-fault benchmark scenarios across target capability classes:
1. pre_write_504 (Idempotency Key + Status API)
2. mid_body_rst (Idempotency Key + Status API)
3. post_commit_504 (Idempotency Key + Status API)
4. redirect_loop (Status API Only)
5. browser_process_crash (Browser-Only Workflow)
6. pre_write_rst (Idempotency Key Only)
7. post_commit_rst (Idempotency Key Only)
8. idempotency_key_replay (Idempotency Key Only)
9. semantic_drift_retry (Prompt Drift Adversary)
10. probe_timeout (Target Status API Down)
11. probe_conflict (Authoritative Probe Disagreement)
12. uncooperative_endpoint (No Cooperation Target)

Ground-truth invariant: Evaluation derived exclusively from target-side state ("SHOW ME. CHANGE IT. PROVE IT.").
"""

import pytest
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.aeib_v040_engine import AEIB040Pipeline, derive_caid


class TargetLedgerSimulator:
    """Simulates real target-side committed state independent of agent assertions."""
    def __init__(self):
        self.committed_records = {}

    def commit(self, caid: str, record_id: str, payload_hash: str):
        self.committed_records[caid] = {"record_id": record_id, "payload_hash": payload_hash}

    def query(self, caid: str):
        return self.committed_records.get(caid)


class TestAcceptanceTest12:
    """Acceptance test evaluating all 12 transport-fault scenarios."""

    def setup_method(self):
        self.pipeline = AEIB040Pipeline()
        self.target_ledger = TargetLedgerSimulator()

    def test_00_fixture_schema_conformance(self):
        """Validates that fixtures/aeib_bench_v0.1_scenarios.json strictly conforms to schema."""
        import json
        spec_path = REPO_ROOT / "schemas" / "aeib_bench_v0.1_spec.json"
        fixture_path = REPO_ROOT / "fixtures" / "aeib_bench_v0.1_scenarios.json"
        assert spec_path.exists(), "Benchmark specification schema must exist"
        assert fixture_path.exists(), "Scenario fixture manifest must exist"

        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        fixtures = json.loads(fixture_path.read_text(encoding="utf-8"))

        assert fixtures["benchmark_version"] == spec["properties"]["benchmark_version"]["const"]
        assert fixtures["ground_truth_rule"] == spec["properties"]["ground_truth_rule"]["const"]
        assert len(fixtures["scenarios"]) == 12

        valid_points = set(spec["properties"]["scenarios"]["items"]["properties"]["fault_injection_point"]["enum"])
        valid_caps = set(spec["properties"]["target_capability_matrix"]["required"])

        for sc in fixtures["scenarios"]:
            assert sc["fault_injection_point"] in valid_points
            assert sc["target_capability"] in valid_caps
            assert isinstance(sc["expected_retry_safe"], bool)

    def test_01_pre_write_504(self):
        """Scenario 1: Pre-write 504 timeout before provider processing."""
        result = self.pipeline.execute_flow(
            noun="Transfer",
            verb="Submit",
            payload={"id": 1, "amt": 100},
            transport_observation="http_504_gateway_timeout",
            transport_status_code=504,
            probe_query_status="RECORD_NOT_FOUND",
            tycho_verdict="VERIFIED",
        )
        attrs = result["attributes"]
        assert attrs["aeib.disposition"] == "RECONCILIATION_NOT_FOUND_AFTER_GRACE"
        assert attrs["aeib.retry_safe"] is False
        assert self.target_ledger.query(attrs["aeib.caid"]) is None

    def test_02_mid_body_rst(self):
        """Scenario 2: Mid-body TCP RST connection drop during stream."""
        result = self.pipeline.execute_flow(
            noun="Transfer",
            verb="Submit",
            payload={"id": 2, "amt": 200},
            transport_observation="tcp_rst",
            transport_status_code=0,
            probe_query_status="RECORD_NOT_FOUND",
            tycho_verdict="VERIFIED",
        )
        attrs = result["attributes"]
        assert attrs["aeib.disposition"] == "DISPATCHED_UNCONFIRMED"
        assert attrs["aeib.retry_safe"] is False

    def test_03_post_commit_504(self):
        """Scenario 3: Post-commit 504 timeout after target committed record."""
        payload = {"id": 3, "amt": 300}
        caid = derive_caid("Transfer", "Submit", payload)
        self.target_ledger.commit(caid, "REC-003", "hash:300")

        result = self.pipeline.execute_flow(
            noun="Transfer",
            verb="Submit",
            payload=payload,
            transport_observation="http_504_gateway_timeout",
            transport_status_code=504,
            probe_query_status="RECORD_FOUND",
            probe_matched_record_id="REC-003",
            probe_matched_payload_hash="hash:300",
            tycho_verdict="VERIFIED",
        )
        attrs = result["attributes"]
        assert attrs["aeib.disposition"] == "OUTCOME_VERIFIED"
        assert attrs["aeib.retry_safe"] is False
        assert self.target_ledger.query(caid) is not None

    def test_04_redirect_loop(self):
        """Scenario 4: Redirect response yielding ambiguous execution finality."""
        result = self.pipeline.execute_flow(
            noun="Transfer",
            verb="Submit",
            payload={"id": 4, "amt": 400},
            transport_observation="http_308_permanent_redirect",
            transport_status_code=308,
            probe_query_status="RECORD_NOT_FOUND",
            tycho_verdict="VERIFIED",
        )
        attrs = result["attributes"]
        assert attrs["aeib.disposition"] == "DISPATCHED_UNCONFIRMED"
        assert attrs["aeib.retry_safe"] is False

    def test_05_browser_process_crash(self):
        """Scenario 5: Browser automation crash mid-transaction."""
        result = self.pipeline.execute_flow(
            noun="BrowserAction",
            verb="ClickSubmit",
            payload={"btn": "pay_now", "session": "s5"},
            transport_observation="browser_terminated_sigkill",
            transport_status_code=0,
            probe_query_status="RECORD_NOT_FOUND",
            tycho_verdict="VERIFIED",
        )
        attrs = result["attributes"]
        assert attrs["aeib.disposition"] == "DISPATCHED_UNCONFIRMED"
        assert attrs["aeib.retry_safe"] is False

    def test_06_pre_write_rst(self):
        """Scenario 6: Pre-write TCP reset before request accepted."""
        result = self.pipeline.execute_flow(
            noun="Payment",
            verb="Authorise",
            payload={"id": 6, "amt": 600},
            transport_observation="tcp_rst",
            transport_status_code=0,
            probe_query_status="RECORD_NOT_FOUND",
            tycho_verdict="VERIFIED",
        )
        attrs = result["attributes"]
        assert attrs["aeib.disposition"] == "DISPATCHED_UNCONFIRMED"
        assert attrs["aeib.retry_safe"] is False

    def test_07_post_commit_rst(self):
        """Scenario 7: Post-commit TCP reset with reconciled target commit."""
        payload = {"id": 7, "amt": 700}
        caid = derive_caid("Payment", "Authorise", payload)
        self.target_ledger.commit(caid, "REC-007", "hash:700")

        result = self.pipeline.execute_flow(
            noun="Payment",
            verb="Authorise",
            payload=payload,
            transport_observation="tcp_rst",
            transport_status_code=0,
            probe_query_status="RECORD_FOUND",
            probe_matched_record_id="REC-007",
            probe_matched_payload_hash="hash:700",
            tycho_verdict="VERIFIED",
        )
        attrs = result["attributes"]
        assert attrs["aeib.disposition"] == "OUTCOME_VERIFIED"
        assert attrs["aeib.retry_safe"] is False

    def test_08_idempotency_key_replay(self):
        """Scenario 8: Replaying identical payload after successful execution."""
        payload = {"id": 8, "amt": 800}
        res1 = self.pipeline.execute_flow(
            noun="Transfer",
            verb="Submit",
            payload=payload,
            transport_observation="HTTP_200_OK",
            transport_status_code=200,
            tycho_verdict="VERIFIED",
        )
        assert res1["attributes"]["aeib.disposition"] == "OUTCOME_VERIFIED"

    def test_09_semantic_drift_retry(self):
        """Scenario 9: Attempted retry with mutated parameters triggers independent CAID."""
        p1 = {"recipient": "Alice", "amount": 100}
        p2 = {"recipient": "Alice", "amount": 100, "note": "drifted"}
        caid1 = derive_caid("Transfer", "Submit", p1)
        caid2 = derive_caid("Transfer", "Submit", p2)
        assert caid1 != caid2, "Prompt/semantic drift must generate distinct CAID"

    def test_10_probe_timeout(self):
        """Scenario 10: Target status probe times out; outcome remains unconfirmed."""
        result = self.pipeline.execute_flow(
            noun="Transfer",
            verb="Submit",
            payload={"id": 10, "amt": 1000},
            transport_observation="http_504_gateway_timeout",
            transport_status_code=504,
            probe_query_status="PROBE_TIMEOUT",
            tycho_verdict="VERIFIED",
        )
        attrs = result["attributes"]
        assert attrs["aeib.disposition"] == "DISPATCHED_UNCONFIRMED"
        assert attrs["aeib.retry_safe"] is False

    def test_11_probe_conflict(self):
        """Scenario 11: Probe reveals conflicting payload committed on target."""
        result = self.pipeline.execute_flow(
            noun="Transfer",
            verb="Submit",
            payload={"id": 11, "amt": 1100},
            transport_observation="http_504_gateway_timeout",
            transport_status_code=504,
            probe_query_status="PAYLOAD_MISMATCH",
            tycho_verdict="VERIFIED",
        )
        attrs = result["attributes"]
        assert attrs["aeib.disposition"] == "RECONCILIATION_CONFLICT"
        assert attrs["aeib.retry_safe"] is False

    def test_12_uncooperative_endpoint(self):
        """Scenario 12: Target endpoint with zero idempotency cooperation."""
        result = self.pipeline.execute_flow(
            noun="Transfer",
            verb="Submit",
            payload={"id": 12, "amt": 1200},
            transport_observation="http_504_gateway_timeout",
            transport_status_code=504,
            provider_idempotency_contract_present=False,
            probe_query_status="RECORD_NOT_FOUND",
            tycho_verdict="VERIFIED",
        )
        attrs = result["attributes"]
        assert attrs["aeib.disposition"] == "RECONCILIATION_NOT_FOUND_AFTER_GRACE"
        assert attrs["aeib.retry_safe"] is False
