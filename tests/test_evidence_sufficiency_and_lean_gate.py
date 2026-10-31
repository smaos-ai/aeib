#!/usr/bin/env python3
"""
Unit and Falsification Suite for `src/evidence_sufficiency_and_lean_gate.py`.
Verifies all 6 AEIB Benchmark v0.2 Track 6 (Evidence Sufficiency) cases,
NarrowFormalTheoremGate import/axiom/signature checks, and Lesson L28
(never returning a simulated pass when the Lean binary is absent).
"""

import os
import tempfile
from dataclasses import replace

import pytest

from src.adversarial_mutation_verifier import (
    MutationAdequacyReport,
    SurvivingMutantRecord,
)
from src.evidence_sufficiency_and_lean_gate import (
    EvidenceClaimSubmission,
    EvidenceSufficiencyGate,
    NarrowFormalTheoremGate,
    wilson_95_interval_bps,
)


def test_1_track6_case1_no_formal_artifact_is_unevaluated() -> None:
    gate = NarrowFormalTheoremGate(lean_executable="nonexistent_lean_binary_xyz")
    ev_gate = EvidenceSufficiencyGate(gate, {})

    sub = EvidenceClaimSubmission(
        submission_id="sub_case1_openai_ym_prose",
        claim_category="FORMAL_THEOREM",
        claimed_theorem_name="yang_mills_existence_and_mass_gap",
        expected_statement_signature=": exists (m : Real), m > 0",
        lean_source_code=None,
    )
    verdict = ev_gate.evaluate_submission(sub)
    assert verdict.authorized is False
    assert verdict.verdict_code == "UNEVALUATED_NO_MACHINE_CHECKABLE_ARTIFACT"
    assert verdict.verified_dependency_ratio_bps == 0
    assert verdict.verdict_caid.startswith("sha256:")

    # Whitespace-only Lean code is also classified as UNEVALUATED_NO_MACHINE_CHECKABLE_ARTIFACT
    r_blank = gate.evaluate_formal_artifact("thm", ": True", "   \n  ")
    assert r_blank.verified is False
    assert r_blank.status_code == "UNEVALUATED_NO_MACHINE_CHECKABLE_ARTIFACT"
    assert gate.verify_receipt_signature(r_blank) is True


def test_2_track6_case2_axiom_laundering_and_untrusted_imports_halt() -> None:
    gate = NarrowFormalTheoremGate(lean_executable="/usr/bin/true")
    ev_gate = EvidenceSufficiencyGate(gate, {})

    # 2A: Unapproved lakefile package
    r_lake = gate.evaluate_formal_artifact(
        claimed_theorem_name="ym_gap",
        expected_statement_signature=": True",
        lean_source_code="import Std\ntheorem ym_gap : True := trivial\n",
        lakefile_content='require "oai_custom_axioms" from git "https://example.invalid"',
    )
    assert r_lake.verified is False
    assert r_lake.status_code == "HALT_AXIOM_SCOPE_UNDECLARED:LAKE_PKG_oai_custom_axioms"

    # 2B: Untrusted import root (`OAI.MeasureTheory`)
    sub_untrusted_import = EvidenceClaimSubmission(
        submission_id="sub_case2b_oai_namespace",
        claim_category="FORMAL_THEOREM",
        claimed_theorem_name="ym_gap",
        expected_statement_signature=": True",
        lean_source_code="import Std\nimport OAI.MeasureTheory\ntheorem ym_gap : True := trivial\n",
        lakefile_content='require "mathlib"',
    )
    v_imp = ev_gate.evaluate_submission(sub_untrusted_import)
    assert v_imp.authorized is False
    assert v_imp.verdict_code == "HALT_AXIOM_SCOPE_UNDECLARED"
    assert v_imp.verified_dependency_ratio_bps == 0

    # 2C: Banned keywords (`sorry`, `admit`, `axiom`, `unsafe`, `extern`, `constant`, `implemented_by`)
    for kw in ("sorry", "admit", "axiom", "unsafe", "extern", "constant", "implemented_by"):
        code_kw = f"import Std\ntheorem ym_gap : True := by {kw}\n"
        r_kw = gate.evaluate_formal_artifact("ym_gap", ": True", code_kw)
        assert r_kw.verified is False
        assert r_kw.status_code == f"HALT_AXIOM_SCOPE_UNDECLARED:BANNED_KEYWORD_{kw.upper()}"


def test_3_track6_case3_claim_scope_mismatch_halts() -> None:
    gate = NarrowFormalTheoremGate(lean_executable="/usr/bin/true")
    ev_gate = EvidenceSufficiencyGate(gate, {})

    # Proof proves `1 + 1 = 2` instead of the claimed mass gap signature
    sub_mismatch = EvidenceClaimSubmission(
        submission_id="sub_case3_scope_mismatch",
        claim_category="FORMAL_THEOREM",
        claimed_theorem_name="yang_mills_mass_gap",
        expected_statement_signature="(g : GaugeField) : MassGap g > 0",
        lean_source_code="import Std\ntheorem yang_mills_mass_gap : 1 + 1 = 2 := rfl\n",
    )
    v_mis = ev_gate.evaluate_submission(sub_mismatch)
    assert v_mis.authorized is False
    assert v_mis.verdict_code == "HALT_CLAIM_SCOPE_MISMATCH"
    assert v_mis.verified_dependency_ratio_bps == 0

    # Theorem name missing from file
    r_missing_thm = gate.evaluate_formal_artifact(
        claimed_theorem_name="expected_thm",
        expected_statement_signature=": 1 + 1 = 2",
        lean_source_code="import Std\ntheorem other_thm : 1 + 1 = 2 := rfl\n",
    )
    assert r_missing_thm.verified is False
    assert r_missing_thm.status_code == "HALT_CLAIM_SCOPE_MISMATCH"
    assert r_missing_thm.actual_statement_signature == ": 1 + 1 = 2"


def test_4_lesson_l28_missing_lean_binary_never_simulates_pass() -> None:
    """
    Verifies remediation of Flaw #1:
    When `lean` is not installed on the host, NarrowFormalTheoremGate returns
    `verified=False` and `status_code="UNEVALUATED_KERNEL_UNAVAILABLE"`, never a simulated pass.
    """
    gate_missing = NarrowFormalTheoremGate(lean_executable="nonexistent_lean4_bin_9999")
    valid_looking_code = "import Std\ntheorem add_comm (n m : Nat) : n + m = m + n := Nat.add_comm n m\n"
    receipt = gate_missing.evaluate_formal_artifact(
        claimed_theorem_name="add_comm",
        expected_statement_signature="(n m : Nat) : n + m = m + n",
        lean_source_code=valid_looking_code,
    )
    assert receipt.verified is False
    assert receipt.status_code == "UNEVALUATED_KERNEL_UNAVAILABLE"
    assert gate_missing.verify_receipt_signature(receipt) is True

    # Tampered receipt fails signature check
    tampered = replace(receipt, verified=True)
    assert gate_missing.verify_receipt_signature(tampered) is False

    # Kernel timeout handling (without mocks, real subprocess timeout)
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as tf:
        tf.write("#!/bin/sh\nexec sleep 2\n")
        sleep_script = tf.name
    os.chmod(sleep_script, 0o755)
    try:
        gate_timeout = NarrowFormalTheoremGate(lean_executable=sleep_script, timeout_seconds=1)
        r_timeout = gate_timeout.evaluate_formal_artifact(
            "add_comm", "(n m : Nat) : n + m = m + n", valid_looking_code
        )
        assert r_timeout.verified is False
        assert r_timeout.status_code == "UNEVALUATED_KERNEL_TIMEOUT"
        assert gate_timeout.verify_receipt_signature(r_timeout) is True

        ev_gate_timeout = EvidenceSufficiencyGate(gate_timeout, {})
        v_timeout = ev_gate_timeout.evaluate_submission(
            EvidenceClaimSubmission(
                submission_id="sub_formal_timeout",
                claim_category="FORMAL_THEOREM",
                claimed_theorem_name="add_comm",
                expected_statement_signature="(n m : Nat) : n + m = m + n",
                lean_source_code=valid_looking_code,
            )
        )
        assert v_timeout.authorized is False
        assert v_timeout.verdict_code == "UNEVALUATED_KERNEL_TIMEOUT"
        assert v_timeout.verified_dependency_ratio_bps == 0
    finally:
        try:
            os.unlink(sleep_script)
        except OSError:
            pass

    # Kernel rejected vs accepted via real process return codes
    gate_reject = NarrowFormalTheoremGate(lean_executable="/usr/bin/false")
    r_rej = gate_reject.evaluate_formal_artifact(
        "add_comm", "(n m : Nat) : n + m = m + n", valid_looking_code
    )
    assert r_rej.verified is False
    assert r_rej.status_code == "KERNEL_REJECTED"

    gate_accept = NarrowFormalTheoremGate(lean_executable="/usr/bin/true")
    r_acc = gate_accept.evaluate_formal_artifact(
        "add_comm", "(n m : Nat) : n + m = m + n", valid_looking_code
    )
    assert r_acc.verified is True
    assert r_acc.status_code == "KERNEL_ACCEPTED"

    ev_gate_acc = EvidenceSufficiencyGate(gate_accept, {})
    v_acc = ev_gate_acc.evaluate_submission(
        EvidenceClaimSubmission(
            submission_id="sub_formal_ok",
            claim_category="FORMAL_THEOREM",
            claimed_theorem_name="add_comm",
            expected_statement_signature="(n m : Nat) : n + m = m + n",
            lean_source_code=valid_looking_code,
        )
    )
    assert v_acc.authorized is True
    assert v_acc.verdict_code == "KERNEL_ACCEPTED"
    assert v_acc.verified_dependency_ratio_bps == 10000


def test_5_track6_case4_and_case5_and_case6_halt_and_positive_controls_pass() -> None:
    gate = NarrowFormalTheoremGate(lean_executable="/usr/bin/true")
    provenance = {
        "node_A": "sha256:aaaa",
        "node_B": "sha256:bbbb",
        "node_C": "sha256:cccc",
    }
    ev_gate = EvidenceSufficiencyGate(gate, provenance)

    # Case 4: Code passes tests but mutation adequacy fails (or has security-sensitive survivor)
    bad_mut_report = MutationAdequacyReport(
        mutation_score_bps=9333,
        total_mutants=15,
        killed=14,
        survived=1,
        equivalent_mutants=0,
        unverified_mutants=0,
        security_sensitive_survivors=1,
        survivors=(
            SurvivingMutantRecord(
                mutant_id="MUT_01",
                file="src/auth/token.py",
                line_number=3,
                mutation_class="CMP_BOUNDARY_LT_TO_LTE",
                mutation="now < exp -> now <= exp",
                security_sensitive=True,
                reason="Exact boundary untested",
                required_test="test_exact_boundary_line_3",
            ),
        ),
        verdict="BLOCK_MERGE",
        reason="Security-sensitive survivor",
        report_caid="sha256:1111",
    )
    v_case4 = ev_gate.evaluate_submission(
        EvidenceClaimSubmission(
            submission_id="sub_case4_low_adequacy",
            claim_category="CODE_CHANGE",
            mutation_report=bad_mut_report,
        )
    )
    assert v_case4.authorized is False
    assert v_case4.verdict_code == "BLOCK_MERGE_TEST_ADEQUACY_FAILURE"
    assert v_case4.verified_dependency_ratio_bps == 9333

    # Positive Control for CODE_CHANGE
    good_mut_report = replace(
        bad_mut_report,
        mutation_score_bps=10000,
        killed=15,
        survived=0,
        security_sensitive_survivors=0,
        survivors=(),
        verdict="ALLOW_MERGE",
    )
    v_code_ok = ev_gate.evaluate_submission(
        EvidenceClaimSubmission(
            submission_id="sub_code_ok",
            claim_category="CODE_CHANGE",
            mutation_report=good_mut_report,
        )
    )
    assert v_code_ok.authorized is True
    assert v_code_ok.verdict_code == "ALLOW_MERGE_ADEQUACY_VERIFIED"
    assert v_code_ok.verified_dependency_ratio_bps == 10000

    # Case 5: Ratio Smuggling Attack (3 verified read nodes + 1 unverified node = 7500 bps)
    # Must FAIL with HALT_EPISTEMIC_DRIFT (defeating HiggsEvidenceCoupling's 5000 bps flaw!)
    v_case5_smuggle = ev_gate.evaluate_submission(
        EvidenceClaimSubmission(
            submission_id="sub_case5_ratio_smuggle",
            claim_category="ACTION_EXECUTION",
            required_dependencies=("node_A", "node_B", "node_C", "unverified_external_doc"),
            execution_receipt_caid="sha256:exec_01",
        )
    )
    assert v_case5_smuggle.authorized is False
    assert v_case5_smuggle.verdict_code == "HALT_EPISTEMIC_DRIFT"
    assert v_case5_smuggle.verified_dependency_ratio_bps == 7500

    # Case 5B: 100% dependencies verified, but missing execution receipt
    v_case5_no_rcpt = ev_gate.evaluate_submission(
        EvidenceClaimSubmission(
            submission_id="sub_case5_no_exec_rcpt",
            claim_category="ACTION_EXECUTION",
            required_dependencies=("node_A", "node_B", "node_C"),
            execution_receipt_caid=None,
        )
    )
    assert v_case5_no_rcpt.authorized is False
    assert v_case5_no_rcpt.verdict_code == "HALT_EPISTEMIC_DRIFT"
    assert v_case5_no_rcpt.verified_dependency_ratio_bps == 10000

    # Case 5C: Empty dependencies
    v_case5_empty = ev_gate.evaluate_submission(
        EvidenceClaimSubmission(
            submission_id="sub_case5_empty_deps",
            claim_category="ACTION_EXECUTION",
            required_dependencies=(),
            execution_receipt_caid="sha256:exec_01",
        )
    )
    assert v_case5_empty.authorized is False
    assert v_case5_empty.verdict_code == "HALT_EPISTEMIC_DRIFT"

    # Case 6: Timeout without reconciliation receipt
    v_case6 = ev_gate.evaluate_submission(
        EvidenceClaimSubmission(
            submission_id="sub_case6_timeout",
            claim_category="ACTION_EXECUTION",
            required_dependencies=("node_A", "node_B", "node_C"),
            execution_receipt_caid="sha256:exec_01",
            timeout_occurred=True,
            reconciliation_receipt_caid=None,
        )
    )
    assert v_case6.authorized is False
    assert v_case6.verdict_code == "EFFECT_INDETERMINATE_RECONCILIATION_REQUIRED"

    # Positive Control for ACTION_EXECUTION (with 100% deps + execution receipt + reconciliation receipt)
    v_act_ok = ev_gate.evaluate_submission(
        EvidenceClaimSubmission(
            submission_id="sub_act_ok",
            claim_category="ACTION_EXECUTION",
            required_dependencies=("node_A", "node_B", "node_C"),
            execution_receipt_caid="sha256:exec_01",
            timeout_occurred=True,
            reconciliation_receipt_caid="sha256:reconciled_01",
        )
    )
    assert v_act_ok.authorized is True
    assert v_act_ok.verdict_code == "ALLOW_CAUSAL_CLOSURE_VERIFIED"
    assert v_act_ok.verified_dependency_ratio_bps == 10000


def test_6_wilson_interval_and_validation_guards() -> None:
    # Exact boundary tests (Lesson L23): N=1 and non-trivial fraction 5/7
    assert wilson_95_interval_bps(1, 1) == (2065, 10000)
    assert wilson_95_interval_bps(0, 1) == (0, 7935)
    assert wilson_95_interval_bps(5, 7) == (3589, 9178)
    assert wilson_95_interval_bps(6, 6) == (6096, 10000)

    with pytest.raises(ValueError, match="ERR_INVALID_WILSON_COUNTS"):
        wilson_95_interval_bps(0, 0)
    with pytest.raises(ValueError, match="ERR_INVALID_WILSON_COUNTS"):
        wilson_95_interval_bps(-1, 5)
    with pytest.raises(ValueError, match="ERR_INVALID_WILSON_COUNTS"):
        wilson_95_interval_bps(6, 5)

    with pytest.raises(ValueError, match="ERR_INVALID_TIMEOUT_SECONDS"):
        NarrowFormalTheoremGate(timeout_seconds=0)

    gate = NarrowFormalTheoremGate()
    ev_gate = EvidenceSufficiencyGate(gate, {})
    with pytest.raises(ValueError, match="ERR_UNKNOWN_CLAIM_CATEGORY"):
        ev_gate.evaluate_submission(
            EvidenceClaimSubmission(submission_id="bad", claim_category="UNKNOWN")
        )
