#!/usr/bin/env python3
"""
tests/test_parallel_economics.py

Verifies the AEIB Concurrency & Token-Economics Observability Engine (tools/measure_parallel_economics.py):
1. Moonshot PARL Critical Steps (arXiv:2602.02276)
2. Spurious Parallelism Detection (arXiv:2602.02276 & arXiv:2610.10263)
3. Saliency Folding Compression Ratio (TrajAudit arXiv:2605.26563)
4. ParaGUIBench & Multi-Agent Architecture Metrics (arXiv:2607.22689)
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.measure_parallel_economics import (
    SubagentStageTrace,
    analyze_parallel_stage,
    evaluate_architectures,
)


def test_analyze_parallel_stage_optimal() -> None:
    traces = [
        SubagentStageTrace("sub-1", 8, 120_000, 14_000, 320, verified_findings_count=3),
        SubagentStageTrace("sub-2", 7, 105_000, 12_500, 290, verified_findings_count=2),
        SubagentStageTrace("sub-3", 8, 118_000, 15_000, 340, verified_findings_count=4),
        SubagentStageTrace("sub-4", 6, 92_000, 11_000, 280, verified_findings_count=2),
    ]

    report = analyze_parallel_stage(
        stage_id="stage-optimal",
        main_orchestrator_steps=2,
        subagents=traces,
    )

    assert report.subagent_count == 4
    # Serial equivalent = 2 + 8 + 7 + 8 + 6 = 31 steps
    assert report.serial_equivalent_steps == 31
    # PARL critical steps = 2 + max(8, 7, 8, 6) = 10 steps
    assert report.parl_critical_steps == 10
    # Speedup = 31 / 10 = 3.1
    assert report.step_latency_speedup == 3.1
    assert report.spurious_subagent_ids == []
    assert report.spurious_token_waste == 0
    assert report.governance_verdict == "OPTIMAL_GOVERNED_CONCURRENCY"
    assert report.saliency_compression_pct > 90.0
    assert report.earliest_decisive_error_subagent is None


def test_analyze_parallel_stage_spurious_parallelism() -> None:
    traces = [
        SubagentStageTrace("sub-1", 8, 120_000, 14_000, 320, verified_findings_count=3),
        SubagentStageTrace("sub-2", 7, 105_000, 12_500, 290, verified_findings_count=0),  # 0 findings -> spurious
    ]

    report = analyze_parallel_stage(
        stage_id="stage-spurious",
        main_orchestrator_steps=1,
        subagents=traces,
    )

    assert report.governance_verdict == "DEGRADED_SPURIOUS_PARALLELISM"
    assert "sub-2" in report.spurious_subagent_ids
    assert report.spurious_token_waste == 105_000


def test_analyze_parallel_stage_concurrency_failure_pattern() -> None:
    traces = [
        SubagentStageTrace("sub-1", 8, 120_000, 14_000, 320, verified_findings_count=3),
        SubagentStageTrace(
            "sub-2", 7, 105_000, 12_500, 290, verified_findings_count=1,
            interface_collision_detected=True,  # Collision!
        ),
    ]

    report = analyze_parallel_stage(
        stage_id="stage-collision",
        main_orchestrator_steps=1,
        subagents=traces,
    )

    assert report.governance_verdict == "HALT_CONCURRENCY_FAILURE_PATTERN_DETECTED"
    assert report.earliest_decisive_error_subagent == "sub-2"


def test_analyze_parallel_stage_empty() -> None:
    report = analyze_parallel_stage("stage-empty", 3, [])
    assert report.governance_verdict == "SERIAL_COLLAPSE_WARNING"
    assert report.step_latency_speedup == 1.0


def test_evaluate_architectures_para_gui_bench() -> None:
    metrics = evaluate_architectures([8, 8, 8, 8])
    assert len(metrics) == 4

    serial = metrics[0]
    mesh = metrics[1]
    naive = metrics[2]
    aeib = metrics[3]

    assert serial.architecture == "1_MONOLITHIC_SERIAL"
    assert serial.critical_path_steps == 32
    assert serial.step_reduction_ratio_S == 1.0
    assert serial.failure_surface_edges == 1

    assert mesh.architecture == "2_DECENTRALIZED_MESH_SWARM"
    assert mesh.critical_path_steps == 36
    assert mesh.failure_surface_edges == (4 * 3) // 2  # 6

    assert naive.architecture == "3_NAIVE_UNCOORDINATED_PARALLEL"
    assert naive.critical_path_steps == 8 + 6  # 14 steps

    assert aeib.architecture == "4_AEIB_CONTRACT_FROZEN_PARALLEL"
    # 1 freeze + 8 max + 1 merge = 10 steps
    assert aeib.critical_path_steps == 10
    assert aeib.step_reduction_ratio_S == 3.2
    assert aeib.failure_surface_edges == 4  # O(K) linear star topology
    assert aeib.token_savings_vs_serial_pct > 50.0
    assert aeib.human_review_tokens < 2_500
