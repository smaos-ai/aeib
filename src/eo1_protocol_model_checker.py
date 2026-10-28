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
src/eo1_protocol_model_checker.py
================================================================================
Exhaustive finite-state BFS model checker (stdlib only) for the Station 1 & 2 budget /
escrow / EO1 settle-before-retry protocol described in formal/tlaplus/AEIBStation1And2.tla.

Status: prototype. ``tla2tools.jar`` is not installed on the evaluation host and network
downloads are not permitted, so TLC was NOT run. This module re-implements the TLA+ actions
as a Python successor function and explores every reachable state by breadth-first search
over immutable tuples, under the declared finite constants. Results hold for the stated
model and bounds only; they are not a proof about the Python/Rust implementation.

Model (per operation ``op``; constants from ``ModelConstants``):
  opState         IDLE | DISPATCHED | INDETERMINATE | CONFIRMED | REFUTED | REJECTED
  opAmount        0 or the authorised amount
  targetEffects   number of effects applied at the target for the op's logical effect
  latchState      NONE | LATCHED | RELEASED
  readbackResult  NONE | APPLIED | NOT_APPLIED | UNKNOWN (UNKNOWN = read-back timeout, F7;
                  sticky: the read-back stays unavailable for that attempt)
  readbackEffects ghost: targetEffects observed when the read-back answered
  releaseEvidence ghost: evidence that released the latch
                  NONE | APPLIED | NOT_APPLIED | UNKNOWN | NO_READBACK
  attempts        dispatch attempts so far (bounded by max_attempts)
  regenerated     whether a regenerated retry (changed memo / UUID) was issued
Globals: reservedMinor, settledMinor.

Actions: AuthorizeAndReserve(op, amt, taint), Transport(op, fault) with fault in
{200, timeout_pre, timeout_post, http500_post}, Readback(op, r) (truthful: APPLIED or UNKNOWN
when an effect exists, NOT_APPLIED or UNKNOWN otherwise), ReconcileConfirmed(op),
ReconcileRefuted(op), Redispatch(op) (one fresh attempt after REFUTED), NaiveRetry(op)
(ablation only), RegeneratedRetry(op).

CAID modes for a regenerated retry:
  EFFECT_KEY    the CAID is derived from the effect key, so the regenerated request maps onto
                the same latched / committed record and is refused.
  FULL_PAYLOAD  the CAID covers incidental fields, so the regenerated request receives a fresh
                CAID, passes every EO1 gate and is delivered (abstraction: one delivery that
                applies, outside the escrow ledger).

Not modelled: late commits after a NOT_APPLIED read-back (LIMBO ``timeout_late``), lying
read-backs, transport redelivery, concurrency between processes.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Callable, Dict, List, NamedTuple, Optional, Tuple

IDLE = "IDLE"
DISPATCHED = "DISPATCHED"
INDETERMINATE = "INDETERMINATE"
CONFIRMED = "CONFIRMED"
REFUTED = "REFUTED"
REJECTED = "REJECTED"

LATCH_NONE = "NONE"
LATCHED = "LATCHED"
RELEASED = "RELEASED"

RB_NONE = "NONE"
APPLIED = "APPLIED"
NOT_APPLIED = "NOT_APPLIED"
UNKNOWN = "UNKNOWN"
NO_READBACK = "NO_READBACK"

WIRE_FAULTS = ("200", "timeout_pre", "timeout_post", "http500_post")
LATE_FAULT = "timeout_late"  # LIMBO timeout_late: write still in flight, may commit after read-back
APPLYING_FAULTS = frozenset({"200", "timeout_post", "http500_post"})

CAID_EFFECT_KEY = "EFFECT_KEY"
CAID_FULL_PAYLOAD = "FULL_PAYLOAD"


@dataclass(frozen=True)
class ModelConstants:
    operations: Tuple[str, ...] = ("op1", "op2")
    amounts: Tuple[int, ...] = (1, 2)
    max_per_call_minor: int = 2
    sprint_limit_minor: int = 3
    max_attempts: int = 2
    late_commit: bool = True


@dataclass(frozen=True)
class ProtocolConfig:
    name: str
    caid_mode: str = CAID_EFFECT_KEY
    naive_retry_without_readback: bool = False
    unknown_as_not_applied: bool = False
    escrow_drift_on_refute: bool = False
    settle_not_applied: bool = True  # False: default fail-closed reconciler (NOT_APPLIED stays latched)
    fence_on_not_applied: bool = False  # True: NOT_APPLIED settles only through an attempt fence


CONFIGS: Dict[str, ProtocolConfig] = {
    "A4_EFFECT_KEY_AND_RECONCILER": ProtocolConfig("A4_EFFECT_KEY_AND_RECONCILER"),
    "A4_DEFAULT_FAIL_CLOSED": ProtocolConfig("A4_DEFAULT_FAIL_CLOSED", settle_not_applied=False),
    "A5_FENCED": ProtocolConfig("A5_FENCED", fence_on_not_applied=True),
    "BUG_VACUOUS_ESCROW_DRIFT": ProtocolConfig("BUG_VACUOUS_ESCROW_DRIFT", escrow_drift_on_refute=True),
    "BUG_NAIVE_RETRY_NO_LATCH": ProtocolConfig("BUG_NAIVE_RETRY_NO_LATCH", naive_retry_without_readback=True),
    "BUG_RETRY_ON_READBACK_UNKNOWN": ProtocolConfig("BUG_RETRY_ON_READBACK_UNKNOWN", unknown_as_not_applied=True),
    "BUG_FULL_PAYLOAD_CAID_ON_REGENERATED_RETRY": ProtocolConfig(
        "BUG_FULL_PAYLOAD_CAID_ON_REGENERATED_RETRY", caid_mode=CAID_FULL_PAYLOAD),
}


class OpVars(NamedTuple):
    state: str = IDLE
    amount: int = 0
    effects: int = 0
    latch: str = LATCH_NONE
    readback: str = RB_NONE
    readback_effects: int = 0
    release_evidence: str = RB_NONE
    attempts: int = 0
    regenerated: bool = False
    inflight: int = 0  # attempt number of a write still in flight at the target (0 = none)
    fence_below: int = 0  # target refuses in-flight writes whose attempt < fence_below


class ModelState(NamedTuple):
    ops: Tuple[OpVars, ...]
    reserved: int
    settled: int


@dataclass(frozen=True)
class Step:
    action: str
    op: str
    args: Tuple[str, ...]
    state: ModelState


@dataclass
class CheckResult:
    config: str
    constants: ModelConstants
    distinct_states: int
    transitions: int
    max_depth: int
    terminal_states: int
    violations: Dict[str, List[Step]]
    violating_state_counts: Dict[str, int]

    @property
    def all_invariants_hold(self) -> bool:
        return not self.violations


def initial_state(constants: ModelConstants) -> ModelState:
    return ModelState(tuple(OpVars() for _ in constants.operations), 0, 0)


def _replace(state: ModelState, idx: int, op: OpVars, reserved: int, settled: int) -> ModelState:
    ops = list(state.ops)
    ops[idx] = op
    return ModelState(tuple(ops), reserved, settled)


def successors(
    state: ModelState, cfg: ProtocolConfig, constants: ModelConstants
) -> List[Tuple[str, str, Tuple[str, ...], ModelState]]:
    """All enabled (action, op, args, next_state) transitions from ``state``."""
    out: List[Tuple[str, str, Tuple[str, ...], ModelState]] = []
    res, setl = state.reserved, state.settled
    for i, name in enumerate(constants.operations):
        o = state.ops[i]

        if o.state == IDLE:
            for amt in constants.amounts:
                for taint in (False, True):
                    admit = (
                        not taint
                        and amt > 0
                        and amt <= constants.max_per_call_minor
                        and res + setl + amt <= constants.sprint_limit_minor
                    )
                    if admit:
                        nxt = _replace(state, i, o._replace(state=DISPATCHED, amount=amt, attempts=1), res + amt, setl)
                    else:
                        nxt = _replace(state, i, o._replace(state=REJECTED), res, setl)
                    out.append(("AuthorizeAndReserve", name, (str(amt), "tier2" if taint else "clean"), nxt))

        if o.state == DISPATCHED:
            faults = WIRE_FAULTS + ((LATE_FAULT,) if constants.late_commit else ())
            for fault in faults:
                effects = o.effects + 1 if fault in APPLYING_FAULTS else o.effects
                if fault == "200":
                    nxt = _replace(state, i, o._replace(state=CONFIRMED, effects=effects),
                                   res - o.amount, setl + o.amount)
                elif fault == LATE_FAULT:
                    nxt = _replace(state, i, o._replace(state=INDETERMINATE, latch=LATCHED, inflight=o.attempts),
                                   res, setl)
                else:
                    nxt = _replace(state, i, o._replace(state=INDETERMINATE, effects=effects, latch=LATCHED), res, setl)
                out.append(("Transport", name, (fault,), nxt))

        if o.inflight > 0:
            if o.inflight >= o.fence_below:
                nxt = _replace(state, i, o._replace(effects=o.effects + 1, inflight=0), res, setl)
                out.append(("LateCommit", name, (str(o.inflight),), nxt))
            nxt = _replace(state, i, o._replace(inflight=0), res, setl)
            out.append(("InflightEnds", name, ("fenced" if o.inflight < o.fence_below else "expired",), nxt))

        if o.state == INDETERMINATE and o.latch == LATCHED and o.readback == RB_NONE:
            # Read-back sees committed effects only; a write still in flight reads as absent.
            answers = (APPLIED, UNKNOWN) if o.effects >= 1 else (NOT_APPLIED, UNKNOWN)
            potential = o.effects + (1 if o.inflight > 0 else 0)
            for r in answers:
                nxt = _replace(state, i, o._replace(readback=r, readback_effects=potential), res, setl)
                out.append(("Readback", name, (r,), nxt))

        if o.state == INDETERMINATE and o.readback == APPLIED:
            nxt = _replace(state, i, o._replace(state=CONFIRMED, latch=RELEASED, release_evidence=APPLIED),
                           res - o.amount, setl + o.amount)
            out.append(("ReconcileConfirmed", name, (), nxt))

        refutable = o.readback == NOT_APPLIED or (cfg.unknown_as_not_applied and o.readback == UNKNOWN)
        if o.state == INDETERMINATE and refutable and cfg.settle_not_applied and not cfg.fence_on_not_applied:
            new_res = res if cfg.escrow_drift_on_refute else res - o.amount
            nxt = _replace(state, i, o._replace(state=REFUTED, latch=RELEASED, release_evidence=o.readback),
                           new_res, setl)
            out.append(("ReconcileRefuted", name, (), nxt))

        if o.state == INDETERMINATE and o.readback == NOT_APPLIED and cfg.fence_on_not_applied:
            # Atomic target-side check-and-fence: refuse in-flight attempts <= current attempt.
            if o.effects == 0:
                nxt = _replace(state, i, o._replace(state=REFUTED, latch=RELEASED, release_evidence=NOT_APPLIED,
                                                    fence_below=o.attempts + 1), res - o.amount, setl)
                out.append(("FenceAndRefute", name, (str(o.attempts + 1),), nxt))
            else:
                nxt = _replace(state, i, o._replace(state=CONFIRMED, latch=RELEASED, release_evidence=APPLIED,
                                                    fence_below=o.attempts + 1), res - o.amount, setl + o.amount)
                out.append(("FenceObservesApplied", name, (str(o.attempts + 1),), nxt))

        if (
            o.state == REFUTED
            and o.attempts < constants.max_attempts
            and res + setl + o.amount <= constants.sprint_limit_minor
        ):
            nxt = _replace(state, i, o._replace(state=DISPATCHED, attempts=o.attempts + 1, latch=LATCH_NONE,
                                                readback=RB_NONE, readback_effects=0), res + o.amount, setl)
            out.append(("Redispatch", name, (), nxt))

        if cfg.naive_retry_without_readback and o.state == INDETERMINATE and o.attempts < constants.max_attempts:
            nxt = _replace(state, i, o._replace(state=DISPATCHED, attempts=o.attempts + 1, latch=LATCH_NONE,
                                                readback=RB_NONE, release_evidence=NO_READBACK), res, setl)
            out.append(("NaiveRetry", name, (), nxt))

        if o.state in (CONFIRMED, INDETERMINATE) and not o.regenerated:
            if cfg.caid_mode == CAID_FULL_PAYLOAD:
                nxt = _replace(state, i, o._replace(regenerated=True, effects=o.effects + 1), res, setl)
                out.append(("RegeneratedRetry", name, ("fresh_caid_dispatched",), nxt))
            else:
                nxt = _replace(state, i, o._replace(regenerated=True), res, setl)
                out.append(("RegeneratedRetry", name, ("same_effect_key_refused",), nxt))
    return out


# ---------------------------------------------------------------------------
# Invariants
# ---------------------------------------------------------------------------


def safety_budget_conservation(s: ModelState, c: ModelConstants) -> bool:
    return s.reserved + s.settled <= c.sprint_limit_minor


def safety_escrow_identity(s: ModelState, c: ModelConstants) -> bool:
    active = sum(o.amount for o in s.ops if o.state in (DISPATCHED, INDETERMINATE))
    confirmed = sum(o.amount for o in s.ops if o.state == CONFIRMED)
    return s.reserved == active and s.settled == confirmed


def safety_no_duplicate_effect(s: ModelState, c: ModelConstants) -> bool:
    return all(o.effects <= 1 for o in s.ops)


def safety_never_release_latch_without_readback(s: ModelState, c: ModelConstants) -> bool:
    for o in s.ops:
        if o.release_evidence not in (RB_NONE, APPLIED, NOT_APPLIED):
            return False
        if o.state == REFUTED and o.release_evidence != NOT_APPLIED:
            return False
    return True


def safety_f7_stays_indeterminate(s: ModelState, c: ModelConstants) -> bool:
    """UNKNOWN read-back: stays latched INDETERMINATE and effects never exceed what was committed
    or in flight when the read-back timed out (no new attempt adds an effect)."""
    for o in s.ops:
        if o.readback == UNKNOWN and not (
            o.state == INDETERMINATE and o.latch == LATCHED and o.effects <= o.readback_effects
        ):
            return False
    return True


INVARIANTS: Dict[str, Callable[[ModelState, ModelConstants], bool]] = {
    "SafetyBudgetConservation": safety_budget_conservation,
    "SafetyEscrowIdentity": safety_escrow_identity,
    "SafetyNoDuplicateEffect": safety_no_duplicate_effect,
    "SafetyNeverReleaseLatchWithoutReadback": safety_never_release_latch_without_readback,
    "SafetyF7StaysIndeterminate": safety_f7_stays_indeterminate,
}


# ---------------------------------------------------------------------------
# Exhaustive BFS
# ---------------------------------------------------------------------------


def _trace(parents: Dict[ModelState, Optional[Tuple[ModelState, str, str, Tuple[str, ...]]]],
           end: ModelState) -> List[Step]:
    steps: List[Step] = []
    cur = end
    while parents[cur] is not None:
        prev, action, op, args = parents[cur]
        steps.append(Step(action, op, args, cur))
        cur = prev
    steps.reverse()
    return steps


def check(cfg: ProtocolConfig, constants: Optional[ModelConstants] = None,
          max_states: Optional[int] = None) -> CheckResult:
    """
    Breadth-first exploration of every reachable state. Because BFS visits states in order of
    depth, the first violating state found for an invariant yields a shortest counterexample.
    ``max_states`` (optional) aborts with RuntimeError if the model is larger than expected.
    """
    constants = constants or ModelConstants()
    init = initial_state(constants)
    parents: Dict[ModelState, Optional[Tuple[ModelState, str, str, Tuple[str, ...]]]] = {init: None}
    depth: Dict[ModelState, int] = {init: 0}
    violations: Dict[str, List[Step]] = {}
    violating_counts: Dict[str, int] = {}
    transitions = 0
    terminal = 0
    queue = deque([init])
    while queue:
        s = queue.popleft()
        for inv_name, inv in INVARIANTS.items():
            if not inv(s, constants):
                violating_counts[inv_name] = violating_counts.get(inv_name, 0) + 1
                if inv_name not in violations:
                    violations[inv_name] = _trace(parents, s)
        nexts = successors(s, cfg, constants)
        if not nexts:
            terminal += 1
        for action, op, args, nxt in nexts:
            transitions += 1
            if nxt not in parents:
                if max_states is not None and len(parents) >= max_states:
                    raise RuntimeError(f"state bound {max_states} exceeded; model is larger than declared")
                parents[nxt] = (s, action, op, args)
                depth[nxt] = depth[s] + 1
                queue.append(nxt)
    return CheckResult(
        config=cfg.name,
        constants=constants,
        distinct_states=len(parents),
        transitions=transitions,
        max_depth=max(depth.values()),
        terminal_states=terminal,
        violations=violations,
        violating_state_counts=violating_counts,
    )


def check_all(constants: Optional[ModelConstants] = None) -> Dict[str, CheckResult]:
    return {name: check(cfg, constants) for name, cfg in CONFIGS.items()}


def format_trace(trace: List[Step]) -> str:
    return " -> ".join(f"{s.action}({s.op}{', ' if s.args else ''}{', '.join(s.args)})" for s in trace)


def main() -> int:
    for name, res in check_all().items():
        print(f"{name}: states={res.distinct_states} transitions={res.transitions} "
              f"max_depth={res.max_depth} terminal={res.terminal_states} "
              f"violations={sorted(res.violations)}")
        for inv, trace in sorted(res.violations.items()):
            print(f"  {inv} (len {len(trace)}, violating states {res.violating_state_counts[inv]}): "
                  f"{format_trace(trace)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
