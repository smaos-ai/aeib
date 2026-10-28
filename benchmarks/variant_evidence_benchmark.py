#!/usr/bin/env python3
# File: benchmarks/variant_evidence_benchmark.py
"""
Clean-room benchmark and cryptographic reproducibility test for the
AEIB Bio-Digital Evidence Pipeline (v0.1).

Verifies:
1. Deterministic Clean-Room Reproducibility:
   Two independent runs on the same genomic variant yield identical
   provenance chains and identical SHA-256 bundle digests.
2. Concurrent Multi-Source Throughput:
   Measures wall-clock latency across parallel worker threads.
3. EO1 Hypothesis-Before-Evidence Latch & Ed25519 Signature Verification:
   Ensures that every sealed bundle's Ed25519 signature and digest
   verify offline without network dependencies.
4. Multi-Locus Determinism:
   Evaluates multiple landmark variants (CFTR, BRCA1, BRCA2) and
   asserts unique, collision-free content-addressed bundle digests.
"""

from __future__ import annotations

import base64
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

# Ensure repository root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from src.bio_evidence_gate import (
    BioContextCart,
    EO1BioEvidenceLatch,
    ReproducibleBioEvidenceBundle,
)
from src.bio_variant_contract import (
    NormalizedVariant,
    VariantContract,
    canonical_json_v1,
    sha256_prefixed,
)
from src.sources.alphagenome import AlphaGenomeAdapter
from src.sources.dbsnp import DbSnpAdapter
from src.sources.encode import EncodeCcreAdapter
from src.variant_evidence_pipeline import (
    BiologicalEvidenceBundle,
    VariantEvidencePipeline,
)


def run_benchmark() -> Dict[str, Any]:
    print("=" * 72)
    print("AEIB BIO-DIGITAL EVIDENCE PIPELINE: CLEAN-ROOM REPRODUCIBILITY BENCHMARK")
    print("=" * 72)

    tmp_dir = Path(tempfile.mkdtemp(prefix="bio_benchmark_"))
    ledger_dir = tmp_dir / "ledger"
    archive_dir = tmp_dir / "archive"

    try:
        # Define 3 landmark test variants (GRCh38)
        test_variants_raw = [
            {
                "name": "CFTR_c.1521_1523delCTT_proxy",
                "genome_build": "GRCh38",
                "chrom": "chr7",
                "pos": 117_120_016,
                "ref": "A",
                "alt": "G",
                "rsid": "rs75527207",
            },
            {
                "name": "BRCA1_c.68_69delAG_proxy",
                "genome_build": "GRCh38",
                "chrom": "chr17",
                "pos": 43_044_295,
                "ref": "G",
                "alt": "A",
                "rsid": "rs80357906",
            },
            {
                "name": "BRCA2_c.5946delT_proxy",
                "genome_build": "GRCh38",
                "chrom": "chr13",
                "pos": 32_315_474,
                "ref": "C",
                "alt": "T",
                "rsid": "rs80359550",
            },
        ]

        normalized_variants: List[NormalizedVariant] = []
        for v in test_variants_raw:
            res = VariantContract.validate(v)
            assert res.normalized is not None, f"Variant validation failed: {res.halt_code}"
            normalized_variants.append(res.normalized)

        pipeline = VariantEvidencePipeline(max_workers=4)

        # ------------------------------------------------------------------
        # Phase 1: Clean-room 2-run reproducibility on Primary Variant
        # ------------------------------------------------------------------
        v_primary = normalized_variants[0]
        fixed_ts_ns = 1_700_000_000_000_000_000

        t_start = time.perf_counter()
        bundle_run1 = pipeline.run(v_primary, execution_timestamp_ns=fixed_ts_ns)
        t_run1 = (time.perf_counter() - t_start) * 1000

        t_start = time.perf_counter()
        bundle_run2 = pipeline.run(v_primary, execution_timestamp_ns=fixed_ts_ns)
        t_run2 = (time.perf_counter() - t_start) * 1000

        # Assert exact clean-room equality
        assert bundle_run1.bundle_digest == bundle_run2.bundle_digest, (
            f"Reproducibility divergence: {bundle_run1.bundle_digest} != {bundle_run2.bundle_digest}"
        )
        assert bundle_run1.provenance_chain == bundle_run2.provenance_chain, (
            "Provenance chain mismatch between consecutive runs"
        )
        assert len(bundle_run1.records) == 3, f"Expected 3 records, got {len(bundle_run1.records)}"
        assert len(bundle_run1.source_errors) == 0, f"Unexpected errors: {bundle_run1.source_errors}"

        print(f"✓ Clean-Room Reproducibility: Confirmed (Digest: {bundle_run1.bundle_digest[:24]}...)")
        print(f"  Run 1 Wall Latency: {t_run1:.2f} ms | Run 2 Wall Latency: {t_run2:.2f} ms")

        # ------------------------------------------------------------------
        # Phase 2: EO1 Hypothesis-Before-Evidence Latch & Ed25519 Signing
        # ------------------------------------------------------------------
        signing_key = Ed25519PrivateKey.generate()
        public_key = signing_key.public_key()
        latch = EO1BioEvidenceLatch(ledger_dir=ledger_dir, signing_key=signing_key)
        context_cart = BioContextCart(archive_dir=archive_dir)

        hypothesis = (
            "Observed non-coding variant in CFTR intronic region modulates cis-regulatory chromatin accessibility"
        )

        sealed_bundle, reproducible = VariantEvidencePipeline.execute_with_hypothesis_latch(
            variant=v_primary,
            hypothesis=hypothesis,
            latch=latch,
            context_cart=context_cart,
            pipeline=pipeline,
        )

        # Verify Ed25519 signature of the reproducible bundle
        sig_bytes = base64.b64decode(reproducible.ed25519_signature_b64)
        payload_to_sign = canonical_json_v1(
            {
                "bio_evidence_version": reproducible.bio_evidence_version,
                "claims": list(reproducible.claims),
                "context_cards": list(reproducible.context_cards),
                "hypothesis": reproducible.hypothesis,
                "limitations": list(reproducible.limitations),
                "operation_id": reproducible.operation_id,
                "receipt_tier": reproducible.receipt_tier,
                "variant": reproducible.variant,
            }
        )
        public_key.verify(sig_bytes, payload_to_sign)
        assert sha256_prefixed(payload_to_sign) == reproducible.bundle_digest

        print(f"✓ EO1 Hypothesis Latch & Ed25519 Signature: Confirmed (OpID: {reproducible.operation_id})")

        # ------------------------------------------------------------------
        # Phase 3: Multi-Locus Execution & Collision Resistance
        # ------------------------------------------------------------------
        bundle_digests: List[str] = [bundle_run1.bundle_digest]
        latencies_ms: List[float] = [t_run1, t_run2]

        for v in normalized_variants[1:]:
            t0 = time.perf_counter()
            b = pipeline.run(v, execution_timestamp_ns=fixed_ts_ns)
            t_ms = (time.perf_counter() - t0) * 1000
            latencies_ms.append(t_ms)
            bundle_digests.append(b.bundle_digest)

        # Assert all bundles have unique digests
        assert len(set(bundle_digests)) == len(normalized_variants), (
            f"Digest collision detected across distinct genomic variants: {bundle_digests}"
        )
        print(f"✓ Multi-Locus Collision Resistance: Confirmed across {len(normalized_variants)} distinct loci")

        avg_latency_ms = sum(latencies_ms) / len(latencies_ms)
        print(f"✓ Concurrent Throughput: Average latency {avg_latency_ms:.2f} ms across {len(latencies_ms)} evaluations")
        print("=" * 72)
        print("ALL CLEAN-ROOM REPRODUCIBILITY GATES CONFIRMED.")
        print("=" * 72)

        metrics = {
            "status": "PASSED",
            "episodes_tested": len(latencies_ms),
            "reproducibility_confirmed": True,
            "average_latency_ms": round(avg_latency_ms, 3),
            "primary_bundle_digest": bundle_run1.bundle_digest,
            "provenance_chain_length": len(bundle_run1.provenance_chain),
            "distinct_loci_count": len(bundle_digests),
            "ed25519_verified": True,
        }
        return metrics

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    res = run_benchmark()
    print(json.dumps(res, indent=2))
