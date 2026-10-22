#!/usr/bin/env python3
# File: tests/test_limbo_proposition_1_fence.py
"""
Verification Harness for Limbo Proposition 1 Visibility-Lag Fence (`arXiv:2609.29095`)
and Fudan / Moonshot PARL Concurrency Governance (`arXiv:2610.10263`).

Evaluates under the stated model:
1. Limbo Proposition 1 (`arXiv:2609.29095`):
   When an external target has commit delay `delta_ms` and NoSQL read-replica
   visibility lag `lambda_ms`, any unguarded read-back retry launched at
   `t < t_dispatch + delta_ms + lambda_ms` observes stale state (`NOT_FOUND`)
   and triggers a duplicate write (56%-74% duplication rate in Limbo).
   Station 2's `VisibilityLagFenceInterlock` mathematically blocks retries and
   premature read-back probes until `t >= t_dispatch + delta_ms + lambda_ms`.
2. Fudan Concurrency (`arXiv:2610.10263`) & Moonshot PARL Critical Steps:
   Detects and halts *Spurious Parallelism* when parallel subagent fan-out
   inflates token spend above critical-step efficiency bounds.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class SimulatedReplicaTarget:
    """
    Simulates an external settlement API backed by an asynchronous primary write
    (`delta_ms`) and a lagging read replica (`lambda_ms`).
    """

    delta_ms: int
    lambda_ms: int
    commits_by_op: Dict[str, List[int]]

    def __init__(self, delta_ms: int = 120, lambda_ms: int = 250) -> None:
        self.delta_ms = delta_ms
        self.lambda_ms = lambda_ms
        self.commits_by_op = {}

    def submit_write(self, operation_id: str, dispatch_time_ms: int) -> str:
        self.commits_by_op.setdefault(operation_id, []).append(dispatch_time_ms)
        return "HTTP_504_GATEWAY_TIMEOUT"

    def query_read_replica(self, operation_id: str, query_time_ms: int) -> str:
        commits = self.commits_by_op.get(operation_id, [])
        for t_disp in commits:
            # Effect only becomes visible on the read replica at t_disp + delta + lambda
            if query_time_ms >= t_disp + self.delta_ms + self.lambda_ms:
                return "SETTLED_VISIBLE"
        return "NOT_FOUND_ON_REPLICA"


class VisibilityLagFenceInterlock:
    """
    Station 2 Visibility-Lag Fence (`arXiv:2609.29095`, Proposition 1 Countermeasure):
    - On HTTP 504 / timeout at `t_dispatch`, latches `EFFECT_INDETERMINATE` and computes
      `visibility_horizon_ms = t_dispatch + delta_ms + lambda_ms + safety_margin_ms`.
    - Rejects any blind retry or premature read-replica negative conclusion before
      `current_time_ms >= visibility_horizon_ms`.
    """

    def __init__(self, delta_ms: int, lambda_ms: int, safety_margin_ms: int = 10) -> None:
        self.delta_ms = delta_ms
        self.lambda_ms = lambda_ms
        self.safety_margin_ms = safety_margin_ms
        self.latched_ops: Dict[str, Dict[str, int | str]] = {}

    def record_indeterminate_timeout(self, operation_id: str, dispatch_time_ms: int) -> int:
        horizon = dispatch_time_ms + self.delta_ms + self.lambda_ms + self.safety_margin_ms
        self.latched_ops[operation_id] = {
            "disposition": "EFFECT_INDETERMINATE",
            "t_dispatch_ms": dispatch_time_ms,
            "visibility_horizon_ms": horizon,
        }
        return horizon

    def evaluate_retry_or_reconcile(
        self,
        operation_id: str,
        current_time_ms: int,
        target: SimulatedReplicaTarget,
    ) -> Tuple[str, str]:
        entry = self.latched_ops.get(operation_id)
        if entry is None:
            return "DISPATCHED", "OK"

        horizon = int(entry["visibility_horizon_ms"])
        if current_time_ms < horizon:
            return (
                "NOT_DISPATCHED",
                "HALT_LIMBO_PROP1_VISIBILITY_LAG_FENCE_ACTIVE",
            )

        replica_status = target.query_read_replica(operation_id, current_time_ms)
        if replica_status == "SETTLED_VISIBLE":
            entry["disposition"] = "CONFIRMED"
            return "CONFIRMED", "RECONCILED_AFTER_VISIBILITY_HORIZON_NO_RETRY"

        entry["disposition"] = "REFUTED"
        return "REFUTED", "SAFE_TO_REISSUE_AFTER_VISIBILITY_HORIZON"


@dataclass(frozen=True)
class ParlCriticalStepTelemetry:
    total_subagent_steps: int
    critical_path_steps: int
    parallelism_efficiency_bps: int
    spurious_parallelism_flagged: bool
    verdict_code: str


def evaluate_parl_concurrency_efficiency(
    subagent_token_costs: List[int],
    critical_path_token_cost: int,
    max_token_inflation_ratio: float = 2.0,
) -> ParlCriticalStepTelemetry:
    """
    Fudan Concurrency (`arXiv:2610.10263`) & Moonshot PARL Critical Steps Evaluator:
    Flags spurious parallelism when parallel subagent fan-out burns > `max_token_inflation_ratio`
    times the critical-path token budget without proportional step reduction.
    """
    total_cost = sum(subagent_token_costs)
    ratio = total_cost / max(1, critical_path_token_cost)
    efficiency_bps = int(round((critical_path_token_cost / max(1, total_cost)) * 10000))
    spurious = ratio > max_token_inflation_ratio
    code = (
        "FLAG_SPURIOUS_PARALLELISM_TOKEN_INFLATION"
        if spurious
        else "OK_BOUNDED_PARALLELISM"
    )
    return ParlCriticalStepTelemetry(
        total_subagent_steps=len(subagent_token_costs),
        critical_path_steps=1,
        parallelism_efficiency_bps=efficiency_bps,
        spurious_parallelism_flagged=spurious,
        verdict_code=code,
    )


def test_limbo_proposition_1_visibility_lag_fence_prevents_duplicates() -> None:
    # Target has commit delay delta=120ms and read-replica lag lambda=250ms (total lag = 370ms)
    unguarded_target = SimulatedReplicaTarget(delta_ms=120, lambda_ms=250)
    guarded_target = SimulatedReplicaTarget(delta_ms=120, lambda_ms=250)

    # 1. Unguarded baseline: dispatches at t=0, gets 504, checks replica at t=100ms (< 370ms),
    # sees NOT_FOUND_ON_REPLICA, and blindly retries -> causes 2 duplicate commits!
    unguarded_target.submit_write("op-limbo-1", dispatch_time_ms=0)
    replica_at_100 = unguarded_target.query_read_replica("op-limbo-1", query_time_ms=100)
    assert replica_at_100 == "NOT_FOUND_ON_REPLICA"
    unguarded_target.submit_write("op-limbo-1", dispatch_time_ms=105)
    assert len(unguarded_target.commits_by_op["op-limbo-1"]) == 2

    # 2. AEIB Station 2 Visibility-Lag Fence:
    fence = VisibilityLagFenceInterlock(delta_ms=120, lambda_ms=250, safety_margin_ms=10)
    guarded_target.submit_write("op-limbo-1", dispatch_time_ms=0)
    horizon = fence.record_indeterminate_timeout("op-limbo-1", dispatch_time_ms=0)
    assert horizon == 380  # 0 + 120 + 250 + 10

    # Premature probe/retry at t=100ms and t=350ms is strictly blocked by the fence
    disp_100, code_100 = fence.evaluate_retry_or_reconcile("op-limbo-1", 100, guarded_target)
    assert disp_100 == "NOT_DISPATCHED"
    assert code_100 == "HALT_LIMBO_PROP1_VISIBILITY_LAG_FENCE_ACTIVE"

    disp_350, code_350 = fence.evaluate_retry_or_reconcile("op-limbo-1", 350, guarded_target)
    assert disp_350 == "NOT_DISPATCHED"
    assert code_350 == "HALT_LIMBO_PROP1_VISIBILITY_LAG_FENCE_ACTIVE"

    # At t=385ms (>= 380ms visibility horizon), reconciliation observes the settled write on replica
    disp_385, code_385 = fence.evaluate_retry_or_reconcile("op-limbo-1", 385, guarded_target)
    assert disp_385 == "CONFIRMED"
    assert code_385 == "RECONCILED_AFTER_VISIBILITY_HORIZON_NO_RETRY"
    assert len(guarded_target.commits_by_op["op-limbo-1"]) == 1


def test_fudan_and_parl_spurious_parallelism_governance() -> None:
    # Unconstrained 10-subagent fan-out burning 3.31x tokens vs critical path (arXiv:2610.10263)
    unconstrained = evaluate_parl_concurrency_efficiency(
        subagent_token_costs=[3310] * 10,
        critical_path_token_cost=10000,
        max_token_inflation_ratio=2.0,
    )
    assert unconstrained.spurious_parallelism_flagged is True
    assert unconstrained.verdict_code == "FLAG_SPURIOUS_PARALLELISM_TOKEN_INFLATION"

    # Governed 3-lane orthogonal dispatch within 1.5x critical path budget
    governed = evaluate_parl_concurrency_efficiency(
        subagent_token_costs=[5000, 5000, 4500],
        critical_path_token_cost=10000,
        max_token_inflation_ratio=2.0,
    )
    assert governed.spurious_parallelism_flagged is False
    assert governed.verdict_code == "OK_BOUNDED_PARALLELISM"
