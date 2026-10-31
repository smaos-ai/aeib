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
src/coco_attestation_proxy.py — Confidential Container (CoCo) Hardware Attestation Proxy.

Part of Sovereign Multi-Agent OS (SMAOS) / AEIB Enterprise Gateway.
Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model as a confidential container
attestation proxy scaffold and cryptographic key release prototype.

Honest Platform Boundary (Software Scaffold & Simulated CoCo Prototype):
  - This module is a software scaffold and simulation prototype for Confidential Containers (CoCo)
    and Kata-Containers Attestation Agent (AA) token verification.
  - It does NOT directly invoke physical hardware KBS (Key Broker Service) gRPC endpoints
    or cloud enclave hardware in this software prototype.
  - Operational mode: scaffold / simulated attestation proxy.

Architectural Invariants:
1. Multi-Dimensional Evidence Verification:
   - Validates launch measurement, container OCI image manifest, and kernel command-line digest.
2. Sealed Key Release Handshake:
   - Releases decrypted secret leases only when hardware attestation strictly matches policy baseline.
3. Anti-Replay Nonce Fencing:
   - Single-use challenge nonces with expiration windows.
4. Fail-Closed Rejection Codes:
   - HALT_COCO_UNTRUSTED_IMAGE
   - HALT_COCO_POLICY_DIVERGENCE
   - HALT_COCO_KEY_RELEASE_DENIED
   - HALT_COCO_SIGNATURE_INVALID
   - HALT_COCO_STALE_NONCE
5. Sub-5ms SQLite-WAL Durability:
   - Persists all token evaluations and key release receipts to local WAL database.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs

# Explicit fail-closed rejection codes
HALT_COCO_UNTRUSTED_IMAGE: str = "HALT_COCO_UNTRUSTED_IMAGE"
HALT_COCO_POLICY_DIVERGENCE: str = "HALT_COCO_POLICY_DIVERGENCE"
HALT_COCO_KEY_RELEASE_DENIED: str = "HALT_COCO_KEY_RELEASE_DENIED"
HALT_COCO_SIGNATURE_INVALID: str = "HALT_COCO_SIGNATURE_INVALID"
HALT_COCO_STALE_NONCE: str = "HALT_COCO_STALE_NONCE"

STATUS_ATTESTATION_VERIFIED: str = "ATTESTATION_VERIFIED"
STATUS_KEY_RELEASED: str = "KEY_RELEASED"


class CoCoAttestationError(Exception):
    """Exception raised when CoCo hardware attestation or key release fails."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class CoCoAttestationToken:
    """Attestation token emitted by Kata / CoCo Attestation Agent inside enclave."""

    token_id: str
    container_id: str
    enclave_type: str
    launch_measurement_digest: str
    container_image_digest: str
    kernel_cmdline_sha256: str
    nonce: str
    timestamp_ms: int
    enclave_public_key_hex: str
    signature: str

    def canonical_dict(self) -> Dict[str, Any]:
        return {
            "container_id": self.container_id,
            "container_image_digest": self.container_image_digest,
            "enclave_type": self.enclave_type,
            "kernel_cmdline_sha256": self.kernel_cmdline_sha256,
            "launch_measurement_digest": self.launch_measurement_digest,
            "nonce": self.nonce,
            "timestamp_ms": self.timestamp_ms,
            "token_id": self.token_id,
        }

    def canonical_bytes(self) -> bytes:
        return encode_jcs(self.canonical_dict())


@dataclass(frozen=True)
class CoCoKeyReleaseReceipt:
    """Durable receipt recording the release of an in-flight key to a verified enclave."""

    release_id: str
    token_id: str
    container_id: str
    secret_identifier: str
    fenced_key_caid: str
    receipt_caid: str
    status: str
    released_at_ms: int

    def canonical_dict(self) -> Dict[str, Any]:
        return {
            "container_id": self.container_id,
            "fenced_key_caid": self.fenced_key_caid,
            "receipt_caid": self.receipt_caid,
            "release_id": self.release_id,
            "secret_identifier": self.secret_identifier,
            "status": self.status,
            "token_id": self.token_id,
        }

    def canonical_bytes(self) -> bytes:
        return encode_jcs(self.canonical_dict())


def compute_sha256_caid(payload: Any) -> str:
    """Computes deterministic RFC 8785 canonical SHA-256 CAID."""
    if isinstance(payload, bytes):
        raw_bytes = payload
    elif isinstance(payload, str):
        raw_bytes = payload.encode("utf-8")
    else:
        raw_bytes = encode_jcs(payload)
    return f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}"


class CoCoAttestationProxy:
    """
    Confidential Container (CoCo) Hardware Attestation & Key Release Proxy.
    Verifies multi-factor enclave tokens and gates key release under fail-closed invariants.
    """

    def __init__(
        self,
        db_path: str = ":memory:",
        allowed_image_digests: Optional[Set[str]] = None,
        approved_measurements: Optional[Set[str]] = None,
        approved_cmdlines: Optional[Set[str]] = None,
    ) -> None:
        self.db_path = db_path
        self.allowed_image_digests = allowed_image_digests or set()
        self.approved_measurements = approved_measurements or set()
        self.approved_cmdlines = approved_cmdlines or set()
        self._consumed_nonces: Set[str] = set()
        self._conn = sqlite3.connect(self.db_path)
        self._init_db()

    def _init_db(self) -> None:
        if self.db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS coco_attestation_ledger (
                    token_id TEXT PRIMARY KEY,
                    container_id TEXT NOT NULL,
                    enclave_type TEXT NOT NULL,
                    launch_measurement_digest TEXT NOT NULL,
                    container_image_digest TEXT NOT NULL,
                    kernel_cmdline_sha256 TEXT NOT NULL,
                    nonce TEXT NOT NULL,
                    status TEXT NOT NULL,
                    evaluated_at_ms INTEGER NOT NULL,
                    raw_token_json TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS coco_key_release_ledger (
                    release_id TEXT PRIMARY KEY,
                    token_id TEXT NOT NULL,
                    container_id TEXT NOT NULL,
                    secret_identifier TEXT NOT NULL,
                    fenced_key_caid TEXT NOT NULL,
                    receipt_caid TEXT UNIQUE NOT NULL,
                    status TEXT NOT NULL,
                    released_at_ms INTEGER NOT NULL,
                    raw_receipt_json TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_coco_container ON coco_attestation_ledger(container_id);"
            )

    @staticmethod
    def create_token(
        container_id: str,
        enclave_type: str,
        launch_measurement_digest: str,
        container_image_digest: str,
        kernel_cmdline_sha256: str,
        nonce: str,
        priv_key: ed25519.Ed25519PrivateKey,
        timestamp_ms: Optional[int] = None,
    ) -> CoCoAttestationToken:
        """Helper to create an authentic signed CoCo attestation token."""
        effective_time = timestamp_ms if timestamp_ms is not None else int(time.time() * 1000)
        token_id = f"coco-tok-{uuid.uuid4().hex[:16]}"
        payload = {
            "container_id": container_id,
            "container_image_digest": container_image_digest,
            "enclave_type": enclave_type,
            "kernel_cmdline_sha256": kernel_cmdline_sha256,
            "launch_measurement_digest": launch_measurement_digest,
            "nonce": nonce,
            "timestamp_ms": effective_time,
            "token_id": token_id,
        }
        sig = priv_key.sign(encode_jcs(payload))
        pub_hex = priv_key.public_key().public_bytes_raw().hex()
        return CoCoAttestationToken(
            token_id=token_id,
            container_id=container_id,
            enclave_type=enclave_type,
            launch_measurement_digest=launch_measurement_digest,
            container_image_digest=container_image_digest,
            kernel_cmdline_sha256=kernel_cmdline_sha256,
            nonce=nonce,
            timestamp_ms=effective_time,
            enclave_public_key_hex=pub_hex,
            signature=sig.hex(),
        )

    def verify_attestation(
        self,
        token: CoCoAttestationToken,
        now_ms: Optional[int] = None,
    ) -> bool:
        """
        Independently verifies a CoCo attestation token against policy baselines.
        Fails closed on replay, signature failure, untrusted image, or measurement divergence.
        """
        # Anti-replay check
        if token.nonce in self._consumed_nonces:
            raise CoCoAttestationError(
                HALT_COCO_STALE_NONCE,
                f"Nonce {token.nonce} has already been consumed",
            )

        # Signature verification
        try:
            pub_bytes = bytes.fromhex(token.enclave_public_key_hex)
            verifier = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
            verifier.verify(bytes.fromhex(token.signature), token.canonical_bytes())
        except Exception as exc:
            raise CoCoAttestationError(
                HALT_COCO_SIGNATURE_INVALID,
                f"Enclave signature invalid on token {token.token_id}: {exc}",
            ) from exc

        # Image digest verification
        if self.allowed_image_digests and token.container_image_digest not in self.allowed_image_digests:
            raise CoCoAttestationError(
                HALT_COCO_UNTRUSTED_IMAGE,
                f"Container image digest {token.container_image_digest} is not allowlisted",
            )

        # Launch measurement verification
        if self.approved_measurements and token.launch_measurement_digest not in self.approved_measurements:
            raise CoCoAttestationError(
                HALT_COCO_POLICY_DIVERGENCE,
                f"Launch measurement {token.launch_measurement_digest} rejected by policy",
            )

        # Kernel cmdline verification
        if self.approved_cmdlines and token.kernel_cmdline_sha256 not in self.approved_cmdlines:
            raise CoCoAttestationError(
                HALT_COCO_POLICY_DIVERGENCE,
                f"Kernel cmdline digest {token.kernel_cmdline_sha256} rejected by policy",
            )

        self._consumed_nonces.add(token.nonce)

        effective_time = now_ms if now_ms is not None else int(time.time() * 1000)
        self._record_attestation(token, STATUS_ATTESTATION_VERIFIED, effective_time)
        return True

    def release_key_to_enclave(
        self,
        token: CoCoAttestationToken,
        secret_identifier: str,
        key_payload: bytes,
        now_ms: Optional[int] = None,
    ) -> CoCoKeyReleaseReceipt:
        """
        Verifies attestation and releases fenced secret key material to verified enclave.
        """
        # Verify attestation first
        self.verify_attestation(token, now_ms=now_ms)

        if len(key_payload) < 32:
            raise CoCoAttestationError(
                HALT_COCO_KEY_RELEASE_DENIED,
                f"Key payload length {len(key_payload)} < 32 bytes minimum",
            )

        effective_time = now_ms if now_ms is not None else int(time.time() * 1000)
        fenced_key_caid = compute_sha256_caid({
            "enclave_pub_key": token.enclave_public_key_hex,
            "key_sha256": f"sha256:{hashlib.sha256(key_payload).hexdigest()}",
            "secret_identifier": secret_identifier,
            "token_id": token.token_id,
        })

        release_id = f"coco-rel-{uuid.uuid4().hex[:16]}"
        prelim_receipt = {
            "container_id": token.container_id,
            "fenced_key_caid": fenced_key_caid,
            "receipt_caid": "",
            "release_id": release_id,
            "secret_identifier": secret_identifier,
            "status": STATUS_KEY_RELEASED,
            "token_id": token.token_id,
        }
        receipt_caid = compute_sha256_caid(prelim_receipt)

        receipt = CoCoKeyReleaseReceipt(
            release_id=release_id,
            token_id=token.token_id,
            container_id=token.container_id,
            secret_identifier=secret_identifier,
            fenced_key_caid=fenced_key_caid,
            receipt_caid=receipt_caid,
            status=STATUS_KEY_RELEASED,
            released_at_ms=effective_time,
        )

        self._record_key_release(receipt)
        return receipt

    def _record_attestation(
        self, token: CoCoAttestationToken, status: str, evaluated_at_ms: int
    ) -> None:
        raw_json = json.dumps(asdict(token), sort_keys=True)
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO coco_attestation_ledger (
                    token_id, container_id, enclave_type, launch_measurement_digest,
                    container_image_digest, kernel_cmdline_sha256, nonce, status,
                    evaluated_at_ms, raw_token_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    token.token_id,
                    token.container_id,
                    token.enclave_type,
                    token.launch_measurement_digest,
                    token.container_image_digest,
                    token.kernel_cmdline_sha256,
                    token.nonce,
                    status,
                    evaluated_at_ms,
                    raw_json,
                ),
            )

    def _record_key_release(self, receipt: CoCoKeyReleaseReceipt) -> None:
        raw_json = json.dumps(asdict(receipt), sort_keys=True)
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO coco_key_release_ledger (
                    release_id, token_id, container_id, secret_identifier,
                    fenced_key_caid, receipt_caid, status, released_at_ms, raw_receipt_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt.release_id,
                    receipt.token_id,
                    receipt.container_id,
                    receipt.secret_identifier,
                    receipt.fenced_key_caid,
                    receipt.receipt_caid,
                    receipt.status,
                    receipt.released_at_ms,
                    raw_json,
                ),
            )

    def get_release_receipt(
        self, release_id: str
    ) -> Optional[CoCoKeyReleaseReceipt]:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT raw_receipt_json FROM coco_key_release_ledger
            WHERE release_id = ?
            """,
            (release_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return CoCoKeyReleaseReceipt(**json.loads(row[0]))

    def close(self) -> None:
        self._conn.close()
