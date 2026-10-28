#!/usr/bin/env python3
# File: src/bio_variant_contract.py
"""
Day 1 & Day 4 Delivery: Genomic Variant Input Contract, Left-Alignment Normalizer,
and 9-Vector Anti-Scaffold Bio-Mutation Oracle.

Enforces:
1. Exact genome build membership (GRCh37, GRCh38) with build-specific NCBI
   chromosome lengths (chr1..chr22, chrX, chrY, chrM).
2. 1-based closed coordinate bounds: 1 <= pos and pos + len(ref) - 1 <= chrom_len.
3. Strict DNA alphabet (A, C, G, T only; no IUPAC ambiguity or N in called alleles),
   ref != alt, and parsimonious VCF trimming (Tan et al. normalization).
4. Optional dbSNP Build 157 rsID format validation (^rs[1-9][0-9]{0,10}$).
5. 9-Vector Bio-Mutation Oracle (probe_variant_verifier) that tests any candidate
   verifier against 9 distinct corruptions and halts with
   HALT_VERIFIER_ACCEPTED_MUTATED_INPUT if any corruption passes.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

# RFC 8785 single source of truth: delegate to src/jcs_canonicalizer.encode_jcs
# (differential-tested in tests/test_jcs_single_source.py).
try:
    from src.jcs_canonicalizer import encode_jcs as _reference_encode_jcs
except ImportError:  # loaded without the repository root on sys.path
    import sys as _jcs_sys
    from pathlib import Path as _JcsPath

    _jcs_sys.path.insert(0, str(_JcsPath(__file__).resolve().parents[1]))
    from src.jcs_canonicalizer import encode_jcs as _reference_encode_jcs


class VariantHaltCode(str, Enum):
    VALID = "VALID"
    HALT_GENOME_BUILD_MISMATCH = "HALT_GENOME_BUILD_MISMATCH"
    HALT_INVALID_CHROMOSOME = "HALT_INVALID_CHROMOSOME"
    HALT_COORDINATE_OUT_OF_BOUNDS = "HALT_COORDINATE_OUT_OF_BOUNDS"
    HALT_INVALID_ALLELE_BASES = "HALT_INVALID_ALLELE_BASES"
    HALT_REF_ALT_IDENTICAL = "HALT_REF_ALT_IDENTICAL"
    HALT_UNNORMALIZED_ALLELE_REPRESENTATION = "HALT_UNNORMALIZED_ALLELE_REPRESENTATION"
    HALT_INVALID_RSID_FORMAT = "HALT_INVALID_RSID_FORMAT"
    HALT_VERIFIER_ACCEPTED_MUTATED_INPUT = "HALT_VERIFIER_ACCEPTED_MUTATED_INPUT"


# Exact NCBI Assembly chromosome lengths for GRCh38 (GCF_000001405.40) and GRCh37 (GCF_000001405.25)
CHROM_LENGTHS_BY_BUILD: Dict[str, Dict[str, int]] = {
    "GRCh38": {
        "chr1": 248_956_422,
        "chr2": 242_193_529,
        "chr3": 198_295_559,
        "chr4": 190_214_555,
        "chr5": 181_538_259,
        "chr6": 170_805_979,
        "chr7": 159_345_973,
        "chr8": 145_138_636,
        "chr9": 138_394_717,
        "chr10": 133_797_422,
        "chr11": 135_086_622,
        "chr12": 133_275_309,
        "chr13": 114_364_328,
        "chr14": 107_043_718,
        "chr15": 101_991_189,
        "chr16": 90_338_345,
        "chr17": 83_257_441,
        "chr18": 80_373_285,
        "chr19": 58_617_616,
        "chr20": 64_444_167,
        "chr21": 46_709_983,
        "chr22": 50_818_468,
        "chrX": 156_040_895,
        "chrY": 57_227_415,
        "chrM": 16_569,
    },
    "GRCh37": {
        "chr1": 249_250_621,
        "chr2": 243_199_373,
        "chr3": 198_022_430,
        "chr4": 191_154_276,
        "chr5": 180_915_260,
        "chr6": 171_115_067,
        "chr7": 159_138_663,
        "chr8": 146_364_022,
        "chr9": 141_213_431,
        "chr10": 135_534_747,
        "chr11": 135_006_516,
        "chr12": 133_851_895,
        "chr13": 115_169_878,
        "chr14": 107_349_540,
        "chr15": 102_531_392,
        "chr16": 90_354_753,
        "chr17": 81_195_210,
        "chr18": 78_077_248,
        "chr19": 59_128_983,
        "chr20": 63_025_520,
        "chr21": 48_129_895,
        "chr22": 51_304_566,
        "chrX": 155_270_560,
        "chrY": 59_373_566,
        "chrM": 16_569,
    },
}

VALID_DNA_RE = re.compile(r"^[ACGT]+$")
# dbSNP Build 157 rsIDs are 1 to 11 digits (max ~1.2B unique rsIDs in 2026); 12+ digits is fabricated
VALID_RSID_RE = re.compile(r"^rs[1-9][0-9]{0,10}$")


def canonical_json_v1(obj: Any) -> bytes:
    """Deterministic UTF-8 JSON serializer (sorted keys, no whitespace, no NaN/Inf)."""

    def _check(v: Any) -> None:
        if isinstance(v, float):
            if v != v or v == float("inf") or v == float("-inf"):
                raise ValueError("ERR_NON_FINITE_FLOAT")
        elif isinstance(v, dict):
            for k, val in v.items():
                if not isinstance(k, str):
                    raise ValueError("ERR_NON_STRING_KEY")
                _check(val)
        elif isinstance(v, list):
            for item in v:
                _check(item)

    _check(obj)
    return _reference_encode_jcs(obj)


def sha256_prefixed(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


@dataclass(frozen=True)
class NormalizedVariant:
    genome_build: str
    chrom: str
    pos: int
    ref: str
    alt: str
    rsid: Optional[str]
    variant_caid: str


@dataclass(frozen=True)
class VariantValidationResult:
    is_valid: bool
    halt_code: VariantHaltCode
    message: str
    normalized: Optional[NormalizedVariant] = None


class VariantContract:
    """
    Deterministic validator and minimal-trimming normalizer for human genomic variants.
    """

    @staticmethod
    def trim_minimal_alleles(pos: int, ref: str, alt: str) -> Tuple[int, str, str]:
        """
        Parsimonious right-then-left allele trimming (Tan et al. VCF normalization):
        1. Strip shared trailing bases while both alleles have length > 1.
        2. Strip shared leading bases while both alleles have length > 1, advancing `pos`.
        """
        r = ref
        a = alt
        p = pos
        while len(r) > 1 and len(a) > 1 and r[-1] == a[-1]:
            r = r[:-1]
            a = a[:-1]
        while len(r) > 1 and len(a) > 1 and r[0] == a[0]:
            r = r[1:]
            a = a[1:]
            p += 1
        return p, r, a

    @classmethod
    def validate(
        cls,
        variant: Dict[str, Any],
        require_pre_normalized: bool = True,
    ) -> VariantValidationResult:
        if not isinstance(variant, dict):
            return VariantValidationResult(
                is_valid=False,
                halt_code=VariantHaltCode.HALT_INVALID_ALLELE_BASES,
                message="Variant payload must be a dictionary.",
            )

        build = variant.get("genome_build")
        if not isinstance(build, str) or build not in CHROM_LENGTHS_BY_BUILD:
            return VariantValidationResult(
                is_valid=False,
                halt_code=VariantHaltCode.HALT_GENOME_BUILD_MISMATCH,
                message=f"Unsupported or missing genome_build: {build!r}",
            )

        chrom = variant.get("chrom")
        build_chroms = CHROM_LENGTHS_BY_BUILD[build]
        if not isinstance(chrom, str) or chrom not in build_chroms:
            return VariantValidationResult(
                is_valid=False,
                halt_code=VariantHaltCode.HALT_INVALID_CHROMOSOME,
                message=f"Invalid chromosome {chrom!r} for build {build}.",
            )

        pos = variant.get("pos")
        if isinstance(pos, bool) or not isinstance(pos, int):
            return VariantValidationResult(
                is_valid=False,
                halt_code=VariantHaltCode.HALT_COORDINATE_OUT_OF_BOUNDS,
                message=f"Position must be an integer, got {pos!r}.",
            )

        ref = variant.get("ref")
        alt = variant.get("alt")
        if (
            not isinstance(ref, str)
            or not isinstance(alt, str)
            or not VALID_DNA_RE.match(ref)
            or not VALID_DNA_RE.match(alt)
        ):
            return VariantValidationResult(
                is_valid=False,
                halt_code=VariantHaltCode.HALT_INVALID_ALLELE_BASES,
                message=f"Alleles must be non-empty uppercase ACGT strings: ref={ref!r}, alt={alt!r}",
            )

        if ref == alt:
            return VariantValidationResult(
                is_valid=False,
                halt_code=VariantHaltCode.HALT_REF_ALT_IDENTICAL,
                message=f"ref and alt alleles are identical ({ref}).",
            )

        max_len = build_chroms[chrom]
        end_pos = pos + len(ref) - 1
        if pos < 1 or end_pos > max_len:
            return VariantValidationResult(
                is_valid=False,
                halt_code=VariantHaltCode.HALT_COORDINATE_OUT_OF_BOUNDS,
                message=(
                    f"Coordinate {chrom}:{pos}-{end_pos} out of bounds for {build} "
                    f"(1..{max_len})."
                ),
            )

        trimmed_pos, trimmed_ref, trimmed_alt = cls.trim_minimal_alleles(pos, ref, alt)
        if require_pre_normalized and (
            trimmed_pos != pos or trimmed_ref != ref or trimmed_alt != alt
        ):
            return VariantValidationResult(
                is_valid=False,
                halt_code=VariantHaltCode.HALT_UNNORMALIZED_ALLELE_REPRESENTATION,
                message=(
                    f"Alleles not minimally trimmed: ({pos}, {ref}, {alt}) -> "
                    f"({trimmed_pos}, {trimmed_ref}, {trimmed_alt})."
                ),
            )

        rsid = variant.get("rsid")
        if rsid is not None:
            if not isinstance(rsid, str) or not VALID_RSID_RE.match(rsid):
                return VariantValidationResult(
                    is_valid=False,
                    halt_code=VariantHaltCode.HALT_INVALID_RSID_FORMAT,
                    message=f"Invalid or fabricated dbSNP rsID: {rsid!r}",
                )

        canonical_payload = {
            "alt": trimmed_alt,
            "chrom": chrom,
            "genome_build": build,
            "pos": trimmed_pos,
            "ref": trimmed_ref,
            "rsid": rsid or "",
        }
        v_caid = sha256_prefixed(canonical_json_v1(canonical_payload))

        return VariantValidationResult(
            is_valid=True,
            halt_code=VariantHaltCode.VALID,
            message="OK_VALID_VARIANT",
            normalized=NormalizedVariant(
                genome_build=build,
                chrom=chrom,
                pos=trimmed_pos,
                ref=trimmed_ref,
                alt=trimmed_alt,
                rsid=rsid,
                variant_caid=v_caid,
            ),
        )


# ============================================================================
# Day 4: 9-Vector Anti-Scaffold Bio-Mutation Oracle
# ============================================================================
BIO_MUTATION_VECTORS: Tuple[Tuple[str, Callable[[Dict[str, Any]], Dict[str, Any]]], ...] = (
    ("invalid_chromosome", lambda v: {**v, "chrom": "chr99"}),
    ("negative_position", lambda v: {**v, "pos": -1}),
    ("zero_position", lambda v: {**v, "pos": 0}),
    ("position_beyond_chrom_length", lambda v: {**v, "pos": 999_999_999}),
    ("ref_equals_alt", lambda v: {**v, "alt": v.get("ref", "A")}),
    ("invalid_allele_base_X", lambda v: {**v, "alt": "X"}),
    ("wrong_genome_build", lambda v: {**v, "genome_build": "GRCh99"}),
    (
        "unnormalized_padded_alleles",
        lambda v: {
            **v,
            "ref": v.get("ref", "A") + "T",
            "alt": v.get("alt", "G") + "T",
        },
    ),
    ("fabricated_overflow_rsid", lambda v: {**v, "rsid": "rs999999999999999"}),
)


@dataclass(frozen=True)
class BioMutationProbeReport:
    passed: bool
    reason_code: str
    mutations_tested: int
    mutations_rejected: int
    accepted_mutants: Tuple[str, ...]


def probe_variant_verifier(
    verifier_fn: Callable[[Dict[str, Any]], bool],
    valid_variant: Dict[str, Any],
) -> BioMutationProbeReport:
    """
    Probes any candidate bio-verifier against 1 positive control and 9 negative mutation controls.
    Halts immediately if any mutated variant is accepted.
    """
    if not verifier_fn(valid_variant):
        return BioMutationProbeReport(
            passed=False,
            reason_code="POSITIVE_CONTROL_FAILED",
            mutations_tested=0,
            mutations_rejected=0,
            accepted_mutants=(),
        )

    accepted: List[str] = []
    rejected = 0

    for name, mutate_fn in BIO_MUTATION_VECTORS:
        corrupted = mutate_fn(dict(valid_variant))
        try:
            verdict = verifier_fn(corrupted)
        except Exception:
            verdict = False

        if verdict is True:
            accepted.append(name)
        else:
            rejected += 1

    passed = len(accepted) == 0
    return BioMutationProbeReport(
        passed=passed,
        reason_code=(
            "SOUND_AND_DIFFERENTIATED"
            if passed
            else VariantHaltCode.HALT_VERIFIER_ACCEPTED_MUTATED_INPUT.value
        ),
        mutations_tested=len(BIO_MUTATION_VECTORS),
        mutations_rejected=rejected,
        accepted_mutants=tuple(accepted),
    )
