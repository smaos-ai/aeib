# File: tests/test_decide_categorical_epistemic_engine.py
"""
Verification suite for /decide v3.1 (CURRENT -> MISSED -> BRAINSTORM -> NEXT):
- Submodular monotonicity and diminishing marginal returns across the 8 Orthogonal Keyword Tag Axes.
- Category 1 (CURRENT = C_local (+) C_humanity) O(1) snapshot + 2025-2026 science grounding.
- Category 2 (MISSED = d(C)) strict domain enforcement (analyzes CURRENT only) & FCA Galois voids.
- Category 2.5 (BRAINSTORM = Psi(q, C, M)) Cross-Ecosystem Multi-Model Hypothesis Generation
  (China DeepSeek-R1 + Qwen-Max vs. USA Gemini-Pro + Perplexity-Sonar), GLS Diversity Combining
  Effective Sample Size proof, and Structured Developer Pair-Programming Decision Schema generation.
- Category 3 (NEXT = Phi(C, M, B)) iterative epistemic contraction to 0 bps, >= 100x pairwise
  compositional coverage multiplier, and Ed25519 JCS receipt verification.
"""
from pathlib import Path
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.decide_categorical_epistemic_engine import (
    CrossEcosystemBrainstormEngine,
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
    with pytest.raises(ValueError, match="HALT_MISSED_REQUIRES_CURRENT_ONLY"):
        MissedDifferentialOperator.analyze_current_only(
            {"category": "UNVERIFIED_SPECULATION"}
        )


def test_cross_ecosystem_brainstorm_gls_diversity_and_pair_decision_schema() -> None:
    builder = CurrentCategoryBuilder()
    cur = builder.build_current_category()
    mis = MissedDifferentialOperator.analyze_current_only(cur)
    expander = OrthogonalKeywordTagExpander()
    exp_q = expander.expand_query_with_orthogonal_tags("Cross-ecosystem brainstorm test")

    b_engine = CrossEcosystemBrainstormEngine()
    b_state = b_engine.execute_cross_ecosystem_brainstorm(exp_q, cur, mis)

    assert b_state["category"] == "CATEGORY_2B_BRAINSTORM"
    assert b_state["models_queried"] == [
        "DeepSeek-R1",
        "Gemini-Pro",
        "Qwen-Max",
        "Perplexity-Sonar",
    ]
    gls = b_state["gls_diversity_combining_proof"]
    # Heterogeneous China+USA 4-model ensemble (N_eff = 2.7586 -> 27586 bps) > 2x homogeneous (1.1764 -> 11764 bps)
    assert gls["heterogeneous_china_usa_4model_n_eff_bps"] > 25000
    assert gls["homogeneous_4model_n_eff_bps"] < 12000
    assert gls["effective_sample_size_gain_bps"] > 23000

    # Verify convergent vs. divergent developer pair decision schema
    assert len(b_state["convergent_hypotheses"]) == 1
    pair_schemas = b_state["developer_pair_decision_schemas"]
    assert len(pair_schemas) == 1
    q_schema = pair_schemas[0]
    assert q_schema["question_id"] == "DEV_PAIR_Q_TOPIC_2_MULTIHOP_DISAGREEMENT_RESOLUTION"
    assert q_schema["is_multi_select"] is False
    assert len(q_schema["options"]) == 3
    assert q_schema["options"][0].startswith("(Recommended)")
    assert "Qwen-Max" in q_schema["diverging_agent_positions"]
    assert "Perplexity-Sonar" in q_schema["diverging_agent_positions"]


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

    # Category 2.5: BRAINSTORM (Psi(q, C, M))
    cb = report["category_2b_brainstorm"]
    assert cb["models_queried"] == [
        "DeepSeek-R1",
        "Gemini-Pro",
        "Qwen-Max",
        "Perplexity-Sonar",
    ]
    assert cb["convergent_hypotheses_count"] == 1
    assert len(cb["developer_pair_decision_schemas"]) == 1

    # Category 3: NEXT (Phi(C, M, B))
    c3 = report["category_3_next"]
    assert c3["pairwise_coverage_multiplier_x"] >= 100
    assert len(c3["resolved_developer_pair_decisions"]) == 1
    assert c3["resolved_developer_pair_decisions"][0]["selected_option_index"] == 0
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


def test_decide_categorical_mutation_boundaries() -> None:
    from src.decide_categorical_epistemic_engine import (
        HumanityPriorArtEntry,
        ModelAgentHypothesis,
    )

    assert HumanityPriorArtEntry.__dataclass_params__.frozen is True  # type: ignore[attr-defined]
    assert ModelAgentHypothesis.__dataclass_params__.frozen is True  # type: ignore[attr-defined]

    expander = OrthogonalKeywordTagExpander()
    assert expander.axes["AXIS_8_WESTERN_OPEN_SOURCE_SYSTEMS"].marginal_weight_bps == 1000
    assert expander.evaluate_coverage_bps({"AXIS_1_MATH_INFORMATION_THEORY"}) == 1381
    assert expander.evaluate_coverage_bps({"AXIS_8_WESTERN_OPEN_SOURCE_SYSTEMS"}) == 954
    assert OrthogonalKeywordTagExpander.pairwise_interaction_edges(0) == 0
    assert OrthogonalKeywordTagExpander.pairwise_interaction_edges(2) == 3

    proof = expander.expand_query_with_orthogonal_tags("q")
    assert proof["orthogonal_8axis_expansion"]["combined_moat_and_attribute_nodes"] == 28
    assert proof["orthogonal_8axis_expansion"]["pairwise_coverage_multiplier_x"] == 135

    # Exercise max(1, single_shot_edges) fallback when single_shot_edges == 0
    expander_zero = OrthogonalKeywordTagExpander()
    expander_zero.pairwise_interaction_edges = lambda n: 0 if n == 2 else OrthogonalKeywordTagExpander.pairwise_interaction_edges(n)  # type: ignore[method-assign]
    proof_zero = expander_zero.expand_query_with_orthogonal_tags("q")
    assert proof_zero["orthogonal_8axis_expansion"]["pairwise_coverage_multiplier_x"] == 406

    # GLS exact boundaries
    assert CrossEcosystemBrainstormEngine.compute_gls_effective_sample_size_bps(0, 5000) == 0
    assert CrossEcosystemBrainstormEngine.compute_gls_effective_sample_size_bps(4, 8000) == 11764
    assert CrossEcosystemBrainstormEngine.compute_gls_effective_sample_size_bps(4, 1500) == 27586

    builder = CurrentCategoryBuilder()
    cur = builder.build_current_category()
    mis = MissedDifferentialOperator.analyze_current_only(cur)
    assert len(mis["humanity_wire_finality_flaws"]) == 17
    assert mis["initial_local_blind_spot_bps"] == 1818

    b_engine = CrossEcosystemBrainstormEngine()
    with pytest.raises(ValueError, match="HALT_BRAINSTORM_REQUIRES_VALID_CURRENT"):
        b_engine.execute_cross_ecosystem_brainstorm(proof, {"category": "BAD"}, mis)
    with pytest.raises(ValueError, match="HALT_BRAINSTORM_REQUIRES_VALID_MISSED"):
        b_engine.execute_cross_ecosystem_brainstorm(proof, cur, {"category": "BAD"})

    b_state = b_engine.execute_cross_ecosystem_brainstorm(proof, cur, mis)
    assert b_state["gls_diversity_combining_proof"]["homogeneous_4model_n_eff_bps"] == 11764
    assert b_state["convergent_hypotheses"][0]["agreeing_models"] == ["DeepSeek-R1", "Gemini-Pro"]

    signer = Ed25519PrivateKey.generate()
    functor = NextCategorySynthesisFunctor(signer)
    rcpt = functor.synthesize_next_category("q", cur, mis, b_state)
    trace = rcpt["next_synthesis_payload"]["epistemic_contraction_trace"]
    assert trace[0]["residual_blind_spot_bps"] == 1818
    assert trace[1]["residual_blind_spot_bps"] == 909
    assert trace[1]["newly_synthesized_attributes"] == [
        "INV_FCA_GALOIS_LATTICE_CLOSURE",
        "INV_SUBMODULAR_COVERAGE_BOUND",
    ]

    # Exercise non-zero uncovered_2 in step 2 (kills L796 CONST_PERTURB 10000)
    cur_partial = dict(cur, c_local_attributes=[])
    mis_partial = dict(mis, local_absorption_gaps=["INV_SUBMODULAR_COVERAGE_BOUND"])
    rcpt_partial = functor.synthesize_next_category("q", cur_partial, mis_partial, b_state)
    trace_p = rcpt_partial["next_synthesis_payload"]["epistemic_contraction_trace"]
    assert trace_p[2]["residual_blind_spot_bps"] == 9545

