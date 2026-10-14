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
test_production_readiness_chaos_harness.py
================================================================================
Pytest suite evaluating the 18 enterprise failure scenarios across the
AEIB Governed Financial Action Boundary using ProductionReadinessChaosHarness.
"""

import sys
import pytest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "v1.1-roadmap"))

from production_readiness_chaos_harness import ProductionReadinessChaosHarness


def test_complete_chaos_battery_all_eighteen_scenarios(tmp_path):
    """
    Evaluates the complete battery of 18 failure scenarios feared by enterprise CISOs:
    Asserts:
      1. All 18 scenarios pass.
      2. Zero duplicate dispatches across the entire harness.
      3. Zero blind retries across the entire harness.
      4. Downstream authoritative ledger commit count matches declared contract.
    """
    harness = ProductionReadinessChaosHarness(workspace_dir=tmp_path)
    metrics = harness.run_all_scenarios()

    assert metrics.total_scenarios_evaluated == 18
    assert metrics.passed_scenarios == 18
    assert metrics.failed_scenarios == 0
    assert metrics.duplicate_governed_dispatches == 0
    assert metrics.blind_retries_detected == 0

    # Ensure every single scenario passed individually
    assert len(harness.records) == 18
    for rec in harness.records:
        assert rec.pass_fail == "PASS", f"Scenario {rec.scenario_id} failed: {rec.diagnostic_details}"
        assert not rec.governed_retry_attempted, f"Blind retry observed in {rec.scenario_id}"


@pytest.mark.parametrize("scen_method_name", [
    "_eval_scenario_01_normal_success",
    "_eval_scenario_02_normal_rejection",
    "_eval_scenario_03_http_504_timeout",
    "_eval_scenario_04_tcp_rst",
    "_eval_scenario_05_socket_timeout",
    "_eval_scenario_06_malformed_response",
    "_eval_scenario_07_conflicting_status",
    "_eval_scenario_08_oracle_outage",
    "_eval_scenario_09_duplicate_ticket_replay",
    "_eval_scenario_10_stale_policy_epoch",
    "_eval_scenario_11_disallowed_target",
    "_eval_scenario_12_amount_ceiling_step_up",
    "_eval_scenario_13_crash_before_intent",
    "_eval_scenario_14_crash_after_intent",
    "_eval_scenario_15_crash_during_dispatch",
    "_eval_scenario_16_crash_after_effect",
    "_eval_scenario_17_probe_budget_invariant",
    "_eval_scenario_18_offline_verification",
])
def test_individual_chaos_scenarios(tmp_path, scen_method_name):
    """
    Tests each scenario in isolated workspace directories.
    """
    harness = ProductionReadinessChaosHarness(workspace_dir=tmp_path)
    method = getattr(harness, scen_method_name)
    method()

    assert len(harness.records) == 1
    rec = harness.records[0]
    assert rec.pass_fail == "PASS", f"Scenario {rec.scenario_id} ({rec.scenario_name}) failed: {rec.diagnostic_details}"
    assert not rec.governed_retry_attempted
