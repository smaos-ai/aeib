"""Tests + falsification vectors for src/accuracy_cascade_router.py."""

from __future__ import annotations

import dataclasses
import sys

import pytest

from src.accuracy_cascade_router import (
    AcceptanceOracle,
    AccuracyCascadeRouter,
    BASE_ORACLE_CHECKS,
    BPS_SCALE,
    CodingTask,
    LedgerEntry,
    RoutingLedger,
    T2_ORACLE_CHECKS,
    T3_ORACLE_CHECKS,
    build_escalation_packet,
    conformal_risk_upper_bound,
    run_check_out_of_process,
    wilson_lower_bound,
    wilson_upper_bound,
)

CHEAP, STRONG = "cheap", "strong"


def _task(tier="T1", cluster="bugfix", noop=False):
    return CodingTask("t1", cluster, tier, noop, {CHEAP: 0.4, STRONG: 2.0})


def _fill(ledger, model, n, ok, cluster="bugfix"):
    for i in range(n):
        ledger.record(LedgerEntry(cluster, model, i >= (n - ok), False, 0.1, 1000 + i))


def _router(ledger, floor=0.80, min_samples=30):
    return AccuracyCascadeRouter(ledger, CHEAP, STRONG, floor, 0.05, min_samples)


def test_wilson_and_conformal_bounds():
    assert BPS_SCALE == 10000
    assert wilson_lower_bound(0, 0) == 0.0
    assert wilson_lower_bound(1, 1) > 0.0
    assert wilson_lower_bound(10, 10) < 1.0  # perfect small sample is not certainty
    assert wilson_lower_bound(95, 100) > wilson_lower_bound(19, 20) - 0.2
    assert wilson_upper_bound(0, 0) == 1.0
    assert wilson_upper_bound(0, 1) < 1.0
    assert wilson_upper_bound(30, 100) < 0.5
    assert conformal_risk_upper_bound(0, 0) == 1.0
    assert conformal_risk_upper_bound(0, 1) == pytest.approx(0.5)
    assert conformal_risk_upper_bound(0, 19) == pytest.approx(1.0 / 20.0)
    assert conformal_risk_upper_bound(4, 20) == pytest.approx(5.0 / 21.0)
    for fn in (wilson_lower_bound, wilson_upper_bound, conformal_risk_upper_bound):
        with pytest.raises(ValueError):
            fn(5, 3)
        with pytest.raises(ValueError):
            fn(-1, 3)


def test_ledger_entry_defaults_and_immutability():
    e = LedgerEntry("c", CHEAP, True, False, 0.1, 10)
    assert e.escalated is False and e.human_approved is False and e.verified is True
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.cost_usd = 9.9  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        _task().task_id = "mut"  # type: ignore[misc]


def test_noop_halts_at_zero_cost():
    d = _router(RoutingLedger()).route(_task(noop=True))
    assert d.model == "none" and d.reason == "HALT_NO_CHANGE_REQUIRED"
    assert d.estimated_cost_usd == 0.0 and d.accuracy_lower_bound == 0.0
    assert d.requires_human_approval is False and d.escalation_allowed is False


def test_cold_start_fails_closed_and_default_min_samples_is_30():
    led = RoutingLedger()
    _fill(led, CHEAP, 29, 29)
    r_default = AccuracyCascadeRouter(led, CHEAP, STRONG, 0.80)
    assert r_default.min_samples == 30 and r_default.lambda_cost == pytest.approx(0.05)
    d29 = r_default.route(_task())
    assert d29.model == STRONG and "COLD_START" in d29.reason and d29.escalation_allowed is False
    _fill(led, CHEAP, 1, 1)  # 30th trial -> calibrated
    d30 = r_default.route(_task())
    assert d30.model == CHEAP and d30.escalation_allowed is True


def test_exploration_is_deterministic_and_never_on_t2_t3():
    led = RoutingLedger()
    r = AccuracyCascadeRouter(led, CHEAP, STRONG, 0.8, 0.05, 30, exploration_bps=10000)
    d1 = r.route(_task("T1"))
    assert d1.reason == "CALIBRATION_EXPLORATION_ORACLE_GATED"
    assert d1.requires_human_approval is False and d1.escalation_allowed is True
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
    d = _router(led, floor=0.90).route(_task("T2"))
    assert d.model == CHEAP and d.escalation_allowed is True and d.requires_human_approval is True

    # Score comparison: both meet floor (0.80), strong has higher LB (199/200 vs 192/200),
    # cheap wins when lambda_cost=0.30 penalizes strong's higher cost, and strong wins when lambda_cost=0.01
    led_s = RoutingLedger()
    _fill(led_s, CHEAP, 200, 192)
    _fill(led_s, STRONG, 200, 199)
    r_cost_sensitive = AccuracyCascadeRouter(led_s, CHEAP, STRONG, 0.80, lambda_cost=0.30)
    assert r_cost_sensitive.route(_task("T1")).model == CHEAP
    r_acc_sensitive = AccuracyCascadeRouter(led_s, CHEAP, STRONG, 0.80, lambda_cost=0.01)
    d_strong = r_acc_sensitive.route(_task("T1"))
    assert d_strong.model == STRONG and d_strong.reason == "FLOOR_OR_SCORE_PREFERS_STRONG"
    # Inverse cost: if cheap is costlier than strong, strong wins even under high lambda_cost
    expensive_cheap = CodingTask("t1", "bugfix", "T1", False, {CHEAP: 5.0, STRONG: 0.5})
    assert r_cost_sensitive.route(expensive_cheap).model == STRONG


def test_falsify_cheap_point_estimate_above_floor_but_lb_below():
    led = RoutingLedger()
    _fill(led, CHEAP, 30, 28)  # 93% point, LB ~0.79
    _fill(led, STRONG, 200, 198)
    d = _router(led, floor=0.85).route(_task())
    assert d.model == STRONG


def test_falsify_non_stationary_drift_and_conformal_risk_trip():
    """
    Falsification (FV-DRIFT, arXiv:2506.00911):
    Cheap model has 295/300 historical successes (cumulative Wilson LB ~0.96 >= 0.85).
    1) Dispersed window degradation: 4 failures interspersed with successes in last 20 trials
       (consecutive_failures == 0, but conformal risk UB = 5/21 = 0.238 > 0.15) trips to STRONG.
    2) Consecutive failure burst: 3 consecutive failures immediately trips to STRONG.
    """
    led = RoutingLedger()
    for _ in range(300):
        led.record(LedgerEntry("bugfix", CHEAP, True, False, 0.1, 10))
    _fill(led, STRONG, 200, 198)
    r = _router(led, floor=0.85)
    assert r.route(_task()).model == CHEAP

    # 3 failures in 20 trials (17/20 = 0.85 == floor) stays within CRC finite-sample margin
    pattern_ok = [False, True, True, True, False, True, True, True, False, True,
                  True, True, True, True, True, True, True, True, True, True]
    for ok in pattern_ok:
        led.record(LedgerEntry("bugfix", CHEAP, ok, False, 0.1, 10))
    assert r.route(_task()).model == CHEAP

    # Inject 4 failures separated by successes over the 20-trial window (ends with success)
    pattern = [False, True, True, True, False, True, True, True, False, True,
               True, True, False, True, True, True, True, True, True, True]
    for ok in pattern:
        led.record(LedgerEntry("bugfix", CHEAP, ok, False, 0.1, 10))
    assert led.stats("bugfix", CHEAP).consecutive_failures == 0
    assert led.accuracy_lower_bound("bugfix", CHEAP) > 0.90  # cumulative LB still high!
    d_crc = r.route(_task("T1"))
    assert d_crc.model == STRONG and d_crc.reason == "DRIFT_OR_CONFORMAL_RISK_TRIP_TO_STRONG"
    assert d_crc.escalation_allowed is False and d_crc.requires_human_approval is False
    assert r.route(_task("T2")).requires_human_approval is True

    # Recover with 20 consecutive successes -> cheap allowed again
    for _ in range(20):
        led.record(LedgerEntry("bugfix", CHEAP, True, False, 0.1, 10))
    assert r.route(_task()).model == CHEAP

    # Now 3 consecutive failures -> immediate consecutive-failure trip
    for _ in range(3):
        led.record(LedgerEntry("bugfix", CHEAP, False, False, 0.1, 10))
    d_consec = r.route(_task())
    assert d_consec.model == STRONG and d_consec.reason == "DRIFT_OR_CONFORMAL_RISK_TRIP_TO_STRONG"


def test_t3_always_strong_with_human():
    led = RoutingLedger()
    _fill(led, CHEAP, 1000, 1000)
    d = _router(led).route(_task("T3"))
    assert d.model == STRONG and d.requires_human_approval is True and d.escalation_allowed is False


def test_regressions_count_against_accuracy():
    led = RoutingLedger()
    for _ in range(100):
        led.record(LedgerEntry("bugfix", CHEAP, True, True, 0.1, 10))
    assert led.accuracy_lower_bound("bugfix", CHEAP) < 1e-9
    rep = led.calibration_report("bugfix", CHEAP)
    assert rep["false_accept_rate_bps"] == 10000 and rep["cost_per_verified_change_usd"] is None
    assert rep["consecutive_failures"] == 100


def _all(checks):
    return {c: True for c in checks}


def test_oracle_accepts_full_t1_evidence():
    assert AcceptanceOracle.evaluate("T1", _all(BASE_ORACLE_CHECKS), CHEAP).accepted is True


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
    ev["regression_tests_pass"] = "yes"  # type: ignore[assignment]
    assert not AcceptanceOracle.evaluate("T1", ev, CHEAP).accepted


def test_falsify_self_review_rejected_on_t2():
    ev = _all(BASE_ORACLE_CHECKS + T2_ORACLE_CHECKS)
    v = AcceptanceOracle.evaluate("T2", ev, CHEAP, reviewed_by=CHEAP)
    assert not v.accepted and "self_review_not_independent" in v.failed_checks
    assert AcceptanceOracle.evaluate("T2", ev, CHEAP, reviewed_by=STRONG).accepted


def test_falsify_utboost_mutation_adequacy_floor():
    """
    Falsification (FV-UTBOOST, arXiv:2506.09289):
    Even when all boolean test checks are True, a weak test suite with surviving mutants
    below min_mutation_kill_bps is rejected by the sovereign oracle.
    """
    ev = _all(BASE_ORACLE_CHECKS)
    v_missing = AcceptanceOracle.evaluate("T1", ev, CHEAP, min_mutation_kill_bps=9000)
    assert not v_missing.accepted and v_missing.missing_checks == ("mutation_kill_ratio_bps",)

    v_low = AcceptanceOracle.evaluate(
        "T1", ev, CHEAP, mutation_kill_ratio_bps=7333, min_mutation_kill_bps=9000
    )
    assert not v_low.accepted and v_low.failed_checks == ("mutation_adequacy_below_floor",)

    v_ok = AcceptanceOracle.evaluate(
        "T1", ev, CHEAP, mutation_kill_ratio_bps=9000, min_mutation_kill_bps=9000
    )
    assert v_ok.accepted is True

    with pytest.raises(ValueError, match="ERR_INVALID_MUTATION_FLOOR"):
        AcceptanceOracle.evaluate("T1", ev, CHEAP, min_mutation_kill_bps=10001)
    with pytest.raises(ValueError, match="ERR_INVALID_MUTATION_FLOOR"):
        AcceptanceOracle.evaluate("T1", ev, CHEAP, min_mutation_kill_bps=-1)


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
    # Either affected_symbols alone or reverse_callers alone is a valid slice (not empty)
    assert build_escalation_packet(verdict=_failed_verdict(), attempt=1, **base)["affected_symbols"] == ["s"]
    only_callers = dict(base, affected_symbols=[], reverse_callers=["a.py::f"])
    assert build_escalation_packet(verdict=_failed_verdict(), attempt=1, **only_callers)["reverse_callers"] == ["a.py::f"]
    with pytest.raises(RuntimeError, match="HALT_REPAIR_BUDGET_EXHAUSTED"):
        build_escalation_packet(verdict=_failed_verdict(), attempt=4, **base)
    ok = AcceptanceOracle.evaluate("T1", _all(BASE_ORACLE_CHECKS), CHEAP)
    with pytest.raises(ValueError, match="ERR_ESCALATION_OF_ACCEPTED"):
        build_escalation_packet(verdict=ok, attempt=1, **base)
    base["affected_symbols"] = []
    with pytest.raises(ValueError, match="FULL_REPO"):
        build_escalation_packet(verdict=_failed_verdict(), attempt=1, **base)


def test_out_of_process_check(tmp_path):
    assert run_check_out_of_process([sys.executable, "-c", "pass"], str(tmp_path)) is True
    assert run_check_out_of_process([sys.executable, "-c", "raise SystemExit(1)"], str(tmp_path)) is False
    assert (
        run_check_out_of_process(
            [sys.executable, "-c", "import time; time.sleep(5)"], str(tmp_path), timeout_s=1
        )
        is False
    )
    assert run_check_out_of_process(["nonexistent_binary_xyz_404"], str(tmp_path)) is False


def test_wilson_upper_bound_and_exploration_stops_when_implausible():
    led = RoutingLedger()
    _fill(led, CHEAP, 100, 30)  # clearly below floor -> UB < floor -> no exploration
    r = AccuracyCascadeRouter(led, CHEAP, STRONG, 0.85, 0.05, 30, exploration_bps=10000)
    assert r.route(_task()).model == STRONG
    led2 = RoutingLedger()
    _fill(led2, CHEAP, 10, 9)  # uncalibrated (10 < 30), 0 consecutive failures -> explore
    r2 = AccuracyCascadeRouter(led2, CHEAP, STRONG, 0.85, 0.05, 30, exploration_bps=10000)
    assert r2.route(_task()).reason == "CALIBRATION_EXPLORATION_ORACLE_GATED"
    r3 = AccuracyCascadeRouter(led2, CHEAP, STRONG, 0.85, 0.05, 30, 10000, max_exploration_trials=10)
    assert r3.route(_task()).model == STRONG


def test_ledger_rejects_negative_and_report_math():
    led = RoutingLedger()
    with pytest.raises(ValueError):
        led.record(LedgerEntry("c", CHEAP, True, False, -1.0, 0))
    with pytest.raises(ValueError):
        led.record(LedgerEntry("c", CHEAP, True, False, 1.0, -1))
    with pytest.raises(ValueError, match="ERR_INVALID_WINDOW"):
        led.recent_conformal_risk_ub("c", CHEAP, window=0)

    # 2-element latency check kills pct() index arithmetic mutations
    led.record(LedgerEntry("two", CHEAP, True, False, 1.0, 10, escalated=True))
    led.record(LedgerEntry("two", CHEAP, True, False, 1.0, 99, escalated=True))
    assert led.recent_conformal_risk_ub("two", CHEAP, window=1) == pytest.approx(0.5)
    rep2 = led.calibration_report("two", CHEAP)
    assert rep2["accuracy_bps"] == 10000 and rep2["escalation_rate_bps"] == 10000
    assert rep2["latency_p50_ms"] == 10 and rep2["latency_p95_ms"] == 99
    assert rep2["accuracy_wilson_lb_bps"] == int(wilson_lower_bound(2, 2) * 10000)

    for i, lat in enumerate([10, 20, 30, 40, 1000]):
        led.record(LedgerEntry("c", CHEAP, i < 4, False, 0.5, lat, escalated=(i == 4)))
    rep = led.calibration_report("c", CHEAP)
    assert rep["trials"] == 5 and rep["accuracy_bps"] == 8000
    assert rep["escalation_rate_bps"] == 2000
    assert rep["cost_per_verified_change_usd"] == 0.625
    assert rep["latency_p50_ms"] == 30 and rep["latency_p95_ms"] == 1000
    empty = led.calibration_report("none", CHEAP)
    assert empty["latency_p50_ms"] is None and empty["accuracy_bps"] == 0
    assert empty["escalation_rate_bps"] == 0 and empty["false_accept_rate_bps"] == 0


def test_router_param_validation_and_missing_cost():
    led = RoutingLedger()
    bad_Cases = (
        dict(accuracy_floor=0.0),
        dict(accuracy_floor=1.1),
        dict(accuracy_floor=0.9, lambda_cost=-1),
        dict(accuracy_floor=0.9, max_consecutive_failures=0),
        dict(accuracy_floor=0.9, drift_window=0),
    )
    for bad in bad_Cases:
        with pytest.raises(ValueError):
            AccuracyCascadeRouter(led, CHEAP, STRONG, **bad)
    r_min = AccuracyCascadeRouter(
        led, CHEAP, STRONG, 0.9, min_samples=1, max_consecutive_failures=1, drift_window=1
    )
    assert r_min.max_consecutive_failures == 1 and r_min.drift_window == 1 and r_min.min_samples == 1
    with pytest.raises(ValueError, match="ERR_MISSING_COST_ESTIMATE"):
        _router(led).route(CodingTask("t", "c", "T1", False, {CHEAP: 1.0}))
    with pytest.raises(ValueError, match="ERR_UNKNOWN_RISK_TIER"):
        _router(led).route(_task("T9"))
    with pytest.raises(ValueError, match="ERR_UNKNOWN_RISK_TIER"):
        AcceptanceOracle.required_checks("T9")
