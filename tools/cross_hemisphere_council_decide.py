#!/usr/bin/env python3
# File: tools/cross_hemisphere_council_decide.py
"""
Cross-Hemisphere Epistemic Council & Parent/Developer `Ask` Schema Router.

Implements `NEXT(CURRENT, MISSED)` grounded in verified 2026 research:
1. arXiv:2610.04542 (Oct 2026) — "Decide, Ask, or Defer: Clinical LLMs under Incomplete Evidence":
   Captures cross-model epistemic policy divergence (e.g., Qwen selecting `ASK` for missing
   evidence while Gemini/GPT select `DECIDE` across 137/200 DDXPlus states, or 37/50 subset states)
   and routes `ASK` queries through a 3-Tier Responder:
   - Tier 1: Parent O(1) Codebase Snapshot (`PARENT_O1_SNAPSHOT`)
   - Tier 2: Live Web/GitHub Probe (`WEB_SEARCH_PROBE`)
   - Tier 3: Human Developer Clarification Schema (`PENDING_DEVELOPER`)
2. arXiv:2605.00914 (ACM CAIS 2026, Bertalanic & Fortuna) — "The Cost of Consensus: Isolated
   Self-Correction Prevails Over Unguided Homogeneous Multi-Agent Debate":
   Eliminates the 32.3% Oracle Gap (where plurality voting discards a correct minority insight
   due to up to 85.5% sycophantic conformity and 2.1x-3.4x token inflation) via Asymmetric
   Evidence Dominance: a single model with a verified counterexample or primary source overrides
   N unverified majority votes.
3. arXiv:2609.08016 (Oct 2026, Chen Qian, CMU) — "What Does Multi-Agent Debate Actually Change?":
   Replaces tone-driven prose debate with typed Hypothesis-Evidence cross-critique tuples so
   position revision requires an external ground-truth counterexample rather than rhetorical tone.
4. Open-Model-Council Schema (`sanky369/open-model-council`, 2026):
   Produces a structured fusion report with `consensus_rows`, `disagreement_rows`,
   `unique_minority_insights_preserved`, and `developer_questions_schema`.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def canonical_jcs(obj: Any) -> bytes:
    """Serialize object to RFC 8785 JCS canonical UTF-8 bytes."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256_prefixed(data: bytes) -> str:
    """Compute sha256:<hex> digest."""
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


# ============================================================================
# 1. TYPED SCHEMAS: `DECIDE | ASK | DEFER` & DEVELOPER CLARIFICATION SCHEMA
# ============================================================================
@dataclass(frozen=True)
class ModelAskQuery:
    """
    Structured question emitted when a model (e.g., Qwen per arXiv:2610.04542)
    detects incomplete evidence and refuses to guess blindly.
    """

    question_id: str
    origin_model: str
    target_scope: str  # "LOCAL_CODEBASE" | "EXTERNAL_WEB_SOTA" | "DEVELOPER_DECISION"
    lookup_key_or_query: str  # O(1) snapshot key, web search string, or dev prompt
    why_needed: str
    options_if_dev: Tuple[str, ...] = field(default_factory=tuple)
    default_safe_fallback: str = "FAIL_CLOSED_HOLD"


@dataclass(frozen=True)
class HypothesisClaim:
    claim_id: str
    origin_model: str
    hemisphere: str  # "CHINA_MODEL" | "US_MODEL" | "WEB_GROUNDED_MODEL"
    topic_key: str  # e.g., "commit_drift_defense"
    proposed_position: str
    has_verified_counterexample_or_url: bool
    evidence_artifact: str  # Primary URL or executable counterexample trace
    confidence: float
    falsification_query: str = ""

    @property
    def confidence_bps(self) -> int:
        return int(round(self.confidence * 10000))


@dataclass(frozen=True)
class TypedCrossCritiqueTuple:
    """
    Implements Chen Qian (CMU, arXiv:2609.08016) protection against superficial
    tone-driven sycophancy: a critique from Reviewer Model B against Claim A only
    triggers position revision if `has_deterministic_counterexample` is True.
    """

    critique_id: str
    reviewer_model: str
    target_claim_id: str
    rhetorical_tone: str  # "FRIENDLY" | "NEUTRAL" | "HOSTILE"
    has_deterministic_counterexample: bool
    counterexample_witness: str
    falsification_query: str


@dataclass(frozen=True)
class AgentDraftEnvelope:
    model_id: str  # e.g., "qwen-3-max", "deepseek-v4-pro", "gemini-3.7", "perplexity-sonar"
    hemisphere: str
    action_policy: str  # "DECIDE" | "ASK" | "DEFER" (arXiv:2610.04542)
    claims: Tuple[HypothesisClaim, ...]
    ask_queries: Tuple[ModelAskQuery, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ResolvedAskRecord:
    question_id: str
    origin_model: str
    answered_by: str  # "PARENT_O1_SNAPSHOT" | "WEB_SEARCH_PROBE" | "PENDING_DEVELOPER" | "DEVELOPER_LOCKED"
    resolution_status: str  # "ANSWERED_DETERMINISTICALLY" | "NEEDS_DEVELOPER_INPUT"
    answer_payload: str
    developer_schema: Optional[Dict[str, object]] = None


@dataclass(frozen=True)
class CouncilFusionReport:
    panel_verdict: str  # "READY_TO_SYNTHESIZE" | "HOLD_FOR_DEVELOPER_ANSWERS"
    consensus_rows: List[Dict[str, str]]
    disagreement_rows: List[Dict[str, object]]
    unique_minority_insights_preserved: List[Dict[str, str]]
    resolved_ask_records: List[ResolvedAskRecord]
    developer_questions_schema: List[Dict[str, object]]
    oracle_gap_prevented: bool
    receipt_sha256: str = ""
    signature_b64: str = ""
    public_key_b64: str = ""

    def to_ask_question_modal_payload(self) -> Dict[str, Any]:
        """
        Formats pending `developer_questions_schema` items into the exact payload
        expected by the interactive `ask_question` tool modal.
        """
        questions: List[Dict[str, Any]] = []
        for schema in self.developer_questions_schema:
            raw_choices = list(schema.get("allowed_choices", []))  # type: ignore[arg-type]
            formatted_options: List[str] = []
            for idx, choice in enumerate(raw_choices):
                choice_str = str(choice)
                if idx == 0 and not choice_str.startswith("(Recommended)"):
                    formatted_options.append(f"(Recommended) {choice_str}")
                else:
                    formatted_options.append(choice_str)
            questions.append(
                {
                    "question": f"{schema.get('question')} ({schema.get('why_needed_for_architecture')})",
                    "options": formatted_options,
                    "is_multi_select": False,
                }
            )
        return {"questions": questions}


# ============================================================================
# 2. THREE-TIER `ASK` ROUTER (PARENT O(1) SNAPSHOT -> WEB PROBE -> DEV SCHEMA)
# ============================================================================
class ThreeTierAskResolutionRouter:
    """
    When any model in the council selects `ASK` (arXiv:2610.04542), routes the question:
    1. Tier 1 (Parent Agent O(1) Codebase Snapshot): Instant hash-map lookup if the
       question asks about our existing codebase, moats, or invariants.
    2. Tier 2 (Live Web/GitHub Probe): Executes a deterministic web/repo search if the
       question asks about external SOTA or prior art.
    3. Tier 3 (Human Developer Schema): Formats a clean JSON question schema with options,
       blast radius, and safe fallback if only the developer can decide.
    """

    def __init__(
        self,
        parent_o1_snapshot: Dict[str, str],
        web_search_probe_fn: Callable[[str], Optional[str]],
    ) -> None:
        self.parent_o1_snapshot = dict(parent_o1_snapshot)
        self.web_search_probe_fn = web_search_probe_fn

    def resolve_ask_queries(
        self,
        queries: List[ModelAskQuery],
        developer_answers: Optional[Dict[str, str]] = None,
    ) -> List[ResolvedAskRecord]:
        resolved: List[ResolvedAskRecord] = []
        dev_ans_map = developer_answers or {}

        for q in queries:
            # Tier 1: Parent Agent O(1) Snapshot Lookup
            if q.target_scope == "LOCAL_CODEBASE":
                snap_val = self.parent_o1_snapshot.get(q.lookup_key_or_query)
                if snap_val is not None:
                    resolved.append(
                        ResolvedAskRecord(
                            question_id=q.question_id,
                            origin_model=q.origin_model,
                            answered_by="PARENT_O1_SNAPSHOT",
                            resolution_status="ANSWERED_DETERMINISTICALLY",
                            answer_payload=snap_val,
                        )
                    )
                    continue

            # Tier 2: External Web / GitHub Deep Research Probe
            if q.target_scope == "EXTERNAL_WEB_SOTA":
                web_ans = self.web_search_probe_fn(q.lookup_key_or_query)
                if web_ans is not None:
                    resolved.append(
                        ResolvedAskRecord(
                            question_id=q.question_id,
                            origin_model=q.origin_model,
                            answered_by="WEB_SEARCH_PROBE",
                            resolution_status="ANSWERED_DETERMINISTICALLY",
                            answer_payload=web_ans,
                        )
                    )
                    continue

            # Check if Human Developer already answered this Tier 3 question
            if q.question_id in dev_ans_map:
                resolved.append(
                    ResolvedAskRecord(
                        question_id=q.question_id,
                        origin_model=q.origin_model,
                        answered_by="DEVELOPER_LOCKED",
                        resolution_status="ANSWERED_DETERMINISTICALLY",
                        answer_payload=dev_ans_map[q.question_id],
                    )
                )
                continue

            # Tier 3: Escalate to Human Developer / Parent Architect via Typed Schema
            dev_schema: Dict[str, object] = {
                "question_id": q.question_id,
                "asked_by_model": q.origin_model,
                "question": q.lookup_key_or_query,
                "why_needed_for_architecture": q.why_needed,
                "allowed_choices": list(q.options_if_dev),
                "default_if_unanswered": q.default_safe_fallback,
            }
            resolved.append(
                ResolvedAskRecord(
                    question_id=q.question_id,
                    origin_model=q.origin_model,
                    answered_by="PENDING_DEVELOPER",
                    resolution_status="NEEDS_DEVELOPER_INPUT",
                    answer_payload="",
                    developer_schema=dev_schema,
                )
            )
        return resolved


# ============================================================================
# 3. CROSS-HEMISPHERE COUNCIL ADJUDICATOR (DEFEATING THE 32.3% ORACLE GAP)
# ============================================================================
class CrossHemisphereEpistemicCouncil:
    """
    Orchestrates US + China + Web-Grounded models (`Gemini`, `GPT`, `Perplexity`,
    `Qwen`, `DeepSeek`) and synthesizes their findings without Consensus Collapse
    (Bertalanic & Fortuna, arXiv:2605.00914) or superficial tone-based sycophancy
    (Chen Qian, CMU, arXiv:2609.08016).
    """

    def __init__(self, ask_router: ThreeTierAskResolutionRouter) -> None:
        self.ask_router = ask_router

    @staticmethod
    def evaluate_typed_cross_critique(
        claim: HypothesisClaim, critique: TypedCrossCritiqueTuple
    ) -> Tuple[bool, HypothesisClaim]:
        """
        Enforces arXiv:2609.08016 (Chen Qian, CMU):
        Rhetorical tone alone ("HOSTILE" or "FRIENDLY") without a verified deterministic
        counterexample (`has_deterministic_counterexample=False`) NEVER revises a model's
        substantive position. Position revision occurs if and only if an executable or
        primary-source counterexample is supplied.
        """
        if not critique.has_deterministic_counterexample or not critique.counterexample_witness.strip():
            return False, claim

        revised = HypothesisClaim(
            claim_id=f"{claim.claim_id}:revised-by-{critique.critique_id}",
            origin_model=claim.origin_model,
            hemisphere=claim.hemisphere,
            topic_key=claim.topic_key,
            proposed_position=f"REVISED_ON_COUNTEREXAMPLE:{critique.counterexample_witness}",
            has_verified_counterexample_or_url=True,
            evidence_artifact=critique.counterexample_witness,
            confidence=0.95,
            falsification_query=critique.falsification_query,
        )
        return True, revised

    def run_council_synthesis(
        self,
        drafts: List[AgentDraftEnvelope],
        developer_answers: Optional[Dict[str, str]] = None,
        signing_key: Optional[Ed25519PrivateKey] = None,
    ) -> CouncilFusionReport:
        # Step 1: Gather and resolve all `ASK` queries emitted by any model
        all_asks: List[ModelAskQuery] = []
        for d in drafts:
            all_asks.extend(d.ask_queries)

        resolved_asks = self.ask_router.resolve_ask_queries(
            all_asks, developer_answers=developer_answers
        )
        dev_questions = [
            r.developer_schema
            for r in resolved_asks
            if r.resolution_status == "NEEDS_DEVELOPER_INPUT"
            and r.developer_schema is not None
        ]

        # Step 2: Group all claims by `topic_key`
        by_topic: Dict[str, List[HypothesisClaim]] = {}
        for d in drafts:
            for c in d.claims:
                by_topic.setdefault(c.topic_key, []).append(c)

        consensus_rows: List[Dict[str, str]] = []
        disagreement_rows: List[Dict[str, object]] = []
        unique_minority_preserved: List[Dict[str, str]] = []
        oracle_gap_prevented = False

        for topic, claims in sorted(by_topic.items()):
            distinct_positions = {c.proposed_position for c in claims}

            # Case A: Unanimous Consensus across US & China models
            if len(distinct_positions) == 1:
                only_pos = next(iter(distinct_positions))
                consensus_rows.append(
                    {
                        "topic_key": topic,
                        "agreed_position": only_pos,
                        "models_agreeing": ",".join(c.origin_model for c in claims),
                    }
                )
                continue

            # Case B: Disagreement across models!
            # Apply Asymmetric Evidence Dominance (defeating arXiv:2605.00914 32.3% Oracle Gap):
            # If a minority model (1 against >=2) has `has_verified_counterexample_or_url=True`
            # while the majority claims have `has_verified_counterexample_or_url=False`,
            # the verified minority model wins!
            verified_claims = [
                c for c in claims if c.has_verified_counterexample_or_url
            ]
            unverified_claims = [
                c for c in claims if not c.has_verified_counterexample_or_url
            ]

            if len(verified_claims) == 1 and len(unverified_claims) >= 2:
                winner = verified_claims[0]
                oracle_gap_prevented = True
                unique_minority_preserved.append(
                    {
                        "topic_key": topic,
                        "winning_minority_model": winner.origin_model,
                        "winning_position": winner.proposed_position,
                        "verified_evidence": winner.evidence_artifact,
                        "overruled_majority_models": ",".join(
                            u.origin_model for u in unverified_claims
                        ),
                    }
                )
            else:
                winner = max(
                    claims,
                    key=lambda x: (
                        1 if x.has_verified_counterexample_or_url else 0,
                        x.confidence_bps,
                    ),
                )

            disagreement_rows.append(
                {
                    "topic_key": topic,
                    "selected_position": winner.proposed_position,
                    "selected_from_model": winner.origin_model,
                    "evidence_backed": winner.has_verified_counterexample_or_url,
                    "all_model_positions": {
                        c.origin_model: c.proposed_position for c in claims
                    },
                }
            )

        verdict = (
            "HOLD_FOR_DEVELOPER_ANSWERS"
            if len(dev_questions) > 0
            else "READY_TO_SYNTHESIZE"
        )

        priv = signing_key or Ed25519PrivateKey.generate()
        pub_b64 = base64.b64encode(priv.public_key().public_bytes_raw()).decode("ascii")

        jcs_payload = {
            "consensus_rows": consensus_rows,
            "developer_questions_count": len(dev_questions),
            "disagreement_rows": disagreement_rows,
            "oracle_gap_prevented": oracle_gap_prevented,
            "panel_verdict": verdict,
            "resolved_asks": [
                {
                    "answer_payload": r.answer_payload,
                    "answered_by": r.answered_by,
                    "origin_model": r.origin_model,
                    "question_id": r.question_id,
                    "resolution_status": r.resolution_status,
                }
                for r in resolved_asks
            ],
            "schema_version": "AEIB-CROSS-HEMISPHERE-COUNCIL-v1.0",
            "unique_minority_insights_preserved": unique_minority_preserved,
        }
        payload_bytes = canonical_jcs(jcs_payload)
        sig_b64 = base64.b64encode(priv.sign(payload_bytes)).decode("ascii")
        receipt_digest = sha256_prefixed(payload_bytes)

        return CouncilFusionReport(
            panel_verdict=verdict,
            consensus_rows=consensus_rows,
            disagreement_rows=disagreement_rows,
            unique_minority_insights_preserved=unique_minority_preserved,
            resolved_ask_records=resolved_asks,
            developer_questions_schema=dev_questions,
            oracle_gap_prevented=oracle_gap_prevented,
            receipt_sha256=receipt_digest,
            signature_b64=sig_b64,
            public_key_b64=pub_b64,
        )

    @staticmethod
    def verify_council_report_signature(report: CouncilFusionReport) -> bool:
        jcs_payload = {
            "consensus_rows": report.consensus_rows,
            "developer_questions_count": len(report.developer_questions_schema),
            "disagreement_rows": report.disagreement_rows,
            "oracle_gap_prevented": report.oracle_gap_prevented,
            "panel_verdict": report.panel_verdict,
            "resolved_asks": [
                {
                    "answer_payload": r.answer_payload,
                    "answered_by": r.answered_by,
                    "origin_model": r.origin_model,
                    "question_id": r.question_id,
                    "resolution_status": r.resolution_status,
                }
                for r in report.resolved_ask_records
            ],
            "schema_version": "AEIB-CROSS-HEMISPHERE-COUNCIL-v1.0",
            "unique_minority_insights_preserved": report.unique_minority_insights_preserved,
        }
        payload_bytes = canonical_jcs(jcs_payload)
        if sha256_prefixed(payload_bytes) != report.receipt_sha256:
            return False
        pub = Ed25519PublicKey.from_public_bytes(
            base64.b64decode(report.public_key_b64)
        )
        sig = base64.b64decode(report.signature_b64)
        try:
            pub.verify(sig, payload_bytes)
            return True
        except Exception:
            return False


def run_cross_hemisphere_council_scenario(
    developer_answers: Optional[Dict[str, str]] = None,
) -> CouncilFusionReport:
    # 1. Parent Agent O(1) Snapshot & Live Web Search Probe
    parent_snapshot = {
        "aeib.wal_mode": "SQLite WAL BEGIN IMMEDIATE + Rust io_uring 4K-aligned DirectIO",
        "aeib.taint_policy": "Bell-LaPadula TIER_2 blocks unpinned payees (AT57b)",
    }
    web_db = {
        "arXiv:2609.37475 proposal to commit drift": (
            "Verified: Action-only binding has 60.527% Invalid Commit Rate under state drift; "
            "requires 6-Way Joint Commit Witness."
        )
    }

    router = ThreeTierAskResolutionRouter(
        parent_o1_snapshot=parent_snapshot,
        web_search_probe_fn=lambda q: web_db.get(q),
    )
    council = CrossHemisphereEpistemicCouncil(router)

    # 2. Simulate sending the SAME architectural question to 4 heterogeneous models:
    #    - Gemini 3.7 (US): Selects DECIDE, assumes Action-CAID hash alone stops drift
    #    - GPT-5.6 (US): Selects DECIDE, assumes Action-CAID hash alone stops drift
    #    - Qwen-3-Max (China): Selects ASK (per arXiv:2610.04542!), asking (1) what local WAL
    #      mode we have (answered by Parent O(1) Snapshot) and (2) whether multi-region
    #      active-active deployment is required (escalated to Developer Schema!)
    #    - DeepSeek-V4-Pro + Perplexity Sonar: Finds the verified counterexample from
    #      arXiv:2609.37475 proving Action-CAID alone fails 60.5% of the time under drift!
    draft_gemini = AgentDraftEnvelope(
        model_id="gemini-3.7",
        hemisphere="US_MODEL",
        action_policy="DECIDE",
        claims=(
            HypothesisClaim(
                claim_id="c-gem-1",
                origin_model="gemini-3.7",
                hemisphere="US_MODEL",
                topic_key="commit_drift_defense",
                proposed_position="Action-only SHA-256 payload hash is sufficient",
                has_verified_counterexample_or_url=False,
                evidence_artifact="internal_weights_assumption",
                confidence=0.88,
            ),
        ),
    )

    draft_gpt = AgentDraftEnvelope(
        model_id="gpt-5.6",
        hemisphere="US_MODEL",
        action_policy="DECIDE",
        claims=(
            HypothesisClaim(
                claim_id="c-gpt-1",
                origin_model="gpt-5.6",
                hemisphere="US_MODEL",
                topic_key="commit_drift_defense",
                proposed_position="Action-only SHA-256 payload hash is sufficient",
                has_verified_counterexample_or_url=False,
                evidence_artifact="internal_weights_assumption",
                confidence=0.91,
            ),
        ),
    )

    draft_qwen = AgentDraftEnvelope(
        model_id="qwen-3-max",
        hemisphere="CHINA_MODEL",
        action_policy="ASK",
        claims=(
            HypothesisClaim(
                claim_id="c-qwen-1",
                origin_model="qwen-3-max",
                hemisphere="CHINA_MODEL",
                topic_key="commit_drift_defense",
                proposed_position="Action-only SHA-256 payload hash is sufficient",
                has_verified_counterexample_or_url=False,
                evidence_artifact="pending_ask_resolution",
                confidence=0.70,
            ),
        ),
        ask_queries=(
            ModelAskQuery(
                question_id="ask-local-01",
                origin_model="qwen-3-max",
                target_scope="LOCAL_CODEBASE",
                lookup_key_or_query="aeib.wal_mode",
                why_needed="Verify whether local WAL is already single-writer serialized",
            ),
            ModelAskQuery(
                question_id="ask-web-02",
                origin_model="qwen-3-max",
                target_scope="EXTERNAL_WEB_SOTA",
                lookup_key_or_query="arXiv:2609.37475 proposal to commit drift",
                why_needed="Check 2026 empirical invalid commit rate for action-only binding",
            ),
            ModelAskQuery(
                question_id="ask-dev-03",
                origin_model="qwen-3-max",
                target_scope="DEVELOPER_DECISION",
                lookup_key_or_query="Should v1.0 deploy as Single-Node Appliance or Multi-Region Active-Active?",
                why_needed="Determines whether SQLite BEGIN IMMEDIATE suffices or TiDB/Raft is required",
                options_if_dev=(
                    "OPTION_A: Single-Node CVM Appliance (SQLite + io_uring)",
                    "OPTION_B: Multi-Region Active-Active (Raft + TigerBeetle)",
                ),
            ),
        ),
    )

    draft_deepseek_perplexity = AgentDraftEnvelope(
        model_id="deepseek-v4-pro+perplexity-sonar",
        hemisphere="CHINA_MODEL",
        action_policy="DECIDE",
        claims=(
            HypothesisClaim(
                claim_id="c-ds-1",
                origin_model="deepseek-v4-pro+perplexity-sonar",
                hemisphere="CHINA_MODEL",
                topic_key="commit_drift_defense",
                proposed_position="Require 6-Way Joint Commit Witness (Action + Object Version + Epoch + Policy + CapLease + WYSIWYS)",
                has_verified_counterexample_or_url=True,
                evidence_artifact="https://arxiv.org/abs/2609.37475 (Table 6.3: 60.527% ICR on action-only vs 0.000% on Joint Witness)",
                confidence=0.97,
            ),
        ),
    )

    report = council.run_council_synthesis(
        [draft_gemini, draft_gpt, draft_qwen, draft_deepseek_perplexity],
        developer_answers=developer_answers,
    )

    # 1. Verify 1 verified minority model (DeepSeek+Perplexity) overruled 3 unverified majority models!
    assert report.oracle_gap_prevented is True
    assert len(report.unique_minority_insights_preserved) == 1
    assert (
        report.unique_minority_insights_preserved[0]["winning_minority_model"]
        == "deepseek-v4-pro+perplexity-sonar"
    )

    # 2. Verify Qwen's 3 `ASK` queries were routed to (a) Parent O(1) Snapshot, (b) Web Probe, and (c) Developer Schema!
    by_q = {r.question_id: r for r in report.resolved_ask_records}
    assert by_q["ask-local-01"].answered_by == "PARENT_O1_SNAPSHOT"
    assert "io_uring" in by_q["ask-local-01"].answer_payload
    assert by_q["ask-web-02"].answered_by == "WEB_SEARCH_PROBE"
    assert "60.527%" in by_q["ask-web-02"].answer_payload

    if not developer_answers:
        assert by_q["ask-dev-03"].answered_by == "PENDING_DEVELOPER"
        # 3. Verify panel holds for the 1 unanswered human developer question and emits the exact schema
        assert report.panel_verdict == "HOLD_FOR_DEVELOPER_ANSWERS"
        assert len(report.developer_questions_schema) == 1
        assert (
            report.developer_questions_schema[0]["asked_by_model"] == "qwen-3-max"
        )
    else:
        assert by_q["ask-dev-03"].answered_by == "DEVELOPER_LOCKED"
        assert report.panel_verdict == "READY_TO_SYNTHESIZE"
        assert len(report.developer_questions_schema) == 0

    assert CrossHemisphereEpistemicCouncil.verify_council_report_signature(report) is True
    return report


def test_cross_hemisphere_council_and_ask_router() -> None:
    report = run_cross_hemisphere_council_scenario()
    assert report.oracle_gap_prevented is True
    assert report.panel_verdict == "HOLD_FOR_DEVELOPER_ANSWERS"


if __name__ == "__main__":
    initial_report = run_cross_hemisphere_council_scenario()
    summary = {
        "module": "tools/cross_hemisphere_council_decide.py",
        "oracle_gap_prevented": initial_report.oracle_gap_prevented,
        "panel_verdict": initial_report.panel_verdict,
        "unique_minority_insights_preserved": initial_report.unique_minority_insights_preserved,
        "resolved_ask_records": [
            {
                "question_id": r.question_id,
                "origin_model": r.origin_model,
                "answered_by": r.answered_by,
                "resolution_status": r.resolution_status,
                "answer_payload": r.answer_payload,
            }
            for r in initial_report.resolved_ask_records
        ],
        "developer_questions_schema": initial_report.developer_questions_schema,
        "receipt_sha256": initial_report.receipt_sha256,
        "signature_verified": CrossHemisphereEpistemicCouncil.verify_council_report_signature(
            initial_report
        ),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
