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
tests/test_scitt_proof_aggregation_reconciler.py
================================================================================
Verification Suite for ScittProofAggregationReconciler.

Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model.

Tests:
1. RFC 9162 domain-separated hashing and power-of-two helper primitives.
2. Single-leaf Merkle tree inclusion proof generation, boundary rejection, and verification.
3. Multi-leaf (balanced and unbalanced) Merkle tree inclusion proofs and invalid path lengths.
4. RFC 9162 Merkle consistency proof generation (power-of-2 and non-power-of-2) and append-only verification.
5. Consistency bounds validation and error raising.
6. Immutability of dataclass models and zero-float validation.
7. Regional Signed Tree Head (STH) ingestion and Ed25519 signature validation.
8. Federated super-root aggregation and deterministic CAID sealing.
9. SQLite-WAL file-backed persistence and durability across connection lifecycle.
"""

from __future__ import annotations

import base64
import dataclasses
import hashlib
import sqlite3
from pathlib import Path
from typing import Any, Dict

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs
from src.scitt_proof_aggregation_reconciler import (
    RegionalSthRecord,
    ScittAggregationReceipt,
    ScittInclusionProofRecord,
    ScittProofAggregationReconciler,
    build_consistency_proof,
    compute_sub_root,
    hash_leaf,
    hash_node,
    largest_power_of_two_less_than,
    sha256_jcs_caid,
    verify_consistency_proof,
    verify_inclusion_proof,
)


def _assert_zero_floats(obj: Any) -> None:
    """Recursively asserts that no float values exist in the object graph."""
    if isinstance(obj, float):
        raise AssertionError(f"Found float value: {obj}")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _assert_zero_floats(k)
            _assert_zero_floats(v)
    elif isinstance(obj, (list, tuple, set, frozenset)):
        for item in obj:
            _assert_zero_floats(item)


def test_rfc9162_primitives_and_hash_functions() -> None:
    """Evaluates RFC 9162 domain separation and power-of-two partitioning."""
    leaf = hash_leaf(b"test-entry")
    assert len(leaf) == 32
    assert leaf == hashlib.sha256(b"\x00test-entry").digest()

    node = hash_node(b"L" * 32, b"R" * 32)
    assert len(node) == 32
    assert node == hashlib.sha256(b"\x01" + b"L" * 32 + b"R" * 32).digest()

    assert largest_power_of_two_less_than(2) == 1
    assert largest_power_of_two_less_than(3) == 2
    assert largest_power_of_two_less_than(4) == 2
    assert largest_power_of_two_less_than(5) == 4
    assert largest_power_of_two_less_than(7) == 4
    assert largest_power_of_two_less_than(8) == 4
    assert largest_power_of_two_less_than(9) == 8

    with pytest.raises(ValueError, match="n must be >= 2"):
        largest_power_of_two_less_than(1)


def test_merkle_tree_single_leaf_inclusion() -> None:
    """Evaluates inclusion proof for a single-leaf tree per RFC 9162."""
    reconciler = ScittProofAggregationReconciler()
    idx = reconciler.append_raw_entry(b"single-event-receipt")
    assert idx == 0

    proof = reconciler.generate_inclusion_proof(0)
    assert isinstance(proof, ScittInclusionProofRecord)
    assert proof.leaf_index == 0
    assert proof.tree_size == 1
    assert len(proof.audit_path_hex) == 0

    leaf_bytes = bytes.fromhex(proof.leaf_hash_hex)
    root_bytes = bytes.fromhex(proof.root_hash_hex)
    audit_path = [bytes.fromhex(h) for h in proof.audit_path_hex]

    # Verification must succeed
    assert verify_inclusion_proof(leaf_bytes, 0, 1, audit_path, root_bytes) is True

    # Falsification: boundary checks (tree_size == 0 or leaf_index >= tree_size)
    assert verify_inclusion_proof(leaf_bytes, 0, 0, audit_path, root_bytes) is False
    assert verify_inclusion_proof(leaf_bytes, 1, 1, audit_path, root_bytes) is False

    # Falsification: tampered root
    fake_root = b"\xff" * 32
    assert verify_inclusion_proof(leaf_bytes, 0, 1, audit_path, fake_root) is False

    reconciler.close()


def test_merkle_tree_multi_leaf_inclusion_proofs() -> None:
    """Evaluates inclusion proofs across balanced (N=4) and unbalanced (N=5) trees."""
    reconciler = ScittProofAggregationReconciler()

    # Build 4 leaves
    for i in range(4):
        reconciler.append_raw_entry(f"event-{i}".encode("utf-8"))

    root_4 = reconciler.current_merkle_root()

    for i in range(4):
        proof = reconciler.generate_inclusion_proof(i)
        assert proof.leaf_index == i
        assert proof.tree_size == 4
        assert len(proof.audit_path_hex) == 2

        leaf_bytes = bytes.fromhex(proof.leaf_hash_hex)
        audit_path = [bytes.fromhex(h) for h in proof.audit_path_hex]
        assert verify_inclusion_proof(leaf_bytes, i, 4, audit_path, root_4) is True

        # Falsification: incorrect audit path length
        assert verify_inclusion_proof(leaf_bytes, i, 4, audit_path[:1], root_4) is False

    # Add 5th leaf (unbalanced tree)
    reconciler.append_raw_entry(b"event-4")
    root_5 = reconciler.current_merkle_root()
    assert root_5 != root_4

    for i in range(5):
        proof = reconciler.generate_inclusion_proof(i)
        assert proof.tree_size == 5
        leaf_bytes = bytes.fromhex(proof.leaf_hash_hex)
        audit_path = [bytes.fromhex(h) for h in proof.audit_path_hex]
        assert verify_inclusion_proof(leaf_bytes, i, 5, audit_path, root_5) is True

    # Out of bounds leaf index
    with pytest.raises(IndexError):
        reconciler.generate_inclusion_proof(5)

    reconciler.close()


def test_merkle_tree_consistency_proof() -> None:
    """Evaluates RFC 9162 append-only consistency proofs for power-of-2 and general sizes."""
    reconciler = ScittProofAggregationReconciler()

    # 1. Start with 2 entries (exact power of 2)
    reconciler.append_raw_entry(b"state-0")
    reconciler.append_raw_entry(b"state-1")
    root_2 = reconciler.current_merkle_root()

    # 2. Add 3rd entry (size 3)
    reconciler.append_raw_entry(b"state-2")
    root_3 = reconciler.current_merkle_root()

    # 3. Add 2 more entries (size 5)
    reconciler.append_raw_entry(b"state-3")
    reconciler.append_raw_entry(b"state-4")
    root_5 = reconciler.current_merkle_root()

    # Verify consistency from power of 2 (first_size = 2) to 5
    proof_2_to_5_hex = reconciler.generate_consistency_proof(2)
    proof_2_to_5 = [bytes.fromhex(h) for h in proof_2_to_5_hex]
    assert verify_consistency_proof(2, 5, root_2, root_5, proof_2_to_5) is True

    # Verify consistency from non-power-of-2 (first_size = 3) to 5
    proof_3_to_5_hex = reconciler.generate_consistency_proof(3)
    proof_3_to_5 = [bytes.fromhex(h) for h in proof_3_to_5_hex]
    assert verify_consistency_proof(3, 5, root_3, root_5, proof_3_to_5) is True

    # Verify consistency from minimal size 1 to 5 (kills m < 1 boundary mutant)
    root_1 = bytes.fromhex(reconciler.generate_inclusion_proof(0).leaf_hash_hex)
    proof_1_to_5_hex = reconciler.generate_consistency_proof(1)
    proof_1_to_5 = [bytes.fromhex(h) for h in proof_1_to_5_hex]
    assert verify_consistency_proof(1, 5, root_1, root_5, proof_1_to_5) is True

    # Verification between equal sizes
    assert verify_consistency_proof(3, 3, root_3, root_3, []) is True

    # Falsification: tampered second root
    assert verify_consistency_proof(3, 5, root_3, b"\x00" * 32, proof_3_to_5) is False

    # Falsification: invalid size bounds
    assert verify_consistency_proof(0, 5, root_3, root_5, proof_3_to_5) is False
    assert verify_consistency_proof(6, 5, root_3, root_5, proof_3_to_5) is False

    # 4. Add entries up to size 7
    reconciler.append_raw_entry(b"state-5")
    root_6 = reconciler.current_merkle_root()
    reconciler.append_raw_entry(b"state-6")
    root_7 = reconciler.current_merkle_root()

    # Verify consistency from (3, 7) - kills sn = second_size + 1 mutant
    proof_3_to_7_hex = reconciler.generate_consistency_proof(3)
    proof_3_to_7 = [bytes.fromhex(h) for h in proof_3_to_7_hex]
    assert verify_consistency_proof(3, 7, root_3, root_7, proof_3_to_7) is True

    # Verify consistency from (5, 6) - exercises inner loop boundary
    dummy_leaves_6 = [hash_leaf(f"state-{i}".encode("utf-8")) for i in range(6)]
    proof_5_to_6 = build_consistency_proof(5, 6, dummy_leaves_6)
    assert verify_consistency_proof(5, 6, compute_sub_root(dummy_leaves_6[:5]), root_6, proof_5_to_6) is True

    reconciler.close()


def test_consistency_bounds_error_handling() -> None:
    """Evaluates build_consistency_proof parameter boundary validations."""
    dummy_leaves = [hash_leaf(f"e-{i}".encode("utf-8")) for i in range(5)]

    # m < 1
    with pytest.raises(ValueError, match="Invalid consistency bounds"):
        build_consistency_proof(0, 5, dummy_leaves)

    # m > n
    with pytest.raises(ValueError, match="Invalid consistency bounds"):
        build_consistency_proof(6, 5, dummy_leaves)

    # n > len(leaves)
    with pytest.raises(ValueError, match="Invalid consistency bounds"):
        build_consistency_proof(3, 6, dummy_leaves)


def test_frozen_dataclasses_and_zero_floats() -> None:
    """Evaluates immutability and recursive zero-float conformance."""
    sth = RegionalSthRecord(
        region="us-east-1",
        tree_size=10,
        root_hash_hex="aa" * 32,
        signature_b64="c2ln",
        timestamp_epoch_ms=1760000000,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        sth.tree_size = 20  # type: ignore

    sth_dict = sth.to_dict()
    assert sth_dict["region"] == "us-east-1"
    _assert_zero_floats(sth_dict)

    receipt = ScittAggregationReceipt(
        receipt_caid="sha256:abc",
        super_root_caid="sha256:def",
        federated_merkle_root_hex="ff" * 32,
        participating_regions_count=3,
        total_leaves_witnessed=100,
        cluster_epoch_id=1,
        created_epoch_ms=1760000000,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        receipt.total_leaves_witnessed = 200  # type: ignore

    receipt_dict = receipt.to_dict()
    assert receipt_dict["participating_regions_count"] == 3
    _assert_zero_floats(receipt_dict)


def test_regional_sth_ingestion_and_ed25519_verification() -> None:
    """Evaluates regional STH signature verification over RFC 8785 canonical bytes."""
    reconciler = ScittProofAggregationReconciler()

    key = ed25519.Ed25519PrivateKey.generate()
    pubkey = key.public_key()

    unsigned_body = {
        "region": "eu-west-1",
        "root_hash_hex": "11" * 32,
        "timestamp_epoch_ms": 1760000000,
        "tree_size": 42,
    }
    canonical = encode_jcs(unsigned_body)
    sig_b64 = base64.b64encode(key.sign(canonical)).decode("ascii")

    record = RegionalSthRecord(
        region="eu-west-1",
        tree_size=42,
        root_hash_hex="11" * 32,
        signature_b64=sig_b64,
        timestamp_epoch_ms=1760000000,
    )

    # Valid ingestion
    assert reconciler.ingest_regional_sth(record, public_key=pubkey) is True
    assert "eu-west-1" in reconciler.regional_sths

    # Tampered signature
    tampered_record = RegionalSthRecord(
        region="eu-west-1",
        tree_size=42,
        root_hash_hex="22" * 32,  # altered root
        signature_b64=sig_b64,
        timestamp_epoch_ms=1760000000,
    )
    with pytest.raises(ValueError, match="ERR_INVALID_REGIONAL_STH_SIGNATURE"):
        reconciler.ingest_regional_sth(tampered_record, public_key=pubkey)

    reconciler.close()


def test_federated_super_root_aggregation() -> None:
    """Evaluates cross-region STH aggregation into a deterministic Super-Root."""
    reconciler = ScittProofAggregationReconciler(cluster_epoch_id=1)

    # Ingest 3 regional STHs
    r1 = RegionalSthRecord("us-east-1", 100, "11" * 32, "sig1", 1760000000)
    r2 = RegionalSthRecord("eu-west-1", 150, "22" * 32, "sig2", 1760000000)
    r3 = RegionalSthRecord("ap-northeast-1", 75, "33" * 32, "sig3", 1760000000)

    reconciler.ingest_regional_sth(r1)
    reconciler.ingest_regional_sth(r2)
    reconciler.ingest_regional_sth(r3)

    receipt = reconciler.aggregate_federated_super_root()
    assert isinstance(receipt, ScittAggregationReceipt)
    assert receipt.receipt_caid.startswith("sha256:")
    assert receipt.super_root_caid.startswith("sha256:")
    assert receipt.participating_regions_count == 3
    assert receipt.total_leaves_witnessed == 325  # 100 + 150 + 75
    assert receipt.cluster_epoch_id == 1

    # Empty aggregator raises RuntimeError
    empty_reconciler = ScittProofAggregationReconciler()
    with pytest.raises(RuntimeError, match="ERR_NO_REGIONAL_STHS"):
        empty_reconciler.aggregate_federated_super_root()

    reconciler.close()
    empty_reconciler.close()


def test_sqlite_wal_file_backed_persistence(tmp_path: Path) -> None:
    """Evaluates file-backed SQLite-WAL ledger initialization, persistence, and recovery."""
    db_file = tmp_path / "scitt_test.db"

    reconciler = ScittProofAggregationReconciler(
        cluster_epoch_id=2,
        db_path=str(db_file),
    )

    # Verify WAL journal mode
    cursor = reconciler._conn.execute("PRAGMA journal_mode;")
    mode = cursor.fetchone()[0]
    assert mode.lower() == "wal"

    r1 = RegionalSthRecord("us-east-1", 50, "aa" * 32, "sig_wal", 1760000100)
    reconciler.ingest_regional_sth(r1)
    receipt = reconciler.aggregate_federated_super_root()

    # Multi-threaded access verifying check_same_thread=False
    import threading
    t_results: list[int] = []

    def query_from_thread() -> None:
        c = reconciler._conn.cursor()
        c.execute("SELECT count(*) FROM regional_sth_ledger;")
        t_results.append(c.fetchone()[0])

    t = threading.Thread(target=query_from_thread)
    t.start()
    t.join()
    assert len(t_results) == 1
    assert t_results[0] == 1

    reconciler.close()

    # Reopen database directly and verify ledger state
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()

    cur.execute("SELECT region, tree_size, root_hash_hex FROM regional_sth_ledger;")
    row = cur.fetchone()
    assert row[0] == "us-east-1"
    assert row[1] == 50
    assert row[2] == "aa" * 32

    cur.execute("SELECT receipt_caid, participating_regions_count, total_leaves_witnessed FROM scitt_aggregation_ledger;")
    r_row = cur.fetchone()
    assert r_row[0] == receipt.receipt_caid
    assert r_row[1] == 1
    assert r_row[2] == 50

    conn.close()
