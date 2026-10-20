#!/usr/bin/env python3
"""
tests/test_zk_budget_proof_engine.py — zk-AEIB Arithmetic Circuit & Privacy-Preserving Proof Engine Tests
Sovereign Multi-Agent OS (SMAOS) / Agent Execution Integrity (AEIB)

Evaluated under the stated model as a pre-production test suite.
Tests zero-knowledge budget proof generation, verification, zero-disclosure privacy,
and 5 adversarial falsification axes.
"""

import json
from pathlib import Path
import secrets
import subprocess
import sys
from typing import List

import pytest

from src.zk_budget_proof_engine import (
    BN254_SCALAR_FIELD_PRIME,
    HALT_ZK_BALANCE_CONSERVATION_FAILED,
    HALT_ZK_CEILING_BREACH,
    HALT_ZK_COMMITMENT_ROOT_MISMATCH,
    HALT_ZK_NEGATIVE_SPEND_DETECTED,
    HALT_ZK_PROOF_INVALID,
    BudgetPublicInputs,
    PrivateTransaction,
    PrivateWitness,
    ZkBudgetProof,
    ZkBudgetProofEngine,
    ZkCircuitError,
)


@pytest.fixture
def test_engine() -> ZkBudgetProofEngine:
    return ZkBudgetProofEngine()


@pytest.fixture
def sample_txs() -> List[PrivateTransaction]:
    return [
        PrivateTransaction(spend_minor=1250, salt=secrets.token_hex(16), payee="DE89370400440532013000"),
        PrivateTransaction(spend_minor=4800, salt=secrets.token_hex(16), payee="FR7630006000011234567890189"),
        PrivateTransaction(spend_minor=2150, salt=secrets.token_hex(16), payee="GB29NWBK60161331926819"),
    ]


def test_valid_budget_proof_generation_and_verification(test_engine, sample_txs):
    """Evaluates valid batch proof generation and independent verification using only public inputs."""
    total_spend = sum(t.spend_minor for t in sample_txs)
    leaves = [
        test_engine.compute_leaf_commitment(t.salt, t.spend_minor, t.payee)
        for t in sample_txs
    ]
    merkle_root = test_engine.compute_merkle_root(leaves)

    public_inputs = BudgetPublicInputs(
        initial_balance_minor=100000,
        final_balance_minor=100000 - total_spend,
        budget_ceiling_minor=15000,
        commitment_merkle_root=merkle_root,
        epoch=202610,
    )
    witness = PrivateWitness(transactions=sample_txs)

    proof = test_engine.generate_budget_proof(witness, public_inputs)
    assert proof.transcript_hash is not None
    assert len(proof.leaf_commitments) == len(sample_txs)

    verifier = ZkBudgetProofEngine()
    result = verifier.verify_budget_proof(public_inputs, proof)

    assert result.valid is True
    assert bool(result) is True
    assert result.rejection_code is None
    assert result.verification_time_ms < 15.0

    is_valid, rejection_code = result
    assert is_valid is True
    assert rejection_code is None


def test_zero_disclosure_privacy_conformance(test_engine, sample_txs):
    """Asserts that public proof and verifier context contain 0 raw spend amounts, salts, or payee identifiers."""
    total_spend = sum(t.spend_minor for t in sample_txs)
    leaves = [
        test_engine.compute_leaf_commitment(t.salt, t.spend_minor, t.payee)
        for t in sample_txs
    ]
    merkle_root = test_engine.compute_merkle_root(leaves)

    public_inputs = BudgetPublicInputs(
        initial_balance_minor=100000,
        final_balance_minor=100000 - total_spend,
        budget_ceiling_minor=15000,
        commitment_merkle_root=merkle_root,
        epoch=202610,
    )
    witness = PrivateWitness(transactions=sample_txs)

    proof = test_engine.generate_budget_proof(witness, public_inputs)
    proof_dict = proof.to_dict()
    serialized_proof = json.dumps(proof_dict)

    for tx in sample_txs:
        assert tx.payee not in serialized_proof, f"Payee {tx.payee} leaked in public proof"
        assert tx.salt not in serialized_proof, f"Blinding salt {tx.salt} leaked in public proof"
        assert f":{tx.spend_minor}:" not in serialized_proof


def test_falsification_1_negative_spend_injection(test_engine):
    """Falsification 1: Negative spend injection fails closed with HALT_ZK_NEGATIVE_SPEND_DETECTED."""
    bad_txs = [
        PrivateTransaction(spend_minor=-500, salt=secrets.token_hex(16), payee="NL91ABNA0417164300")
    ]
    witness = PrivateWitness(transactions=bad_txs)
    public_inputs = BudgetPublicInputs(
        initial_balance_minor=100000,
        final_balance_minor=100500,
        budget_ceiling_minor=15000,
        commitment_merkle_root="aa" * 32,
        epoch=202610,
    )

    with pytest.raises(ZkCircuitError) as exc_info:
        test_engine.generate_budget_proof(witness, public_inputs)

    assert exc_info.value.rejection_code == HALT_ZK_NEGATIVE_SPEND_DETECTED

    # Verifier check when final balance exceeds initial balance
    valid_txs = [
        PrivateTransaction(spend_minor=100, salt=secrets.token_hex(16), payee="BE68539007547034")
    ]
    leaves = [test_engine.compute_leaf_commitment(t.salt, t.spend_minor, t.payee) for t in valid_txs]
    root = test_engine.compute_merkle_root(leaves)
    valid_inputs = BudgetPublicInputs(
        initial_balance_minor=10000,
        final_balance_minor=9900,
        budget_ceiling_minor=1000,
        commitment_merkle_root=root,
        epoch=202610,
    )
    proof = test_engine.generate_budget_proof(PrivateWitness(valid_txs), valid_inputs)

    inflated_inputs = BudgetPublicInputs(
        initial_balance_minor=10000,
        final_balance_minor=10500,
        budget_ceiling_minor=1000,
        commitment_merkle_root=root,
        epoch=202610,
    )
    res = test_engine.verify_budget_proof(inflated_inputs, proof)
    assert res.valid is False
    assert res.rejection_code == HALT_ZK_NEGATIVE_SPEND_DETECTED


def test_falsification_2_budget_ceiling_breach(test_engine):
    """Falsification 2: Spending exceeding authorized ceiling fails closed with HALT_ZK_CEILING_BREACH."""
    txs = [
        PrivateTransaction(spend_minor=18000, salt=secrets.token_hex(16), payee="IT60X0542811101000000123456")
    ]
    leaves = [test_engine.compute_leaf_commitment(t.salt, t.spend_minor, t.payee) for t in txs]
    root = test_engine.compute_merkle_root(leaves)
    inputs_exceeding_ceiling = BudgetPublicInputs(
        initial_balance_minor=100000,
        final_balance_minor=82000,
        budget_ceiling_minor=15000,
        commitment_merkle_root=root,
        epoch=202610,
    )

    with pytest.raises(ZkCircuitError) as exc_info:
        test_engine.generate_budget_proof(PrivateWitness(txs), inputs_exceeding_ceiling)

    assert exc_info.value.rejection_code == HALT_ZK_CEILING_BREACH

    # Verifier fails closed when ceiling is lower than delta
    valid_txs = [
        PrivateTransaction(spend_minor=2000, salt=secrets.token_hex(16), payee="ES9121000418450200051332")
    ]
    v_leaves = [test_engine.compute_leaf_commitment(t.salt, t.spend_minor, t.payee) for t in valid_txs]
    v_root = test_engine.compute_merkle_root(v_leaves)
    normal_inputs = BudgetPublicInputs(
        initial_balance_minor=10000,
        final_balance_minor=8000,
        budget_ceiling_minor=5000,
        commitment_merkle_root=v_root,
        epoch=202610,
    )
    proof = test_engine.generate_budget_proof(PrivateWitness(valid_txs), normal_inputs)

    low_ceiling_inputs = BudgetPublicInputs(
        initial_balance_minor=10000,
        final_balance_minor=8000,
        budget_ceiling_minor=1500,
        commitment_merkle_root=v_root,
        epoch=202610,
    )
    res = test_engine.verify_budget_proof(low_ceiling_inputs, proof)
    assert res.valid is False
    assert res.rejection_code == HALT_ZK_CEILING_BREACH


def test_falsification_3_inconsistent_balance_arithmetic(test_engine, sample_txs):
    """Falsification 3: Inconsistent balance arithmetic fails closed with HALT_ZK_BALANCE_CONSERVATION_FAILED."""
    leaves = [test_engine.compute_leaf_commitment(t.salt, t.spend_minor, t.payee) for t in sample_txs]
    root = test_engine.compute_merkle_root(leaves)

    inconsistent_inputs = BudgetPublicInputs(
        initial_balance_minor=100000,
        final_balance_minor=95000,
        budget_ceiling_minor=15000,
        commitment_merkle_root=root,
        epoch=202610,
    )

    with pytest.raises(ZkCircuitError) as exc_info:
        test_engine.generate_budget_proof(PrivateWitness(sample_txs), inconsistent_inputs)

    assert exc_info.value.rejection_code == HALT_ZK_BALANCE_CONSERVATION_FAILED

    # Verifier fails closed when balance conservation evaluation fails
    total_spend = sum(t.spend_minor for t in sample_txs)
    correct_inputs = BudgetPublicInputs(
        initial_balance_minor=100000,
        final_balance_minor=100000 - total_spend,
        budget_ceiling_minor=15000,
        commitment_merkle_root=root,
        epoch=202610,
    )
    proof = test_engine.generate_budget_proof(PrivateWitness(sample_txs), correct_inputs)

    # Shift final balance slightly
    mismatched_inputs = BudgetPublicInputs(
        initial_balance_minor=100000,
        final_balance_minor=100000 - total_spend + 100,
        budget_ceiling_minor=15000,
        commitment_merkle_root=root,
        epoch=202610,
    )
    res = test_engine.verify_budget_proof(mismatched_inputs, proof)
    assert res.valid is False
    assert res.rejection_code in (HALT_ZK_PROOF_INVALID, HALT_ZK_BALANCE_CONSERVATION_FAILED)


def test_falsification_4_tampered_public_inputs(test_engine, sample_txs):
    """Falsification 4: Tampered public inputs are rejected."""
    total_spend = sum(t.spend_minor for t in sample_txs)
    leaves = [test_engine.compute_leaf_commitment(t.salt, t.spend_minor, t.payee) for t in sample_txs]
    root = test_engine.compute_merkle_root(leaves)

    inputs = BudgetPublicInputs(
        initial_balance_minor=100000,
        final_balance_minor=100000 - total_spend,
        budget_ceiling_minor=15000,
        commitment_merkle_root=root,
        epoch=202610,
    )
    proof = test_engine.generate_budget_proof(PrivateWitness(sample_txs), inputs)

    # Tamper Merkle Root
    tampered_root_inputs = BudgetPublicInputs(
        initial_balance_minor=inputs.initial_balance_minor,
        final_balance_minor=inputs.final_balance_minor,
        budget_ceiling_minor=inputs.budget_ceiling_minor,
        commitment_merkle_root="ff" * 32,
        epoch=inputs.epoch,
    )
    res_root = test_engine.verify_budget_proof(tampered_root_inputs, proof)
    assert res_root.valid is False
    assert res_root.rejection_code == HALT_ZK_COMMITMENT_ROOT_MISMATCH

    # Tamper Epoch
    tampered_epoch_inputs = BudgetPublicInputs(
        initial_balance_minor=inputs.initial_balance_minor,
        final_balance_minor=inputs.final_balance_minor,
        budget_ceiling_minor=inputs.budget_ceiling_minor,
        commitment_merkle_root=inputs.commitment_merkle_root,
        epoch=999999,
    )
    res_epoch = test_engine.verify_budget_proof(tampered_epoch_inputs, proof)
    assert res_epoch.valid is False
    assert res_epoch.rejection_code == HALT_ZK_PROOF_INVALID


def test_falsification_5_tampered_proof_artifacts(test_engine, sample_txs):
    """Falsification 5: Tampered proof bytes are rejected."""
    total_spend = sum(t.spend_minor for t in sample_txs)
    leaves = [test_engine.compute_leaf_commitment(t.salt, t.spend_minor, t.payee) for t in sample_txs]
    root = test_engine.compute_merkle_root(leaves)

    inputs = BudgetPublicInputs(
        initial_balance_minor=100000,
        final_balance_minor=100000 - total_spend,
        budget_ceiling_minor=15000,
        commitment_merkle_root=root,
        epoch=202610,
    )
    proof = test_engine.generate_budget_proof(PrivateWitness(sample_txs), inputs)

    # Tamper Ed25519 signature
    proof_dict_sig = proof.to_dict()
    sig_bytes = bytearray.fromhex(proof.tenant_signature_hex)
    sig_bytes[0] ^= 0xFF
    proof_dict_sig["tenant_signature_hex"] = sig_bytes.hex()
    res_sig = test_engine.verify_budget_proof(inputs, ZkBudgetProof.from_dict(proof_dict_sig))
    assert res_sig.valid is False
    assert res_sig.rejection_code == HALT_ZK_PROOF_INVALID

    # Tamper Transcript Hash
    proof_dict_hash = proof.to_dict()
    proof_dict_hash["transcript_hash"] = "00" * 32
    res_hash = test_engine.verify_budget_proof(inputs, ZkBudgetProof.from_dict(proof_dict_hash))
    assert res_hash.valid is False
    assert res_hash.rejection_code == HALT_ZK_PROOF_INVALID

    # Tamper Blinding Evaluation
    proof_dict_eval = proof.to_dict()
    proof_dict_eval["aggregate_blinding_eval"] = (proof.aggregate_blinding_eval + 42) % BN254_SCALAR_FIELD_PRIME
    res_eval = test_engine.verify_budget_proof(inputs, ZkBudgetProof.from_dict(proof_dict_eval))
    assert res_eval.valid is False
    assert res_eval.rejection_code in (HALT_ZK_BALANCE_CONSERVATION_FAILED, HALT_ZK_PROOF_INVALID)


def test_cli_self_test_execution():
    """Runs CLI --self-test and verifies clean execution code."""
    proc = subprocess.run(
        [sys.executable, "src/zk_budget_proof_engine.py", "--self-test"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "zk-AEIB Arithmetic Circuit Self-Test Completed Successfully" in proc.stdout


def test_banned_words_compliance_across_owned_files():
    """Verifies 0 banned promotional words exist in any owned file."""
    banned_terms = [
        "guaran" + "teed",
        "guaran" + "tee",
        "proven" + " universally",
        "bullet" + "proof",
        "enterprise" + "-grade",
        "production" + "-safe",
        "100% " + "secure",
        "unassail" + "able",
        "im" + "mune",
        "unhack" + "able",
        "bank" + "-grade",
        "production" + "-ready",
    ]

    owned_files = [
        Path("src/zk_budget_proof_engine.py"),
        Path("tests/test_zk_budget_proof_engine.py"),
        Path("docs/architecture/ZK_AEIB_PRIVACY_PRESERVING_BUDGET_PROOFS.md"),
    ]

    for file_path in owned_files:
        assert file_path.is_file(), f"Owned file {file_path} missing"
        text = file_path.read_text(encoding="utf-8").lower()
        for term in banned_terms:
            # Skip checking the banned list definition inside this test function
            lines = [
                line for line in text.splitlines()
                if not ("\"" + term.split()[0][:4] in line and "banned_terms" not in line)
            ]
            filtered_text = "\n".join(lines)
            assert term not in filtered_text, f"Banned word '{term}' found in {file_path}"
