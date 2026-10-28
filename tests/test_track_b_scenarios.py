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
tests/test_track_b_scenarios.py — AEIB Track B (Web Mutation Finality) Test Suite
Executes all 11 Track B scenarios (B01 - B11) against the physical harness.
Ground-truth invariant: Evaluated exclusively against target-side ledger state.
"""

import json
import pytest
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.track_b_harness import (
    MockTargetLedger,
    FaultInjector,
    AEIBWebGateway,
)


class TestTrackBWebMutationFinality:
    """Track B Benchmark Scenario Matrix (B01 through B11)."""

    def setup_method(self):
        self.target_ledger = MockTargetLedger()
        self.gateway = AEIBWebGateway(self.target_ledger)

    def test_00_track_b_schema_conformance(self):
        """Validates that Track B schema exists and is syntactically valid."""
        schema_path = REPO_ROOT / "schemas" / "aeib-bench-web-v0.1.schema.json"
        assert schema_path.exists(), "Track B schema must exist"
        schema_data = json.loads(schema_path.read_text(encoding="utf-8"))
        assert schema_data["properties"]["benchmark_track"]["const"] == "Track B: Web Mutation Finality"
        assert schema_data["properties"]["version"]["const"] == "0.1.0"
        assert len(schema_data["properties"]["scenarios"]["items"]["properties"]["scenario_id"]["enum"]) == 18

    def test_b01_nominal_execution(self):
        """B01: Nominal Execution & Response Arrives."""
        res = self.gateway.execute_transaction(
            scenario_id="B01",
            noun="WebCheckout",
            verb="SubmitOrder",
            business_key="order_b01",
            payload={"order_id": "b01", "amount": 100},
            fault_injector=FaultInjector(phase="post_response", wire_event="HTTP_200_OK")
        )
        assert res.gateway_disposition in ("OUTCOME_CONFIRMED", "ACTION_CONFIRMED")
        assert res.outcome == "OUTCOME_CONFIRMED"
        assert res.effect_status == "COMMITTED"
        assert res.retry_safe is False
        assert res.retry_reason == "effect_already_committed"
        assert res.release_authorization == "not_provided"
        assert res.wire_event == "HTTP_200_OK"
        assert res.latch_engaged is False
        assert res.target_ground_truth == "COMMITTED"
        assert res.commit_count == 1

    def test_oracle_independence_assertions(self):
        """Validates that target ledger oracle rejects any context leakage or gateway state."""
        # Querying with valid business key succeeds
        self.target_ledger.commit_mutation("order_iso_01", {"amount": 50})
        rec = self.target_ledger.probe_state("order_iso_01")
        assert rec["status"] == "COMMITTED"

        # Querying with forbidden context parameter raises ValueError
        with pytest.raises(ValueError, match="Oracle independence violation"):
            self.target_ledger.probe_state("order_iso_01", gateway_state="CONFIRMED")

        with pytest.raises(ValueError, match="Oracle independence violation"):
            self.target_ledger.probe_state("order_iso_01", expected_disposition="ACTION_CONFIRMED")

        with pytest.raises(ValueError, match="Oracle independence violation"):
            self.target_ledger.probe_state("order_iso_01", fault_label="504_TIMEOUT")

        with pytest.raises(ValueError, match="Oracle independence violation"):
            self.target_ledger.probe_state("order_iso_01", test_assertion=True)

        with pytest.raises(TypeError, match="Oracle independence violation"):
            self.target_ledger.probe_state(12345)

    def test_b02_pre_body_tcp_rst(self):
        """B02: Response Lost Before Target Commit - Pre-body Drop."""
        res = self.gateway.execute_transaction(
            scenario_id="B02",
            noun="WebCheckout",
            verb="SubmitOrder",
            business_key="order_b02",
            payload={"order_id": "b02", "amount": 200},
            fault_injector=FaultInjector(phase="pre_body", wire_event="TCP_RST")
        )
        assert res.gateway_disposition == "EFFECT_INDETERMINATE"
        assert res.wire_event == "TCP_RST"
        assert res.latch_engaged is True
        assert res.probe_reconciliation == "EFFECT_ABSENT_VIA_PROBE"
        assert res.target_ground_truth == "NOT_FOUND"
        assert res.commit_count == 0

    def test_b03_post_commit_504_timeout(self):
        """B03: Response Lost After Target Commit - HTTP 504 Timeout."""
        res = self.gateway.execute_transaction(
            scenario_id="B03",
            noun="WebCheckout",
            verb="SubmitOrder",
            business_key="order_b03",
            payload={"order_id": "b03", "amount": 300},
            fault_injector=FaultInjector(phase="post_commit", wire_event="HTTP_504_GATEWAY_TIMEOUT")
        )
        assert res.gateway_disposition == "EFFECT_INDETERMINATE"
        assert res.wire_event == "HTTP_504_GATEWAY_TIMEOUT"
        assert res.latch_engaged is True
        assert res.probe_reconciliation == "EFFECT_CONFIRMED_VIA_PROBE"
        assert res.target_ground_truth == "COMMITTED"
        assert res.commit_count == 1

    def test_b04_browser_process_killed_after_click(self):
        """B04: Browser Process Killed After Click."""
        res = self.gateway.execute_transaction(
            scenario_id="B04",
            noun="WebCheckout",
            verb="ClickSubmit",
            business_key="order_b04",
            payload={"order_id": "b04", "amount": 400},
            fault_injector=FaultInjector(phase="post_click", wire_event="FAULT_BROWSER_KILL_POST_COMMIT")
        )
        assert res.gateway_disposition == "EFFECT_INDETERMINATE"
        assert res.wire_event == "FAULT_BROWSER_KILL_POST_COMMIT"
        assert res.latch_engaged is True
        assert res.probe_reconciliation == "EFFECT_CONFIRMED_VIA_PROBE"
        assert res.target_ground_truth == "COMMITTED"
        assert res.commit_count == 1

    def test_b05_tcp_reset_mid_body(self):
        """B05: TCP Reset Mid-Request Body."""
        res = self.gateway.execute_transaction(
            scenario_id="B05",
            noun="WebCheckout",
            verb="SubmitOrder",
            business_key="order_b05",
            payload={"order_id": "b05", "amount": 500},
            fault_injector=FaultInjector(phase="mid_body", wire_event="TCP_RST")
        )
        assert res.gateway_disposition == "EFFECT_INDETERMINATE"
        assert res.wire_event == "TCP_RST"
        assert res.latch_engaged is True
        assert res.probe_reconciliation == "EFFECT_ABSENT_VIA_PROBE"
        assert res.target_ground_truth == "NOT_FOUND"
        assert res.commit_count == 0

    def test_b06_post_commit_stale_dom_banner(self):
        """B06: Post-Commit Drop with Stale Success Banner."""
        res = self.gateway.execute_transaction(
            scenario_id="B06",
            noun="WebCheckout",
            verb="SubmitOrder",
            business_key="order_b06",
            payload={"order_id": "b06", "amount": 600},
            fault_injector=FaultInjector(phase="post_response", wire_event="STALE_DOM_CONFIRMATION")
        )
        assert res.gateway_disposition == "EFFECT_INDETERMINATE"
        assert res.wire_event == "STALE_DOM_CONFIRMATION"
        assert res.latch_engaged is True
        assert res.probe_reconciliation == "EFFECT_CONFIRMED_VIA_PROBE"
        assert res.target_ground_truth == "COMMITTED"
        assert res.commit_count == 1

    def test_b07_pre_dispatch_validation_failure(self):
        """B07: Pre-Dispatch Schema Validation Failure."""
        res = self.gateway.execute_transaction(
            scenario_id="B07",
            noun="WebCheckout",
            verb="SubmitOrder",
            business_key="order_b07",
            payload={"order_id": "b07", "invalid_param": True},
            fault_injector=FaultInjector(phase="pre_dispatch", wire_event="VALIDATION_FAILED")
        )
        assert res.gateway_disposition == "DISPATCH_REJECTED"
        assert res.retry_safe is True
        assert res.wire_event == "VALIDATION_FAILED"
        assert res.target_ground_truth == "NOT_FOUND"
        assert res.commit_count == 0
        assert res.telemetry.bytes_sent == 0, "Zero bytes sent on wire when pre-dispatch fails"

    def test_b08_post_commit_504_drop(self):
        """B08: Post-Commit Drop with HTTP 504 Timeout."""
        res = self.gateway.execute_transaction(
            scenario_id="B08",
            noun="WebCheckout",
            verb="SubmitOrder",
            business_key="order_b08",
            payload={"order_id": "b08", "amount": 800},
            fault_injector=FaultInjector(phase="post_commit", wire_event="HTTP_504_GATEWAY_TIMEOUT")
        )
        assert res.gateway_disposition == "EFFECT_INDETERMINATE"
        assert res.wire_event == "HTTP_504_GATEWAY_TIMEOUT"
        assert res.latch_engaged is True
        assert res.probe_reconciliation == "EFFECT_CONFIRMED_VIA_PROBE"
        assert res.target_ground_truth == "COMMITTED"
        assert res.commit_count == 1

    def test_b09_post_commit_connection_drop(self):
        """B09: Post-Commit Connection Drop."""
        res = self.gateway.execute_transaction(
            scenario_id="B09",
            noun="WebCheckout",
            verb="SubmitOrder",
            business_key="order_b09",
            payload={"order_id": "b09", "amount": 900},
            fault_injector=FaultInjector(phase="post_commit", wire_event="FAULT_CONNECTION_DROP_POST_COMMIT")
        )
        assert res.gateway_disposition == "EFFECT_INDETERMINATE"
        assert res.wire_event == "FAULT_CONNECTION_DROP_POST_COMMIT"
        assert res.latch_engaged is True
        assert res.probe_reconciliation == "EFFECT_CONFIRMED_VIA_PROBE"
        assert res.target_ground_truth == "COMMITTED"
        assert res.commit_count == 1

    def test_b10_pre_body_connection_drop(self):
        """B10: Pre-Body Connection Drop."""
        res = self.gateway.execute_transaction(
            scenario_id="B10",
            noun="WebCheckout",
            verb="SubmitOrder",
            business_key="order_b10",
            payload={"order_id": "b10", "amount": 1000},
            fault_injector=FaultInjector(phase="pre_body", wire_event="CONNECTION_DROP")
        )
        assert res.gateway_disposition == "EFFECT_INDETERMINATE"
        assert res.wire_event == "CONNECTION_DROP"
        assert res.latch_engaged is True
        assert res.probe_reconciliation == "EFFECT_ABSENT_VIA_PROBE"
        assert res.target_ground_truth == "NOT_FOUND"
        assert res.commit_count == 0

    def test_b11_post_click_tcp_reset(self):
        """B11: Post-Click TCP Reset."""
        res = self.gateway.execute_transaction(
            scenario_id="B11",
            noun="WebCheckout",
            verb="ClickSubmit",
            business_key="order_b11",
            payload={"order_id": "b11", "amount": 1100},
            fault_injector=FaultInjector(phase="post_click", wire_event="FAULT_TCP_RST_POST_COMMIT")
        )
        assert res.gateway_disposition == "EFFECT_INDETERMINATE"
        assert res.wire_event == "FAULT_TCP_RST_POST_COMMIT"
        assert res.latch_engaged is True
        assert res.probe_reconciliation == "EFFECT_CONFIRMED_VIA_PROBE"
        assert res.target_ground_truth == "COMMITTED"
        assert res.commit_count == 1

    def test_bt12_duplicate_retry_blocked(self):
        """BT12: Post-Ambiguity Blind Retry Blocked Fail-Closed (Commit Count Remains 1)."""
        # Step 1: Initial dispatch encounters post-commit 504 timeout
        res1 = self.gateway.execute_transaction(
            scenario_id="BT12",
            noun="WebCheckout",
            verb="SubmitOrder",
            business_key="order_bt12",
            payload={"order_id": "bt12", "amount": 1200},
            fault_injector=FaultInjector(phase="post_commit", wire_event="HTTP_504_GATEWAY_TIMEOUT")
        )
        assert res1.gateway_disposition == "EFFECT_INDETERMINATE"
        assert res1.latch_engaged is True
        assert res1.target_ground_truth == "COMMITTED"
        assert res1.commit_count == 1

        # Step 2: Agent attempts speculative/blind retry with the same candidate
        res2 = self.gateway.execute_transaction(
            scenario_id="BT12",
            noun="WebCheckout",
            verb="SubmitOrder",
            business_key="order_bt12",
            payload={"order_id": "bt12", "amount": 1200},
            fault_injector=FaultInjector(phase="post_response", wire_event="HTTP_200_OK")
        )
        assert res2.wire_event == "UNCERTAINTY_LATCHED_RETRY_BLOCKED"
        assert res2.latch_engaged is True
        assert res2.retry_safe is False
        assert res2.attributes["block_reason"] == "UNCERTAINTY_LATCHED_RETRY_BLOCKED"
        assert self.target_ledger.get_commit_count("order_bt12") == 1, "Duplicate retry MUST NOT touch target ledger"

    def test_bt13_probe_tampering_overridden(self):
        """BT13: Immutable Target Ledger State Overrides Client Claim Modifications."""
        res = self.gateway.execute_transaction(
            scenario_id="BT13",
            noun="WebCheckout",
            verb="SubmitOrder",
            business_key="order_bt13",
            payload={"order_id": "bt13", "amount": 1300},
            fault_injector=FaultInjector(phase="post_commit", wire_event="HTTP_504_GATEWAY_TIMEOUT")
        )
        # Agent claims it failed/never committed, but independent target probe confirms committed
        client_self_report = {"claimed_status": "FAILED_NEVER_EXECUTED"}
        probe_result = self.target_ledger.probe_state("order_bt13")
        assert probe_result["status"] == "COMMITTED"
        assert probe_result["status"] != client_self_report["claimed_status"]
        assert res.probe_reconciliation == "EFFECT_CONFIRMED_VIA_PROBE"
        assert res.target_ground_truth == "COMMITTED"

    def test_bt14_probe_disagreement_freezes_authority(self):
        """BT14: Conflicting Target Probes Trigger RECONCILIATION_CONFLICT."""
        def conflicting_probe(bkey: str) -> str:
            return "RECONCILIATION_CONFLICT"

        res = self.gateway.execute_transaction(
            scenario_id="BT14",
            noun="WebCheckout",
            verb="SubmitOrder",
            business_key="order_bt14",
            payload={"order_id": "bt14", "amount": 1400},
            fault_injector=FaultInjector(phase="post_commit", wire_event="HTTP_504_GATEWAY_TIMEOUT"),
            probe_override_fn=conflicting_probe
        )
        assert res.gateway_disposition == "RECONCILIATION_CONFLICT"
        assert res.retry_safe is False
        assert res.attributes["release_status"] == "frozen_dual_control"

    def test_bt15_target_ledger_unavailable_escalates_to_human(self):
        """BT15: Probe Timeouts Preserve EFFECT_INDETERMINATE and Escalate to Human Operator."""
        def timeout_probe(bkey: str) -> str:
            return "PROBE_TIMEOUT"

        res = self.gateway.execute_transaction(
            scenario_id="BT15",
            noun="WebCheckout",
            verb="SubmitOrder",
            business_key="order_bt15",
            payload={"order_id": "bt15", "amount": 1500},
            fault_injector=FaultInjector(phase="post_commit", wire_event="HTTP_504_GATEWAY_TIMEOUT"),
            probe_override_fn=timeout_probe
        )
        assert res.gateway_disposition == "EFFECT_INDETERMINATE"
        assert res.retry_safe is False
        assert res.attributes["escalation"] == "operator_intervention_required"

    def test_bt16_process_restart_recovery_durable_ledger(self):
        """BT16: Durable Out-of-Context Ledger Maintains Uncertainty Latching Across Process Crash."""
        durable_storage = {}
        # Instance 1: Encounters fault and latches CAID in durable store
        gw1 = AEIBWebGateway(self.target_ledger, durable_store=durable_storage)
        res1 = gw1.execute_transaction(
            scenario_id="BT16",
            noun="WebCheckout",
            verb="SubmitOrder",
            business_key="order_bt16",
            payload={"order_id": "bt16", "amount": 1600},
            fault_injector=FaultInjector(phase="post_commit", wire_event="HTTP_504_GATEWAY_TIMEOUT")
        )
        assert res1.latch_engaged is True
        assert self.target_ledger.get_commit_count("order_bt16") == 1

        # Simulate process crash: gw1 volatile memory wiped, instance reconstructed
        del gw1
        gw2 = AEIBWebGateway(self.target_ledger, durable_store=durable_storage)

        # Agent attempts blind retry against new gateway process instance
        res2 = gw2.execute_transaction(
            scenario_id="BT16",
            noun="WebCheckout",
            verb="SubmitOrder",
            business_key="order_bt16",
            payload={"order_id": "bt16", "amount": 1600},
            fault_injector=FaultInjector(phase="post_response", wire_event="HTTP_200_OK")
        )
        assert res2.wire_event == "UNCERTAINTY_LATCHED_RETRY_BLOCKED"
        assert res2.retry_safe is False
        assert self.target_ledger.get_commit_count("order_bt16") == 1

    def test_bt17_browser_session_isolation(self):
        """BT17: Browser Session and Context Profiles Remain Isolated Across Runs."""
        res_ephemeral = self.gateway.execute_transaction(
            scenario_id="BT17",
            noun="WebCheckout",
            verb="SubmitOrder",
            business_key="order_bt17_eph",
            payload={"order_id": "bt17_eph", "amount": 1700},
            fault_injector=FaultInjector(phase="post_response", wire_event="HTTP_200_OK"),
            session_id="session_ephemeral_01",
            context_profile_id="prof_ephemeral"
        )
        assert res_ephemeral.gateway_disposition in ("OUTCOME_CONFIRMED", "ACTION_CONFIRMED")
        assert "session_ephemeral_01" in self.gateway.session_contexts
        assert self.gateway.session_contexts["session_ephemeral_01"]["context_profile_id"] == "prof_ephemeral"

        # Verify distinct persistent session does not share context
        res_pers = self.gateway.execute_transaction(
            scenario_id="BT17",
            noun="WebCheckout",
            verb="SubmitOrder",
            business_key="order_bt17_pers",
            payload={"order_id": "bt17_pers", "amount": 1700},
            fault_injector=FaultInjector(phase="post_response", wire_event="HTTP_200_OK"),
            session_id="session_persistent_02",
            context_profile_id="prof_persistent"
        )
        assert res_pers.gateway_disposition in ("OUTCOME_CONFIRMED", "ACTION_CONFIRMED")
        assert self.gateway.session_contexts["session_persistent_02"]["context_profile_id"] == "prof_persistent"

    def test_bt18_schema_and_caid_invalidation(self):
        """BT18: Parameter or Destination Alteration Changes CAID, Invalidating Prior Approvals."""
        payload_original = {"order_id": "bt18", "amount": 1800}
        payload_mutated = {"order_id": "bt18", "amount": 1801}

        res_orig = self.gateway.execute_transaction(
            scenario_id="BT18",
            noun="WebCheckout",
            verb="SubmitOrder",
            business_key="order_bt18",
            payload=payload_original,
            fault_injector=FaultInjector(phase="post_response", wire_event="HTTP_200_OK")
        )
        res_mutated = self.gateway.execute_transaction(
            scenario_id="BT18",
            noun="WebCheckout",
            verb="SubmitOrder",
            business_key="order_bt18_mut",
            payload=payload_mutated,
            fault_injector=FaultInjector(phase="post_response", wire_event="HTTP_200_OK")
        )

        caid_orig = res_orig.attributes["aeib.caid"]
        caid_mutated = res_mutated.attributes["aeib.caid"]
        assert caid_orig != caid_mutated, "Payload parameter change MUST invalidate CAID"
