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


def test_section25_mutation_adequacy_boundary_oracles() -> None:
    """Comprehensive boundary, arithmetic, and CLI oracles for Section 25."""
    import builtins
    import sys
    import src.vendor_independent_prepush_cegis_gate as v_mod

    gate = VendorIndependentPrePushGate()
    report = gate.run_full_vendor_independence_audit()
    assert report["metamorphic_total_trials"] == 169
    assert report["complexity_gate_quadratic_rejected"] is True
    assert report["cegis_shrunk_repair"]["original_failing_input_size"] == 20

    # MR-02 default trials == 30
    mr02_v = MetamorphicRelationalOracleEngine.check_mr02_idempotent_dispatch_invariance(
        lambda c, a: ("COMMITTED", a)
    )
    assert mr02_v.trials_executed == 3 * 10

    # MR-03 exact branch & invariant tracking via int subclasses
    lt_zero_checks = {"count": 0}

    class _ModInt(int):
        def __eq__(self, other: object) -> bool:
            if other != 0:
                raise ValueError(f"Expected == 0 in t % 2 == 0, got {other}")
            return int(self) == int(other)  # type: ignore[arg-type]

    class _AmtInt(int):
        def __le__(self, other: int) -> bool:
            return int(self) <= int(other)

        def __gt__(self, other: int) -> bool:
            raise ValueError("Mutated available >= amt to available < amt")

        def __lt__(self, other: int) -> bool:
            if other == 0:
                lt_zero_checks["count"] += 1
            return int(self) < int(other)

        def __add__(self, other: int) -> "_AmtInt":
            return _AmtInt(int(self) + int(other))

        def __radd__(self, other: int) -> "_AmtInt":
            return _AmtInt(int(other) + int(self))

        def __sub__(self, other: int) -> "_AmtInt":
            return _AmtInt(int(self) - int(other))

        def __rsub__(self, other: int) -> "_AmtInt":
            return _AmtInt(int(other) - int(self))

    class _StepInt(int):
        def __mul__(self, other: int) -> "_StepInt":
            return _StepInt(int(self) * int(other))

        def __mod__(self, divisor: int) -> int:
            if divisor == 4000:
                return _StepInt(int(self) % 4000)
            if divisor != 2:
                raise ValueError(f"Expected t % 2, got divisor {divisor}")
            return _ModInt(int(self) % 2)

        def __add__(self, other: int) -> "_AmtInt":
            return _AmtInt(int(self) + int(other))

    orig_range = builtins.range
    builtins.range = lambda *a: (_StepInt(x) for x in orig_range(*a))  # type: ignore[assignment]
    try:
        mr03_v = MetamorphicRelationalOracleEngine.check_mr03_monetary_mass_conservation(4)
        assert mr03_v.passed is True
        assert lt_zero_checks["count"] == 8
    finally:
        builtins.range = orig_range  # type: ignore[assignment]

    # MR-05 exact (t_a, t_b) pairs
    orig_max = builtins.max
    seen_pairs = []

    def _recording_max(a: int, b: int) -> int:
        seen_pairs.append((a, b))
        return orig_max(a, b)

    builtins.max = _recording_max  # type: ignore[assignment]
    try:
        MetamorphicRelationalOracleEngine.check_mr05_taint_lattice_monotonicity(10)
        assert seen_pairs == [
            (0, 0), (1, 0), (2, 0),
            (0, 1), (1, 1), (2, 1),
            (0, 2), (1, 2), (2, 2),
            (0, 0),
        ]
    finally:
        builtins.max = orig_max  # type: ignore[assignment]

    # Scaling exponent across all 3 intervals (64->128, 128->256, 256->512)
    alpha, _ = AsymptoticComplexityAndAstMaintainabilityGate.measure_empirical_scaling_exponent(
        lambda n: 64 if n < 512 else 512
    )
    assert alpha == 1.0

    # CLI main() without --self-test flag
    class _DummyCapsule:
        capsule_sha256 = "sha256:00"

    orig_argv = sys.argv
    orig_sync = v_mod.SovereignIndependentStateCapsuleEngine.build_and_sync_capsule
    orig_print = builtins.print
    printed = []
    sys.argv = ["vendor_independent_prepush_cegis_gate.py"]
    v_mod.SovereignIndependentStateCapsuleEngine.build_and_sync_capsule = lambda self, persist=True: _DummyCapsule()  # type: ignore[assignment]
    builtins.print = lambda *a, **kw: printed.append(a)  # type: ignore[assignment]
    try:
        assert v_mod.main() == 0
        assert len(printed) == 1
    finally:
        sys.argv = orig_argv
        v_mod.SovereignIndependentStateCapsuleEngine.build_and_sync_capsule = orig_sync  # type: ignore[assignment]
        builtins.print = orig_print  # type: ignore[assignment]


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
