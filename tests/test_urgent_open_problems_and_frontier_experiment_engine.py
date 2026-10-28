"""Tests for Parallel Frontier Math & Urgent 2026 AI Verification Bottleneck Engine (Section 26)."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from src.proof_carrying_lean4_airlock import LeanComparatorSandboxAuditor
from src.urgent_open_problems_and_frontier_experiment_engine import (
    AgentDelegationEdge,
    BilinearMatMulTensorProver,
    DynamicPrivilegeAttenuationProver,
    ParallelUrgentOpenProblemsExperimentEngine,
    PatternBoostZarankiewiczProver,
    RepoScaleAssumeGuaranteeCohesionEngine,
    SpecMutantSensitivityProver,
    TaoEquationalMagmaProver,
    ViazovskaE8KissingAndHammingProver,
)


def test_math08_bilinear_matmul_tensor_64_brent_equations_and_falsification() -> None:
    witness = BilinearMatMulTensorProver.run_experiment()
    assert witness.verification_passed is True
    assert witness.exhaustive_checks_executed == 64
    assert witness.constraint_violations == 0
    assert witness.improvement_bps == 2344

    # Negative control: flip one sign in U_FACTORS[0][0] -> violates Brent tensor identity
    corrupted_u = [list(r) for r in BilinearMatMulTensorProver.U_FACTORS]
    corrupted_u[0][0] = -1
    passed, checked, violations, status = (
        BilinearMatMulTensorProver.verify_brent_tensor_equations(
            corrupted_u,
            BilinearMatMulTensorProver.V_FACTORS,
            BilinearMatMulTensorProver.W_FACTORS,
        )
    )
    assert passed is False
    assert checked == 64
    assert violations > 0
    assert status == "HALT_BRENT_TENSOR_IDENTITY_VIOLATED"


def test_math09_tao_equational_magma_1485_and_lean4_comparator(
    tmp_path: Path,
) -> None:
    witness = TaoEquationalMagmaProver.run_experiment(proofs_dir=tmp_path)
    assert witness.verification_passed is True
    assert witness.exhaustive_checks_executed == 4 ** 3
    assert witness.constraint_violations == 0
    assert witness.witness_summary["lean4_text_lint_passed"] is True
    assert (tmp_path / "Math09TaoEquationalMagma.lean").exists()

    # Negative control 1: Constant zero magma is associative/commutative, so it fails anti-implication
    zero_table = [[0] * 4 for _ in range(4)]
    passed_zero, _, _, _ = TaoEquationalMagmaProver.verify_cayley_table(
        zero_table
    )
    assert passed_zero is False

    # Negative control 2: Inject `sorry` into Math09TaoEquationalMagma.lean -> rejected by comparator
    spec, clean_lean = TaoEquationalMagmaProver.build_lean4_challenge_and_proof()
    tampered_lean = clean_lean.replace(":= by decide", ":= by sorry")
    verdict = LeanComparatorSandboxAuditor.verify_submission_against_trusted_spec(
        spec, tampered_lean
    )
    assert verdict.passed is False
    assert verdict.rejection_code == "HALT_COMPARATOR_SORRY_AXIOM_DETECTED"


def test_math10_patternboost_zarankiewicz_c4_free_optimal_21_edges() -> None:
    witness = PatternBoostZarankiewiczProver.run_experiment()
    assert witness.verification_passed is True
    assert float(witness.naive_or_vibe_baseline_metric) == 13.0
    assert float(witness.sovereign_verified_metric) == 21.0
    assert witness.improvement_bps == 6154
    assert witness.constraint_violations == 0

    # Negative control: Adding a 22nd edge to the 7x7 PG(2,2) incidence matrix forces a C4 cycle
    adj = PatternBoostZarankiewiczProver.construct_optimal_fano_pg22_incidence()
    added = False
    for i in range(7):
        for j in range(7):
            if adj[i][j] == 0:
                adj[i][j] = 1
                added = True
                break
        if added:
            break
    ok, _, violations = PatternBoostZarankiewiczProver.has_no_c4(adj)
    assert ok is False
    assert violations >= 1


def test_math11_viazovska_e8_kissing_240_and_extended_hamming_16() -> None:
    witness = ViazovskaE8KissingAndHammingProver.run_experiment()
    assert witness.verification_passed is True
    assert float(witness.sovereign_verified_metric) == 240.0
    assert witness.exhaustive_checks_executed == 28680 + 120
    assert witness.constraint_violations == 0
    assert witness.witness_summary["e8_max_pairwise_inner_product"] == 4
    assert witness.witness_summary["extended_hamming_min_distance"] == 4


def test_urgent_ai_01_vibe_coding_spec_wall_vacuity_detection() -> None:
    witness = SpecMutantSensitivityProver.run_experiment()
    assert witness.verification_passed is True
    assert witness.naive_or_vibe_baseline_metric == 2500.0
    assert witness.sovereign_verified_metric == 10000.0
    assert witness.improvement_bps == 7500

    vibe_audit = witness.witness_summary["vibe_coded_spec_audit"]
    assert vibe_audit["passed"] is False
    assert (
        vibe_audit["status_code"]
        == "HALT_VACUOUS_OR_WEAKENED_SPECIFICATION"
    )
    assert len(vibe_audit["surviving_mutants"]) == 6


def test_urgent_ai_02_repo_scale_assume_guarantee_cohesion() -> None:
    witness = RepoScaleAssumeGuaranteeCohesionEngine.run_experiment()
    assert witness.verification_passed is True
    assert witness.improvement_bps == 8333
    reg_audit = witness.witness_summary["injected_m3_regression_audit"]
    assert reg_audit["passed"] is False
    assert (
        reg_audit["status_code"]
        == "HALT_CROSS_FILE_ASSUME_GUARANTEE_BROKEN"
    )
    assert "M3_TCC_ESCROW_LEDGER->M4_EO1_LATCH" in reg_audit["broken_edges"]


def test_urgent_ai_03_dynamic_privilege_creep_lattice_prover() -> None:
    witness = DynamicPrivilegeAttenuationProver.run_experiment()
    assert witness.verification_passed is True
    assert (
        witness.witness_summary["scope_escalation_caught"]
        == "HALT_DYNAMIC_SCOPE_ESCALATION_DETECTED"
    )
    assert (
        witness.witness_summary["budget_amplification_caught"]
        == "HALT_SUBAGENT_BUDGET_AMPLIFICATION"
    )
    assert (
        witness.witness_summary["transitive_taint_loop_caught"]
        == "HALT_TRANSITIVE_PRIVILEGE_ESCALATION_LOOP"
    )

    # Direct negative test on custom edge
    bad_edge = [
        AgentDelegationEdge(
            parent_agent="P",
            child_agent="C",
            parent_scopes=("read",),
            child_scopes=("read", "write"),
            parent_budget_minor=100,
            child_budget_minor=50,
            parent_taint_tier=0,
            child_taint_tier=0,
        )
    ]
    res = DynamicPrivilegeAttenuationProver.verify_delegation_swarm_lattice(
        bad_edge
    )
    assert res["passed"] is False
    assert res["status_code"] == "HALT_DYNAMIC_SCOPE_ESCALATION_DETECTED"


def test_parallel_all_7_orchestrator_and_cli_export(tmp_path: Path) -> None:
    bundle = ParallelUrgentOpenProblemsExperimentEngine.run_all_7_parallel(
        proofs_dir=tmp_path
    )
    assert bundle["all_passed"] is True
    assert bundle["problems_solved_count"] == 7
    assert bundle["total_constraint_violations"] == 0
    assert (
        ParallelUrgentOpenProblemsExperimentEngine.verify_bundle_signature(
            bundle
        )
        is True
    )

    # Tamper with bundle -> signature verification fails closed
    tampered = dict(bundle)
    tampered["total_exhaustive_checks_executed"] = 999999
    assert (
        ParallelUrgentOpenProblemsExperimentEngine.verify_bundle_signature(
            tampered
        )
        is False
    )

    # CLI test & boundary oracles (lines 299, 766, 869, 901, 1072, 1380)
    assert TaoEquationalMagmaProver.verify_cayley_table([[0] * 4 for _ in range(4)])[3][
        "non_commutative_witness_pairs"
    ] == 0
    assert (
        SpecMutantSensitivityProver.audit_specification_strength(
            lambda st, exp: exp != 15 * 100
        )["killed_mutants_count"]
        == 8
    )
    pipe = RepoScaleAssumeGuaranteeCohesionEngine.build_6_module_pipeline()
    assert pipe["M3_TCC_ESCROW_LEDGER"].assume_predicate({}) is False
    assert pipe["M3_TCC_ESCROW_LEDGER"].assume_predicate({"amount_minor": 1}) is True
    assert (
        pipe["M6_SCITT_TRANSPARENCY_ANCHOR"].assume_predicate(
            {"comparator_verified": True, "ed25519_signed": False}
        )
        is False
    )
    bad_edge_res = DynamicPrivilegeAttenuationProver.verify_delegation_swarm_lattice(
        [
            AgentDelegationEdge(
                parent_agent="P",
                child_agent="C",
                parent_scopes=("read",),
                child_scopes=("read", "write"),
                parent_budget_minor=100,
                child_budget_minor=50,
                parent_taint_tier=0,
                child_taint_tier=0,
            )
        ]
    )
    assert bad_edge_res["checks_executed"] == 1

    import builtins
    import src.urgent_open_problems_and_frontier_experiment_engine as u_mod

    out_file = tmp_path / "bundle.json"
    orig_argv = sys.argv
    orig_print = builtins.print
    orig_run7 = ParallelUrgentOpenProblemsExperimentEngine.run_all_7_parallel
    printed = []
    sys.argv = [
        "urgent_open_problems_and_frontier_experiment_engine.py",
        "--self-test",
        "--export-bundle",
        str(out_file),
    ]
    builtins.print = lambda *a, **kw: printed.append(a)  # type: ignore[assignment]
    ParallelUrgentOpenProblemsExperimentEngine.run_all_7_parallel = classmethod(  # type: ignore[assignment]
        lambda cls, signing_key=None, proofs_dir=None: bundle
    )
    try:
        assert u_mod.main() == 0
        assert len(printed) == 1
        assert out_file.exists()
    finally:
        sys.argv = orig_argv
        builtins.print = orig_print  # type: ignore[assignment]
        ParallelUrgentOpenProblemsExperimentEngine.run_all_7_parallel = orig_run7  # type: ignore[assignment]


def test_epistemic_no_banned_words_in_section_26() -> None:
    banned = [
        "guaran" + "teed",
        "proven universal" + "ly",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
    ]
    targets = [
        Path("src/urgent_open_problems_and_frontier_experiment_engine.py"),
        Path("tests/test_urgent_open_problems_and_frontier_experiment_engine.py"),
        Path("proofs/Math09TaoEquationalMagma.lean"),
    ]
    for path in targets:
        text = path.read_text(encoding="utf-8").lower()
        for word in banned:
            assert word not in text, f"Forbidden phrase in {path}"
