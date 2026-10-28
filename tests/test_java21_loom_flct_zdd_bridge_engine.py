"""Tests for Java 21 Loom Virtual-Thread + Zero-Copy FLCT/ZDD Bridge Engine (Section 29)."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

from src.java21_loom_flct_zdd_bridge_engine import (
    FieldsMedalistConceptualCompressionGate,
    GradiumPhononEdgeVoiceStepUpGate,
    Java21LoomFlctNativeBridge,
    KnuthZddCombinatorialCompressor,
    ParallelJava21LoomAndZddBridgeEngine,
    main,
)


def test_worker1_compiled_java21_loom_and_flct_zero_copy_bridge() -> None:
    res = Java21LoomFlctNativeBridge.run_experiment()
    assert res.passed is True
    assert int(res.achieved_metric) == 20
    assert res.improvement_bps == 9 * 1000
    assert res.violations_found == 0

    naive = res.details["naive_draft_falsification"]
    assert naive["duplicate_points_bug_confirmed"] is True
    assert naive["unique_points_count"] == 2
    assert naive["naive_path_output"] == [0, 0, 1, 0, 0, 1, 0, 0]

    java_out = res.details["compiled_openjdk21_output"]
    assert int(java_out["flct_zero_copy_capset_f3_4_size"]) == 20
    assert java_out["flct_collinear_violations"] == 0
    assert int(java_out["golomb_8_mark_span"]) == 34
    assert java_out["golomb_8_mark_valid"] is True
    assert java_out["virtual_threads_is_virtual_verified"] == 1024


def test_worker2_knuth_zdd_canonical_dag_compression(monkeypatch) -> None:
    res = KnuthZddCombinatorialCompressor.run_experiment()
    assert res.passed is True
    assert res.baseline_metric == 2047
    assert res.achieved_metric == 4 * 7
    assert res.improvement_bps == 9863

    # Boundary check at canonical_zdd_nodes == 61 (> 60 threshold) & forward index order (i + 1) % n
    class _IndexRecorder(tuple):
        def __init__(self, iterable):
            self.accessed = []

        def __getitem__(self, idx):
            self.accessed.append(idx)
            return super().__getitem__(idx)

    def spy_build_zdd(n_vars, pred):
        probe = _IndexRecorder((1, 0, 0, 0, 0, 0, 0, 0, 0, 0))
        pred(probe)
        assert probe.accessed[:2] == [0, 1]
        return {
            "n_vars": n_vars,
            "raw_decision_tree_nodes": 2047,
            "canonical_zdd_nodes": 60 + 1,
            "zdd_root_id": 2,
            "compression_bps": 9702,
        }

    monkeypatch.setattr(
        KnuthZddCombinatorialCompressor,
        "build_zdd_for_valid_subsets",
        staticmethod(spy_build_zdd),
    )
    assert KnuthZddCombinatorialCompressor.run_experiment().passed is False


def test_worker3_fields_medalist_conceptual_compression_gate(monkeypatch) -> None:
    res = FieldsMedalistConceptualCompressionGate.run_experiment()
    assert res.passed is True
    assert res.improvement_bps >= 8000
    assert (
        res.details["distilled_generator_audit"]["status_code"]
        == "VERIFIED_HUMAN_COMPREHENSIBLE_GENERATOR"
    )
    assert (
        res.details["opaque_brute_force_audit"]["status_code"]
        == "HALT_OPAQUE_BRUTE_FORCE_WITNESS_REJECTED"
    )
    assert res.details["fake_short_descriptor_audit"]["passed"] is False
    assert (
        res.details["fake_short_descriptor_audit"]["reconstructed_point_count"]
        == 0
    )

    # Verify conjunction in run_experiment rejects when negative control unexpectedly passes
    calls = [0]

    def fake_eval(*args, **kwargs):
        calls[0] += 1
        return {
            "passed": True,
            "status_code": "VERIFIED_HUMAN_COMPREHENSIBLE_GENERATOR",
            "raw_witness_bytes": 100,
            "generator_law_bytes": 10,
            "conceptual_compression_bps": 9000,
        }

    monkeypatch.setattr(
        FieldsMedalistConceptualCompressionGate,
        "evaluate_conceptual_compression",
        staticmethod(fake_eval),
    )
    assert FieldsMedalistConceptualCompressionGate.run_experiment().passed is False


def test_worker4_gradium_phonon_edge_voice_stepup_gate() -> None:
    res = GradiumPhononEdgeVoiceStepUpGate.run_experiment()
    assert res.passed is True
    assert res.details["cloud_egress_bytes"] == 0
    assert res.details["execution_status"] == "TEXT_LINT_ONLY"
    assert (
        res.details["model_profile"]
        == "TEXT_ALERT_PACKETIZER_PHONON_WEIGHTS_NOT_LOADED"
    )


def test_parallel_java21_zdd_orchestrator_and_cli(
    tmp_path: Path, monkeypatch
) -> None:
    bundle = ParallelJava21LoomAndZddBridgeEngine.run_all_4_parallel()
    assert bundle["all_passed"] is True
    assert bundle["workers_executed"] == 4
    assert bundle["total_violations"] == 0
    assert (
        ParallelJava21LoomAndZddBridgeEngine.verify_bundle_signature(bundle)
        is True
    )

    tampered = dict(bundle)
    tampered["total_checks_executed"] = 0
    assert (
        ParallelJava21LoomAndZddBridgeEngine.verify_bundle_signature(tampered)
        is False
    )

    out_file = tmp_path / "java21_bundle.json"
    monkeypatch.setattr(
        ParallelJava21LoomAndZddBridgeEngine,
        "run_all_4_parallel",
        classmethod(lambda cls, signing_key=None: bundle),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["prog", "--self-test", "--export-bundle", str(out_file)],
    )
    assert main() == 0
    assert out_file.exists()

    # Verify CLI main() raises SystemExit(1) when signature check fails
    monkeypatch.setattr(
        ParallelJava21LoomAndZddBridgeEngine,
        "verify_bundle_signature",
        staticmethod(lambda b: False),
    )
    with pytest.raises(SystemExit):
        main()


def test_epistemic_no_banned_words_in_section_29() -> None:
    banned = [
        "guaran" + "teed",
        "proven universal" + "ly",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
    ]
    targets = [
        Path("src/java/io/sovereign/nexus/SovereignVirtualThreadProver.java"),
        Path("src/java21_loom_flct_zdd_bridge_engine.py"),
        Path("tests/test_java21_loom_flct_zdd_bridge_engine.py"),
    ]
    for path in targets:
        text = path.read_text(encoding="utf-8").lower()
        for word in banned:
            assert word not in text, f"Forbidden phrase in {path}"
