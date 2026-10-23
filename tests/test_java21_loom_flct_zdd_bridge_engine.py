"""Tests for Java 21 Loom Virtual-Thread + Zero-Copy FLCT/ZDD Bridge Engine (Section 29)."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from src.java21_loom_flct_zdd_bridge_engine import (
    FieldsMedalistConceptualCompressionGate,
    GradiumPhononEdgeVoiceStepUpGate,
    Java21LoomFlctNativeBridge,
    KnuthZddCombinatorialCompressor,
    ParallelJava21LoomAndZddBridgeEngine,
)


def test_worker1_compiled_java21_loom_and_flct_zero_copy_bridge() -> None:
    res = Java21LoomFlctNativeBridge.run_experiment()
    assert res.passed is True
    assert res.achieved_metric == 20
    assert res.violations_found == 0

    naive = res.details["naive_draft_falsification"]
    assert naive["duplicate_points_bug_confirmed"] is True
    assert naive["unique_points_count"] == 2

    java_out = res.details["compiled_openjdk21_output"]
    assert java_out["flct_zero_copy_capset_f3_4_size"] == 20
    assert java_out["flct_collinear_violations"] == 0
    assert java_out["golomb_8_mark_span"] == 34
    assert java_out["golomb_8_mark_valid"] is True
    assert java_out["virtual_threads_is_virtual_verified"] == 1024


def test_worker2_knuth_zdd_canonical_dag_compression() -> None:
    res = KnuthZddCombinatorialCompressor.run_experiment()
    assert res.passed is True
    assert res.baseline_metric == 2047
    assert res.achieved_metric <= 60
    assert res.improvement_bps >= 9700


def test_worker3_fields_medalist_conceptual_compression_gate() -> None:
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


def test_worker4_gradium_phonon_edge_voice_stepup_gate() -> None:
    res = GradiumPhononEdgeVoiceStepUpGate.run_experiment()
    assert res.passed is True
    assert res.details["cloud_egress_bytes"] == 0
    assert res.details["ttfa_under_6900_micros_budget"] is True
    assert res.improvement_bps >= 9800


def test_parallel_java21_zdd_orchestrator_and_cli(tmp_path: Path) -> None:
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
    proc = subprocess.run(
        [
            sys.executable,
            "src/java21_loom_flct_zdd_bridge_engine.py",
            "--self-test",
            "--export-bundle",
            str(out_file),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert out_file.exists()


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
