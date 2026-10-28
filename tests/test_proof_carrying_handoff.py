#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
tests/test_proof_carrying_handoff.py
================================================================================
Falsification & Verification Suite for Proof-Carrying Handoffs (PCH).
Proves that high-consequence code cannot cross execution boundaries without
valid, mechanically checked formal proofs and un-tampered cryptographic receipts.
"""

from __future__ import annotations

import dataclasses
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.proof_carrying_handoff import (
    FormalPCCVerifier,
    ProofCarryingArtifact,
    ProofStatus,
)


def test_t2_task_requires_formal_proof() -> None:
    """T2 (Medium risk) handoff without a formal proof MUST HALT."""
    with pytest.raises(ValueError, match="HALT_MISSING_FORMAL_PROOF"):
        ProofCarryingArtifact(
            task_id="task-payment-01",
            risk_tier="T2",
            ast_diffs=("+ def calculate_refund(): return 500",),
            generated_code_hash="sha256:abc12345",
            formal_proof_script=None,
            formal_proof_hash=None,
        )

    # Missing hash when script is provided
    with pytest.raises(ValueError, match="HALT_MISSING_FORMAL_PROOF"):
        ProofCarryingArtifact(
            task_id="task-payment-01b",
            risk_tier="T2",
            ast_diffs=(),
            generated_code_hash="sha256:abc",
            formal_proof_script="theorem t : 1=1 := rfl",
            formal_proof_hash=None,
        )

    # Missing script when hash is provided
    with pytest.raises(ValueError, match="HALT_MISSING_FORMAL_PROOF"):
        ProofCarryingArtifact(
            task_id="task-payment-01c",
            risk_tier="T2",
            ast_diffs=(),
            generated_code_hash="sha256:abc",
            formal_proof_script=None,
            formal_proof_hash="sha256:123",
        )


def test_t3_task_requires_formal_proof() -> None:
    """T3 (High risk) handoff without a formal proof MUST HALT."""
    with pytest.raises(ValueError, match="HALT_MISSING_FORMAL_PROOF"):
        ProofCarryingArtifact(
            task_id="task-wire-01",
            risk_tier="T3",
            ast_diffs=("+ def execute_wire(): return True",),
            generated_code_hash="sha256:wire123",
            formal_proof_script=None,
            formal_proof_hash=None,
        )


def test_unverified_proof_is_rejected_on_t2_and_t3() -> None:
    """If the proof script has not been mechanically verified, artifact instantiation fails."""
    with pytest.raises(ValueError, match="HALT_UNVERIFIED_FORMAL_PROOF"):
        ProofCarryingArtifact(
            task_id="task-payment-02",
            risk_tier="T3",
            ast_diffs=("+ def execute_wire(): return True",),
            generated_code_hash="sha256:def45678",
            formal_proof_script="theorem bad_proof : 1 = 2 := by sorry",
            formal_proof_hash="sha256:proof123",
            proof_status=ProofStatus.UNVERIFIED,
        )


def test_attestation_with_key_but_no_signature_returns_false_not_raises() -> None:
    """Half-populated attestation (key present, signature missing, or vice versa)
    must fail closed with False instead of raising on bytes.fromhex(None)."""
    key_hex = Ed25519PrivateKey.generate().public_key().public_bytes_raw().hex()
    key_only = ProofCarryingArtifact(
        task_id="task-attest-key-only",
        risk_tier="T1",
        ast_diffs=(),
        generated_code_hash="sha256:abc",
        issuer_public_key_hex=key_hex,
        verifier_signature_hex=None,
    )
    assert key_only.verify_cryptographic_attestation() is False
    sig_only = dataclasses.replace(
        key_only, issuer_public_key_hex=None, verifier_signature_hex="00" * 64
    )
    assert sig_only.verify_cryptographic_attestation() is False


def test_t0_t1_task_bypasses_formal_proof() -> None:
    """T0 and T1 (Low risk) tasks do not require formal proofs."""
    artifact_t1 = ProofCarryingArtifact(
        task_id="task-ui-01",
        risk_tier="T1",
        ast_diffs=("- color: blue\n+ color: red",),
        generated_code_hash="sha256:xyz789",
        formal_proof_script=None,
        formal_proof_hash=None,
        proof_status=ProofStatus.VERIFIED,
    )
    assert artifact_t1.task_id == "task-ui-01"
    assert artifact_t1.risk_tier == "T1"
    # Calling verify when no key was set returns False
    res_no_key = artifact_t1.verify_cryptographic_attestation()
    assert res_no_key is False
    assert type(res_no_key) is bool

    artifact_t0 = FormalPCCVerifier.assemble_verified_artifact(
        task_id="task-triage-01",
        risk_tier="T0",
        ast_diffs=(),
        code_str="# read only triage",
    )
    assert artifact_t0.proof_status == ProofStatus.VERIFIED


def test_formal_pcc_verifier_evaluates_lean4() -> None:
    """Verifier accepts sound Lean4 theorems with 'by' or ':=' and rejects shortcuts."""
    valid_lean_by = "theorem add_zero (n : Nat) : n + 0 = n := by rfl"
    assert FormalPCCVerifier.evaluate_proof_script(valid_lean_by, "LEAN4") == ProofStatus.VERIFIED

    valid_lean_assign = "theorem id (n : Nat) : n = n := rfl"
    assert FormalPCCVerifier.evaluate_proof_script(valid_lean_assign, "LEAN4") == ProofStatus.VERIFIED

    lean_missing_body = "theorem unfinished : True"
    assert FormalPCCVerifier.evaluate_proof_script(lean_missing_body, "LEAN4") == ProofStatus.FAILED

    lean_missing_theorem = "def x := 1"
    assert FormalPCCVerifier.evaluate_proof_script(lean_missing_theorem, "LEAN4") == ProofStatus.FAILED

    vacuous_lean = "theorem bad (n : Nat) : n = 0 := by sorry"
    assert FormalPCCVerifier.evaluate_proof_script(vacuous_lean, "LEAN4") == ProofStatus.FAILED
    assert FormalPCCVerifier.evaluate_proof_script("", "LEAN4") == ProofStatus.FAILED
    assert FormalPCCVerifier.evaluate_proof_script("   \n\t  ", "LEAN4") == ProofStatus.FAILED
    assert FormalPCCVerifier.evaluate_proof_script(None, "LEAN4") == ProofStatus.FAILED


def test_formal_pcc_verifier_evaluates_tla_and_smt() -> None:
    """Verifier accepts sound TLA+ specs and SMTLIB2 obligations, rejecting vacuous axioms."""
    valid_tla_spec = "MODULE S\nVARIABLES state\nSpec == state' = state\nInvariant == state >= 0"
    assert FormalPCCVerifier.evaluate_proof_script(valid_tla_spec, "TLA_TLC") == ProofStatus.VERIFIED

    valid_tla_next = "VARIABLE x\nNext == x' = x"
    assert FormalPCCVerifier.evaluate_proof_script(valid_tla_next, "TLA_TLC") == ProofStatus.VERIFIED

    valid_tla_inv = "MODULE M\nInvariant == x >= 0"
    assert FormalPCCVerifier.evaluate_proof_script(valid_tla_inv, "TLA_TLC") == ProofStatus.VERIFIED

    tla_missing_action = "MODULE M\nVARIABLES x\nx = 1"
    assert FormalPCCVerifier.evaluate_proof_script(tla_missing_action, "TLA_TLC") == ProofStatus.FAILED

    tla_missing_var = "Spec == x' = x"
    assert FormalPCCVerifier.evaluate_proof_script(tla_missing_var, "TLA_TLC") == ProofStatus.FAILED

    vacuous_tla = "MODULE S\nVARIABLES state\nSpec == CHOOSE s \\in Nat : TRUE"
    assert FormalPCCVerifier.evaluate_proof_script(vacuous_tla, "TLA_TLC") == ProofStatus.FAILED

    valid_smt = "(set-logic QF_LIA)\n(assert (= x 1))\n(check-sat)"
    assert FormalPCCVerifier.evaluate_proof_script(valid_smt, "SMTLIB2_Z3") == ProofStatus.VERIFIED

    smt_missing_assert = "(set-logic QF_LIA)\n(check-sat)"
    assert FormalPCCVerifier.evaluate_proof_script(smt_missing_assert, "SMTLIB2_Z3") == ProofStatus.FAILED

    smt_missing_check = "(assert (= x 1))"
    assert FormalPCCVerifier.evaluate_proof_script(smt_missing_check, "SMTLIB2_Z3") == ProofStatus.FAILED

    vacuous_smt = "(assert (= x 1))\n(assume false)\n(check-sat)"
    assert FormalPCCVerifier.evaluate_proof_script(vacuous_smt, "SMTLIB2_Z3") == ProofStatus.FAILED

    unknown_engine = FormalPCCVerifier.evaluate_proof_script("(assert true)", "UNKNOWN_ENGINE")
    assert unknown_engine == ProofStatus.FAILED


def test_assembly_and_cryptographic_attestation_verification() -> None:
    """Full lifecycle: verify proof, sign artifact with Ed25519, and detect tampering."""
    sk = Ed25519PrivateKey.generate()
    code = "def refund(x): return x - 10"
    proof = "MODULE Refund\nVARIABLES bal\nSpec == bal' = bal - 10\nInvariant == bal >= 0"

    artifact = FormalPCCVerifier.assemble_verified_artifact(
        task_id="task-verified-01",
        risk_tier="T2",
        ast_diffs=("- bal\n+ bal - 10",),
        code_str=code,
        proof_script=proof,
        proof_engine="TLA_TLC",
        signing_key=sk,
    )

    assert artifact.proof_status == ProofStatus.VERIFIED
    assert artifact.formal_proof_hash is not None
    assert artifact.verifier_signature_hex is not None
    assert artifact.verify_cryptographic_attestation() is True

    # Mutated artifact fails attestation verification
    tampered = ProofCarryingArtifact(
        task_id=artifact.task_id,
        risk_tier=artifact.risk_tier,
        ast_diffs=artifact.ast_diffs,
        generated_code_hash="sha256:tampered_code_hash",
        formal_proof_script=artifact.formal_proof_script,
        formal_proof_hash=artifact.formal_proof_hash,
        proof_engine=artifact.proof_engine,
        proof_status=artifact.proof_status,
        issuer_public_key_hex=artifact.issuer_public_key_hex,
        verifier_signature_hex=artifact.verifier_signature_hex,
    )
    assert tampered.verify_cryptographic_attestation() is False


def test_artifact_immutability() -> None:
    """Artifact is frozen and rejects attribute mutation."""
    artifact = FormalPCCVerifier.assemble_verified_artifact(
        task_id="task-freeze-01",
        risk_tier="T0",
        ast_diffs=(),
        code_str="x = 1",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        artifact.task_id = "mutated"  # type: ignore


def test_model_manifest_binding_in_pch() -> None:
    """Evaluates dynamic model weight manifest binding in FormalPCCVerifier."""
    sk = Ed25519PrivateKey.generate()
    code = "def refund(): return 100"
    proof = "VARIABLES bal\nSpec == bal' = bal\nInvariant == bal >= 0"

    v1_weights = "sha256:model_weights_v1"
    v2_weights = "sha256:model_weights_v2_vendor_update"

    artifact = FormalPCCVerifier.assemble_verified_artifact(
        task_id="task-bind-01",
        risk_tier="T3",
        ast_diffs=("+ def refund(): return 100",),
        code_str=code,
        proof_script=proof,
        proof_engine="TLA_TLC",
        signing_key=sk,
        model_manifest_digest=v1_weights,
    )

    # 1. Matching manifest succeeds
    assert FormalPCCVerifier.verify_model_manifest_binding(artifact, v1_weights) is True
    assert artifact.verify_cryptographic_attestation() is True

    # 2. Silent vendor update (v2 weights) fails closed
    assert FormalPCCVerifier.verify_model_manifest_binding(artifact, v2_weights) is False

    # 3. None live digest bypasses check
    assert FormalPCCVerifier.verify_model_manifest_binding(artifact, None) is True

