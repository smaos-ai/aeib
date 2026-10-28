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
tests/test_eo1_real_duplicate_benchmark.py
================================================================================
Small-N evaluation of benchmarks/eo1_real_duplicate_benchmark.py. Drives the real
PreDispatchIntentInterlock against the real local HTTP effect target (no mocks):

  - A2 (EO1 interlock) shows zero duplicate effects at the target on F1-F7.
  - A3 (EO1 + read-back reconciler) shows zero duplicate effects on F1-F7 and fewer residual
    INDETERMINATE intents than A2; F7 (read-back times out) stays INDETERMINATE.
  - F8 (regenerated retry after ack loss + restore): the prediction "A3 > 0 duplicates, A4 = 0"
    is asserted as measured at small N (it can fail); A4 refuses the regenerated call.
  - A4 (A3 + effect-key CAID) behaves like A3 on F1-F7 (no regression from the new key).
  - Negative control: A0 (naive retry) shows duplicate effects under F1 (ack lost),
    so the benchmark is able to fail.
  - F9 late commit (LIMBO timeout_late): per-intent predictions by seeded late-commit factor:
    A0 always duplicates (negative control); A3/A4 (unsafe opt-in) duplicate iff the commit lands
    after their single reconcile pass; A4N3 iff it lands after its third spaced probe; A4D never
    duplicates but stays INDETERMINATE; A5 (fenced) never duplicates and refuses the late write.
  - Same seed -> same fault schedule and same effect / duplicate / INDETERMINATE counts.
  - Wilson interval helper evaluated against hand-derivable reference points.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.eo1_real_duplicate_benchmark import (  # noqa: E402
    ARM_NOT_APPLIED_BASIS,
    EFFECT_KEY_REGISTRY,
    F9_LATE_FACTORS,
    F8_REGENERATED_VARIANT,
    FAULTS,
    TOOL_NAME,
    arm_caid,
    build_schedule,
    render_markdown,
    run_benchmark,
    tool_call_payload,
    wilson_ci,
)
from src.eo1_effect_key import compute_effect_caid  # noqa: E402
from src.eo1_write_before_execute import compute_caid  # noqa: E402

SMALL_N = 18  # two intents per fault (balanced schedule, 9 faults)
SEED = 42
PRE_F8_FAULTS = ("F1", "F2", "F3", "F4", "F5", "F6", "F7")


@pytest.fixture(scope="module")
def small_run():
    return run_benchmark(n=SMALL_N, seed=SEED, timeout_s=0.3)


def _counts(result):
    keys = ("actual_effects", "duplicate_effects", "intents_with_duplicate",
            "lost_effects_unflagged", "indeterminate_intents", "refused_submissions")
    return {arm: {k: s[k] for k in keys} for arm, s in result["arms"].items()}


def test_schedule_is_balanced_and_seeded():
    sched = build_schedule(SMALL_N, SEED)
    faults = [f for f, _ in sched]
    for f in FAULTS:
        assert faults.count(f) == SMALL_N // len(FAULTS)
    assert sched == build_schedule(SMALL_N, SEED)
    assert sched != build_schedule(SMALL_N, SEED + 1)


def test_a2_interlock_has_zero_duplicates(small_run):
    a2 = small_run["arms"]["A2"]
    assert a2["total_intents"] == SMALL_N
    for f in PRE_F8_FAULTS:
        assert a2["per_fault"][f]["duplicate_effects"] == 0
    assert all(r["effects"] <= 1 for r in small_run["intents"] if r["arm"] == "A2" and r["fault"] != "F8")


def test_negative_control_a0_duplicates_under_f1(small_run):
    a0_f1 = small_run["arms"]["A0"]["per_fault"]["F1"]
    assert a0_f1["total_intents"] > 0
    assert a0_f1["duplicate_effects"] > 0


def test_a2_indeterminate_cost_is_reported_not_hidden(small_run):
    a2 = small_run["arms"]["A2"]
    # F1/F2/F3/F7 wire faults must latch the CAID rather than silently retry or drop.
    for f in ("F1", "F2", "F3", "F7"):
        pf = a2["per_fault"][f]
        assert pf["indeterminate_intents"] == pf["total_intents"]
    assert a2["indeterminate_intents"] == a2["indeterminate_effect_applied"] + a2["indeterminate_effect_absent"]
    assert a2["lost_effects_unflagged"] == 0
    assert a2["reconcile_probes"] == 0
    assert "INDETERMINATE" in render_markdown(small_run)


def test_a3_reconciler_zero_duplicates_and_fewer_indeterminate(small_run):
    a2, a3 = small_run["arms"]["A2"], small_run["arms"]["A3"]
    assert a3["total_intents"] == SMALL_N
    for f in PRE_F8_FAULTS:
        assert a3["per_fault"][f]["duplicate_effects"] == 0
    assert all(r["effects"] <= 1 for r in small_run["intents"] if r["arm"] == "A3" and r["fault"] not in ("F8", "F9"))
    assert a3["indeterminate_intents"] < a2["indeterminate_intents"]
    assert a3["lost_effects_unflagged"] == 0
    assert a3["reconcile_probes"] > 0


def test_a3_settles_by_readback_per_fault(small_run):
    pf = small_run["arms"]["A3"]["per_fault"]
    # Read-back answers: F1/F3 settle COMMITTED, F2 settles NOT_COMMITTED and its one retry applies.
    for f in ("F1", "F2", "F3", "F4"):
        assert pf[f]["indeterminate_intents"] == 0
        assert pf[f]["actual_effects"] == pf[f]["total_intents"]
    # F7: the read-back itself times out -> stays INDETERMINATE (never guessed, never duplicated).
    assert pf["F7"]["indeterminate_intents"] == pf["F7"]["total_intents"]
    assert pf["F7"]["duplicate_effects"] == 0
    assert pf["F7"]["reconcile_probes"] == 3 * pf["F7"]["total_intents"]
    f2 = [r for r in small_run["intents"] if r["arm"] == "A3" and r["fault"] == "F2"]
    assert all(r["reconcile_statuses"] == ["SETTLED_NOT_COMMITTED"] and "RETRY_SUCCESS" in r["outcomes"] for r in f2)
    a3 = small_run["arms"]["A3"]
    assert a3["reconcile_settled_not_committed"] >= len(f2)
    assert a3["reconcile_left_latched"] == pf["F7"]["total_intents"]


def test_effects_counted_at_target_match_records(small_run):
    for arm, s in small_run["arms"].items():
        recs = [r for r in small_run["intents"] if r["arm"] == arm]
        assert s["actual_effects"] == sum(r["effects"] for r in recs)
        assert s["duplicate_effects"] == sum(max(0, r["effects"] - 1) for r in recs)


def test_f8_regenerated_call_differs_only_in_incidental_fields():
    key = "A4-s42-i0"
    orig, regen = tool_call_payload(key, 0), tool_call_payload(key, F8_REGENERATED_VARIANT)
    changed = {k for k in orig if orig[k] != regen[k]}
    assert changed == {"memo", "client_request_id", "tags"}
    assert list(orig["options"]) != list(regen["options"]) and orig["options"] == regen["options"]
    assert set(orig) == set(regen)
    assert tool_call_payload(key, 0) == orig  # deterministic per (key, variant)
    # Full-payload CAID splits the regenerated call; the effect-key CAID does not.
    assert compute_caid(orig) != compute_caid(regen)
    assert arm_caid("A3", key, 0) != arm_caid("A3", key, F8_REGENERATED_VARIANT)
    assert arm_caid("A4", key, 0) == arm_caid("A4", key, F8_REGENERATED_VARIANT)
    assert arm_caid("A4", key, 0) == compute_effect_caid(TOOL_NAME, orig, EFFECT_KEY_REGISTRY)
    assert arm_caid("A4", key, 0) != arm_caid("A4", "A4-s42-i1", 0)


def test_f8_prediction_a3_duplicates_a4_none(small_run):
    """Prediction under test (not assumed): full-payload CAID lets the regenerated retry through."""
    arms = small_run["arms"]
    n_f8 = arms["A3"]["per_fault"]["F8"]["total_intents"]
    assert n_f8 == SMALL_N // len(FAULTS)
    assert arms["A0"]["per_fault"]["F8"]["duplicate_effects"] > 0
    assert arms["A2"]["per_fault"]["F8"]["duplicate_effects"] > 0
    assert arms["A3"]["per_fault"]["F8"]["duplicate_effects"] > 0
    a4 = arms["A4"]["per_fault"]["F8"]
    assert a4["duplicate_effects"] == 0
    assert a4["actual_effects"] == n_f8
    assert a4["indeterminate_intents"] == 0
    f8_a4 = [r for r in small_run["intents"] if r["arm"] == "A4" and r["fault"] == "F8"]
    assert all(r["outcomes"][-1] == "REFUSED" and "SETTLED_COMMITTED" in r["reconcile_statuses"] for r in f8_a4)
    f8_a3 = [r for r in small_run["intents"] if r["arm"] == "A3" and r["fault"] == "F8"]
    assert all(r["outcomes"][-1] == "SUCCESS" and r["effects"] == 2 for r in f8_a3)
    md = render_markdown(small_run)
    assert "F8 regenerated retry" in md and "A4 EO1 + reconciler + effect-key CAID" in md


def test_a4_matches_a3_on_pre_f8_faults(small_run):
    a3, a4 = small_run["arms"]["A3"]["per_fault"], small_run["arms"]["A4"]["per_fault"]
    keys = ("actual_effects", "duplicate_effects", "indeterminate_intents", "lost_effects_unflagged",
            "reconcile_probes", "reconcile_settled_committed", "reconcile_settled_not_committed")
    for f in PRE_F8_FAULTS:
        assert {k: a4[f][k] for k in keys} == {k: a3[f][k] for k in keys}, f


def test_determinism_same_seed(small_run):
    again = run_benchmark(n=SMALL_N, seed=SEED, timeout_s=0.3)
    assert _counts(again) == _counts(small_run)
    assert again["config"]["fault_counts"] == small_run["config"]["fault_counts"]


def test_wilson_ci_reference_points():
    assert wilson_ci(0, 0) is None
    lo, hi = wilson_ci(0, 10)
    assert lo == 0.0 and 0.27 < hi < 0.28
    lo, hi = wilson_ci(5, 10)
    assert abs((lo + hi) / 2 - 0.5) < 1e-9 and 0.23 < lo < 0.24


# ---------------------------------------------------------------------------
# F9 late commit (LIMBO timeout_late)
# ---------------------------------------------------------------------------


def _f9(small_run, arm):
    return [r for r in small_run["intents"] if r["arm"] == arm and r["fault"] == "F9"]


def test_f9_schedule_draws_late_factors():
    sched = build_schedule(90, SEED)
    factors = [v["late_commit_factor"] for f, v in sched if f == "F9"]
    assert len(factors) == 10 and set(factors) <= set(F9_LATE_FACTORS)
    assert len(set(factors)) > 1
    assert all("late_commit_factor" not in v for f, v in sched if f != "F9")


def test_f9_negative_control_a0_always_duplicates(small_run):
    recs = _f9(small_run, "A0")
    assert len(recs) == SMALL_N // len(FAULTS)
    assert all(r["effects"] == 2 for r in recs)
    pf = small_run["arms"]["A0"]["per_fault"]["F9"]
    assert pf["intents_with_duplicate"] == pf["total_intents"]


def test_f9_unsafe_opt_in_duplicates_iff_commit_after_reconcile(small_run):
    for arm in ("A3", "A4"):
        for r in _f9(small_run, arm):
            late = r["variant"]["late_commit_factor"] > 1.0
            assert r["effects"] == (2 if late else 1), (arm, r["variant"], r["effects"])
            assert r["reconcile_statuses"] == (["SETTLED_NOT_COMMITTED"] if late else ["SETTLED_COMMITTED"])
    for r in _f9(small_run, "A4N3"):
        after_window = r["variant"]["late_commit_factor"] > 3.1
        assert r["effects"] == (2 if after_window else 1), (r["variant"], r["effects"])


def test_f9_fail_closed_default_never_duplicates_but_stays_indeterminate(small_run):
    for r in _f9(small_run, "A4D"):
        late = r["variant"]["late_commit_factor"] > 1.0
        assert r["effects"] == 1
        assert r["indeterminate"] is late
        assert r["reconcile_statuses"] == (["LATCHED_NOT_APPLIED_UNFENCED"] if late else ["SETTLED_COMMITTED"])
    a4d = small_run["arms"]["A4D"]
    assert a4d["duplicate_effects"] == 0 and a4d["reconcile_settled_not_committed"] == 0


def test_f9_fenced_arm_never_duplicates_and_refuses_late_write(small_run):
    recs = _f9(small_run, "A5")
    for r in recs:
        late = r["variant"]["late_commit_factor"] > 1.0
        assert r["effects"] == 1 and r["indeterminate"] is False
        assert r["fenced_refusals"] == (1 if late else 0)
        assert r["fence_calls"] == (1 if late else 0)
    a5, a4d = small_run["arms"]["A5"], small_run["arms"]["A4D"]
    assert a5["duplicate_effects"] == 0
    assert a5["indeterminate_intents"] < a4d["indeterminate_intents"]
    assert a5["lost_effects_unflagged"] == 0 and a5["reconcile_fence_failed"] == 0
    md = render_markdown(small_run)
    assert "F9 late commit" in md and ARM_NOT_APPLIED_BASIS["A5"] in md
