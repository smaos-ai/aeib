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
tests/test_zk_scitt_proof_rollup.py
================================================================================
Verification Suite for ZkScittProofRollupEngine and ZkScittProofRollupReceipt.

Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model.

Tests:
1. BN254 scalar field arithmetic and hash-to-scalar range verification.
2. Polynomial commitment generation (odd and even degree) and challenge evaluation.
3. Nominal proof rollup generation across multi-region leaves.
4. Cryptographic verification of valid rollup transcripts.
5. Rejection of tampered polynomial commitments and evaluation scalars.
6. Rejection of tampered CAID and mismatched leaf lists.
7. Fail-closed rejection on empty batches, stale epochs, and non-monotonic advances.
8. SQLite-WAL persistence and leaf ledger durability.
9. Dataclass immutability and exhaustive parameter validation.
10. Default timestamp and monotonic identifier generation.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
import sqlite3
import time
from typing import Any, Dict, List

import pytest

from src.zk_scitt_proof_rollup import (
    BN254_SCALAR_FIELD_PRIME,
    HALT_ZK_ROLLUP_EMPTY_BATCH,
    HALT_ZK_ROLLUP_STALE_EPOCH,
    STATUS_ROLLUP_INVALID,
    STATUS_ROLLUP_VERIFIED,
    ScittRollupLeafRecord,
    ZkScittProofRollupEngine,
    ZkScittProofRollupReceipt,
    compute_sha256_caid,
    hash_to_bn254_scalar,
)


@pytest.fixture
def temp_db(tmp_path: Path) -> str:
    db_file = tmp_path / "test_zk_scitt_rollup.db"
    return str(db_file)


@pytest.fixture
def sample_leaves() -> List[ScittRollupLeafRecord]:
    """Sets up sample leaves across us-east-1, eu-west-1, and ap-northeast-1."""
    return [
        ScittRollupLeafRecord(0, "sha256:" + "a" * 64, "us-east-1", 100),
        ScittRollupLeafRecord(1, "sha256:" + "b" * 64, "us-east-1", 100),
        ScittRollupLeafRecord(0, "sha256:" + "c" * 64, "eu-west-1", 50),
        ScittRollupLeafRecord(1, "sha256:" + "d" * 64, "eu-west-1", 50),
        ScittRollupLeafRecord(0, "sha256:" + "e" * 64, "ap-northeast-1", 80),
    ]


@pytest.fixture
def sample_sth_roots() -> Dict[str, str]:
    return {
        "us-east-1": "sha256:" + "1" * 64,
        "eu-west-1": "sha256:" + "2" * 64,
        "ap-northeast-1": "sha256:" + "3" * 64,
    }


def test_01_bn254_scalar_field_and_hashing() -> None:
    """Verifies BN254 scalar field prime constant and deterministic hash-to-scalar mapping."""
    assert BN254_SCALAR_FIELD_PRIME == 21888242871839275222246405745257275088548364400416034343698204186575808495617

    s1 = hash_to_bn254_scalar(b"sample_leaf_1")
    s2 = hash_to_bn254_scalar(b"sample_leaf_2")
    assert 0 <= s1 < BN254_SCALAR_FIELD_PRIME
    assert 0 <= s2 < BN254_SCALAR_FIELD_PRIME
    assert s1 != s2

    # Determinism
    assert hash_to_bn254_scalar(b"sample_leaf_1") == s1


def test_02_polynomial_commitment_and_evaluation() -> None:
    """Verifies polynomial commitment for even and odd counts and challenge evaluation."""
    engine = ZkScittProofRollupEngine(current_cluster_epoch_id=1)

    scalars_odd = [10, 20, 30]
    c_hex_odd, w_odd = engine.compute_zk_polynomial_commitment(scalars_odd)
    assert len(c_hex_odd) == 64
    assert 0 <= w_odd < BN254_SCALAR_FIELD_PRIME
    # (-1)^3 * (10*20*30) = -6000 mod r
    expected_w_odd = (BN254_SCALAR_FIELD_PRIME - 6000) % BN254_SCALAR_FIELD_PRIME
    assert w_odd == expected_w_odd

    scalars_even = [10, 20]
    c_hex_even, w_even = engine.compute_zk_polynomial_commitment(scalars_even)
    assert len(c_hex_even) == 64
    # (-1)^2 * (10*20) = 200 mod r
    assert w_even == 200

    # Evaluate at challenge = 50
    # (50 - 10)*(50 - 20)*(50 - 30) = 40 * 30 * 20 = 24000
    val = engine.evaluate_polynomial_at_challenge(scalars_odd, 50)
    assert val == 24000


def test_03_nominal_rollup_generation(
    sample_leaves: List[ScittRollupLeafRecord],
    sample_sth_roots: Dict[str, str],
    temp_db: str,
) -> None:
    """Verifies nominal generation of ZK SCITT proof rollup receipt."""
    engine = ZkScittProofRollupEngine(current_cluster_epoch_id=1, db_path=temp_db)
    super_root_hex = "0" * 64

    receipt = engine.generate_proof_rollup(
        leaves=sample_leaves,
        regional_sth_roots=sample_sth_roots,
        federated_super_root_hex=super_root_hex,
        cluster_epoch_id=1,
        creation_time_ms=1700000000000,
    )

    assert isinstance(receipt, ZkScittProofRollupReceipt)
    assert receipt.rollup_id.startswith("zk-scitt-rollup-ep1-")
    assert receipt.cluster_epoch_id == 1
    assert receipt.total_leaves_aggregated == len(sample_leaves)
    assert receipt.federated_super_root_hex == super_root_hex
    assert len(receipt.zk_commitment_hex) == 64
    assert 0 <= receipt.fiat_shamir_challenge_scalar < BN254_SCALAR_FIELD_PRIME
    assert 0 <= receipt.zk_evaluation_scalar < BN254_SCALAR_FIELD_PRIME
    assert receipt.status == STATUS_ROLLUP_VERIFIED
    assert receipt.sealed_at_epoch_ms == 1700000000000
    assert receipt.rollup_caid.startswith("sha256:")
    engine.close()


def test_04_verification_positive_and_tampered_transcripts(
    sample_leaves: List[ScittRollupLeafRecord],
    sample_sth_roots: Dict[str, str],
) -> None:
    """Verifies that legitimate rollups pass and any tampered field fails closed."""
    engine = ZkScittProofRollupEngine(current_cluster_epoch_id=1)
    super_root_hex = "f" * 64

    receipt = engine.generate_proof_rollup(sample_leaves, sample_sth_roots, super_root_hex, 1, 1700000000000)

    # 1. Nominal verification passes
    assert engine.verify_proof_rollup(receipt, sample_leaves) is True

    # 2. Tampered leaves list
    tampered_leaves = list(sample_leaves)
    tampered_leaves[0] = ScittRollupLeafRecord(0, "sha256:" + "9" * 64, "us-east-1", 100)
    assert engine.verify_proof_rollup(receipt, tampered_leaves) is False

    # 3. Mismatched leaves count
    assert engine.verify_proof_rollup(receipt, sample_leaves[:3]) is False

    # 4. Empty leaves list
    assert engine.verify_proof_rollup(receipt, []) is False

    # 5. Tampered commitment hex
    bad_receipt_c = dataclasses.replace(receipt, zk_commitment_hex="e" * 64)
    assert engine.verify_proof_rollup(bad_receipt_c, sample_leaves) is False

    # 6. Tampered challenge scalar
    bad_receipt_chal = dataclasses.replace(receipt, fiat_shamir_challenge_scalar=12345)
    assert engine.verify_proof_rollup(bad_receipt_chal, sample_leaves) is False

    # 7. Tampered evaluation scalar
    bad_receipt_eval = dataclasses.replace(receipt, zk_evaluation_scalar=99999)
    assert engine.verify_proof_rollup(bad_receipt_eval, sample_leaves) is False

    # 8. Tampered CAID
    bad_receipt_caid = dataclasses.replace(receipt, rollup_caid="sha256:" + "0" * 64)
    assert engine.verify_proof_rollup(bad_receipt_caid, sample_leaves) is False


def test_05_falsification_and_error_handling(sample_leaves: List[ScittRollupLeafRecord], sample_sth_roots: Dict[str, str]) -> None:
    """Verifies fail-closed halts on invalid generation parameters."""
    engine = ZkScittProofRollupEngine(current_cluster_epoch_id=5)

    # Empty leaves batch
    with pytest.raises(ValueError, match=HALT_ZK_ROLLUP_EMPTY_BATCH):
        engine.generate_proof_rollup([], sample_sth_roots, "0" * 64, 5)

    # Empty regional roots
    with pytest.raises(ValueError, match="ERR_EMPTY_REGIONAL_STH_ROOTS"):
        engine.generate_proof_rollup(sample_leaves, {}, "0" * 64, 5)

    # Invalid super root length
    with pytest.raises(ValueError, match="ERR_INVALID_SUPER_ROOT_HEX"):
        engine.generate_proof_rollup(sample_leaves, sample_sth_roots, "short", 5)
    assert engine._total_rollups_generated == 0

    # Stale epoch
    with pytest.raises(ValueError, match=HALT_ZK_ROLLUP_STALE_EPOCH):
        engine.generate_proof_rollup(sample_leaves, sample_sth_roots, "0" * 64, 4)

    # Non-monotonic epoch advance
    with pytest.raises(ValueError, match="ERR_NON_MONOTONIC_EPOCH"):
        engine.advance_cluster_epoch(5)
    with pytest.raises(ValueError, match="ERR_NON_MONOTONIC_EPOCH"):
        engine.advance_cluster_epoch(4)

    engine.advance_cluster_epoch(6)
    assert engine.current_cluster_epoch_id == 6


def test_06_sqlite_wal_persistence_and_durability(
    sample_leaves: List[ScittRollupLeafRecord],
    sample_sth_roots: Dict[str, str],
    temp_db: str,
) -> None:
    """Verifies that rollups and leaves are persisted in SQLite-WAL across connection lifecycle."""
    engine = ZkScittProofRollupEngine(current_cluster_epoch_id=1, db_path=temp_db)
    receipt = engine.generate_proof_rollup(sample_leaves, sample_sth_roots, "0" * 64, 1, 1700000000000)
    engine.close()

    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute(
        "SELECT rollup_id, cluster_epoch_id, total_leaves_aggregated, status FROM zk_scitt_rollups_ledger WHERE rollup_id = ?",
        (receipt.rollup_id,),
    )
    row = cur.fetchone()
    assert row is not None
    assert row[0] == receipt.rollup_id
    assert row[1] == 1
    assert row[2] == len(sample_leaves)
    assert row[3] == STATUS_ROLLUP_VERIFIED

    cur.execute("SELECT COUNT(*) FROM zk_scitt_rollup_leaves_ledger WHERE rollup_id = ?", (receipt.rollup_id,))
    assert cur.fetchone()[0] == len(sample_leaves)
    conn.close()


def test_07_leaf_record_validations() -> None:
    """Verifies parameter bounds and validation on ScittRollupLeafRecord."""
    with pytest.raises(ValueError, match="ERR_INVALID_LEAF_INDEX"):
        ScittRollupLeafRecord(-1, "sha256:" + "0" * 64, "us-east-1", 100)
    with pytest.raises(ValueError, match="ERR_INVALID_LEAF_INDEX"):
        ScittRollupLeafRecord(1.5, "sha256:" + "0" * 64, "us-east-1", 100)  # type: ignore

    with pytest.raises(ValueError, match="ERR_INVALID_LEAF_CAID"):
        ScittRollupLeafRecord(0, "not_sha256", "us-east-1", 100)

    with pytest.raises(ValueError, match="ERR_INVALID_REGION_ID"):
        ScittRollupLeafRecord(0, "sha256:" + "0" * 64, "", 100)
    with pytest.raises(ValueError, match="ERR_INVALID_REGION_ID"):
        ScittRollupLeafRecord(0, "sha256:" + "0" * 64, "   ", 100)

    with pytest.raises(ValueError, match="ERR_INVALID_TREE_SIZE"):
        ScittRollupLeafRecord(5, "sha256:" + "0" * 64, "us-east-1", 5)
    with pytest.raises(ValueError, match="ERR_INVALID_TREE_SIZE"):
        ScittRollupLeafRecord(5, "sha256:" + "0" * 64, "us-east-1", 4)
    with pytest.raises(ValueError, match="ERR_INVALID_TREE_SIZE"):
        ScittRollupLeafRecord(5, "sha256:" + "0" * 64, "us-east-1", 5.5)  # type: ignore


def test_08_receipt_validations() -> None:
    """Verifies parameter bounds and frozen immutability of ZkScittProofRollupReceipt."""
    valid_args: Dict[str, Any] = {
        "rollup_id": "r1",
        "cluster_epoch_id": 1,
        "total_leaves_aggregated": 5,
        "regional_sth_roots": {"us-east-1": "root1"},
        "federated_super_root_hex": "0" * 64,
        "zk_commitment_hex": "0" * 64,
        "fiat_shamir_challenge_scalar": 12345,
        "zk_evaluation_scalar": 67890,
        "status": STATUS_ROLLUP_VERIFIED,
        "sealed_at_epoch_ms": 1700000000000,
        "rollup_caid": "sha256:" + "0" * 64,
    }

    receipt = ZkScittProofRollupReceipt(**valid_args)
    assert receipt.rollup_id == "r1"

    # Exact boundary validations (kills boundary perturbation mutants)
    receipt_leaf_1 = ZkScittProofRollupReceipt(**dict(valid_args, total_leaves_aggregated=1))
    assert receipt_leaf_1.total_leaves_aggregated == 1

    receipt_eval_0 = ZkScittProofRollupReceipt(**dict(valid_args, zk_evaluation_scalar=0))
    assert receipt_eval_0.zk_evaluation_scalar == 0

    receipt_chal_0 = ZkScittProofRollupReceipt(**dict(valid_args, fiat_shamir_challenge_scalar=0))
    assert receipt_chal_0.fiat_shamir_challenge_scalar == 0

    receipt_epoch_1 = ZkScittProofRollupReceipt(**dict(valid_args, cluster_epoch_id=1))
    assert receipt_epoch_1.cluster_epoch_id == 1

    receipt_ms_1 = ZkScittProofRollupReceipt(**dict(valid_args, sealed_at_epoch_ms=1))
    assert receipt_ms_1.sealed_at_epoch_ms == 1

    with pytest.raises(dataclasses.FrozenInstanceError):
        receipt.status = "MUTATED"  # type: ignore

    with pytest.raises(ValueError, match="ERR_INVALID_ROLLUP_ID"):
        ZkScittProofRollupReceipt(**dict(valid_args, rollup_id=""))
    with pytest.raises(ValueError, match="ERR_INVALID_CLUSTER_EPOCH_ID"):
        ZkScittProofRollupReceipt(**dict(valid_args, cluster_epoch_id=0))
    with pytest.raises(ValueError, match="ERR_INVALID_CLUSTER_EPOCH_ID"):
        ZkScittProofRollupReceipt(**dict(valid_args, cluster_epoch_id=1.5))
    with pytest.raises(ValueError, match="ERR_INVALID_TOTAL_LEAVES"):
        ZkScittProofRollupReceipt(**dict(valid_args, total_leaves_aggregated=0))
    with pytest.raises(ValueError, match="ERR_INVALID_REGIONAL_STH_ROOTS"):
        ZkScittProofRollupReceipt(**dict(valid_args, regional_sth_roots={}))
    with pytest.raises(ValueError, match="ERR_INVALID_SUPER_ROOT_HEX"):
        ZkScittProofRollupReceipt(**dict(valid_args, federated_super_root_hex="short"))
    with pytest.raises(ValueError, match="ERR_INVALID_ZK_COMMITMENT_HEX"):
        ZkScittProofRollupReceipt(**dict(valid_args, zk_commitment_hex="short"))
    with pytest.raises(ValueError, match="ERR_INVALID_CHALLENGE_SCALAR"):
        ZkScittProofRollupReceipt(**dict(valid_args, fiat_shamir_challenge_scalar=-1))
    with pytest.raises(ValueError, match="ERR_INVALID_CHALLENGE_SCALAR"):
        ZkScittProofRollupReceipt(**dict(valid_args, fiat_shamir_challenge_scalar=BN254_SCALAR_FIELD_PRIME))
    with pytest.raises(ValueError, match="ERR_INVALID_EVALUATION_SCALAR"):
        ZkScittProofRollupReceipt(**dict(valid_args, zk_evaluation_scalar=-1))
    with pytest.raises(ValueError, match="ERR_INVALID_EVALUATION_SCALAR"):
        ZkScittProofRollupReceipt(**dict(valid_args, zk_evaluation_scalar=BN254_SCALAR_FIELD_PRIME))
    with pytest.raises(ValueError, match="ERR_INVALID_STATUS"):
        ZkScittProofRollupReceipt(**dict(valid_args, status="UNKNOWN"))
    with pytest.raises(ValueError, match="ERR_INVALID_SEALED_AT_EPOCH_MS"):
        ZkScittProofRollupReceipt(**dict(valid_args, sealed_at_epoch_ms=0))
    with pytest.raises(ValueError, match="ERR_INVALID_SEALED_AT_EPOCH_MS"):
        ZkScittProofRollupReceipt(**dict(valid_args, sealed_at_epoch_ms=100.5))
    with pytest.raises(ValueError, match="ERR_INVALID_ROLLUP_CAID"):
        ZkScittProofRollupReceipt(**dict(valid_args, rollup_caid="bad_caid"))


def test_09_default_timestamp_generation(sample_leaves: List[ScittRollupLeafRecord], sample_sth_roots: Dict[str, str]) -> None:
    """Verifies that omiting creation_time_ms generates a valid current timestamp."""
    engine = ZkScittProofRollupEngine(current_cluster_epoch_id=1)
    now = int(time.time() * 1000)
    receipt = engine.generate_proof_rollup(sample_leaves, sample_sth_roots, "0" * 64, 1)
    assert receipt.sealed_at_epoch_ms >= now - 1000
    assert receipt.sealed_at_epoch_ms <= now + 10000

    with pytest.raises(ValueError, match="ERR_INVALID_CLUSTER_EPOCH_ID"):
        ZkScittProofRollupEngine(current_cluster_epoch_id=0)
