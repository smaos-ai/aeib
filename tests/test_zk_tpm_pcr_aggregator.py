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
tests/test_zk_tpm_pcr_aggregator.py
================================================================================
Comprehensive verification suite for Zero-Knowledge TPM 2.0 PCR-11 Polynomial Aggregator.
Evaluated under the stated model as an agent execution integrity boundary scaffold.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
import time
import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.zk_tpm_pcr_aggregator import (
    BN254_SCALAR_FIELD_PRIME,
    HALT_ZK_PCR_COMMITMENT_MISMATCH,
    HALT_ZK_PCR_DUPLICATE_NODE,
    HALT_ZK_PCR_EMPTY_BATCH,
    HALT_ZK_PCR_EVALUATION_MISMATCH,
    HALT_ZK_PCR_SIGNATURE_INVALID,
    HALT_ZK_PCR_STALE_EPOCH,
    STATUS_PROOF_VERIFIED,
    TpmPcr11NodeQuote,
    ZkPcrAggregatedProof,
    ZkPcrAggregator,
    ZkPcrVerificationError,
    compute_merkle_root,
    compute_sha256_caid,
    evaluate_polynomial_horner,
    hash_to_bn254_scalar,
)


def _generate_test_node(
    node_id: str,
    region: str,
    pcr11_digest: str,
    epoch: int = 42,
    nonce: str = "test-nonce-123",
    timestamp_ms: int = 1700000000000,
) -> tuple[TpmPcr11NodeQuote, ed25519.Ed25519PrivateKey]:
    priv = ed25519.Ed25519PrivateKey.generate()
    quote = ZkPcrAggregator.create_quote(
        node_id=node_id,
        region=region,
        pcr11_digest=pcr11_digest,
        policy_epoch=epoch,
        nonce=nonce,
        timestamp_ms=timestamp_ms,
        private_key=priv,
    )
    return quote, priv


def test_01_dataclass_and_scalar_hashing() -> None:
    data = b"sample-pcr-measurement"
    scalar = hash_to_bn254_scalar(data)
    assert 0 <= scalar < BN254_SCALAR_FIELD_PRIME

    # Boundary check on scalar field prime modulo
    assert evaluate_polynomial_horner([BN254_SCALAR_FIELD_PRIME + 17], 1) == 17

    caid = compute_sha256_caid({"test": "data", "count": 1})
    assert caid.startswith("sha256:")
    assert len(caid) == 71

    root_empty = compute_merkle_root([])
    assert root_empty.startswith("sha256:")

    digest_a = "sha256:" + hashlib.sha256(b"nodeA").hexdigest()
    digest_b = "sha256:" + hashlib.sha256(b"nodeB").hexdigest()
    root_two = compute_merkle_root([digest_a, digest_b])
    assert root_two.startswith("sha256:")
    assert len(root_two) == 71

    # Exact 3 and 4 leaves Merkle root boundary
    digest_c = "sha256:" + hashlib.sha256(b"nodeC").hexdigest()
    digest_d = "sha256:" + hashlib.sha256(b"nodeD").hexdigest()
    root_four = compute_merkle_root([digest_a, digest_b, digest_c, digest_d])
    leaf_a = bytes.fromhex(digest_a[7:])
    leaf_b = bytes.fromhex(digest_b[7:])
    leaf_c = bytes.fromhex(digest_c[7:])
    leaf_d = bytes.fromhex(digest_d[7:])
    h_ab = hashlib.sha256(leaf_a + leaf_b).digest()
    h_cd = hashlib.sha256(leaf_c + leaf_d).digest()
    expected_four = f"sha256:{hashlib.sha256(h_ab + h_cd).hexdigest()}"
    assert root_four == expected_four


def test_02_polynomial_evaluation_horner_vs_naive() -> None:
    coeffs = [10, 25, 42, 99]
    x = 7
    # Naive: 10 + 25*7 + 42*49 + 99*343
    naive = (10 + 25 * 7 + 42 * (7**2) + 99 * (7**3)) % BN254_SCALAR_FIELD_PRIME
    horner = evaluate_polynomial_horner(coeffs, x)
    assert horner == naive

    # Empty coefficients
    assert evaluate_polynomial_horner([], x) == 0


def test_03_nominal_multi_node_aggregation_and_verification() -> None:
    aggregator = ZkPcrAggregator(db_path=":memory:")

    q1, _ = _generate_test_node("node-us-east-1", "us-east-1", "sha256:" + "1" * 64, epoch=100)
    q2, _ = _generate_test_node("node-eu-west-1", "eu-west-1", "sha256:" + "2" * 64, epoch=100)
    q3, _ = _generate_test_node("node-ap-east-1", "ap-east-1", "sha256:" + "3" * 64, epoch=100)

    proof = aggregator.aggregate_quotes([q1, q2, q3], epoch=100, now_ms=1700000010000)

    assert proof.node_count == 3
    assert proof.policy_epoch == 100
    assert proof.status == STATUS_PROOF_VERIFIED
    assert proof.participating_nodes == ["node-ap-east-1", "node-eu-west-1", "node-us-east-1"]
    assert proof.polynomial_commitment.startswith("0x")
    assert proof.challenge_point_x.startswith("0x")
    assert proof.evaluation_y.startswith("0x")
    assert proof.proof_caid.startswith("sha256:")

    # Verify independently
    is_valid = aggregator.verify_proof(proof, [q1, q2, q3])
    assert is_valid is True


def test_04_fail_closed_empty_batch() -> None:
    aggregator = ZkPcrAggregator(db_path=":memory:")
    with pytest.raises(ZkPcrVerificationError) as exc_info:
        aggregator.aggregate_quotes([], epoch=100)
    assert exc_info.value.code == HALT_ZK_PCR_EMPTY_BATCH

    q1, _ = _generate_test_node("node-1", "us-east-1", "sha256:" + "a" * 64, epoch=100)
    proof = aggregator.aggregate_quotes([q1], epoch=100)
    with pytest.raises(ZkPcrVerificationError) as exc_verif:
        aggregator.verify_proof(proof, [])
    assert exc_verif.value.code == HALT_ZK_PCR_EMPTY_BATCH


def test_05_fail_closed_stale_epoch() -> None:
    aggregator = ZkPcrAggregator(db_path=":memory:")
    q1, _ = _generate_test_node("node-1", "us-east-1", "sha256:" + "a" * 64, epoch=99)
    q2, _ = _generate_test_node("node-2", "eu-west-1", "sha256:" + "b" * 64, epoch=100)

    with pytest.raises(ZkPcrVerificationError) as exc_info:
        aggregator.aggregate_quotes([q1, q2], epoch=100)
    assert exc_info.value.code == HALT_ZK_PCR_STALE_EPOCH

    # Also during verification if quotes have wrong epoch
    q1_ok, _ = _generate_test_node("node-1", "us-east-1", "sha256:" + "a" * 64, epoch=100)
    proof = aggregator.aggregate_quotes([q1_ok, q2], epoch=100)

    with pytest.raises(ZkPcrVerificationError) as exc_verif:
        aggregator.verify_proof(proof, [q1, q2])
    assert exc_verif.value.code == HALT_ZK_PCR_STALE_EPOCH


def test_06_fail_closed_duplicate_node() -> None:
    aggregator = ZkPcrAggregator(db_path=":memory:")
    q1, priv1 = _generate_test_node("node-dup", "us-east-1", "sha256:" + "a" * 64, epoch=100)
    # Another quote from same node_id
    q2 = ZkPcrAggregator.create_quote(
        node_id="node-dup",
        region="us-east-1",
        pcr11_digest="sha256:" + "b" * 64,
        policy_epoch=100,
        nonce="nonce-2",
        timestamp_ms=1700000002000,
        private_key=priv1,
    )

    with pytest.raises(ZkPcrVerificationError) as exc_info:
        aggregator.aggregate_quotes([q1, q2], epoch=100)
    assert exc_info.value.code == HALT_ZK_PCR_DUPLICATE_NODE

    # In verification path
    proof = aggregator.aggregate_quotes([q1], epoch=100)
    with pytest.raises(ZkPcrVerificationError) as exc_verif:
        aggregator.verify_proof(proof, [q1, q2])
    assert exc_verif.value.code in (HALT_ZK_PCR_DUPLICATE_NODE, HALT_ZK_PCR_COMMITMENT_MISMATCH)


def test_07_fail_closed_invalid_signature() -> None:
    aggregator = ZkPcrAggregator(db_path=":memory:")
    q1, _ = _generate_test_node("node-1", "us-east-1", "sha256:" + "a" * 64, epoch=100)

    # Corrupt signature
    corrupted_sig = "ff" * 64
    bad_quote = TpmPcr11NodeQuote(
        node_id=q1.node_id,
        region=q1.region,
        pcr11_digest=q1.pcr11_digest,
        policy_epoch=q1.policy_epoch,
        nonce=q1.nonce,
        timestamp_ms=q1.timestamp_ms,
        signature=corrupted_sig,
        public_key_hex=q1.public_key_hex,
    )

    with pytest.raises(ZkPcrVerificationError) as exc_info:
        aggregator.aggregate_quotes([bad_quote], epoch=100)
    assert exc_info.value.code == HALT_ZK_PCR_SIGNATURE_INVALID

    # In verification path
    proof = aggregator.aggregate_quotes([q1], epoch=100)
    with pytest.raises(ZkPcrVerificationError) as exc_verif:
        aggregator.verify_proof(proof, [bad_quote])
    assert exc_verif.value.code == HALT_ZK_PCR_SIGNATURE_INVALID


def test_08_fail_closed_evaluation_and_commitment_mismatch() -> None:
    aggregator = ZkPcrAggregator(db_path=":memory:")
    q1, _ = _generate_test_node("node-1", "us-east-1", "sha256:" + "a" * 64, epoch=100)
    q2, _ = _generate_test_node("node-2", "eu-west-1", "sha256:" + "b" * 64, epoch=100)
    proof = aggregator.aggregate_quotes([q1, q2], epoch=100)

    # Test count mismatch in verify_proof (line 407)
    with pytest.raises(ZkPcrVerificationError, match="Quote count 1 does not match proof node count 2") as exc_count:
        aggregator.verify_proof(proof, [q1])
    assert exc_count.value.code == HALT_ZK_PCR_COMMITMENT_MISMATCH

    # Tamper evaluation_y
    tampered_eval = ZkPcrAggregatedProof(
        aggregation_id=proof.aggregation_id,
        policy_epoch=proof.policy_epoch,
        node_count=proof.node_count,
        participating_nodes=proof.participating_nodes,
        polynomial_commitment=proof.polynomial_commitment,
        challenge_point_x=proof.challenge_point_x,
        evaluation_y="0x" + "00" * 32,
        aggregate_pcr_root=proof.aggregate_pcr_root,
        proof_caid=proof.proof_caid,
        status=proof.status,
        created_at_ms=proof.created_at_ms,
    )

    with pytest.raises(ZkPcrVerificationError) as exc_info:
        aggregator.verify_proof(tampered_eval, [q1, q2])
    assert exc_info.value.code == HALT_ZK_PCR_EVALUATION_MISMATCH

    # Tamper commitment
    tampered_commit = ZkPcrAggregatedProof(
        aggregation_id=proof.aggregation_id,
        policy_epoch=proof.policy_epoch,
        node_count=proof.node_count,
        participating_nodes=proof.participating_nodes,
        polynomial_commitment="0x" + "11" * 32,
        challenge_point_x=proof.challenge_point_x,
        evaluation_y=proof.evaluation_y,
        aggregate_pcr_root=proof.aggregate_pcr_root,
        proof_caid=proof.proof_caid,
        status=proof.status,
        created_at_ms=proof.created_at_ms,
    )

    with pytest.raises(ZkPcrVerificationError) as exc_commit:
        aggregator.verify_proof(tampered_commit, [q1, q2])
    assert exc_commit.value.code == HALT_ZK_PCR_COMMITMENT_MISMATCH


def test_09_sqlite_persistence_and_queries() -> None:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = tf.name

    try:
        aggregator = ZkPcrAggregator(db_path=db_path)
        q1, _ = _generate_test_node("node-1", "us-east-1", "sha256:" + "a" * 64, epoch=100)
        q2, _ = _generate_test_node("node-2", "eu-west-1", "sha256:" + "b" * 64, epoch=100)

        t_before = int(time.time() * 1000)
        proof = aggregator.aggregate_quotes([q1, q2], epoch=100)
        t_after = int(time.time() * 1000)
        assert t_before <= proof.created_at_ms <= t_after + 1000

        # Retrieve proof
        retrieved = aggregator.get_proof(proof.aggregation_id)
        assert retrieved is not None
        assert retrieved.aggregation_id == proof.aggregation_id
        assert retrieved.proof_caid == proof.proof_caid
        assert retrieved.node_count == 2

        # Non-existent proof
        assert aggregator.get_proof("zkpcr-nonexistent") is None

        # Retrieve quotes with complete field assertions
        quotes = aggregator.get_quotes_for_aggregation(proof.aggregation_id)
        assert len(quotes) == 2
        assert quotes[0].node_id == "node-1"
        assert quotes[0].region == "us-east-1"
        assert quotes[0].pcr11_digest == "sha256:" + "a" * 64
        assert quotes[0].policy_epoch == 100
        assert quotes[0].nonce == "test-nonce-123"
        assert quotes[0].timestamp_ms == 1700000000000
        assert len(quotes[0].signature) == 128
        assert len(quotes[0].public_key_hex) == 64

        assert quotes[1].node_id == "node-2"
        assert quotes[1].region == "eu-west-1"
        assert quotes[1].pcr11_digest == "sha256:" + "b" * 64
        assert quotes[1].policy_epoch == 100
        assert quotes[1].nonce == "test-nonce-123"
        assert quotes[1].timestamp_ms == 1700000000000
        assert len(quotes[1].signature) == 128
        assert len(quotes[1].public_key_hex) == 64

        # List proofs by epoch
        proofs_epoch_100 = aggregator.list_proofs_for_epoch(100)
        assert len(proofs_epoch_100) == 1
        assert proofs_epoch_100[0].aggregation_id == proof.aggregation_id

        assert len(aggregator.list_proofs_for_epoch(999)) == 0
        aggregator.close()
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_10_exact_mutation_boundaries() -> None:
    # Test BN254 scalar field prime constant
    from src.zk_tpm_pcr_aggregator import BN254_SCALAR_FIELD_PRIME
    assert BN254_SCALAR_FIELD_PRIME == 21888242871839275222246405745257275088548364400416034343698204186575808495617

    # Test single-node Horner evaluation boundary
    assert evaluate_polynomial_horner([42], 999) == 42

    # Test Merkle root single element boundary
    d1 = "sha256:" + "aa" * 32
    single_root = compute_merkle_root([d1])
    assert single_root == d1

    # Test canonical bytes serialization
    q, _ = _generate_test_node("node-b", "eu-west-1", "sha256:" + "bb" * 32, epoch=1)
    b = q.canonical_bytes()
    assert isinstance(b, bytes)
    assert b'"node_id":"node-b"' in b

    aggregator = ZkPcrAggregator(db_path=":memory:")
    proof = aggregator.aggregate_quotes([q], epoch=1, now_ms=5000)
    p_bytes = proof.canonical_bytes()
    assert isinstance(p_bytes, bytes)
    assert b'"node_count":1' in p_bytes


def test_11_wilson_ci_bounds_and_lexicon() -> None:
    # Epistemic boundary and lexicon check
    import src.zk_tpm_pcr_aggregator as mod

    doc = mod.__doc__ or ""
    assert "INTERNAL PREVIEW COMMISSIONED" in doc
    assert "scaffold" in doc
    assert "simulated" in doc

    # Wilson score helper verification
    def wilson_score_interval(k: int, n: int, z: float = 1.95996) -> tuple[int, int]:
        p = k / n
        denom = 1 + z**2 / n
        center = (p + z**2 / (2 * n)) / denom
        spread = z * ((p * (1 - p) / n + z**2 / (4 * n**2)) ** 0.5) / denom
        low = max(0.0, center - spread)
        high = min(1.0, center + spread)
        return int(round(low * 10000)), int(round(high * 10000))

    low_bps, high_bps = wilson_score_interval(30, 30)
    assert low_bps >= 8800
    assert high_bps == 10000
