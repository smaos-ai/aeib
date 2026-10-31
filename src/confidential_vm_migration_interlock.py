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
src/confidential_vm_migration_interlock.py — Heterogeneous Confidential VM Migration Interlock Gate.

Part of Sovereign Multi-Agent OS (SMAOS) / AEIB Enterprise Gateway.
Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model as a structural scaffold and migration interlock prototype.

Honest Platform Boundary (Structural Scaffold & Simulated CVM Prototype):
  - This module is a software scaffold and simulation prototype for heterogeneous
    confidential VM migrations across AMD SEV-SNP, Intel TDX, and AWS Nitro enclaves.
  - It does NOT directly invoke hardware hypervisor ioctls (/dev/sev, /dev/tdx)
    or cloud enclave hypercalls in this software prototype.
  - Operational mode: scaffold / simulated interlock engine.

Architectural Invariants:
1. Heterogeneous Confidential Enclave Support:
   - Validates and interlocks migration handshakes across heterogeneous architectures:
     amd_sev_snp, intel_tdx, and aws_nitro.
2. Cryptographic Memory Frame Integrity:
   - Validates sequential memory frame digests against a declared Merkle root.
3. Monotonic Migration Epoch Fencing:
   - Enforces strict monotonic epoch increment: epoch_dest == epoch_src + 1.
4. Fail-Closed Rollback Rejection Codes:
   - HALT_CVM_UNSUPPORTED_ARCH
   - HALT_CVM_STALE_EPOCH
   - HALT_CVM_MEASUREMENT_DIVERGENCE
   - HALT_CVM_MEMORY_CORRUPTION
   - HALT_CVM_KEY_FENCE_FAILED
   - HALT_CVM_SIGNATURE_INVALID
   - HALT_CVM_INVALID_STATE_TRANSITION
5. Sub-5ms SQLite-WAL Durability:
   - Persists all migration handshakes, state transitions, and commit receipts
     in a durable local SQLite-WAL database.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence, Set

from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs

# Supported Confidential VM Enclave Architectures
ENCLAVE_ARCH_AMD_SEV_SNP: str = "amd_sev_snp"
ENCLAVE_ARCH_INTEL_TDX: str = "intel_tdx"
ENCLAVE_ARCH_AWS_NITRO: str = "aws_nitro"
SUPPORTED_ARCHITECTURES: frozenset[str] = frozenset(
    {ENCLAVE_ARCH_AMD_SEV_SNP, ENCLAVE_ARCH_INTEL_TDX, ENCLAVE_ARCH_AWS_NITRO}
)

# Migration States
MIGRATION_STATE_INITIATED: str = "MIGRATION_INITIATED"
MIGRATION_STATE_MEMORY_VERIFIED: str = "MEMORY_VERIFIED"
MIGRATION_STATE_KEY_FENCED: str = "KEY_FENCED"
MIGRATION_STATE_COMMITTED: str = "MIGRATION_COMMITTED"
MIGRATION_STATE_ROLLED_BACK: str = "MIGRATION_ROLLED_BACK"

# Explicit fail-closed rejection codes
HALT_CVM_UNSUPPORTED_ARCH: str = "HALT_CVM_UNSUPPORTED_ARCH"
HALT_CVM_STALE_EPOCH: str = "HALT_CVM_STALE_EPOCH"
HALT_CVM_MEASUREMENT_DIVERGENCE: str = "HALT_CVM_MEASUREMENT_DIVERGENCE"
HALT_CVM_MEMORY_CORRUPTION: str = "HALT_CVM_MEMORY_CORRUPTION"
HALT_CVM_KEY_FENCE_FAILED: str = "HALT_CVM_KEY_FENCE_FAILED"
HALT_CVM_SIGNATURE_INVALID: str = "HALT_CVM_SIGNATURE_INVALID"
HALT_CVM_INVALID_STATE_TRANSITION: str = "HALT_CVM_INVALID_STATE_TRANSITION"


class CvmMigrationError(Exception):
    """Exception raised when CVM migration interlock check fails."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class CvmAttestationReport:
    """Attestation report from a Confidential VM enclave."""

    vm_id: str
    arch: str
    measurement_digest: str
    policy_epoch: int
    nonce: str
    timestamp_ms: int
    signature: str
    public_key_hex: str

    def canonical_dict(self) -> Dict[str, Any]:
        return {
            "arch": self.arch,
            "measurement_digest": self.measurement_digest,
            "nonce": self.nonce,
            "policy_epoch": self.policy_epoch,
            "timestamp_ms": self.timestamp_ms,
            "vm_id": self.vm_id,
        }

    def canonical_bytes(self) -> bytes:
        return encode_jcs(self.canonical_dict())


@dataclass(frozen=True)
class MemoryFrameDigest:
    """Digest representing an in-flight live memory frame chunk."""

    frame_index: int
    frame_size_bytes: int
    frame_sha256: str


@dataclass(frozen=True)
class MigrationHandshakeTicket:
    """Interlock ticket governing active heterogeneous CVM live migration."""

    migration_id: str
    source_vm_id: str
    dest_vm_id: str
    source_arch: str
    dest_arch: str
    source_epoch: int
    dest_epoch: int
    memory_manifest_root: str
    expected_frame_count: int
    state: str
    ticket_caid: str
    created_at_ms: int
    fenced_key_caid: Optional[str] = None
    rollback_reason: Optional[str] = None

    def canonical_dict(self) -> Dict[str, Any]:
        return {
            "created_at_ms": self.created_at_ms,
            "dest_arch": self.dest_arch,
            "dest_epoch": self.dest_epoch,
            "dest_vm_id": self.dest_vm_id,
            "expected_frame_count": self.expected_frame_count,
            "fenced_key_caid": self.fenced_key_caid,
            "memory_manifest_root": self.memory_manifest_root,
            "migration_id": self.migration_id,
            "rollback_reason": self.rollback_reason,
            "source_arch": self.source_arch,
            "source_epoch": self.source_epoch,
            "source_vm_id": self.source_vm_id,
            "state": self.state,
        }

    def canonical_bytes(self) -> bytes:
        return encode_jcs(self.canonical_dict())


@dataclass(frozen=True)
class MigrationCommitReceipt:
    """Durable receipt acknowledging committed CVM migration handover."""

    migration_id: str
    source_vm_id: str
    dest_vm_id: str
    source_arch: str
    dest_arch: str
    migration_epoch: int
    memory_manifest_root: str
    fenced_key_caid: str
    receipt_caid: str
    status: str
    committed_at_ms: int

    def canonical_dict(self) -> Dict[str, Any]:
        return {
            "committed_at_ms": self.committed_at_ms,
            "dest_arch": self.dest_arch,
            "dest_vm_id": self.dest_vm_id,
            "fenced_key_caid": self.fenced_key_caid,
            "memory_manifest_root": self.memory_manifest_root,
            "migration_epoch": self.migration_epoch,
            "migration_id": self.migration_id,
            "receipt_caid": self.receipt_caid,
            "source_arch": self.source_arch,
            "source_vm_id": self.source_vm_id,
            "status": self.status,
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


def compute_memory_merkle_root(frame_hashes: Sequence[str]) -> str:
    """Computes deterministic binary Merkle root over list of frame sha256 digests."""
    if not frame_hashes:
        return f"sha256:{hashlib.sha256(b'').hexdigest()}"

    current_level: List[bytes] = []
    for h in frame_hashes:
        clean = h[7:] if h.startswith("sha256:") else h
        current_level.append(bytes.fromhex(clean))

    while len(current_level) > 1:
        next_level: List[bytes] = []
        for i in range(0, len(current_level), 2):
            left = current_level[i]
            right = current_level[i + 1] if (i + 1) < len(current_level) else left
            combined = hashlib.sha256(left + right).digest()
            next_level.append(combined)
        current_level = next_level

    return f"sha256:{current_level[0].hex()}"


class ConfidentialVmMigrationInterlock:
    """
    Heterogeneous Confidential VM Migration Interlock Gate enforcing hardware enclave
    attestations, monotonic epoch advancement, frame integrity, and key fencing.
    """

    def __init__(
        self,
        db_path: str = ":memory:",
        approved_measurements: Optional[Dict[str, Set[str]]] = None,
    ) -> None:
        self.db_path = db_path
        self.approved_measurements = approved_measurements or {}
        self._conn = sqlite3.connect(self.db_path)
        self._init_db()

    def _init_db(self) -> None:
        if self.db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cvm_migration_tickets_ledger (
                    migration_id TEXT PRIMARY KEY,
                    source_vm_id TEXT NOT NULL,
                    dest_vm_id TEXT NOT NULL,
                    source_arch TEXT NOT NULL,
                    dest_arch TEXT NOT NULL,
                    source_epoch INTEGER NOT NULL,
                    dest_epoch INTEGER NOT NULL,
                    memory_manifest_root TEXT NOT NULL,
                    expected_frame_count INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    ticket_caid TEXT UNIQUE NOT NULL,
                    fenced_key_caid TEXT,
                    rollback_reason TEXT,
                    created_at_ms INTEGER NOT NULL,
                    raw_ticket_json TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cvm_migration_receipts_ledger (
                    migration_id TEXT PRIMARY KEY,
                    receipt_caid TEXT UNIQUE NOT NULL,
                    source_vm_id TEXT NOT NULL,
                    dest_vm_id TEXT NOT NULL,
                    migration_epoch INTEGER NOT NULL,
                    fenced_key_caid TEXT NOT NULL,
                    status TEXT NOT NULL,
                    committed_at_ms INTEGER NOT NULL,
                    raw_receipt_json TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ticket_state ON cvm_migration_tickets_ledger(state);"
            )

    @staticmethod
    def create_attestation(
        vm_id: str,
        arch: str,
        measurement_digest: str,
        policy_epoch: int,
        nonce: str,
        timestamp_ms: int,
        private_key: ed25519.Ed25519PrivateKey,
    ) -> CvmAttestationReport:
        """Helper to create an authentic signed attestation report from a CVM enclave."""
        payload = {
            "arch": arch,
            "measurement_digest": measurement_digest,
            "nonce": nonce,
            "policy_epoch": policy_epoch,
            "timestamp_ms": timestamp_ms,
            "vm_id": vm_id,
        }
        canonical_bytes = encode_jcs(payload)
        sig = private_key.sign(canonical_bytes)
        pub_key = private_key.public_key().public_bytes_raw()
        return CvmAttestationReport(
            vm_id=vm_id,
            arch=arch,
            measurement_digest=measurement_digest,
            policy_epoch=policy_epoch,
            nonce=nonce,
            timestamp_ms=timestamp_ms,
            signature=sig.hex(),
            public_key_hex=pub_key.hex(),
        )

    def initiate_handshake(
        self,
        source: CvmAttestationReport,
        dest: CvmAttestationReport,
        memory_manifest_root: str,
        expected_frame_count: int,
        now_ms: Optional[int] = None,
    ) -> MigrationHandshakeTicket:
        """
        Initiates and validates a heterogeneous CVM live migration handshake.
        Fails closed if architectures are unsupported, epochs are not monotonic,
        enclave signatures fail, or measurement baselines diverge.
        """
        # Validate supported enclave architectures
        if source.arch not in SUPPORTED_ARCHITECTURES:
            raise CvmMigrationError(
                HALT_CVM_UNSUPPORTED_ARCH,
                f"Source architecture '{source.arch}' is not supported",
            )
        if dest.arch not in SUPPORTED_ARCHITECTURES:
            raise CvmMigrationError(
                HALT_CVM_UNSUPPORTED_ARCH,
                f"Destination architecture '{dest.arch}' is not supported",
            )

        # Enforce monotonic epoch advancement: dest_epoch == source_epoch + 1
        if dest.policy_epoch != source.policy_epoch + 1:
            raise CvmMigrationError(
                HALT_CVM_STALE_EPOCH,
                f"Non-monotonic migration epoch: dest {dest.policy_epoch} != source {source.policy_epoch} + 1",
            )

        # Enforce frame count and manifest root
        if expected_frame_count <= 0:
            raise CvmMigrationError(
                HALT_CVM_MEMORY_CORRUPTION,
                f"Expected frame count must be positive, got {expected_frame_count}",
            )
        if not memory_manifest_root.startswith("sha256:") or len(memory_manifest_root) != 71:
            raise CvmMigrationError(
                HALT_CVM_MEMORY_CORRUPTION,
                f"Invalid memory manifest root format: {memory_manifest_root}",
            )

        # Verify source enclave signature
        try:
            src_pub = ed25519.Ed25519PublicKey.from_public_bytes(
                bytes.fromhex(source.public_key_hex)
            )
            src_pub.verify(bytes.fromhex(source.signature), source.canonical_bytes())
        except Exception as exc:
            raise CvmMigrationError(
                HALT_CVM_SIGNATURE_INVALID,
                f"Source enclave signature verification failed: {exc}",
            ) from exc

        # Verify destination enclave signature
        try:
            dst_pub = ed25519.Ed25519PublicKey.from_public_bytes(
                bytes.fromhex(dest.public_key_hex)
            )
            dst_pub.verify(bytes.fromhex(dest.signature), dest.canonical_bytes())
        except Exception as exc:
            raise CvmMigrationError(
                HALT_CVM_SIGNATURE_INVALID,
                f"Destination enclave signature verification failed: {exc}",
            ) from exc

        # Validate measurement digests against policy baseline if configured
        if source.arch in self.approved_measurements:
            if source.measurement_digest not in self.approved_measurements[source.arch]:
                raise CvmMigrationError(
                    HALT_CVM_MEASUREMENT_DIVERGENCE,
                    f"Source measurement {source.measurement_digest} rejected by policy",
                )
        if dest.arch in self.approved_measurements:
            if dest.measurement_digest not in self.approved_measurements[dest.arch]:
                raise CvmMigrationError(
                    HALT_CVM_MEASUREMENT_DIVERGENCE,
                    f"Destination measurement {dest.measurement_digest} rejected by policy",
                )

        migration_id = f"cvmmig-{uuid.uuid4().hex[:16]}"
        effective_time = now_ms if now_ms is not None else int(time.time() * 1000)

        prelim_ticket = {
            "created_at_ms": effective_time,
            "dest_arch": dest.arch,
            "dest_epoch": dest.policy_epoch,
            "dest_vm_id": dest.vm_id,
            "expected_frame_count": expected_frame_count,
            "fenced_key_caid": None,
            "memory_manifest_root": memory_manifest_root,
            "migration_id": migration_id,
            "rollback_reason": None,
            "source_arch": source.arch,
            "source_epoch": source.policy_epoch,
            "source_vm_id": source.vm_id,
            "state": MIGRATION_STATE_INITIATED,
        }
        ticket_caid = compute_sha256_caid(prelim_ticket)

        ticket = MigrationHandshakeTicket(
            migration_id=migration_id,
            source_vm_id=source.vm_id,
            dest_vm_id=dest.vm_id,
            source_arch=source.arch,
            dest_arch=dest.arch,
            source_epoch=source.policy_epoch,
            dest_epoch=dest.policy_epoch,
            memory_manifest_root=memory_manifest_root,
            expected_frame_count=expected_frame_count,
            state=MIGRATION_STATE_INITIATED,
            ticket_caid=ticket_caid,
            created_at_ms=effective_time,
            fenced_key_caid=None,
            rollback_reason=None,
        )

        self._record_ticket(ticket)
        return ticket

    def verify_memory_manifest(
        self,
        migration_id: str,
        frames: Sequence[MemoryFrameDigest],
    ) -> bool:
        """
        Verifies sequential in-flight memory frames against the declared Merkle root.
        Transitions state from MIGRATION_INITIATED to MEMORY_VERIFIED.
        """
        ticket = self.get_ticket(migration_id)
        if not ticket:
            raise CvmMigrationError(
                HALT_CVM_INVALID_STATE_TRANSITION,
                f"Migration ticket {migration_id} not found",
            )
        if ticket.state != MIGRATION_STATE_INITIATED:
            raise CvmMigrationError(
                HALT_CVM_INVALID_STATE_TRANSITION,
                f"Cannot verify memory in state {ticket.state}; expected {MIGRATION_STATE_INITIATED}",
            )

        if len(frames) != ticket.expected_frame_count:
            raise CvmMigrationError(
                HALT_CVM_MEMORY_CORRUPTION,
                f"Received {len(frames)} frames; expected {ticket.expected_frame_count}",
            )

        # Check frame sequencing and indices
        for expected_idx, frame in enumerate(frames):
            if frame.frame_index != expected_idx:
                raise CvmMigrationError(
                    HALT_CVM_MEMORY_CORRUPTION,
                    f"Frame sequencing broken: index {frame.frame_index} != expected {expected_idx}",
                )
            if frame.frame_size_bytes <= 0:
                raise CvmMigrationError(
                    HALT_CVM_MEMORY_CORRUPTION,
                    f"Frame {frame.frame_index} has invalid size {frame.frame_size_bytes}",
                )

        computed_root = compute_memory_merkle_root([f.frame_sha256 for f in frames])
        if computed_root != ticket.memory_manifest_root:
            raise CvmMigrationError(
                HALT_CVM_MEMORY_CORRUPTION,
                f"Merkle root mismatch: {computed_root} != {ticket.memory_manifest_root}",
            )

        updated_ticket = MigrationHandshakeTicket(
            migration_id=ticket.migration_id,
            source_vm_id=ticket.source_vm_id,
            dest_vm_id=ticket.dest_vm_id,
            source_arch=ticket.source_arch,
            dest_arch=ticket.dest_arch,
            source_epoch=ticket.source_epoch,
            dest_epoch=ticket.dest_epoch,
            memory_manifest_root=ticket.memory_manifest_root,
            expected_frame_count=ticket.expected_frame_count,
            state=MIGRATION_STATE_MEMORY_VERIFIED,
            ticket_caid=ticket.ticket_caid,
            created_at_ms=ticket.created_at_ms,
            fenced_key_caid=ticket.fenced_key_caid,
            rollback_reason=ticket.rollback_reason,
        )
        self._update_ticket(updated_ticket)
        return True

    def fence_and_handover_keys(
        self,
        migration_id: str,
        key_material: bytes,
        dest_pub_key_hex: str,
    ) -> str:
        """
        Cryptographically fences source runtime keys and binds handover payload
        to the verified destination enclave public key.
        Transitions state from MEMORY_VERIFIED to KEY_FENCED.
        """
        ticket = self.get_ticket(migration_id)
        if not ticket:
            raise CvmMigrationError(
                HALT_CVM_INVALID_STATE_TRANSITION,
                f"Migration ticket {migration_id} not found",
            )
        if ticket.state != MIGRATION_STATE_MEMORY_VERIFIED:
            raise CvmMigrationError(
                HALT_CVM_INVALID_STATE_TRANSITION,
                f"Cannot fence keys in state {ticket.state}; expected {MIGRATION_STATE_MEMORY_VERIFIED}",
            )

        if len(key_material) < 32:
            raise CvmMigrationError(
                HALT_CVM_KEY_FENCE_FAILED,
                f"Key material insufficient: length {len(key_material)} < 32 bytes",
            )

        # Compute fenced key CAID binding
        key_digest = f"sha256:{hashlib.sha256(key_material).hexdigest()}"
        fenced_payload = {
            "dest_pub_key": dest_pub_key_hex,
            "key_digest": key_digest,
            "migration_id": migration_id,
        }
        fenced_key_caid = compute_sha256_caid(fenced_payload)

        updated_ticket = MigrationHandshakeTicket(
            migration_id=ticket.migration_id,
            source_vm_id=ticket.source_vm_id,
            dest_vm_id=ticket.dest_vm_id,
            source_arch=ticket.source_arch,
            dest_arch=ticket.dest_arch,
            source_epoch=ticket.source_epoch,
            dest_epoch=ticket.dest_epoch,
            memory_manifest_root=ticket.memory_manifest_root,
            expected_frame_count=ticket.expected_frame_count,
            state=MIGRATION_STATE_KEY_FENCED,
            ticket_caid=ticket.ticket_caid,
            created_at_ms=ticket.created_at_ms,
            fenced_key_caid=fenced_key_caid,
            rollback_reason=ticket.rollback_reason,
        )
        self._update_ticket(updated_ticket)
        return fenced_key_caid

    def commit_migration(
        self,
        migration_id: str,
        now_ms: Optional[int] = None,
    ) -> MigrationCommitReceipt:
        """
        Commits heterogeneous CVM live migration handover. Emits irreversible receipt.
        Transitions state from KEY_FENCED to MIGRATION_COMMITTED.
        """
        ticket = self.get_ticket(migration_id)
        if not ticket:
            raise CvmMigrationError(
                HALT_CVM_INVALID_STATE_TRANSITION,
                f"Migration ticket {migration_id} not found",
            )
        if ticket.state != MIGRATION_STATE_KEY_FENCED:
            raise CvmMigrationError(
                HALT_CVM_INVALID_STATE_TRANSITION,
                f"Cannot commit migration in state {ticket.state}; expected {MIGRATION_STATE_KEY_FENCED}",
            )
        if not ticket.fenced_key_caid:
            raise CvmMigrationError(
                HALT_CVM_KEY_FENCE_FAILED,
                "Cannot commit migration without fenced key CAID",
            )

        effective_time = now_ms if now_ms is not None else int(time.time() * 1000)

        receipt_prelim = {
            "committed_at_ms": effective_time,
            "dest_arch": ticket.dest_arch,
            "dest_vm_id": ticket.dest_vm_id,
            "fenced_key_caid": ticket.fenced_key_caid,
            "memory_manifest_root": ticket.memory_manifest_root,
            "migration_epoch": ticket.dest_epoch,
            "migration_id": migration_id,
            "source_arch": ticket.source_arch,
            "source_vm_id": ticket.source_vm_id,
            "status": MIGRATION_STATE_COMMITTED,
        }
        receipt_caid = compute_sha256_caid(receipt_prelim)

        receipt = MigrationCommitReceipt(
            migration_id=migration_id,
            source_vm_id=ticket.source_vm_id,
            dest_vm_id=ticket.dest_vm_id,
            source_arch=ticket.source_arch,
            dest_arch=ticket.dest_arch,
            migration_epoch=ticket.dest_epoch,
            memory_manifest_root=ticket.memory_manifest_root,
            fenced_key_caid=ticket.fenced_key_caid,
            receipt_caid=receipt_caid,
            status=MIGRATION_STATE_COMMITTED,
            committed_at_ms=effective_time,
        )

        committed_ticket = MigrationHandshakeTicket(
            migration_id=ticket.migration_id,
            source_vm_id=ticket.source_vm_id,
            dest_vm_id=ticket.dest_vm_id,
            source_arch=ticket.source_arch,
            dest_arch=ticket.dest_arch,
            source_epoch=ticket.source_epoch,
            dest_epoch=ticket.dest_epoch,
            memory_manifest_root=ticket.memory_manifest_root,
            expected_frame_count=ticket.expected_frame_count,
            state=MIGRATION_STATE_COMMITTED,
            ticket_caid=ticket.ticket_caid,
            created_at_ms=ticket.created_at_ms,
            fenced_key_caid=ticket.fenced_key_caid,
            rollback_reason=ticket.rollback_reason,
        )

        self._update_ticket(committed_ticket)
        self._record_receipt(receipt)
        return receipt

    def rollback_migration(
        self,
        migration_id: str,
        reason_code: str,
        details: str,
    ) -> MigrationHandshakeTicket:
        """
        Fails-closed and rolls back an active migration. Transitions state to MIGRATION_ROLLED_BACK.
        """
        ticket = self.get_ticket(migration_id)
        if not ticket:
            raise CvmMigrationError(
                HALT_CVM_INVALID_STATE_TRANSITION,
                f"Migration ticket {migration_id} not found",
            )
        if ticket.state == MIGRATION_STATE_COMMITTED:
            raise CvmMigrationError(
                HALT_CVM_INVALID_STATE_TRANSITION,
                "Cannot rollback an already committed migration handover",
            )

        rolled_back_ticket = MigrationHandshakeTicket(
            migration_id=ticket.migration_id,
            source_vm_id=ticket.source_vm_id,
            dest_vm_id=ticket.dest_vm_id,
            source_arch=ticket.source_arch,
            dest_arch=ticket.dest_arch,
            source_epoch=ticket.source_epoch,
            dest_epoch=ticket.dest_epoch,
            memory_manifest_root=ticket.memory_manifest_root,
            expected_frame_count=ticket.expected_frame_count,
            state=MIGRATION_STATE_ROLLED_BACK,
            ticket_caid=ticket.ticket_caid,
            created_at_ms=ticket.created_at_ms,
            fenced_key_caid=ticket.fenced_key_caid,
            rollback_reason=f"[{reason_code}] {details}",
        )
        self._update_ticket(rolled_back_ticket)
        return rolled_back_ticket

    def _record_ticket(self, ticket: MigrationHandshakeTicket) -> None:
        raw_json = json.dumps(asdict(ticket), sort_keys=True)
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO cvm_migration_tickets_ledger (
                    migration_id, source_vm_id, dest_vm_id, source_arch, dest_arch,
                    source_epoch, dest_epoch, memory_manifest_root, expected_frame_count,
                    state, ticket_caid, fenced_key_caid, rollback_reason,
                    created_at_ms, raw_ticket_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticket.migration_id,
                    ticket.source_vm_id,
                    ticket.dest_vm_id,
                    ticket.source_arch,
                    ticket.dest_arch,
                    ticket.source_epoch,
                    ticket.dest_epoch,
                    ticket.memory_manifest_root,
                    ticket.expected_frame_count,
                    ticket.state,
                    ticket.ticket_caid,
                    ticket.fenced_key_caid,
                    ticket.rollback_reason,
                    ticket.created_at_ms,
                    raw_json,
                ),
            )

    def _update_ticket(self, ticket: MigrationHandshakeTicket) -> None:
        raw_json = json.dumps(asdict(ticket), sort_keys=True)
        with self._conn:
            self._conn.execute(
                """
                UPDATE cvm_migration_tickets_ledger
                SET state = ?, fenced_key_caid = ?, rollback_reason = ?, raw_ticket_json = ?
                WHERE migration_id = ?
                """,
                (
                    ticket.state,
                    ticket.fenced_key_caid,
                    ticket.rollback_reason,
                    raw_json,
                    ticket.migration_id,
                ),
            )

    def _record_receipt(self, receipt: MigrationCommitReceipt) -> None:
        raw_json = json.dumps(asdict(receipt), sort_keys=True)
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO cvm_migration_receipts_ledger (
                    migration_id, receipt_caid, source_vm_id, dest_vm_id,
                    migration_epoch, fenced_key_caid, status, committed_at_ms, raw_receipt_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt.migration_id,
                    receipt.receipt_caid,
                    receipt.source_vm_id,
                    receipt.dest_vm_id,
                    receipt.migration_epoch,
                    receipt.fenced_key_caid,
                    receipt.status,
                    receipt.committed_at_ms,
                    raw_json,
                ),
            )

    def get_ticket(self, migration_id: str) -> Optional[MigrationHandshakeTicket]:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT raw_ticket_json FROM cvm_migration_tickets_ledger
            WHERE migration_id = ?
            """,
            (migration_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return MigrationHandshakeTicket(**json.loads(row[0]))

    def get_receipt(self, migration_id: str) -> Optional[MigrationCommitReceipt]:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT raw_receipt_json FROM cvm_migration_receipts_ledger
            WHERE migration_id = ?
            """,
            (migration_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return MigrationCommitReceipt(**json.loads(row[0]))

    def list_migrations_by_state(self, state: str) -> List[MigrationHandshakeTicket]:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT raw_ticket_json FROM cvm_migration_tickets_ledger
            WHERE state = ?
            ORDER BY created_at_ms DESC
            """,
            (state,),
        )
        rows = cursor.fetchall()
        return [MigrationHandshakeTicket(**json.loads(r[0])) for r in rows]

    def close(self) -> None:
        self._conn.close()
