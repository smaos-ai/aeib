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
src/enclave_bpf_policy_loader.py — Enclave-Attested eBPF Policy Loader Scaffold.

Part of Sovereign Multi-Agent OS (SMAOS) / AEIB Enterprise Gateway.
Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model as an enclave-attested
eBPF policy packaging, encrypted delivery, and remote attestation verification prototype.

Honest Platform Boundary (Software Scaffold & Simulated Prototype):
  - This module is a software scaffold and simulation prototype for enclave-gated eBPF policy
    distribution and remote attestation verification.
  - It simulates Intel SGX / AMD SEV-SNP hardware attestation evidence verification, AES-256-GCM
    policy payload decryption, and kernel-space eBPF staging without invoking native kernel BPF
    syscalls or hardware enclave drivers.
  - Operational mode: scaffold / simulated policy loader.

Architectural Invariants:
1. Hardware Remote Attestation Gate:
   - Evaluates hardware measurements (PCR-11, SEV launch digest, TDX RTMR) and Ed25519 enclave
     signatures with nonce freshness to prevent replay attacks.
2. AEAD Encrypted Policy Delivery:
   - In-kernel policies are sealed using AES-256-GCM authenticated encryption. Decryption occurs
     strictly within the verified enclave context.
3. Monotonic Policy Epoch Advancing:
   - Re-keying requires epoch_new == epoch_active + 1. Rejects stale or out-of-order policy packages.
4. Fail-Closed Codes:
   - HALT_BPF_LOADER_ATTESTATION_FAILED
   - HALT_BPF_LOADER_NON_MONOTONIC_EPOCH
   - HALT_BPF_LOADER_MEASUREMENT_MISMATCH
   - HALT_BPF_LOADER_DECRYPTION_FAILED
   - HALT_BPF_LOADER_DIGEST_MISMATCH
   - HALT_BPF_LOADER_UNAUTHORIZED_TARGET
   - HALT_BPF_LOADER_EXPIRED_WARRANT
5. RFC 8785 Canonical Auditing & SQLite-WAL Durability:
   - All deployments, nonces, and attestation receipts are sealed via JCS and persisted to SQLite-WAL.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from src.jcs_canonicalizer import encode_jcs

# Status Constants
STATUS_POLICY_STAGED: str = "POLICY_STAGED"
STATUS_POLICY_ACTIVE: str = "POLICY_ACTIVE"
STATUS_POLICY_REJECTED: str = "POLICY_REJECTED"

# Fail-Closed Rejection Codes
HALT_BPF_LOADER_ATTESTATION_FAILED: str = "HALT_BPF_LOADER_ATTESTATION_FAILED"
HALT_BPF_LOADER_NON_MONOTONIC_EPOCH: str = "HALT_BPF_LOADER_NON_MONOTONIC_EPOCH"
HALT_BPF_LOADER_MEASUREMENT_MISMATCH: str = "HALT_BPF_LOADER_MEASUREMENT_MISMATCH"
HALT_BPF_LOADER_DECRYPTION_FAILED: str = "HALT_BPF_LOADER_DECRYPTION_FAILED"
HALT_BPF_LOADER_DIGEST_MISMATCH: str = "HALT_BPF_LOADER_DIGEST_MISMATCH"
HALT_BPF_LOADER_UNAUTHORIZED_TARGET: str = "HALT_BPF_LOADER_UNAUTHORIZED_TARGET"
HALT_BPF_LOADER_EXPIRED_WARRANT: str = "HALT_BPF_LOADER_EXPIRED_WARRANT"

VALID_ENCLAVE_TYPES: Set[str] = {"AMD_SEV_SNP", "INTEL_TDX", "INTEL_SGX", "AWS_NITRO", "APPLE_ENCLAVE", "TPM20"}
MAX_ALLOWED_CLOCK_SKEW_MS: int = 30_000  # claim: config - 30s max clock skew


def compute_sha256(data: bytes) -> str:
    """Compute standard lowercase hex SHA-256 digest."""
    return hashlib.sha256(data).hexdigest()


def compute_wilson_ci_bps(k: int, n: int, z: float = 1.95996) -> Tuple[int, int]:
    """Compute conservative Wilson 95% confidence interval in basis points."""
    if n <= 0 or k < 0 or k > n:
        return 0, 0
    p = k / n
    denom = 1.0 + (z * z) / n
    center = (p + (z * z) / (2.0 * n)) / denom
    half_width = (z * math.sqrt((p * (1.0 - p) + (z * z) / (4.0 * n)) / n)) / denom
    low = max(0.0, center - half_width)
    high = min(1.0, center + half_width)
    return round(low * 10000), round(high * 10000)


@dataclass(frozen=True)
class EnclaveAttestationEvidence:
    """Remote hardware attestation evidence presented by an agent enclave."""
    enclave_id: str
    enclave_type: str
    measurement_hash: str
    nonce: str
    enclave_pubkey_hex: str
    signature_hex: str
    timestamp_ms: int

    def __post_init__(self) -> None:
        if not self.enclave_id or not isinstance(self.enclave_id, str):
            raise ValueError("enclave_id must be a non-empty string")
        if self.enclave_type.upper() not in VALID_ENCLAVE_TYPES:
            raise ValueError(f"Unsupported enclave type: {self.enclave_type}")
        if len(self.measurement_hash) != 64:
            raise ValueError("measurement_hash must be a 64-char hex SHA-256 string")
        if len(self.nonce) < 16:
            raise ValueError("nonce must be at least 16 characters for replay protection")
        if len(self.enclave_pubkey_hex) != 64:
            raise ValueError("enclave_pubkey_hex must be a 64-char hex Ed25519 public key")
        if len(self.signature_hex) != 128:
            raise ValueError("signature_hex must be a 128-char hex Ed25519 signature")
        if self.timestamp_ms <= 0:
            raise ValueError("timestamp_ms must be positive")

    def compute_canonical_message(self) -> bytes:
        """Compute message signed by the enclave identity key."""
        doc = {
            "enclave_id": self.enclave_id,
            "enclave_type": self.enclave_type.upper(),
            "measurement_hash": self.measurement_hash,
            "nonce": self.nonce,
            "timestamp_ms": self.timestamp_ms,
        }
        return encode_jcs(doc)


@dataclass(frozen=True)
class EncryptedBpfPolicyPackage:
    """Encrypted eBPF policy container sealed under AES-256-GCM."""
    package_id: str
    target_enclave_id: str
    expected_measurement_hash: str
    policy_epoch: int
    encrypted_payload_hex: str
    nonce_hex: str
    aad_hex: str
    payload_sha256: str
    created_at_ms: int
    expires_at_ms: int

    def __post_init__(self) -> None:
        if not self.package_id:
            raise ValueError("package_id must be non-empty")
        if not self.target_enclave_id:
            raise ValueError("target_enclave_id must be non-empty")
        if len(self.expected_measurement_hash) != 64:
            raise ValueError("expected_measurement_hash must be 64-char hex")
        if self.policy_epoch <= 0:
            raise ValueError("policy_epoch must be positive")
        if not self.encrypted_payload_hex:
            raise ValueError("encrypted_payload_hex must be non-empty")
        if len(self.nonce_hex) != 24:
            raise ValueError("nonce_hex must be 24-char hex (12 bytes for AES-GCM)")
        if len(self.payload_sha256) != 64:
            raise ValueError("payload_sha256 must be 64-char hex")
        if self.expires_at_ms <= self.created_at_ms:
            raise ValueError("expires_at_ms must be strictly greater than created_at_ms")


@dataclass(frozen=True)
class BpfPolicyDeploymentVerdict:
    """Cryptographic audit verdict of policy deployment."""
    package_id: str
    target_enclave_id: str
    policy_epoch: int
    status: str
    reason: str
    applied_at_ms: int
    caid: str

    def __post_init__(self) -> None:
        if not self.package_id:
            raise ValueError("package_id must be non-empty")
        if not self.target_enclave_id:
            raise ValueError("target_enclave_id must be non-empty")
        if self.policy_epoch <= 0:
            raise ValueError("policy_epoch must be positive")
        if not self.caid:
            raise ValueError("caid must be non-empty")


class EnclaveAttestedBpfPolicyLoader:
    """
    Enclave-Attested eBPF Policy Loader Scaffold.
    Enforces hardware remote attestation, AES-256-GCM authenticated decryption,
    and monotonic epoch gating for in-kernel policy distribution.
    """

    def __init__(
        self,
        loader_id: str,
        db_path: str = ":memory:",
        max_clock_skew_ms: int = MAX_ALLOWED_CLOCK_SKEW_MS,
    ) -> None:
        if not loader_id or not isinstance(loader_id, str):
            raise ValueError("loader_id must be a non-empty string")

        self.loader_id = loader_id
        self.db_path = db_path
        self.max_clock_skew_ms = max_clock_skew_ms

        self._active_epochs: Dict[str, int] = {}             # key: enclave_id -> active policy epoch
        self._pinned_measurements: Dict[str, str] = {}       # key: enclave_id -> pinned measurement hash
        self._used_nonces: Set[str] = set()
        self._staged_policies: Dict[str, Dict[str, Any]] = {} # key: enclave_id -> decrypted policy dict

        self._conn = sqlite3.connect(self.db_path)
        self._init_sqlite_schema()

    def _init_sqlite_schema(self) -> None:
        """Initialize SQLite tables and WAL configuration."""
        with self._conn:
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS bpf_enclave_registry (
                    enclave_id TEXT PRIMARY KEY,
                    enclave_type TEXT NOT NULL,
                    pinned_measurement_hex TEXT NOT NULL,
                    enclave_pubkey_hex TEXT NOT NULL,
                    active_epoch INTEGER NOT NULL,
                    updated_at_ms INTEGER NOT NULL
                );
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS bpf_policy_deployments (
                    caid TEXT PRIMARY KEY,
                    package_id TEXT NOT NULL,
                    target_enclave_id TEXT NOT NULL,
                    policy_epoch INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    applied_at_ms INTEGER NOT NULL
                );
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS bpf_attestation_audit (
                    nonce TEXT PRIMARY KEY,
                    enclave_id TEXT NOT NULL,
                    measurement_hash TEXT NOT NULL,
                    verified_at_ms INTEGER NOT NULL
                );
                """
            )

    def register_enclave(
        self,
        enclave_id: str,
        enclave_type: str,
        pinned_measurement_hex: str,
        enclave_pubkey_hex: str,
        initial_epoch: int = 0,
        now_ms: Optional[int] = None,
    ) -> None:
        """Register an authorized enclave and pin its expected hardware measurement."""
        if not enclave_id or not isinstance(enclave_id, str):
            raise ValueError("enclave_id must be a non-empty string")
        if enclave_type.upper() not in VALID_ENCLAVE_TYPES:
            raise ValueError(f"Unsupported enclave type: {enclave_type}")
        if len(pinned_measurement_hex) != 64:
            raise ValueError("pinned_measurement_hex must be a 64-char hex string")
        if len(enclave_pubkey_hex) != 64:
            raise ValueError("enclave_pubkey_hex must be a 64-char hex string")
        if initial_epoch < 0:
            raise ValueError("initial_epoch cannot be negative")
        if now_ms is None:
            now_ms = int(time.time() * 1000)

        self._pinned_measurements[enclave_id] = pinned_measurement_hex
        self._active_epochs[enclave_id] = initial_epoch

        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO bpf_enclave_registry (
                    enclave_id, enclave_type, pinned_measurement_hex, enclave_pubkey_hex, active_epoch, updated_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    enclave_id,
                    enclave_type.upper(),
                    pinned_measurement_hex,
                    enclave_pubkey_hex,
                    initial_epoch,
                    now_ms,
                ),
            )

    def create_encrypted_package(
        self,
        package_id: str,
        target_enclave_id: str,
        expected_measurement_hash: str,
        policy_epoch: int,
        policy_payload: Dict[str, Any],
        encryption_key: bytes,
        ttl_ms: int = 120_000,
        now_ms: Optional[int] = None,
    ) -> EncryptedBpfPolicyPackage:
        """
        Encrypt a raw eBPF policy dictionary under AES-256-GCM.
        Returns a sealed EncryptedBpfPolicyPackage.
        """
        if len(encryption_key) != 32:
            raise ValueError("encryption_key must be exactly 32 bytes (AES-256)")
        if now_ms is None:
            now_ms = int(time.time() * 1000)

        payload_bytes = encode_jcs(policy_payload)
        payload_sha256 = compute_sha256(payload_bytes)

        # 12-byte AESGCM nonce
        aes_nonce = os.urandom(12)
        aad_doc = {
            "expected_measurement_hash": expected_measurement_hash,
            "package_id": package_id,
            "policy_epoch": policy_epoch,
            "target_enclave_id": target_enclave_id,
        }
        aad_bytes = encode_jcs(aad_doc)

        aesgcm = AESGCM(encryption_key)
        ciphertext = aesgcm.encrypt(aes_nonce, payload_bytes, aad_bytes)

        return EncryptedBpfPolicyPackage(
            package_id=package_id,
            target_enclave_id=target_enclave_id,
            expected_measurement_hash=expected_measurement_hash,
            policy_epoch=policy_epoch,
            encrypted_payload_hex=ciphertext.hex(),
            nonce_hex=aes_nonce.hex(),
            aad_hex=aad_bytes.hex(),
            payload_sha256=payload_sha256,
            created_at_ms=now_ms,
            expires_at_ms=now_ms + ttl_ms,
        )

    def deploy_policy_package(
        self,
        package: EncryptedBpfPolicyPackage,
        evidence: EnclaveAttestationEvidence,
        decryption_key: bytes,
        now_ms: Optional[int] = None,
    ) -> Tuple[BpfPolicyDeploymentVerdict, Optional[Dict[str, Any]]]:
        """
        Verify remote attestation evidence, decrypt policy payload, and stage for in-kernel execution.
        Returns (BpfPolicyDeploymentVerdict, decrypted_policy_dict).
        """
        if now_ms is None:
            now_ms = int(time.time() * 1000)

        # 1. Package expiration check
        if now_ms > package.expires_at_ms:
            return self._build_verdict(
                package.package_id,
                package.target_enclave_id,
                package.policy_epoch,
                STATUS_POLICY_REJECTED,
                HALT_BPF_LOADER_EXPIRED_WARRANT,
                now_ms,
            ), None

        # 2. Target enclave ID validation
        if package.target_enclave_id != evidence.enclave_id:
            return self._build_verdict(
                package.package_id,
                package.target_enclave_id,
                package.policy_epoch,
                STATUS_POLICY_REJECTED,
                HALT_BPF_LOADER_UNAUTHORIZED_TARGET,
                now_ms,
            ), None

        # 3. Clock-skew and freshness validation
        if abs(now_ms - evidence.timestamp_ms) > self.max_clock_skew_ms:
            return self._build_verdict(
                package.package_id,
                package.target_enclave_id,
                package.policy_epoch,
                STATUS_POLICY_REJECTED,
                HALT_BPF_LOADER_ATTESTATION_FAILED,
                now_ms,
            ), None

        # 4. Anti-replay nonce freshness check
        if evidence.nonce in self._used_nonces:
            return self._build_verdict(
                package.package_id,
                package.target_enclave_id,
                package.policy_epoch,
                STATUS_POLICY_REJECTED,
                HALT_BPF_LOADER_ATTESTATION_FAILED,
                now_ms,
            ), None

        # 5. Pinned hardware measurement verification
        pinned_meas = self._pinned_measurements.get(evidence.enclave_id)
        if pinned_meas is None or evidence.measurement_hash != pinned_meas:
            return self._build_verdict(
                package.package_id,
                package.target_enclave_id,
                package.policy_epoch,
                STATUS_POLICY_REJECTED,
                HALT_BPF_LOADER_MEASUREMENT_MISMATCH,
                now_ms,
            ), None

        if evidence.measurement_hash != package.expected_measurement_hash:
            return self._build_verdict(
                package.package_id,
                package.target_enclave_id,
                package.policy_epoch,
                STATUS_POLICY_REJECTED,
                HALT_BPF_LOADER_MEASUREMENT_MISMATCH,
                now_ms,
            ), None

        # 6. Verify enclave remote attestation signature
        try:
            pubkey_bytes = bytes.fromhex(evidence.enclave_pubkey_hex)
            sig_bytes = bytes.fromhex(evidence.signature_hex)
            if len(pubkey_bytes) != 32 or len(sig_bytes) != 64:
                return self._build_verdict(
                    package.package_id,
                    package.target_enclave_id,
                    package.policy_epoch,
                    STATUS_POLICY_REJECTED,
                    HALT_BPF_LOADER_ATTESTATION_FAILED,
                    now_ms,
                ), None
            public_key = ed25519.Ed25519PublicKey.from_public_bytes(pubkey_bytes)
            public_key.verify(sig_bytes, evidence.compute_canonical_message())
        except (ValueError, InvalidSignature):
            return self._build_verdict(
                package.package_id,
                package.target_enclave_id,
                package.policy_epoch,
                STATUS_POLICY_REJECTED,
                HALT_BPF_LOADER_ATTESTATION_FAILED,
                now_ms,
            ), None

        # 7. Monotonic policy epoch check
        current_epoch = self._active_epochs.get(evidence.enclave_id, 0)
        if package.policy_epoch != current_epoch + 1:
            return self._build_verdict(
                package.package_id,
                package.target_enclave_id,
                package.policy_epoch,
                STATUS_POLICY_REJECTED,
                HALT_BPF_LOADER_NON_MONOTONIC_EPOCH,
                now_ms,
            ), None

        # 8. Authenticated decryption under AES-256-GCM
        try:
            aesgcm = AESGCM(decryption_key)
            ciphertext = bytes.fromhex(package.encrypted_payload_hex)
            nonce = bytes.fromhex(package.nonce_hex)
            aad = bytes.fromhex(package.aad_hex)
            plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, aad)
        except (ValueError, InvalidTag):
            return self._build_verdict(
                package.package_id,
                package.target_enclave_id,
                package.policy_epoch,
                STATUS_POLICY_REJECTED,
                HALT_BPF_LOADER_DECRYPTION_FAILED,
                now_ms,
            ), None

        # 9. Verify decrypted payload digest
        if compute_sha256(plaintext_bytes) != package.payload_sha256:
            return self._build_verdict(
                package.package_id,
                package.target_enclave_id,
                package.policy_epoch,
                STATUS_POLICY_REJECTED,
                HALT_BPF_LOADER_DIGEST_MISMATCH,
                now_ms,
            ), None

        decrypted_policy = json.loads(plaintext_bytes.decode("utf-8"))

        # Update in-memory state
        self._used_nonces.add(evidence.nonce)
        self._active_epochs[evidence.enclave_id] = package.policy_epoch
        self._staged_policies[evidence.enclave_id] = decrypted_policy

        # Persist nonce audit to SQLite
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO bpf_attestation_audit (nonce, enclave_id, measurement_hash, verified_at_ms)
                VALUES (?, ?, ?, ?);
                """,
                (evidence.nonce, evidence.enclave_id, evidence.measurement_hash, now_ms),
            )
            self._conn.execute(
                """
                UPDATE bpf_enclave_registry
                SET active_epoch = ?, updated_at_ms = ?
                WHERE enclave_id = ?;
                """,
                (package.policy_epoch, now_ms, evidence.enclave_id),
            )

        verdict = self._build_verdict(
            package.package_id,
            package.target_enclave_id,
            package.policy_epoch,
            STATUS_POLICY_STAGED,
            "ATTESTATION_VERIFIED_AND_POLICY_STAGED",
            now_ms,
        )
        return verdict, decrypted_policy

    def _build_verdict(
        self,
        package_id: str,
        target_enclave_id: str,
        policy_epoch: int,
        status: str,
        reason: str,
        now_ms: int,
    ) -> BpfPolicyDeploymentVerdict:
        """Construct, seal via RFC 8785 JCS, and persist a deployment verdict."""
        doc = {
            "package_id": package_id,
            "policy_epoch": policy_epoch,
            "reason": reason,
            "status": status,
            "target_enclave_id": target_enclave_id,
            "timestamp_ms": now_ms,
        }
        caid = compute_sha256(encode_jcs(doc))

        verdict = BpfPolicyDeploymentVerdict(
            package_id=package_id,
            target_enclave_id=target_enclave_id,
            policy_epoch=policy_epoch,
            status=status,
            reason=reason,
            applied_at_ms=now_ms,
            caid=caid,
        )

        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO bpf_policy_deployments (
                    caid, package_id, target_enclave_id, policy_epoch, status, reason, applied_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    verdict.caid,
                    verdict.package_id,
                    verdict.target_enclave_id,
                    verdict.policy_epoch,
                    verdict.status,
                    verdict.reason,
                    verdict.applied_at_ms,
                ),
            )

        return verdict

    def get_staged_policy(self, enclave_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve the currently staged in-kernel policy for an enclave."""
        return self._staged_policies.get(enclave_id)
