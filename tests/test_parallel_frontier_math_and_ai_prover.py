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
    assert int(w4.sovereign_optimal_metric_bps_or_val) == 45
    assert w4.baseline_metric_bps_or_val == 32
    assert w4.constraints_verified_count == 14190
    assert w4.violations_count == 0
    assert w4.improvement_bps == 4062

    # 2. MATH-05: Rank-7 Matrix Multiplication Tensor (64/64 tensor equations satisfied)
    w5 = engine.solve_math05_strassen_tensor_rank_7()
    assert int(w5.sovereign_optimal_metric_bps_or_val) == 343
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
    assert int(w7.sovereign_optimal_metric_bps_or_val) == 44
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
    assert int(w_ai3.sovereign_optimal_metric_bps_or_val) == 9940
    assert int(w_ai3.baseline_metric_bps_or_val) == 3800
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


def test_section23_mutation_adequacy_boundary_oracles() -> None:
    """Comprehensive boundary, solver-branch, and mutant-injection oracles for Section 23."""
    import builtins
    import pytest

    engine = ParallelFrontierMathAndAiProverEngine()

    # 1. MATH-04 failure branches (lines 253 and 261)
    orig_len = builtins.len

    def _zero_orbit_len(obj: object) -> int:
        n = orig_len(obj)  # type: ignore[arg-type]
        if isinstance(obj, list) and n == 5 and obj and isinstance(obj[0], tuple) and orig_len(obj[0]) == 5:
            return 0
        return n

    builtins.len = _zero_orbit_len  # type: ignore[assignment]
    try:
        with pytest.raises(RuntimeError, match="Failed to find 9-orbit 45-cap"):
            engine.solve_math04_cap_set_f3_5()
    finally:
        builtins.len = orig_len  # type: ignore[assignment]

    orig_v_cap5 = ParallelFrontierMathAndAiProverEngine.verify_cap_set_f3_5
    ParallelFrontierMathAndAiProverEngine.verify_cap_set_f3_5 = staticmethod(lambda pts: (False, 0, 1))  # type: ignore[assignment]
    try:
        with pytest.raises(RuntimeError, match="45-cap verification failed"):
            engine.solve_math04_cap_set_f3_5()
    finally:
        ParallelFrontierMathAndAiProverEngine.verify_cap_set_f3_5 = staticmethod(orig_v_cap5)  # type: ignore[assignment]

    # 2. MATH-05 mismatched rank length check (line 308)
    assert ParallelFrontierMathAndAiProverEngine.verify_bilinear_matrix_tensor_2x2(
        [[1, 0, 0, 0]], [], []
    ) == (False, 0, 1)

    # 3. MATH-06 k=1 lag correlation & exact improvement_bps (lines 422, 462)
    assert ParallelFrontierMathAndAiProverEngine.compute_labs_energy_and_merit([1, 1, 1])[0] == 5
    w6 = engine.solve_math06_labs_barker13_and_n15()
    expected_w6_imp = int(
        round(
            ((w6.sovereign_optimal_metric_bps_or_val - w6.baseline_metric_bps_or_val) / w6.baseline_metric_bps_or_val)
            * (100 * 100)
        )
    )
    assert w6.improvement_bps == expected_w6_imp

    # 4. MATH-07 MRV backtracking branch (line 583)
    orig_v_schur = ParallelFrontierMathAndAiProverEngine.verify_schur_sum_free_partition
    orig_enum = builtins.enumerate
    schur_calls = {"n": 0}

    def _force_mrv_schur(partition, target_n: int = 44):  # type: ignore[no-untyped-def]
        schur_calls["n"] += 1
        if schur_calls["n"] == 1:
            return False, 0, 1
        return orig_v_schur(partition, target_n)

    def _perturbed_enum(iterable, start: int = 0):  # type: ignore[no-untyped-def]
        lst = list(iterable)
        if orig_len(lst) == 4 and isinstance(lst[0], set) and 44 in lst[0]:
            s0 = set(lst[0]) - {44}
            s1 = set(lst[1]) | {44}
            lst = [s0, s1, lst[2], lst[3]]
        return orig_enum(lst, start)

    ParallelFrontierMathAndAiProverEngine.verify_schur_sum_free_partition = staticmethod(_force_mrv_schur)  # type: ignore[assignment]
    builtins.enumerate = _perturbed_enum  # type: ignore[assignment]
    try:
        w7_mrv = engine.solve_math07_schur_number_s4_44()
        assert w7_mrv.violations_count == 0
    finally:
        ParallelFrontierMathAndAiProverEngine.verify_schur_sum_free_partition = staticmethod(orig_v_schur)  # type: ignore[assignment]
        builtins.enumerate = orig_enum  # type: ignore[assignment]

    # 5. AI-MATH-01 exact budget boundary & Smith inversion counter (lines 687, 703)
    w_ai1 = engine.solve_aimath01_kid_sake_optimal_packing()
    assert w_ai1.constructive_witness_summary["total_selected_tokens"] == 45 * 100

    orig_sorted = builtins.sorted
    builtins.sorted = lambda it, key=None, reverse=False: orig_sorted(it, key=key, reverse=False)  # type: ignore[assignment]
    try:
        w_ai1_inv = engine.solve_aimath01_kid_sake_optimal_packing()
        assert w_ai1_inv.violations_count == 7
    finally:
        builtins.sorted = orig_sorted  # type: ignore[assignment]

    # 6. AI-MATH-02 exact float expected latency (line 770)
    orig_round = builtins.round
    seen_floats = []

    def _rec_round(val, *a):  # type: ignore[no-untyped-def]
        seen_floats.append(val)
        return orig_round(val, *a)

    builtins.round = _rec_round  # type: ignore[assignment]
    try:
        engine.solve_aimath02_limbo_minimax_fence()
        assert abs(seen_floats[0] - 422.65) < 1e-6
    finally:
        builtins.round = orig_round  # type: ignore[assignment]

    # 7. Parallel bundle T4+ mutant inputs & single-violation boundary (lines 895, 898, 901)
    orig_v_ten = ParallelFrontierMathAndAiProverEngine.verify_bilinear_matrix_tensor_2x2

    def _checked_cap5(pts):  # type: ignore[no-untyped-def]
        ok, c, v = orig_v_cap5(pts)
        if orig_len(pts) == 3:
            return False, 1, 1
        return ok, c, v

    def _checked_ten(u, v, w):  # type: ignore[no-untyped-def]
        if w == [[0, 0, 0, 0]] * 7:
            assert u == [[1, 0, 0, 0]] * 7
            assert v == [[1, 0, 0, 0]] * 7
        return orig_v_ten(u, v, w)

    def _checked_schur(part, target_n: int = 44):  # type: ignore[no-untyped-def]
        if target_n == 4:
            assert part == [[1, 2, 3], [4]]
        return orig_v_schur(part, target_n)

    ParallelFrontierMathAndAiProverEngine.verify_cap_set_f3_5 = staticmethod(_checked_cap5)  # type: ignore[assignment]
    ParallelFrontierMathAndAiProverEngine.verify_bilinear_matrix_tensor_2x2 = staticmethod(_checked_ten)  # type: ignore[assignment]
    ParallelFrontierMathAndAiProverEngine.verify_schur_sum_free_partition = staticmethod(_checked_schur)  # type: ignore[assignment]
    try:
        b = engine.execute_all_in_parallel_and_sign()
        assert b["t4_plus_mutation_adequacy"]["mutants_killed"] == 3
    finally:
        ParallelFrontierMathAndAiProverEngine.verify_cap_set_f3_5 = staticmethod(orig_v_cap5)  # type: ignore[assignment]
        ParallelFrontierMathAndAiProverEngine.verify_bilinear_matrix_tensor_2x2 = staticmethod(orig_v_ten)  # type: ignore[assignment]
        ParallelFrontierMathAndAiProverEngine.verify_schur_sum_free_partition = staticmethod(orig_v_schur)  # type: ignore[assignment]


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
