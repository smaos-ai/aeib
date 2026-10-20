#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
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
tests/test_temporal_conformance.py — Verification Suite for Temporal Conformance Checker
Verifies the 5 normative temporal invariants from conformance/temporal_invariants_v1.yaml:
1. durable_intent_before_dispatch
2. no_blind_retry_after_uncertainty
3. bounded_reconciliation
4. halt_blocks_future_dispatch
5. no_settlement_without_authoritative_evidence
"""

import subprocess
import sys
import pytest
from tools.temporal_trace_checker import (
    TemporalTraceChecker,
    TemporalConformanceError,
)


def test_rule_1_durable_intent_before_dispatch_falsification():
    checker = TemporalTraceChecker()

    # Step 0: Dispatch without intent -> must fail
    violating_trace = [
        {"operation_id": "op-unpersisted", "action": "DISPATCH"},
    ]
    with pytest.raises(TemporalConformanceError) as exc_info:
        checker.verify_trace(violating_trace)
    assert exc_info.value.rule_id == "durable_intent_before_dispatch"
    assert exc_info.value.step_index == 0


def test_rule_2_no_blind_retry_after_uncertainty_falsification():
    checker = TemporalTraceChecker()

    # Dispatches, times out into indeterminate, then blind retries without reconciliation
    violating_trace = [
        {"operation_id": "op-504", "action": "INTENT_STAGED"},
        {"operation_id": "op-504", "action": "DISPATCH"},
        {"operation_id": "op-504", "action": "TRANSPORT_TIMEOUT_504"},
        {"operation_id": "op-504", "action": "DISPATCH"},  # VIOLATION: blind retry
    ]
    with pytest.raises(TemporalConformanceError) as exc_info:
        checker.verify_trace(violating_trace)
    assert exc_info.value.rule_id == "no_blind_retry_after_uncertainty"
    assert exc_info.value.step_index == 3


def test_rule_3_bounded_reconciliation_falsification():
    # Set horizon to 5 steps
    checker = TemporalTraceChecker(max_reconciliation_horizon_steps=5)

    # Indeterminate state lingers for 6 steps without terminal settlement
    violating_trace = [
        {"operation_id": "op-linger", "action": "INTENT_STAGED"},
        {"operation_id": "op-linger", "action": "DISPATCH"},
        {"operation_id": "op-linger", "action": "TRANSPORT_TIMEOUT_504"},
        {"operation_id": "op-other", "action": "INTENT_STAGED"},
        {"operation_id": "op-other", "action": "DISPATCH"},
        {"operation_id": "op-other", "action": "INTENT_STAGED"},
        {"operation_id": "op-other", "action": "INTENT_STAGED"},
        {"operation_id": "op-other", "action": "INTENT_STAGED"},
        {"operation_id": "op-other", "action": "INTENT_STAGED"},
    ]
    with pytest.raises(TemporalConformanceError) as exc_info:
        checker.verify_trace(violating_trace)
    assert exc_info.value.rule_id == "bounded_reconciliation"


def test_rule_4_halt_blocks_future_dispatch_falsification():
    checker = TemporalTraceChecker()

    violating_trace = [
        {"operation_id": "op-halt", "action": "HALT_CORRUPTED_LEDGER_CHAIN"},
        {"operation_id": "op-subsequent", "action": "INTENT_STAGED"},
        {"operation_id": "op-subsequent", "action": "DISPATCH"},  # VIOLATION after halt
    ]
    with pytest.raises(TemporalConformanceError) as exc_info:
        checker.verify_trace(violating_trace)
    assert exc_info.value.rule_id == "halt_blocks_future_dispatch"


def test_rule_5_no_settlement_without_authoritative_evidence_falsification():
    checker = TemporalTraceChecker()

    # Confirms without evidence indicator
    violating_trace = [
        {"operation_id": "op-unattested", "action": "INTENT_STAGED"},
        {"operation_id": "op-unattested", "action": "DISPATCH"},
        {"operation_id": "op-unattested", "action": "TRANSPORT_TIMEOUT_504"},
        {"operation_id": "op-unattested", "action": "RECONCILE_CONFIRMED"},  # missing evidence
    ]
    with pytest.raises(TemporalConformanceError) as exc_info:
        checker.verify_trace(violating_trace)
    assert exc_info.value.rule_id == "no_settlement_without_authoritative_evidence"
    assert exc_info.value.step_index == 3


def test_nominal_trace_satisfies_all_five_rules():
    checker = TemporalTraceChecker()

    valid_trace = [
        {"operation_id": "op-ok-1", "action": "INTENT_STAGED"},
        {"operation_id": "op-ok-1", "action": "DISPATCH"},
        {"operation_id": "op-ok-1", "action": "TRANSPORT_TIMEOUT_504"},
        {
            "operation_id": "op-ok-1",
            "action": "RECONCILE_CONFIRMED",
            "authoritative_evidence_observed": True,
        },
        {"operation_id": "op-ok-2", "action": "INTENT_STAGED"},
        {"operation_id": "op-ok-2", "action": "DISPATCH"},
        {"operation_id": "op-ok-2", "action": "RECONCILE_REFUTED"},
    ]
    report = checker.verify_trace(valid_trace)
    assert report["valid"] is True
    assert report["evaluated_steps"] == 7
    assert len(report["unresolved_within_horizon"]) == 0


def test_temporal_trace_checker_cli_self_test():
    proc = subprocess.run(
        [sys.executable, "tools/temporal_trace_checker.py", "--self-test"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "Self-test passed" in proc.stdout


def test_temporal_conformance_monitor_direct():
    from tools.temporal_conformance import (
        TemporalConformanceMonitor,
        TemporalViolationError,
        OperationTemporalState,
    )

    mon = TemporalConformanceMonitor(max_reconciliation_horizon_steps=10)
    mon.record_intent("op-1", "caid-1", 100_00, step_index=0)
    assert mon.timelines["op-1"].current_state == OperationTemporalState.INTENT_PERSISTED

    mon.record_dispatch("op-1", "POST /v1/mutations", step_index=1)
    assert mon.timelines["op-1"].current_state == OperationTemporalState.DISPATCH_SENT

    mon.record_uncertainty("op-1", "HTTP_504_TIMEOUT", step_index=2)
    assert mon.timelines["op-1"].current_state == OperationTemporalState.EFFECT_INDETERMINATE

    # Blind retry is blocked
    with pytest.raises(TemporalViolationError) as exc_info:
        mon.record_dispatch("op-1", "POST /v1/mutations", step_index=3)
    assert exc_info.value.rule_id == "no_blind_retry_after_uncertainty"

    # Confirmed settlement with evidence
    mon.record_settlement("op-1", "CONFIRMED", evidence_digest="sha256:evidence1", step_index=4)
    assert mon.timelines["op-1"].current_state == OperationTemporalState.CONFIRMED


def test_temporal_conformance_cli_self_test():
    proc = subprocess.run(
        [sys.executable, "tools/temporal_conformance.py", "--self-test"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "PASSED" in proc.stdout

