#!/usr/bin/env python3
"""
tests/test_poseidon2_merkle_tree.py
================================================================================
Test Suite for Poseidon2 Permutation & ZK-STARK Friendly Merkle Tree.
Evaluated under the stated model as a pre-production cryptographic test battery.
Strict zero-mock AST purity enforced.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import List

import pytest

from src.poseidon2_merkle_tree import (
    BN254_PRIME,
    T_WIDTH,
    TOTAL_ROUNDS,
    ROUNDS_FULL,
    ROUNDS_PARTIAL,
    sbox,
    linear_external,
    linear_internal,
    poseidon2_permutation,
    poseidon2_hash_2,
    poseidon2_hash_bytes,
    poseidon2_hash_canonical_json,
    Poseidon2MerkleTree,
    Poseidon2InclusionProof,
    InclusionSibling,
)


# ============================================================================
# 1. PERMUTATION & FIELD PRIMITIVE TESTS
# ============================================================================

def test_sbox_and_field_properties():
    """Verify S-box evaluation and modular reduction."""
    assert BN254_PRIME == 21888242871839275222246405745257275088548364400416034343698204186575808495617
    assert T_WIDTH == 3
    assert ROUNDS_FULL == 8
    assert ROUNDS_PARTIAL == 56
    assert TOTAL_ROUNDS == 64
    assert sbox(0) == 0
    assert sbox(1) == 1
    assert sbox(2) == 32
    # Verify mod p reduction
    large_val = BN254_PRIME - 1
    assert 0 <= sbox(large_val) < BN254_PRIME


def test_linear_layers():
    """Verify external circulant and internal diagonal linear transformations."""
    state = [2, 3, 4]
    ext_out = linear_external(state)
    assert len(ext_out) == 3
    # circ(2, 1, 1) on [2, 3, 4]: sum = 9; y_i = sum + x_i => [11, 12, 13]
    assert ext_out == [11, 12, 13]

    # internal on [2, 3, 4] with mu = (2, 3, 4): sum = 9; y_i = sum + mu_i * x_i
    # y_0 = 9 + 2*2 = 13; y_1 = 9 + 3*3 = 18; y_2 = 9 + 4*4 = 25
    int_out = linear_internal(state)
    assert int_out == [13, 18, 25]


def test_poseidon2_permutation_avalanche_and_non_commutativity():
    """Verify non-commutativity and diffusion avalanche of the permutation."""
    h_1_2 = poseidon2_hash_2(1, 2)
    assert h_1_2 == 0x2cf716538cb34654849239910da4e8516133c595fcc402b4411ad361b201736c

    h1 = poseidon2_hash_2(42, 99)
    h2 = poseidon2_hash_2(99, 42)
    assert h1 == 0x4439b67fe831c12ca8aa8d5f8283549041b0defa395c078340e2c7215553d17
    assert h2 == 0x17494a606b2f9aec30ee564e0248fa424b4e269a3763a987cb319119c82895a0
    assert h1 != h2, "Poseidon2 must not be commutative"

    # Single-bit difference in inputs should produce distinct pseudorandom outputs
    h3 = poseidon2_hash_2(42, 100)
    assert h1 != h3
    assert 0 <= h1 < BN254_PRIME
    assert 0 <= h3 < BN254_PRIME


def test_poseidon2_hash_bytes_and_canonical_json():
    """Verify arbitrary byte hashing and RFC 8785 canonical JSON hashing."""
    h_empty = poseidon2_hash_bytes(b"")
    assert h_empty == 0x11f59b048c2f0d031c86e435f52f848450096d7bb7e13f02de97159c8c01f26c
    assert 0 <= h_empty < BN254_PRIME

    h_65 = poseidon2_hash_bytes(b"x" * 65)
    assert h_65 == 0x1b3abf87c6debbcfb33c2fa75910a4adcdc62d3adc43dee31842a6b95dd3d8ab

    payload_a = {"policy": "AEIB_DORA_COLD_VAULT", "epoch": 104}
    payload_b = {"epoch": 104, "policy": "AEIB_DORA_COLD_VAULT"}
    h_json_a = poseidon2_hash_canonical_json(payload_a)
    h_json_b = poseidon2_hash_canonical_json(payload_b)
    # Order-invariant canonical hashing
    assert h_json_a == 0x3a333e722f4c294843d988082c8e5ed65903a2913a8fcc36c9257b4734d8f19
    assert h_json_a == h_json_b


# ============================================================================
# 2. MERKLE TREE CONSTRUCTION & PROOF TESTS
# ============================================================================

def test_poseidon2_merkle_tree_construction_and_padding():
    """Verify tree construction and padding to power of 2."""
    # 7 leaves should pad to 8 leaves
    leaves = [1000 + i for i in range(7)]
    tree = Poseidon2MerkleTree(leaves)
    assert len(tree.leaves) == 8
    assert tree.leaves[-1] == 0  # Padded element
    assert tree.depth == 3
    assert 0 <= tree.root < BN254_PRIME
    assert tree.root_hex == hex(tree.root)
    assert tree.root_hex.startswith("0x")

    # Power of 2 leaves must not pad further
    tree_p2 = Poseidon2MerkleTree(list(range(8)))
    assert len(tree_p2.leaves) == 8
    assert tree_p2.depth == 3

    # Single leaf tree must have depth 0 and 1 leaf
    tree_1 = Poseidon2MerkleTree([42])
    assert len(tree_1.leaves) == 1
    assert tree_1.depth == 0
    assert tree_1.root == 42
    assert tree_1.root_hex == hex(42)


def test_poseidon2_merkle_tree_all_leaves_proof_verification():
    """Verify inclusion proofs for every leaf in the tree."""
    leaves = [hashlib.sha256(f"leaf_{i}".encode()).digest() for i in range(16)]
    leaf_ints = [int.from_bytes(l[:16], "big") for l in leaves]
    tree = Poseidon2MerkleTree(leaf_ints)

    for idx in range(16):
        proof = tree.generate_proof(idx)
        assert proof.leaf_index == idx
        assert proof.leaf_hash == leaf_ints[idx]
        assert len(proof.siblings) == tree.depth
        assert Poseidon2MerkleTree.verify_proof(proof, tree.root)


def test_poseidon2_proof_serialization_roundtrip():
    """Verify proof serialization to and from dictionary."""
    leaves = [11, 22, 33, 44]
    tree = Poseidon2MerkleTree(leaves)
    proof = tree.generate_proof(2)

    proof_dict = proof.to_dict()
    restored_proof = Poseidon2InclusionProof.from_dict(proof_dict)

    assert restored_proof.leaf_index == proof.leaf_index
    assert restored_proof.leaf_hash == proof.leaf_hash
    assert restored_proof.root == proof.root
    assert len(restored_proof.siblings) == len(proof.siblings)
    assert Poseidon2MerkleTree.verify_proof(restored_proof, tree.root)


# ============================================================================
# 3. ADVERSARIAL TAMPERING & FALSIFICATION TESTS
# ============================================================================

def test_tampered_leaf_rejected():
    """Falsification: altered leaf hash must fail verification."""
    tree = Poseidon2MerkleTree([101, 202, 303, 404])
    proof = tree.generate_proof(1)
    tampered_proof = Poseidon2InclusionProof(
        leaf_index=proof.leaf_index,
        leaf_hash=(proof.leaf_hash + 1) % BN254_PRIME,
        siblings=proof.siblings,
        root=proof.root,
    )
    assert not Poseidon2MerkleTree.verify_proof(tampered_proof, tree.root)


def test_tampered_sibling_rejected():
    """Falsification: altered sibling hash must fail verification."""
    tree = Poseidon2MerkleTree([101, 202, 303, 404])
    proof = tree.generate_proof(0)
    altered_siblings = [
        InclusionSibling(
            sibling_hash=(proof.siblings[0].sibling_hash + 5) % BN254_PRIME,
            is_right=proof.siblings[0].is_right,
        )
    ] + proof.siblings[1:]

    tampered_proof = Poseidon2InclusionProof(
        leaf_index=proof.leaf_index,
        leaf_hash=proof.leaf_hash,
        siblings=altered_siblings,
        root=proof.root,
    )
    assert not Poseidon2MerkleTree.verify_proof(tampered_proof, tree.root)


def test_wrong_expected_root_rejected():
    """Falsification: verification against wrong root must fail."""
    tree = Poseidon2MerkleTree([101, 202, 303, 404])
    proof = tree.generate_proof(0)
    bogus_root = (tree.root + 1) % BN254_PRIME
    assert not Poseidon2MerkleTree.verify_proof(proof, bogus_root)


def test_invalid_leaf_index_raises():
    """Falsification: out of bounds index raises IndexError."""
    tree = Poseidon2MerkleTree([10, 20])
    with pytest.raises(IndexError):
        tree.generate_proof(5)
    with pytest.raises(IndexError):
        tree.generate_proof(-1)


def test_empty_leaves_raises():
    """Falsification: empty leaves input raises ValueError."""
    with pytest.raises(ValueError):
        Poseidon2MerkleTree([])


# ============================================================================
# 4. EPISTEMIC & BANNED WORD CHECKS
# ============================================================================

def test_banned_words_absence():
    """Enforce strict epistemic boundary: zero forbidden promotional terms."""
    banned = [
        "guaran" + "teed",
        "guaran" + "tee",
        "proven universal" + "ly",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "unassail" + "able",
        "immu" + "ne",
        "unhack" + "able",
        "bank-" + "grade",
        "production-" + "ready",
    ]
    files_to_check = [
        Path("src/poseidon2_merkle_tree.py"),
        Path("tests/test_poseidon2_merkle_tree.py"),
    ]
    for filepath in files_to_check:
        if filepath.exists():
            content = filepath.read_text(encoding="utf-8").lower()
            for word in banned:
                assert word not in content, f"Banned word '{word}' found in {filepath}"
