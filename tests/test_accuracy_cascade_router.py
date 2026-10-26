"""Tests + falsification vectors for src/accuracy_cascade_router.py."""

from __future__ import annotations

import sys

import pytest

from src.accuracy_cascade_router import (
    AcceptanceOracle,
    AccuracyCascadeRouter,
    BASE_ORACLE_CHECKS,
    CodingTask,
    LedgerEntry,
    RoutingLedger,
    T2_ORACLE_CHECKS,
    T3_ORACLE_CHECKS,
    build_escalation_packet,
    run_check_out_of_process,
    wilson_lower_bound,
)

CHEAP, STRONG = "cheap", "strong"


def _task(tier="T1", cluster="bugfix", noop=False):
    return CodingTask("t1", cluster, tier, noop, {CHEAP: 0.4, STRONG: 2.0})


def _fill(ledger, model, n, ok, cluster="bugfix"):
    for i in range(n):
        ledger.record(LedgerEntry(cluster, model, i < ok, False, 0.1, 1000 + i))


def _router(ledger, floor=0.80, min_samples=30):
    return AccuracyCascadeRouter(ledger, CHEAP, STRONG, floor, 0.05, min_samples)


def test_wilson_bounds():
    assert wilson_lower_bound(0, 0) == 0.0
    assert wilson_lower_bound(10, 10) < 1.0  # perfect small sample is not certainty
    assert wilson_lower_bound(95, 100) > wilson_lower_bound(19, 20) - 0.2
    with pytest.raises(ValueError):
        wilson_lower_bound(5, 3)


def test_noop_halts_at_zero_cost():
    d = _router(RoutingLedger()).route(_task(noop=True))
    assert d.reason == "HALT_NO_CHANGE_REQUIRED" and d.estimated_cost_usd == 0.0


def test_cold_start_fails_closed_to_strong():
    led = RoutingLedger()
    _fill(led, CHEAP, 10, 10)  # perfect but too few samples
    d = _router(led).route(_task())
    assert d.model == STRONG and "COLD_START" in d.reason


def test_exploration_is_deterministic_and_never_on_t2_t3():
    led = RoutingLedger()
    r = AccuracyCascadeRouter(led, CHEAP, STRONG, 0.8, 0.05, 30, exploration_bps=10000)
    assert r.route(_task("T1")).reason == "CALIBRATION_EXPLORATION_ORACLE_GATED"
    assert r.route(_task("T2")).model == STRONG
    assert r.route(_task("T3")).model == STRONG
    r_half = AccuracyCascadeRouter(led, CHEAP, STRONG, 0.8, 0.05, 30, exploration_bps=5000)
    picks = [
        r_half.route(CodingTask(f"t{i}", "bugfix", "T1", False, {CHEAP: 0.4, STRONG: 2.0})).model
        for i in range(400)
    ]
    assert 120 < picks.count(CHEAP) < 280
    assert picks == [
        r_half.route(CodingTask(f"t{i}", "bugfix", "T1", False, {CHEAP: 0.4, STRONG: 2.0})).model
        for i in range(400)
    ]
    with pytest.raises(ValueError):
        AccuracyCascadeRouter(led, CHEAP, STRONG, 0.8, exploration_bps=10001)


def test_cheap_selected_when_calibrated_lb_meets_floor():
    led = RoutingLedger()
    _fill(led, CHEAP, 200, 196)
    _fill(led, STRONG, 200, 198)
    d = _router(led, floor=0.90).route(_task())
    assert d.model == CHEAP and d.escalation_allowed


def test_falsify_cheap_point_estimate_above_floor_but_lb_below():
    led = RoutingLedger()
    _fill(led, CHEAP, 30, 28)  # 93% point, LB ~0.79
    _fill(led, STRONG, 200, 198)
    d = _router(led, floor=0.85).route(_task())
    assert d.model == STRONG


def test_t3_always_strong_with_human():
    led = RoutingLedger()
    _fill(led, CHEAP, 1000, 1000)
    d = _router(led).route(_task("T3"))
    assert d.model == STRONG and d.requires_human_approval and not d.escalation_allowed


def test_regressions_count_against_accuracy():
    led = RoutingLedger()
    for _ in range(100):
        led.record(LedgerEntry("bugfix", CHEAP, True, True, 0.1, 10))
    assert led.accuracy_lower_bound("bugfix", CHEAP) < 1e-9
    rep = led.calibration_report("bugfix", CHEAP)
    assert rep["false_accept_rate_bps"] == 10000 and rep["cost_per_verified_change_usd"] is None


def _all(checks):
    return {c: True for c in checks}


def test_oracle_accepts_full_t1_evidence():
    assert AcceptanceOracle.evaluate("T1", _all(BASE_ORACLE_CHECKS), CHEAP).accepted


def test_falsify_formatter_and_ast_only_is_rejected():
    ev = {"diff_applies_cleanly": True, "syntax_valid": True}
    v = AcceptanceOracle.evaluate("T0", ev, CHEAP)
    assert not v.accepted and "contract_tests_pass" in v.missing_checks


def test_falsify_failed_property_test_rejected():
    ev = _all(BASE_ORACLE_CHECKS)
    ev["property_tests_pass"] = False
    v = AcceptanceOracle.evaluate("T1", ev, CHEAP)
    assert not v.accepted and v.failed_checks == ("property_tests_pass",)


def test_falsify_truthy_non_bool_not_accepted():
    ev = _all(BASE_ORACLE_CHECKS)
    ev["regression_tests_pass"] = "yes"
    assert not AcceptanceOracle.evaluate("T1", ev, CHEAP).accepted


def test_falsify_self_review_rejected_on_t2():
    ev = _all(BASE_ORACLE_CHECKS + T2_ORACLE_CHECKS)
    v = AcceptanceOracle.evaluate("T2", ev, CHEAP, reviewed_by=CHEAP)
    assert not v.accepted and "self_review_not_independent" in v.failed_checks
    assert AcceptanceOracle.evaluate("T2", ev, CHEAP, reviewed_by=STRONG).accepted


def test_t3_requires_human_evidence():
    ev = _all(BASE_ORACLE_CHECKS + T2_ORACLE_CHECKS + T3_ORACLE_CHECKS)
    del ev["exact_human_approval"]
    assert not AcceptanceOracle.evaluate("T3", ev, STRONG, reviewed_by="r").accepted


def _failed_verdict():
    ev = _all(BASE_ORACLE_CHECKS)
    ev["contract_tests_pass"] = False
    return AcceptanceOracle.evaluate("T1", ev, CHEAP)


def test_escalation_packet_slice_only_and_deterministic():
    kw = dict(
        task={"id": "t1"}, contract={"c": 1}, failed_candidate_diff="--- a\n+++ b\n",
        verdict=_failed_verdict(), failing_output="E" * 10000,
        affected_symbols=["create_refund"], reverse_callers=["api/refunds.py"],
        constraints=["no_duplicate_financial_effect"], attempt=1,
    )
    p1, p2 = build_escalation_packet(**kw), build_escalation_packet(**kw)
    assert p1 == p2
    assert p1["failing_output_truncated"] and len(p1["failing_test_output"]) < 4100
    assert p1["failed_checks"] == ["contract_tests_pass"]


def test_falsify_escalation_bounds():
    base = dict(
        task={}, contract={}, failed_candidate_diff="", failing_output="",
        affected_symbols=["s"], reverse_callers=[], constraints=[],
    )
    with pytest.raises(RuntimeError, match="HALT_REPAIR_BUDGET_EXHAUSTED"):
        build_escalation_packet(verdict=_failed_verdict(), attempt=4, **base)
    ok = AcceptanceOracle.evaluate("T1", _all(BASE_ORACLE_CHECKS), CHEAP)
    with pytest.raises(ValueError, match="ERR_ESCALATION_OF_ACCEPTED"):
        build_escalation_packet(verdict=ok, attempt=1, **base)
    base["affected_symbols"] = []
    with pytest.raises(ValueError, match="FULL_REPO"):
        build_escalation_packet(verdict=_failed_verdict(), attempt=1, **base)


def test_out_of_process_check(tmp_path):
    assert run_check_out_of_process([sys.executable, "-c", "pass"], str(tmp_path))
    assert not run_check_out_of_process([sys.executable, "-c", "raise SystemExit(1)"], str(tmp_path))
    assert not run_check_out_of_process(
        [sys.executable, "-c", "import time; time.sleep(5)"], str(tmp_path), timeout_s=1
    )


def test_wilson_upper_bound_and_exploration_stops_when_implausible():
    from src.accuracy_cascade_router import wilson_upper_bound
    assert wilson_upper_bound(0, 0) == 1.0
    assert wilson_upper_bound(30, 100) < 0.5
    led = RoutingLedger()
    _fill(led, CHEAP, 100, 30)  # clearly below floor -> UB < floor -> no exploration
    r = AccuracyCascadeRouter(led, CHEAP, STRONG, 0.85, 0.05, 30, exploration_bps=10000)
    assert r.route(_task()).model == STRONG
    led2 = RoutingLedger()
    _fill(led2, CHEAP, 30, 28)  # LB < floor but UB admits floor -> keep exploring
    r2 = AccuracyCascadeRouter(led2, CHEAP, STRONG, 0.85, 0.05, 30, exploration_bps=10000)
    assert r2.route(_task()).reason == "CALIBRATION_EXPLORATION_ORACLE_GATED"
    r3 = AccuracyCascadeRouter(led2, CHEAP, STRONG, 0.85, 0.05, 30, 10000, max_exploration_trials=30)
    assert r3.route(_task()).model == STRONG


def test_ledger_rejects_negative_and_report_math():
    led = RoutingLedger()
    with pytest.raises(ValueError):
        led.record(LedgerEntry("c", CHEAP, True, False, -1.0, 0))
    with pytest.raises(ValueError):
        led.record(LedgerEntry("c", CHEAP, True, False, 1.0, -1))
    for i, lat in enumerate([10, 20, 30, 40, 1000]):
        led.record(LedgerEntry("c", CHEAP, i < 4, False, 0.5, lat, escalated=(i == 4)))
    rep = led.calibration_report("c", CHEAP)
    assert rep["trials"] == 5 and rep["accuracy_bps"] == 8000
    assert rep["escalation_rate_bps"] == 2000
    assert rep["cost_per_verified_change_usd"] == 0.625
    assert rep["latency_p50_ms"] == 30 and rep["latency_p95_ms"] == 1000
    empty = led.calibration_report("none", CHEAP)
    assert empty["latency_p50_ms"] is None and empty["accuracy_bps"] == 0


def test_router_param_validation_and_missing_cost():
    led = RoutingLedger()
    for bad in (dict(accuracy_floor=0.0), dict(accuracy_floor=1.1), dict(accuracy_floor=0.9, lambda_cost=-1)):
        with pytest.raises(ValueError):
            AccuracyCascadeRouter(led, CHEAP, STRONG, **bad)
    with pytest.raises(ValueError, match="ERR_MISSING_COST_ESTIMATE"):
        _router(led).route(CodingTask("t", "c", "T1", False, {CHEAP: 1.0}))
    with pytest.raises(ValueError, match="ERR_UNKNOWN_RISK_TIER"):
        _router(led).route(_task("T9"))
