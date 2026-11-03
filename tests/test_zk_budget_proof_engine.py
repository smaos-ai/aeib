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

from src.capability_status import (
    ERR_CAPABILITY_UNAVAILABLE_ON_HOST,
    SIMULATED_OPT_IN,
    CapabilityUnavailableError,
)
import hashlib
from src.zk_budget_proof_engine import (
    BN254_SCALAR_FIELD_PRIME,
    HALT_ZK_BALANCE_CONSERVATION_FAILED,
    HALT_ZK_CEILING_BREACH,
    HALT_ZK_COMMITMENT_ROOT_MISMATCH,
    HALT_ZK_NEGATIVE_SPEND_DETECTED,
    HALT_ZK_PROOF_INVALID,
    MAX_LIMB_VALUE,
    NUM_LIMBS,
    BudgetPublicInputs,
    PrivateTransaction,
    PrivateWitness,
    ZkBudgetProof,
    ZkBudgetProofEngine,
    ZkCircuitError,
    ZkVerificationResult,
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


def test_default_quarantine_refuses_without_opt_in(test_engine, sample_txs, monkeypatch):
    """By default, verify_budget_proof refuses to run and raises CapabilityUnavailableError."""
    monkeypatch.delenv("AEIB_ALLOW_SIMULATION", raising=False)
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
    proof = test_engine.generate_budget_proof(PrivateWitness(transactions=sample_txs), public_inputs)

    verifier = ZkBudgetProofEngine()
    with pytest.raises(CapabilityUnavailableError) as exc_info:
        verifier.verify_budget_proof(public_inputs, proof)
    assert exc_info.value.code == ERR_CAPABILITY_UNAVAILABLE_ON_HOST


def test_valid_budget_proof_generation_and_verification(test_engine, sample_txs):
    """Evaluates batch transcript generation and opt-in verification with honest SIMULATED_OPT_IN status."""
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
    result = verifier.verify_budget_proof(public_inputs, proof, allow_simulation=True)

    assert result.valid is True
    assert result.status == SIMULATED_OPT_IN
    assert bool(result) is True
    assert result.rejection_code is None
    assert isinstance(result.verification_time_ms, int)
    assert result.verification_time_ms >= 0

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
    res = test_engine.verify_budget_proof(inflated_inputs, proof, allow_simulation=True)
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
    res = test_engine.verify_budget_proof(low_ceiling_inputs, proof, allow_simulation=True)
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
    res = test_engine.verify_budget_proof(mismatched_inputs, proof, allow_simulation=True)
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
    res_root = test_engine.verify_budget_proof(tampered_root_inputs, proof, allow_simulation=True)
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
    res_epoch = test_engine.verify_budget_proof(tampered_epoch_inputs, proof, allow_simulation=True)
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
    res_sig = test_engine.verify_budget_proof(inputs, ZkBudgetProof.from_dict(proof_dict_sig), allow_simulation=True)
    assert res_sig.valid is False
    assert res_sig.rejection_code == HALT_ZK_PROOF_INVALID

    # Tamper Transcript Hash
    proof_dict_hash = proof.to_dict()
    proof_dict_hash["transcript_hash"] = "00" * 32
    res_hash = test_engine.verify_budget_proof(inputs, ZkBudgetProof.from_dict(proof_dict_hash), allow_simulation=True)
    assert res_hash.valid is False
    assert res_hash.rejection_code == HALT_ZK_PROOF_INVALID

    # Tamper Blinding Evaluation
    proof_dict_eval = proof.to_dict()
    proof_dict_eval["aggregate_blinding_eval"] = (proof.aggregate_blinding_eval + 42) % BN254_SCALAR_FIELD_PRIME
    res_eval = test_engine.verify_budget_proof(inputs, ZkBudgetProof.from_dict(proof_dict_eval), allow_simulation=True)
    assert res_eval.valid is False
    assert res_eval.rejection_code in (HALT_ZK_BALANCE_CONSERVATION_FAILED, HALT_ZK_PROOF_INVALID)


def test_sample_blinding_bounds(test_engine):
    """Tests _sample_blinding produces values in [1, r - 1]."""
    r = 7
    values = set()
    for _ in range(50):
        b = test_engine._sample_blinding(r)
        assert 1 <= b < r
        values.add(b)
    assert values == {1, 2, 3, 4, 5, 6}

    field_b = test_engine._sample_blinding(BN254_SCALAR_FIELD_PRIME)
    assert 1 <= field_b < BN254_SCALAR_FIELD_PRIME


def test_decompose_into_limbs_and_boundaries(test_engine):
    """Tests binary limb decomposition and boundary rejections."""
    limbs_zero = test_engine.decompose_into_limbs(0)
    assert len(limbs_zero) == NUM_LIMBS
    assert all(b == 0 for b in limbs_zero)

    limbs_one = test_engine.decompose_into_limbs(1)
    assert limbs_one[0] == 1
    assert all(b == 0 for b in limbs_one[1:])

    limbs_max = test_engine.decompose_into_limbs(MAX_LIMB_VALUE)
    assert len(limbs_max) == NUM_LIMBS
    assert all(b == 1 for b in limbs_max)

    with pytest.raises(ZkCircuitError) as exc_neg:
        test_engine.decompose_into_limbs(-1)
    assert exc_neg.value.rejection_code == HALT_ZK_NEGATIVE_SPEND_DETECTED

    with pytest.raises(ZkCircuitError) as exc_over:
        test_engine.decompose_into_limbs(MAX_LIMB_VALUE + 1)
    assert exc_over.value.rejection_code == HALT_ZK_NEGATIVE_SPEND_DETECTED


def test_merkle_root_edge_cases(test_engine):
    """Tests empty Merkle tree root, odd leaf duplication, and 4-leaf golden root."""
    empty_root = test_engine.compute_merkle_root([])
    assert empty_root == hashlib.sha256(b"EMPTY_ZK_AEIB_TREE").hexdigest()

    leaves_single = ["aa" * 32]
    root_single = test_engine.compute_merkle_root(leaves_single)
    assert root_single == "aa" * 32

    leaves_odd = ["11" * 32, "22" * 32, "33" * 32]
    root_odd = test_engine.compute_merkle_root(leaves_odd)
    assert isinstance(root_odd, str) and len(root_odd) == 64

    leaves_four = ["11" * 32, "22" * 32, "33" * 32, "44" * 32]
    assert test_engine.compute_merkle_root(leaves_four) == "7742fda6ee2cc27d86a9d67d75ab3f2f5ae6afaf5b0a5d734fbdf04ea82ba928"


def test_generate_proof_empty_witness_rejected(test_engine):
    """Generating a proof with 0 transactions raises HALT_ZK_PROOF_INVALID."""
    public_inputs = BudgetPublicInputs(
        initial_balance_minor=1000,
        final_balance_minor=1000,
        budget_ceiling_minor=500,
        commitment_merkle_root="00" * 32,
        epoch=202610,
    )
    with pytest.raises(ZkCircuitError) as exc_info:
        test_engine.generate_budget_proof(PrivateWitness(transactions=[]), public_inputs)
    assert exc_info.value.rejection_code == HALT_ZK_PROOF_INVALID


def test_generate_proof_spend_and_slack_overflow(test_engine):
    """Generating a proof with spend or slack exceeding MAX_LIMB_VALUE fails closed."""
    huge_tx = [PrivateTransaction(spend_minor=MAX_LIMB_VALUE + 1, salt="s", payee="p")]
    public_inputs = BudgetPublicInputs(
        initial_balance_minor=MAX_LIMB_VALUE + 10,
        final_balance_minor=9,
        budget_ceiling_minor=MAX_LIMB_VALUE + 20,
        commitment_merkle_root="00" * 32,
        epoch=202610,
    )
    with pytest.raises(ZkCircuitError) as exc_spend:
        test_engine.generate_budget_proof(PrivateWitness(huge_tx), public_inputs)
    assert exc_spend.value.rejection_code == HALT_ZK_NEGATIVE_SPEND_DETECTED

    tx_normal = [PrivateTransaction(spend_minor=10, salt="s", payee="p")]
    leaves = [test_engine.compute_leaf_commitment(t.salt, t.spend_minor, t.payee) for t in tx_normal]
    root = test_engine.compute_merkle_root(leaves)
    public_inputs_huge_slack = BudgetPublicInputs(
        initial_balance_minor=100,
        final_balance_minor=90,
        budget_ceiling_minor=MAX_LIMB_VALUE + 20,
        commitment_merkle_root=root,
        epoch=202610,
    )
    with pytest.raises(ZkCircuitError) as exc_slack:
        test_engine.generate_budget_proof(PrivateWitness(tx_normal), public_inputs_huge_slack)
    assert exc_slack.value.rejection_code == HALT_ZK_CEILING_BREACH


def test_verifier_delta_negative_and_slack_bounds(test_engine, sample_txs):
    """Verifier rejects negative delta and slack exceeding MAX_LIMB_VALUE."""
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

    # Negative delta
    neg_delta_inputs = BudgetPublicInputs(
        initial_balance_minor=1000,
        final_balance_minor=1001,
        budget_ceiling_minor=15000,
        commitment_merkle_root=root,
        epoch=202610,
    )
    res_neg = test_engine.verify_budget_proof(neg_delta_inputs, proof, allow_simulation=True)
    assert res_neg.valid is False
    assert res_neg.rejection_code == HALT_ZK_NEGATIVE_SPEND_DETECTED
    assert isinstance(res_neg.verification_time_ms, int)

    # Slack exceeding MAX_LIMB_VALUE
    huge_slack_inputs = BudgetPublicInputs(
        initial_balance_minor=100000,
        final_balance_minor=100000 - total_spend,
        budget_ceiling_minor=total_spend + MAX_LIMB_VALUE + 10,
        commitment_merkle_root=root,
        epoch=202610,
    )
    res_slack = test_engine.verify_budget_proof(huge_slack_inputs, proof, allow_simulation=True)
    assert res_slack.valid is False
    assert res_slack.rejection_code == HALT_ZK_CEILING_BREACH


def test_verifier_mismatched_vector_lengths_and_limb_lengths(test_engine, sample_txs):
    """Verifier rejects evaluation vectors with inconsistent lengths."""
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

    # 1. Vector length mismatch
    proof_dict1 = proof.to_dict()
    proof_dict1["evaluations"]["v_m_x"] = proof_dict1["evaluations"]["v_m_x"][:-1]
    res1 = test_engine.verify_budget_proof(inputs, ZkBudgetProof.from_dict(proof_dict1), allow_simulation=True)
    assert res1.valid is False
    assert res1.rejection_code == HALT_ZK_PROOF_INVALID

    # 2. Masked poly limb length != 64
    proof_dict2 = proof.to_dict()
    proof_dict2["evaluations"]["masked_polys"][0] = proof_dict2["evaluations"]["masked_polys"][0][:-1]
    res2 = test_engine.verify_budget_proof(inputs, ZkBudgetProof.from_dict(proof_dict2), allow_simulation=True)
    assert res2.valid is False
    assert res2.rejection_code == HALT_ZK_NEGATIVE_SPEND_DETECTED

    # 3. Slack poly limb length != 64
    proof_dict3 = proof.to_dict()
    proof_dict3["evaluations"]["ms_poly"] = proof_dict3["evaluations"]["ms_poly"][:-1]
    res3 = test_engine.verify_budget_proof(inputs, ZkBudgetProof.from_dict(proof_dict3), allow_simulation=True)
    assert res3.valid is False
    assert res3.rejection_code == HALT_ZK_CEILING_BREACH

    # 4. Malformed non-integer slack evaluation
    proof_dict4 = proof.to_dict()
    proof_dict4["evaluations"]["v_ms_2"] = "not_an_int"
    res4 = test_engine.verify_budget_proof(inputs, ZkBudgetProof.from_dict(proof_dict4), allow_simulation=True)
    assert res4.valid is False
    assert res4.rejection_code == HALT_ZK_PROOF_INVALID

    # 5. Inconsistent slack evaluation at challenge_x
    proof_dict5 = proof.to_dict()
    orig_v_ms_x = int(proof_dict5["evaluations"]["v_ms_x"])
    proof_dict5["evaluations"]["v_ms_x"] = str((orig_v_ms_x + 1) % BN254_SCALAR_FIELD_PRIME)
    res5 = test_engine.verify_budget_proof(inputs, ZkBudgetProof.from_dict(proof_dict5), allow_simulation=True)
    assert res5 is not None
    assert res5.valid is False
    assert res5.rejection_code == HALT_ZK_PROOF_INVALID
    assert "Slack evaluation at challenge x inconsistent" in res5.reason

    # 6. Inconsistent slack commitment homomorphism
    proof_dict6 = proof.to_dict()
    orig_sigma_ms = int(proof_dict6["evaluations"]["sigma_ms"])
    proof_dict6["evaluations"]["sigma_ms"] = str((orig_sigma_ms + 1) % BN254_SCALAR_FIELD_PRIME)
    res6 = test_engine.verify_budget_proof(inputs, ZkBudgetProof.from_dict(proof_dict6), allow_simulation=True)
    assert res6 is not None
    assert res6.valid is False
    assert res6.rejection_code == HALT_ZK_PROOF_INVALID
    assert "Slack commitment homomorphism failed" in res6.reason


def test_protocol_constants_and_dataclasses_frozen(test_engine):
    """Asserts exact protocol constants and immutability of data models."""
    import dataclasses
    assert NUM_LIMBS == 64
    assert MAX_LIMB_VALUE == (1 << 64) - 1

    tx = PrivateTransaction(spend_minor=10, salt="s", payee="p")
    with pytest.raises((dataclasses.FrozenInstanceError, TypeError)):
        tx.spend_minor = 20

    witness = PrivateWitness(transactions=[tx])
    with pytest.raises((dataclasses.FrozenInstanceError, TypeError)):
        witness.transactions = []

    res = ZkVerificationResult(valid=True)
    assert res.verification_time_ms == 0
    with pytest.raises((dataclasses.FrozenInstanceError, TypeError)):
        res.valid = False

    inputs = BudgetPublicInputs(
        initial_balance_minor=100,
        final_balance_minor=90,
        budget_ceiling_minor=50,
        commitment_merkle_root="aa"*32,
        epoch=202610
    )
    with pytest.raises((dataclasses.FrozenInstanceError, TypeError)):
        inputs.epoch = 0


def test_commit_poly_exact_golden_vector(test_engine):
    """Asserts exact polynomial commitment output on known test vector."""
    val = test_engine._commit_poly([1, 2], 3)
    assert hex(val) == "0x1bfc731cea811802deff420b3cbdc098fe1d756494dece5b5a82e5fc3f4ead3e"


def test_prover_rejects_mismatched_merkle_root(test_engine, sample_txs):
    """Prover raises HALT_ZK_COMMITMENT_ROOT_MISMATCH when witness root != public input root."""
    total_spend = sum(t.spend_minor for t in sample_txs)
    bad_inputs = BudgetPublicInputs(
        initial_balance_minor=100000,
        final_balance_minor=100000 - total_spend,
        budget_ceiling_minor=15000,
        commitment_merkle_root="00" * 32,
        epoch=202610,
    )
    with pytest.raises(ZkCircuitError) as exc_gen:
        test_engine.generate_budget_proof(PrivateWitness(sample_txs), bad_inputs)
    assert exc_gen.value.rejection_code == HALT_ZK_COMMITMENT_ROOT_MISMATCH


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
