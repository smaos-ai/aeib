#!/usr/bin/env python3
# File: src/variant_evidence_pipeline.py
"""
Unified parallel biological evidence aggregation pipeline for the AEIB
Bio-Digital Evidence Gate (v0.1).

Features:
1. Concurrent multi-source execution via ThreadPoolExecutor with per-source isolation.
2. Content-addressed provenance binding: gathers verified EvidenceRecords,
   orders provenance chains deterministically, and seals a canonical bundle_digest.
3. Fail-closed error isolation: failures or timeouts in individual sources are
   explicitly captured in source_errors and never silently dropped.
4. Seamless integration with:
   - BioEvidenceScorer (evaluates SUPPORTS | REFUTES | UNKNOWN)
   - EO1BioEvidenceLatch (prevents HARKing by enforcing pre-evidence hypothesis recording)
   - BioContextCart (lossless raw payload archiving and digest recovery)
"""

from __future__ import annotations

import concurrent.futures
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.bio_evidence_gate import (
    BioContextCard,
    BioContextCart,
    BioEvidenceScorer,
    ClaimVerdict,
    EO1BioEvidenceLatch,
    EvidenceRecord,
    ReproducibleBioEvidenceBundle,
)
from src.bio_variant_contract import (
    NormalizedVariant,
    canonical_json_v1,
    sha256_prefixed,
)
from src.sources.alphagenome import AlphaGenomeAdapter
from src.sources.base import (
    BaseBioSourceAdapter,
    SourceHaltCode,
    SourceQueryResult,
)
from src.sources.dbsnp import DbSnpAdapter
from src.sources.encode import EncodeCcreAdapter


@dataclass(frozen=True)
class BiologicalEvidenceBundle:
    """
    Deterministic, provenance-bound bundle of verified biological evidence records.
    """

    target_variant: NormalizedVariant
    pipeline_version: str
    execution_timestamp_ns: int
    total_wall_time_ms: int
    records: Tuple[EvidenceRecord, ...]
    provenance_chain: Tuple[str, ...]
    source_errors: Dict[str, str]
    bundle_digest: str

    def verify_bundle_integrity(self) -> None:
        """
        Verifies internal consistency of the bundle:
        1. Verifies SHA-256 integrity of every contained EvidenceRecord.
        2. Asserts provenance_chain matches sorted content_digests of records.
        3. Recomputes and verifies the bundle_digest.
        """
        expected_digests = tuple(sorted(r.content_digest for r in self.records))
        if self.provenance_chain != expected_digests:
            raise RuntimeError(
                f"{SourceHaltCode.HALT_SOURCE_DIGEST_MISMATCH.value}:"
                f"Bundle provenance chain does not match record digests"
            )

        for rec in self.records:
            rec.verify_integrity()

        recomputed_digest = sha256_prefixed(
            canonical_json_v1(
                {
                    "pipeline_version": self.pipeline_version,
                    "provenance_chain": list(self.provenance_chain),
                    "source_errors": self.source_errors,
                    "variant_caid": self.target_variant.variant_caid,
                }
            )
        )
        if recomputed_digest != self.bundle_digest:
            raise RuntimeError(
                f"{SourceHaltCode.HALT_SOURCE_DIGEST_MISMATCH.value}:"
                f"Bundle digest mismatch: expected {self.bundle_digest}, recomputed {recomputed_digest}"
            )


class VariantEvidencePipeline:
    """
    Orchestrates concurrent execution of biological source adapters.
    """

    DEFAULT_PIPELINE_VERSION: str = "v0.1.0"

    def __init__(
        self,
        adapters: Optional[Sequence[BaseBioSourceAdapter]] = None,
        max_workers: int = 4,
        timeout_seconds: float = 10.0,
        pipeline_version: Optional[str] = None,
    ) -> None:
        if adapters is not None:
            self.adapters = tuple(adapters)
        else:
            self.adapters = (
                DbSnpAdapter(offline_only=True),
                AlphaGenomeAdapter(offline_only=True),
                EncodeCcreAdapter(offline_only=True),
            )
        self.max_workers = max_workers
        self.timeout_seconds = timeout_seconds
        self.pipeline_version = pipeline_version or self.DEFAULT_PIPELINE_VERSION

    def run(
        self,
        variant: NormalizedVariant,
        execution_timestamp_ns: Optional[int] = None,
    ) -> BiologicalEvidenceBundle:
        """
        Executes all configured adapters in parallel, binds content digests,
        and constructs a verified BiologicalEvidenceBundle.
        """
        t0 = time.perf_counter()
        ts_ns = execution_timestamp_ns if execution_timestamp_ns is not None else time.time_ns()

        records_map: Dict[str, EvidenceRecord] = {}
        errors_map: Dict[str, str] = {}

        def _fetch_single(adapter: BaseBioSourceAdapter) -> Tuple[str, Optional[EvidenceRecord], Optional[str]]:
            src_name = getattr(adapter, "source_name", getattr(adapter, "SOURCE_NAME", type(adapter).__name__))
            try:
                rec = adapter.fetch(variant)
                rec.verify_integrity()
                return src_name, rec, None
            except Exception as exc:
                return src_name, None, str(exc)

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(_fetch_single, adapter) for adapter in self.adapters]
            for future in concurrent.futures.as_completed(futures, timeout=self.timeout_seconds):
                try:
                    src_name, rec, err = future.result()
                    if rec is not None:
                        records_map[src_name] = rec
                    else:
                        errors_map[src_name] = err or "UNKNOWN_FETCH_ERROR"
                except Exception as exc:
                    errors_map["concurrency_executor"] = str(exc)

        # Sort records deterministically by source name
        sorted_records = tuple(records_map[k] for k in sorted(records_map.keys()))
        provenance_chain = tuple(sorted(r.content_digest for r in sorted_records))

        bundle_payload = {
            "pipeline_version": self.pipeline_version,
            "provenance_chain": list(provenance_chain),
            "source_errors": errors_map,
            "variant_caid": variant.variant_caid,
        }
        bundle_digest = sha256_prefixed(canonical_json_v1(bundle_payload))

        elapsed_ms = max(1, int((time.perf_counter() - t0) * 1000))

        bundle = BiologicalEvidenceBundle(
            target_variant=variant,
            pipeline_version=self.pipeline_version,
            execution_timestamp_ns=ts_ns,
            total_wall_time_ms=elapsed_ms,
            records=sorted_records,
            provenance_chain=provenance_chain,
            source_errors=errors_map,
            bundle_digest=bundle_digest,
        )
        bundle.verify_bundle_integrity()
        return bundle

    @staticmethod
    def evaluate(
        bundle: BiologicalEvidenceBundle,
        scorer: Optional[BioEvidenceScorer] = None,
    ) -> Tuple[ClaimVerdict, ...]:
        """
        Evaluates the evidence bundle using the BioEvidenceScorer.
        """
        active_scorer = scorer or BioEvidenceScorer()
        return active_scorer.score_claims(bundle.target_variant, bundle.records)

    @classmethod
    def execute_with_hypothesis_latch(
        cls,
        variant: NormalizedVariant,
        hypothesis: str,
        latch: EO1BioEvidenceLatch,
        context_cart: BioContextCart,
        pipeline: Optional[VariantEvidencePipeline] = None,
    ) -> Tuple[BiologicalEvidenceBundle, ReproducibleBioEvidenceBundle]:
        """
        Executes the full pipeline under EO1 pre-evidence hypothesis latching:
        1. Pre-records and fsyncs hypothesis to durable disk ledger BEFORE fetching evidence.
        2. Executes multi-source evidence pipeline.
        3. Archives raw response payloads in BioContextCart.
        4. Scores evidence via BioEvidenceScorer.
        5. Cryptographically seals and Ed25519-signs the final reproducible bundle.
        """
        # Step 1: Latch hypothesis before fetching any evidence
        op_id, hyp_recorded_at_ns = latch.record_hypothesis_before_fetch(
            variant=variant,
            hypothesis=hypothesis,
        )

        # Step 2: Fetch evidence in parallel
        active_pipeline = pipeline or cls()
        bundle = active_pipeline.run(variant)

        # Step 3: Archive into BioContextCart
        cards: List[BioContextCard] = []
        for rec in bundle.records:
            card = context_cart.archive_and_create_card(rec)
            cards.append(card)

        # Step 4: Evaluate verdicts
        verdicts = cls.evaluate(bundle)

        # Step 5: Seal and sign bundle with EO1 latch
        reproducible_bundle = latch.bind_evidence_and_seal_bundle(
            operation_id=op_id,
            variant=variant,
            records=bundle.records,
            verdicts=verdicts,
            cards=cards,
        )

        return bundle, reproducible_bundle
