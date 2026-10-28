#!/usr/bin/env python3
# File: tests/test_sources_alphagenome_encode.py
"""
Deterministic falsification and verification test suite for
AlphaGenome Atlas and ENCODE4 cCRE source adapters.

Tests:
1. AlphaGenome valid parsing, mandatory sub-score unpacking, and integer bps conversion.
2. AlphaGenome fails closed on missing, None, boolean, string, or out-of-bounds sub-scores.
3. AlphaGenome fails closed on non-GRCh38 build mismatch.
4. AlphaGenome coordinate mismatch triggers HALT_LOOKUP_PROVENANCE_UNBOUND.
5. ENCODE valid cCRE parsing, overlap containment, and biochemical classification.
6. ENCODE invalid or fabricated cCRE ID fails closed with HALT_ENCODE_INVALID_CCRE_ID.
7. ENCODE interval containment violation fails closed with HALT_LOOKUP_PROVENANCE_UNBOUND.
8. ENCODE fails closed on non-GRCh38 build mismatch.
9. ENCODE unparseable payload or invalid schema fails closed.
10. Protocol conformance: fetch() yields verified EvidenceRecord with preserved raw bytes.
11. Epistemic purity: zero banned promotional terms across newly added source modules.
"""

from pathlib import Path
from typing import Any, Dict

import pytest

from src.bio_variant_contract import (
    NormalizedVariant,
    VariantContract,
    canonical_json_v1,
    sha256_prefixed,
)
from src.sources.alphagenome import AlphaGenomeAdapter
from src.sources.base import SourceHaltCode, SourceQueryResult
from src.sources.encode import EncodeCcreAdapter


def get_grch38_cftr_variant() -> NormalizedVariant:
    res = VariantContract.validate(
        {
            "genome_build": "GRCh38",
            "chrom": "chr7",
            "pos": 117_120_016,
            "ref": "A",
            "alt": "G",
            "rsid": "rs75527207",
        }
    )
    assert res.normalized is not None
    return res.normalized


def get_grch37_cftr_variant() -> NormalizedVariant:
    res = VariantContract.validate(
        {
            "genome_build": "GRCh37",
            "chrom": "chr7",
            "pos": 117_559_590,
            "ref": "A",
            "alt": "G",
            "rsid": "rs75527207",
        }
    )
    assert res.normalized is not None
    return res.normalized


# ==============================================================================
# AlphaGenome Tests
# ==============================================================================


def test_1_alphagenome_valid_parsing_and_subscores() -> None:
    variant = get_grch38_cftr_variant()
    payload = {
        "chrom": variant.chrom,
        "pos": variant.pos,
        "ref": variant.ref,
        "alt": variant.alt,
        "avi_phred": 24.50,
        "component_scores": {
            "coding_missense": 0.8250,
            "noncoding_regulatory": 0.1200,
            "phastcons_470way": 0.9400,
            "zoonomia_241way": 0.8850,
        },
        "build": "v2026-09-08",
    }
    raw = canonical_json_v1(payload)

    result = AlphaGenomeAdapter.parse_alphagenome_json(raw, variant, query_latency_ms=2)
    result.verify_integrity()

    assert result.source_name == "alphagenome_atlas"
    assert result.source_version == "v2026-09-08"
    assert result.query_latency_ms == 2

    data = result.parsed_data
    assert data["avi_phred_x100"] == 2450
    sub_scores = data["component_scores_bps"]
    assert sub_scores["coding_missense"] == 8250
    assert sub_scores["noncoding_regulatory"] == 1200
    assert sub_scores["phastcons_470way"] == 9400
    assert sub_scores["zoonomia_241way"] == 8850

    # Also test with integer basis points inputs
    payload_bps = {
        "chrom": variant.chrom,
        "pos": variant.pos,
        "ref": variant.ref,
        "alt": variant.alt,
        "avi_phred": 3000,
        "component_scores": {
            "coding_missense": 5000,
            "noncoding_regulatory": 1000,
            "phastcons_470way": 10000,
            "zoonomia_241way": 0,
        },
    }
    res_bps = AlphaGenomeAdapter.parse_alphagenome_json(canonical_json_v1(payload_bps), variant)
    assert res_bps.parsed_data["avi_phred_x100"] == 3000
    assert res_bps.parsed_data["component_scores_bps"]["coding_missense"] == 5000
    assert res_bps.parsed_data["component_scores_bps"]["zoonomia_241way"] == 0

    # Test root-level sub-scores fallback
    payload_flat = {
        "chrom": variant.chrom,
        "pos": variant.pos,
        "ref": variant.ref,
        "alt": variant.alt,
        "avi_phred": 12.0,
        "coding_missense": 0.5,
        "noncoding_regulatory": 0.5,
        "phastcons_470way": 0.5,
        "zoonomia_241way": 0.5,
    }
    res_flat = AlphaGenomeAdapter.parse_alphagenome_json(canonical_json_v1(payload_flat), variant)
    assert res_flat.parsed_data["component_scores_bps"]["coding_missense"] == 5000


def test_2_alphagenome_missing_subscore_fails_closed() -> None:
    variant = get_grch38_cftr_variant()
    base_scores = {
        "coding_missense": 0.8,
        "noncoding_regulatory": 0.2,
        "phastcons_470way": 0.9,
        "zoonomia_241way": 0.7,
    }

    # 1. Missing each mandatory score
    for key in AlphaGenomeAdapter.MANDATORY_SUB_SCORES:
        corrupted = dict(base_scores)
        del corrupted[key]
        payload = {"chrom": variant.chrom, "pos": variant.pos, "ref": variant.ref, "alt": variant.alt, "component_scores": corrupted}
        with pytest.raises(ValueError) as exc:
            AlphaGenomeAdapter.parse_alphagenome_json(canonical_json_v1(payload), variant)
        assert SourceHaltCode.HALT_ALPHAGENOME_MISSING_COMPONENT_SCORES.value in str(exc.value)

    # 2. None value
    corrupted_none = dict(base_scores)
    corrupted_none["coding_missense"] = None
    with pytest.raises(ValueError) as exc:
        AlphaGenomeAdapter.parse_alphagenome_json(canonical_json_v1({"component_scores": corrupted_none}), variant)
    assert SourceHaltCode.HALT_ALPHAGENOME_MISSING_COMPONENT_SCORES.value in str(exc.value)

    # 3. Boolean value
    corrupted_bool = dict(base_scores)
    corrupted_bool["zoonomia_241way"] = True
    with pytest.raises(ValueError) as exc:
        AlphaGenomeAdapter.parse_alphagenome_json(canonical_json_v1({"component_scores": corrupted_bool}), variant)
    assert SourceHaltCode.HALT_ALPHAGENOME_MISSING_COMPONENT_SCORES.value in str(exc.value)

    # 4. Out of bounds float
    corrupted_high_float = dict(base_scores)
    corrupted_high_float["phastcons_470way"] = 1.05
    with pytest.raises(ValueError) as exc:
        AlphaGenomeAdapter.parse_alphagenome_json(canonical_json_v1({"component_scores": corrupted_high_float}), variant)
    assert SourceHaltCode.HALT_ALPHAGENOME_MISSING_COMPONENT_SCORES.value in str(exc.value)

    # 5. Out of bounds int
    corrupted_high_int = dict(base_scores)
    corrupted_high_int["noncoding_regulatory"] = 10001
    with pytest.raises(ValueError) as exc:
        AlphaGenomeAdapter.parse_alphagenome_json(canonical_json_v1({"component_scores": corrupted_high_int}), variant)
    assert SourceHaltCode.HALT_ALPHAGENOME_MISSING_COMPONENT_SCORES.value in str(exc.value)

    # 6. Non-numeric string
    corrupted_str = dict(base_scores)
    corrupted_str["coding_missense"] = "0.8"
    with pytest.raises(ValueError) as exc:
        AlphaGenomeAdapter.parse_alphagenome_json(canonical_json_v1({"component_scores": corrupted_str}), variant)
    assert SourceHaltCode.HALT_ALPHAGENOME_MISSING_COMPONENT_SCORES.value in str(exc.value)

    # 7. Unparseable JSON and non-dict payload root
    with pytest.raises(ValueError) as exc_malformed:
        AlphaGenomeAdapter.parse_alphagenome_json(b"not json {", variant)
    assert SourceHaltCode.HALT_SOURCE_RESPONSE_UNPARSEABLE.value in str(exc_malformed.value)

    with pytest.raises(ValueError) as exc_nondict:
        AlphaGenomeAdapter.parse_alphagenome_json(b"[]", variant)
    assert SourceHaltCode.HALT_SOURCE_RESPONSE_UNPARSEABLE.value in str(exc_nondict.value)

    # 8. Omitted avi_phred and boolean avi_phred
    payload_no_avi = {
        "chrom": variant.chrom,
        "pos": variant.pos,
        "ref": variant.ref,
        "alt": variant.alt,
        "component_scores": base_scores,
    }
    res_no_avi = AlphaGenomeAdapter.parse_alphagenome_json(canonical_json_v1(payload_no_avi), variant)
    assert res_no_avi.parsed_data["avi_phred_x100"] == 0
    assert res_no_avi.query_latency_ms == 1

    payload_bool_avi = dict(payload_no_avi)
    payload_bool_avi["avi_phred"] = True
    res_bool_avi = AlphaGenomeAdapter.parse_alphagenome_json(canonical_json_v1(payload_bool_avi), variant)
    assert res_bool_avi.parsed_data["avi_phred_x100"] == 0


def test_3_alphagenome_genome_build_mismatch() -> None:
    variant_b37 = get_grch37_cftr_variant()
    adapter = AlphaGenomeAdapter()
    assert adapter.offline_only is True

    with pytest.raises(ValueError) as exc1:
        adapter.query_raw(variant_b37)
    assert SourceHaltCode.HALT_ALPHAGENOME_BUILD_UNSUPPORTED.value in str(exc1.value)

    with pytest.raises(ValueError) as exc2:
        AlphaGenomeAdapter.parse_alphagenome_json(b"{}", variant_b37)
    assert SourceHaltCode.HALT_ALPHAGENOME_BUILD_UNSUPPORTED.value in str(exc2.value)


def test_4_alphagenome_coordinate_mismatch() -> None:
    variant = get_grch38_cftr_variant()
    payload = {
        "chrom": variant.chrom,
        "pos": variant.pos + 10,  # altered coordinate
        "ref": variant.ref,
        "alt": variant.alt,
        "component_scores": {
            "coding_missense": 0.5,
            "noncoding_regulatory": 0.5,
            "phastcons_470way": 0.5,
            "zoonomia_241way": 0.5,
        },
    }
    with pytest.raises(ValueError) as exc:
        AlphaGenomeAdapter.parse_alphagenome_json(canonical_json_v1(payload), variant)
    assert SourceHaltCode.HALT_LOOKUP_PROVENANCE_UNBOUND.value in str(exc.value)


# ==============================================================================
# ENCODE cCRE Tests
# ==============================================================================


def test_5_encode_valid_parsing_and_overlap() -> None:
    variant = get_grch38_cftr_variant()
    # 1. Overlapping cCRE
    payload_overlap = {
        "chrom": variant.chrom,
        "pos": variant.pos,
        "ccre_overlap": True,
        "ccre_id": "EH38E1524318",
        "biochemical_class": "pELS",
        "interval_start": variant.pos - 100,
        "interval_end": variant.pos + 100,
        "distance_to_tss_bp": 350,
    }
    raw = canonical_json_v1(payload_overlap)
    res = EncodeCcreAdapter.parse_encode_json(raw, variant, query_latency_ms=3)
    res.verify_integrity()

    assert res.source_name == "encode_ccre"
    assert res.source_version == "ENCODE4_v3"
    assert res.parsed_data["ccre_overlap"] is True
    assert res.parsed_data["ccre_id"] == "EH38E1524318"
    assert res.parsed_data["biochemical_class"] == "pELS"
    assert res.parsed_data["interval_start"] == variant.pos - 100
    assert res.parsed_data["interval_end"] == variant.pos + 100
    assert res.parsed_data["distance_to_tss_bp"] == 350
    assert len(res.limitations) == 3

    # 2. Non-overlapping cCRE
    payload_no_overlap = {
        "chrom": variant.chrom,
        "pos": variant.pos,
        "ccre_overlap": False,
    }
    res_no = EncodeCcreAdapter.parse_encode_json(canonical_json_v1(payload_no_overlap), variant)
    assert res_no.parsed_data["ccre_overlap"] is False
    assert res_no.parsed_data["ccre_id"] is None
    assert res_no.parsed_data["biochemical_class"] is None


def test_6_encode_invalid_ccre_id_fails_closed() -> None:
    variant = get_grch38_cftr_variant()
    bad_ccre_ids = [
        "EH38E12345678",   # 8 digits (expected 7)
        "EH38E12345",      # 5 digits
        "ccre1234567",     # wrong prefix
        "EH38EABCDEFG",    # non-digits
        "",                # empty
    ]
    for bad_id in bad_ccre_ids:
        payload = {
            "chrom": variant.chrom,
            "pos": variant.pos,
            "ccre_overlap": True,
            "ccre_id": bad_id,
            "interval_start": variant.pos - 10,
            "interval_end": variant.pos + 10,
        }
        with pytest.raises(ValueError) as exc:
            EncodeCcreAdapter.parse_encode_json(canonical_json_v1(payload), variant)
        assert SourceHaltCode.HALT_ENCODE_INVALID_CCRE_ID.value in str(exc.value)


def test_7_encode_interval_containment_violation() -> None:
    variant = get_grch38_cftr_variant()
    # Interval strictly before variant
    payload_before = {
        "chrom": variant.chrom,
        "pos": variant.pos,
        "ccre_overlap": True,
        "ccre_id": "EH38E1524318",
        "interval_start": variant.pos - 500,
        "interval_end": variant.pos - 100,
    }
    with pytest.raises(ValueError) as exc:
        EncodeCcreAdapter.parse_encode_json(canonical_json_v1(payload_before), variant)
    assert SourceHaltCode.HALT_LOOKUP_PROVENANCE_UNBOUND.value in str(exc.value)

    # Missing interval bounds on overlap
    payload_no_bounds = {
        "chrom": variant.chrom,
        "pos": variant.pos,
        "ccre_overlap": True,
        "ccre_id": "EH38E1524318",
    }
    with pytest.raises(ValueError) as exc2:
        EncodeCcreAdapter.parse_encode_json(canonical_json_v1(payload_no_bounds), variant)
    assert SourceHaltCode.HALT_SOURCE_RESPONSE_UNPARSEABLE.value in str(exc2.value)


def test_8_encode_genome_build_mismatch() -> None:
    variant_b37 = get_grch37_cftr_variant()
    adapter = EncodeCcreAdapter()
    assert adapter.offline_only is True

    with pytest.raises(ValueError) as exc1:
        adapter.query_raw(variant_b37)
    assert SourceHaltCode.HALT_ENCODE_BUILD_UNSUPPORTED.value in str(exc1.value)

    with pytest.raises(ValueError) as exc2:
        EncodeCcreAdapter.parse_encode_json(b"{}", variant_b37)
    assert SourceHaltCode.HALT_ENCODE_BUILD_UNSUPPORTED.value in str(exc2.value)


def test_9_encode_unparseable_or_invalid_schema() -> None:
    variant = get_grch38_cftr_variant()
    with pytest.raises(ValueError) as exc1:
        EncodeCcreAdapter.parse_encode_json(b"not valid json {", variant)
    assert SourceHaltCode.HALT_SOURCE_RESPONSE_UNPARSEABLE.value in str(exc1.value)

    with pytest.raises(ValueError) as exc2:
        EncodeCcreAdapter.parse_encode_json(b"[]", variant)
    assert SourceHaltCode.HALT_SOURCE_RESPONSE_UNPARSEABLE.value in str(exc2.value)

    payload_bad_bool = {"ccre_overlap": "yes"}
    with pytest.raises(ValueError) as exc3:
        EncodeCcreAdapter.parse_encode_json(canonical_json_v1(payload_bad_bool), variant)
    assert SourceHaltCode.HALT_SOURCE_RESPONSE_UNPARSEABLE.value in str(exc3.value)

    # Chromosome mismatch
    payload_bad_chrom = {
        "chrom": "chr8",
        "pos": variant.pos,
        "ccre_overlap": False,
    }
    with pytest.raises(ValueError) as exc4:
        EncodeCcreAdapter.parse_encode_json(canonical_json_v1(payload_bad_chrom), variant)
    assert SourceHaltCode.HALT_LOOKUP_PROVENANCE_UNBOUND.value in str(exc4.value)

    # Position mismatch
    payload_bad_pos = {
        "chrom": variant.chrom,
        "pos": variant.pos + 1,
        "ccre_overlap": False,
    }
    with pytest.raises(ValueError) as exc5:
        EncodeCcreAdapter.parse_encode_json(canonical_json_v1(payload_bad_pos), variant)
    assert SourceHaltCode.HALT_LOOKUP_PROVENANCE_UNBOUND.value in str(exc5.value)


def test_10_fetch_protocol_conformance() -> None:
    variant = get_grch38_cftr_variant()

    # AlphaGenome fetch
    ag_adapter = AlphaGenomeAdapter()
    ag_raw = ag_adapter.query_raw(variant)
    assert ag_raw.query_latency_ms == 1
    ag_rec = ag_adapter.fetch(variant)
    ag_rec.verify_integrity()
    assert ag_rec.source_name == "alphagenome_atlas"
    assert ag_rec.source_version == "v2026-09-08"
    assert "component_scores_bps" in ag_rec.normalized_evidence

    # ENCODE fetch
    encode_adapter = EncodeCcreAdapter()
    enc_raw = encode_adapter.query_raw(variant)
    assert enc_raw.query_latency_ms == 1
    enc_rec = encode_adapter.fetch(variant)
    enc_rec.verify_integrity()
    assert enc_rec.source_name == "encode_ccre"
    assert enc_rec.source_version == "ENCODE4_v3"
    assert enc_rec.normalized_evidence["ccre_overlap"] is True
    assert enc_rec.normalized_evidence["ccre_id"] == "EH38E1524318"
    assert enc_rec.normalized_evidence["interval_start"] == variant.pos - 150
    assert enc_rec.normalized_evidence["interval_end"] == variant.pos + 150
    assert enc_rec.normalized_evidence["distance_to_tss_bp"] == (400 + 50)


def test_11_epistemic_purity() -> None:
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
        Path("src/sources/alphagenome.py"),
        Path("src/sources/encode.py"),
        Path("tests/test_sources_alphagenome_encode.py"),
    ]
    for p in target_files:
        if not p.exists():
            continue
        content = p.read_text(encoding="utf-8").lower()
        for tok in forbidden_tokens:
            assert tok not in content, f"Forbidden promotional term '{tok}' found in {p}"
