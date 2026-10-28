#!/usr/bin/env python3
# File: src/sources/base.py
"""
Base protocols, data structures, and cryptographic digest binders for
AEIB biological source adapters.

Enforces:
1. Dual-digest binding:
   - lookup_digest: cryptographically binds query parameters and target variant_caid.
   - content_digest: cryptographically binds raw upstream response payload bytes.
2. Lossless limitation preservation across all source adapters.
3. Strict fail-closed error handling with explicit halt codes.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Protocol, Sequence, Tuple

from src.bio_evidence_gate import (
    EvidenceRecord,
    build_verified_evidence_record,
)
from src.bio_variant_contract import (
    NormalizedVariant,
    canonical_json_v1,
    sha256_prefixed,
)


class SourceHaltCode(str, Enum):
    VALID = "VALID"
    HALT_LOOKUP_PROVENANCE_UNBOUND = "HALT_LOOKUP_PROVENANCE_UNBOUND"
    HALT_SOURCE_DIGEST_MISMATCH = "HALT_SOURCE_DIGEST_MISMATCH"
    HALT_INVALID_RSID_FORMAT = "HALT_INVALID_RSID_FORMAT"
    HALT_SOURCE_RESPONSE_UNPARSEABLE = "HALT_SOURCE_RESPONSE_UNPARSEABLE"
    HALT_SOURCE_RATE_LIMITED = "HALT_SOURCE_RATE_LIMITED"
    HALT_SOURCE_UPSTREAM_UNAVAILABLE = "HALT_SOURCE_UPSTREAM_UNAVAILABLE"
    HALT_ALPHAGENOME_MISSING_COMPONENT_SCORES = "HALT_ALPHAGENOME_MISSING_COMPONENT_SCORES"
    HALT_ALPHAGENOME_BUILD_UNSUPPORTED = "HALT_ALPHAGENOME_BUILD_UNSUPPORTED"
    HALT_ENCODE_BUILD_UNSUPPORTED = "HALT_ENCODE_BUILD_UNSUPPORTED"
    HALT_ENCODE_INVALID_CCRE_ID = "HALT_ENCODE_INVALID_CCRE_ID"


def compute_lookup_digest(
    source_name: str,
    variant: NormalizedVariant,
    extra_params: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Computes a canonical SHA-256 digest over the source identifier,
    variant_caid, and query parameters, binding the provenance of the lookup.
    """
    payload = {
        "extra": extra_params or {},
        "source": source_name,
        "variant_caid": variant.variant_caid,
    }
    return sha256_prefixed(canonical_json_v1(payload))


@dataclass(frozen=True)
class SourceQueryResult:
    """
    Immutable representation of an upstream biological query execution.
    """

    source_name: str
    source_version: str
    lookup_digest: str
    raw_payload_bytes: bytes
    content_digest: str
    parsed_data: Dict[str, Any]
    limitations: Tuple[str, ...]
    query_latency_ms: int

    def verify_integrity(self) -> None:
        """Asserts that raw payload bytes match the recorded content digest."""
        computed_digest = sha256_prefixed(self.raw_payload_bytes)
        if computed_digest != self.content_digest:
            raise RuntimeError(
                f"HALT_SOURCE_DIGEST_MISMATCH:{self.source_name} expected "
                f"{self.content_digest}, got {computed_digest}"
            )


class BaseBioSourceAdapter(Protocol):
    """Protocol implemented by all typed biological data adapters."""

    source_name: str
    source_version: str

    def query_raw(self, variant: NormalizedVariant) -> SourceQueryResult:
        """Executes query and returns raw bytes with verified digests."""
        ...

    def fetch(self, variant: NormalizedVariant) -> EvidenceRecord:
        """Returns standard verified EvidenceRecord for the evidence gate."""
        ...


def query_result_to_evidence_record(
    result: SourceQueryResult,
    fetched_at_ns: Optional[int] = None,
) -> EvidenceRecord:
    """
    Converts a SourceQueryResult into an EvidenceRecord with raw bytes and digest preserved.
    """
    result.verify_integrity()
    ts = fetched_at_ns if fetched_at_ns is not None else time.time_ns()
    rec = EvidenceRecord(
        source_name=result.source_name,
        source_version=result.source_version,
        fetched_at_ns=ts,
        raw_response_bytes=result.raw_payload_bytes,
        content_digest=result.content_digest,
        normalized_evidence=result.parsed_data,
        limitations=result.limitations,
    )
    rec.verify_integrity()
    return rec
