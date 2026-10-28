"""
Verification and Mutation-Adequacy Test Suite for:
- Part I: 6-State Model Integrity Layer, Signed ModelDecisionEnvelopeV1, AtomicClaimRouter,
  and FiveLayerModelIntegrityMonitor
- Part II: Bio-Agentic Execution Boundary (GenomicScittReceiptEngine, WetLabJidokaStateMachine,
  BioStochasticAcidReagentEscrow, and 15-Step Enzymatic Cascade Bio-ChaosBench).
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import replace

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.jcs_canonicalizer import encode_jcs
from src.model_integrity_layer_and_bio_aeib_gate import (
    AtomicClaimEvidence,
    AtomicClaimRouter,
    BioStochasticAcidReagentEscrow,
    ClaimCategory,
    FiveLayerModelIntegrityMonitor,
    GenomicScittReceiptEngine,
    ModelDecisionEnvelopeV1,
    ModelIntegrityState,
    SupportLevel,
    WetLabJidokaStateMachine,
    run_bio_chaos_benchmark,
)


def _independent_sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _make_sample_claim(
    source_doc: str,
    *,
    claim_id: str = "claim-1",
    claim_type: ClaimCategory = ClaimCategory.FACTUAL,
    support_level: SupportLevel = SupportLevel.DIRECT,
    source_uri: str = "local://sources/apoe_gencode_v46.txt",
    source_digest_override: str | None = None,
    start_char: int = 0,
    end_char: int = 27,
    cited_span_override: str | None = None,
) -> AtomicClaimEvidence:
    digest = (
        source_digest_override
        if source_digest_override is not None
        else _independent_sha256_text(source_doc)
    )
    span = cited_span_override if cited_span_override is not None else source_doc[start_char:end_char]
    return AtomicClaimEvidence(
        claim_id=claim_id,
        claim_type=claim_type,
        claim_text="APOE MANE Select is ENST00000252486.9 on chr19.",
        source_uri=source_uri,
        source_digest=digest,
        start_char=start_char,
        end_char=end_char,
        cited_span_text=span,
        support_level=support_level,
    )


def _make_signed_envelope(
    priv_key: Ed25519PrivateKey,
    claims: list[AtomicClaimEvidence],
    *,
    retrieval_digest: str = "sha256:ret-apoe-01",
    uncertainty_entropy: float = 0.08,
    calibrated: bool = True,
    input_taint_tier: str = "TIER_0_TRUSTED_SYSTEM",
    inherited_taint: bool = False,
    capability_expansion_requested: bool = False,
) -> ModelDecisionEnvelopeV1:
    return ModelDecisionEnvelopeV1.sign_envelope(
        decision_id="dec-2026-10-24-001",
        timestamp_ns=1792836000000000000,
        model_id="gemini-2.5-pro-verifier",
        model_version="2026-10",
        prompt_text="Verify APOE MANE Select transcript and ABL1 domain boundaries.",
        response_text="APOE MANE Select is ENST00000252486.9; ABL1 rigid domain is 75-512.",
        context_text="GENCODE v46 + AlphaFold DB v6 P00520",
        retrieval_digest=retrieval_digest,
        evidence=claims,
        uncertainty_method="semantic_cluster_entropy",
        uncertainty_entropy=uncertainty_entropy,
        calibration_dataset="bio-aeib-golden-v1",
        calibrated=calibrated,
        input_taint_tier=input_taint_tier,
        inherited_taint=inherited_taint,
        capability_expansion_requested=capability_expansion_requested,
        policy_id="aeib-model-integrity-v1",
        policy_digest="sha256:pol-001",
        decision="PROPOSE_ACTION",
        required_checks=["source_span_check", "bio_admissibility_screen"],
        key_id="ed25519-model-gateway-01",
        signer_private_key=priv_key,
    )


def test_decision_envelope_signing_and_tamper_rejection() -> None:
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    source_doc = "ENST00000252486.9 chr19:44905795-44909393 APOE MANE Select"
    claim = _make_sample_claim(source_doc)
    env = _make_signed_envelope(priv, [claim], uncertainty_entropy=0.08123456)

    assert env.decision_envelope_version == "1"
    assert env.verify_signature(pub) is True
    with pytest.raises(AttributeError):
        env.decision = "ALLOW"  # type: ignore[misc]
    stmt = env.statement_dict()
    assert stmt["model_id"] == "gemini-2.5-pro-verifier"
    assert stmt["evidence"][0]["claim_id"] == "claim-1"
    assert stmt["evidence"][0]["support_level"] == "DIRECT"
    assert stmt["uncertainty"]["entropy_val"] == 0.081235

    # Tampering with uncertainty_entropy or signature_b64 must fail closed
    tampered_env = replace(env, uncertainty_entropy=0.99)
    with pytest.raises(ValueError, match="HALT_INVALID_DECISION_ENVELOPE_SIGNATURE"):
        tampered_env.verify_signature(pub)

    wrong_pub = Ed25519PrivateKey.generate().public_key()
    with pytest.raises(ValueError, match="HALT_INVALID_DECISION_ENVELOPE_SIGNATURE"):
        env.verify_signature(wrong_pub)


def test_atomic_claim_router_all_categories_and_span_validation() -> None:
    source_doc = "ENST00000252486.9 chr19:44905795-44909393 APOE MANE Select"
    uri = "local://sources/apoe_gencode_v46.txt"
    pinned = {uri: source_doc}

    # Empty claim set fails closed
    empty_res = AtomicClaimRouter.verify_claims_against_sources([], pinned)
    assert empty_res["all_supported"] is False
    assert empty_res["unsupported_claim_ids"] == ["EMPTY_CLAIM_SET"]

    # All 6 categories with valid span
    all_cat_claims = [
        _make_sample_claim(source_doc, claim_id=f"c-{cat.value}", claim_type=cat)
        for cat in ClaimCategory
    ]
    valid_res = AtomicClaimRouter.verify_claims_against_sources(all_cat_claims, pinned)
    assert valid_res["all_supported"] is True
    assert valid_res["unsupported_claim_ids"] == []
    assert valid_res["stale_claim_ids"] == []
    assert valid_res["routes"]["c-FACTUAL"] == "source_span_check"
    assert valid_res["routes"]["c-MATHEMATICAL"] == "deterministic_math_checker"
    assert valid_res["routes"]["c-CODE_BEHAVIOR"] == "compile_and_test"
    assert valid_res["routes"]["c-SECURITY_PROPERTY"] == "policy_and_adversarial_test"
    assert valid_res["routes"]["c-BIOLOGICAL_DESIGN"] == "bio_admissibility_screen"
    assert valid_res["routes"]["c-OPEN_WORLD"] == "consistency_and_abstention"

    # SupportLevel.NONE, missing URI, stale digest, bad bounds, and mismatched span slice
    bad_claims = [
        _make_sample_claim(source_doc, claim_id="c-none", support_level=SupportLevel.NONE),
        _make_sample_claim(source_doc, claim_id="c-missing-uri", source_uri="local://missing"),
        _make_sample_claim(source_doc, claim_id="c-stale", source_digest_override="sha256:0000"),
        _make_sample_claim(source_doc, claim_id="c-neg-start", start_char=-1, end_char=5, cited_span_override="ENST0"),
        _make_sample_claim(source_doc, claim_id="c-over-end", start_char=0, end_char=999, cited_span_override="ENST0"),
        _make_sample_claim(source_doc, claim_id="c-inverted", start_char=10, end_char=10, cited_span_override=""),
        _make_sample_claim(source_doc, claim_id="c-mismatch-text", start_char=0, end_char=10, cited_span_override="WRONG_SPAN"),
    ]
    bad_res = AtomicClaimRouter.verify_claims_against_sources(bad_claims, pinned)
    assert bad_res["all_supported"] is False
    assert bad_res["stale_claim_ids"] == ["c-stale"]
    assert bad_res["unsupported_claim_ids"] == [
        "c-none",
        "c-missing-uri",
        "c-neg-start",
        "c-over-end",
        "c-inverted",
        "c-mismatch-text",
    ]


def test_five_layer_model_integrity_monitor_all_six_states_and_calibration() -> None:
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    source_doc = "ENST00000252486.9 chr19:44905795-44909393 APOE MANE Select"
    uri = "local://sources/apoe_gencode_v46.txt"
    pinned = {uri: source_doc}
    claim = _make_sample_claim(source_doc)
    env = _make_signed_envelope(priv, [claim])

    # Entropy helper checks
    assert FiveLayerModelIntegrityMonitor.compute_shannon_entropy([]) == 0.0
    assert FiveLayerModelIntegrityMonitor.compute_shannon_entropy([0.0, -1.0]) == 0.0
    assert FiveLayerModelIntegrityMonitor.compute_shannon_entropy([0.25, 0.25, 0.25, 0.25]) == pytest.approx(2.0)

    # 1. VERIFIED state -> ALLOW for CODE_GENERATION, ESCALATE_REQUIRES_HUMAN_STEP_UP for PAYMENT_OR_IRREVERSIBLE
    res_verified = FiveLayerModelIntegrityMonitor.evaluate_proposal(
        envelope=env,
        signer_public_key=pub,
        pinned_sources_by_uri=pinned,
        known_retrieval_digests=["sha256:ret-apoe-01"],
        endpoint_reachable=True,
        observed_latency_units=120,
        max_latency_ceiling_units=500,
        observed_tokens=400,
        max_token_budget=2000,
        golden_tasks_passed=20,
        golden_tasks_total=20,
        attention_weights=[0.25, 0.25, 0.25, 0.25],
        attention_entropy_band=(1.0, 2.5),
        recent_tool_call_window=["fetch_gencode", "verify_span"],
        deterministic_verifier_passed=True,
        action_category="CODE_GENERATION",
    )
    assert res_verified["integrity_state"] == ModelIntegrityState.VERIFIED
    assert res_verified["policy_action"] == "ALLOW"
    assert res_verified["reasons"] == []

    res_irreversible_no_human = FiveLayerModelIntegrityMonitor.evaluate_proposal(
        envelope=env,
        signer_public_key=pub,
        pinned_sources_by_uri=pinned,
        known_retrieval_digests=["sha256:ret-apoe-01"],
        endpoint_reachable=True,
        observed_latency_units=120,
        max_latency_ceiling_units=500,
        observed_tokens=400,
        max_token_budget=2000,
        golden_tasks_passed=20,
        golden_tasks_total=20,
        attention_weights=[0.25, 0.25, 0.25, 0.25],
        attention_entropy_band=(1.0, 2.5),
        recent_tool_call_window=["fetch_gencode"],
        deterministic_verifier_passed=True,
        action_category="PAYMENT_OR_IRREVERSIBLE",
        human_step_up_present=False,
    )
    assert res_irreversible_no_human["integrity_state"] == ModelIntegrityState.VERIFIED
    assert res_irreversible_no_human["policy_action"] == "ESCALATE_REQUIRES_HUMAN_STEP_UP"

    # 2. PROVISIONAL state (uncalibrated model) -> ALLOW_PROVISIONAL_READ_ONLY for READ_ONLY_LOW_RISK, ESCALATE otherwise
    env_uncal = _make_signed_envelope(priv, [claim], calibrated=False)
    res_prov_read = FiveLayerModelIntegrityMonitor.evaluate_proposal(
        envelope=env_uncal,
        signer_public_key=pub,
        pinned_sources_by_uri=pinned,
        known_retrieval_digests=["sha256:ret-apoe-01"],
        endpoint_reachable=True,
        observed_latency_units=100,
        max_latency_ceiling_units=500,
        observed_tokens=300,
        max_token_budget=2000,
        golden_tasks_passed=20,
        golden_tasks_total=20,
        attention_weights=[0.25, 0.25, 0.25, 0.25],
        attention_entropy_band=(1.0, 2.5),
        recent_tool_call_window=["read_doc"],
        deterministic_verifier_passed=True,
        action_category="READ_ONLY_LOW_RISK",
    )
    assert res_prov_read["integrity_state"] == ModelIntegrityState.PROVISIONAL
    assert res_prov_read["policy_action"] == "ALLOW_PROVISIONAL_READ_ONLY"

    res_prov_write = FiveLayerModelIntegrityMonitor.evaluate_proposal(
        envelope=env_uncal,
        signer_public_key=pub,
        pinned_sources_by_uri=pinned,
        known_retrieval_digests=["sha256:ret-apoe-01"],
        endpoint_reachable=True,
        observed_latency_units=100,
        max_latency_ceiling_units=500,
        observed_tokens=300,
        max_token_budget=2000,
        golden_tasks_passed=20,
        golden_tasks_total=20,
        attention_weights=[0.25, 0.25, 0.25, 0.25],
        attention_entropy_band=(1.0, 2.5),
        recent_tool_call_window=["read_doc"],
        deterministic_verifier_passed=True,
        action_category="EXTERNAL_TOOL_CALL",
    )
    assert res_prov_write["integrity_state"] == ModelIntegrityState.PROVISIONAL
    assert res_prov_write["policy_action"] == "ESCALATE"

    # 3. UNKNOWN state (unbound retrieval digest) -> ESCALATE
    res_unknown = FiveLayerModelIntegrityMonitor.evaluate_proposal(
        envelope=env,
        signer_public_key=pub,
        pinned_sources_by_uri=pinned,
        known_retrieval_digests=["sha256:different-digest"],
        endpoint_reachable=True,
        observed_latency_units=100,
        max_latency_ceiling_units=500,
        observed_tokens=300,
        max_token_budget=2000,
        golden_tasks_passed=20,
        golden_tasks_total=20,
        attention_weights=[0.25, 0.25, 0.25, 0.25],
        attention_entropy_band=(1.0, 2.5),
        recent_tool_call_window=["read_doc"],
        deterministic_verifier_passed=True,
        action_category="READ_ONLY_LOW_RISK",
    )
    assert res_unknown["integrity_state"] == ModelIntegrityState.UNKNOWN
    assert res_unknown["policy_action"] == "ESCALATE"
    assert "LAYER3_UNBOUND_RETRIEVAL_DIGEST" in res_unknown["reasons"]

    # 4. DEGRADED state (AgentFuse 4-call loop or liveness breach or stale source) -> DENY_AND_HALT
    for live_cfg in [
        {"endpoint_reachable": False, "observed_latency_units": 100, "observed_tokens": 300},
        {"endpoint_reachable": True, "observed_latency_units": 501, "observed_tokens": 300},
        {"endpoint_reachable": True, "observed_latency_units": 100, "observed_tokens": 2001},
    ]:
        res_live = FiveLayerModelIntegrityMonitor.evaluate_proposal(
            envelope=env,
            signer_public_key=pub,
            pinned_sources_by_uri=pinned,
            known_retrieval_digests=["sha256:ret-apoe-01"],
            max_latency_ceiling_units=500,
            max_token_budget=2000,
            golden_tasks_passed=20,
            golden_tasks_total=20,
            attention_weights=[0.25, 0.25, 0.25, 0.25],
            attention_entropy_band=(1.0, 2.5),
            recent_tool_call_window=["read_doc"],
            deterministic_verifier_passed=True,
            action_category="EXTERNAL_TOOL_CALL",
            **live_cfg,
        )
        assert res_live["integrity_state"] == ModelIntegrityState.DEGRADED
        assert "LAYER1_LIVENESS_DEGRADED" in res_live["reasons"]

    res_degraded_loop = FiveLayerModelIntegrityMonitor.evaluate_proposal(
        envelope=env,
        signer_public_key=pub,
        pinned_sources_by_uri=pinned,
        known_retrieval_digests=["sha256:ret-apoe-01"],
        endpoint_reachable=True,
        observed_latency_units=100,
        max_latency_ceiling_units=500,
        observed_tokens=300,
        max_token_budget=2000,
        golden_tasks_passed=20,
        golden_tasks_total=20,
        attention_weights=[0.25, 0.25, 0.25, 0.25],
        attention_entropy_band=(1.0, 2.5),
        recent_tool_call_window=["retry_tool", "retry_tool", "retry_tool", "retry_tool"],
        deterministic_verifier_passed=True,
        action_category="EXTERNAL_TOOL_CALL",
    )
    assert res_degraded_loop["integrity_state"] == ModelIntegrityState.DEGRADED
    assert res_degraded_loop["policy_action"] == "DENY_AND_HALT"
    assert "HALT_AGENTFUSE_TOOL_LOOP_DETECTED" in res_degraded_loop["reasons"]

    # 5. UNTRUSTED state (Attention-Entropy Circuit Breaker or Confident-Wrong Calibration Miss or Tainted Expansion)
    res_untrusted_entropy = FiveLayerModelIntegrityMonitor.evaluate_proposal(
        envelope=env,
        signer_public_key=pub,
        pinned_sources_by_uri=pinned,
        known_retrieval_digests=["sha256:ret-apoe-01"],
        endpoint_reachable=True,
        observed_latency_units=100,
        max_latency_ceiling_units=500,
        observed_tokens=300,
        max_token_budget=2000,
        golden_tasks_passed=20,
        golden_tasks_total=20,
        attention_weights=[0.999, 0.001, 0.0, 0.0],  # collapsed entropy ~0.0114 < 1.0
        attention_entropy_band=(1.0, 2.5),
        recent_tool_call_window=["step1"],
        deterministic_verifier_passed=False,
        action_category="EXTERNAL_TOOL_CALL",
    )
    assert res_untrusted_entropy["integrity_state"] == ModelIntegrityState.UNTRUSTED
    assert res_untrusted_entropy["policy_action"] == "DENY_AND_HALT"
    assert res_untrusted_entropy["computed_attention_entropy"] == 0.011408
    assert "HALT_ATTENTION_ENTROPY_CIRCUIT_BREAKER" in res_untrusted_entropy["reasons"]
    assert "LAYER5_CONFIDENT_WRONG_CALIBRATION_MISS" in res_untrusted_entropy["reasons"]

    # 6. QUARANTINED state (golden task regression) -> DENY_AND_HALT (highest priority)
    res_quarantined = FiveLayerModelIntegrityMonitor.evaluate_proposal(
        envelope=env,
        signer_public_key=pub,
        pinned_sources_by_uri=pinned,
        known_retrieval_digests=["sha256:ret-apoe-01"],
        endpoint_reachable=True,
        observed_latency_units=100,
        max_latency_ceiling_units=500,
        observed_tokens=300,
        max_token_budget=2000,
        golden_tasks_passed=18,
        golden_tasks_total=20,
        attention_weights=[0.25, 0.25, 0.25, 0.25],
        attention_entropy_band=(1.0, 2.5),
        recent_tool_call_window=["step1"],
        deterministic_verifier_passed=True,
        action_category="READ_ONLY_LOW_RISK",
    )
    assert res_quarantined["integrity_state"] == ModelIntegrityState.QUARANTINED
    assert res_quarantined["policy_action"] == "DENY_AND_HALT"
    assert "LAYER4_GOLDEN_TASK_REGRESSION_QUARANTINE" in res_quarantined["reasons"]

    # Calibration trace evaluation
    with pytest.raises(ValueError, match="Calibration trace cannot be empty"):
        FiveLayerModelIntegrityMonitor.evaluate_calibration_trace([])

    cal_metrics = FiveLayerModelIntegrityMonitor.evaluate_calibration_trace(
        [
            (0.95, True, "ALLOW"),
            (0.92, True, "ALLOW"),
            (0.90, False, "ALLOW"),  # false accept
            (0.80, True, "DENY_AND_HALT"),  # false block
            (0.45, False, "ESCALATE"),  # abstention
        ]
    )
    assert cal_metrics["total_evaluated"] == 5
    assert cal_metrics["false_accept_count"] == 1
    assert cal_metrics["false_block_count"] == 1
    assert cal_metrics["abstention_count"] == 1
    assert cal_metrics["mean_calibration_deviation"] == pytest.approx(
        (0.05 + 0.08 + 0.90 + 0.20 + 0.45) / 5.0
    )
    cal_repeating = FiveLayerModelIntegrityMonitor.evaluate_calibration_trace(
        [
            (1.0, True, "ALLOW"),
            (1.0, False, "ALLOW"),
            (0.0, False, "DENY_AND_HALT"),
        ]
    )
    assert cal_repeating["mean_calibration_deviation"] == 0.333333


def test_genomic_scitt_receipt_engine_p00520_disorder_and_biosecurity_gates() -> None:
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    # Grounded in live AlphaFold DB P00520 (ABL1 kinase): global pLDDT = 63.44, rigid domain = (75, 512)
    abl1_kinase_seq = "M" * 252
    atlas_url = (
        "https://alphagenomedocs.readthedocs.io/en/latest/Index.html"
        "#chr19:44908822:C>T"
    )

    with pytest.raises(ValueError, match="HALT_EMPTY_BIOLOGICAL_SEQUENCE"):
        GenomicScittReceiptEngine.compute_bio_caid("   ", "P00520", (75, 512))

    # 1. Nominal order inside rigid domain (242, 493) subset of (75, 512)
    receipt = GenomicScittReceiptEngine.evaluate_and_sign_synthesis_order(
        receipt_id="gscitt-p00520-001",
        sequence=abl1_kinase_seq,
        target_uniprot_or_gene="P00520",
        requested_residue_range=(242, 493),
        verified_rigid_domain_range=(75, 512),
        alphafold_global_plddt=63.44,
        ucsc_phylop100way=6.16111,
        alphamissense_pathogenicity_val=0.18,
        pathogenicity_ceiling=0.50,
        homologous_to_regulated_pathogen=False,
        input_taint_tier="TIER_1_CURATED_DATABASE",
        pi_step_up_verified=False,
        atlas_deep_link=atlas_url,
        signer_private_key=priv,
    )
    assert receipt.admissibility_status == "ADMISSIBLE_FOR_SYNTHESIS"
    assert receipt.sequence_length == 252
    pub.verify(base64.b64decode(receipt.signature_b64), encode_jcs(receipt.statement_dict()))

    # 2. Disordered N-terminal cap (1, 74) outside verified rigid domain (75, 512) -> HALT
    with pytest.raises(ValueError, match="HALT_DISORDERED_REGION_DOCKING_FORBIDDEN"):
        GenomicScittReceiptEngine.evaluate_and_sign_synthesis_order(
            receipt_id="gscitt-p00520-disordered-n",
            sequence=abl1_kinase_seq,
            target_uniprot_or_gene="P00520",
            requested_residue_range=(1, 74),
            verified_rigid_domain_range=(75, 512),
            alphafold_global_plddt=63.44,
            ucsc_phylop100way=6.16111,
            alphamissense_pathogenicity_val=0.18,
            pathogenicity_ceiling=0.50,
            homologous_to_regulated_pathogen=False,
            input_taint_tier="TIER_1_CURATED_DATABASE",
            pi_step_up_verified=False,
            atlas_deep_link=atlas_url,
            signer_private_key=priv,
        )

    # 3. Disordered C-terminal tail (513, 1130) outside (75, 512) -> HALT
    with pytest.raises(ValueError, match="HALT_DISORDERED_REGION_DOCKING_FORBIDDEN"):
        GenomicScittReceiptEngine.evaluate_and_sign_synthesis_order(
            receipt_id="gscitt-p00520-disordered-c",
            sequence=abl1_kinase_seq,
            target_uniprot_or_gene="P00520",
            requested_residue_range=(513, 1130),
            verified_rigid_domain_range=(75, 512),
            alphafold_global_plddt=63.44,
            ucsc_phylop100way=6.16111,
            alphamissense_pathogenicity_val=0.18,
            pathogenicity_ceiling=0.50,
            homologous_to_regulated_pathogen=False,
            input_taint_tier="TIER_1_CURATED_DATABASE",
            pi_step_up_verified=False,
            atlas_deep_link=atlas_url,
            signer_private_key=priv,
        )

    # 4. Biosecurity pathogen homology -> HALT even if PI step-up is True
    with pytest.raises(ValueError, match="HALT_BIOSECURITY_PATHOGEN_HOMOLOGY"):
        GenomicScittReceiptEngine.evaluate_and_sign_synthesis_order(
            receipt_id="gscitt-pathogen",
            sequence=abl1_kinase_seq,
            target_uniprot_or_gene="P00520",
            requested_residue_range=(242, 493),
            verified_rigid_domain_range=(75, 512),
            alphafold_global_plddt=63.44,
            ucsc_phylop100way=6.16111,
            alphamissense_pathogenicity_val=0.18,
            pathogenicity_ceiling=0.50,
            homologous_to_regulated_pathogen=True,
            input_taint_tier="TIER_1_CURATED_DATABASE",
            pi_step_up_verified=True,
            atlas_deep_link=atlas_url,
            signer_private_key=priv,
        )

    # 5. Unverified preprint taint (TIER_2_UNTRUSTED_EXTERNAL) without PI step-up -> HALT
    with pytest.raises(ValueError, match="HALT_UNVERIFIED_PREPRINT_TAINT_BLOCKS_SYNTHESIS"):
        GenomicScittReceiptEngine.evaluate_and_sign_synthesis_order(
            receipt_id="gscitt-preprint-taint",
            sequence=abl1_kinase_seq,
            target_uniprot_or_gene="P00520",
            requested_residue_range=(242, 493),
            verified_rigid_domain_range=(75, 512),
            alphafold_global_plddt=63.44,
            ucsc_phylop100way=6.16111,
            alphamissense_pathogenicity_val=0.18,
            pathogenicity_ceiling=0.50,
            homologous_to_regulated_pathogen=False,
            input_taint_tier="TIER_2_UNTRUSTED_EXTERNAL",
            pi_step_up_verified=False,
            atlas_deep_link=atlas_url,
            signer_private_key=priv,
        )

    # 6. High AlphaMissense pathogenicity without PI step-up -> HALT
    with pytest.raises(ValueError, match="HALT_PATHOGENICITY_SCREEN_REJECTED"):
        GenomicScittReceiptEngine.evaluate_and_sign_synthesis_order(
            receipt_id="gscitt-pathogenic-missense",
            sequence=abl1_kinase_seq,
            target_uniprot_or_gene="P00520",
            requested_residue_range=(242, 493),
            verified_rigid_domain_range=(75, 512),
            alphafold_global_plddt=63.44,
            ucsc_phylop100way=6.16111,
            alphamissense_pathogenicity_val=0.89,
            pathogenicity_ceiling=0.50,
            homologous_to_regulated_pathogen=False,
            input_taint_tier="TIER_1_CURATED_DATABASE",
            pi_step_up_verified=False,
            atlas_deep_link=atlas_url,
            signer_private_key=priv,
        )


def test_wetlab_jidoka_state_machine_and_tcc_reagent_escrow() -> None:
    reactor = WetLabJidokaStateMachine(
        reactor_id="reactor-01",
        temp_bounds_c=(25.0, 42.0),
        ph_bounds=(6.8, 7.6),
    )

    # Step 1 nominal
    s1 = reactor.inject_catalyst_step("step-1", "Buffer-A", observed_temp_c=37.0, observed_ph=7.2)
    assert s1["dispensed"] is True
    assert s1["quench_valve_diverted"] is False
    assert reactor.lifecycle_state == "NOMINAL_FLOW"

    # Step 2 thermal drift (58.0 C > 42.0 C) -> quench valve diverted & EFFECT_INDETERMINATE latch
    s2 = reactor.inject_catalyst_step("step-2", "Catalyst-X", observed_temp_c=58.0, observed_ph=7.2)
    assert s2["dispensed"] is False
    assert s2["quench_valve_diverted"] is True
    assert reactor.lifecycle_state == "EFFECT_INDETERMINATE"

    # Step 3 blocked while latched
    with pytest.raises(RuntimeError, match="HALT_BIOREACTOR_LATCHED_INDETERMINATE"):
        reactor.inject_catalyst_step("step-3", "Catalyst-Y", observed_temp_c=37.0, observed_ph=7.2)

    # Reconcile with signed assay
    assay_priv = Ed25519PrivateKey.generate()
    assay_pub = assay_priv.public_key()
    bad_payload = {"reactor_id": "reactor-01", "cleared_safe": False}
    bad_sig = base64.b64encode(assay_priv.sign(encode_jcs(bad_payload))).decode("ascii")
    with pytest.raises(ValueError, match="HALT_ASSAY_NOT_CLEARED"):
        reactor.reconcile_with_signed_assay(bad_payload, bad_sig, assay_pub)

    good_payload = {"reactor_id": "reactor-01", "cleared_safe": True}
    good_sig = base64.b64encode(assay_priv.sign(encode_jcs(good_payload))).decode("ascii")
    with pytest.raises(ValueError, match="HALT_INVALID_ASSAY_SIGNATURE"):
        reactor.reconcile_with_signed_assay(good_payload, "invalid_base64_sig!!", assay_pub)

    reactor.reconcile_with_signed_assay(good_payload, good_sig, assay_pub)
    assert reactor.lifecycle_state == "NOMINAL_FLOW"
    assert reactor.quench_valve_diverted is False

    # TCC Reagent Escrow checks
    escrow = BioStochasticAcidReagentEscrow("Enzyme-Z", epoch_ceiling_micrograms=1000)
    with pytest.raises(ValueError, match="Reservation amount must be positive"):
        escrow.try_reserve("b0", 0)

    r1 = escrow.try_reserve("b1", 600)
    assert r1["remaining_epoch_micrograms"] == 400

    with pytest.raises(ValueError, match="HALT_DUPLICATE_BRANCH_RESERVATION"):
        escrow.try_reserve("b1", 100)

    with pytest.raises(ValueError, match="HALT_REAGENT_EPOCH_QUOTA_EXCEEDED"):
        escrow.try_reserve("b2", 500)

    r2 = escrow.try_reserve("b2", 400)
    assert r2["remaining_epoch_micrograms"] == 0

    assert escrow.confirm_uncap_and_dispense("b1") == 600
    assert escrow.cancel_before_uncap("b2") == 400
    assert escrow.total_committed_or_reserved == 600

    with pytest.raises(ValueError, match="HALT_UNRESERVED_REAGENT_DISPENSE"):
        escrow.confirm_uncap_and_dispense("b-unknown")
    with pytest.raises(ValueError, match="Unknown reservation branch_id"):
        escrow.cancel_before_uncap("b-unknown")

    # 15-Step Bio-ChaosBench verification
    bench = run_bio_chaos_benchmark()
    assert bench["total_steps"] == 3 * 5
    assert bench["naive_micrograms_burned"] == 14100
    assert bench["bio_aeib_micrograms_consumed"] == 900
    assert bench["micrograms_saved"] == 13200
    assert bench["halted_at_step"] == 4
    assert bench["reactor_terminal_state"] == "EFFECT_INDETERMINATE"


def test_end_to_end_model_integrity_eo1_janus_bio_and_contextcart_pipeline(tmp_path) -> None:
    """
    End-to-End Integration Verification:
    Brain Proposal (ModelDecisionEnvelopeV1)
      -> 5-Layer Model Integrity Gate (VERIFIED)
      -> EO1 Hardware-Latched PreDispatchIntentInterlock (F_FULLFSYNC + single-use approval)
      -> Janus Offline Saga Log Verifier (VERIFIED_CONSISTENT)
      -> Bio-AEIB GenomicScittReceiptEngine (P00520 rigid core 75-512) + WetLabJidokaStateMachine
      -> ContextCartArchivalForgettingEngine (lossless SHA-256 archival of bulky trace while
         protecting EO1_APPROVAL_RECORD).
    """
    from src.eo1_write_before_execute import (
        OperationApprovalGrant,
        PreDispatchIntentInterlock,
        compute_caid,
    )
    from src.oct2026_runtime_trace_contextcart_and_hazard_gate import (
        GENESIS_TRACE_HASH,
        ContextCartArchivalForgettingEngine,
        ContextRecordKind,
        CrashAmbiguityState,
        JanusOfflineSagaLogVerifier,
        SignedApprovalArtifact,
    )

    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()

    # Step 1: Model Decision Envelope + 5-Layer Integrity Gate
    source_doc = "P00520 ABL1 rigid domain 75-512; global pLDDT 63.44; ENST00000252486.9"
    uri = "local://sources/p00520_afdb_v6.txt"
    claim = _make_sample_claim(
        source_doc,
        claim_id="c-bio-1",
        claim_type=ClaimCategory.BIOLOGICAL_DESIGN,
        source_uri=uri,
        start_char=0,
        end_char=31,
    )
    env = _make_signed_envelope(priv, [claim], retrieval_digest="sha256:ret-p00520-v6")
    eval_res = FiveLayerModelIntegrityMonitor.evaluate_proposal(
        envelope=env,
        signer_public_key=pub,
        pinned_sources_by_uri={uri: source_doc},
        known_retrieval_digests=["sha256:ret-p00520-v6"],
        endpoint_reachable=True,
        observed_latency_units=95,
        max_latency_ceiling_units=500,
        observed_tokens=310,
        max_token_budget=2000,
        golden_tasks_passed=20,
        golden_tasks_total=20,
        attention_weights=[0.25, 0.25, 0.25, 0.25],
        attention_entropy_band=(1.0, 2.5),
        recent_tool_call_window=["fetch_afdb", "propose_synthesis"],
        deterministic_verifier_passed=True,
        action_category="EXTERNAL_TOOL_CALL",
    )
    assert eval_res["integrity_state"] == ModelIntegrityState.VERIFIED
    assert eval_res["policy_action"] == "ALLOW"

    # Step 2: Bio-AEIB Genomic SCITT Admissibility Gate (P00520 rigid core 242-493 inside 75-512)
    seq = "M" * 252
    gscitt = GenomicScittReceiptEngine.evaluate_and_sign_synthesis_order(
        receipt_id="gscitt-e2e-001",
        sequence=seq,
        target_uniprot_or_gene="P00520",
        requested_residue_range=(242, 493),
        verified_rigid_domain_range=(75, 512),
        alphafold_global_plddt=63.44,
        ucsc_phylop100way=6.16111,
        alphamissense_pathogenicity_val=0.12,
        pathogenicity_ceiling=0.50,
        homologous_to_regulated_pathogen=False,
        input_taint_tier="TIER_1_CURATED_DATABASE",
        pi_step_up_verified=False,
        atlas_deep_link="https://alphagenomedocs.readthedocs.io/en/latest/Index.html#chr19:44908822:C>T",
        signer_private_key=priv,
    )
    assert gscitt.admissibility_status == "ADMISSIBLE_FOR_SYNTHESIS"

    # Step 3: EO1 Hardware-Latched Dispatch + Single-Use Approval + Wet-Lab Jidoka Execution
    interlock = PreDispatchIntentInterlock(
        ledger_path=tmp_path / "e2e_eo1_ledger.jsonl",
        output_state_dir=tmp_path / "e2e_eo1_state",
        authority_id="bio-agent-01",
    )
    action_payload = {
        "bio_caid": gscitt.bio_caid,
        "receipt_id": gscitt.receipt_id,
        "requested_range": [242, 493],
        "reagent_ug": 300,
    }
    caid = compute_caid(action_payload)
    grant = OperationApprovalGrant(
        approval_id="appr-e2e-bio-001",
        subject_actor_id="bio-agent-01",
        tool_name="bioreactor_inject_v1",
        operation_caid=caid,
    )
    escrow = BioStochasticAcidReagentEscrow("Kinase-Core-Synthesizer", epoch_ceiling_micrograms=2000)
    reactor = WetLabJidokaStateMachine("reactor-e2e", temp_bounds_c=(25.0, 42.0), ph_bounds=(6.8, 7.6))

    escrow.try_reserve("e2e-step-1", 300)
    intent_rec = interlock.record_intent(
        target_uri="custom://bioreactor-e2e",
        tool_name="bioreactor_inject_v1",
        payload=action_payload,
        approval=grant,
        actor_id="bio-agent-01",
    )
    assert intent_rec.caid == caid
    step_out = reactor.inject_catalyst_step("e2e-step-1", "Kinase-Mix", observed_temp_c=37.0, observed_ph=7.2)
    assert step_out["dispensed"] is True
    dispensed_ug = escrow.confirm_uncap_and_dispense("e2e-step-1")
    assert dispensed_ug == 300

    continuity_rec = interlock.reconcile_out_of_band(
        caid=caid,
        reconciliation_evidence={"outcome": "COMMITTED", "dispensed_ug": dispensed_ug},
        target_outcome="COMMITTED",
    )
    assert continuity_rec.status == "RECONCILED"

    # Step 4: Janus Offline Saga Log Verifier over 12+ Field EO1EnforcementTraceV1
    signed_appr = SignedApprovalArtifact.issue(
        approval_id="appr-e2e-bio-001",
        approver_actor_id="pi-approver-01",
        subject_agent_id="bio-agent-01",
        tool_id="bioreactor_inject_v1",
        capability_id="cap:wetlab:inject",
        action_payload=action_payload,
        policy_version="aeib-bio-v1",
        approver_private_key=priv,
    )
    trace_entry = JanusOfflineSagaLogVerifier.build_and_sign_trace(
        trace_id="tr-e2e-001",
        timestamp_ns=1792836000000000000,
        actor_id="bio-agent-01",
        session_id="sess-e2e-01",
        agent_id="bio-agent-01",
        tool_id="bioreactor_inject_v1",
        capability_id="cap:wetlab:inject",
        operation_id=intent_rec.intent_id,
        idempotency_key=caid,
        action_payload=action_payload,
        approval=signed_appr,
        input_taint_tier=1,
        provenance_lookup_digest=env.retrieval_digest,
        policy_version="aeib-bio-v1",
        decision="ALLOW",
        decision_reason="Model VERIFIED + GenomicSCITT ADMISSIBLE",
        crash_state=CrashAmbiguityState.INTENT_PREPARED_NOT_DISPATCHED,
        prev_trace_hash=GENESIS_TRACE_HASH,
        actor_private_key=priv,
    )
    janus_audit = JanusOfflineSagaLogVerifier.verify_signed_log_offline(
        traces=[trace_entry],
        approvals_by_digest={signed_appr.approval_digest: signed_appr},
        public_keys_by_actor={"bio-agent-01": pub, "pi-approver-01": pub},
    )
    assert janus_audit["verified_trace_count"] == 1
    assert janus_audit["terminal_chain_tip"] == trace_entry.trace_hash

    # Step 5: ContextCart Archival Forgetting compresses bulky tool observation while protecting EO1 approval
    cart = ContextCartArchivalForgettingEngine()
    cart.append_slot("slot-approval", ContextRecordKind.EO1_APPROVAL_RECORD, grant.approval_id)
    bulky_trace = ("BIOREACTOR_SPECTROMETRY_LOG_LINE: temp=37.0C ph=7.20 yield=99.4%\n") * 40
    cart.append_slot("slot-spectrometry", ContextRecordKind.TOOL_OBSERVATION, bulky_trace)

    archive_res = cart.archive_observation(
        "slot-spectrometry",
        compact_note="Step 1 nominal 37.0C/pH 7.20 spectrometry log",
    )
    assert archive_res["bytes_reclaimed"] > 2000
    assert cart.recover_observation("slot-spectrometry") == bulky_trace

