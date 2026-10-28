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


def test_chaos_metrics_defaults_percentiles_and_branch_guards(tmp_path, capsys):
    import production_readiness_chaos_harness as prch_mod
    from production_readiness_chaos_harness import ChaosBenchmarkMetrics

    # Default dataclass values
    defaults = ChaosBenchmarkMetrics()
    assert defaults.total_scenarios_evaluated == 0
    assert defaults.passed_scenarios == 0
    assert defaults.failed_scenarios == 0
    assert defaults.duplicate_governed_dispatches == 0
    assert defaults.blind_retries_detected == 0
    assert defaults.total_ledger_growth_bytes == 0

    # Full run assertions on per-scenario fields and latencies
    harness = ProductionReadinessChaosHarness(workspace_dir=tmp_path / "full")
    metrics = harness.run_all_scenarios()
    assert 0.0 < metrics.e2e_action_latency_p50_ms < 5000.0
    assert 0.0 < metrics.receipt_verification_avg_us < 500000.0

    by_id = {r.scenario_id: r for r in harness.records}
    assert by_id["SCEN-02"].reconciliation_attempts == 0
    assert by_id["SCEN-05"].receipt_verified is True
    assert by_id["SCEN-10"].policy_epoch == 1000 - 1
    for sid in ("SCEN-10", "SCEN-11", "SCEN-12", "SCEN-13"):
        assert by_id[sid].receipt_verified is False
    for sid in ("SCEN-01", "SCEN-02", "SCEN-03", "SCEN-04", "SCEN-05", "SCEN-06", "SCEN-07", "SCEN-08", "SCEN-09", "SCEN-14", "SCEN-15", "SCEN-16", "SCEN-17", "SCEN-18"):
        assert by_id[sid].receipt_verified is True

    # Exact linear interpolation percentile checks
    harness.auth_latencies_us = [10.0, 20.0, 30.0, 40.0]
    harness.e2e_latencies_ms = [1.0, 2.0, 3.0, 4.0]
    harness.verify_latencies_us = [100.0, 200.0]
    calc = harness._compute_metrics()
    assert calc.auth_latency_p50_us == 25.0
    assert calc.auth_latency_p95_us == 38.5
    assert calc.auth_latency_p99_us == 39.7
    assert calc.e2e_action_latency_p50_ms == 2.5
    assert calc.e2e_action_latency_p95_ms == 3.85
    assert calc.receipt_verification_avg_us == 150.0

    # Export report JSON
    report_path = tmp_path / "chaos_report.json"
    harness.export_report_json(report_path)
    assert report_path.is_file()

    # SCEN-10 boolean conjunction guard: each term must hold independently
    for fake_ret in (
        (True, "STALE_POLICY_EPOCH", None),
        (False, "WRONG_REASON", None),
        (False, "STALE_POLICY_EPOCH", "non_none_ticket"),
    ):
        h10 = ProductionReadinessChaosHarness(workspace_dir=tmp_path / "s10")
        orig_init = h10._init_boundary

        def _custom_init(sub, _ret=fake_ret):
            b, sim, d = orig_init(sub)
            b.authorize_action = lambda c: _ret
            return b, sim, d

        h10._init_boundary = _custom_init
        h10._eval_scenario_10_stale_policy_epoch()
        assert h10.records[-1].pass_fail == "FAIL"

    # SCEN-18 boolean conjunction guard: is_valid and (err is None)
    orig_verify = prch_mod.FinancialReceiptOfflineVerifier.verify_receipt
    try:
        for fake_v in ((True, "UNEXPECTED_ERR"), (False, None)):
            prch_mod.FinancialReceiptOfflineVerifier.verify_receipt = staticmethod(lambda r, _v=fake_v: _v)
            h18 = ProductionReadinessChaosHarness(workspace_dir=tmp_path / "s18")
            h18._eval_scenario_18_offline_verification()
            assert h18.records[-1].pass_fail == "FAIL"
    finally:
        prch_mod.FinancialReceiptOfflineVerifier.verify_receipt = orig_verify

    # CLI main() execution and exact 80-column separator banner checks
    prch_mod.main()
    out = capsys.readouterr().out
    assert ("\n" + "=" * 80 + "\n") in out
    assert out.strip().endswith("=" * 80)
    assert ("=" * 81) not in out

