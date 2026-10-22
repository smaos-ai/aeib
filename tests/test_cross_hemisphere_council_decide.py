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
