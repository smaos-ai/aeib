"""Verification suite for Vendor-Independent Pre-Push CI/CD Gate: Metamorphic Oracles,
CEGIS Shrunk-Counterexample Repair, and Asymptotic Big-O Complexity Enforcer (Section 25).
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

from src.vendor_independent_prepush_cegis_gate import (
    AsymptoticComplexityAndAstMaintainabilityGate,
    CegisCounterexampleShrinkerAndSketchEngine,
    MetamorphicRelationalOracleEngine,
    VendorIndependentPrePushGate,
)


def test_boundary1_metamorphic_oracles_catch_non_idempotent_bug() -> None:
    """Verify MR-01..MR-05 pass on governed implementation and catch a buggy implementation."""
    gate = VendorIndependentPrePushGate()
    report = gate.run_full_vendor_independence_audit()
    assert report["metamorphic_relations_passed"] == 5
    assert report["metamorphic_total_violations"] == 0

    # Falsification: unguarded dispatch that double-charges on replay fails MR-02
    debited = 0

    def buggy_dispatch(_caid: str, amount: int) -> Tuple[str, int]:
        nonlocal debited
        debited += amount
        return ("COMMITTED", debited)

    verdict_buggy = (
        MetamorphicRelationalOracleEngine.check_mr02_idempotent_dispatch_invariance(
            buggy_dispatch, trials=10
        )
    )
    assert verdict_buggy.passed is False
    assert verdict_buggy.violations_found == 10
    assert verdict_buggy.minimal_counterexample is not None


def test_boundary2_cegis_counterexample_shrinking_and_ast_localization() -> None:
    """Verify that a 20-step failing trace shrinks to the exact 2-element duplicate pair."""
    buggy_code = """
    def unguarded_dispatch(caid: str, amount: int) -> int:
        debited = 0
        debited += amount
        return debited
    """
    trace = [f"caid-{i}" for i in range(10)] + ["caid-dup", "caid-x", "caid-dup"]
    directive = (
        CegisCounterexampleShrinkerAndSketchEngine.analyze_and_emit_cegis_sketch(
            buggy_code,
            trace,
            predicate_fails_fn=lambda seq: len(set(seq)) < len(seq),
        )
    )
    assert directive.shrunk_minimal_counterexample == ["caid-dup", "caid-dup"]
    assert directive.directive_token_estimate <= 120
    assert directive.token_savings_bps == 9515


def test_boundary3_asymptotic_complexity_and_ast_spaghetti_rejection() -> None:
    """Verify that O(N^2) scaling and deep AST nesting (>4 levels) are rejected."""
    clean_code = """
    def lookup_fast(items: list[int]) -> int:
        total = 0
        for x in items:
            total += x
        return total
    """
    # 1. Linear O(N) passes
    v_ok = AsymptoticComplexityAndAstMaintainabilityGate.evaluate_candidate(
        clean_code, work_counter_fn=lambda n: n
    )
    assert v_ok.passed is True
    assert v_ok.rejection_code == "OK_COMPLEXITY_AND_AST_CLEAN"

    # 2. Quadratic O(N^2) rejected even with clean AST
    v_quad = AsymptoticComplexityAndAstMaintainabilityGate.evaluate_candidate(
        clean_code, work_counter_fn=lambda n: n * n
    )
    assert v_quad.passed is False
    assert v_quad.rejection_code == "HALT_ASYMPTOTIC_COMPLEXITY_REGRESSION_O_N2"
    assert v_quad.empirical_scaling_exponent >= 1.95

    # 3. Deeply nested (>4 levels) spaghetti code rejected even with O(N) runtime
    spaghetti_code = """
    def deeply_nested(x: int) -> int:
        if x > 0:
            if x > 1:
                if x > 2:
                    if x > 3:
                        if x > 4:
                            return x
        return 0
    """
    v_spag = AsymptoticComplexityAndAstMaintainabilityGate.evaluate_candidate(
        spaghetti_code, work_counter_fn=lambda n: n
    )
    assert v_spag.passed is False
    assert v_spag.rejection_code == "HALT_AST_CYCLOMATIC_SPAGHETTI_DETECTED"
    assert v_spag.max_nesting_depth == 5


def test_zero_banned_promotional_words_in_section25_files() -> None:
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
        "src/vendor_independent_prepush_cegis_gate.py",
        "tests/test_vendor_independent_prepush_cegis_gate.py",
    ):
        content = (root / rel).read_text(encoding="utf-8").lower()
        for word in banned:
            assert word not in content, f"Banned term found in {rel}: {word}"
