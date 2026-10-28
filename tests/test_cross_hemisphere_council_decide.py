#!/usr/bin/env python3
"""
Tests for `tools/cross_hemisphere_council_decide.py` and `tools/current_missed_next_calculus.py`.
"""

from pathlib import Path
import pytest

from tools.cross_hemisphere_council_decide import (
    CrossHemisphereEpistemicCouncil,
    HypothesisClaim,
    TypedCrossCritiqueTuple,
    run_cross_hemisphere_council_scenario,
    test_cross_hemisphere_council_and_ask_router,
)
from tools.current_missed_next_calculus import (
    CurrentCategorySnapshot,
    EpistemicObservation,
    MissedBoundaryOperator,
    NonDilutableConflictRegister,
    WeightedPartialMaxSatSynthesizer,
)


def test_cross_hemisphere_council_and_3tier_ask_router_hold_and_dominance() -> None:
    test_cross_hemisphere_council_and_ask_router()
    report = run_cross_hemisphere_council_scenario()
    assert report.oracle_gap_prevented is True
    assert report.panel_verdict == "HOLD_FOR_DEVELOPER_ANSWERS"
    assert len(report.unique_minority_insights_preserved) == 1
    assert (
        report.unique_minority_insights_preserved[0]["winning_minority_model"]
        == "deepseek-v4-pro+perplexity-sonar"
    )
    modal_payload = report.to_ask_question_modal_payload()
    assert len(modal_payload["questions"]) == 1
    assert modal_payload["questions"][0]["options"][0].startswith("(Recommended)")
    assert CrossHemisphereEpistemicCouncil.verify_council_report_signature(report) is True


def test_cross_hemisphere_council_developer_answer_unlocks_synthesis() -> None:
    report_locked = run_cross_hemisphere_council_scenario(
        developer_answers={
            "ask-dev-03": "OPTION_A: Single-Node CVM Appliance (SQLite + io_uring)"
        }
    )
    assert report_locked.panel_verdict == "READY_TO_SYNTHESIZE"
    assert len(report_locked.developer_questions_schema) == 0
    assert CrossHemisphereEpistemicCouncil.verify_council_report_signature(report_locked) is True


def test_typed_cross_critique_prevents_tone_sycophancy_arxiv_2609_08016() -> None:
    initial_claim = HypothesisClaim(
        claim_id="claim-initial-01",
        origin_model="gemini-3.7",
        hemisphere="US_MODEL",
        topic_key="commit_drift_defense",
        proposed_position="Action-only SHA-256 payload hash is sufficient",
        has_verified_counterexample_or_url=False,
        evidence_artifact="internal_weights_assumption",
        confidence=0.88,
    )

    # 1. Hostile rhetorical critique WITHOUT a deterministic counterexample must NOT revise position
    tone_only_critique = TypedCrossCritiqueTuple(
        critique_id="crit-hostile-tone-01",
        reviewer_model="gpt-5.6",
        target_claim_id="claim-initial-01",
        rhetorical_tone="HOSTILE",
        has_deterministic_counterexample=False,
        counterexample_witness="",
        falsification_query="",
    )
    revised_flag, after_tone = CrossHemisphereEpistemicCouncil.evaluate_typed_cross_critique(
        initial_claim, tone_only_critique
    )
    assert revised_flag is False
    assert after_tone.proposed_position == initial_claim.proposed_position

    # 2. Neutral critique WITH a deterministic counterexample witness MUST revise position
    verified_critique = TypedCrossCritiqueTuple(
        critique_id="crit-counterexample-02",
        reviewer_model="deepseek-v4-pro",
        target_claim_id="claim-initial-01",
        rhetorical_tone="NEUTRAL",
        has_deterministic_counterexample=True,
        counterexample_witness="arXiv:2609.37475 Table 6.3: 60.527% Invalid Commit Rate under state drift",
        falsification_query="mutate_object_version_between_qualify_and_commit()",
    )
    revised_flag_2, after_ce = CrossHemisphereEpistemicCouncil.evaluate_typed_cross_critique(
        initial_claim, verified_critique
    )
    assert revised_flag_2 is True
    assert after_ce.has_verified_counterexample_or_url is True
    assert "60.527%" in after_ce.evidence_artifact


def test_current_missed_next_calculus_maxsat_and_nondilutable_register() -> None:
    snap = CurrentCategorySnapshot(
        local_invariants={
            "aeib.wal_mode": "SQLite WAL BEGIN IMMEDIATE + Rust io_uring 4K-aligned DirectIO",
        },
        humanity_today_findings={
            "arxiv.2610.04542": "Decide, Ask, or Defer 3-action epistemic divergence",
        },
    )
    assert "io_uring" in (snap.get_o1("aeib.wal_mode") or "")

    with pytest.raises(ValueError, match="HALT_MISSED_REQUIRES_CURRENT_ONLY"):
        MissedBoundaryOperator.compute_boundary(snap, source_stage="CATEGORY_3_NEXT")

    boundary = MissedBoundaryOperator.compute_boundary(snap)
    assert "arxiv.2610.04542" in boundary["unabsorbed_humanity_findings"]

    reg = NonDilutableConflictRegister()
    reg.record_observation(
        EpistemicObservation(
            action_id="act-drift-01",
            direction="PRIOR_ART_SEARCH",
            query_or_mutation="Action-only SHA-256 binding",
            conflict_detected=True,
            evidence_summary="60.527% Invalid Commit Rate under state drift",
            primary_reference="arXiv:2609.37475",
        )
    )

    council_locked = run_cross_hemisphere_council_scenario(
        developer_answers={
            "ask-dev-03": "OPTION_A: Single-Node CVM Appliance (SQLite + io_uring)"
        }
    )

    # While conflict is unresolved in NonDilutableConflictRegister, synthesis MUST hold
    synth_blocked = WeightedPartialMaxSatSynthesizer.synthesize_next(
        current=snap,
        missed=boundary,
        conflict_register=reg,
        council_report=council_locked,
    )
    assert synth_blocked["next_status"] == "HOLD_UNRESOLVED_HARD_CLAUSE_OR_DEV_ASK"

    # Once conflict is resolved with a concrete mitigation clause, synthesis locks ready
    reg.mark_resolved(
        "conflict:act-drift-01",
        "Enforce 6-Way Joint Commit Witness across Action, Object Version, Epoch, Policy, CapLease, and WYSIWYS.",
    )
    synth_ready = WeightedPartialMaxSatSynthesizer.synthesize_next(
        current=snap,
        missed=boundary,
        conflict_register=reg,
        council_report=council_locked,
    )
    assert synth_ready["next_status"] == "SYNTHESIS_LOCKED_READY"
    assert synth_ready["hard_clauses_satisfied"] is True
    assert synth_ready["oracle_gap_prevented"] is True


def test_banned_words_absence() -> None:
    banned = [
        "guaran" + "teed",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "proven universal" + "ly",
    ]
    repo_root = Path(__file__).resolve().parent.parent
    for rel in (
        "tools/cross_hemisphere_council_decide.py",
        "tools/current_missed_next_calculus.py",
        "tests/test_cross_hemisphere_council_decide.py",
    ):
        text = (repo_root / rel).read_text(encoding="utf-8").lower()
        for w in banned:
            assert w not in text, f"Forbidden word found in {rel}"


def test_cross_hemisphere_and_maxsat_mutation_boundaries() -> None:
    import ast as _ast
    import tools.cross_hemisphere_council_decide as chcd
    import tools.cross_hemisphere_epistemic_council as chec
    import tools.current_missed_next_calculus as cmnc
    from tools.cross_hemisphere_council_decide import (
        AgentDraftEnvelope,
        CouncilFusionReport,
        ModelAskQuery,
        ThreeTierAskResolutionRouter,
    )
    from tools.current_missed_next_calculus import MaxSatClause

    # 1. AST checks for __main__ and sys.path guards across all 3 modules
    for mod in (chcd, chec, cmnc):
        tree = _ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
        found_main = False
        for node in _ast.walk(tree):
            if isinstance(node, _ast.Call) and isinstance(node.func, _ast.Name) and node.func.id == "EpistemicObservation":
                kw_map = {k.arg: k.value for k in node.keywords if isinstance(k.value, _ast.Constant)}
                assert kw_map["conflict_detected"].value is True
            if isinstance(node, _ast.Call) and isinstance(node.func, _ast.Name) and node.func.id == "MaxSatClause":
                kw_map = {k.arg: k.value for k in node.keywords if isinstance(k.value, _ast.Constant)}
                if kw_map["is_hard"].value is True:
                    assert kw_map["weight_bps"].value == 10000
                    if "satisfied" in kw_map:
                        assert kw_map["satisfied"].value is True
                else:
                    assert kw_map["is_hard"].value is False
                    assert kw_map["weight_bps"].value == 90 * 100
                    assert kw_map["satisfied"].value is True
            if isinstance(node, _ast.If) and isinstance(node.test, _ast.Compare):
                if isinstance(node.test.left, _ast.Name) and node.test.left.id == "__name__":
                    assert isinstance(node.test.ops[0], _ast.Eq)
                    found_main = True
                    for sub in _ast.walk(node):
                        if isinstance(sub, _ast.Call) and isinstance(sub.func, _ast.Attribute) and sub.func.attr == "dumps":
                            kw_map = {k.arg: k.value for k in sub.keywords if isinstance(k.value, _ast.Constant)}
                            assert kw_map["indent"].value == 2 and kw_map["sort_keys"].value is True
        assert found_main is True

    for mod in (chec, cmnc):
        tree = _ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
        found_path_guard = False
        for node in _ast.walk(tree):
            if isinstance(node, _ast.If) and isinstance(node.test, _ast.Compare):
                if isinstance(node.test.left, _ast.Name) and node.test.left.id == "_REPO_ROOT":
                    assert isinstance(node.test.ops[0], _ast.NotIn)
                    found_path_guard = True
                    for sub in _ast.walk(node):
                        if isinstance(sub, _ast.Call) and isinstance(sub.func, _ast.Attribute) and sub.func.attr == "insert":
                            assert isinstance(sub.args[0], _ast.Constant) and sub.args[0].value == 0
        assert found_path_guard is True

    # 2. Execute tools/cross_hemisphere_epistemic_council.py end-to-end
    chec.test_integrated_tri_partition_architecture()
    e2e_res = chec.run_integrated_tri_partition_architecture()
    assert e2e_res["maxsat_synthesis"]["hard_clauses_count"] == 2

    # 3. Frozen dataclasses & defaults
    assert ModelAskQuery.__dataclass_params__.frozen is True  # type: ignore[attr-defined]
    assert CouncilFusionReport.__dataclass_params__.frozen is True  # type: ignore[attr-defined]
    assert MaxSatClause.__dataclass_params__.frozen is True  # type: ignore[attr-defined]
    assert MaxSatClause("c1", "HARD", True, 10000, "desc").satisfied is True

    # 4. evaluate_typed_cross_critique individual Or-branch boundaries
    base_claim = HypothesisClaim(
        "c1", "m1", "US_MODEL", "top1", "pos1", False, "ev1", 0.80
    )
    assert base_claim.confidence_bps == 8000
    crit_false_with_witness = TypedCrossCritiqueTuple(
        "cr1", "m2", "c1", "HOSTILE", False, "non-empty witness", "q1"
    )
    assert CrossHemisphereEpistemicCouncil.evaluate_typed_cross_critique(base_claim, crit_false_with_witness)[0] is False
    crit_true_blank_witness = TypedCrossCritiqueTuple(
        "cr2", "m2", "c1", "NEUTRAL", True, "   ", "q1"
    )
    assert CrossHemisphereEpistemicCouncil.evaluate_typed_cross_critique(base_claim, crit_true_blank_witness)[0] is False

    # 5. Council synthesis boundaries: exact 1 vs 2 minority override, and 0 vs 2 unverified disagreement
    router = ThreeTierAskResolutionRouter({}, lambda _: None)
    council = CrossHemisphereEpistemicCouncil(router)
    d_ver = AgentDraftEnvelope(
        "m_ver", "CHINA_MODEL", "DECIDE",
        (HypothesisClaim("c_v", "m_ver", "CHINA_MODEL", "t1", "pos_v", True, "url", 0.90),),
    )
    d_unv1 = AgentDraftEnvelope(
        "m_u1", "US_MODEL", "DECIDE",
        (HypothesisClaim("c_u1", "m_u1", "US_MODEL", "t1", "pos_u", False, "none", 0.85),),
    )
    d_unv2 = AgentDraftEnvelope(
        "m_u2", "US_MODEL", "DECIDE",
        (HypothesisClaim("c_u2", "m_u2", "US_MODEL", "t1", "pos_u", False, "none", 0.80),),
    )
    rep_1v2 = council.run_council_synthesis([d_ver, d_unv1, d_unv2])
    assert rep_1v2.oracle_gap_prevented is True
    assert len(rep_1v2.unique_minority_insights_preserved) == 1

    d_unv_alt = AgentDraftEnvelope(
        "m_u3", "US_MODEL", "DECIDE",
        (HypothesisClaim("c_u3", "m_u3", "US_MODEL", "t1", "pos_alt", False, "none", 0.95),),
    )
    rep_0v2 = council.run_council_synthesis([d_unv1, d_unv_alt])
    assert rep_0v2.oracle_gap_prevented is False
    assert rep_0v2.disagreement_rows[0]["selected_from_model"] == "m_u3"

    # Unanimous consensus row
    rep_cons = council.run_council_synthesis([d_unv1, d_unv2])
    assert rep_cons.oracle_gap_prevented is False
    assert len(rep_cons.consensus_rows) == 1

    # Signature tamper tests (sha256 mismatch and signature mismatch)
    rep_bad_sha = CouncilFusionReport(
        panel_verdict=rep_1v2.panel_verdict,
        consensus_rows=rep_1v2.consensus_rows,
        disagreement_rows=rep_1v2.disagreement_rows,
        unique_minority_insights_preserved=rep_1v2.unique_minority_insights_preserved,
        resolved_ask_records=rep_1v2.resolved_ask_records,
        developer_questions_schema=rep_1v2.developer_questions_schema,
        oracle_gap_prevented=rep_1v2.oracle_gap_prevented,
        receipt_sha256="sha256:0000",
        signature_b64=rep_1v2.signature_b64,
        public_key_b64=rep_1v2.public_key_b64,
    )
    assert CrossHemisphereEpistemicCouncil.verify_council_report_signature(rep_bad_sha) is False

    import base64 as _b64
    rep_bad_sig = CouncilFusionReport(
        panel_verdict=rep_1v2.panel_verdict,
        consensus_rows=rep_1v2.consensus_rows,
        disagreement_rows=rep_1v2.disagreement_rows,
        unique_minority_insights_preserved=rep_1v2.unique_minority_insights_preserved,
        resolved_ask_records=rep_1v2.resolved_ask_records,
        developer_questions_schema=rep_1v2.developer_questions_schema,
        oracle_gap_prevented=rep_1v2.oracle_gap_prevented,
        receipt_sha256=rep_1v2.receipt_sha256,
        signature_b64=_b64.b64encode(b"\x00" * 64).decode("ascii"),
        public_key_b64=rep_1v2.public_key_b64,
    )
    assert CrossHemisphereEpistemicCouncil.verify_council_report_signature(rep_bad_sig) is False

    # 6. CurrentCategorySnapshot, MissedBoundaryOperator, and WeightedPartialMaxSatSynthesizer exact clauses
    snap = CurrentCategorySnapshot({"loc_only": "v1", "shared": "v2"}, {"hum_only": "v3", "shared": "v2"})
    assert snap.to_dict() == {"loc_only": "v1", "shared": "v2", "hum_only": "v3"}
    mb = MissedBoundaryOperator.compute_boundary(snap)
    assert mb["unabsorbed_humanity_findings"] == ["hum_only"]
    assert mb["unique_local_moats"] == ["loc_only"]

    reg_clean = NonDilutableConflictRegister()
    council_hold = run_cross_hemisphere_council_scenario()
    assert council_hold.to_ask_question_modal_payload()["questions"][0]["is_multi_select"] is False
    synth_hold = WeightedPartialMaxSatSynthesizer.synthesize_next(snap, mb, reg_clean, council_hold)
    assert synth_hold["hard_clauses_satisfied"] is False
    assert synth_hold["next_status"] == "HOLD_UNRESOLVED_HARD_CLAUSE_OR_DEV_ASK"

    synth_ok = WeightedPartialMaxSatSynthesizer.synthesize_next(snap, mb, reg_clean, rep_cons)
    assert synth_ok["soft_weight_total_bps"] == 90 * 100
    assert synth_ok["hard_clauses_satisfied"] is True
    assert synth_ok["next_status"] == "SYNTHESIS_LOCKED_READY"


