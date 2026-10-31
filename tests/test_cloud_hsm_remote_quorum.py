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
tests/test_cloud_hsm_remote_quorum.py
================================================================================
Verification Suite for CloudHsmRemoteQuorumCoordinator and CloudHsmEnclaveNode.

Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model.

Tests:
1. Node initialization, algorithm enforcement (Ed25519 & ECDSA P-256), and PEM generation.
2. Share generation and cryptographic verification across heterogeneous algorithms.
3. Threshold quorum evaluation: 3-of-5 quorum established with valid shares.
4. Quorum failure on insufficient shares (e.g. 2 of 3 required).
5. Tampered share payload and invalid signature rejection fail-closed.
6. Replay protection: nonce reuse blocked across evaluations.
7. Deduplication of multiple shares submitted by the same node in a batch.
8. Suspended node share rejection.
9. Cluster epoch fencing and stale epoch rejection.
10. Non-monotonic cluster epoch advance rejection.
11. SQLite-WAL ledger durability and retrieval across connection close.
12. Quorum certificate export, CAID integrity, and tampering verification.
13. Dataclass immutability and zero-float validation.
"""

from __future__ import annotations

import base64
import dataclasses
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519

from src.cloud_hsm_remote_quorum import (
    QUORUM_STATUS_ESTABLISHED,
    QUORUM_STATUS_FAILED_INSUFFICIENT_SHARES,
    STATUS_ACTIVE,
    STATUS_SUSPENDED,
    SUPPORTED_ALGORITHMS,
    SUPPORTED_PROVIDERS,
    CloudHsmEnclaveNode,
    CloudHsmRemoteQuorumCoordinator,
    HsmNodeRecord,
    QuorumAuthorizationReceipt,
    QuorumShareReceipt,
    compute_sha256_caid,
)


@pytest.fixture
def temp_db(tmp_path: Path) -> str:
    db_file = tmp_path / "test_hsm_quorum.db"
    return str(db_file)


@pytest.fixture
def standard_nodes() -> List[CloudHsmEnclaveNode]:
    """Sets up 5 heterogeneous HSM participant nodes across cloud providers."""
    return [
        CloudHsmEnclaveNode("node-aws-kms", "AWS_KMS", "ED25519"),
        CloudHsmEnclaveNode("node-gcp-kms", "GCP_CLOUD_KMS", "ECDSA_P256_SHA256"),
        CloudHsmEnclaveNode("node-azure-kv", "AZURE_KEY_VAULT", "ED25519"),
        CloudHsmEnclaveNode("node-softhsm", "SOFTHSM_PKCS11", "ECDSA_P256_SHA256"),
        CloudHsmEnclaveNode("node-apple-se", "APPLE_SECURE_ENCLAVE", "ECDSA_P256_SHA256"),
    ]


def test_01_node_initialization_and_algorithms(standard_nodes: List[CloudHsmEnclaveNode]) -> None:
    """Verifies node instantiation, supported providers, algorithms, and PEM export."""
    assert len(standard_nodes) == 5
    assert SUPPORTED_ALGORITHMS == {"ED25519", "ECDSA_P256_SHA256"}
    assert "AWS_KMS" in SUPPORTED_PROVIDERS

    for node in standard_nodes:
        assert node.node_id.startswith("node-")
        assert "BEGIN PUBLIC KEY" in node.public_key_pem
        rec = node.to_record(registered_at_epoch_ms=1700000000000)
        assert rec.status == STATUS_ACTIVE
        assert rec.registered_at_epoch_ms == 1700000000000

    # Invalid node inputs
    with pytest.raises(ValueError, match="ERR_INVALID_NODE_ID"):
        CloudHsmEnclaveNode("")
    with pytest.raises(ValueError, match="ERR_UNSUPPORTED_PROVIDER"):
        CloudHsmEnclaveNode("node-bad", "UNKNOWN_CLOUD", "ED25519")
    with pytest.raises(ValueError, match="ERR_UNSUPPORTED_ALGORITHM"):
        CloudHsmEnclaveNode("node-bad", "AWS_KMS", "RSA_2048")


def test_02_share_generation_and_signature_verification(standard_nodes: List[CloudHsmEnclaveNode]) -> None:
    """Verifies cryptographic share generation and signature validation for Ed25519 and ECDSA."""
    coordinator = CloudHsmRemoteQuorumCoordinator(threshold_m=3, current_cluster_epoch_id=1)
    for node in standard_nodes:
        coordinator.register_node_record(node.to_record(1700000000000))

    action_type = "SCITT_SUPER_ROOT_COMMIT"
    payload = {"super_root": "0x1234abcd", "leaf_count": 42}
    digest_hex = compute_sha256_caid(payload).split("sha256:")[1]

    for node in standard_nodes:
        share = node.sign_share(
            action_type=action_type,
            payload_digest_hex=digest_hex,
            cluster_epoch_id=1,
            signed_at_epoch_ms=1700000001000,
        )
        assert share.node_id == node.node_id
        assert share.key_algorithm == node.key_algorithm
        assert coordinator.verify_share_signature(share, action_type, digest_hex, 1) is True


def test_03_threshold_quorum_established(standard_nodes: List[CloudHsmEnclaveNode], temp_db: str) -> None:
    """Verifies that submitting 3 valid shares out of 5 establishes quorum (3-of-5)."""
    coordinator = CloudHsmRemoteQuorumCoordinator(threshold_m=3, current_cluster_epoch_id=1, db_path=temp_db)
    for node in standard_nodes:
        coordinator.register_node_record(node.to_record(1700000000000))

    action_type = "SCITT_SUPER_ROOT_COMMIT"
    payload = {"super_root_caid": "sha256:6f58cffa", "round": 10}
    digest_hex = compute_sha256_caid(payload).split("sha256:")[1]

    # Collect 3 shares
    shares = [
        standard_nodes[0].sign_share(action_type, digest_hex, 1, nonce="n1", signed_at_epoch_ms=1700000001000),
        standard_nodes[1].sign_share(action_type, digest_hex, 1, nonce="n2", signed_at_epoch_ms=1700000001000),
        standard_nodes[2].sign_share(action_type, digest_hex, 1, nonce="n3", signed_at_epoch_ms=1700000001000),
    ]

    receipt = coordinator.evaluate_quorum(
        action_type=action_type,
        payload=payload,
        shares=shares,
        cluster_epoch_id=1,
        evaluation_time_ms=1700000002000,
    )

    assert receipt.quorum_status == QUORUM_STATUS_ESTABLISHED
    assert receipt.valid_shares_count == 3
    assert receipt.required_threshold_m == 3
    assert receipt.total_participants_n == 5
    assert len(receipt.participating_node_ids) == 3
    assert receipt.receipt_caid.startswith("sha256:")
    coordinator.close()


def test_04_quorum_insufficient_shares_fails_closed(standard_nodes: List[CloudHsmEnclaveNode]) -> None:
    """Verifies that submitting fewer shares than required fails closed."""
    coordinator = CloudHsmRemoteQuorumCoordinator(threshold_m=3, current_cluster_epoch_id=1)
    for node in standard_nodes:
        coordinator.register_node_record(node.to_record(1700000000000))

    action_type = "FAILOVER_PRIMARY_PROMOTION"
    payload = {"new_primary": "gcp-europe-west3"}
    digest_hex = compute_sha256_caid(payload).split("sha256:")[1]

    # Only 2 shares provided (threshold is 3)
    shares = [
        standard_nodes[0].sign_share(action_type, digest_hex, 1, nonce="m1"),
        standard_nodes[1].sign_share(action_type, digest_hex, 1, nonce="m2"),
    ]

    receipt = coordinator.evaluate_quorum(action_type, payload, shares)
    assert receipt.quorum_status == QUORUM_STATUS_FAILED_INSUFFICIENT_SHARES
    assert receipt.valid_shares_count == 2
    assert receipt.required_threshold_m == 3


def test_05_tampered_payload_and_corrupt_signature_rejected(standard_nodes: List[CloudHsmEnclaveNode]) -> None:
    """Verifies that tampered payloads and forged signatures are rejected."""
    coordinator = CloudHsmRemoteQuorumCoordinator(threshold_m=3, current_cluster_epoch_id=1)
    for node in standard_nodes:
        coordinator.register_node_record(node.to_record(1700000000000))

    action_type = "EMERGENCY_LINE_STOP_RESET"
    payload = {"reason": "Authorized line stop reset"}
    digest_hex = compute_sha256_caid(payload).split("sha256:")[1]

    share_valid = standard_nodes[0].sign_share(action_type, digest_hex, 1, nonce="t1")

    # 1. Tampered action_type in verify_share_signature
    assert coordinator.verify_share_signature(share_valid, "OTHER_ACTION", digest_hex, 1) is False

    # 2. Tampered digest_hex
    assert coordinator.verify_share_signature(share_valid, action_type, "a" * 64, 1) is False

    # 3. Tampered epoch
    assert coordinator.verify_share_signature(share_valid, action_type, digest_hex, 2) is False

    # 4. Corrupted signature bytes
    corrupt_sig_b64 = base64.b64encode(b"corrupt_signature_bytes_00000000").decode("ascii")
    corrupt_share = QuorumShareReceipt(
        share_id=share_valid.share_id,
        node_id=share_valid.node_id,
        key_algorithm=share_valid.key_algorithm,
        public_key_pem=share_valid.public_key_pem,
        signature_b64=corrupt_sig_b64,
        share_payload=share_valid.share_payload,
    )
    assert coordinator.verify_share_signature(corrupt_share, action_type, digest_hex, 1) is False


def test_06_nonce_replay_protection(standard_nodes: List[CloudHsmEnclaveNode]) -> None:
    """Verifies that an identical share nonce cannot be re-used across evaluations."""
    coordinator = CloudHsmRemoteQuorumCoordinator(threshold_m=2, current_cluster_epoch_id=1)
    for node in standard_nodes[:3]:
        coordinator.register_node_record(node.to_record(1700000000000))

    action_type = "SCITT_SUPER_ROOT_COMMIT"
    payload = {"commit_id": 1}
    digest_hex = compute_sha256_caid(payload).split("sha256:")[1]

    fixed_nonce = "fixed-nonce-12345"
    share1 = standard_nodes[0].sign_share(action_type, digest_hex, 1, nonce=fixed_nonce)
    share2 = standard_nodes[1].sign_share(action_type, digest_hex, 1, nonce="other-nonce-1")

    # First evaluation succeeds
    receipt1 = coordinator.evaluate_quorum(action_type, payload, [share1, share2])
    assert receipt1.quorum_status == QUORUM_STATUS_ESTABLISHED
    assert receipt1.valid_shares_count == 2

    # Second evaluation attempting to reuse share1 (with fixed_nonce)
    share3 = standard_nodes[2].sign_share(action_type, digest_hex, 1, nonce="other-nonce-2")
    receipt2 = coordinator.evaluate_quorum(action_type, payload, [share1, share3])
    # share1 is discarded because nonce was already seen, leaving only 1 valid share
    assert receipt2.quorum_status == QUORUM_STATUS_FAILED_INSUFFICIENT_SHARES
    assert receipt2.valid_shares_count == 1


def test_07_batch_deduplication_of_node_shares(standard_nodes: List[CloudHsmEnclaveNode]) -> None:
    """Verifies that submitting multiple shares from the same node only counts as one vote."""
    coordinator = CloudHsmRemoteQuorumCoordinator(threshold_m=3, current_cluster_epoch_id=1)
    for node in standard_nodes:
        coordinator.register_node_record(node.to_record(1700000000000))

    action_type = "SCITT_SUPER_ROOT_COMMIT"
    payload = {"data": "test"}
    digest_hex = compute_sha256_caid(payload).split("sha256:")[1]

    # Node 0 submits two distinct shares (with different nonces)
    share_0a = standard_nodes[0].sign_share(action_type, digest_hex, 1, nonce="node0-a")
    share_0b = standard_nodes[0].sign_share(action_type, digest_hex, 1, nonce="node0-b")
    share_1 = standard_nodes[1].sign_share(action_type, digest_hex, 1, nonce="node1-a")

    receipt = coordinator.evaluate_quorum(action_type, payload, [share_0a, share_0b, share_1])
    # Total distinct nodes is 2, so threshold of 3 is not met
    assert receipt.quorum_status == QUORUM_STATUS_FAILED_INSUFFICIENT_SHARES
    assert receipt.valid_shares_count == 2


def test_08_suspended_node_shares_rejected(standard_nodes: List[CloudHsmEnclaveNode]) -> None:
    """Verifies that suspending a node causes its shares to be rejected."""
    coordinator = CloudHsmRemoteQuorumCoordinator(threshold_m=3, current_cluster_epoch_id=1)
    for node in standard_nodes:
        coordinator.register_node_record(node.to_record(1700000000000))

    action_type = "SCITT_SUPER_ROOT_COMMIT"
    payload = {"epoch": 1}
    digest_hex = compute_sha256_caid(payload).split("sha256:")[1]

    # Suspend node 0
    coordinator.suspend_node("node-aws-kms")

    shares = [
        standard_nodes[0].sign_share(action_type, digest_hex, 1, nonce="s0"),
        standard_nodes[1].sign_share(action_type, digest_hex, 1, nonce="s1"),
        standard_nodes[2].sign_share(action_type, digest_hex, 1, nonce="s2"),
    ]

    receipt = coordinator.evaluate_quorum(action_type, payload, shares)
    # node-aws-kms is suspended, so only 2 shares are accepted
    assert receipt.quorum_status == QUORUM_STATUS_FAILED_INSUFFICIENT_SHARES
    assert receipt.valid_shares_count == 2

    with pytest.raises(KeyError, match="ERR_NODE_NOT_FOUND"):
        coordinator.suspend_node("non-existent-node")


def test_09_stale_cluster_epoch_rejected(standard_nodes: List[CloudHsmEnclaveNode]) -> None:
    """Verifies that evaluations against stale cluster epochs fail closed."""
    coordinator = CloudHsmRemoteQuorumCoordinator(threshold_m=2, current_cluster_epoch_id=5)
    for node in standard_nodes[:3]:
        coordinator.register_node_record(node.to_record(1700000000000))

    action_type = "SCITT_SUPER_ROOT_COMMIT"
    payload = {"data": "epoch-test"}
    digest_hex = compute_sha256_caid(payload).split("sha256:")[1]

    shares = [
        standard_nodes[0].sign_share(action_type, digest_hex, 5, nonce="ep5-1"),
        standard_nodes[1].sign_share(action_type, digest_hex, 5, nonce="ep5-2"),
    ]

    # Specifying stale epoch 4 must raise ValueError
    with pytest.raises(ValueError, match="ERR_STALE_CLUSTER_EPOCH"):
        coordinator.evaluate_quorum(action_type, payload, shares, cluster_epoch_id=4)


def test_10_monotonic_cluster_epoch_advance(standard_nodes: List[CloudHsmEnclaveNode]) -> None:
    """Verifies advancing cluster epoch strictly requires monotonic increments."""
    coordinator = CloudHsmRemoteQuorumCoordinator(threshold_m=2, current_cluster_epoch_id=5)

    coordinator.advance_cluster_epoch(6)
    assert coordinator.current_cluster_epoch_id == 6

    with pytest.raises(ValueError, match="ERR_NON_MONOTONIC_EPOCH"):
        coordinator.advance_cluster_epoch(6)

    with pytest.raises(ValueError, match="ERR_NON_MONOTONIC_EPOCH"):
        coordinator.advance_cluster_epoch(4)


def test_11_sqlite_wal_persistence_and_durability(standard_nodes: List[CloudHsmEnclaveNode], temp_db: str) -> None:
    """Verifies that quorum receipts and shares are persisted durably in SQLite-WAL."""
    coordinator = CloudHsmRemoteQuorumCoordinator(threshold_m=2, current_cluster_epoch_id=1, db_path=temp_db)
    for node in standard_nodes[:3]:
        coordinator.register_node_record(node.to_record(1700000000000))

    action_type = "SCITT_SUPER_ROOT_COMMIT"
    payload = {"merkle_root": "0xcafe9999"}
    digest_hex = compute_sha256_caid(payload).split("sha256:")[1]

    shares = [
        standard_nodes[0].sign_share(action_type, digest_hex, 1, nonce="wal-1"),
        standard_nodes[1].sign_share(action_type, digest_hex, 1, nonce="wal-2"),
    ]

    receipt = coordinator.evaluate_quorum(action_type, payload, shares)
    assert receipt.quorum_status == QUORUM_STATUS_ESTABLISHED
    coordinator.close()

    # Verify directly via a fresh SQLite connection
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute("SELECT quorum_id, quorum_status, valid_shares_count FROM quorum_decisions_ledger WHERE quorum_id = ?", (receipt.quorum_id,))
    row = cur.fetchone()
    assert row is not None
    assert row[0] == receipt.quorum_id
    assert row[1] == QUORUM_STATUS_ESTABLISHED
    assert row[2] == 2

    cur.execute("SELECT COUNT(*) FROM quorum_shares_ledger WHERE quorum_id = ?", (receipt.quorum_id,))
    shares_count = cur.fetchone()[0]
    assert shares_count == 2
    conn.close()


def test_12_quorum_certificate_export_and_verification(standard_nodes: List[CloudHsmEnclaveNode]) -> None:
    """Verifies exporting and verifying a tamper-evident Quorum Certificate."""
    coordinator = CloudHsmRemoteQuorumCoordinator(threshold_m=3, current_cluster_epoch_id=1)
    for node in standard_nodes:
        coordinator.register_node_record(node.to_record(1700000000000))

    action_type = "SCITT_SUPER_ROOT_COMMIT"
    payload = {"batch_id": 99}
    digest_hex = compute_sha256_caid(payload).split("sha256:")[1]

    shares = [
        standard_nodes[0].sign_share(action_type, digest_hex, 1, nonce="c1"),
        standard_nodes[1].sign_share(action_type, digest_hex, 1, nonce="c2"),
        standard_nodes[2].sign_share(action_type, digest_hex, 1, nonce="c3"),
    ]

    receipt = coordinator.evaluate_quorum(action_type, payload, shares)
    cert = coordinator.export_quorum_certificate(receipt)

    assert cert["certificate_type"] == "CLOUD_HSM_REMOTE_QUORUM_CERTIFICATE"
    assert cert["status"] == QUORUM_STATUS_ESTABLISHED
    assert coordinator.verify_quorum_certificate(cert) is True

    # Tamper with certificate
    tampered_cert = dict(cert)
    tampered_receipt = dict(tampered_cert["receipt"])
    tampered_receipt["valid_shares_count"] = 999
    tampered_cert["receipt"] = tampered_receipt
    assert coordinator.verify_quorum_certificate(tampered_cert) is False


def test_13_immutability_and_validation_errors() -> None:
    """Verifies frozen dataclass immutability and error checking on invalid parameters."""
    with pytest.raises(ValueError, match="ERR_INVALID_THRESHOLD_M"):
        CloudHsmRemoteQuorumCoordinator(threshold_m=0)

    with pytest.raises(ValueError, match="ERR_INVALID_CLUSTER_EPOCH_ID"):
        CloudHsmRemoteQuorumCoordinator(threshold_m=3, current_cluster_epoch_id=0)

    coordinator = CloudHsmRemoteQuorumCoordinator(threshold_m=3, current_cluster_epoch_id=1)
    with pytest.raises(ValueError, match="ERR_INVALID_ACTION_TYPE"):
        coordinator.evaluate_quorum("", {}, [])

    with pytest.raises(ValueError, match="ERR_EMPTY_SHARES_COLLECTION"):
        coordinator.evaluate_quorum("TEST", {}, [])

    # Insufficient registered nodes
    node = CloudHsmEnclaveNode("node-single", "AWS_KMS", "ED25519")
    coordinator.register_node_record(node.to_record(1700000000000))
    share = node.sign_share("TEST", "a" * 64, 1)
    with pytest.raises(ValueError, match="ERR_INSUFFICIENT_REGISTERED_NODES"):
        coordinator.evaluate_quorum("TEST", {"key": "val"}, [share])

    # Dataclass immutability
    rec = node.to_record(1700000000000)
    with pytest.raises(dataclasses.FrozenInstanceError):
        rec.status = "MODIFIED"  # type: ignore


def test_14_hsm_node_record_exhaustive_validations() -> None:
    """Verifies all validation branches of HsmNodeRecord."""
    valid_pem = "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA\n-----END PUBLIC KEY-----"

    with pytest.raises(ValueError, match="ERR_INVALID_NODE_ID"):
        HsmNodeRecord("", "AWS_KMS", "ED25519", valid_pem, STATUS_ACTIVE, 1700000000000)
    with pytest.raises(ValueError, match="ERR_UNSUPPORTED_PROVIDER"):
        HsmNodeRecord("n1", "BAD_PROVIDER", "ED25519", valid_pem, STATUS_ACTIVE, 1700000000000)
    with pytest.raises(ValueError, match="ERR_UNSUPPORTED_ALGORITHM"):
        HsmNodeRecord("n1", "AWS_KMS", "BAD_ALGO", valid_pem, STATUS_ACTIVE, 1700000000000)
    with pytest.raises(ValueError, match="ERR_INVALID_PUBLIC_KEY_PEM"):
        HsmNodeRecord("n1", "AWS_KMS", "ED25519", "", STATUS_ACTIVE, 1700000000000)
    with pytest.raises(ValueError, match="ERR_INVALID_STATUS"):
        HsmNodeRecord("n1", "AWS_KMS", "ED25519", valid_pem, "INVALID_STATUS", 1700000000000)
    with pytest.raises(ValueError, match="ERR_INVALID_REGISTERED_AT_EPOCH_MS"):
        HsmNodeRecord("n1", "AWS_KMS", "ED25519", valid_pem, STATUS_ACTIVE, 0)
    with pytest.raises(ValueError, match="ERR_INVALID_REGISTERED_AT_EPOCH_MS"):
        HsmNodeRecord("n1", "AWS_KMS", "ED25519", valid_pem, STATUS_ACTIVE, 1700000.5)  # type: ignore


def test_15_quorum_share_receipt_exhaustive_validations() -> None:
    """Verifies all validation branches of QuorumShareReceipt."""
    valid_pem = "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA\n-----END PUBLIC KEY-----"
    valid_payload = {
        "action_type": "TEST_ACTION",
        "cluster_epoch_id": 1,
        "node_id": "node-1",
        "nonce": "n1",
        "payload_digest_hex": "0" * 64,
        "signed_at_epoch_ms": 1700000000000,
    }

    with pytest.raises(ValueError, match="ERR_INVALID_SHARE_ID"):
        QuorumShareReceipt("", "node-1", "ED25519", valid_pem, "sig", valid_payload)
    with pytest.raises(ValueError, match="ERR_INVALID_NODE_ID"):
        QuorumShareReceipt("s1", "", "ED25519", valid_pem, "sig", valid_payload)
    with pytest.raises(ValueError, match="ERR_UNSUPPORTED_ALGORITHM"):
        QuorumShareReceipt("s1", "node-1", "BAD_ALGO", valid_pem, "sig", valid_payload)
    with pytest.raises(ValueError, match="ERR_INVALID_PUBLIC_KEY_PEM"):
        QuorumShareReceipt("s1", "node-1", "ED25519", "", "sig", valid_payload)
    with pytest.raises(ValueError, match="ERR_INVALID_PUBLIC_KEY_PEM"):
        QuorumShareReceipt("s1", "node-1", "ED25519", "   ", "sig", valid_payload)
    with pytest.raises(ValueError, match="ERR_INVALID_SIGNATURE_B64"):
        QuorumShareReceipt("s1", "node-1", "ED25519", valid_pem, "", valid_payload)
    with pytest.raises(ValueError, match="ERR_INVALID_SHARE_PAYLOAD"):
        QuorumShareReceipt("s1", "node-1", "ED25519", valid_pem, "sig", {})  # type: ignore
    with pytest.raises(ValueError, match="ERR_INVALID_SHARE_PAYLOAD"):
        QuorumShareReceipt("s1", "node-1", "ED25519", valid_pem, "sig", "not_a_dict")  # type: ignore

    # Missing mandatory fields
    for field in ("action_type", "cluster_epoch_id", "node_id", "nonce", "payload_digest_hex", "signed_at_epoch_ms"):
        bad_payload = dict(valid_payload)
        bad_payload.pop(field)
        with pytest.raises(ValueError, match=f"ERR_MISSING_PAYLOAD_FIELD: {field}"):
            QuorumShareReceipt("s1", "node-1", "ED25519", valid_pem, "sig", bad_payload)

    # Invalid epoch and timestamp
    bad_epoch = dict(valid_payload, cluster_epoch_id=0)
    with pytest.raises(ValueError, match="ERR_INVALID_CLUSTER_EPOCH_ID"):
        QuorumShareReceipt("s1", "node-1", "ED25519", valid_pem, "sig", bad_epoch)
    bad_epoch_float = dict(valid_payload, cluster_epoch_id=1.5)
    with pytest.raises(ValueError, match="ERR_INVALID_CLUSTER_EPOCH_ID"):
        QuorumShareReceipt("s1", "node-1", "ED25519", valid_pem, "sig", bad_epoch_float)

    bad_ts = dict(valid_payload, signed_at_epoch_ms=-1)
    with pytest.raises(ValueError, match="ERR_INVALID_SIGNED_AT_EPOCH_MS"):
        QuorumShareReceipt("s1", "node-1", "ED25519", valid_pem, "sig", bad_ts)
    bad_ts_float = dict(valid_payload, signed_at_epoch_ms=100.5)
    with pytest.raises(ValueError, match="ERR_INVALID_SIGNED_AT_EPOCH_MS"):
        QuorumShareReceipt("s1", "node-1", "ED25519", valid_pem, "sig", bad_ts_float)

    # Node ID mismatch
    bad_node = dict(valid_payload, node_id="node-other")
    with pytest.raises(ValueError, match="ERR_NODE_ID_PAYLOAD_MISMATCH"):
        QuorumShareReceipt("s1", "node-1", "ED25519", valid_pem, "sig", bad_node)


def test_16_quorum_authorization_receipt_exhaustive_validations() -> None:
    """Verifies all validation branches of QuorumAuthorizationReceipt."""
    valid_args: Dict[str, Any] = {
        "quorum_id": "q1",
        "action_type": "ACTION",
        "payload_digest_hex": "0" * 64,
        "cluster_epoch_id": 1,
        "required_threshold_m": 3,
        "total_participants_n": 5,
        "valid_shares_count": 3,
        "quorum_status": QUORUM_STATUS_ESTABLISHED,
        "participating_node_ids": ["n1", "n2", "n3"],
        "shares": [{"share": "data"}],
        "sealed_at_epoch_ms": 1700000000000,
        "receipt_caid": "sha256:" + "0" * 64,
    }

    # Invalid quorum_id
    with pytest.raises(ValueError, match="ERR_INVALID_QUORUM_ID"):
        QuorumAuthorizationReceipt(**dict(valid_args, quorum_id=""))
    # Invalid action_type
    with pytest.raises(ValueError, match="ERR_INVALID_ACTION_TYPE"):
        QuorumAuthorizationReceipt(**dict(valid_args, action_type=""))
    # Invalid payload_digest_hex
    with pytest.raises(ValueError, match="ERR_INVALID_PAYLOAD_DIGEST_HEX"):
        QuorumAuthorizationReceipt(**dict(valid_args, payload_digest_hex="short"))
    # Invalid cluster_epoch_id
    with pytest.raises(ValueError, match="ERR_INVALID_CLUSTER_EPOCH_ID"):
        QuorumAuthorizationReceipt(**dict(valid_args, cluster_epoch_id=0))
    with pytest.raises(ValueError, match="ERR_INVALID_CLUSTER_EPOCH_ID"):
        QuorumAuthorizationReceipt(**dict(valid_args, cluster_epoch_id=1.5))
    # Invalid threshold_m
    with pytest.raises(ValueError, match="ERR_INVALID_THRESHOLD_M"):
        QuorumAuthorizationReceipt(**dict(valid_args, required_threshold_m=0))
    # Invalid total_participants_n
    with pytest.raises(ValueError, match="ERR_INVALID_TOTAL_N"):
        QuorumAuthorizationReceipt(**dict(valid_args, total_participants_n=2))
    # Invalid valid_shares_count
    with pytest.raises(ValueError, match="ERR_INVALID_VALID_SHARES_COUNT"):
        QuorumAuthorizationReceipt(**dict(valid_args, valid_shares_count=-1))
    # Invalid quorum_status
    with pytest.raises(ValueError, match="ERR_INVALID_QUORUM_STATUS"):
        QuorumAuthorizationReceipt(**dict(valid_args, quorum_status="UNKNOWN"))
    # Invalid participating_node_ids
    with pytest.raises(ValueError, match="ERR_INVALID_PARTICIPATING_NODES"):
        QuorumAuthorizationReceipt(**dict(valid_args, participating_node_ids="not_a_list"))  # type: ignore
    # Invalid shares list
    with pytest.raises(ValueError, match="ERR_INVALID_SHARES_LIST"):
        QuorumAuthorizationReceipt(**dict(valid_args, shares="not_a_list"))  # type: ignore
    # Invalid sealed_at_epoch_ms
    with pytest.raises(ValueError, match="ERR_INVALID_SEALED_AT_EPOCH_MS"):
        QuorumAuthorizationReceipt(**dict(valid_args, sealed_at_epoch_ms=0))
    with pytest.raises(ValueError, match="ERR_INVALID_SEALED_AT_EPOCH_MS"):
        QuorumAuthorizationReceipt(**dict(valid_args, sealed_at_epoch_ms=100.5))
    # Invalid receipt_caid
    with pytest.raises(ValueError, match="ERR_INVALID_RECEIPT_CAID"):
        QuorumAuthorizationReceipt(**dict(valid_args, receipt_caid="not_sha256"))
    with pytest.raises(ValueError, match="ERR_INVALID_RECEIPT_CAID"):
        QuorumAuthorizationReceipt(**dict(valid_args, receipt_caid=12345))  # type: ignore


def test_17_coordinator_and_node_edge_branches() -> None:
    """Verifies edge branches in coordinator and node signing."""
    node = CloudHsmEnclaveNode("node-edge", "AWS_KMS", "ED25519")
    now = int(time.time() * 1000)

    # 1. Default registered_at_epoch_ms
    rec = node.to_record()
    assert rec.registered_at_epoch_ms >= now - 1000

    # 2. Default sign_share nonce and share_id
    share = node.sign_share("ACTION", "1" * 64, 1)
    assert share.share_payload["nonce"].startswith("nonce-")
    assert share.share_id.startswith("share-node-edge-")
    assert len(share.share_id.split("-")[-1]) == 8
    assert share.share_payload["signed_at_epoch_ms"] >= now - 1000

    # 3. sign_share error on unsupported algorithm (via monkeypatch of instance attribute)
    object.__setattr__(node, "key_algorithm", "INVALID_ALGO")
    with pytest.raises(ValueError, match="ERR_UNSUPPORTED_ALGORITHM"):
        node.sign_share("ACTION", "1" * 64, 1)
    object.__setattr__(node, "key_algorithm", "ED25519")

    # 4. register_node with default timestamp
    coord = CloudHsmRemoteQuorumCoordinator(threshold_m=2, current_cluster_epoch_id=1)
    rec2 = coord.register_node("node-auto-ts", "GCP_CLOUD_KMS", "ECDSA_P256_SHA256", rec.public_key_pem)
    assert rec2.registered_at_epoch_ms >= now - 1000
    assert coord.registered_nodes_count == 1

    # 5. verify_share_signature with key algorithm mismatch
    share_valid = node.sign_share("ACTION", "1" * 64, 1, nonce="edge-nonce")
    coord.register_node_record(node.to_record())
    assert coord.verify_share_signature(share_valid, "ACTION", "1" * 64, 1) is True

    # Mutate share algorithm in receipt
    share_mismatched = QuorumShareReceipt(
        share_id=share_valid.share_id,
        node_id=share_valid.node_id,
        key_algorithm="ECDSA_P256_SHA256",
        public_key_pem=share_valid.public_key_pem,
        signature_b64=share_valid.signature_b64,
        share_payload=share_valid.share_payload,
    )
    assert coord.verify_share_signature(share_mismatched, "ACTION", "1" * 64, 1) is False

    # 6. verify_share_signature with PEM mismatch
    other_pem = "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA\n-----END PUBLIC KEY-----"
    share_pem_mismatch = QuorumShareReceipt(
        share_id=share_valid.share_id,
        node_id=share_valid.node_id,
        key_algorithm=share_valid.key_algorithm,
        public_key_pem=other_pem,
        signature_b64=share_valid.signature_b64,
        share_payload=share_valid.share_payload,
    )
    assert coord.verify_share_signature(share_pem_mismatch, "ACTION", "1" * 64, 1) is False

    # 7. verify_quorum_certificate failure branches
    cert_base = coord.export_quorum_certificate(
        QuorumAuthorizationReceipt(
            quorum_id="q1",
            action_type="ACTION",
            payload_digest_hex="0" * 64,
            cluster_epoch_id=1,
            required_threshold_m=2,
            total_participants_n=2,
            valid_shares_count=2,
            quorum_status=QUORUM_STATUS_ESTABLISHED,
            participating_node_ids=["n1", "n2"],
            shares=[],
            sealed_at_epoch_ms=1700000000000,
            receipt_caid=compute_sha256_caid({
                "action_type": "ACTION",
                "cluster_epoch_id": 1,
                "participating_node_ids": ["n1", "n2"],
                "payload_digest_hex": "0" * 64,
                "quorum_id": "q1",
                "quorum_status": QUORUM_STATUS_ESTABLISHED,
                "required_threshold_m": 2,
                "sealed_at_epoch_ms": 1700000000000,
                "shares": [],
                "total_participants_n": 2,
                "valid_shares_count": 2,
            }),
        )
    )
    assert coord.verify_quorum_certificate(cert_base) is True

    # Bad certificate type
    bad_type_cert = dict(cert_base, certificate_type="WRONG_TYPE")
    assert coord.verify_quorum_certificate(bad_type_cert) is False

    # Bad receipt not dict
    bad_receipt_cert = dict(cert_base, receipt="not_a_dict")
    assert coord.verify_quorum_certificate(bad_receipt_cert) is False

    # Inconsistent status vs threshold
    bad_status_receipt = dict(cert_base["receipt"], quorum_status=QUORUM_STATUS_FAILED_INSUFFICIENT_SHARES)
    bad_status_caid = compute_sha256_caid(bad_status_receipt)
    bad_status_receipt["receipt_caid"] = bad_status_caid
    bad_status_cert = dict(cert_base, receipt=bad_status_receipt, certificate_caid=bad_status_caid)
    assert coord.verify_quorum_certificate(bad_status_cert) is False

    # 7. evaluate_quorum with default evaluation_time_ms=None (kills line 482 constant 1000 perturbation)
    node_b = CloudHsmEnclaveNode("node-edge-b", "AWS_KMS", "ED25519")
    coord.register_node_record(node_b.to_record())
    share_b = node_b.sign_share("ACTION", compute_sha256_caid({"msg": "test_eval_time"}).split("sha256:")[1], 1, nonce="edge-nonce-b")
    share_a = node.sign_share("ACTION", compute_sha256_caid({"msg": "test_eval_time"}).split("sha256:")[1], 1, nonce="edge-nonce-a")
    t_eval_before = int(time.time() * 1000)
    receipt_default_eval = coord.evaluate_quorum(
        action_type="ACTION",
        payload={"msg": "test_eval_time"},
        shares=[share_a, share_b],
        cluster_epoch_id=1,
        evaluation_time_ms=None,
    )
    t_eval_after = int(time.time() * 1000)
    assert t_eval_before <= receipt_default_eval.sealed_at_epoch_ms <= t_eval_after + 500
    assert abs(receipt_default_eval.sealed_at_epoch_ms - t_eval_before) <= 500
    cert_default_eval = coord.export_quorum_certificate(receipt_default_eval)
    assert coord.verify_quorum_certificate(cert_default_eval) is True



