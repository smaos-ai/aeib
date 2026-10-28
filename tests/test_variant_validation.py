#!/usr/bin/env python3
# File: tests/test_variant_validation.py
"""
Verification & Falsification Suite for `src/bio_variant_contract.py` and `src/bio_evidence_gate.py`.
"""

from __future__ import annotations

import tempfile
from dataclasses import FrozenInstanceError
from pathlib import Path
import pytest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from src.bio_evidence_gate import (
    BioContextCart,
    BioEvidenceScorer,
    BioScopeGate,
    BioScopeTier,
    CapabilityUnavailableError,
    ClaimDisposition,
    EO1BioEvidenceLatch,
    EvidenceRecord,
    ReproducibleBioEvidenceBundle,
    build_verified_evidence_record,
)
from src.bio_variant_contract import (
    VariantContract,
    VariantHaltCode,
    canonical_json_v1,
    probe_variant_verifier,
    sha256_prefixed,
)

# Independent ground-truth NCBI reference chromosome lengths for falsification testing
NCBI_REF_LENGTHS = {
    "GRCh38": {
        "chr1": 248956422,
        "chr2": 242193529,
        "chr3": 198295559,
        "chr4": 190214555,
        "chr5": 181538259,
        "chr6": 170805979,
        "chr7": 159345973,
        "chr8": 145138636,
        "chr9": 138394717,
        "chr10": 133797422,
        "chr11": 135086622,
        "chr12": 133275309,
        "chr13": 114364328,
        "chr14": 107043718,
        "chr15": 101991189,
        "chr16": 90338345,
        "chr17": 83257441,
        "chr18": 80373285,
        "chr19": 58617616,
        "chr20": 64444167,
        "chr21": 46709983,
        "chr22": 50818468,
        "chrX": 156040895,
        "chrY": 57227415,
        "chrM": 16569,
    },
    "GRCh37": {
        "chr1": 249250621,
        "chr2": 243199373,
        "chr3": 198022430,
        "chr4": 191154276,
        "chr5": 180915260,
        "chr6": 171115067,
        "chr7": 159138663,
        "chr8": 146364022,
        "chr9": 141213431,
        "chr10": 135534747,
        "chr11": 135006516,
        "chr12": 133851895,
        "chr13": 115169878,
        "chr14": 107349540,
        "chr15": 102531392,
        "chr16": 90354753,
        "chr17": 81195210,
        "chr18": 78077248,
        "chr19": 59128983,
        "chr20": 63025520,
        "chr21": 48129895,
        "chr22": 51304566,
        "chrX": 155270560,
        "chrY": 59373566,
        "chrM": 16569,
    },
}


def test_1_variant_contract_validation_and_build_coordinate_bounds() -> None:
    # 1. Valid GRCh38 CFTR locus variant
    valid_v = {
        "genome_build": "GRCh38",
        "chrom": "chr7",
        "pos": 117_120_016,
        "ref": "A",
        "alt": "G",
        "rsid": "rs75527207",
    }
    res_ok = VariantContract.validate(valid_v)
    assert res_ok.is_valid is True
    assert res_ok.halt_code == VariantHaltCode.VALID
    assert res_ok.normalized is not None
    assert res_ok.normalized.variant_caid.startswith("sha256:")

    # NormalizedVariant dataclass is frozen
    with pytest.raises(FrozenInstanceError):
        res_ok.normalized.pos = 123  # type: ignore

    # 2. GRCh37 vs GRCh38 chr1 boundary difference:
    pos_only_valid_in_grch37 = 249_000_000
    res_37 = VariantContract.validate(
        {
            "genome_build": "GRCh37",
            "chrom": "chr1",
            "pos": pos_only_valid_in_grch37,
            "ref": "C",
            "alt": "T",
        }
    )
    res_38 = VariantContract.validate(
        {
            "genome_build": "GRCh38",
            "chrom": "chr1",
            "pos": pos_only_valid_in_grch37,
            "ref": "C",
            "alt": "T",
        }
    )
    assert res_37.is_valid is True
    assert res_38.is_valid is False
    assert res_38.halt_code == VariantHaltCode.HALT_COORDINATE_OUT_OF_BOUNDS

    # 3. Unnormalized right-padded allele rejected when require_pre_normalized=True
    res_unnorm = VariantContract.validate(
        {
            "genome_build": "GRCh38",
            "chrom": "chr7",
            "pos": 1000,
            "ref": "AT",
            "alt": "GT",
        }
    )
    assert res_unnorm.is_valid is False
    assert res_unnorm.halt_code == VariantHaltCode.HALT_UNNORMALIZED_ALLELE_REPRESENTATION

    # 4. Non-dict input returns is_valid=False
    res_nondict = VariantContract.validate("not_a_dictionary")  # type: ignore
    assert res_nondict.is_valid is False


def test_2_bio_mutation_oracle_catches_stub_and_certifies_real_contract() -> None:
    valid_v = {
        "genome_build": "GRCh38",
        "chrom": "chr7",
        "pos": 117_120_016,
        "ref": "A",
        "alt": "G",
        "rsid": "rs75527207",
    }
    # Failing positive control: verifier rejects even valid input
    fail_pos_report = probe_variant_verifier(lambda v: False, valid_v)
    assert fail_pos_report.passed is False
    assert fail_pos_report.reason_code == "POSITIVE_CONTROL_FAILED"
    assert fail_pos_report.mutations_tested == 0

    # Negative Control: Stub verifier that always returns True -> MUST HALT!
    stub_report = probe_variant_verifier(lambda v: True, valid_v)
    assert stub_report.passed is False
    assert stub_report.reason_code == VariantHaltCode.HALT_VERIFIER_ACCEPTED_MUTATED_INPUT.value
    assert len(stub_report.accepted_mutants) == 9
    assert stub_report.mutations_tested == 9

    # Positive Control: Real VariantContract.validate -> Rejects all 9/9 mutations!
    real_report = probe_variant_verifier(
        lambda v: VariantContract.validate(v).is_valid, valid_v
    )
    assert real_report.passed is True
    assert real_report.reason_code == "SOUND_AND_DIFFERENTIATED"
    assert real_report.mutations_rejected == 9
    assert real_report.mutations_tested == 9
    assert real_report.accepted_mutants == ()


def test_3_t3_wet_lab_and_clinical_boundary_fails_closed() -> None:
    assert (
        BioScopeGate.authorize_bio_operation("evidence.collect_dbsnp")
        == BioScopeTier.T2_PARALLEL_EVIDENCE_PIPELINE
    )
    assert (
        BioScopeGate.authorize_bio_operation("lib.sequence_align")
        == BioScopeTier.T1_VETTED_LIBRARY
    )
    assert (
        BioScopeGate.authorize_bio_operation("lookup.gene_symbol")
        == BioScopeTier.T0_INLINE_LOOKUP
    )
    for forbidden_tool in (
        "crispr.transfect",
        "crispr.execute_edit",
        "opentrons.pipette",
        "dna.synthesize_oligo",
        "clinical.issue_diagnosis",
        "patient.prescribe_therapy",
    ):
        caught = False
        try:
            BioScopeGate.authorize_bio_operation(forbidden_tool)
        except CapabilityUnavailableError as exc:
            if "HALT_T3_WET_LAB_OR_CLINICAL_BOUNDARY" in str(exc):
                caught = True
        assert caught is True, f"Failed to block T3 tool {forbidden_tool}"


def test_4_end_to_end_7_source_gate_eo1_anti_harking_and_reproducible_bundle() -> None:
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    v_res = VariantContract.validate(
        {
            "genome_build": "GRCh38",
            "chrom": "chr7",
            "pos": 117_120_016,
            "ref": "A",
            "alt": "G",
            "rsid": "rs75527207",
        }
    )
    assert v_res.normalized is not None
    norm_v = v_res.normalized

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        latch = EO1BioEvidenceLatch(tmp_path / "ledger", priv)
        cart = BioContextCart(tmp_path / "archive")

        # 1. Timestamp hypothesis in EO1 BEFORE fetching evidence
        op_id, hyp_ts = latch.record_hypothesis_before_fetch(
            norm_v,
            "Prioritize chr7:117120016 A>G for regulatory and CFTR pathway review.",
        )

        # 2. Collect from all 7 typed sources (timestamps strictly >= hyp_ts)
        records = [
            build_verified_evidence_record(
                "dbsnp_b157",
                "Build157",
                {"rsid": "rs75527207", "maf_global_bps": 12},
                ["Population allele frequencies vary by ancestry."],
                fetched_at_ns=hyp_ts + 100,
            ),
            build_verified_evidence_record(
                "alphagenome_atlas",
                "2026-09-08",
                {
                    "avi_phred": 22,
                    "component_scores": {
                        "coding_missense": 19,
                        "noncoding_regulatory": 24,
                        "phastcons_470way": 21,
                        "zoonomia_241way": 20,
                    },
                },
                ["AVI is a prioritization signal (nominal eQTL Spearman rho <= 0.138)."],
                fetched_at_ns=hyp_ts + 200,
            ),
            build_verified_evidence_record(
                "encode_ccre",
                "ENCODE4_2348854",
                {"ccre_id": "EH38E2591104", "ccre_overlap": True, "class": "dELS"},
                ["Biosample-agnostic cCRE overlap does not prove tissue activity."],
                fetched_at_ns=hyp_ts + 300,
            ),
            build_verified_evidence_record(
                "jaspar_2026",
                "JASPAR2026_DeepTF",
                {"motif_id": "MA0137.4", "tf_name": "STAT1", "motif_delta_bps": 3400},
                ["In-silico motif delta requires ChIP-seq / MPRA confirmation."],
                fetched_at_ns=hyp_ts + 400,
            ),
            build_verified_evidence_record(
                "ucsc_conservation",
                "PhastCons470_MostConserved",
                {"most_conserved_overlap": True, "phastcons_470_bps": 9400},
                ["Evolutionary conservation does not specify directional phenotype."],
                fetched_at_ns=hyp_ts + 500,
            ),
            build_verified_evidence_record(
                "alphafold_db",
                "AFDB_v4",
                {"uniprot_id": "P13569", "plddt_score": 88, "ddg_destabilizing_x100": 210},
                ["Static structure does not model allosteric or induced-fit dynamics."],
                fetched_at_ns=hyp_ts + 600,
            ),
            build_verified_evidence_record(
                "reactome_pathway",
                "v97.0",
                {"pathway_id": "R-HSA-5678895", "fdr_method": "Benjamini-Hochberg", "bh_fdr_bps": 120},
                ["Pathway enrichment reflects gene-level membership."],
                fetched_at_ns=hyp_ts + 700,
            ),
        ]

        # 3. Score claims (strictly SUPPORTS / REFUTES / UNKNOWN)
        verdicts = BioEvidenceScorer.score_claims(norm_v, records)
        assert len(verdicts) == 2
        assert verdicts[0].verdict == ClaimDisposition.SUPPORTS
        assert verdicts[0].confidence_bps == 82 * 100
        assert verdicts[1].verdict == ClaimDisposition.SUPPORTS
        assert verdicts[1].confidence_bps == 78 * 100

        # 4. Archive in BioContextCart and verify lossless byte recovery
        cards = [cart.archive_and_create_card(r) for r in records]
        for r, c in zip(records, cards):
            recovered = cart.recover_raw_bytes(c.content_digest)
            assert recovered == r.raw_response_bytes

        # 5. Seal reproducible bundle and verify Ed25519 signature + clean-room determinism
        bundle_1 = latch.bind_evidence_and_seal_bundle(op_id, norm_v, records, verdicts, cards)
        bundle_2 = latch.bind_evidence_and_seal_bundle(op_id, norm_v, records, verdicts, cards)
        assert bundle_1.bundle_digest == bundle_2.bundle_digest
        assert EO1BioEvidenceLatch.verify_bundle_signature(bundle_1, pub) is True

        # 6. Anti-HARKing Negative Control: Evidence fetched BEFORE hypothesis timestamp -> MUST HALT!
        backdated_record = build_verified_evidence_record(
            "dbsnp_b157",
            "Build157",
            {"rsid": "rs75527207", "maf_global_bps": 12},
            ["Backdated test"],
            fetched_at_ns=hyp_ts - 1,
        )
        caught_harking = False
        try:
            latch.bind_evidence_and_seal_bundle(
                op_id, norm_v, [backdated_record], verdicts, cards
            )
        except RuntimeError as exc:
            if "HALT_RETROACTIVE_HYPOTHESIS_TIMESTAMP_VIOLATION" in str(exc):
                caught_harking = True
        assert caught_harking is True


def test_5_epistemic_purity() -> None:
    # Scan files for forbidden promotional words
    forbidden_tokens = [
        "guaran" + "teed",
        "guaran" + "tee",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "unassail" + "able",
        "immu" + "ne",
        "unhack" + "able",
    ]
    target_files = [
        Path("src/bio_variant_contract.py"),
        Path("src/bio_evidence_gate.py"),
        Path("tests/test_variant_validation.py"),
    ]
    for p in target_files:
        if not p.exists():
            continue
        content = p.read_text(encoding="utf-8").lower()
        for tok in forbidden_tokens:
            assert tok not in content, f"Forbidden term '{tok}' found in {p}"


def test_6_all_chromosome_boundaries_and_assembly_lengths() -> None:
    # Tests that every chromosome length against independently pinned ground-truth reference lengths
    for build in ("GRCh37", "GRCh38"):
        for chrom, length in NCBI_REF_LENGTHS[build].items():
            # pos = length (exact end of chromosome) is valid
            valid_end = VariantContract.validate(
                {"genome_build": build, "chrom": chrom, "pos": length, "ref": "A", "alt": "T"}
            )
            assert valid_end.is_valid is True, f"Failed at valid end {build} {chrom}:{length}"
            assert valid_end.halt_code == VariantHaltCode.VALID

            # pos = length + 1 is out of bounds
            oob = VariantContract.validate(
                {"genome_build": build, "chrom": chrom, "pos": length + 1, "ref": "A", "alt": "T"}
            )
            assert oob.is_valid is False
            assert oob.halt_code == VariantHaltCode.HALT_COORDINATE_OUT_OF_BOUNDS

    # Test pos = 0 is out of bounds
    res_zero = VariantContract.validate(
        {"genome_build": "GRCh38", "chrom": "chr1", "pos": 0, "ref": "A", "alt": "T"}
    )
    assert res_zero.is_valid is False
    assert res_zero.halt_code == VariantHaltCode.HALT_COORDINATE_OUT_OF_BOUNDS

    # Test non-integer pos (e.g. bool or str)
    res_bool = VariantContract.validate(
        {"genome_build": "GRCh38", "chrom": "chr1", "pos": True, "ref": "A", "alt": "T"}
    )
    assert res_bool.is_valid is False
    assert res_bool.halt_code == VariantHaltCode.HALT_COORDINATE_OUT_OF_BOUNDS

    # Test invalid build
    res_bad_build = VariantContract.validate(
        {"genome_build": "hg19", "chrom": "chr1", "pos": 100, "ref": "A", "alt": "T"}
    )
    assert res_bad_build.is_valid is False
    assert res_bad_build.halt_code == VariantHaltCode.HALT_GENOME_BUILD_MISMATCH

    # Test invalid chrom
    res_bad_chrom = VariantContract.validate(
        {"genome_build": "GRCh38", "chrom": "chr99", "pos": 100, "ref": "A", "alt": "T"}
    )
    assert res_bad_chrom.is_valid is False
    assert res_bad_chrom.halt_code == VariantHaltCode.HALT_INVALID_CHROMOSOME


def test_7_allele_normalization_and_syntax() -> None:
    # Test trim_minimal_alleles
    p, r, a = VariantContract.trim_minimal_alleles(100, "ATG", "AG")
    assert (p, r, a) == (100, "AT", "A")

    p, r, a = VariantContract.trim_minimal_alleles(100, "CTA", "CA")
    assert (p, r, a) == (100, "CT", "C")

    p, r, a = VariantContract.trim_minimal_alleles(100, "TAT", "GAT")
    assert (p, r, a) == (100, "T", "G")

    # Identical ref and alt
    res_ident = VariantContract.validate(
        {"genome_build": "GRCh38", "chrom": "chr1", "pos": 100, "ref": "A", "alt": "A"}
    )
    assert res_ident.is_valid is False
    assert res_ident.halt_code == VariantHaltCode.HALT_REF_ALT_IDENTICAL

    # Invalid DNA alphabet
    res_bad_bases = VariantContract.validate(
        {"genome_build": "GRCh38", "chrom": "chr1", "pos": 100, "ref": "ANN", "alt": "G"}
    )
    assert res_bad_bases.is_valid is False
    assert res_bad_bases.halt_code == VariantHaltCode.HALT_INVALID_ALLELE_BASES

    # Invalid rsID formats
    for bad_rsid in ("rs0", "rs0123", "rsABC", "rs1234567890123", "12345"):
        res_bad_rsid = VariantContract.validate(
            {
                "genome_build": "GRCh38",
                "chrom": "chr1",
                "pos": 100,
                "ref": "A",
                "alt": "T",
                "rsid": bad_rsid,
            }
        )
        assert res_bad_rsid.is_valid is False
        assert res_bad_rsid.halt_code == VariantHaltCode.HALT_INVALID_RSID_FORMAT


def test_8_canonical_json_and_digest_primitives() -> None:
    canon = canonical_json_v1({"b": 2, "a": 1})
    assert canon == b'{"a":1,"b":2}'

    # ensure_ascii=False preservation of UTF-8 characters
    canon_unicode = canonical_json_v1({"symbol": "α"})
    assert canon_unicode == '{"symbol":"α"}'.encode("utf-8")

    # Rejection of non-finite floats and non-string keys
    with pytest.raises(ValueError, match="ERR_NON_FINITE_FLOAT"):
        canonical_json_v1({"nan": float("nan")})
    with pytest.raises(ValueError, match="ERR_NON_FINITE_FLOAT"):
        canonical_json_v1({"inf": float("inf")})
    with pytest.raises(ValueError, match="ERR_NON_STRING_KEY"):
        canonical_json_v1({123: "int_key"})
    with pytest.raises(ValueError):
        canonical_json_v1({"tup_nan": (float("nan"),)})

    d = sha256_prefixed(b"test")
    assert d.startswith("sha256:")
    assert len(d) == 7 + 64


def test_9_evidence_record_schema_and_integrity_checks() -> None:
    # Corrupted content digest
    corrupt_rec = EvidenceRecord(
        source_name="test_src",
        source_version="v1",
        fetched_at_ns=1000,
        raw_response_bytes=b"actual_data",
        content_digest="sha256:0000000000000000000000000000000000000000000000000000000000000000",
        normalized_evidence={},
        limitations=(),
    )
    with pytest.raises(RuntimeError, match="HALT_SOURCE_DIGEST_MISMATCH"):
        corrupt_rec.verify_integrity()

    # AlphaGenome missing required sub-scores
    with pytest.raises(RuntimeError, match="HALT_ALPHAGENOME_MISSING_COMPONENT_SCORES"):
        build_verified_evidence_record(
            "alphagenome_atlas",
            "v1",
            {"avi_phred": 25, "component_scores": {"coding_missense": 20}},
            [],
        )

    # AlphaFold missing plddt_score
    with pytest.raises(RuntimeError, match="HALT_ALPHAFOLD_MISSING_PLDDT_CONFIDENCE"):
        build_verified_evidence_record(
            "alphafold_db", "v1", {"uniprot_id": "P12345"}, []
        )

    # Reactome missing BH FDR method
    with pytest.raises(RuntimeError, match="HALT_REACTOME_MISSING_BH_FDR_CORRECTION"):
        build_verified_evidence_record(
            "reactome_pathway",
            "v1",
            {"pathway_id": "R-1", "fdr_method": "Bonferroni", "bh_fdr_bps": 100},
            [],
        )


def test_10_evidence_scorer_refutes_unknown_and_banned_claims() -> None:
    v_res = VariantContract.validate(
        {"genome_build": "GRCh38", "chrom": "chr7", "pos": 1000, "ref": "A", "alt": "G"}
    )
    assert v_res.normalized is not None
    norm_v = v_res.normalized

    # Case 1: Refutes for regulatory impact
    refuting_records = [
        build_verified_evidence_record(
            "alphagenome_atlas",
            "v1",
            {
                "avi_phred": 5,
                "component_scores": {
                    "coding_missense": 2,
                    "noncoding_regulatory": 3,
                    "phastcons_470way": 1,
                    "zoonomia_241way": 2,
                },
            },
            [],
        ),
        build_verified_evidence_record(
            "encode_ccre", "v1", {"ccre_overlap": False}, []
        ),
        build_verified_evidence_record(
            "jaspar_2026", "v1", {"motif_delta_bps": 500}, []
        ),
        build_verified_evidence_record(
            "ucsc_conservation", "v1", {"phastcons_470_bps": 1000}, []
        ),
    ]
    verdicts = BioEvidenceScorer.score_claims(norm_v, refuting_records)
    assert verdicts[0].verdict == ClaimDisposition.REFUTES
    assert verdicts[0].confidence_bps == 80 * 100

    # Jaspar and UCSC boundary checks:
    # 1999 motif delta -> conflicting; 2000 -> supporting
    jas_under = build_verified_evidence_record("jaspar_2026", "v1", {"motif_delta_bps": 1999}, [])
    jas_exact = build_verified_evidence_record("jaspar_2026", "v1", {"motif_delta_bps": 2000}, [])
    jas_none = build_verified_evidence_record("jaspar_2026", "v1", {}, [])
    ucsc_under = build_verified_evidence_record("ucsc_conservation", "v1", {"phastcons_470_bps": 6999}, [])
    ucsc_exact = build_verified_evidence_record("ucsc_conservation", "v1", {"phastcons_470_bps": 7000}, [])
    ucsc_none = build_verified_evidence_record("ucsc_conservation", "v1", {}, [])

    v_jas_under = BioEvidenceScorer.score_claims(norm_v, [jas_under])
    assert "jaspar_2026" in v_jas_under[0].conflicting_sources
    v_jas_exact = BioEvidenceScorer.score_claims(norm_v, [jas_exact])
    assert "jaspar_2026" in v_jas_exact[0].supporting_sources
    v_jas_none = BioEvidenceScorer.score_claims(norm_v, [jas_none])
    assert "jaspar_2026" in v_jas_none[0].conflicting_sources

    v_ucsc_under = BioEvidenceScorer.score_claims(norm_v, [ucsc_under])
    assert "ucsc_conservation" in v_ucsc_under[0].conflicting_sources
    v_ucsc_exact = BioEvidenceScorer.score_claims(norm_v, [ucsc_exact])
    assert "ucsc_conservation" in v_ucsc_exact[0].supporting_sources
    v_ucsc_none = BioEvidenceScorer.score_claims(norm_v, [ucsc_none])
    assert "ucsc_conservation" in v_ucsc_none[0].conflicting_sources

    # Case 2: Unknown for mixed regulatory evidence
    mixed_records = [
        build_verified_evidence_record(
            "alphagenome_atlas",
            "v1",
            {
                "avi_phred": 25,
                "component_scores": {
                    "coding_missense": 20,
                    "noncoding_regulatory": 20,
                    "phastcons_470way": 20,
                    "zoonomia_241way": 20,
                },
            },
            [],
        ),
        build_verified_evidence_record(
            "encode_ccre", "v1", {"ccre_overlap": False}, []
        ),
    ]
    mixed_verdicts = BioEvidenceScorer.score_claims(norm_v, mixed_records)
    assert mixed_verdicts[0].verdict == ClaimDisposition.UNKNOWN
    assert mixed_verdicts[0].confidence_bps == 45 * 100

    # Case 3: Structural refutes (plddt >= 70, ddg < 150, reactome fdr > 500)
    struct_refute_records = [
        build_verified_evidence_record(
            "alphafold_db",
            "v1",
            {"plddt_score": 80, "ddg_destabilizing_x100": 50},
            [],
        ),
        build_verified_evidence_record(
            "reactome_pathway",
            "v1",
            {"fdr_method": "Benjamini-Hochberg", "bh_fdr_bps": 800},
            [],
        ),
    ]
    str_ref_verdicts = BioEvidenceScorer.score_claims(norm_v, struct_refute_records)
    assert str_ref_verdicts[1].verdict == ClaimDisposition.REFUTES
    assert str_ref_verdicts[1].confidence_bps == 75 * 100

    # Case 4: Structural unknown due to low plddt
    low_plddt_records = [
        build_verified_evidence_record(
            "alphafold_db",
            "v1",
            {"plddt_score": 50, "ddg_destabilizing_x100": 200},
            [],
        ),
    ]
    low_plddt_verdicts = BioEvidenceScorer.score_claims(norm_v, low_plddt_records)
    assert low_plddt_verdicts[1].verdict == ClaimDisposition.UNKNOWN
    assert low_plddt_verdicts[1].confidence_bps == 40 * 100
    assert "alphafold_db_low_plddt" in low_plddt_verdicts[1].conflicting_sources

    # Case 5: Structural conflict (1 supporting, 1 conflicting) -> must be UNKNOWN
    conflict_records = [
        build_verified_evidence_record(
            "alphafold_db",
            "v1",
            {"plddt_score": 85, "ddg_destabilizing_x100": 200},  # supporting
            [],
        ),
        build_verified_evidence_record(
            "reactome_pathway",
            "v1",
            {"fdr_method": "Benjamini-Hochberg", "bh_fdr_bps": 900},  # conflicting
            [],
        ),
    ]
    conflict_verdicts = BioEvidenceScorer.score_claims(norm_v, conflict_records)
    assert conflict_verdicts[1].verdict == ClaimDisposition.UNKNOWN
    assert conflict_verdicts[1].confidence_bps == 40 * 100

    # Single supporting source (len == 1, conflicting == 0) must still be UNKNOWN (kills BOOL_SWAP on lines 258 & 309)
    assert v_jas_exact[0].verdict == ClaimDisposition.UNKNOWN
    assert BioEvidenceScorer.score_claims(norm_v, [conflict_records[0]])[1].verdict == ClaimDisposition.UNKNOWN

    # Exact 3 supporting / 3 conflicting regulatory sources (kills CONST_PERTURB 3->4 on lines 258 & 261)
    reg_3_supp = [
        mixed_records[0],
        jas_exact,
        ucsc_exact,
    ]
    assert BioEvidenceScorer.score_claims(norm_v, reg_3_supp)[0].verdict == ClaimDisposition.SUPPORTS
    assert BioEvidenceScorer.score_claims(norm_v, refuting_records[:3])[0].verdict == ClaimDisposition.REFUTES

    # Exact structural boundaries: plddt=70, ddg=150 (supporting), ddg=149 (conflicting), bh_fdr_bps=500 (supporting), bh_fdr_bps=501 (conflicting)
    af_exact = build_verified_evidence_record(
        "alphafold_db", "v1", {"plddt_score": 70, "ddg_destabilizing_x100": 150}, []
    )
    af_under_ddg = build_verified_evidence_record(
        "alphafold_db", "v1", {"plddt_score": 70, "ddg_destabilizing_x100": 149}, []
    )
    react_500 = build_verified_evidence_record(
        "reactome_pathway", "v1", {"fdr_method": "Benjamini-Hochberg", "bh_fdr_bps": 500}, []
    )
    react_501 = build_verified_evidence_record(
        "reactome_pathway", "v1", {"fdr_method": "Benjamini-Hochberg", "bh_fdr_bps": 501}, []
    )
    assert BioEvidenceScorer.score_claims(norm_v, [af_exact, react_500])[1].verdict == ClaimDisposition.SUPPORTS
    assert BioEvidenceScorer.score_claims(norm_v, [af_under_ddg, react_501])[1].verdict == ClaimDisposition.REFUTES

    # Line 336: BANNED_CLINICAL_OVERCLAIMS halt check
    import src.bio_evidence_gate as _beg

    orig_banned = _beg.BANNED_CLINICAL_OVERCLAIMS
    try:
        _beg.BANNED_CLINICAL_OVERCLAIMS = ("cis-regulatory",)
        with pytest.raises(RuntimeError, match="HALT_BANNED_CLINICAL_OVERCLAIM"):
            BioEvidenceScorer.score_claims(norm_v, [conflict_records[0]])
    finally:
        _beg.BANNED_CLINICAL_OVERCLAIMS = orig_banned


def test_11_biocontext_cart_budget_and_tamper(monkeypatch) -> None:
    import fcntl as _fcntl
    import os as _os
    import sys as _sys
    import src.bio_evidence_gate as _beg

    with tempfile.TemporaryDirectory() as tmp:
        cart = BioContextCart(Path(tmp))

        # Line 73: durable_fsync_fd on non-darwin must call os.fsync, not fcntl.fcntl
        probe_file = Path(tmp) / "fsync_probe.bin"
        fd = _os.open(str(probe_file), _os.O_CREAT | _os.O_WRONLY, 0o600)
        try:
            monkeypatch.setattr(_sys, "platform", "linux")
            monkeypatch.setattr(_fcntl, "fcntl", lambda *a: (_ for _ in ()).throw(RuntimeError("fcntl on linux")))
            _beg.durable_fsync_fd(fd)
        finally:
            monkeypatch.undo()
            _os.close(fd)

        # Test context card budget overflow (> 500 tokens)
        huge_rec = build_verified_evidence_record(
            "dbsnp_b157",
            "Build157",
            {"huge_array": ["x" * 50] * 50},
            ["Limitation 1"],
        )
        with pytest.raises(RuntimeError, match="HALT_CONTEXT_CARD_EXCEEDS_BUDGET"):
            cart.archive_and_create_card(huge_rec)

        # Normal record
        rec = build_verified_evidence_record(
            "dbsnp_b157", "Build157", {"rsid": "rs1"}, ["Limitation"]
        )
        card = cart.archive_and_create_card(rec)
        assert card.token_estimate >= 1

        # BioContextCard is frozen
        with pytest.raises(FrozenInstanceError):
            card.token_estimate = 999  # type: ignore

        # Missing archive file
        with pytest.raises(FileNotFoundError, match="ERR_ARCHIVE_MISSING"):
            cart.recover_raw_bytes("sha256:1111111111111111111111111111111111111111111111111111111111111111")

        # Line 402: split(":", 1)[1] with colon in hex_part
        (Path(tmp) / "abc:def.json").write_bytes(b"corrupt")
        with pytest.raises(RuntimeError, match="HALT_ARCHIVE_CORRUPTED"):
            cart.recover_raw_bytes("sha256:abc:def")

        # Corrupted archive file
        archive_path = Path(card.archive_path)
        archive_path.write_bytes(b"tampered_content")
        with pytest.raises(RuntimeError, match="HALT_ARCHIVE_CORRUPTED"):
            cart.recover_raw_bytes(card.content_digest)


def test_12_eo1_latch_unlatched_missing_and_tampered_signature(monkeypatch) -> None:
    import os as _os

    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    wrong_pub = Ed25519PrivateKey.generate().public_key()

    v_res = VariantContract.validate(
        {"genome_build": "GRCh38", "chrom": "chr7", "pos": 1000, "ref": "A", "alt": "G"}
    )
    assert v_res.normalized is not None
    norm_v = v_res.normalized

    with tempfile.TemporaryDirectory() as tmp:
        latch = EO1BioEvidenceLatch(Path(tmp) / "ledger", priv)
        # Re-instantiate on existing dir tests exist_ok=True
        latch_dup = EO1BioEvidenceLatch(Path(tmp) / "ledger", priv)

        # Missing ledger file raises
        with pytest.raises(RuntimeError, match="HALT_MISSING_PRE_FETCH_HYPOTHESIS_LEDGER"):
            latch.bind_evidence_and_seal_bundle("op:nonexistent", norm_v, [], [], [])

        # Verify 1-byte chunked partial os.write succeeds and 0-byte os.write raises ERR_SHORT_WRITE (line 473)
        real_write = _os.write
        calls = []

        def chunked_write(fd: int, data: bytes) -> int:
            calls.append(len(data))
            if len(calls) == 1:
                return real_write(fd, data[:1])
            return real_write(fd, data)

        monkeypatch.setattr(_os, "write", chunked_write)
        op_id, hyp_ts = latch.record_hypothesis_before_fetch(norm_v, "Test hypothesis")
        monkeypatch.undo()
        assert len(calls) >= 2

        monkeypatch.setattr(_os, "write", lambda fd, data: 0)
        with pytest.raises(IOError, match="ERR_SHORT_WRITE"):
            latch.record_hypothesis_before_fetch(norm_v, "Short write fail")
        monkeypatch.undo()
        import stat
        assert stat.S_IMODE(latch.ledger_path.stat().st_mode) == 6 * 64

        # Unlatched hypothesis (non-matching op_id)
        with pytest.raises(RuntimeError, match="HALT_UNLATCHED_HYPOTHESIS"):
            latch.bind_evidence_and_seal_bundle("op:other", norm_v, [], [], [])

        # Seal valid bundle
        bundle = latch.bind_evidence_and_seal_bundle(op_id, norm_v, [], [], [])
        assert EO1BioEvidenceLatch.verify_bundle_signature(bundle, pub) is True
        # Wrong key fails
        assert EO1BioEvidenceLatch.verify_bundle_signature(bundle, wrong_pub) is False

        # Altered bundle digest fails verification
        tampered_bundle = ReproducibleBioEvidenceBundle(
            bio_evidence_version=bundle.bio_evidence_version,
            operation_id=bundle.operation_id,
            variant=bundle.variant,
            hypothesis=bundle.hypothesis,
            hypothesis_recorded_at_ns=bundle.hypothesis_recorded_at_ns,
            claims=bundle.claims,
            context_cards=bundle.context_cards,
            limitations=bundle.limitations,
            receipt_tier=bundle.receipt_tier,
            bundle_digest="sha256:0000000000000000000000000000000000000000000000000000000000000000",
            ed25519_signature_b64=bundle.ed25519_signature_b64,
        )
        assert EO1BioEvidenceLatch.verify_bundle_signature(tampered_bundle, pub) is False

        # Bundle is frozen
        with pytest.raises(FrozenInstanceError):
            bundle.receipt_tier = "MODIFIED"  # type: ignore
