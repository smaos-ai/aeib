#!/usr/bin/env python3
# File: tests/test_sources_dbsnp.py
"""
Unit and Falsification Test Suite for AEIB biological source adapters:
- src/sources/base.py
- src/sources/dbsnp.py
"""

from __future__ import annotations

import json

from dataclasses import FrozenInstanceError
from pathlib import Path
import pytest

from src.bio_variant_contract import (
    VariantContract,
    canonical_json_v1,
    sha256_prefixed,
)
from src.sources.base import (
    SourceHaltCode,
    SourceQueryResult,
    compute_lookup_digest,
    query_result_to_evidence_record,
)
from src.sources.dbsnp import DbSnpAdapter


def get_cftr_variant():
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


def test_1_base_protocol_and_lookup_digest() -> None:
    variant = get_cftr_variant()
    d1 = compute_lookup_digest("dbsnp_b157", variant, {"param": 1})
    d2 = compute_lookup_digest("dbsnp_b157", variant, {"param": 1})
    d3 = compute_lookup_digest("dbsnp_b157", variant, {"param": 2})

    assert d1 == d2
    assert d1 != d3
    assert d1.startswith("sha256:")

    raw = b'{"hello":"world"}'
    res = SourceQueryResult(
        source_name="test_src",
        source_version="v1",
        lookup_digest=d1,
        raw_payload_bytes=raw,
        content_digest=sha256_prefixed(raw),
        parsed_data={"hello": "world"},
        limitations=("None",),
        query_latency_ms=10,
    )
    res.verify_integrity()

    # Immutable dataclass
    with pytest.raises(FrozenInstanceError):
        res.query_latency_ms = 20  # type: ignore

    # Conversion to EvidenceRecord
    rec = query_result_to_evidence_record(res)
    assert rec.source_name == "test_src"
    assert rec.content_digest == sha256_prefixed(raw)


def test_2_dbsnp_valid_parsing_and_maf() -> None:
    variant = get_cftr_variant()
    payload = {
        "refsnp_id": "rs75527207",
        "global_maf": 0.0012,
        "ancestral_frequencies": {
            "AFR": 0.0005,
            "EUR": 0.0018,
            "EAS": 0.0001,
            "GLOBAL": 0.0012,
        },
        "build": "Build157",
        "organism": "Homo sapiens",
    }
    raw_bytes = canonical_json_v1(payload)

    # 1. Parsing with explicit latency_ms
    parsed = DbSnpAdapter.parse_dbsnp_json(raw_bytes, variant, query_latency_ms=5)
    assert parsed.source_name == "dbsnp_b157"
    assert parsed.source_version == "Build157"
    assert parsed.parsed_data["rsid"] == "rs75527207"
    assert parsed.parsed_data["maf_global_bps"] == 12
    assert parsed.parsed_data["ancestral_frequencies_bps"]["EUR"] == 18
    assert parsed.parsed_data["ancestral_frequencies_bps"]["AFR"] == 5
    assert len(parsed.limitations) == 2
    assert "dbSNP Build 157 reports observational allele counts" in parsed.limitations[0]

    # 2. Parsing without explicit latency_ms
    parsed_auto_latency = DbSnpAdapter.parse_dbsnp_json(raw_bytes, variant)
    assert parsed_auto_latency.query_latency_ms == 1

    # 3. Parsing with MAF provided in integer basis points via the explicit *_bps fields
    payload_bps = {
        "refsnp_id": "rs75527207",
        "global_maf_bps": 350,
        "ancestral_frequencies_bps": {
            "EUR": 420,
            "AFR": 150,
        },
    }
    parsed_bps = DbSnpAdapter.parse_dbsnp_json(canonical_json_v1(payload_bps), variant)
    assert parsed_bps.parsed_data["maf_global_bps"] == 350
    assert parsed_bps.parsed_data["ancestral_frequencies_bps"]["EUR"] == 420
    assert parsed_bps.parsed_data["ancestral_frequencies_bps"]["AFR"] == 150

    # 4. Parsing with missing MAF and missing ancestral frequencies defaults to 0
    payload_empty = {"refsnp_id": "rs75527207"}
    parsed_empty = DbSnpAdapter.parse_dbsnp_json(canonical_json_v1(payload_empty), variant)
    assert parsed_empty.parsed_data["maf_global_bps"] == 0
    assert parsed_empty.parsed_data["ancestral_frequencies_bps"] == {}

    # 5. Boundary testing for fraction-unit fields (units come from the field name,
    # never from the JSON literal type; out-of-range values are tested in test_12).
    payload_boundaries = {
        "refsnp_id": "rs75527207",
        "global_maf": 0.75,
        "ancestral_frequencies": {
            "HALF_FLOAT": 0.75,
            "MIN_FLOAT": 0.0,
            "MAX_FLOAT": 1.0,
            "MIN_INT": 0,
            "MAX_INT": 1,
        },
    }
    for raw_boundaries in (
        json.dumps(payload_boundaries, separators=(",", ":")).encode("utf-8"),
        canonical_json_v1(payload_boundaries),
    ):
        parsed_boundaries = DbSnpAdapter.parse_dbsnp_json(raw_boundaries, variant)
        assert parsed_boundaries.parsed_data["maf_global_bps"] == 75 * 100
        anc = parsed_boundaries.parsed_data["ancestral_frequencies_bps"]
        assert anc == {
            "HALF_FLOAT": 7500,
            "MIN_FLOAT": 0,
            "MAX_FLOAT": 10000,
            "MIN_INT": 0,
            "MAX_INT": 10000,
        }

    # 5b. Exact 0 fraction and explicit 0 / 10000 basis points
    payload_zero_int_maf = {"refsnp_id": "rs75527207", "global_maf": 0}
    assert DbSnpAdapter.parse_dbsnp_json(canonical_json_v1(payload_zero_int_maf), variant).parsed_data["maf_global_bps"] == 0

    payload_zero_bps = {"refsnp_id": "rs75527207", "global_maf_bps": 0}
    assert DbSnpAdapter.parse_dbsnp_json(canonical_json_v1(payload_zero_bps), variant).parsed_data["maf_global_bps"] == 0

    payload_max_bps = {"refsnp_id": "rs75527207", "global_maf_bps": 10000}
    assert DbSnpAdapter.parse_dbsnp_json(canonical_json_v1(payload_max_bps), variant).parsed_data["maf_global_bps"] == 10000

    # 6. Fallback to variant.rsid when refsnp_id is omitted
    payload_no_refsnp = {"global_maf": 0.05}
    parsed_no_refsnp = DbSnpAdapter.parse_dbsnp_json(canonical_json_v1(payload_no_refsnp), variant)
    assert parsed_no_refsnp.parsed_data["rsid"] == "rs75527207"


def test_2b_dbsnp_query_raw_without_rsid_synthesizes_valid_rsid() -> None:
    # Variant without rsid
    res = VariantContract.validate(
        {
            "genome_build": "GRCh38",
            "chrom": "chr7",
            "pos": 117_120_016,
            "ref": "A",
            "alt": "G",
        }
    )
    assert res.normalized is not None
    variant_no_rsid = res.normalized
    assert variant_no_rsid.rsid is None

    adapter = DbSnpAdapter(offline_only=True)
    assert adapter.offline_only is True

    adapter_online = DbSnpAdapter(offline_only=False)
    assert adapter_online.offline_only is False

    query_res = adapter.query_raw(variant_no_rsid)
    assert query_res.parsed_data["rsid"] == "rs118120016"
    DbSnpAdapter.validate_rsid_syntax(query_res.parsed_data["rsid"])
    assert query_res.parsed_data["maf_global_bps"] == 12


def test_3_dbsnp_fabricated_rsid_rejection() -> None:
    fabricated_ids = [
        "rs999999999999999",  # 15 digits (exceeds 11 digits bound)
        "rs0",                # 0 is not 1-9
        "rs0123",             # leading zero
        "rsABC",              # non-digit
        "12345678",           # missing rs prefix
    ]
    for bad_id in fabricated_ids:
        with pytest.raises(ValueError) as exc:
            DbSnpAdapter.validate_rsid_syntax(bad_id)
        assert SourceHaltCode.HALT_INVALID_RSID_FORMAT.value in str(exc.value)


def test_4_dbsnp_mismatched_rsid_rejection() -> None:
    variant = get_cftr_variant()  # rs75527207
    mismatched_payload = {
        "refsnp_id": "rs12345",
        "global_maf": 0.05,
    }
    raw_bytes = canonical_json_v1(mismatched_payload)
    with pytest.raises(ValueError) as exc:
        DbSnpAdapter.parse_dbsnp_json(raw_bytes, variant)
    assert SourceHaltCode.HALT_LOOKUP_PROVENANCE_UNBOUND.value in str(exc.value)


def test_5_dbsnp_unparseable_json() -> None:
    variant = get_cftr_variant()
    with pytest.raises(ValueError) as exc1:
        DbSnpAdapter.parse_dbsnp_json(b"not json {", variant)
    assert SourceHaltCode.HALT_SOURCE_RESPONSE_UNPARSEABLE.value in str(exc1.value)

    with pytest.raises(ValueError) as exc2:
        DbSnpAdapter.parse_dbsnp_json(b'["list", "not", "dict"]', variant)
    assert SourceHaltCode.HALT_SOURCE_RESPONSE_UNPARSEABLE.value in str(exc2.value)


def test_6_dbsnp_digest_tampering() -> None:
    variant = get_cftr_variant()
    raw = canonical_json_v1({"refsnp_id": "rs75527207", "global_maf": 0.001})
    res = DbSnpAdapter.parse_dbsnp_json(raw, variant)
    res.verify_integrity()

    # Create tampered result with altered raw payload
    tampered = SourceQueryResult(
        source_name=res.source_name,
        source_version=res.source_version,
        lookup_digest=res.lookup_digest,
        raw_payload_bytes=b'{"refsnp_id":"rs75527207","global_maf":0.999}',
        content_digest=res.content_digest,
        parsed_data=res.parsed_data,
        limitations=res.limitations,
        query_latency_ms=res.query_latency_ms,
    )
    with pytest.raises(RuntimeError) as exc:
        tampered.verify_integrity()
    assert SourceHaltCode.HALT_SOURCE_DIGEST_MISMATCH.value in str(exc.value)

    from src.sources.base import query_result_to_evidence_record

    rec_explicit = query_result_to_evidence_record(res, fetched_at_ns=123456789)
    assert rec_explicit.fetched_at_ns == 123456789
    rec_auto = query_result_to_evidence_record(res)
    assert rec_auto.fetched_at_ns > 1_000_000_000


def test_7_dbsnp_adapter_fetch_conformance() -> None:
    variant = get_cftr_variant()
    adapter = DbSnpAdapter()
    assert adapter.offline_only is True
    rec = adapter.fetch(variant)
    assert rec.source_name == "dbsnp_b157"
    assert rec.source_version == "Build157"
    assert rec.normalized_evidence["rsid"] == "rs75527207"
    assert rec.normalized_evidence["maf_global_bps"] == 12
    rec.verify_integrity()


def test_8_epistemic_purity() -> None:
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
        Path("src/sources/base.py"),
        Path("src/sources/dbsnp.py"),
        Path("tests/test_sources_dbsnp.py"),
    ]
    for p in target_files:
        if not p.exists():
            continue
        content = p.read_text(encoding="utf-8").lower()
        for tok in forbidden_tokens:
            assert tok not in content, f"Forbidden promotional term '{tok}' found in {p}"


# ---------------------------------------------------------------------------
# Frequency unit contract regressions (units from the field name, never from
# the JSON literal type). Each test below fails on the pre-fix adapter, which
# read float 1.0 as a fraction and int 1 as 1 bps.
# ---------------------------------------------------------------------------

FREQ_UNIT_HALT = "HALT_FREQUENCY_UNIT_INVALID"


def _parse_raw(raw: bytes):
    return DbSnpAdapter.parse_dbsnp_json(raw, get_cftr_variant()).parsed_data


def _wire(payload_json: str) -> bytes:
    return payload_json.encode("utf-8")


def test_9_fraction_field_literal_forms_all_map_to_10000_bps() -> None:
    for literal in ("1.0", "1", '"1"', '"1.0"', "1e0", "10E-1"):
        raw = _wire('{"refsnp_id":"rs75527207","global_maf":%s,'
                    '"ancestral_frequencies":{"EUR":%s}}' % (literal, literal))
        data = _parse_raw(raw)
        assert data["maf_global_bps"] == 10000, literal
        assert data["ancestral_frequencies_bps"] == {"EUR": 10000}, literal


def test_10_half_and_small_fractions_and_rounding() -> None:
    for literal in ("0.5", '"0.5"', "5e-1"):
        data = _parse_raw(_wire('{"global_maf":%s,"ancestral_frequencies":{"AFR":%s}}' % (literal, literal)))
        assert data["maf_global_bps"] == 5000, literal
        assert data["ancestral_frequencies_bps"]["AFR"] == 5000, literal
    # 0.0001 is exactly 1 bps when read as a fraction; half-even rounding on ties.
    data = _parse_raw(_wire('{"global_maf":0.0001,"ancestral_frequencies":'
                            '{"A":0.00005,"B":0.00015,"C":0.00016,"D":"0.00025"}}'))
    assert data["maf_global_bps"] == 1
    assert data["ancestral_frequencies_bps"] == {"A": 0, "B": 2, "C": 2, "D": 2}


def test_11_one_bps_only_from_explicit_bps_field() -> None:
    # Integer 1 in a fraction field is 100%, not 1 bps.
    assert _parse_raw(_wire('{"global_maf":1}'))["maf_global_bps"] == 10000
    # 1 bps is produced only by the explicit *_bps field.
    data = _parse_raw(_wire('{"global_maf_bps":1,"ancestral_frequencies_bps":{"EUR":1,"AFR":"7"}}'))
    assert data["maf_global_bps"] == 1
    assert data["ancestral_frequencies_bps"] == {"EUR": 1, "AFR": 7}
    # Integral-valued decimal is accepted for bps (a JCS round trip prints 350.0 as 350).
    assert _parse_raw(_wire('{"global_maf_bps":350.0}'))["maf_global_bps"] == 350


def test_12_jcs_round_trip_preserves_bps() -> None:
    from src.jcs_canonicalizer import encode_jcs

    payload = {
        "refsnp_id": "rs75527207",
        "global_maf": 1.0,
        "ancestral_frequencies": {"EUR": 0.5, "AFR": 1.0, "EAS": 0.0012, "SAS": 0.0},
    }
    wire_python = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    wire_jcs = encode_jcs(payload)
    # RFC 8785 renders 1.0 as 1 and 0.0 as 0: the literal type is erased.
    assert b'"global_maf":1,' in wire_jcs
    expected_anc = {"EUR": 5000, "AFR": 10000, "EAS": 12, "SAS": 0}
    for wire in (wire_python, wire_jcs, canonical_json_v1(payload)):
        data = _parse_raw(wire)
        assert data["maf_global_bps"] == 10000
        assert data["ancestral_frequencies_bps"] == expected_anc
        # The bps payload itself is integer-only and survives encode_jcs + json.loads.
        assert json.loads(encode_jcs(data)) == data
        # Re-ingesting the canonical form of the source payload is a fixed point.
        assert _parse_raw(encode_jcs(json.loads(wire))) == data


@pytest.mark.parametrize(
    "payload_json",
    [
        '{"global_maf":1.5}',
        '{"global_maf":1.0001}',
        '{"global_maf":-0.1}',
        '{"global_maf":"-0.1"}',
        '{"global_maf":350}',
        '{"global_maf":"NaN"}',
        '{"global_maf":"Infinity"}',
        '{"global_maf":"1_0"}',
        '{"global_maf":" 1"}',
        '{"global_maf":"abc"}',
        '{"global_maf":true}',
        '{"global_maf":null}',
        '{"global_maf":[0.5]}',
        '{"global_maf_bps":10001}',
        '{"global_maf_bps":-1}',
        '{"global_maf_bps":350.5}',
        '{"global_maf_bps":"0.5"}',
        '{"global_maf":0.5,"global_maf_bps":5000}',
        '{"ancestral_frequencies":{"EUR":1.5}}',
        '{"ancestral_frequencies":{"EUR":10000}}',
        '{"ancestral_frequencies":{"EUR":false}}',
        '{"ancestral_frequencies":[0.5]}',
        '{"ancestral_frequencies_bps":{"EUR":10001}}',
        '{"ancestral_frequencies_bps":{"EUR":0.5}}',
        '{"ancestral_frequencies":{"EUR":0.5},"ancestral_frequencies_bps":{"EUR":5000}}',
    ],
)
def test_13_invalid_frequencies_fail_closed(payload_json: str) -> None:
    with pytest.raises(ValueError) as exc:
        _parse_raw(_wire(payload_json))
    assert str(exc.value).startswith(FREQ_UNIT_HALT + ":")

    from src.sources.dbsnp import DbSnpFrequencyUnitError

    assert isinstance(exc.value, DbSnpFrequencyUnitError)
    assert exc.value.halt_code == FREQ_UNIT_HALT


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity"])
def test_14_non_finite_json_constants_fail_closed(token: str) -> None:
    with pytest.raises(ValueError) as exc:
        _parse_raw(_wire('{"global_maf":%s}' % token))
    assert SourceHaltCode.HALT_SOURCE_RESPONSE_UNPARSEABLE.value in str(exc.value)


def test_15_public_unit_helpers() -> None:
    from decimal import Decimal

    from src.sources.dbsnp import (
        BPS_SCALE,
        FREQUENCY_FIELD_UNITS,
        DbSnpFrequencyUnitError,
        explicit_bps,
        fraction_to_bps,
    )

    assert BPS_SCALE == 10000
    assert FREQUENCY_FIELD_UNITS == {
        "global_maf": "fraction",
        "ancestral_frequencies": "fraction",
        "global_maf_bps": "bps",
        "ancestral_frequencies_bps": "bps",
    }
    for v in (1.0, 1, "1", "1.0", Decimal("1"), Decimal("1.000")):
        assert fraction_to_bps(v) == 10000, v
    assert fraction_to_bps(0.1) == 1000  # repr(0.1) == "0.1", no binary drift
    assert fraction_to_bps(0) == 0
    assert explicit_bps(1) == 1
    assert explicit_bps(10000.0) == 10000
    assert explicit_bps("0") == 0
    for bad in (float("nan"), float("inf"), -0.5, 2, True, None, object(), Decimal("NaN")):
        with pytest.raises(DbSnpFrequencyUnitError) as exc:
            fraction_to_bps(bad, "f")
        assert exc.value.field == "f"
    for bad in (10000.5, 10001, -1, float("nan"), False, "1e9"):
        with pytest.raises(DbSnpFrequencyUnitError):
            explicit_bps(bad)
    # Field label is carried in the message for diagnostics.
    with pytest.raises(DbSnpFrequencyUnitError, match=r"ancestral_frequencies\.EUR"):
        _parse_raw(_wire('{"ancestral_frequencies":{"EUR":2}}'))

    # Strict require_global_maf=True rejects missing global_maf/global_maf_bps fail-closed
    from src.sources.dbsnp import parse_frequency_fields

    with pytest.raises(DbSnpFrequencyUnitError, match="missing required global_maf"):
        parse_frequency_fields({"refsnp_id": "rs75527207"}, require_global_maf=True)
    with pytest.raises(DbSnpFrequencyUnitError, match="missing required global_maf"):
        DbSnpAdapter.parse_dbsnp_json(
            b'{"refsnp_id":"rs75527207"}', get_cftr_variant(), require_global_maf=True
        )
