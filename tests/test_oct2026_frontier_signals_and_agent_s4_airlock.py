"""Tests for October 2026 Frontier Signals & Governed Agent-S4 Evolution Airlock (Section 28)."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest

from src.oct2026_frontier_signals_and_agent_s4_airlock import (
    DeterministicMultiLangSqliteAcidVerifier,
    GovernedAgentS4InterfaceEvolutionAirlock,
    Oct2026SupplyChainAndStorm0940DefenseGate,
    ParallelOct2026FrontierSignalsEngine,
    Sub50msDecisionAndCalibratedFocusEngine,
)


def test_signal01_sub50ms_400_decisions_and_calibrated_rerank() -> None:
    res = Sub50msDecisionAndCalibratedFocusEngine.run_experiment()
    assert res.passed is True
    assert res.violations_found == 0
    assert res.sovereign_verified_metric >= 6000.0
    assert res.details["batch_400_decisions_count"] == 400
    assert res.details["batch_400_approved_count"] == 244

    # Negative control: >400 questions in a single Decisions batch raises limit error
    with pytest.raises(ValueError, match="HALT_DECISIONS_BATCH_EXCEEDS_400_LIMIT"):
        Sub50msDecisionAndCalibratedFocusEngine.evaluate_400_decisions_batch(
            [{"q_id": i} for i in range(401)]
        )


def test_signal02_agent_s4_governed_tool_evolution_airlock() -> None:
    res = GovernedAgentS4InterfaceEvolutionAirlock.run_experiment()
    assert res.passed is True
    assert res.improvement_bps == 7500
    assert (
        res.details["missing_caid_rejected"]
        == "HALT_EVOLVED_INTERFACE_MISSING_CAID"
    )
    assert (
        res.details["unsafe_ast_rejected"]
        == "HALT_EVOLVED_INTERFACE_UNSAFE_AST"
    )


def test_signal03_litellm_node_brotli_and_storm0940_defense() -> None:
    res = Oct2026SupplyChainAndStorm0940DefenseGate.run_experiment()
    assert res.passed is True
    assert res.violations_found == 0
    assert (
        res.details["litellm_1_107_0_verdict"]
        == "HALT_POISONED_DEPENDENCY_LITELLM_1_107_0"
    )
    assert (
        res.details["nodejs_22_23_0_verdict"]
        == "HALT_VULNERABLE_NODEJS_BROTLI_RCE"
    )
    assert (
        res.details["storm0940_2900_rpm_verdict"]
        == "HALT_STORM0940_AGENT_VELOCITY_BREAKER"
    )


def test_signal04_multilangbench_sqlite_acid_and_omniparse_scorer() -> None:
    res = DeterministicMultiLangSqliteAcidVerifier.run_experiment()
    assert res.passed is True
    assert res.checks_executed == 20
    assert res.violations_found == 0
    assert res.sovereign_verified_metric == 10000.0

    # Negative control: malformed COBOL fixed-width line rejected
    with pytest.raises(ValueError, match="HALT_COBOL_FIXED_WIDTH_LENGTH_INVALID"):
        DeterministicMultiLangSqliteAcidVerifier.parse_cobol_fixed_width_record(
            "SHORT_LINE"
        )


def test_parallel_oct2026_signals_orchestrator_and_cli(tmp_path: Path) -> None:
    bundle = ParallelOct2026FrontierSignalsEngine.run_all_4_parallel()
    assert bundle["all_passed"] is True
    assert bundle["workers_executed"] == 4
    assert bundle["total_violations"] == 0
    assert (
        ParallelOct2026FrontierSignalsEngine.verify_bundle_signature(bundle)
        is True
    )

    tampered = dict(bundle)
    tampered["total_checks_executed"] = 999999
    assert (
        ParallelOct2026FrontierSignalsEngine.verify_bundle_signature(tampered)
        is False
    )

    out_json = tmp_path / "oct2026_bundle.json"
    proc = subprocess.run(
        [
            sys.executable,
            "src/oct2026_frontier_signals_and_agent_s4_airlock.py",
            "--self-test",
            "--export-bundle",
            str(out_json),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert out_json.exists()


def test_epistemic_no_banned_words_in_sections_27_and_28() -> None:
    banned = [
        "guaran" + "teed",
        "proven universal" + "ly",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
    ]
    targets = [
        Path("tools/parallel_open_frontier_and_urgent_solver.py"),
        Path("src/oct2026_frontier_signals_and_agent_s4_airlock.py"),
        Path("tests/test_oct2026_frontier_signals_and_agent_s4_airlock.py"),
    ]
    for path in targets:
        text = path.read_text(encoding="utf-8").lower()
        for word in banned:
            assert word not in text, f"Forbidden phrase in {path}"
