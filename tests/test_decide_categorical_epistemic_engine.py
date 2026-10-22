# File: tests/test_decide_categorical_epistemic_engine.py
"""
Verification suite for /decide v3.0:
- Submodular monotonicity and diminishing marginal returns across the 8 Orthogonal Keyword Tag Axes.
- Category 1 (CURRENT = C_local (+) C_humanity) O(1) snapshot + 2025-2026 science grounding.
- Category 2 (MISSED = d(C)) strict domain enforcement (analyzes CURRENT only) & FCA Galois voids.
- Category 3 (NEXT = Phi(C, M)) iterative epistemic contraction to 0 bps, >= 100x pairwise
  compositional coverage multiplier vs. single-shot prompt baseline, and Ed25519 JCS receipt verification.
"""
from pathlib import Path
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.decide_categorical_epistemic_engine import (
    CurrentCategoryBuilder,
    MissedDifferentialOperator,
    NextCategorySynthesisFunctor,
    OrthogonalKeywordTagExpander,
    run_decide_v3_categorical_pipeline,
)


def test_submodular_monotonicity_and_100x_pairwise_coverage() -> None:
    expander = OrthogonalKeywordTagExpander()

    # 1. Verify strict monotonicity across nested tag subsets S <= T
    s_small = {"AXIS_1_MATH_INFORMATION_THEORY"}
    s_medium = {
        "AXIS_1_MATH_INFORMATION_THEORY",
        "AXIS_2_SYSTEMS_KERNEL_SUBSTRATE",
        "AXIS_3_CRYPTOGRAPHIC_WIRE_FINALITY",
    }
    s_all = {a.axis_id for a in expander.ordered_axes}

    cov_empty = expander.evaluate_coverage_bps(set())
    cov_small = expander.evaluate_coverage_bps(s_small)
    cov_medium = expander.evaluate_coverage_bps(s_medium)
    cov_all = expander.evaluate_coverage_bps(s_all)

    assert cov_empty == 0
    assert cov_small > cov_empty
    assert cov_medium > cov_small
    assert cov_all > cov_medium
    assert cov_all >= 9500

    # 2. Verify positive marginal gain for every orthogonal axis
    current_set = set()
    for axis in expander.ordered_axes:
        gain = expander.marginal_gain_bps(current_set, axis.axis_id)
        assert gain > 0
        current_set.add(axis.axis_id)
    assert expander.marginal_gain_bps(current_set, "AXIS_1_MATH_INFORMATION_THEORY") == 0

    # 3. Verify >= 100x Pairwise Compositional Coverage Multiplier vs. single-shot baseline
    proof = expander.expand_query_with_orthogonal_tags(
        "Design next-generation autonomous execution boundary"
    )
    assert proof["axes_activated"] == 8
    assert (
        proof["orthogonal_8axis_expansion"]["pairwise_coverage_multiplier_x"] >= 100
    )


def test_missed_operator_enforces_current_only_constraint() -> None:
    # Passing a non-CURRENT dictionary into MissedDifferentialOperator must fail closed
    with pytest.raises(ValueError, match="HALT_MISSED_REQUIRES_CURRENT_ONLY"):
        MissedDifferentialOperator.analyze_current_only(
            {"category": "UNVERIFIED_SPECULATION"}
        )


def test_current_missed_next_categorical_contraction_and_ed25519_receipt() -> None:
    report = run_decide_v3_categorical_pipeline()

    # Category 1: CURRENT
    c1 = report["category_1_current"]
    assert c1["local_modules_indexed"] >= 400
    assert c1["local_keywords_indexed"] >= 7000
    assert c1["local_attributes_count"] == 18
    assert c1["humanity_2026_solutions_count"] == 4

    # Category 2: MISSED (d(C))
    c2 = report["category_2_missed"]
    assert c2["analyzed_current_only"] is True
    assert len(c2["local_absorption_gaps"]) == 4
    assert c2["galois_frontier_voids_count"] == 4
    assert c2["initial_local_blind_spot_bps"] > 0

    # Category 3: NEXT (Phi(C, M))
    c3 = report["category_3_next"]
    assert c3["pairwise_coverage_multiplier_x"] >= 100
    trace = c3["contraction_trace"]
    assert len(trace) == 3
    assert (
        trace[0]["residual_blind_spot_bps"]
        > trace[1]["residual_blind_spot_bps"]
        > trace[2]["residual_blind_spot_bps"]
    )
    assert trace[2]["residual_blind_spot_bps"] == 0
    assert c3["final_residual_blind_spot_bps"] == 0
    assert c3["signature_verified"] is True

    # Falsification: tampering with the NEXT synthesis payload invalidates the Ed25519 receipt
    builder = CurrentCategoryBuilder()
    cur = builder.build_current_category()
    mis = MissedDifferentialOperator.analyze_current_only(cur)
    signer = Ed25519PrivateKey.generate()
    functor = NextCategorySynthesisFunctor(signer)
    receipt = functor.synthesize_next_category("test query", cur, mis)
    assert NextCategorySynthesisFunctor.verify_next_synthesis_receipt(
        receipt, functor.pubkey
    )

    tampered = dict(receipt)
    tampered["next_synthesis_payload"] = {
        **receipt["next_synthesis_payload"],
        "final_residual_blind_spot_bps": 500,
    }
    assert not NextCategorySynthesisFunctor.verify_next_synthesis_receipt(
        tampered, functor.pubkey
    )


def test_banned_words_absence() -> None:
    forbidden = [
        "guaran" + "teed",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "unhack" + "able",
        "proven universal" + "ly",
    ]
    for path in (
        Path("src/decide_categorical_epistemic_engine.py"),
        Path(__file__),
    ):
        text = path.read_text(encoding="utf-8").lower()
        for word in forbidden:
            assert word not in text, f"Forbidden token '{word}' found in {path}"
