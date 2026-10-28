#!/usr/bin/env python3
# File: tests/test_variant_evidence_pipeline.py
"""
Deterministic falsification and verification test suite for the
AEIB Biological Evidence Pipeline (src/variant_evidence_pipeline.py).

Tests:
1. Concurrent execution of biological source adapters and deterministic bundle creation.
2. Clean-room reproducibility across consecutive runs.
3. Fail-closed error isolation when an adapter fails (e.g. build mismatch).
4. Bundle integrity tamper rejection.
5. Evidence evaluation via BioEvidenceScorer.
6. Full EO1 pre-evidence hypothesis latching and Ed25519 signing.
7. Epistemic purity scan for zero banned promotional words.
"""

import base64
import shutil
import tempfile
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.bio_evidence_gate import (
    BioContextCart,
    EO1BioEvidenceLatch,
    EvidenceRecord,
)
from src.bio_variant_contract import (
    NormalizedVariant,
    VariantContract,
    canonical_json_v1,
    sha256_prefixed,
)
from src.sources.alphagenome import AlphaGenomeAdapter
from src.sources.base import SourceHaltCode
from src.sources.dbsnp import DbSnpAdapter
from src.sources.encode import EncodeCcreAdapter
from src.variant_evidence_pipeline import (
    BiologicalEvidenceBundle,
    VariantEvidencePipeline,
)


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


def test_1_pipeline_concurrent_execution_and_digests() -> None:
    variant = get_grch38_cftr_variant()
    default_p = VariantEvidencePipeline()
    assert default_p.max_workers == 4
    assert default_p.timeout_seconds == 10.0
    assert default_p.pipeline_version == "v0.1.0"
    assert len(default_p.adapters) == 3
    assert all(getattr(a, "offline_only", False) is True for a in default_p.adapters)

    pipeline = VariantEvidencePipeline(max_workers=3)
    bundle = pipeline.run(variant)
    bundle.verify_bundle_integrity()

    # Immutable dataclass
    with pytest.raises(Exception):
        bundle.pipeline_version = "mutated"  # type: ignore

    assert bundle.pipeline_version == "v0.1.0"
    assert len(bundle.records) == 3
    source_names = [r.source_name for r in bundle.records]
    assert source_names == ["alphagenome_atlas", "dbsnp_b157", "encode_ccre"]

    assert len(bundle.source_errors) == 0
    assert len(bundle.provenance_chain) == 3
    for digest in bundle.provenance_chain:
        assert digest.startswith("sha256:")

    assert bundle.bundle_digest.startswith("sha256:")
    assert bundle.total_wall_time_ms >= 1


def test_2_clean_room_reproducibility() -> None:
    variant = get_grch38_cftr_variant()
    pipeline = VariantEvidencePipeline(max_workers=2)
    fixed_ts = 1_700_000_000_000_000_000

    b1 = pipeline.run(variant, execution_timestamp_ns=fixed_ts)
    b2 = pipeline.run(variant, execution_timestamp_ns=fixed_ts)

    assert b1.bundle_digest == b2.bundle_digest
    assert b1.provenance_chain == b2.provenance_chain
    assert len(b1.records) == len(b2.records)
    assert b1.execution_timestamp_ns == fixed_ts


def test_2b_pipeline_latency_measurement_and_timestamp_modes(monkeypatch) -> None:
    import time as _time

    variant = get_grch38_cftr_variant()
    pipeline = VariantEvidencePipeline(max_workers=2)

    # 1. execution_timestamp_ns is None branch
    t_start_ns = 1_000_000_000
    b_dynamic = pipeline.run(variant, execution_timestamp_ns=None)
    assert b_dynamic.execution_timestamp_ns > t_start_ns

    # 1b. Exact max(1, int((t1 - t0) * 1000)) boundaries
    monkeypatch.setattr(_time, "perf_counter", lambda: 50.0)
    assert pipeline.run(variant).total_wall_time_ms == 1
    vals = iter([50.0, 52.5])
    monkeypatch.setattr(_time, "perf_counter", lambda: next(vals, 52.5))
    assert pipeline.run(variant).total_wall_time_ms == 25 * 100
    monkeypatch.undo()

    # 2. Timing calculation with sleep
    class SlowTestAdapter:
        source_name = "slow_test_adapter"
        source_version = "v1"

        def fetch(self, v: NormalizedVariant) -> EvidenceRecord:
            import time
            time.sleep(0.003)
            raw = b'{"status":"ok"}'
            rec = EvidenceRecord(
                source_name=self.source_name,
                source_version=self.source_version,
                fetched_at_ns=time.time_ns(),
                raw_response_bytes=raw,
                content_digest=sha256_prefixed(raw),
                normalized_evidence={"status": "ok"},
                limitations=("Slow test limitation",),
            )
            rec.verify_integrity()
            return rec

    slow_pipeline = VariantEvidencePipeline(adapters=[SlowTestAdapter()], max_workers=1)
    b_slow = slow_pipeline.run(variant)
    assert b_slow.total_wall_time_ms >= 3
    assert b_slow.total_wall_time_ms < 500


def test_3_source_failure_captured_fail_closed() -> None:
    variant_b37 = get_grch37_cftr_variant()
    pipeline = VariantEvidencePipeline(
        adapters=[
            DbSnpAdapter(offline_only=True),
            AlphaGenomeAdapter(offline_only=True),  # Requires GRCh38
            EncodeCcreAdapter(offline_only=True),   # Requires GRCh38
        ]
    )

    bundle = pipeline.run(variant_b37)
    bundle.verify_bundle_integrity()

    assert len(bundle.records) == 1
    assert bundle.records[0].source_name == "dbsnp_b157"

    assert len(bundle.source_errors) == 2
    assert "alphagenome_atlas" in bundle.source_errors
    assert "encode_ccre" in bundle.source_errors
    assert SourceHaltCode.HALT_ALPHAGENOME_BUILD_UNSUPPORTED.value in bundle.source_errors["alphagenome_atlas"]
    assert SourceHaltCode.HALT_ENCODE_BUILD_UNSUPPORTED.value in bundle.source_errors["encode_ccre"]


def test_4_bundle_digest_tampering() -> None:
    variant = get_grch38_cftr_variant()
    pipeline = VariantEvidencePipeline()
    bundle = pipeline.run(variant)
    bundle.verify_bundle_integrity()

    # Tamper with bundle digest
    tampered_bundle = BiologicalEvidenceBundle(
        target_variant=bundle.target_variant,
        pipeline_version=bundle.pipeline_version,
        execution_timestamp_ns=bundle.execution_timestamp_ns,
        total_wall_time_ms=bundle.total_wall_time_ms,
        records=bundle.records,
        provenance_chain=bundle.provenance_chain,
        source_errors=bundle.source_errors,
        bundle_digest="sha256:" + "0" * 64,
    )
    with pytest.raises(RuntimeError) as exc:
        tampered_bundle.verify_bundle_integrity()
    assert SourceHaltCode.HALT_SOURCE_DIGEST_MISMATCH.value in str(exc.value)

    # Tamper with provenance chain
    tampered_chain = BiologicalEvidenceBundle(
        target_variant=bundle.target_variant,
        pipeline_version=bundle.pipeline_version,
        execution_timestamp_ns=bundle.execution_timestamp_ns,
        total_wall_time_ms=bundle.total_wall_time_ms,
        records=bundle.records,
        provenance_chain=("sha256:corrupted",),
        source_errors=bundle.source_errors,
        bundle_digest=bundle.bundle_digest,
    )
    with pytest.raises(RuntimeError) as exc2:
        tampered_chain.verify_bundle_integrity()
    assert SourceHaltCode.HALT_SOURCE_DIGEST_MISMATCH.value in str(exc2.value)
    assert "Bundle provenance chain does not match record digests" in str(exc2.value)


def test_5_evaluation_and_verdicts() -> None:
    variant = get_grch38_cftr_variant()
    pipeline = VariantEvidencePipeline()
    bundle = pipeline.run(variant)

    verdicts = VariantEvidencePipeline.evaluate(bundle)
    assert len(verdicts) >= 1
    for v in verdicts:
        assert v.verdict.value in ("SUPPORTS", "REFUTES", "UNKNOWN")
        assert 0 <= v.confidence_bps <= 10000


def test_6_eo1_latch_integration() -> None:
    variant = get_grch38_cftr_variant()
    tmp_dir = Path(tempfile.mkdtemp(prefix="test_pipeline_latch_"))
    try:
        ledger_dir = tmp_dir / "ledger"
        archive_dir = tmp_dir / "archive"

        signing_key = Ed25519PrivateKey.generate()
        public_key = signing_key.public_key()
        latch = EO1BioEvidenceLatch(ledger_dir=ledger_dir, signing_key=signing_key)
        context_cart = BioContextCart(archive_dir=archive_dir)

        hypothesis = "Test hypothesis for CFTR variant"
        bundle, reproducible = VariantEvidencePipeline.execute_with_hypothesis_latch(
            variant=variant,
            hypothesis=hypothesis,
            latch=latch,
            context_cart=context_cart,
        )

        assert reproducible.operation_id.startswith("bio-op:")
        assert reproducible.hypothesis == hypothesis
        assert len(reproducible.claims) >= 1
        assert len(reproducible.context_cards) == len(bundle.records)

        # Offline Ed25519 signature verification
        sig_bytes = base64.b64decode(reproducible.ed25519_signature_b64)
        deterministic_core = canonical_json_v1(
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
        public_key.verify(sig_bytes, deterministic_core)
        assert sha256_prefixed(deterministic_core) == reproducible.bundle_digest

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_7_epistemic_purity() -> None:
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
        Path("src/variant_evidence_pipeline.py"),
        Path("benchmarks/variant_evidence_benchmark.py"),
        Path("tests/test_variant_evidence_pipeline.py"),
    ]
    for p in target_files:
        if not p.exists():
            continue
        content = p.read_text(encoding="utf-8").lower()
        for tok in forbidden_tokens:
            assert tok not in content, f"Forbidden promotional term '{tok}' found in {p}"
