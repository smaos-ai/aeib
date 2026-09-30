#!/usr/bin/env python3
r"""
metrics.py — Metric Collector and Manifest Generator
Sovereign Multi-Agent OS (SMAOS) / Deterministic Fault-Injection Testbed

Computes empirical metrics against the two formal invariants:
  - Safety (Double-Mutation Constraint): commits(O) <= 1
  - Liveness (Terminal State Constraint): terminal state reached without deadlock
Generates reproducible JSON run manifests.
"""

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Any


@dataclass
class TrialResult:
    trial_index: int
    logical_operation_id: str
    control_baseline: str  # 'C_0', 'C_1', 'C_2', 'AEIB'
    injected_fault: str
    initial_http_status: int
    final_disposition: str
    commits_count: int
    safety_violation: bool  # True if commits_count > 1
    liveness_violation: bool  # True if remained in unconfirmed/deadlocked state
    overhead_ms: float


@dataclass
class BaselineManifest:
    baseline: str
    description: str
    total_trials: int
    safety_violations: int
    duplicate_rate_pct: float
    liveness_rate_pct: float
    avg_latency_ms: float
    summary: Dict[str, Any]
    trials: List[Dict[str, Any]]


def compute_manifest(baseline: str, description: str, trials: List[TrialResult]) -> BaselineManifest:
    total = len(trials)
    if total == 0:
        return BaselineManifest(
            baseline=baseline,
            description=description,
            total_trials=0,
            safety_violations=0,
            duplicate_rate_pct=0.0,
            liveness_rate_pct=0.0,
            avg_latency_ms=0.0,
            summary={},
            trials=[],
        )

    violations = sum(1 for t in trials if t.safety_violation)
    dup_rate = (violations / total) * 100.0
    live_count = sum(1 for t in trials if not t.liveness_violation)
    live_rate = (live_count / total) * 100.0
    avg_lat = sum(t.overhead_ms for t in trials) / total

    trials_dicts = [asdict(t) for t in trials]

    summary = {
        "safety_invariant_held": violations == 0,
        "liveness_invariant_held": live_rate == 100.0,
        "total_operations": total,
        "duplicate_commits": violations,
        "duplicate_rate": f"{dup_rate:.1f}%",
        "mean_overhead_ms": round(avg_lat, 2),
    }

    return BaselineManifest(
        baseline=baseline,
        description=description,
        total_trials=total,
        safety_violations=violations,
        duplicate_rate_pct=round(dup_rate, 2),
        liveness_rate_pct=round(live_rate, 2),
        avg_latency_ms=round(avg_lat, 2),
        summary=summary,
        trials=trials_dicts,
    )


def save_manifest(manifest: BaselineManifest, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(asdict(manifest), f, indent=2)
