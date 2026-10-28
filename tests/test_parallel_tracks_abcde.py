#!/usr/bin/env python3
"""
tests/test_parallel_tracks_abcde.py — Verification Suite for Parallel Tracks A, B, C, D, and E.

Evaluated under the stated model (prototype):
- Single-source RFC 8785 JCS delegation (`_canonical_json_bytes`, `sha256_caid`)
- Track A: `BioDigitalNineSourceGate` offline structural and temporal checks
- Track B: `OspreyPreToolUseHookChain` (8 hooks) & `RealZeroMockSlopAndCVEFilter`
- Track C: `ExhaustiveF9StateSpaceProver` finite-state BFS checks
- Track D: `HawkesContextRAMManager` integer Hawkes decay and `[C]` constraint pinning
- Track E: `ReproducibleEvidenceBundleBuilder` in-memory `.tar.gz` generation and extraction
"""

from __future__ import annotations

import dataclasses
import gzip
import io
import tarfile
from pathlib import Path

import pytest

from src.jcs_canonicalizer import encode_jcs
from src.parallel_tracks_abcde_engine import (
    BFSModelCheckReport,
    BioDigitalNineSourceGate,
    ContextRAMBlock,
    ExactActionProposal,
    ExhaustiveF9StateSpaceProver,
    HawkesContextRAMManager,
    NineSourceOmicsRecord,
    OspreyPreToolUseHookChain,
    ProtocolModelState,
    RealZeroMockSlopAndCVEFilter,
    ReproducibleEvidenceBundleBuilder,
    _canonical_json_bytes,
    canonical_json_v1,
    sha256_caid,
)


def test_jcs_delegation_and_float_non_string_key_rejection() -> None:
    assert canonical_json_v1 is _canonical_json_bytes

    # Supplementary-plane key U+1F600 vs BMP U+E000 verifies RFC 8785 UTF-16 code-unit sorting
    payload = {"\ue000": [1, 2], "\U0001f600": {"b": True, "a": False}}
    assert _canonical_json_bytes(payload) == encode_jcs(payload)

    # sha256_caid over bytes, str, and dict
    assert sha256_caid(b"abc") == sha256_caid("abc")
    dict_caid = sha256_caid({"b": 1, "a": 2})
    assert dict_caid == sha256_caid(b'{"a":2,"b":1}')
    assert dict_caid.startswith("sha256:") and len(dict_caid) == 7 + 64

    # Float rejection at root, in dict value, and inside list/tuple
    for bad_float in (1.5, {"x": 0.1}, {"x": [1, 2.0]}, (3.14,)):
        with pytest.raises(ValueError, match="ERR_FLOAT_FORBIDDEN_IN_CANONICAL_JSON_V1"):
            _canonical_json_bytes(bad_float)

    # Non-string key rejection at root and nested dict
    for bad_key in ({1: "v"}, {"outer": {None: 1}}):
        with pytest.raises(ValueError, match="ERR_NON_STRING_KEY"):
            _canonical_json_bytes(bad_key)


def test_track_a_nine_source_bio_gate_and_anti_harking_lock() -> None:
    # Reject bool or negative grch38_pos / pre_registered_epoch_sec in register_hypothesis
    for bad_pos, bad_epoch in ((True, 100), (100, True), (-1, 100), (100, -1)):
        with pytest.raises(ValueError, match="ERR_INVALID_HYPOTHESIS_BOUNDS"):
            BioDigitalNineSourceGate.register_hypothesis(
                hypothesis_id="hyp_bad",
                rs_id="rs7412",
                grch38_chrom="chr19",
                grch38_pos=bad_pos,  # type: ignore[arg-type]
                ref_allele="C",
                alt_allele="T",
                ensembl_gene_id="ENSG00000130203",
                expected_direction="REGULATORY_GAIN",
                pre_registered_epoch_sec=bad_epoch,  # type: ignore[arg-type]
            )

    # Zero epoch and zero position are non-negative integers allowed at registration time
    hyp_zero = BioDigitalNineSourceGate.register_hypothesis(
        hypothesis_id="hyp_zero",
        rs_id="rs7412",
        grch38_chrom="chr19",
        grch38_pos=0,
        ref_allele="C",
        alt_allele="T",
        ensembl_gene_id="ENSG00000130203",
        expected_direction="BENIGN",
        pre_registered_epoch_sec=0,
    )
    assert hyp_zero.grch38_pos == 0 and hyp_zero.pre_registered_epoch_sec == 0

    hyp = BioDigitalNineSourceGate.register_hypothesis(
        hypothesis_id="hyp_apoe_01",
        rs_id="rs7412",
        grch38_chrom="chr19",
        grch38_pos=44908822,
        ref_allele="C",
        alt_allele="T",
        ensembl_gene_id="ENSG00000130203",
        expected_direction="REGULATORY_GAIN",
        pre_registered_epoch_sec=1_761_500_000,
    )
    assert hyp.hypothesis_caid.startswith("sha256:")

    # Note: rs7412 (chr19:44908822 C>T, ENSG00000130203, P02649, R-HSA-174824) are real
    # APOE identifiers; EH38E2941922 (ENCODE4 cCRE) and MA0139.1 (JASPAR CTCF motif) are
    # real accession-format controls in a synthetic test fixture, not a claim of biological
    # binding at rs7412. The metric values below (AVI 9150, phyloP 4200 milli, pLDDT 9250)
    # are SYNTHETIC branch-coverage values, not database observations; see
    # test_track_a_observed_rs7412_values_do_not_reach_supports for observed values.
    rec_ok = NineSourceOmicsRecord(
        rs_id="rs7412",
        grch38_chrom="chr19",
        grch38_pos=44908822,
        ref_allele="C",
        alt_allele="T",
        dbsnp_build_id=157,
        ensembl_gene_id="ENSG00000130203",
        uniprot_accession="P02649",
        alphagenome_avi_phred_bps=9150,
        encode4_ccre_id="EH38E2941922",
        jaspar_tfbs_motif_id="MA0139.1",
        ucsc_phylop_milli=4200,
        reactome_pathway_id="R-HSA-174824",
        alphafold_plddt_bps=9250,
        evidence_timestamp_sec=1_761_500_500,
    )
    v_ok = BioDigitalNineSourceGate.evaluate(hyp, rec_ok)
    assert v_ok.verdict == "SUPPORTS"
    assert v_ok.reason_code == "OK_CONCORDANT_9_SOURCE_PATHOGENIC_SUPPORT"
    assert v_ok.lookup_caid.startswith("sha256:")
    assert v_ok.content_caid.startswith("sha256:")

    # Exact timestamp tie (pre_registered_epoch_sec == evidence_timestamp_sec) is permitted
    v_tie = BioDigitalNineSourceGate.evaluate(
        hyp, dataclasses.replace(rec_ok, evidence_timestamp_sec=1_761_500_000)
    )
    assert v_tie.verdict == "SUPPORTS"

    # Metric bounds & boolean trap checks
    for bad_rec in (
        dataclasses.replace(rec_ok, dbsnp_build_id=True),  # type: ignore[arg-type]
        dataclasses.replace(rec_ok, dbsnp_build_id=0),
        dataclasses.replace(rec_ok, alphagenome_avi_phred_bps=-1),
        dataclasses.replace(rec_ok, alphagenome_avi_phred_bps=10001),
        dataclasses.replace(rec_ok, alphafold_plddt_bps=-1),
        dataclasses.replace(rec_ok, alphafold_plddt_bps=10001),
        dataclasses.replace(rec_ok, evidence_timestamp_sec=-1),
    ):
        v_bounds = BioDigitalNineSourceGate.evaluate(hyp, bad_rec)
        assert v_bounds.verdict == "HALT_INVALID_OMICS_METRIC_BOUNDS"

    # Boundary values 0 and 10000 on basis-point fields and dbsnp_build_id=1 pass bounds check
    v_boundary_high = BioDigitalNineSourceGate.evaluate(
        hyp,
        dataclasses.replace(
            rec_ok,
            dbsnp_build_id=1,
            alphagenome_avi_phred_bps=10000,
            alphafold_plddt_bps=10000,
        ),
    )
    assert v_boundary_high.verdict == "SUPPORTS"
    v_boundary_zero = BioDigitalNineSourceGate.evaluate(
        hyp_zero,
        dataclasses.replace(
            rec_ok,
            grch38_pos=0,
            alphagenome_avi_phred_bps=0,
            alphafold_plddt_bps=0,
            evidence_timestamp_sec=0,
        ),
    )
    assert v_boundary_zero.verdict == "HALT_INVALID_ALLELE_OR_RSID"

    # Vector 1: Anti-HARKing violation (evidence older than hypothesis)
    rec_harked = dataclasses.replace(rec_ok, evidence_timestamp_sec=1_761_499_999)
    v_hark = BioDigitalNineSourceGate.evaluate(hyp, rec_harked)
    assert v_hark.verdict == "HALT_POST_HOC_HARKING_DETECTED"

    # Vector 2: Coordinate & Variant Identity Parity mismatches
    for mismatch_rec in (
        dataclasses.replace(rec_ok, rs_id="rs429358"),
        dataclasses.replace(rec_ok, grch38_chrom="chr20"),
        dataclasses.replace(rec_ok, grch38_pos=44908823),
        dataclasses.replace(rec_ok, ensembl_gene_id="ENSG00000000001"),
    ):
        assert (
            BioDigitalNineSourceGate.evaluate(hyp, mismatch_rec).verdict
            == "HALT_VARIANT_COORDINATE_MISMATCH"
        )

    # Vector 3: Allele & dbSNP Format Validation
    for bad_allele_kw in (
        {"rs_id": "ss7412"},
        {"rs_id": "rsXYZ"},
        {"grch38_pos": 0},
        {"ref_allele": "N"},
        {"alt_allele": "U"},
        {"ref_allele": "C", "alt_allele": "C"},
    ):
        hyp_v3 = dataclasses.replace(hyp, **{k: v for k, v in bad_allele_kw.items() if k in hyp.__dict__})
        rec_v3 = dataclasses.replace(rec_ok, **bad_allele_kw)
        assert (
            BioDigitalNineSourceGate.evaluate(hyp_v3, rec_v3).verdict
            == "HALT_INVALID_ALLELE_OR_RSID"
        )
    # Positive position boundary grch38_pos=1 and 1-digit rsID ("rs7") pass Vector 3
    hyp_pos1 = dataclasses.replace(hyp, rs_id="rs7", grch38_pos=1)
    rec_pos1 = dataclasses.replace(rec_ok, rs_id="rs7", grch38_pos=1)
    assert BioDigitalNineSourceGate.evaluate(hyp_pos1, rec_pos1).verdict == "SUPPORTS"

    # Vector 4: Accession Provenance
    hyp_bad_ensg = dataclasses.replace(hyp, ensembl_gene_id="GENE130203")
    rec_bad_ensg = dataclasses.replace(rec_ok, ensembl_gene_id="GENE130203")
    assert (
        BioDigitalNineSourceGate.evaluate(hyp_bad_ensg, rec_bad_ensg).verdict
        == "HALT_MISSING_OMICS_ACCESSION"
    )
    assert (
        BioDigitalNineSourceGate.evaluate(
            hyp, dataclasses.replace(rec_ok, uniprot_accession="")
        ).verdict
        == "HALT_MISSING_OMICS_ACCESSION"
    )
    assert (
        BioDigitalNineSourceGate.evaluate(
            hyp, dataclasses.replace(rec_ok, reactome_pathway_id="KEGG-123")
        ).verdict
        == "HALT_MISSING_OMICS_ACCESSION"
    )

    # Vector 5: AlphaFold pLDDT floor at 7000 bps
    v_low_plddt = BioDigitalNineSourceGate.evaluate(
        hyp, dataclasses.replace(rec_ok, alphafold_plddt_bps=6999)
    )
    assert v_low_plddt.verdict == "UNKNOWN"
    assert v_low_plddt.reason_code == "INCONCLUSIVE_LOW_ALPHAFOLD_PLDDT"
    v_exact_plddt = BioDigitalNineSourceGate.evaluate(
        hyp, dataclasses.replace(rec_ok, alphafold_plddt_bps=7000)
    )
    assert v_exact_plddt.verdict == "SUPPORTS"

    # Vector 6: Concordant Multi-Omics Scoring boundaries (SUPPORTS, REFUTES, UNKNOWN)
    v_exact_support = BioDigitalNineSourceGate.evaluate(
        hyp,
        dataclasses.replace(rec_ok, ucsc_phylop_milli=2000, alphagenome_avi_phred_bps=8000),
    )
    assert v_exact_support.verdict == "SUPPORTS"

    for discordant_rec in (
        dataclasses.replace(rec_ok, encode4_ccre_id="NONE"),
        dataclasses.replace(rec_ok, jaspar_tfbs_motif_id="NONE"),
        dataclasses.replace(rec_ok, ucsc_phylop_milli=1999),
        dataclasses.replace(rec_ok, alphagenome_avi_phred_bps=7999),
        dataclasses.replace(rec_ok, alphagenome_avi_phred_bps=2001, ucsc_phylop_milli=0),
        dataclasses.replace(rec_ok, alphagenome_avi_phred_bps=2000, ucsc_phylop_milli=1),
    ):
        v_disc = BioDigitalNineSourceGate.evaluate(hyp, discordant_rec)
        assert v_disc.verdict == "UNKNOWN"
        assert v_disc.reason_code == "INCONCLUSIVE_DISCORDANT_OMICS_EVIDENCE"

    v_refute = BioDigitalNineSourceGate.evaluate(
        hyp,
        dataclasses.replace(rec_ok, alphagenome_avi_phred_bps=2000, ucsc_phylop_milli=0),
    )
    assert v_refute.verdict == "REFUTES"
    assert v_refute.reason_code == "OK_CONCORDANT_BENIGN_REFUTATION"


def test_track_b_osprey_8_hook_chain_and_cve_2026_33017_filter() -> None:
    chain = OspreyPreToolUseHookChain(
        frozen_tenants=frozenset({"tenant_frozen"}),
        max_per_call_minor=50_000,
        allowed_tools=frozenset({"payments.create_refund", "epics.caput"}),
        live_model_manifest_digest="sha256:opus_v1",
    )

    base_p = ExactActionProposal(
        tool_name="payments.create_refund",
        arguments={"payment_id": "pay_1"},
        risk_tier="T3",
        tenant_id="tenant_active",
        data_jurisdiction="EU",
        target_model_jurisdiction="EU",
        amount_minor=4999,
        idempotency_key="idem_01",
        model_manifest_digest="sha256:opus_v1",
    )
    assert base_p.operator_signed_action_caid is None
    assert base_p.co_tenant_count_on_host == 0
    exact_caid = base_p.action_caid()
    signed_p = dataclasses.replace(base_p, operator_signed_action_caid=exact_caid)

    # Hook 1: Kill Switch
    r1 = chain.evaluate(dataclasses.replace(signed_p, tenant_id="tenant_frozen"))
    assert r1.allowed is False and r1.failed_hook == "HOOK_1_KILL_SWITCH"
    assert r1.reason_code == "HALT_TENANT_KILL_SWITCH_ACTIVE"

    # Hook 2: Budget & Setpoint Limits (bool, <0, >max_per_call_minor)
    for bad_amt in (True, -1, 50_001):
        p_amt = dataclasses.replace(base_p, amount_minor=bad_amt)  # type: ignore[arg-type]
        r2 = chain.evaluate(p_amt)
        assert r2.allowed is False and r2.failed_hook == "HOOK_2_LIMITS"
        assert r2.reason_code == "HALT_AMOUNT_EXCEEDS_PER_CALL_LIMIT"

    # Hook 3: Jurisdiction
    r3_export = chain.evaluate(
        dataclasses.replace(signed_p, target_model_jurisdiction="RESTRICTED_EXPORT")
    )
    assert r3_export.allowed is False and r3_export.failed_hook == "HOOK_3_JURISDICTION"
    assert r3_export.reason_code == "HALT_GEOPOLITICAL_EXPORT_VIOLATION"

    r3_eu = chain.evaluate(
        dataclasses.replace(signed_p, data_jurisdiction="EU", target_model_jurisdiction="US")
    )
    assert r3_eu.allowed is False and r3_eu.failed_hook == "HOOK_3_JURISDICTION"
    assert r3_eu.reason_code == "HALT_EU_DATA_RESIDENCY_VIOLATION"

    # Hook 4: Tool Manifest
    r4 = chain.evaluate(dataclasses.replace(signed_p, tool_name="shell.exec"))
    assert r4.allowed is False and r4.failed_hook == "HOOK_4_TOOL_MANIFEST"
    assert r4.reason_code == "HALT_UNREGISTERED_TOOL:shell.exec"

    # Hook 5: Model Manifest
    r5 = chain.evaluate(dataclasses.replace(signed_p, model_manifest_digest="sha256:drifted"))
    assert r5.allowed is False and r5.failed_hook == "HOOK_5_MODEL_MANIFEST"
    assert r5.reason_code == "HALT_MODEL_MANIFEST_EXPIRED"

    # Hook 6: Hardware Cache Isolation Policy (T3 requires co_tenant_count_on_host == 0)
    for bad_cotenant in (2, -1, True):
        r6 = chain.evaluate(
            dataclasses.replace(signed_p, co_tenant_count_on_host=bad_cotenant)  # type: ignore[arg-type]
        )
        assert r6.allowed is False and r6.failed_hook == "HOOK_6_CACHE_ISOLATION"
        assert r6.reason_code == "HALT_T3_SHARED_L3_CACHE_CO_TENANT_FORBIDDEN"

    # Hook 7: Missing idempotency key
    r7_empty = chain.evaluate(dataclasses.replace(signed_p, idempotency_key=""))
    assert r7_empty.allowed is False and r7_empty.failed_hook == "HOOK_7_IDEMPOTENCY"
    assert r7_empty.reason_code == "HALT_DUPLICATE_OR_MISSING_IDEMPOTENCY_KEY"

    # Hook 8: Unsigned or mismatched operator signature for T3 (must NOT burn idempotency_key)
    r8_unsigned = chain.evaluate(base_p)
    assert r8_unsigned.allowed is False and r8_unsigned.failed_hook == "HOOK_8_EXACT_APPROVAL"
    assert r8_unsigned.reason_code == "HALT_T3_EXACT_ACTION_DIGEST_UNAPPROVED"

    # Now submit valid signed_p with the same idempotency_key="idem_01" -> ALLOW
    res_ok = chain.evaluate(signed_p)
    assert res_ok.allowed is True and res_ok.failed_hook == "NONE"
    assert res_ok.reason_code == "OK_ALL_8_PRE_TOOL_HOOKS_PASSED"
    assert res_ok.action_caid == exact_caid

    # Replay of committed idempotency_key="idem_01" -> HALT
    res_replay = chain.evaluate(signed_p)
    assert res_replay.allowed is False and res_replay.failed_hook == "HOOK_7_IDEMPOTENCY"
    assert res_replay.reason_code == "HALT_DUPLICATE_OR_MISSING_IDEMPOTENCY_KEY"

    # Boundary: T1 call with amount_minor=0 and amount_minor=max_per_call_minor on US->US shared host
    for boundary_amt, idem in ((0, "idem_t1_zero"), (50_000, "idem_t1_max")):
        p_t1 = dataclasses.replace(
            base_p,
            risk_tier="T1",
            data_jurisdiction="US",
            target_model_jurisdiction="US",
            amount_minor=boundary_amt,
            idempotency_key=idem,
            co_tenant_count_on_host=4,
        )
        r_t1 = chain.evaluate(p_t1)
        assert r_t1.allowed is True

    # RealZeroMockSlopAndCVEFilter tests
    cve_filter = RealZeroMockSlopAndCVEFilter(
        pinned_sbom_packages=frozenset({"json", "hashlib", "math"})
    )

    for tok in RealZeroMockSlopAndCVEFilter.DANGEROUS_TEMPLATE_TOKENS:
        ok_t, code_t = cve_filter.inspect_code_and_templates("x = 1\n", f"prefix {tok} suffix")
        assert ok_t is False and code_t == f"HALT_TEMPLATE_OR_DUNDER_INJECTION:{tok}"
        ok_s, code_s = cve_filter.inspect_code_and_templates(f"# {tok}\nx = 1\n")
        assert ok_s is False and code_s == f"HALT_TEMPLATE_OR_DUNDER_INJECTION:{tok}"

    ok_syn, code_syn = cve_filter.inspect_code_and_templates("def broken(:\n")
    assert ok_syn is False and code_syn.startswith("HALT_AST_SYNTAX_ERROR:")

    for top_call_src in (
        "import json\nx = json.loads('{}')\n",
        "import json\nx: dict = json.loads('{}')\n",
        "import json\njson.loads('{}')\n",
    ):
        ok_rce, code_rce = cve_filter.inspect_code_and_templates(top_call_src)
        assert ok_rce is False
        assert code_rce == "HALT_CVE_2026_33017_TOP_LEVEL_CALL_IN_ASSIGN_OR_EXPR"

    for slop_src, pkg_name in (
        ("import hallucinated_ai_sdk.sub\ndef run():\n    return 1\n", "hallucinated_ai_sdk"),
        ("from unpinned_pkg.mod import helper\ndef run():\n    return 1\n", "unpinned_pkg"),
    ):
        ok_slop, code_slop = cve_filter.inspect_code_and_templates(slop_src)
        assert ok_slop is False
        assert code_slop == f"HALT_UNPINNED_SBOM_IMPORT:{pkg_name}"

    clean_src = (
        "import json.decoder\n"
        "from hashlib import sha256\n"
        "from . import local_mod\n"
        "CONST_VAL = 42\n"
        "def compute(data: bytes) -> str:\n"
        "    return sha256(data).hexdigest()\n"
    )
    ok_clean, code_clean = cve_filter.inspect_code_and_templates(clean_src, "plain template")
    assert ok_clean is True and code_clean == "OK_AST_AND_SBOM_CLEAN"


def test_track_c_exhaustive_bfs_f9_state_space_prover() -> None:
    fenced_report = ExhaustiveF9StateSpaceProver.prove_fenced_protocol_invariants()
    assert fenced_report == BFSModelCheckReport(
        explored_states=9,
        max_committed_count_observed=1,
        budget_conservation_holds=True,
        at_most_once_holds=True,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        fenced_report.explored_states = 0  # type: ignore[misc]

    unfenced_report = ExhaustiveF9StateSpaceProver.prove_fenced_protocol_invariants(
        enable_target_fencing=False
    )
    assert unfenced_report == BFSModelCheckReport(
        explored_states=9,
        max_committed_count_observed=2,
        budget_conservation_holds=True,
        at_most_once_holds=False,
    )

    st = ProtocolModelState("IDLE", 0, 1, False, 0, 0)
    assert st.client_state == "IDLE" and st.escrow_locked == 0
    with pytest.raises(dataclasses.FrozenInstanceError):
        st.attempt_seq = 5  # type: ignore[misc]


def test_track_d_hawkes_context_ram_preserves_constraints_under_1500_token_cap() -> None:
    for bad_ceiling in (True, 0, -10):
        with pytest.raises(ValueError, match="ERR_INVALID_RAM_TOKEN_CEILING"):
            HawkesContextRAMManager(ram_token_ceiling=bad_ceiling)  # type: ignore[arg-type]

    # Minimum valid ceiling (1) and minimum valid token_count (1)
    tiny_ram = HawkesContextRAMManager(ram_token_ceiling=1)
    tiny_ids, tiny_used = tiny_ram.upsert_and_compact(
        ContextRAMBlock("tiny_1", "[E]", 1, 1000, 1, 0, "x"), current_turn=1
    )
    assert tiny_ids == ("tiny_1",) and tiny_used == 1

    ram = HawkesContextRAMManager()

    for bad_tokens in (True, 0, -5):
        with pytest.raises(ValueError, match="ERR_INVALID_BLOCK_TOKEN_COUNT"):
            ram.upsert_and_compact(
                ContextRAMBlock("bad", "[E]", bad_tokens, 5000, 1, 0, "x"),  # type: ignore[arg-type]
                current_turn=1,
            )

    c_block = ContextRAMBlock("c_law_1", "[C]", 600, 10000, 0, 1, "NEVER_BLIND_RETRY")
    with pytest.raises(dataclasses.FrozenInstanceError):
        c_block.token_count = 10  # type: ignore[misc]
    assert ram.compute_hawkes_intensity_bps(c_block, current_turn=100) == 100_000

    # Verify exact Hawkes arithmetic: base + excitation * alpha - max(0, turn - last_turn) * decay
    e_probe = ContextRAMBlock("e_probe", "[E]", 100, 5000, 4, 2, "trace")
    # At turn 6: age = 2, intensity = 5000 + 2*1200 - 2*800 = 5800
    intensity_t6 = ram.compute_hawkes_intensity_bps(e_probe, current_turn=6)
    assert intensity_t6 == 5800
    # Future last_event_turn clamps age to 0: intensity = 5000 + 2*1200 - 0 = 7400
    intensity_future = ram.compute_hawkes_intensity_bps(e_probe, current_turn=2)
    assert intensity_future == 7400
    # Large age clamps intensity floor to 0
    intensity_decayed = ram.compute_hawkes_intensity_bps(e_probe, current_turn=50)
    assert intensity_decayed == 0

    ram.upsert_and_compact(c_block, current_turn=1)
    ram.upsert_and_compact(
        ContextRAMBlock("e_old_log", "[E]", 500, 3000, 1, 0, "old grep output"),
        current_turn=2,
    )
    ram.upsert_and_compact(
        ContextRAMBlock("e_mid_log", "[E]", 500, 5000, 4, 1, "mid test trace"),
        current_turn=5,
    )
    retained_ids, total_tokens = ram.upsert_and_compact(
        ContextRAMBlock("e_fresh_slice", "[E]", 400, 8000, 8, 2, "active AST slice"),
        current_turn=8,
    )

    assert total_tokens == 1500
    assert retained_ids == ("c_law_1", "e_fresh_slice", "e_mid_log")
    assert "e_old_log" not in retained_ids

    # [C] tier outranks non-[C] blocks even if an [E] block has base_salience_bps > 100_000
    prio_ram = HawkesContextRAMManager(ram_token_ceiling=100)
    prio_ram.upsert_and_compact(
        ContextRAMBlock("c_pin", "[C]", 60, 10000, 1, 0, "pin"), current_turn=1
    )
    prio_ids, prio_used = prio_ram.upsert_and_compact(
        ContextRAMBlock("e_burst", "[E]", 60, 200_000, 1, 0, "burst"), current_turn=1
    )
    assert prio_ids == ("c_pin",) and prio_used == 60

    # Overflowing [C] tier beyond ram_token_ceiling raises RuntimeError
    with pytest.raises(RuntimeError, match="HALT_CONSTRAINT_TIER_EXCEEDS_RAM_CEILING"):
        ram.upsert_and_compact(
            ContextRAMBlock("c_law_2", "[C]", 901, 10000, 8, 0, "SECOND_STATUTORY_PIN"),
            current_turn=8,
        )


def test_track_e_reproducible_source_date_epoch_evidence_bundle(tmp_path: Path) -> None:
    # Regression demonstration: the old GzipFile call without `fileobj=buf` wrote to a disk
    # file and left the in-memory BytesIO buffer empty (len == 0).
    buggy_buf = io.BytesIO()
    stray_file = tmp_path / "evidence_bundle.tar"
    with gzip.GzipFile(
        filename=str(stray_file),
        mode="wb",
        compresslevel=9,
        mtime=ReproducibleEvidenceBundleBuilder.FIXED_EPOCH,
    ) as buggy_gz:
        buggy_gz.write(b"test")
    assert len(buggy_buf.getvalue()) == 0

    with pytest.raises(ValueError, match="HALT_EMPTY_EVIDENCE_BUNDLE"):
        ReproducibleEvidenceBundleBuilder.build_deterministic_bundle_bytes({})

    artifacts = {
        "manifest/wave6_verdict.json": {"status": "EVALUATED", "tests_run": 3447},
        "proofs/f9_bfs_report.json": {"at_most_once": True, "max_commits": 1},
    }
    bytes_run_1, caid_1 = ReproducibleEvidenceBundleBuilder.build_deterministic_bundle_bytes(
        artifacts
    )
    bytes_run_2, caid_2 = ReproducibleEvidenceBundleBuilder.build_deterministic_bundle_bytes(
        artifacts
    )

    assert len(bytes_run_1) > 64
    assert bytes_run_1 == bytes_run_2
    assert caid_1 == caid_2
    assert caid_1 == sha256_caid(bytes_run_1)
    assert not Path("evidence_bundle.tar").exists()

    # Inspect tar headers for deterministic metadata (mtime, mode, uid, gid, uname, gname, order)
    with gzip.GzipFile(fileobj=io.BytesIO(bytes_run_1), mode="rb") as gz:
        with tarfile.open(fileobj=gz, mode="r:*") as tar:
            members = tar.getmembers()
            assert [m.name for m in members] == sorted(artifacts.keys())
            for m in members:
                assert int(m.mtime) == 1761523200
                assert int(m.mode) == 0o644
                assert m.uid == 0 and m.gid == 0
                assert m.uname == "root" and m.gname == "root"

    extracted = ReproducibleEvidenceBundleBuilder.verify_and_extract_bundle(bytes_run_1, caid_1)
    assert extracted == artifacts

    with pytest.raises(ValueError, match="HALT_EMPTY_ARCHIVE_BYTES"):
        ReproducibleEvidenceBundleBuilder.verify_and_extract_bundle(b"", caid_1)

    tampered = bytes_run_1[:-1] + bytes([bytes_run_1[-1] ^ 0xFF])
    with pytest.raises(ValueError, match="HALT_EVIDENCE_BUNDLE_CAID_MISMATCH"):
        ReproducibleEvidenceBundleBuilder.verify_and_extract_bundle(tampered, caid_1)


def test_track_a_observed_rs7412_values_do_not_reach_supports() -> None:
    """Observed this session (2026-10-27, local science skills): UCSC hg38 phyloP100way
    at chr19:44908822 = 0.827898 (828 milli); AlphaFold AF-P02649-F1 mean pLDDT 75.50
    (7550 bps). AlphaGenome AVI was NOT queried; it is held at the synthetic 9150 (the
    value most favourable to SUPPORTS). With observed conservation below the gate's
    2000-milli floor, the gate must not emit SUPPORTS for rs7412."""
    hyp = BioDigitalNineSourceGate.register_hypothesis(
        hypothesis_id="hyp_apoe_observed", rs_id="rs7412", grch38_chrom="chr19",
        grch38_pos=44908822, ref_allele="C", alt_allele="T",
        ensembl_gene_id="ENSG00000130203", expected_direction="REGULATORY_GAIN",
        pre_registered_epoch_sec=1_761_500_000,
    )
    rec = NineSourceOmicsRecord(
        rs_id="rs7412", grch38_chrom="chr19", grch38_pos=44908822, ref_allele="C",
        alt_allele="T", dbsnp_build_id=157, ensembl_gene_id="ENSG00000130203",
        uniprot_accession="P02649", alphagenome_avi_phred_bps=9150,
        encode4_ccre_id="EH38E2941922", jaspar_tfbs_motif_id="MA0139.1",
        ucsc_phylop_milli=828, reactome_pathway_id="R-HSA-174824",
        alphafold_plddt_bps=7550, evidence_timestamp_sec=1_761_500_500,
    )
    v = BioDigitalNineSourceGate.evaluate(hyp, rec)
    assert (v.verdict, v.reason_code) == ("UNKNOWN", "INCONCLUSIVE_DISCORDANT_OMICS_EVIDENCE")
