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
tests/test_eo1_protocol_model_checker.py
================================================================================
Evaluates src/eo1_protocol_model_checker.py:
  - A4 (effect-key CAID + read-back reconciler): every reachable state satisfies all five
    invariants; exact state / transition counts are pinned as a regression oracle and the
    reachable set is re-derived by an independent DFS.
  - Four ablations each yield the expected shortest counterexample (BFS order).
  - Unit checks of successors and of each invariant on hand-built states (positive and
    negative), so the invariants are not trivially true.
  - The TLA+ module no longer contains the vacuous CHOOSE and names the same invariants.
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.eo1_protocol_model_checker import (  # noqa: E402
    APPLIED,
    CONFIGS,
    CONFIRMED,
    DISPATCHED,
    IDLE,
    INDETERMINATE,
    INVARIANTS,
    LATCHED,
    NO_READBACK,
    NOT_APPLIED,
    REFUTED,
    REJECTED,
    RELEASED,
    UNKNOWN,
    ModelConstants,
    ModelState,
    OpVars,
    ProtocolConfig,
    check,
    check_all,
    format_trace,
    initial_state,
    main,
    successors,
)

A4 = CONFIGS["A4_EFFECT_KEY_AND_RECONCILER"]
A4D = CONFIGS["A4_DEFAULT_FAIL_CLOSED"]
A5 = CONFIGS["A5_FENCED"]
C = ModelConstants()
NOLATE = ModelConstants(late_commit=False)
TLA_PATH = ROOT / "formal" / "tlaplus" / "AEIBStation1And2.tla"


@pytest.fixture(scope="module")
def results():
    return check_all()


def _actions(trace):
    return [(s.action, s.op, s.args) for s in trace]


def _st(*ops, reserved=0, settled=0):
    return ModelState(tuple(ops), reserved, settled)


def _explore(cfg, constants):
    init = initial_state(constants)
    seen = {init}
    stack = [init]
    edges = 0
    actions = set()
    while stack:
        s = stack.pop()
        for a, _o, args, nxt in successors(s, cfg, constants):
            edges += 1
            actions.add((a, args))
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen, edges, actions


# ---------------------------------------------------------------------------
# Late commits (LIMBO timeout_late): A4 trusting NOT_APPLIED duplicates; A5 fenced holds
# ---------------------------------------------------------------------------


def test_a4_trusting_not_applied_duplicates_under_late_commit(results):
    r = results["A4_EFFECT_KEY_AND_RECONCILER"]
    assert set(r.violations) == {"SafetyNoDuplicateEffect"}
    t = r.violations["SafetyNoDuplicateEffect"]
    assert _actions(t) == [
        ("AuthorizeAndReserve", "op1", ("1", "clean")),
        ("Transport", "op1", ("timeout_late",)),
        ("Readback", "op1", ("NOT_APPLIED",)),
        ("LateCommit", "op1", ("1",)),
        ("ReconcileRefuted", "op1", ()),
        ("Redispatch", "op1", ()),
        ("Transport", "op1", ("200",)),
    ]
    assert t[-1].state.ops[0].effects == 2 and t[-1].state.ops[0].attempts == 2
    assert (r.distinct_states, r.transitions, r.max_depth, r.terminal_states) == (48927, 196154, 20, 1804)
    assert r.violating_state_counts["SafetyNoDuplicateEffect"] == 7400


def test_a5_fenced_all_invariants_hold_exhaustively(results):
    r = results["A5_FENCED"]
    assert r.all_invariants_hold and r.violations == {} and r.violating_state_counts == {}
    assert (r.distinct_states, r.transitions, r.max_depth, r.terminal_states) == (34047, 116952, 20, 1285)
    assert r.config == "A5_FENCED" and r.constants == C


def test_a4_default_fail_closed_holds_but_never_redispatches(results):
    r = results["A4_DEFAULT_FAIL_CLOSED"]
    assert r.all_invariants_hold
    assert (r.distinct_states, r.transitions, r.max_depth, r.terminal_states) == (2759, 8670, 10, 225)
    _seen, _edges, actions = _explore(A4D, C)
    assert not any(a in ("ReconcileRefuted", "Redispatch", "FenceAndRefute") for a, _ in actions)


def test_a5_reachable_set_matches_independent_dfs_and_every_state_holds(results):
    seen, edges, actions = _explore(A5, C)
    for s in seen:
        for name, inv in INVARIANTS.items():
            assert inv(s, C) is True, (name, s)
    assert len(seen) == results["A5_FENCED"].distinct_states
    assert edges == results["A5_FENCED"].transitions
    for a in (("LateCommit", ("1",)), ("InflightEnds", ("fenced",)), ("InflightEnds", ("expired",)),
              ("FenceAndRefute", ("2",)), ("FenceObservesApplied", ("2",)), ("Transport", ("timeout_late",))):
        assert a in actions, a
    assert not any(a == "ReconcileRefuted" for a, _ in actions)
    assert any(o.inflight == 1 and o.fence_below == 2 and o.state == DISPATCHED for s in seen for o in s.ops)


def test_without_late_commits_a4_and_a5_match_previous_space():
    for cfg in (A4, A5):
        r = check(cfg, NOLATE)
        assert r.all_invariants_hold
        assert (r.distinct_states, r.transitions, r.max_depth, r.terminal_states) == (5175, 14140, 18, 409)
    _seen, _e, actions = _explore(A4, NOLATE)
    assert not any(a in ("LateCommit", "InflightEnds") for a, _ in actions)
    assert ("Transport", ("timeout_late",)) not in actions


# ---------------------------------------------------------------------------
# A4 without late commits: exhaustive, all invariants hold
# ---------------------------------------------------------------------------


def test_a4_all_invariants_hold_exhaustively_without_late_commit():
    r = check(A4, NOLATE)
    assert r.all_invariants_hold
    assert r.violations == {} and r.violating_state_counts == {}
    assert r.distinct_states == 5175
    assert r.transitions == 14140
    assert r.max_depth == 18
    assert r.terminal_states == 409
    assert r.config == "A4_EFFECT_KEY_AND_RECONCILER" and r.constants == NOLATE


def test_a4_reachable_set_matches_independent_dfs_and_every_state_holds():
    C = NOLATE
    reference = check(A4, NOLATE)
    init = initial_state(C)
    seen = {init}
    stack = [init]
    edges = 0
    while stack:
        s = stack.pop()
        for name, inv in INVARIANTS.items():
            assert inv(s, C), (name, s)
        for _a, _o, _args, nxt in successors(s, A4, C):
            edges += 1
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    assert len(seen) == reference.distinct_states
    assert edges == reference.transitions


def test_a4_reaches_every_protocol_situation():
    """Coverage check: the explored space contains F7 latches, refute+redispatch and refused regenerations."""
    C = NOLATE
    init = initial_state(C)
    seen = {init}
    stack = [init]
    actions = set()
    while stack:
        s = stack.pop()
        for a, _o, args, nxt in successors(s, A4, C):
            actions.add((a, args))
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    for fault in ("200", "timeout_pre", "timeout_post", "http500_post"):
        assert ("Transport", (fault,)) in actions
    for r in ("APPLIED", "NOT_APPLIED", "UNKNOWN"):
        assert ("Readback", (r,)) in actions
    assert ("Redispatch", ()) in actions
    assert ("RegeneratedRetry", ("same_effect_key_refused",)) in actions
    assert not any(a == "NaiveRetry" for a, _ in actions)
    assert any(o.readback == UNKNOWN for s in seen for o in s.ops)
    assert any(o.attempts == 2 and o.state == CONFIRMED for s in seen for o in s.ops)


# ---------------------------------------------------------------------------
# Ablations: shortest counterexamples
# ---------------------------------------------------------------------------


def test_bug_escrow_drift_counterexample(results):
    r = results["BUG_VACUOUS_ESCROW_DRIFT"]
    assert set(r.violations) == {"SafetyEscrowIdentity", "SafetyNoDuplicateEffect"}
    t = r.violations["SafetyEscrowIdentity"]
    assert _actions(t) == [
        ("AuthorizeAndReserve", "op1", ("1", "clean")),
        ("Transport", "op1", ("timeout_pre",)),
        ("Readback", "op1", ("NOT_APPLIED",)),
        ("ReconcileRefuted", "op1", ()),
    ]
    assert t[-1].state.reserved == 1 and t[-1].state.ops[0].state == REFUTED
    assert (r.distinct_states, r.transitions) == (10959, 38942)
    assert r.violating_state_counts["SafetyEscrowIdentity"] == 8200
    assert check(CONFIGS["BUG_VACUOUS_ESCROW_DRIFT"], NOLATE).violating_state_counts == {"SafetyEscrowIdentity": 1072}


def test_bug_naive_retry_counterexample(results):
    r = results["BUG_NAIVE_RETRY_NO_LATCH"]
    assert set(r.violations) == {"SafetyNoDuplicateEffect", "SafetyNeverReleaseLatchWithoutReadback"}
    t = r.violations["SafetyNoDuplicateEffect"]
    assert _actions(t) == [
        ("AuthorizeAndReserve", "op1", ("1", "clean")),
        ("Transport", "op1", ("timeout_post",)),
        ("NaiveRetry", "op1", ()),
        ("Transport", "op1", ("200",)),
    ]
    assert t[-1].state.ops[0].effects == 2
    assert len(r.violations["SafetyNeverReleaseLatchWithoutReadback"]) == 3
    assert r.violations["SafetyNeverReleaseLatchWithoutReadback"][-1].state.ops[0].release_evidence == NO_READBACK
    assert (r.distinct_states, r.transitions) == (142527, 699704)


def test_bug_retry_on_unknown_counterexample(results):
    r = results["BUG_RETRY_ON_READBACK_UNKNOWN"]
    assert {"SafetyNoDuplicateEffect", "SafetyF7StaysIndeterminate"} <= set(r.violations)
    f7 = r.violations["SafetyF7StaysIndeterminate"]
    assert _actions(f7) == [
        ("AuthorizeAndReserve", "op1", ("1", "clean")),
        ("Transport", "op1", ("timeout_pre",)),
        ("Readback", "op1", ("UNKNOWN",)),
        ("ReconcileRefuted", "op1", ()),
    ]
    dup = r.violations["SafetyNoDuplicateEffect"]
    assert _actions(dup) == [
        ("AuthorizeAndReserve", "op1", ("1", "clean")),
        ("Transport", "op1", ("timeout_post",)),
        ("Readback", "op1", ("UNKNOWN",)),
        ("ReconcileRefuted", "op1", ()),
        ("Redispatch", "op1", ()),
        ("Transport", "op1", ("200",)),
    ]
    assert (r.distinct_states, r.transitions) == (151887, 673288)


def test_bug_full_payload_caid_counterexample(results):
    r = results["BUG_FULL_PAYLOAD_CAID_ON_REGENERATED_RETRY"]
    assert "SafetyNoDuplicateEffect" in r.violations
    t = r.violations["SafetyNoDuplicateEffect"]
    assert _actions(t) == [
        ("AuthorizeAndReserve", "op1", ("1", "clean")),
        ("Transport", "op1", ("200",)),
        ("RegeneratedRetry", "op1", ("fresh_caid_dispatched",)),
    ]
    assert t[1].state.ops[0].state == CONFIRMED and t[-1].state.ops[0].effects == 2
    assert "SafetyEscrowIdentity" not in r.violations and "SafetyBudgetConservation" not in r.violations
    assert (r.distinct_states, r.transitions) == (78575, 289218)


def test_check_all_covers_seven_configs(results):
    assert set(results) == set(CONFIGS) and len(results) == 7
    assert [n for n, r in results.items() if r.all_invariants_hold] == ["A4_DEFAULT_FAIL_CLOSED", "A5_FENCED"]


# ---------------------------------------------------------------------------
# Successor function units
# ---------------------------------------------------------------------------


def test_initial_state_and_authorize_branches():
    init = initial_state(C)
    assert init.reserved == 0 and init.settled == 0 and len(init.ops) == 2
    o = init.ops[0]
    assert (o.state, o.amount, o.effects, o.attempts, o.regenerated) == (IDLE, 0, 0, 0, False)
    assert (o.latch, o.readback, o.release_evidence, o.readback_effects) == ("NONE", "NONE", "NONE", 0)
    succ = successors(init, A4, C)
    assert len(succ) == 8  # 2 ops x 2 amounts x {clean, tier2}
    by = {(op, args): nxt for _a, op, args, nxt in succ}
    ok = by[("op1", ("2", "clean"))]
    assert ok.ops[0].state == DISPATCHED and ok.ops[0].amount == 2 and ok.ops[0].attempts == 1
    assert ok.reserved == 2 and ok.settled == 0
    tainted = by[("op1", ("2", "tier2"))]
    assert tainted.ops[0].state == REJECTED and tainted.reserved == 0 and tainted.ops[0].amount == 0


def test_authorize_rejects_over_budget_and_over_cap():
    s = _st(OpVars(state=DISPATCHED, amount=2, attempts=1), OpVars(), reserved=2)
    by = {args: nxt for a, op, args, nxt in successors(s, A4, C) if a == "AuthorizeAndReserve" and op == "op2"}
    assert by[("1", "clean")].ops[1].state == DISPATCHED and by[("1", "clean")].reserved == 3
    assert by[("2", "clean")].ops[1].state == REJECTED and by[("2", "clean")].reserved == 2
    big = ModelConstants(amounts=(3,), max_per_call_minor=2, sprint_limit_minor=9)
    succ = successors(initial_state(big), A4, big)
    assert succ and all(nxt.ops[0].state == REJECTED or nxt.ops[1].state == REJECTED for *_x, nxt in succ)
    zero = ModelConstants(amounts=(0,))
    assert all(REJECTED in (n.ops[0].state, n.ops[1].state) for *_x, n in successors(initial_state(zero), A4, zero))


def test_transport_outcomes():
    s = _st(OpVars(state=DISPATCHED, amount=2, attempts=1), OpVars(), reserved=2)
    by = {args[0]: nxt for a, op, args, nxt in successors(s, A4, C) if a == "Transport"}
    assert set(by) == {"200", "timeout_pre", "timeout_post", "http500_post", "timeout_late"}
    late = by["timeout_late"]
    assert late.ops[0].state == INDETERMINATE and late.ops[0].effects == 0 and late.ops[0].inflight == 1
    assert late.ops[0].latch == LATCHED and late.reserved == 2
    assert {args[0] for a, op, args, n in successors(s, A4, NOLATE) if a == "Transport"} == {"200", "timeout_pre", "timeout_post", "http500_post"}
    ok = by["200"]
    assert ok.ops[0].state == CONFIRMED and ok.ops[0].effects == 1 and ok.reserved == 0 and ok.settled == 2
    assert ok.ops[0].latch == "NONE"
    pre = by["timeout_pre"]
    assert pre.ops[0].state == INDETERMINATE and pre.ops[0].effects == 0 and pre.ops[0].latch == LATCHED
    assert pre.reserved == 2 and pre.settled == 0
    for f in ("timeout_post", "http500_post"):
        assert by[f].ops[0].effects == 1 and by[f].ops[0].state == INDETERMINATE and by[f].reserved == 2


def test_readback_is_truthful_and_single_shot():
    applied = _st(OpVars(state=INDETERMINATE, amount=1, effects=1, latch=LATCHED, attempts=1), OpVars(), reserved=1)
    rb = {args[0]: n for a, _o, args, n in successors(applied, A4, C) if a == "Readback"}
    assert set(rb) == {APPLIED, UNKNOWN} and rb[APPLIED].ops[0].readback_effects == 1
    absent = applied._replace(ops=(applied.ops[0]._replace(effects=0), applied.ops[1]))
    rb2 = {args[0]: n for a, _o, args, n in successors(absent, A4, C) if a == "Readback"}
    assert set(rb2) == {NOT_APPLIED, UNKNOWN}
    answered = applied._replace(ops=(applied.ops[0]._replace(readback=UNKNOWN, readback_effects=1), applied.ops[1]))
    acts = {a for a, op, _args, _n in successors(answered, A4, C) if op == "op1"}
    assert "Readback" not in acts and "ReconcileRefuted" not in acts and "ReconcileConfirmed" not in acts
    unlatched = applied._replace(ops=(applied.ops[0]._replace(latch="NONE"), applied.ops[1]))
    assert not [a for a, op, *_r in successors(unlatched, A4, C) if a == "Readback" and op == "op1"]


def test_reconcile_and_redispatch_transitions():
    base = OpVars(state=INDETERMINATE, amount=2, effects=1, latch=LATCHED, readback=APPLIED,
                  readback_effects=1, attempts=1)
    s = _st(base, OpVars(), reserved=2)
    conf = [n for a, op, _x, n in successors(s, A4, C) if a == "ReconcileConfirmed" and op == "op1"][0]
    assert conf.ops[0].state == CONFIRMED and conf.ops[0].latch == RELEASED
    assert conf.ops[0].release_evidence == APPLIED and conf.reserved == 0 and conf.settled == 2

    na = _st(base._replace(effects=0, readback=NOT_APPLIED, readback_effects=0), OpVars(), reserved=2)
    ref = [n for a, op, _x, n in successors(na, A4, C) if a == "ReconcileRefuted" and op == "op1"][0]
    assert ref.ops[0].state == REFUTED and ref.reserved == 0 and ref.ops[0].release_evidence == NOT_APPLIED
    drift = [n for a, op, _x, n in successors(na, CONFIGS["BUG_VACUOUS_ESCROW_DRIFT"], C)
             if a == "ReconcileRefuted"][0]
    assert drift.reserved == 2

    red = [n for a, op, _x, n in successors(ref, A4, C) if a == "Redispatch" and op == "op1"][0]
    o = red.ops[0]
    assert (o.state, o.attempts, o.latch, o.readback, o.readback_effects) == (DISPATCHED, 2, "NONE", "NONE", 0)
    assert red.reserved == 2 and o.release_evidence == NOT_APPLIED
    assert not [a for a, *_r in successors(red._replace(ops=(o._replace(state=REFUTED), red.ops[1]), reserved=0),
                                           A4, C) if a == "Redispatch"]
    tight = ref._replace(settled=2)
    assert not [a for a, *_r in successors(tight, A4, C) if a == "Redispatch"]
    fits = ref._replace(settled=1)
    assert [a for a, *_r in successors(fits, A4, C) if a == "Redispatch"]


def test_naive_retry_and_regenerated_modes():
    s = _st(OpVars(state=INDETERMINATE, amount=1, effects=1, latch=LATCHED, attempts=1), OpVars(), reserved=1)
    assert not [a for a, *_r in successors(s, A4, C) if a == "NaiveRetry"]
    naive = [n for a, *_r, n in successors(s, CONFIGS["BUG_NAIVE_RETRY_NO_LATCH"], C) if a == "NaiveRetry"][0]
    o = naive.ops[0]
    assert (o.state, o.attempts, o.latch, o.release_evidence) == (DISPATCHED, 2, "NONE", NO_READBACK)
    assert naive.reserved == 1
    maxed = s._replace(ops=(s.ops[0]._replace(attempts=2), s.ops[1]))
    assert not [a for a, *_r in successors(maxed, CONFIGS["BUG_NAIVE_RETRY_NO_LATCH"], C) if a == "NaiveRetry"]

    conf = _st(OpVars(state=CONFIRMED, amount=1, effects=1, attempts=1), OpVars(), settled=1)
    refused = [n for a, *_r, n in successors(conf, A4, C) if a == "RegeneratedRetry"][0]
    assert refused.ops[0].regenerated is True and refused.ops[0].effects == 1
    fresh = [n for a, *_r, n in successors(conf, CONFIGS["BUG_FULL_PAYLOAD_CAID_ON_REGENERATED_RETRY"], C)
             if a == "RegeneratedRetry"][0]
    assert fresh.ops[0].effects == 2 and fresh.settled == 1
    assert not [a for a, *_r in successors(refused, A4, C) if a == "RegeneratedRetry"]
    for st in (IDLE, DISPATCHED, REFUTED, REJECTED):
        other = _st(OpVars(state=st, amount=1), OpVars(state=REJECTED), reserved=1 if st == DISPATCHED else 0)
        assert not [a for a, *_r in successors(other, A4, C) if a == "RegeneratedRetry"]


def test_terminal_state_has_no_successors():
    done = _st(OpVars(state=CONFIRMED, amount=1, effects=1, attempts=1, regenerated=True),
               OpVars(state=REJECTED), settled=1)
    assert successors(done, A4, C) == []


# ---------------------------------------------------------------------------
# Invariant units (each must be falsifiable)
# ---------------------------------------------------------------------------


def test_budget_invariant():
    inv = INVARIANTS["SafetyBudgetConservation"]
    assert inv(_st(OpVars(), OpVars(), reserved=2, settled=1), C) is True
    assert inv(_st(OpVars(), OpVars(), reserved=2, settled=2), C) is False


def test_escrow_identity_invariant():
    inv = INVARIANTS["SafetyEscrowIdentity"]
    good = _st(OpVars(state=INDETERMINATE, amount=2), OpVars(state=CONFIRMED, amount=1), reserved=2, settled=1)
    assert inv(good, C) is True
    assert inv(_st(OpVars(state=DISPATCHED, amount=1), OpVars(state=REFUTED, amount=2), reserved=1), C) is True
    assert inv(good._replace(reserved=1), C) is False
    assert inv(good._replace(settled=2), C) is False
    assert inv(_st(OpVars(state=REFUTED, amount=2), OpVars(), reserved=2), C) is False


def test_no_duplicate_invariant():
    inv = INVARIANTS["SafetyNoDuplicateEffect"]
    assert inv(_st(OpVars(effects=1), OpVars(effects=0)), C) is True
    assert inv(_st(OpVars(effects=1), OpVars(effects=2)), C) is False


def test_never_release_without_readback_invariant():
    inv = INVARIANTS["SafetyNeverReleaseLatchWithoutReadback"]
    assert inv(_st(OpVars(state=REFUTED, release_evidence=NOT_APPLIED), OpVars(state=CONFIRMED, release_evidence=APPLIED)), C) is True
    assert inv(_st(OpVars(state=REFUTED, release_evidence=APPLIED), OpVars()), C) is False
    assert inv(_st(OpVars(state=REFUTED), OpVars()), C) is False
    assert inv(_st(OpVars(), OpVars(state=DISPATCHED, release_evidence=NO_READBACK)), C) is False
    assert inv(_st(OpVars(state=CONFIRMED, release_evidence=UNKNOWN), OpVars()), C) is False


def test_f7_invariant():
    inv = INVARIANTS["SafetyF7StaysIndeterminate"]
    ok = OpVars(state=INDETERMINATE, latch=LATCHED, readback=UNKNOWN, effects=1, readback_effects=1)
    assert inv(_st(ok, OpVars()), C) is True
    assert inv(_st(ok._replace(state=REFUTED), OpVars()), C) is False
    assert inv(_st(ok._replace(latch=RELEASED), OpVars()), C) is False
    assert inv(_st(ok._replace(effects=2), OpVars()), C) is False
    assert inv(_st(OpVars(state=CONFIRMED, readback=APPLIED), ok), C) is True
    assert inv(_st(OpVars(), ok._replace(state=CONFIRMED)), C) is False
    # A late commit of a write that was in flight at read-back time stays within the bound.
    assert inv(_st(ok._replace(effects=0), OpVars()), C) is True
    assert inv(_st(ok._replace(effects=1, readback_effects=0), OpVars()), C) is False


# ---------------------------------------------------------------------------
# Bounds, constants, formatting, CLI
# ---------------------------------------------------------------------------


def test_max_states_bound_raises():
    with pytest.raises(RuntimeError):
        check(A4, max_states=10)
    assert check(A4, NOLATE, max_states=5175).distinct_states == 5175
    with pytest.raises(RuntimeError):
        check(A4, NOLATE, max_states=5174)


def test_constants_change_state_space():
    small = check(A5, ModelConstants(sprint_limit_minor=2))
    assert small.all_invariants_hold and small.distinct_states < 34047
    one_attempt = check(A4, ModelConstants(max_attempts=1))
    assert one_attempt.all_invariants_hold and one_attempt.distinct_states < 48927
    single = check(A5, ModelConstants(operations=("op1",)))
    assert single.all_invariants_hold and single.distinct_states < one_attempt.distinct_states
    assert single.max_depth < 18 and single.terminal_states >= 1


def test_custom_config_defaults():
    cfg = ProtocolConfig("custom")
    assert cfg == dataclasses.replace(A4, name="custom")
    assert cfg.caid_mode == "EFFECT_KEY"
    assert (cfg.naive_retry_without_readback, cfg.unknown_as_not_applied, cfg.escrow_drift_on_refute) == (False, False, False)
    assert check(cfg, NOLATE).distinct_states == 5175
    assert (cfg.settle_not_applied, cfg.fence_on_not_applied) == (True, False)


def test_format_trace_and_main(results, capsys):
    t = results["BUG_FULL_PAYLOAD_CAID_ON_REGENERATED_RETRY"].violations["SafetyNoDuplicateEffect"]
    assert format_trace(t) == ("AuthorizeAndReserve(op1, 1, clean) -> Transport(op1, 200) -> "
                               "RegeneratedRetry(op1, fresh_caid_dispatched)")
    refute = results["BUG_VACUOUS_ESCROW_DRIFT"].violations["SafetyEscrowIdentity"]
    assert format_trace(refute).endswith("-> ReconcileRefuted(op1)")
    assert format_trace([]) == ""
    assert main() == 0
    out = capsys.readouterr().out
    assert "A5_FENCED: states=34047 transitions=116952 max_depth=20 terminal=1285 violations=[]" in out
    assert "SafetyEscrowIdentity (len 4, violating states 8200)" in out
    assert "SafetyNoDuplicateEffect (len 7, violating states 7400)" in out


# ---------------------------------------------------------------------------
# TLA+ module
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not TLA_PATH.exists(), reason="formal/ is not copied into the mutation-gate shadow root")
def test_tla_module_has_fold_sum_and_named_invariants():
    text = TLA_PATH.read_text(encoding="utf-8")
    assert "CHOOSE s \\in Nat : TRUE" not in text
    assert "RECURSIVE SumAmounts(_)" in text
    assert "opAmount[x] + SumAmounts(S \\ {x})" in text
    for name in INVARIANTS:
        assert f"{name} ==" in text
    for var in ("targetEffects", "latchState", "readbackResult"):
        assert var in text
    assert "checked with TLC" in text and "scripts/run_tlc_formal_gate.sh" in text
    for cfg_name in ("AEIBStation1And2_A5.cfg", "AEIBStation1And2_A4.cfg"):
        assert (TLA_PATH.parent / cfg_name).is_file()
    for action in ("LateCommit(op) ==", "InflightEnds(op) ==", "FenceAndRefute(op) ==", "FenceObservesApplied(op) =="):
        assert action in text
    for var in ("inflight", "fenceBelow", "FencingEnabled      \\* TRUE = A5", '"timeout_late"'):
        assert var in text
    assert "FencingEnabled == TRUE" not in text, "FencingEnabled must be a model constant, not a fixed definition"


# ---------------------------------------------------------------------------
# Late-commit and fencing transition units
# ---------------------------------------------------------------------------


def _inflight_state(**kw):
    base = dict(state=INDETERMINATE, amount=1, latch=LATCHED, attempts=1, inflight=1)
    base.update(kw)
    return _st(OpVars(**base), OpVars(), reserved=1)


def test_late_commit_and_inflight_end_transitions():
    s = _inflight_state()
    by = {(a, args): n for a, op, args, n in successors(s, A4, C) if op == "op1" and a in ("LateCommit", "InflightEnds")}
    assert set(by) == {("LateCommit", ("1",)), ("InflightEnds", ("expired",))}
    assert by[("LateCommit", ("1",))].ops[0].effects == 1 and by[("LateCommit", ("1",))].ops[0].inflight == 0
    assert by[("InflightEnds", ("expired",))].ops[0].effects == 0 and by[("InflightEnds", ("expired",))].ops[0].inflight == 0
    fenced = _inflight_state(state=REFUTED, latch=RELEASED, fence_below=2)
    acts = {(a, args) for a, op, args, _n in successors(fenced, A5, C) if op == "op1" and a in ("LateCommit", "InflightEnds")}
    assert acts == {("InflightEnds", ("fenced",))}
    same = _inflight_state(inflight=2, attempts=2, fence_below=2)
    assert ("LateCommit", ("2",)) in {(a, args) for a, op, args, _n in successors(same, A5, C) if op == "op1"}
    assert not [a for a, *_r in successors(_inflight_state(inflight=0), A4, C) if a in ("LateCommit", "InflightEnds")]


def test_readback_records_inflight_potential():
    s = _inflight_state()
    rb = {args[0]: n for a, op, args, n in successors(s, A4, C) if a == "Readback" and op == "op1"}
    assert set(rb) == {NOT_APPLIED, UNKNOWN}
    assert rb[NOT_APPLIED].ops[0].readback_effects == 1
    plain = _inflight_state(inflight=0)
    rb2 = {args[0]: n for a, op, args, n in successors(plain, A4, C) if a == "Readback" and op == "op1"}
    assert rb2[UNKNOWN].ops[0].readback_effects == 0


def test_refute_modes_per_config():
    s = _inflight_state(readback=NOT_APPLIED, readback_effects=1)
    a4 = {a for a, op, *_r in successors(s, A4, C) if op == "op1"}
    assert "ReconcileRefuted" in a4 and "FenceAndRefute" not in a4
    a4d = {a for a, op, *_r in successors(s, A4D, C) if op == "op1"}
    assert not ({"ReconcileRefuted", "FenceAndRefute", "FenceObservesApplied"} & a4d)
    fence = {a: n for a, op, _args, n in successors(s, A5, C) if op == "op1"}
    assert "ReconcileRefuted" not in fence and "FenceObservesApplied" not in fence
    r = fence["FenceAndRefute"]
    o = r.ops[0]
    assert (o.state, o.latch, o.release_evidence, o.fence_below, o.inflight) == (REFUTED, RELEASED, NOT_APPLIED, 2, 1)
    assert r.reserved == 0 and r.settled == 0
    landed = _inflight_state(readback=NOT_APPLIED, readback_effects=1, effects=1, inflight=0)
    fence2 = {a: n for a, op, _args, n in successors(landed, A5, C) if op == "op1"}
    assert "FenceAndRefute" not in fence2
    c = fence2["FenceObservesApplied"]
    assert (c.ops[0].state, c.ops[0].release_evidence, c.ops[0].fence_below) == (CONFIRMED, APPLIED, 2)
    assert c.reserved == 0 and c.settled == 1
    unknown = _inflight_state(readback=UNKNOWN, readback_effects=1)
    assert not [a for a, *_r in successors(unknown, A5, C) if a in ("FenceAndRefute", "FenceObservesApplied")]


def test_opvars_late_defaults():
    o = OpVars()
    assert (o.inflight, o.fence_below) == (0, 0)
    assert C.late_commit is True and NOLATE.late_commit is False
