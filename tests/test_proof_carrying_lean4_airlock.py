"""Verification suite for Proof-Carrying Contract (PC2) Escrow Airlock and
Lean 4 Comparator Sandbox Auditor (Section 24).
"""

from __future__ import annotations

import shutil
from pathlib import Path

from src.capability_status import REAL_EXECUTED, TEXT_LINT_ONLY
from src.proof_carrying_lean4_airlock import (
    LEAN_NOT_EXECUTED,
    Lean4WitnessCertificateExporter,
    LeanComparatorSandboxAuditor,
    Pc2ProofCarryingEscrowAirlock,
    ProofCarryingContractEscrow,
    verify_barker13_energy,
)


def test_pc2_airlock_and_lean_comparator_adversarial_falsification(tmp_path: Path) -> None:
    """Verify that PC2 Airlock rejects sorryAx, custom axiom, definition tampering,
    and comment-smuggled false theorems, and holds escrow when `lean` binary is absent.
    """
    airlock = Pc2ProofCarryingEscrowAirlock()
    barker_seq = [1, 1, 1, 1, 1, -1, -1, 1, 1, -1, 1, -1, 1]
    spec, valid_lean = (
        Lean4WitnessCertificateExporter.build_labs_barker13_challenge_and_solution(
            barker_seq
        )
    )
    contract = ProofCarryingContractEscrow(
        contract_id="pc2-contract-radar-barker13",
        client_id="org:aerospace-dsp",
        contractor_agent_id="agent:sovereign-prover-w6",
        escrow_amount_minor=2500_00,
        required_challenge_spec=spec,
        deterministic_evaluator_fn=verify_barker13_energy,
    )
    airlock.register_contract_and_lock_escrow(contract)

    # 1. Falsification A: `sorry` injection -> HALT_COMPARATOR_SORRY_AXIOM_DETECTED
    sorry_lean = valid_lean.replace(":= by decide", ":= by sorry")
    res_sorry = airlock.submit_proof_carrying_deliverable(
        "pc2-contract-radar-barker13", sorry_lean, barker_seq
    )
    assert res_sorry["disposition"] == "AIRLOCK_REJECTED_PROOF"
    assert res_sorry["code"] == "HALT_COMPARATOR_SORRY_AXIOM_DETECTED"
    assert contract.status == "ESCROW_LOCKED"

    # 2. Falsification B: Custom `axiom` injection -> HALT_COMPARATOR_CUSTOM_AXIOM_FORBIDDEN
    axiom_lean = "axiom fake_proof : True\n" + valid_lean
    res_ax = airlock.submit_proof_carrying_deliverable(
        "pc2-contract-radar-barker13", axiom_lean, barker_seq
    )
    assert res_ax["disposition"] == "AIRLOCK_REJECTED_PROOF"
    assert res_ax["code"] == "HALT_COMPARATOR_CUSTOM_AXIOM_FORBIDDEN"
    assert contract.status == "ESCROW_LOCKED"

    # 3. Falsification C: Definition redefinition -> HALT_COMPARATOR_DEFINITION_REDEFINITION_DETECTED
    redef_lean = valid_lean.replace("acc + c * c) 0", "6) 6")
    res_redef = airlock.submit_proof_carrying_deliverable(
        "pc2-contract-radar-barker13", redef_lean, barker_seq
    )
    assert res_redef["disposition"] == "AIRLOCK_REJECTED_PROOF"
    assert res_redef["code"] == "HALT_COMPARATOR_DEFINITION_REDEFINITION_DETECTED"
    assert contract.status == "ESCROW_LOCKED"

    # 4. Falsification D: Comment-hidden required theorem clause rejected by comment stripper
    comment_bypass = (
        f"{spec.trusted_definitions_lean}\n"
        f"/-\n{spec.trusted_theorem_header_lean.strip()} := by decide\n-/\n"
        "theorem false_claim : 0 = 1 := by decide\n"
    )
    res_comment = airlock.submit_proof_carrying_deliverable(
        "pc2-contract-radar-barker13", comment_bypass, barker_seq
    )
    assert res_comment["disposition"] == "AIRLOCK_REJECTED_PROOF"
    assert contract.status == "ESCROW_LOCKED"

    # 5. Falsification E: False theorem appended after valid text never releases escrow
    false_theorem_lean = valid_lean + "\ntheorem contradiction : 0 = 1 := by decide\n"
    res_false = airlock.submit_proof_carrying_deliverable(
        "pc2-contract-radar-barker13", false_theorem_lean, barker_seq
    )
    assert res_false["disposition"] != "AIRLOCK_ACCEPTED_ESCROW_RELEASED"
    assert contract.status == "ESCROW_LOCKED"

    # 6. Nominal submission: if `lean` is installed on PATH, kernel executes and escrow releases;
    #    if `lean` is absent, status is TEXT_LINT_ONLY and escrow remains locked.
    res_ok = airlock.submit_proof_carrying_deliverable(
        "pc2-contract-radar-barker13", valid_lean, barker_seq
    )
    if shutil.which("lean") is not None:
        assert res_ok["disposition"] == "AIRLOCK_ACCEPTED_ESCROW_RELEASED"
        assert res_ok["verification_status"] == REAL_EXECUTED
        assert contract.status == "SETTLED_RELEASED_TO_CONTRACTOR"
    else:
        assert res_ok["disposition"] == "AIRLOCK_HELD_TEXT_LINT_ONLY"
        assert res_ok["code"] == LEAN_NOT_EXECUTED
        assert res_ok["verification_status"] == TEXT_LINT_ONLY
        assert contract.status == "ESCROW_LOCKED"


def test_sec_15c3_5_and_golomb8_lean4_export(tmp_path: Path) -> None:
    """Verify standalone `.lean` proof export and SEC Rule 15c3-5 pre-trade check."""
    digests = Lean4WitnessCertificateExporter.export_all_to_proofs_dir(tmp_path)
    assert "Math06Barker13.lean" in digests
    assert "Math02Golomb8.lean" in digests
    assert "FinSec15c35PreTrade.lean" in digests
    assert "comparator_config.json" in digests

    sec_spec, sec_lean = (
        Lean4WitnessCertificateExporter.build_sec_rule_15c3_5_pretrade_challenge_and_solution(
            order_notional_minor=400_00,
            current_exposure_minor=1500_00,
            credit_cap_minor=2500_00,
            max_single_order_minor=500_00,
        )
    )
    verdict = LeanComparatorSandboxAuditor.verify_submission_against_trusted_spec(
        sec_spec, sec_lean
    )
    assert verdict.text_lint_passed is True
    assert verdict.certificate_caid.startswith("sha256:")
    if shutil.which("lean") is not None:
        assert verdict.passed is True
        assert verdict.status == REAL_EXECUTED
    else:
        assert verdict.passed is False
        assert verdict.status == TEXT_LINT_ONLY
        assert verdict.rejection_code == LEAN_NOT_EXECUTED


def test_pc2_lean4_airlock_mutation_adequacy_oracles(tmp_path: Path) -> None:
    """Comprehensive boundary, kernel-execution, and CLI oracles for Section 24."""
    import subprocess
    import sys
    import src.proof_carrying_lean4_airlock as pc2_mod
    from src.proof_carrying_lean4_airlock import (
        HALT_LEAN_SORRY_WARNING,
        HALT_LEAN_UNPERMITTED_AXIOM,
        OK_LEAN_KERNEL_CHECKED,
    )

    barker_seq = [1, 1, 1, 1, 1, -1, -1, 1, 1, -1, 1, -1, 1]
    spec, valid_lean = (
        Lean4WitnessCertificateExporter.build_labs_barker13_challenge_and_solution(
            barker_seq
        )
    )
    assert spec.definitions_sha256.startswith("sha256:")
    assert spec.theorem_header_sha256.startswith("sha256:")
    cfg = spec.to_comparator_config()
    assert isinstance(cfg, dict)
    assert cfg["definitions_sha256"] == spec.definitions_sha256
    assert cfg["theorem_header_sha256"] == spec.theorem_header_sha256

    # Exported files content & JSON formatting invariants
    Lean4WitnessCertificateExporter.export_all_to_proofs_dir(tmp_path)
    barker_file = (tmp_path / "proofs" / "Math06Barker13.lean").read_text(encoding="utf-8")
    golomb_file = (tmp_path / "proofs" / "Math02Golomb8.lean").read_text(encoding="utf-8")
    cfg_file = (tmp_path / "proofs" / "comparator_config.json").read_text(encoding="utf-8")
    assert "def barker13 : List Int := [1, 1, 1, 1, 1, -1, -1, 1, 1, -1, 1, -1, 1]" in barker_file
    assert "def golomb8 : List Nat := [0, 1, 4, 9, 15, 22, 32, 34]" in golomb_file
    assert '  "challenges": [\n    {\n      "definitions_sha256":' in cfg_file

    # Direct auditor rejection check (kills _reject passed=False mutation)
    v_rej = LeanComparatorSandboxAuditor.verify_submission_against_trusted_spec(
        spec, valid_lean.replace(":= by decide", ":= by sorry")
    )
    assert v_rej.passed is False
    assert v_rej.text_lint_passed is False

    # verify_barker13_energy exact boundary checks
    import builtins

    class _SpinInt(int):
        def __floordiv__(self, other: int) -> int:
            raise TypeError("Bipolar spin correlation must use multiplication, not floor-division")

    orig_int = builtins.int
    builtins.int = _SpinInt  # type: ignore[assignment]
    try:
        assert verify_barker13_energy(barker_seq) is True
    finally:
        builtins.int = orig_int  # type: ignore[assignment]
    assert verify_barker13_energy("not_a_list") is False
    assert verify_barker13_energy([1, 1, 1]) is False
    assert verify_barker13_energy([2] + [1] * 12) is False
    assert verify_barker13_energy([0] + [1] * 12) is False
    assert verify_barker13_energy([1] * 13) is False

    # Direct run_lean_kernel checks & full PC2 escrow settlement + witness rejection
    class _ProcResult:
        def __init__(self, returncode: int, stdout: str, stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    orig_run = subprocess.run
    orig_which = shutil.which
    orig_argv = sys.argv
    orig_export = Lean4WitnessCertificateExporter.export_all_to_proofs_dir
    orig_sync = pc2_mod.SovereignIndependentStateCapsuleEngine.build_and_sync_capsule

    mode = {"out": "depends on axioms: [propext, Quot.sound]", "rc": 0}

    def _stub_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        if kwargs.get("text") is not True:
            raise ValueError("Expected text=True")
        return _ProcResult(int(mode["rc"]), str(mode["out"]))

    try:
        subprocess.run = _stub_run  # type: ignore[assignment]
        mode["out"] = "warning: declaration uses 'sorry'"
        assert LeanComparatorSandboxAuditor.run_lean_kernel(
            spec, valid_lean, "/usr/bin/lean"
        ) == (False, HALT_LEAN_SORRY_WARNING)

        mode["out"] = "depends on axioms: [propext, CustomBadAx]"
        assert LeanComparatorSandboxAuditor.run_lean_kernel(
            spec, valid_lean, "/usr/bin/lean"
        ) == (False, f"{HALT_LEAN_UNPERMITTED_AXIOM}:CustomBadAx")

        mode["out"] = "depends on axioms: [propext, Quot.sound]"
        assert LeanComparatorSandboxAuditor.run_lean_kernel(
            spec, valid_lean, "/usr/bin/lean"
        ) == (True, OK_LEAN_KERNEL_CHECKED)

        # Airlock witness evaluation failure when Lean kernel passes
        shutil.which = lambda _: "/usr/bin/lean"  # type: ignore[assignment]
        airlock = Pc2ProofCarryingEscrowAirlock()
        contract = ProofCarryingContractEscrow(
            contract_id="c1",
            client_id="cli",
            contractor_agent_id="ag",
            escrow_amount_minor=100,
            required_challenge_spec=spec,
            deterministic_evaluator_fn=verify_barker13_energy,
        )
        airlock.register_contract_and_lock_escrow(contract)
        bad_wit_res = airlock.submit_proof_carrying_deliverable(
            "c1", valid_lean, [1] * 13
        )
        assert bad_wit_res is not None
        assert bad_wit_res["disposition"] == "AIRLOCK_REJECTED_WITNESS_EVALUATION"

        # CLI main() with Lean present and with Lean absent
        class _DummyCapsule:
            capsule_sha256 = "sha256:00"

        sys.argv = ["proof_carrying_lean4_airlock.py", "--self-test"]
        Lean4WitnessCertificateExporter.export_all_to_proofs_dir = classmethod(lambda cls, root: {})  # type: ignore[assignment]
        pc2_mod.SovereignIndependentStateCapsuleEngine.build_and_sync_capsule = lambda self, persist=True: _DummyCapsule()  # type: ignore[assignment]

        assert pc2_mod.main() == 0
        shutil.which = lambda _: None  # type: ignore[assignment]
        assert pc2_mod.main() == 0
    finally:
        subprocess.run = orig_run  # type: ignore[assignment]
        shutil.which = orig_which  # type: ignore[assignment]
        sys.argv = orig_argv
        Lean4WitnessCertificateExporter.export_all_to_proofs_dir = orig_export  # type: ignore[assignment]
        pc2_mod.SovereignIndependentStateCapsuleEngine.build_and_sync_capsule = orig_sync  # type: ignore[assignment]


def test_zero_banned_promotional_words_in_section24_files() -> None:
    """Ensure strict adherence to AGENTS.md epistemic boundaries."""
    banned = [
        "guaran" + "teed",
        "proven universal" + "ly",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
    ]
    root = Path(__file__).resolve().parent.parent
    for rel in (
        "src/proof_carrying_lean4_airlock.py",
        "tests/test_proof_carrying_lean4_airlock.py",
    ):
        content = (root / rel).read_text(encoding="utf-8").lower()
        for word in banned:
            assert word not in content, f"Banned term found in {rel}: {word}"
