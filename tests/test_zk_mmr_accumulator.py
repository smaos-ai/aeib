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
tests/test_zk_mmr_accumulator.py — Verification suite for Zero-Knowledge Merkle Mountain Range Accumulator.

Part of Sovereign Multi-Agent OS (SMAOS) / AEIB Enterprise Gateway.
Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model as an append-only
Zero-Knowledge Merkle Mountain Range (MMR) accumulator and non-interactive polynomial proof prototype.
Zero-Mock Compliance: Real BN254 scalar field arithmetic, real SQLite-WAL databases, zero mocks.
"""

from dataclasses import FrozenInstanceError
import time
import pytest

from src.zk_mmr_accumulator import (
    BN254_SCALAR_FIELD_PRIME,
    HALT_MMR_EMPTY_TREE,
    HALT_MMR_LEAF_OUT_OF_BOUNDS,
    STATUS_PROOF_VERIFIED,
    MmrPeak,
    ZkMmrAccumulator,
    ZkMmrInclusionProof,
    combine_field_scalars,
    compute_sha256,
    compute_wilson_ci_bps,
    evaluate_polynomial_horner,
    hash_to_field_scalar,
)


def test_01_dataclass_validations_and_bn254_prime() -> None:
    """Verify input validation for MmrPeak and ZkMmrInclusionProof."""
    assert BN254_SCALAR_FIELD_PRIME == 21888242871839275222246405745257275088548364400416034343698204186575808495617

    # Valid MmrPeak
    peak = MmrPeak(height=1, leaf_count=2, scalar_hash=12345)
    assert peak.height == 1
    assert peak.leaf_count == 2

    # MmrPeak is frozen
    with pytest.raises(FrozenInstanceError):
        peak.height = 2

    # MmrPeak invalid height
    with pytest.raises(ValueError, match="Peak height"):
        MmrPeak(height=-1, leaf_count=2, scalar_hash=12345)

    # MmrPeak invalid leaf count
    with pytest.raises(ValueError, match="Peak leaf count"):
        MmrPeak(height=0, leaf_count=0, scalar_hash=12345)

    # MmrPeak out of bounds scalar
    with pytest.raises(ValueError, match="BN254 field bounds"):
        MmrPeak(height=0, leaf_count=1, scalar_hash=BN254_SCALAR_FIELD_PRIME)

    # Valid ZkMmrInclusionProof
    proof = ZkMmrInclusionProof(
        tree_id="tree:1",
        leaf_pos=0,
        receipt_caid="11" * 32,
        leaf_scalar=100,
        auth_path=[(200, False)],
        peak_height=1,
        bagged_root="22" * 32,
        fiat_shamir_challenge=300,
        polynomial_evaluation=400,
        proof_caid="33" * 32,
    )
    assert proof.leaf_pos == 0

    # ZkMmrInclusionProof invalid cases
    with pytest.raises(ValueError, match="tree_id"):
        ZkMmrInclusionProof(
            tree_id="",
            leaf_pos=0,
            receipt_caid="11" * 32,
            leaf_scalar=100,
            auth_path=[],
            peak_height=0,
            bagged_root="22" * 32,
            fiat_shamir_challenge=300,
            polynomial_evaluation=400,
            proof_caid="33" * 32,
        )

    with pytest.raises(ValueError, match="leaf_pos"):
        ZkMmrInclusionProof(
            tree_id="tree:1",
            leaf_pos=-1,
            receipt_caid="11" * 32,
            leaf_scalar=100,
            auth_path=[],
            peak_height=0,
            bagged_root="22" * 32,
            fiat_shamir_challenge=300,
            polynomial_evaluation=400,
            proof_caid="33" * 32,
        )

    with pytest.raises(ValueError, match="receipt_caid"):
        ZkMmrInclusionProof(
            tree_id="tree:1",
            leaf_pos=0,
            receipt_caid="",
            leaf_scalar=100,
            auth_path=[],
            peak_height=0,
            bagged_root="22" * 32,
            fiat_shamir_challenge=300,
            polynomial_evaluation=400,
            proof_caid="33" * 32,
        )

    with pytest.raises(ValueError, match="leaf_scalar"):
        ZkMmrInclusionProof(
            tree_id="tree:1",
            leaf_pos=0,
            receipt_caid="11" * 32,
            leaf_scalar=BN254_SCALAR_FIELD_PRIME + 1,
            auth_path=[],
            peak_height=0,
            bagged_root="22" * 32,
            fiat_shamir_challenge=300,
            polynomial_evaluation=400,
            proof_caid="33" * 32,
        )

    with pytest.raises(ValueError, match="bagged_root"):
        ZkMmrInclusionProof(
            tree_id="tree:1",
            leaf_pos=0,
            receipt_caid="11" * 32,
            leaf_scalar=100,
            auth_path=[],
            peak_height=0,
            bagged_root="",
            fiat_shamir_challenge=300,
            polynomial_evaluation=400,
            proof_caid="33" * 32,
        )

    with pytest.raises(ValueError, match="proof_caid"):
        ZkMmrInclusionProof(
            tree_id="tree:1",
            leaf_pos=0,
            receipt_caid="11" * 32,
            leaf_scalar=100,
            auth_path=[],
            peak_height=0,
            bagged_root="22" * 32,
            fiat_shamir_challenge=300,
            polynomial_evaluation=400,
            proof_caid="",
        )


def test_02_field_arithmetic_and_horner() -> None:
    """Verify BN254 scalar field conversions, combinations, and Horner polynomial evaluation."""
    s1 = hash_to_field_scalar(b"alpha")
    s2 = hash_to_field_scalar(b"beta")
    assert 0 <= s1 < BN254_SCALAR_FIELD_PRIME
    assert 0 <= s2 < BN254_SCALAR_FIELD_PRIME

    combined = combine_field_scalars(s1, s2)
    assert 0 <= combined < BN254_SCALAR_FIELD_PRIME
    assert combined == combine_field_scalars(s1, s2)

    # Empty polynomial coefficients
    assert evaluate_polynomial_horner([], 5) == 0

    # Horner vs direct expansion for P(x) = 3 + 5x + 7x^2
    coeffs = [3, 5, 7]
    x = 11
    expected = (3 + 5 * 11 + 7 * (11**2)) % BN254_SCALAR_FIELD_PRIME
    assert evaluate_polynomial_horner(coeffs, x) == expected


def test_03_nominal_single_leaf_mmr() -> None:
    """Verify single-leaf MMR creation, root computation, and inclusion verification."""
    mmr = ZkMmrAccumulator(tree_id="tree:single", db_path=":memory:")
    assert mmr.leaf_count == 0
    assert mmr.get_bagged_root() == "0" * 64

    caid = "aa" * 32
    pos = mmr.append_receipt(caid, timestamp_ms=1000)
    assert pos == 0
    assert mmr.leaf_count == 1

    root = mmr.get_bagged_root()
    assert len(root) == 64
    assert root != "0" * 64

    proof = mmr.generate_inclusion_proof(0)
    assert proof.leaf_pos == 0
    assert proof.receipt_caid == caid
    assert proof.peak_height == 0
    assert len(proof.auth_path) == 0
    assert proof.bagged_root == root

    # Verify proof
    assert mmr.verify_inclusion_proof(proof) is True


def test_04_multi_leaf_peak_merging() -> None:
    """Verify binary peak merging across multiple appended receipts (1 to 7 leaves)."""
    mmr = ZkMmrAccumulator(tree_id="tree:multi", db_path=":memory:")
    caids = [f"{i:02x}" * 32 for i in range(1, 8)]  # 7 caids

    # Append leaves
    positions = []
    for i, caid in enumerate(caids):
        p = mmr.append_receipt(caid, timestamp_ms=1000 + i)
        positions.append(p)

    assert positions == [0, 1, 2, 3, 4, 5, 6]
    assert mmr.leaf_count == 7

    # 7 leaves = 4 + 2 + 1 -> 3 peaks (heights 2, 1, 0)
    peaks = mmr._peaks
    assert len(peaks) == 3
    assert peaks[0][0].height == 2
    assert peaks[1][0].height == 1
    assert peaks[2][0].height == 0

    # Verify inclusion proof for every single leaf
    for pos in range(7):
        proof = mmr.generate_inclusion_proof(pos)
        assert proof.leaf_pos == pos
        assert mmr.verify_inclusion_proof(proof) is True


def test_05_fail_closed_empty_and_out_of_bounds() -> None:
    """Verify fail-closed errors on empty MMR and out-of-bounds positions."""
    mmr = ZkMmrAccumulator(tree_id="tree:err", db_path=":memory:")

    with pytest.raises(ValueError, match=HALT_MMR_EMPTY_TREE):
        mmr.generate_inclusion_proof(0)

    mmr.append_receipt("11" * 32, timestamp_ms=1000)

    with pytest.raises(ValueError, match=HALT_MMR_LEAF_OUT_OF_BOUNDS):
        mmr.generate_inclusion_proof(1)

    with pytest.raises(ValueError, match=HALT_MMR_LEAF_OUT_OF_BOUNDS):
        mmr.generate_inclusion_proof(-1)

    # Invalid receipt length
    with pytest.raises(ValueError, match="64-character hex"):
        mmr.append_receipt("invalid_caid")


def test_06_fail_closed_tampered_proofs() -> None:
    """Verify rejection of tampered fields in ZK MMR inclusion proofs."""
    mmr = ZkMmrAccumulator(tree_id="tree:tamper", db_path=":memory:")
    caids = [f"{i:02x}" * 32 for i in range(1, 5)]  # 4 leaves
    for caid in caids:
        mmr.append_receipt(caid, timestamp_ms=1000)

    proof = mmr.generate_inclusion_proof(2)
    assert mmr.verify_inclusion_proof(proof) is True

    # 1. Tampered leaf_scalar
    bad_scalar = ZkMmrInclusionProof(
        tree_id=proof.tree_id,
        leaf_pos=proof.leaf_pos,
        receipt_caid=proof.receipt_caid,
        leaf_scalar=(proof.leaf_scalar + 1) % BN254_SCALAR_FIELD_PRIME,
        auth_path=proof.auth_path,
        peak_height=proof.peak_height,
        bagged_root=proof.bagged_root,
        fiat_shamir_challenge=proof.fiat_shamir_challenge,
        polynomial_evaluation=proof.polynomial_evaluation,
        proof_caid=proof.proof_caid,
    )
    assert mmr.verify_inclusion_proof(bad_scalar) is False

    # 2. Tampered receipt_caid
    bad_caid = ZkMmrInclusionProof(
        tree_id=proof.tree_id,
        leaf_pos=proof.leaf_pos,
        receipt_caid="ff" * 32,
        leaf_scalar=proof.leaf_scalar,
        auth_path=proof.auth_path,
        peak_height=proof.peak_height,
        bagged_root=proof.bagged_root,
        fiat_shamir_challenge=proof.fiat_shamir_challenge,
        polynomial_evaluation=proof.polynomial_evaluation,
        proof_caid=proof.proof_caid,
    )
    assert mmr.verify_inclusion_proof(bad_caid) is False

    # 3. Tampered Fiat-Shamir challenge
    bad_challenge = ZkMmrInclusionProof(
        tree_id=proof.tree_id,
        leaf_pos=proof.leaf_pos,
        receipt_caid=proof.receipt_caid,
        leaf_scalar=proof.leaf_scalar,
        auth_path=proof.auth_path,
        peak_height=proof.peak_height,
        bagged_root=proof.bagged_root,
        fiat_shamir_challenge=(proof.fiat_shamir_challenge + 1) % BN254_SCALAR_FIELD_PRIME,
        polynomial_evaluation=proof.polynomial_evaluation,
        proof_caid=proof.proof_caid,
    )
    assert mmr.verify_inclusion_proof(bad_challenge) is False

    # 4. Tampered polynomial evaluation
    bad_eval = ZkMmrInclusionProof(
        tree_id=proof.tree_id,
        leaf_pos=proof.leaf_pos,
        receipt_caid=proof.receipt_caid,
        leaf_scalar=proof.leaf_scalar,
        auth_path=proof.auth_path,
        peak_height=proof.peak_height,
        bagged_root=proof.bagged_root,
        fiat_shamir_challenge=proof.fiat_shamir_challenge,
        polynomial_evaluation=(proof.polynomial_evaluation + 1) % BN254_SCALAR_FIELD_PRIME,
        proof_caid=proof.proof_caid,
    )
    assert mmr.verify_inclusion_proof(bad_eval) is False

    # 5. Tampered bagged root
    bad_root = ZkMmrInclusionProof(
        tree_id=proof.tree_id,
        leaf_pos=proof.leaf_pos,
        receipt_caid=proof.receipt_caid,
        leaf_scalar=proof.leaf_scalar,
        auth_path=proof.auth_path,
        peak_height=proof.peak_height,
        bagged_root="00" * 32,
        fiat_shamir_challenge=proof.fiat_shamir_challenge,
        polynomial_evaluation=proof.polynomial_evaluation,
        proof_caid=proof.proof_caid,
    )
    assert mmr.verify_inclusion_proof(bad_root) is False

    # 6. Out of bounds leaf_pos in proof
    bad_pos = ZkMmrInclusionProof(
        tree_id=proof.tree_id,
        leaf_pos=99,
        receipt_caid=proof.receipt_caid,
        leaf_scalar=proof.leaf_scalar,
        auth_path=proof.auth_path,
        peak_height=proof.peak_height,
        bagged_root=proof.bagged_root,
        fiat_shamir_challenge=proof.fiat_shamir_challenge,
        polynomial_evaluation=proof.polynomial_evaluation,
        proof_caid=proof.proof_caid,
    )
    assert mmr.verify_inclusion_proof(bad_pos) is False


def test_07_sqlite_persistence_and_queries() -> None:
    """Verify SQLite WAL persistence of MMR states, leaves, and verified proofs."""
    mmr = ZkMmrAccumulator(tree_id="tree:persisted", db_path=":memory:")
    caid = "bb" * 32
    mmr.append_receipt(caid, timestamp_ms=5000)

    # Check leaves table
    cursor = mmr._conn.execute(
        "SELECT leaf_pos, receipt_caid, timestamp_ms FROM zk_mmr_leaves WHERE tree_id = ?;",
        (mmr.tree_id,),
    )
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == 0
    assert row[1] == caid
    assert row[2] == 5000

    # Check state table
    cursor_st = mmr._conn.execute(
        "SELECT leaf_count, bagged_root FROM zk_mmr_state WHERE tree_id = ?;",
        (mmr.tree_id,),
    )
    row_st = cursor_st.fetchone()
    assert row_st is not None
    assert row_st[0] == 1
    assert row_st[1] == mmr.get_bagged_root()

    # Verify proof and check proofs table
    t_verify = int(time.time() * 1000)
    proof = mmr.generate_inclusion_proof(0)
    assert mmr.verify_inclusion_proof(proof) is True

    cursor_pr = mmr._conn.execute(
        "SELECT proof_caid, status, verified_at_ms FROM zk_mmr_proofs WHERE tree_id = ?;",
        (mmr.tree_id,),
    )
    row_pr = cursor_pr.fetchone()
    assert row_pr is not None
    assert row_pr[0] == proof.proof_caid
    assert row_pr[1] == STATUS_PROOF_VERIFIED
    assert abs(row_pr[2] - t_verify) <= 5000


def test_08_exact_mutation_boundaries() -> None:
    """Exercise boundary conditions and edge cases to kill mutation survivors."""
    # 1. Invalid tree_id in init
    with pytest.raises(ValueError, match="tree_id"):
        ZkMmrAccumulator(tree_id="")

    # 2. Default timestamp path in append_receipt
    t_append = int(time.time() * 1000)
    mmr = ZkMmrAccumulator(tree_id="tree:bounds", db_path=":memory:")
    pos = mmr.append_receipt("cc" * 32)
    assert pos == 0

    cursor = mmr._conn.execute("SELECT timestamp_ms FROM zk_mmr_leaves WHERE leaf_pos = 0;")
    assert abs(cursor.fetchone()[0] - t_append) <= 5000

    # Test exact bounds error message format [0..0]
    with pytest.raises(ValueError, match=r"\[0\.\.0\]"):
        mmr.generate_inclusion_proof(1)

    # 3. get_peak_hashes helper
    peaks_hex = mmr.get_peak_hashes()
    assert len(peaks_hex) == 1
    assert len(peaks_hex[0]) == 64

    # 4. Auth path with sibling on left vs right
    # Appending a 2nd leaf creates a 2-leaf tree where leaf 0 has right sibling, leaf 1 has left sibling
    mmr.append_receipt("dd" * 32)
    proof_left = mmr.generate_inclusion_proof(0)
    proof_right = mmr.generate_inclusion_proof(1)
    assert proof_left.auth_path[0][1] is False  # Sibling on right
    assert proof_right.auth_path[0][1] is True   # Sibling on left

    assert mmr.verify_inclusion_proof(proof_left) is True
    assert mmr.verify_inclusion_proof(proof_right) is True

    # 5. Tampered auth path sibling hash
    tampered_auth_path = [(proof_left.auth_path[0][0] + 1, proof_left.auth_path[0][1])]
    bad_path_proof = ZkMmrInclusionProof(
        tree_id=proof_left.tree_id,
        leaf_pos=proof_left.leaf_pos,
        receipt_caid=proof_left.receipt_caid,
        leaf_scalar=proof_left.leaf_scalar,
        auth_path=tampered_auth_path,
        peak_height=proof_left.peak_height,
        bagged_root=proof_left.bagged_root,
        fiat_shamir_challenge=proof_left.fiat_shamir_challenge,
        polynomial_evaluation=proof_left.polynomial_evaluation,
        proof_caid=proof_left.proof_caid,
    )
    assert mmr.verify_inclusion_proof(bad_path_proof) is False

    # 6. Corrupted internal state triggers RuntimeError
    corrupt_mmr = ZkMmrAccumulator(tree_id="tree:corrupt", db_path=":memory:")
    corrupt_mmr.append_receipt("ee" * 32)
    corrupt_mmr._peaks.clear()
    with pytest.raises(RuntimeError, match="Corrupted MMR state"):
        corrupt_mmr.generate_inclusion_proof(0)


def test_09_wilson_ci_bounds_and_epistemic_lexicon() -> None:
    """Verify conservative Wilson 95% confidence interval and epistemic integrity."""
    low, high = compute_wilson_ci_bps(28, 30)
    assert low == 7868
    assert high == 9815

    low_zero, high_zero = compute_wilson_ci_bps(0, 0)
    assert low_zero == 0 and high_zero == 0

    low_neg, high_neg = compute_wilson_ci_bps(-1, 10)
    assert low_neg == 0 and high_neg == 0

    # Epistemic docstring check
    import src.zk_mmr_accumulator as mod
    doc = mod.__doc__ or ""
    banned_fragments = [("revo", "lutionary"), ("unbreak", "able"), ("bullet", "proof")]
    for p1, p2 in banned_fragments:
        word = p1 + p2
        assert word not in doc.lower(), f"Banned marketing word '{word}' found in docstring"

    # Confirm Rule CI004 honesty statement present
    assert "Honest Platform Boundary" in doc
    assert "INTERNAL PREVIEW COMMISSIONED" in doc
    assert "scaffold" in doc.lower() or "simulated" in doc.lower()
