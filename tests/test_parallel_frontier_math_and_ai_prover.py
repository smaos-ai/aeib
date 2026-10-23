"""Verification suite for Parallel Frontier Mathematical & AI Systems Optimization
Prover Engine (Section 23).
"""

from __future__ import annotations

from pathlib import Path

from src.parallel_frontier_math_and_ai_prover import (
    ParallelFrontierMathAndAiProverEngine,
)


def test_parallel_track_a_pure_math_solvers() -> None:
    """Verify MATH-04 (5D Cap Set F_3^5), MATH-05 (Strassen Rank-7 Tensor),
    MATH-06 (Barker-13 LABS), and MATH-07 (Schur S(4)=44).
    """
    engine = ParallelFrontierMathAndAiProverEngine()

    # 1. MATH-04: F_3^5 Cap Set (|S*| = 45 points, 0 collinear triples across 14,190 triples)
    w4 = engine.solve_math04_cap_set_f3_5()
    assert w4.sovereign_optimal_metric_bps_or_val == 45
    assert w4.baseline_metric_bps_or_val == 32
    assert w4.constraints_verified_count == 14190
    assert w4.violations_count == 0
    assert w4.improvement_bps == 4062

    # 2. MATH-05: Rank-7 Matrix Multiplication Tensor (64/64 tensor equations satisfied)
    w5 = engine.solve_math05_strassen_tensor_rank_7()
    assert w5.sovereign_optimal_metric_bps_or_val == 343
    assert w5.baseline_metric_bps_or_val == 512
    assert w5.constraints_verified_count == 64
    assert w5.violations_count == 0

    # 3. MATH-06: Barker-13 LABS Ground State (Energy E* = 6, Merit Factor 14.0833 = 140833 bps)
    w6 = engine.solve_math06_labs_barker13_and_n15()
    assert w6.sovereign_optimal_metric_bps_or_val == 140833
    assert w6.violations_count == 0
    assert w6.constructive_witness_summary["optimal_ground_state_energy"] == 6
    assert w6.constructive_witness_summary["max_aperiodic_sidelobe"] == 1

    # 4. MATH-07: Schur Sum-Free 4-Partition of {1..44} (S(4) = 44)
    w7 = engine.solve_math07_schur_number_s4_44()
    assert w7.sovereign_optimal_metric_bps_or_val == 44
    assert w7.baseline_metric_bps_or_val < 44
    assert w7.violations_count == 0


def test_parallel_track_b_ai_systems_math_solvers() -> None:
    """Verify AI-MATH-01 (Smith-Rule KID Packing), AI-MATH-02 (Limbo DP Fence),
    and AI-MATH-03 (CAVEAT Precision-Matrix Council Weighting).
    """
    engine = ParallelFrontierMathAndAiProverEngine()

    w_ai1 = engine.solve_aimath01_kid_sake_optimal_packing()
    assert w_ai1.sovereign_optimal_metric_bps_or_val > w_ai1.baseline_metric_bps_or_val * 5
    assert w_ai1.violations_count == 0

    w_ai2 = engine.solve_aimath02_limbo_minimax_fence()
    assert w_ai2.sovereign_optimal_metric_bps_or_val < w_ai2.baseline_metric_bps_or_val
    assert w_ai2.violations_count == 0

    w_ai3 = engine.solve_aimath03_caveat_mahalanobis_council()
    assert w_ai3.sovereign_optimal_metric_bps_or_val == 9940
    assert w_ai3.baseline_metric_bps_or_val == 3800
    assert w_ai3.violations_count == 0


def test_parallel_execution_and_signed_bundle_falsification() -> None:
    """Verify 7-worker concurrent execution, T4+ 10,000 bps mutation kill rate, and Ed25519 signature."""
    engine = ParallelFrontierMathAndAiProverEngine()
    bundle = engine.execute_all_in_parallel_and_sign()

    assert bundle["total_problems_solved"] == 7
    assert bundle["total_violations_found"] == 0
    assert bundle["t4_plus_mutation_adequacy"]["kill_rate_bps"] == 10000
    assert bundle["t4_plus_mutation_adequacy"]["qualifies_as_t4_plus"] is True
    assert engine.verify_signed_bundle(bundle) is True

    # Falsification: tampering with total_violations_found breaks Ed25519 signature
    tampered = dict(bundle)
    tampered["total_violations_found"] = 1
    assert engine.verify_signed_bundle(tampered) is False


def test_zero_banned_promotional_words_in_section23_files() -> None:
    """Ensure strict adherence to AGENTS.md epistemic boundaries."""
    banned = [
        "guaran" + "teed",
        "proven universal" + "ly",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
    ]
    root = Path(__file__).resolve().parent.parent
    for rel in (
        "src/parallel_frontier_math_and_ai_prover.py",
        "tests/test_parallel_frontier_math_and_ai_prover.py",
    ):
        content = (root / rel).read_text(encoding="utf-8").lower()
        for word in banned:
            assert word not in content, f"Banned term found in {rel}: {word}"
