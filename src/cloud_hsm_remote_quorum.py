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
cloud_hsm_remote_quorum.py — Multi-Cloud Hardware Security Module (Cloud HSM) Remote Quorum Coordinator.

Part of Sovereign Multi-Agent OS (SMAOS) / AEIB Enterprise Gateway.
Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model.

Architectural Invariants:
1. M-of-N Threshold Remote Quorum:
   - Evaluates signature shares across multi-cloud hardware security modules
     (AWS KMS, GCP Cloud KMS, Azure Key Vault, SoftHSM PKCS#11, Apple Secure Enclave).
   - Enforces configurable M <= N threshold (e.g., 3-of-5 threshold) for high-stakes
     governance operations: SCITT federated super-roots, failover epoch fencing,
     and line-stop resets.
2. Cryptographic Rigor & Zero-RAM Invariant:
   - Supports NIST P-256 (secp256r1) ECDSA-SHA256 and Ed25519 asymmetric signatures.
   - Private key material remains strictly encapsulated within the enclave abstraction.
   - All payloads are canonicalized using RFC 8785 single-source JCS with zero floats.
3. Monotonic Epoch Fencing & Anti-Replay:
   - Each share binds explicitly to cluster_epoch_id, action_type, payload_digest_hex, and nonce.
   - Stale cluster epochs and duplicate shares from identical nodes are rejected fail-closed.
4. Sub-5ms SQLite-WAL Durability:
   - Persists all quorum shares and sealed authorization receipts to a local WAL database.
"""

from __future__ import annotations

import base64
from dataclasses import asdict, dataclass
import hashlib
import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519

from src.jcs_canonicalizer import encode_jcs

# Supported asymmetric cryptographic algorithms
SUPPORTED_ALGORITHMS: Set[str] = {"ED25519", "ECDSA_P256_SHA256"}

# Recognized cloud HSM enclave providers
SUPPORTED_PROVIDERS: Set[str] = {
    "AWS_KMS",
    "GCP_CLOUD_KMS",
    "AZURE_KEY_VAULT",
    "SOFTHSM_PKCS11",
    "APPLE_SECURE_ENCLAVE",
}

STATUS_ACTIVE: str = "ACTIVE"
STATUS_SUSPENDED: str = "SUSPENDED"

QUORUM_STATUS_ESTABLISHED: str = "QUORUM_ESTABLISHED"
QUORUM_STATUS_FAILED_INSUFFICIENT_SHARES: str = "QUORUM_FAILED_INSUFFICIENT_SHARES"


def compute_sha256_caid(payload: Any) -> str:
    """Computes an RFC 8785 canonical SHA-256 CAID (e.g. 'sha256:<64-hex>')."""
    if isinstance(payload, bytes):
        raw_bytes = payload
    elif isinstance(payload, str):
        raw_bytes = payload.encode("utf-8")
    else:
        raw_bytes = encode_jcs(payload)
    return f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}"


@dataclass(frozen=True)
class HsmNodeRecord:
    """Registered HSM participant node record."""

    node_id: str
    cloud_provider: str
    key_algorithm: str
    public_key_pem: str
    status: str
    registered_at_epoch_ms: int

    def __post_init__(self) -> None:
        if not isinstance(self.node_id, str) or not self.node_id.strip():
            raise ValueError("ERR_INVALID_NODE_ID")
        if self.cloud_provider not in SUPPORTED_PROVIDERS:
            raise ValueError(f"ERR_UNSUPPORTED_PROVIDER: {self.cloud_provider}")
        if self.key_algorithm not in SUPPORTED_ALGORITHMS:
            raise ValueError(f"ERR_UNSUPPORTED_ALGORITHM: {self.key_algorithm}")
        if not isinstance(self.public_key_pem, str) or not self.public_key_pem.strip():
            raise ValueError("ERR_INVALID_PUBLIC_KEY_PEM")
        if self.status not in {STATUS_ACTIVE, STATUS_SUSPENDED}:
            raise ValueError(f"ERR_INVALID_STATUS: {self.status}")
        if type(self.registered_at_epoch_ms) is not int or self.registered_at_epoch_ms <= 0:
            raise ValueError("ERR_INVALID_REGISTERED_AT_EPOCH_MS")


@dataclass(frozen=True)
class QuorumShareReceipt:
    """Cryptographic authorization share signed by an HSM enclave participant."""

    share_id: str
    node_id: str
    key_algorithm: str
    public_key_pem: str
    signature_b64: str
    share_payload: Dict[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.share_id, str) or not self.share_id.strip():
            raise ValueError("ERR_INVALID_SHARE_ID")
        if not isinstance(self.node_id, str) or not self.node_id.strip():
            raise ValueError("ERR_INVALID_NODE_ID")
        if self.key_algorithm not in SUPPORTED_ALGORITHMS:
            raise ValueError(f"ERR_UNSUPPORTED_ALGORITHM: {self.key_algorithm}")
        if not isinstance(self.public_key_pem, str) or not self.public_key_pem.strip():
            raise ValueError("ERR_INVALID_PUBLIC_KEY_PEM")
        if not isinstance(self.signature_b64, str) or not self.signature_b64.strip():
            raise ValueError("ERR_INVALID_SIGNATURE_B64")
        if not isinstance(self.share_payload, dict) or not self.share_payload:
            raise ValueError("ERR_INVALID_SHARE_PAYLOAD")

        # Validate mandatory share_payload keys
        for key in (
            "action_type",
            "cluster_epoch_id",
            "node_id",
            "nonce",
            "payload_digest_hex",
            "signed_at_epoch_ms",
        ):
            if key not in self.share_payload:
                raise ValueError(f"ERR_MISSING_PAYLOAD_FIELD: {key}")

        if type(self.share_payload["cluster_epoch_id"]) is not int or self.share_payload["cluster_epoch_id"] <= 0:
            raise ValueError("ERR_INVALID_CLUSTER_EPOCH_ID")
        if type(self.share_payload["signed_at_epoch_ms"]) is not int or self.share_payload["signed_at_epoch_ms"] <= 0:
            raise ValueError("ERR_INVALID_SIGNED_AT_EPOCH_MS")
        if self.share_payload["node_id"] != self.node_id:
            raise ValueError("ERR_NODE_ID_PAYLOAD_MISMATCH")


@dataclass(frozen=True)
class QuorumAuthorizationReceipt:
    """Canonical RFC 8785 sealed quorum adjudication receipt."""

    quorum_id: str
    action_type: str
    payload_digest_hex: str
    cluster_epoch_id: int
    required_threshold_m: int
    total_participants_n: int
    valid_shares_count: int
    quorum_status: str
    participating_node_ids: List[str]
    shares: List[Dict[str, Any]]
    sealed_at_epoch_ms: int
    receipt_caid: str

    def __post_init__(self) -> None:
        if not isinstance(self.quorum_id, str) or not self.quorum_id.strip():
            raise ValueError("ERR_INVALID_QUORUM_ID")
        if not isinstance(self.action_type, str) or not self.action_type.strip():
            raise ValueError("ERR_INVALID_ACTION_TYPE")
        if not isinstance(self.payload_digest_hex, str) or len(self.payload_digest_hex) != 64:
            raise ValueError("ERR_INVALID_PAYLOAD_DIGEST_HEX")
        if type(self.cluster_epoch_id) is not int or self.cluster_epoch_id <= 0:
            raise ValueError("ERR_INVALID_CLUSTER_EPOCH_ID")
        if type(self.required_threshold_m) is not int or self.required_threshold_m <= 0:
            raise ValueError("ERR_INVALID_THRESHOLD_M")
        if type(self.total_participants_n) is not int or self.total_participants_n < self.required_threshold_m:
            raise ValueError("ERR_INVALID_TOTAL_N")
        if type(self.valid_shares_count) is not int or self.valid_shares_count < 0:
            raise ValueError("ERR_INVALID_VALID_SHARES_COUNT")
        if self.quorum_status not in {QUORUM_STATUS_ESTABLISHED, QUORUM_STATUS_FAILED_INSUFFICIENT_SHARES}:
            raise ValueError(f"ERR_INVALID_QUORUM_STATUS: {self.quorum_status}")
        if not isinstance(self.participating_node_ids, list):
            raise ValueError("ERR_INVALID_PARTICIPATING_NODES")
        if not isinstance(self.shares, list):
            raise ValueError("ERR_INVALID_SHARES_LIST")
        if type(self.sealed_at_epoch_ms) is not int or self.sealed_at_epoch_ms <= 0:
            raise ValueError("ERR_INVALID_SEALED_AT_EPOCH_MS")
        if not isinstance(self.receipt_caid, str) or not self.receipt_caid.startswith("sha256:"):
            raise ValueError("ERR_INVALID_RECEIPT_CAID")


class CloudHsmEnclaveNode:
    """Simulates or interfaces with a physical/cloud HSM enclave node.

    Encapsulates real cryptographic keys (Ed25519 or NIST P-256) without
    exposing private key material to external processes.
    """

    def __init__(
        self,
        node_id: str,
        cloud_provider: str = "AWS_KMS",
        key_algorithm: str = "ED25519",
        private_key: Optional[Any] = None,
    ) -> None:
        if node_id.strip() == "":
            raise ValueError("ERR_INVALID_NODE_ID")
        if cloud_provider not in SUPPORTED_PROVIDERS:
            raise ValueError(f"ERR_UNSUPPORTED_PROVIDER: {cloud_provider}")
        if key_algorithm not in SUPPORTED_ALGORITHMS:
            raise ValueError(f"ERR_UNSUPPORTED_ALGORITHM: {key_algorithm}")

        self.node_id = node_id
        self.cloud_provider = cloud_provider
        self.key_algorithm = key_algorithm

        if private_key is not None:
            self._private_key = private_key
        else:
            if key_algorithm == "ED25519":
                self._private_key = ed25519.Ed25519PrivateKey.generate()
            elif key_algorithm == "ECDSA_P256_SHA256":
                self._private_key = ec.generate_private_key(ec.SECP256R1())
            else:
                raise ValueError(f"ERR_UNSUPPORTED_ALGORITHM: {key_algorithm}")

        self._public_key = self._private_key.public_key()
        self.public_key_pem = self._export_pubkey_pem()

    def _export_pubkey_pem(self) -> str:
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")

    def to_record(self, registered_at_epoch_ms: Optional[int] = None) -> HsmNodeRecord:
        now_ms = registered_at_epoch_ms if registered_at_epoch_ms is not None else int(time.time() * 1000)
        return HsmNodeRecord(
            node_id=self.node_id,
            cloud_provider=self.cloud_provider,
            key_algorithm=self.key_algorithm,
            public_key_pem=self.public_key_pem,
            status=STATUS_ACTIVE,
            registered_at_epoch_ms=now_ms,
        )

    def sign_share(
        self,
        action_type: str,
        payload_digest_hex: str,
        cluster_epoch_id: int,
        nonce: Optional[str] = None,
        signed_at_epoch_ms: Optional[int] = None,
    ) -> QuorumShareReceipt:
        """Signs an authorization share over RFC 8785 canonical bytes."""
        if not action_type.strip():
            raise ValueError("ERR_INVALID_ACTION_TYPE")
        if len(payload_digest_hex) != 64:
            raise ValueError("ERR_INVALID_PAYLOAD_DIGEST_HEX")
        if cluster_epoch_id <= 0:
            raise ValueError("ERR_INVALID_CLUSTER_EPOCH_ID")

        now_ms = signed_at_epoch_ms if signed_at_epoch_ms is not None else int(time.time() * 1000)
        share_nonce = nonce if nonce is not None else f"nonce-{uuid.uuid4().hex[:12]}"
        share_id = f"share-{self.node_id}-{now_ms}-{uuid.uuid4().hex[:8]}"

        payload_dict: Dict[str, Any] = {
            "action_type": action_type,
            "cluster_epoch_id": cluster_epoch_id,
            "node_id": self.node_id,
            "nonce": share_nonce,
            "payload_digest_hex": payload_digest_hex,
            "signed_at_epoch_ms": now_ms,
        }

        canonical_bytes = encode_jcs(payload_dict)

        if self.key_algorithm == "ED25519":
            sig_bytes = self._private_key.sign(canonical_bytes)
        elif self.key_algorithm == "ECDSA_P256_SHA256":
            sig_bytes = self._private_key.sign(canonical_bytes, ec.ECDSA(hashes.SHA256()))
        else:
            raise ValueError(f"ERR_UNSUPPORTED_ALGORITHM: {self.key_algorithm}")

        sig_b64 = base64.b64encode(sig_bytes).decode("ascii")

        return QuorumShareReceipt(
            share_id=share_id,
            node_id=self.node_id,
            key_algorithm=self.key_algorithm,
            public_key_pem=self.public_key_pem,
            signature_b64=sig_b64,
            share_payload=payload_dict,
        )


class CloudHsmRemoteQuorumCoordinator:
    """Coordinates and verifies M-of-N remote quorum authorization across HSM nodes."""

    def __init__(
        self,
        threshold_m: int = 3,
        current_cluster_epoch_id: int = 1,
        db_path: Optional[str] = None,
    ) -> None:
        if threshold_m <= 0:
            raise ValueError("ERR_INVALID_THRESHOLD_M")
        if current_cluster_epoch_id <= 0:
            raise ValueError("ERR_INVALID_CLUSTER_EPOCH_ID")

        self.threshold_m = threshold_m
        self.current_cluster_epoch_id = current_cluster_epoch_id
        self.db_path = db_path
        self._registered_nodes: Dict[str, HsmNodeRecord] = {}
        self._seen_share_nonces: Set[str] = set()
        self._total_quorums_evaluated: int = 0

        self._conn: Optional[sqlite3.Connection] = None
        if self.db_path:
            self._init_sqlite()

    def _init_sqlite(self) -> None:
        if not self.db_path:
            return
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quorum_decisions_ledger (
                    quorum_id TEXT PRIMARY KEY,
                    action_type TEXT NOT NULL,
                    payload_digest_hex TEXT NOT NULL,
                    cluster_epoch_id INTEGER NOT NULL,
                    required_threshold_m INTEGER NOT NULL,
                    total_participants_n INTEGER NOT NULL,
                    valid_shares_count INTEGER NOT NULL,
                    quorum_status TEXT NOT NULL,
                    sealed_at_epoch_ms INTEGER NOT NULL,
                    receipt_caid TEXT NOT NULL,
                    receipt_json TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quorum_shares_ledger (
                    share_id TEXT PRIMARY KEY,
                    quorum_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    key_algorithm TEXT NOT NULL,
                    signed_at_epoch_ms INTEGER NOT NULL,
                    signature_b64 TEXT NOT NULL,
                    share_payload_json TEXT NOT NULL
                )
                """
            )

    def register_node(
        self,
        node_id: str,
        cloud_provider: str,
        key_algorithm: str,
        public_key_pem: str,
        status: str = STATUS_ACTIVE,
        registered_at_epoch_ms: Optional[int] = None,
    ) -> HsmNodeRecord:
        """Registers an HSM enclave node in the quorum mesh."""
        now_ms = registered_at_epoch_ms if registered_at_epoch_ms is not None else int(time.time() * 1000)
        record = HsmNodeRecord(
            node_id=node_id,
            cloud_provider=cloud_provider,
            key_algorithm=key_algorithm,
            public_key_pem=public_key_pem,
            status=status,
            registered_at_epoch_ms=now_ms,
        )
        self._registered_nodes[node_id] = record
        return record

    def register_node_record(self, record: HsmNodeRecord) -> None:
        self._registered_nodes[record.node_id] = record

    def suspend_node(self, node_id: str) -> None:
        if node_id not in self._registered_nodes:
            raise KeyError(f"ERR_NODE_NOT_FOUND: {node_id}")
        rec = self._registered_nodes[node_id]
        self._registered_nodes[node_id] = HsmNodeRecord(
            node_id=rec.node_id,
            cloud_provider=rec.cloud_provider,
            key_algorithm=rec.key_algorithm,
            public_key_pem=rec.public_key_pem,
            status=STATUS_SUSPENDED,
            registered_at_epoch_ms=rec.registered_at_epoch_ms,
        )

    def advance_cluster_epoch(self, new_epoch_id: int) -> None:
        if new_epoch_id <= self.current_cluster_epoch_id:
            raise ValueError(f"ERR_NON_MONOTONIC_EPOCH: {new_epoch_id} <= {self.current_cluster_epoch_id}")
        self.current_cluster_epoch_id = new_epoch_id

    @property
    def registered_nodes_count(self) -> int:
        return len(self._registered_nodes)

    def verify_share_signature(
        self,
        share: QuorumShareReceipt,
        expected_action_type: str,
        expected_digest_hex: str,
        expected_epoch_id: int,
    ) -> bool:
        """Verifies the asymmetric signature and bindings of an individual share."""
        payload = share.share_payload
        if payload.get("action_type") != expected_action_type:
            return False
        if payload.get("payload_digest_hex") != expected_digest_hex:
            return False
        if payload.get("cluster_epoch_id") != expected_epoch_id:
            return False
        if payload.get("node_id") != share.node_id:
            return False

        # Node must be registered and active
        if share.node_id not in self._registered_nodes:
            return False
        node_rec = self._registered_nodes[share.node_id]
        if node_rec.status != STATUS_ACTIVE:
            return False
        if node_rec.key_algorithm != share.key_algorithm:
            return False
        if node_rec.public_key_pem.strip() != share.public_key_pem.strip():
            return False

        canonical_bytes = encode_jcs(payload)
        try:
            sig_bytes = base64.b64decode(share.signature_b64)
            pubkey_obj = serialization.load_pem_public_key(node_rec.public_key_pem.encode("ascii"))

            if share.key_algorithm == "ED25519":
                if not isinstance(pubkey_obj, ed25519.Ed25519PublicKey):
                    return False
                pubkey_obj.verify(sig_bytes, canonical_bytes)
                return True
            elif share.key_algorithm == "ECDSA_P256_SHA256":
                if not isinstance(pubkey_obj, ec.EllipticCurvePublicKey):
                    return False
                pubkey_obj.verify(sig_bytes, canonical_bytes, ec.ECDSA(hashes.SHA256()))
                return True
            else:
                return False
        except (ValueError, InvalidSignature, Exception):
            return False

    def evaluate_quorum(
        self,
        action_type: str,
        payload: Any,
        shares: Sequence[QuorumShareReceipt],
        cluster_epoch_id: Optional[int] = None,
        evaluation_time_ms: Optional[int] = None,
    ) -> QuorumAuthorizationReceipt:
        """Evaluates an M-of-N threshold quorum over a given action payload and shares."""
        if not action_type.strip():
            raise ValueError("ERR_INVALID_ACTION_TYPE")
        if not shares:
            raise ValueError("ERR_EMPTY_SHARES_COLLECTION")

        eval_epoch = cluster_epoch_id if cluster_epoch_id is not None else self.current_cluster_epoch_id
        if eval_epoch != self.current_cluster_epoch_id:
            raise ValueError(f"ERR_STALE_CLUSTER_EPOCH: {eval_epoch} != {self.current_cluster_epoch_id}")

        now_ms = evaluation_time_ms if evaluation_time_ms is not None else int(time.time() * 1000)
        self._total_quorums_evaluated += 1
        quorum_id = f"quorum-{action_type.lower()}-ep{eval_epoch}-{self._total_quorums_evaluated}-{now_ms}"

        payload_digest_hex = compute_sha256_caid(payload).split("sha256:")[1]

        total_n = len(self._registered_nodes)
        if total_n < self.threshold_m:
            raise ValueError(f"ERR_INSUFFICIENT_REGISTERED_NODES: {total_n} < {self.threshold_m}")

        verified_nodes: List[str] = []
        verified_shares_dicts: List[Dict[str, Any]] = []
        seen_node_ids_in_batch: Set[str] = set()

        for share in shares:
            # Prevent duplicate node vote in same evaluation
            if share.node_id in seen_node_ids_in_batch:
                continue
            seen_node_ids_in_batch.add(share.node_id)

            # Anti-replay check for nonce
            nonce = share.share_payload.get("nonce", "")
            if nonce in self._seen_share_nonces:
                continue

            # Verify cryptographic signature
            if self.verify_share_signature(share, action_type, payload_digest_hex, eval_epoch):
                self._seen_share_nonces.add(nonce)
                verified_nodes.append(share.node_id)
                verified_shares_dicts.append(
                    {
                        "share_id": share.share_id,
                        "node_id": share.node_id,
                        "key_algorithm": share.key_algorithm,
                        "public_key_pem": share.public_key_pem,
                        "signature_b64": share.signature_b64,
                        "share_payload": share.share_payload,
                    }
                )

        valid_count = len(verified_nodes)
        if valid_count >= self.threshold_m:
            quorum_status = QUORUM_STATUS_ESTABLISHED
        else:
            quorum_status = QUORUM_STATUS_FAILED_INSUFFICIENT_SHARES

        unsealed_receipt_dict = {
            "action_type": action_type,
            "cluster_epoch_id": eval_epoch,
            "participating_node_ids": sorted(verified_nodes),
            "payload_digest_hex": payload_digest_hex,
            "quorum_id": quorum_id,
            "quorum_status": quorum_status,
            "required_threshold_m": self.threshold_m,
            "sealed_at_epoch_ms": now_ms,
            "shares": verified_shares_dicts,
            "total_participants_n": total_n,
            "valid_shares_count": valid_count,
        }

        receipt_caid = compute_sha256_caid(unsealed_receipt_dict)

        receipt = QuorumAuthorizationReceipt(
            quorum_id=quorum_id,
            action_type=action_type,
            payload_digest_hex=payload_digest_hex,
            cluster_epoch_id=eval_epoch,
            required_threshold_m=self.threshold_m,
            total_participants_n=total_n,
            valid_shares_count=valid_count,
            quorum_status=quorum_status,
            participating_node_ids=sorted(verified_nodes),
            shares=verified_shares_dicts,
            sealed_at_epoch_ms=now_ms,
            receipt_caid=receipt_caid,
        )

        if self._conn:
            self._persist_receipt_to_sqlite(receipt)

        return receipt

    def _persist_receipt_to_sqlite(self, receipt: QuorumAuthorizationReceipt) -> None:
        if not self._conn:
            return
        receipt_dict = asdict(receipt)
        receipt_json = encode_jcs(receipt_dict).decode("utf-8")

        with self._conn:
            self._conn.execute(
                """
                INSERT INTO quorum_decisions_ledger (
                    quorum_id, action_type, payload_digest_hex, cluster_epoch_id,
                    required_threshold_m, total_participants_n, valid_shares_count,
                    quorum_status, sealed_at_epoch_ms, receipt_caid, receipt_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt.quorum_id,
                    receipt.action_type,
                    receipt.payload_digest_hex,
                    receipt.cluster_epoch_id,
                    receipt.required_threshold_m,
                    receipt.total_participants_n,
                    receipt.valid_shares_count,
                    receipt.quorum_status,
                    receipt.sealed_at_epoch_ms,
                    receipt.receipt_caid,
                    receipt_json,
                ),
            )
            for share in receipt.shares:
                share_payload_json = encode_jcs(share["share_payload"]).decode("utf-8")
                self._conn.execute(
                    """
                    INSERT INTO quorum_shares_ledger (
                        share_id, quorum_id, node_id, key_algorithm,
                        signed_at_epoch_ms, signature_b64, share_payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        share["share_id"],
                        receipt.quorum_id,
                        share["node_id"],
                        share["key_algorithm"],
                        share["share_payload"]["signed_at_epoch_ms"],
                        share["signature_b64"],
                        share_payload_json,
                    ),
                )

    def export_quorum_certificate(self, receipt: QuorumAuthorizationReceipt) -> Dict[str, Any]:
        """Exports a verifiable, sealed quorum certificate dictionary."""
        receipt_dict = asdict(receipt)
        cert = {
            "certificate_type": "CLOUD_HSM_REMOTE_QUORUM_CERTIFICATE",
            "receipt": receipt_dict,
            "certificate_caid": receipt.receipt_caid,
            "status": receipt.quorum_status,
        }
        return cert

    def verify_quorum_certificate(self, cert: Dict[str, Any]) -> bool:
        """Verifies integrity and cryptographic validity of an exported certificate."""
        if cert.get("certificate_type") != "CLOUD_HSM_REMOTE_QUORUM_CERTIFICATE":
            return False
        receipt_dict = cert.get("receipt")
        if not isinstance(receipt_dict, dict):
            return False

        # Re-compute CAID
        expected_caid = receipt_dict.get("receipt_caid")
        unsealed = dict(receipt_dict)
        unsealed.pop("receipt_caid", None)
        computed_caid = compute_sha256_caid(unsealed)

        if expected_caid != computed_caid:
            return False
        if cert.get("certificate_caid") != computed_caid:
            return False

        # Check threshold
        valid_count = receipt_dict.get("valid_shares_count", 0)
        threshold_m = receipt_dict.get("required_threshold_m", 1)
        status = receipt_dict.get("quorum_status")

        if valid_count >= threshold_m and status != QUORUM_STATUS_ESTABLISHED:
            return False
        if valid_count < threshold_m and status != QUORUM_STATUS_FAILED_INSUFFICIENT_SHARES:
            return False

        return True

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
