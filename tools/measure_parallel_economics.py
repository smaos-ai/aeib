#!/usr/bin/env python3
"""
tools/measure_parallel_economics.py — AEIB Concurrency & Token-Economics Observability Engine

Integrates empirical multi-agent research metrics:
1. Moonshot PARL Critical Steps (arXiv:2602.02276):
   CriticalSteps = sum_t (S_main^(t) + max_i S_sub,i^(t))
2. Spurious Parallelism Detection (arXiv:2602.02276 & arXiv:2610.10263):
   Flags subagents that consume tokens without reducing CriticalSteps or returning verified findings.
3. Saliency Folding Compression Ratio (TrajAudit arXiv:2605.26563):
   Measures parent context saved via bounded <=250-word JCS hand-back contracts.
4. Endogenous Security Budget Burn (Token Economics arXiv:2605.09104):
   Tracks root-sponsor token & financial velocity against hard sprint caps.
5. ParaGUIBench & Multi-Agent Architecture Metrics (arXiv:2607.22689 & arXiv:2603.22651):
   Step Reduction Ratio S, Parallelism Degree P, Failure Surface Edges, and Human Review Load.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class SubagentStageTrace:
    subagent_id: str
    steps_taken: int
    input_tokens_billed: int
    raw_transcript_tokens: int
    handback_tokens: int
    verified_findings_count: int
    interface_collision_detected: bool = False
    timed_out: bool = False


@dataclass(frozen=True)
class StageObservabilityReport:
    stage_id: str
    subagent_count: int
    serial_equivalent_steps: int
    parl_critical_steps: int
    step_latency_speedup: float
    spurious_subagent_ids: List[str]
    spurious_token_waste: int
    saliency_compression_pct: float
    total_stage_tokens: int
    earliest_decisive_error_subagent: Optional[str]
    governance_verdict: str


def analyze_parallel_stage(
    stage_id: str,
    main_orchestrator_steps: int,
    subagents: List[SubagentStageTrace],
) -> StageObservabilityReport:
    if not subagents:
        return StageObservabilityReport(
            stage_id=stage_id,
            subagent_count=0,
            serial_equivalent_steps=main_orchestrator_steps,
            parl_critical_steps=main_orchestrator_steps,
            step_latency_speedup=1.0,
            spurious_subagent_ids=[],
            spurious_token_waste=0,
            saliency_compression_pct=0.0,
            total_stage_tokens=0,
            earliest_decisive_error_subagent=None,
            governance_verdict="SERIAL_COLLAPSE_WARNING",
        )

    serial_steps = main_orchestrator_steps + sum(s.steps_taken for s in subagents)
    # Moonshot PARL equation: S_main^(t) + max_i S_sub,i^(t)
    parl_crit_steps = main_orchestrator_steps + max(s.steps_taken for s in subagents)
    speedup = round(serial_steps / max(parl_crit_steps, 1), 2)

    # Detect Spurious Parallelism (subagents with 0 verified findings, timeout, or collision)
    spurious_ids: List[str] = []
    spurious_waste = 0
    decisive_error_agent: Optional[str] = None

    for s in subagents:
        if s.interface_collision_detected or s.timed_out:
            if decisive_error_agent is None:
                decisive_error_agent = s.subagent_id
        if s.verified_findings_count == 0 or s.timed_out or s.interface_collision_detected:
            spurious_ids.append(s.subagent_id)
            spurious_waste += s.input_tokens_billed

    total_raw = sum(s.raw_transcript_tokens for s in subagents)
    total_handback = sum(s.handback_tokens for s in subagents)
    compression_pct = (
        round((1.0 - (total_handback / total_raw)) * 100.0, 2) if total_raw > 0 else 0.0
    )
    total_tokens = sum(s.input_tokens_billed for s in subagents)

    if decisive_error_agent is not None:
        verdict = "HALT_CONCURRENCY_FAILURE_PATTERN_DETECTED"
    elif len(spurious_ids) > 0:
        verdict = "DEGRADED_SPURIOUS_PARALLELISM"
    else:
        verdict = "OPTIMAL_GOVERNED_CONCURRENCY"

    return StageObservabilityReport(
        stage_id=stage_id,
        subagent_count=len(subagents),
        serial_equivalent_steps=serial_steps,
        parl_critical_steps=parl_crit_steps,
        step_latency_speedup=speedup,
        spurious_subagent_ids=spurious_ids,
        spurious_token_waste=spurious_waste,
        saliency_compression_pct=compression_pct,
        total_stage_tokens=total_tokens,
        earliest_decisive_error_subagent=decisive_error_agent,
        governance_verdict=verdict,
    )


@dataclass(frozen=True)
class ArchitectureMetrics:
    architecture: str
    worker_count: int
    serial_steps: int
    critical_path_steps: int
    step_reduction_ratio_S: float
    parallelism_degree_P: float
    total_billed_input_tokens: int
    token_savings_vs_serial_pct: float
    failure_surface_edges: int
    human_review_tokens: int


def evaluate_architectures(
    worker_step_counts: List[int],
    parent_base_tokens: int = 80_000,
    subagent_base_tokens: int = 12_000,
    tokens_per_step: int = 2_500,
    handback_cap_tokens: int = 350,
    naive_conflict_rework_steps: int = 6,
) -> List[ArchitectureMetrics]:
    k = len(worker_step_counts)
    l_serial = sum(worker_step_counts)

    # 1. Monolithic Serial Agent: every step re-bills the growing parent context
    serial_tokens = 0
    curr_ctx = parent_base_tokens
    for _ in range(l_serial):
        curr_ctx += tokens_per_step
        serial_tokens += curr_ctx
    serial_human_review = curr_ctx - parent_base_tokens

    # 2. Decentralized Mesh Swarm: sequential active execution + handoff restatement overhead
    swarm_steps = l_serial + k  # +1 handoff step per agent transition
    swarm_tokens = int(serial_tokens * 2.15)  # Empirical >2x token sprawl from context restatement
    swarm_edges = (k * (k - 1)) // 2

    # 3. Naive Fan-Out Parallel (no contract freeze -> merge conflict rework in parent)
    naive_crit_steps = max(worker_step_counts) + naive_conflict_rework_steps
    naive_sub_tokens = sum(
        sum(subagent_base_tokens + (m + 1) * tokens_per_step for m in range(steps))
        for steps in worker_step_counts
    )
    # Parent dumps full raw subagent logs (e.g., 8,000 tokens each) + runs rework steps
    naive_parent_ctx = parent_base_tokens + (k * 8_000)
    naive_rework_tokens = sum(
        naive_parent_ctx + (r + 1) * tokens_per_step
        for r in range(naive_conflict_rework_steps)
    )
    naive_total_tokens = naive_sub_tokens + naive_rework_tokens

    # 4. AEIB Contract-Frozen Shared-Nothing Parallel (Phase B freeze + Move 1-4)
    # 1 contract-freeze step + max(worker_steps) + 1 deterministic receipt merge step
    aeib_crit_steps = 1 + max(worker_step_counts) + 1
    aeib_sub_tokens = naive_sub_tokens
    # Parent only ingests k * 350-token bounded JSON receipts
    aeib_parent_merge_tokens = (parent_base_tokens + tokens_per_step) + (
        parent_base_tokens + tokens_per_step + (k * handback_cap_tokens)
    )
    aeib_total_tokens = aeib_sub_tokens + aeib_parent_merge_tokens
    aeib_human_review = 500 + (k * handback_cap_tokens)  # 1 contract + k compact receipts

    return [
        ArchitectureMetrics(
            architecture="1_MONOLITHIC_SERIAL",
            worker_count=1,
            serial_steps=l_serial,
            critical_path_steps=l_serial,
            step_reduction_ratio_S=1.0,
            parallelism_degree_P=1.0,
            total_billed_input_tokens=serial_tokens,
            token_savings_vs_serial_pct=0.0,
            failure_surface_edges=1,
            human_review_tokens=serial_human_review,
        ),
        ArchitectureMetrics(
            architecture="2_DECENTRALIZED_MESH_SWARM",
            worker_count=k,
            serial_steps=l_serial,
            critical_path_steps=swarm_steps,
            step_reduction_ratio_S=round(l_serial / swarm_steps, 2),
            parallelism_degree_P=1.0,
            total_billed_input_tokens=swarm_tokens,
            token_savings_vs_serial_pct=round(
                (1.0 - (swarm_tokens / serial_tokens)) * 100, 1
            ),
            failure_surface_edges=swarm_edges,
            human_review_tokens=serial_human_review * 2,
        ),
        ArchitectureMetrics(
            architecture="3_NAIVE_UNCOORDINATED_PARALLEL",
            worker_count=k,
            serial_steps=l_serial,
            critical_path_steps=naive_crit_steps,
            step_reduction_ratio_S=round(l_serial / naive_crit_steps, 2),
            parallelism_degree_P=round(l_serial / naive_crit_steps, 2),
            total_billed_input_tokens=naive_total_tokens,
            token_savings_vs_serial_pct=round(
                (1.0 - (naive_total_tokens / serial_tokens)) * 100, 1
            ),
            failure_surface_edges=swarm_edges,
            human_review_tokens=k * 8_000,
        ),
        ArchitectureMetrics(
            architecture="4_AEIB_CONTRACT_FROZEN_PARALLEL",
            worker_count=k,
            serial_steps=l_serial,
            critical_path_steps=aeib_crit_steps,
            step_reduction_ratio_S=round(l_serial / aeib_crit_steps, 2),
            parallelism_degree_P=round(l_serial / max(worker_step_counts), 2),
            total_billed_input_tokens=aeib_total_tokens,
            token_savings_vs_serial_pct=round(
                (1.0 - (aeib_total_tokens / serial_tokens)) * 100, 1
            ),
            failure_surface_edges=k,
            human_review_tokens=aeib_human_review,
        ),
    ]


if __name__ == "__main__":
    report_stage = analyze_parallel_stage(
        stage_id="stage-aeib-governed",
        main_orchestrator_steps=2,
        subagents=[
            SubagentStageTrace("sub-1", 8, 120_000, 14_000, 320, verified_findings_count=3),
            SubagentStageTrace("sub-2", 7, 105_000, 12_500, 290, verified_findings_count=2),
            SubagentStageTrace("sub-3", 8, 118_000, 15_000, 340, verified_findings_count=4),
            SubagentStageTrace("sub-4", 6, 92_000, 11_000, 280, verified_findings_count=2),
        ],
    )
    arch_comparison = evaluate_architectures([8, 8, 8, 8])
    print(json.dumps({
        "stage_report": asdict(report_stage),
        "architectures": [asdict(a) for a in arch_comparison],
    }, indent=2))
