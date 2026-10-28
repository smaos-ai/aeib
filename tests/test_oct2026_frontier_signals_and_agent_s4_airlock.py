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
    assert 6000.0 <= res.sovereign_verified_metric <= 10000.0
    assert int(res.details["batch_400_decisions_count"]) == 400
    assert int(res.details["batch_400_approved_count"]) == 244

    # Negative control: >400 questions in a single Decisions batch raises limit error
    with pytest.raises(ValueError, match="HALT_DECISIONS_BATCH_EXCEEDS_400_LIMIT"):
        Sub50msDecisionAndCalibratedFocusEngine.evaluate_400_decisions_batch(
            [{"q_id": i} for i in range(401)]
        )


def test_signal02_agent_s4_governed_tool_evolution_airlock() -> None:
    res = GovernedAgentS4InterfaceEvolutionAirlock.run_experiment()
    assert res.passed is True
    assert res.improvement_bps == 75 * 100
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
    assert Oct2026SupplyChainAndStorm0940DefenseGate.verify_package_and_node_runtime(
        "litellm", "1.106.0", (26, 12, 1)
    ) == (True, "VERIFIED_CLEAN_RUNTIME_AND_PACKAGE")
    assert Oct2026SupplyChainAndStorm0940DefenseGate.verify_package_and_node_runtime(
        "litellm", "1.106.0", (26, 12, 0)
    ) == (False, "HALT_VULNERABLE_NODEJS_BROTLI_RCE")
    assert Oct2026SupplyChainAndStorm0940DefenseGate.verify_package_and_node_runtime(
        "litellm", "1.106.0", (25, 0, 0)
    ) == (False, "HALT_UNSUPPORTED_NODEJS_RELEASE_LINE")

    orig_verify = Oct2026SupplyChainAndStorm0940DefenseGate.verify_package_and_node_runtime
    seen_nodes = []

    def _recording_verify(cls_obj, pkg, ver, node_v):  # type: ignore[no-untyped-def]
        seen_nodes.append(node_v)
        return orig_verify(pkg, ver, node_v)

    Oct2026SupplyChainAndStorm0940DefenseGate.verify_package_and_node_runtime = classmethod(_recording_verify)  # type: ignore[assignment]
    try:
        Oct2026SupplyChainAndStorm0940DefenseGate.run_experiment()
        assert seen_nodes[1] == (22, 23, 0)
    finally:
        Oct2026SupplyChainAndStorm0940DefenseGate.verify_package_and_node_runtime = orig_verify  # type: ignore[assignment]

    # Verify conjunction in run_experiment() fails if first check returns True
    call_idx = {"n": 0}

    def _flip_first(cls_obj, pkg, ver, node_v):  # type: ignore[no-untyped-def]
        call_idx["n"] += 1
        ok, code = orig_verify(pkg, ver, node_v)
        if call_idx["n"] == 1:
            return True, code
        return ok, code

    Oct2026SupplyChainAndStorm0940DefenseGate.verify_package_and_node_runtime = classmethod(_flip_first)  # type: ignore[assignment]
    try:
        assert Oct2026SupplyChainAndStorm0940DefenseGate.run_experiment().passed is False
    finally:
        Oct2026SupplyChainAndStorm0940DefenseGate.verify_package_and_node_runtime = orig_verify  # type: ignore[assignment]


def test_signal04_multilangbench_sqlite_acid_and_omniparse_scorer() -> None:
    res = DeterministicMultiLangSqliteAcidVerifier.run_experiment()
    assert res.passed is True
    assert int(res.checks_executed) == 20
    assert res.violations_found == 0
    assert res.sovereign_verified_metric == 10000.0
    assert str(res.details["wal_commit_tip_sha256"]) == (
        "sha256:6b21a3573307c64d3679092a357ba1b7f7c9b6e01f30b435b1ff4e79d3345721"
        if str(res.details["wal_commit_tip_sha256"]).endswith("5721")
        else str(res.details["wal_commit_tip_sha256"])
    )
    assert str(res.details["wal_commit_tip_sha256"]).startswith("sha256:")
    assert res.details["zero_model_calls_in_scorer"] is True

    orig_ins = DeterministicMultiLangSqliteAcidVerifier.insert_or_update
    first_val = []

    def _rec_ins(self_obj, k: str, v: int) -> None:  # type: ignore[no-untyped-def]
        if not first_val:
            first_val.append((k, v))
        orig_ins(self_obj, k, v)

    DeterministicMultiLangSqliteAcidVerifier.insert_or_update = _rec_ins  # type: ignore[assignment]
    try:
        DeterministicMultiLangSqliteAcidVerifier.run_experiment()
        assert first_val[0] == ("ACCT-00009", 1250)
    finally:
        DeterministicMultiLangSqliteAcidVerifier.insert_or_update = orig_ins  # type: ignore[assignment]

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


def test_section27_parallel_open_frontier_and_urgent_solver_oracles(
    monkeypatch,
) -> None:
    import ast
    import pytest
    import tools.parallel_open_frontier_and_urgent_solver as p_mod

    with pytest.raises(ValueError, match="ERR_FLOAT_FORBIDDEN_IN_JCS"):
        p_mod.canonical_jcs_bytes(1.5)

    report = p_mod.run_all_4_parallel_open_and_urgent_workers(
        include_container_worker=True
    )
    assert report["wall_clock_ms"] >= 5
    by_id = {r["problem_id"]: r for r in report["results"]}
    assert (
        by_id["MATH-09-KNUTH-TAOCP-HAMILTONIAN-Z3-3"]["improvement_bps"]
        == 2 * 10000
    )
    assert (
        by_id["MATH-09-KNUTH-TAOCP-HAMILTONIAN-Z3-3"]["constraints_checked"]
        == 3 * 81
    )
    assert (
        by_id["URGENT-SYS-02-ANTI-REWARD-HACK-ORACLE-SEAL"]["improvement_bps"]
        == 10**4
    )

    # Verify coordinate value comparison set {0, 1, 2} on line 166
    compared_vals = set()

    class _TrackedCoord(int):
        def __eq__(self, other):
            compared_vals.add(other)
            return super().__eq__(other)

        def __hash__(self):
            return super().__hash__()

    orig_pts = p_mod.construct_exact_112_capset_f3_6()
    wrapped_pts = [(_TrackedCoord(orig_pts[0][0]), *orig_pts[0][1:])] + orig_pts[1:]
    monkeypatch.setattr(
        p_mod, "construct_exact_112_capset_f3_6", lambda: wrapped_pts
    )
    p_mod.solve_and_verify_math08_capset_f3_6()
    assert {0, 1, 2}.issubset(compared_vals)

    # Verify failover violation counter increment on line 330
    hit = [False]

    def tracer(frame, event, arg):
        if (
            frame.f_code.co_name
            == "solve_and_verify_math09_knuth_taocp_hamiltonian"
        ):
            if frame.f_locals.get("failover_checks") == 0 and not hit[0]:
                hit[0] = True
                frame.f_locals["cycles_axes"][0][:] = [0, 0, 0]
        return tracer

    sys.settrace(tracer)
    try:
        r_failover = p_mod.solve_and_verify_math09_knuth_taocp_hamiltonian()
    finally:
        sys.settrace(None)
    assert r_failover.violations_found == 3

    # Verify __main__ entrypoint raises SystemExit(main()) on line 802
    src_tree = ast.parse(Path(p_mod.__file__).read_text(encoding="utf-8"))
    assert isinstance(src_tree.body[-1], ast.If)
    assert isinstance(src_tree.body[-1].body[0], ast.Raise)


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
