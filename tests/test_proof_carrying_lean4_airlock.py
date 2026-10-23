"""Verification suite for Proof-Carrying Contract (PC2) Escrow Airlock and
Lean 4 Comparator Sandbox Auditor (Section 24).
"""

from __future__ import annotations

from pathlib import Path

from src.proof_carrying_lean4_airlock import (
    Lean4WitnessCertificateExporter,
    LeanComparatorSandboxAuditor,
    Pc2ProofCarryingEscrowAirlock,
    ProofCarryingContractEscrow,
    verify_barker13_energy,
)


def test_pc2_airlock_and_lean_comparator_adversarial_falsification(tmp_path: Path) -> None:
    """Verify that PC2 Airlock rejects sorryAx, custom axiom, definition tampering,
    and statement tampering, and releases escrow only on Comparator-clean proof + T4+ check.
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

    # 4. Falsification D: Invalid witness data rejected by semantic T4+ evaluator
    bad_witness = [1] * 13
    res_bad_w = airlock.submit_proof_carrying_deliverable(
        "pc2-contract-radar-barker13", valid_lean, bad_witness
    )
    assert res_bad_w["disposition"] == "AIRLOCK_REJECTED_WITNESS_EVALUATION"
    assert res_bad_w["code"] == "HALT_PC2_SEMANTIC_INVARIANT_FALSE"
    assert contract.status == "ESCROW_LOCKED"

    # 5. Nominal valid proof-carrying submission -> Escrow Released!
    res_ok = airlock.submit_proof_carrying_deliverable(
        "pc2-contract-radar-barker13", valid_lean, barker_seq
    )
    assert res_ok["disposition"] == "AIRLOCK_ACCEPTED_ESCROW_RELEASED"
    assert contract.status == "SETTLED_RELEASED_TO_CONTRACTOR"
    receipt = res_ok["settlement_receipt"]
    assert receipt["escrow_released_minor"] == 2500_00


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
    assert verdict.passed is True
    assert verdict.certificate_caid.startswith("sha256:")


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
