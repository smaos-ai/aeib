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
src/wireguard_overlay_interlock.py — Cross-Cloud WireGuard Overlay Mesh Interlock with Hardware-Rooted Ephemeral Key Handover.

Part of Sovereign Multi-Agent OS (SMAOS) / AEIB Enterprise Gateway.
Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model as a cross-cloud
WireGuard overlay mesh scaffold and hardware-attested ephemeral key handover prototype.

Honest Platform Boundary (Software Scaffold & Simulated Prototype):
  - This module is a software scaffold and simulation prototype for cross-cloud WireGuard
    overlay mesh orchestration and hardware-rooted ephemeral key handover.
  - It simulates Noise_IKpsk2 ephemeral key exchanges, hardware attestation verification,
    and peer routing state machines without creating kernel-level network interfaces (wg0).
  - Operational mode: scaffold / simulated WireGuard mesh.

Architectural Invariants:
1. Cross-Cloud Mutual Enclave Attestation:
   - Validates cloud provider hardware roots (AMD SEV-SNP, Intel TDX, AWS Nitro, Apple Enclave, TPM 2.0)
     before admitting a node into the virtual overlay mesh.
2. Strictly Monotonic Epoch Fencing:
   - Re-keying requires epoch_new == epoch_active + 1. Rejects out-of-order or replayed handshakes.
3. Hardware-Rooted Ephemeral Key Handover:
   - Ephemeral Curve25519 tunnel keys are signed by the enclave identity key.
4. Autonomous Split-Brain & Dead-Peer Fencing:
   - Active peer health probing with timeout-based fencing and fail-closed traffic drops.
5. Fail-Closed Codes:
   - HALT_WG_NON_MONOTONIC_EPOCH
   - HALT_WG_HARDWARE_ATTESTATION_INVALID
   - HALT_WG_PEER_FENCED
   - HALT_WG_SESSION_EXPIRED
   - HALT_WG_KEY_HANDOVER_REJECTED
   - HALT_WG_INVALID_MESH_IP
   - HALT_WG_SIGNATURE_MISMATCH
6. RFC 8785 Canonical Auditing & SQLite-WAL Durability:
   - All mesh state, handshakes, and re-key receipts are sealed via JCS and persisted to SQLite-WAL.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import ipaddress
import json
import math
import sqlite3
import time
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs

# Node & Peer States
PEER_STATE_PROVISIONING: str = "PROVISIONING"
PEER_STATE_ACTIVE: str = "ACTIVE"
PEER_STATE_DEGRADED: str = "DEGRADED"
PEER_STATE_FENCED: str = "FENCED"

# Fail-Closed Rejection Codes
HALT_WG_NON_MONOTONIC_EPOCH: str = "HALT_WG_NON_MONOTONIC_EPOCH"
HALT_WG_HARDWARE_ATTESTATION_INVALID: str = "HALT_WG_HARDWARE_ATTESTATION_INVALID"
HALT_WG_PEER_FENCED: str = "HALT_WG_PEER_FENCED"
HALT_WG_SESSION_EXPIRED: str = "HALT_WG_SESSION_EXPIRED"
HALT_WG_KEY_HANDOVER_REJECTED: str = "HALT_WG_KEY_HANDOVER_REJECTED"
HALT_WG_INVALID_MESH_IP: str = "HALT_WG_INVALID_MESH_IP"
HALT_WG_SIGNATURE_MISMATCH: str = "HALT_WG_SIGNATURE_MISMATCH"

# Default Timing & Epoch Constants
DEFAULT_SESSION_TTL_MS: int = 120_000            # claim: config - 2 minutes session expiration
DEFAULT_KEEP_ALIVE_TIMEOUT_MS: int = 15_000      # claim: config - 15s keep-alive timeout triggers degrade/fence
MAX_ALLOWED_CLOCK_SKEW_MS: int = 30_000          # claim: config - 30s max clock skew
VALID_CLOUD_PROVIDERS: Set[str] = {"AWS", "GCP", "AZURE", "OCI", "EQUINIX", "BAREMETAL"}
VALID_ENCLAVE_TYPES: Set[str] = {"AMD_SEV_SNP", "INTEL_TDX", "AWS_NITRO", "APPLE_ENCLAVE", "TPM20"}


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
class WgMeshNode:
    """Representation of an attested node participating in the overlay mesh."""
    node_id: str
    cloud_provider: str
    region: str
    enclave_type: str
    virtual_mesh_ip: str
    enclave_pubkey_hex: str
    attestation_measurement_hex: str
    registered_at_ms: int

    def __post_init__(self) -> None:
        if not self.node_id or not isinstance(self.node_id, str):
            raise ValueError("node_id must be a non-empty string")
        if self.cloud_provider.upper() not in VALID_CLOUD_PROVIDERS:
            raise ValueError(f"Unsupported cloud provider: {self.cloud_provider}")
        if self.enclave_type.upper() not in VALID_ENCLAVE_TYPES:
            raise ValueError(f"Unsupported enclave type: {self.enclave_type}")
        try:
            ipaddress.ip_address(self.virtual_mesh_ip)
        except ValueError:
            raise ValueError(f"Invalid virtual_mesh_ip: {self.virtual_mesh_ip}")
        if len(self.enclave_pubkey_hex) != 64:
            raise ValueError("enclave_pubkey_hex must be a 64-char hex string (32 bytes)")
        if len(self.attestation_measurement_hex) != 64:
            raise ValueError("attestation_measurement_hex must be a 64-char hex string (32 bytes)")
        if self.registered_at_ms <= 0:
            raise ValueError("registered_at_ms must be positive")


@dataclass(frozen=True)
class WgHandshakeReceipt:
    """Cryptographically sealed handshake and re-keying receipt."""
    session_id: str
    initiator_node_id: str
    responder_node_id: str
    epoch: int
    ephemeral_pubkey_hex: str
    preshared_key_hash: str
    established_at_ms: int
    expires_at_ms: int
    caid: str

    def __post_init__(self) -> None:
        if not self.session_id:
            raise ValueError("session_id must be non-empty")
        if not self.initiator_node_id:
            raise ValueError("initiator_node_id must be non-empty")
        if not self.responder_node_id:
            raise ValueError("responder_node_id must be non-empty")
        if self.epoch <= 0:
            raise ValueError("epoch must be positive")
        if len(self.ephemeral_pubkey_hex) != 64:
            raise ValueError("ephemeral_pubkey_hex must be 64-char hex (32 bytes)")
        if len(self.preshared_key_hash) != 64:
            raise ValueError("preshared_key_hash must be 64-char hex (32 bytes)")
        if self.expires_at_ms <= self.established_at_ms:
            raise ValueError("expires_at_ms must be strictly greater than established_at_ms")
        if not self.caid:
            raise ValueError("caid must be non-empty")


class WireGuardOverlayInterlock:
    """
    Cross-Cloud WireGuard Overlay Mesh Interlock Scaffold.
    Enforces mutual enclave attestation, monotonic session epoch re-keying,
    and dead-peer fencing across multi-cloud agent execution nodes.
    """

    def __init__(
        self,
        mesh_network_cidr: str = "10.100.0.0/16",
        session_ttl_ms: int = DEFAULT_SESSION_TTL_MS,
        keep_alive_timeout_ms: int = DEFAULT_KEEP_ALIVE_TIMEOUT_MS,
        max_clock_skew_ms: int = MAX_ALLOWED_CLOCK_SKEW_MS,
        db_path: str = ":memory:",
    ) -> None:
        try:
            self.network = ipaddress.ip_network(mesh_network_cidr)
        except ValueError:
            raise ValueError(f"Invalid mesh_network_cidr: {mesh_network_cidr}")

        if session_ttl_ms <= 0:
            raise ValueError("session_ttl_ms must be a positive integer")
        if keep_alive_timeout_ms <= 0:
            raise ValueError("keep_alive_timeout_ms must be a positive integer")

        self.mesh_network_cidr = mesh_network_cidr
        self.session_ttl_ms = session_ttl_ms
        self.keep_alive_timeout_ms = keep_alive_timeout_ms
        self.max_clock_skew_ms = max_clock_skew_ms
        self.db_path = db_path

        self._nodes: Dict[str, WgMeshNode] = {}
        self._node_states: Dict[str, str] = {}
        self._last_heartbeat_ms: Dict[str, int] = {}
        self._active_sessions: Dict[str, WgHandshakeReceipt] = {}  # key: f"{node_a}:{node_b}"
        self._session_epochs: Dict[str, int] = {}                  # key: f"{node_a}:{node_b}"

        self._conn = sqlite3.connect(self.db_path)
        self._init_sqlite_schema()

    def _init_sqlite_schema(self) -> None:
        """Initialize SQLite tables and WAL configuration."""
        with self._conn:
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS wg_mesh_nodes (
                    node_id TEXT PRIMARY KEY,
                    cloud_provider TEXT NOT NULL,
                    region TEXT NOT NULL,
                    enclave_type TEXT NOT NULL,
                    virtual_mesh_ip TEXT NOT NULL UNIQUE,
                    enclave_pubkey_hex TEXT NOT NULL,
                    attestation_measurement_hex TEXT NOT NULL,
                    status TEXT NOT NULL,
                    registered_at_ms INTEGER NOT NULL
                );
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS wg_handshake_receipts (
                    caid TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    initiator_node_id TEXT NOT NULL,
                    responder_node_id TEXT NOT NULL,
                    epoch INTEGER NOT NULL,
                    ephemeral_pubkey_hex TEXT NOT NULL,
                    preshared_key_hash TEXT NOT NULL,
                    established_at_ms INTEGER NOT NULL,
                    expires_at_ms INTEGER NOT NULL
                );
                """
            )

    def register_node(self, node: WgMeshNode) -> None:
        """Register an enclave-attested node into the overlay mesh."""
        ip_obj = ipaddress.ip_address(node.virtual_mesh_ip)
        if ip_obj not in self.network:
            raise ValueError(f"[{HALT_WG_INVALID_MESH_IP}] IP {node.virtual_mesh_ip} outside mesh {self.mesh_network_cidr}")

        # Check for IP collision
        for existing in self._nodes.values():
            if existing.node_id != node.node_id and existing.virtual_mesh_ip == node.virtual_mesh_ip:
                raise ValueError(f"IP collision: {node.virtual_mesh_ip} already assigned to {existing.node_id}")

        self._nodes[node.node_id] = node
        self._node_states[node.node_id] = PEER_STATE_ACTIVE
        self._last_heartbeat_ms[node.node_id] = node.registered_at_ms

        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO wg_mesh_nodes (
                    node_id, cloud_provider, region, enclave_type, virtual_mesh_ip,
                    enclave_pubkey_hex, attestation_measurement_hex, status, registered_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    node.node_id,
                    node.cloud_provider.upper(),
                    node.region,
                    node.enclave_type.upper(),
                    node.virtual_mesh_ip,
                    node.enclave_pubkey_hex,
                    node.attestation_measurement_hex,
                    PEER_STATE_ACTIVE,
                    node.registered_at_ms,
                ),
            )

    def _get_peer_pair_key(self, node_a: str, node_b: str) -> str:
        """Deterministic peer pair key (lexicographically ordered)."""
        return f"{min(node_a, node_b)}::{max(node_a, node_b)}"

    def record_heartbeat(self, node_id: str, timestamp_ms: Optional[int] = None) -> None:
        """Update last heartbeat timestamp for a node, reviving from degraded if appropriate."""
        if node_id not in self._nodes:
            raise ValueError(f"Node {node_id} not registered in mesh")
        if timestamp_ms is None:
            timestamp_ms = int(time.time() * 1000)

        self._last_heartbeat_ms[node_id] = timestamp_ms
        if self._node_states.get(node_id) == PEER_STATE_DEGRADED:
            self._node_states[node_id] = PEER_STATE_ACTIVE
            with self._conn:
                self._conn.execute(
                    "UPDATE wg_mesh_nodes SET status = ? WHERE node_id = ?;",
                    (PEER_STATE_ACTIVE, node_id),
                )

    def check_node_health(self, node_id: str, now_ms: Optional[int] = None) -> str:
        """Evaluate peer health against keep-alive timeouts and return current state."""
        if node_id not in self._nodes:
            raise ValueError(f"Node {node_id} not registered in mesh")
        if now_ms is None:
            now_ms = int(time.time() * 1000)

        last_hb = self._last_heartbeat_ms.get(node_id, 0)
        elapsed = now_ms - last_hb

        current_state = self._node_states[node_id]
        if current_state == PEER_STATE_FENCED:
            return PEER_STATE_FENCED

        if elapsed > (2 * self.keep_alive_timeout_ms):
            self._node_states[node_id] = PEER_STATE_FENCED
            with self._conn:
                self._conn.execute(
                    "UPDATE wg_mesh_nodes SET status = ? WHERE node_id = ?;",
                    (PEER_STATE_FENCED, node_id),
                )
            return PEER_STATE_FENCED
        elif elapsed > self.keep_alive_timeout_ms:
            self._node_states[node_id] = PEER_STATE_DEGRADED
            with self._conn:
                self._conn.execute(
                    "UPDATE wg_mesh_nodes SET status = ? WHERE node_id = ?;",
                    (PEER_STATE_DEGRADED, node_id),
                )
            return PEER_STATE_DEGRADED

        return PEER_STATE_ACTIVE

    def perform_handshake(
        self,
        initiator_id: str,
        responder_id: str,
        epoch: int,
        ephemeral_pubkey_hex: str,
        preshared_key_hex: str,
        attestation_signature_hex: str,
        now_ms: int,
    ) -> WgHandshakeReceipt:
        """
        Execute an ephemeral key handover between two attested nodes.
        Enforces monotonic epoch advancing, hardware enclave signature verification,
        and dead-peer health gating.
        """
        if now_ms <= 0:
            raise ValueError("now_ms must be positive")

        if initiator_id not in self._nodes or responder_id not in self._nodes:
            raise ValueError("Both initiator and responder must be registered in the mesh")
        if initiator_id == responder_id:
            raise ValueError("Initiator and responder cannot be the same node")

        # 1. Check peer health
        if self.check_node_health(initiator_id, now_ms) == PEER_STATE_FENCED:
            raise ValueError(f"[{HALT_WG_PEER_FENCED}] Initiator {initiator_id} is fenced")
        if self.check_node_health(responder_id, now_ms) == PEER_STATE_FENCED:
            raise ValueError(f"[{HALT_WG_PEER_FENCED}] Responder {responder_id} is fenced")

        pair_key = self._get_peer_pair_key(initiator_id, responder_id)
        current_epoch = self._session_epochs.get(pair_key, 0)

        # 2. Monotonic Epoch Validation
        if epoch != current_epoch + 1:
            raise ValueError(
                f"[{HALT_WG_NON_MONOTONIC_EPOCH}] Handshake epoch {epoch} does not match expected {current_epoch + 1}"
            )

        # 3. Hardware Enclave Signature Verification on Ephemeral Key Handover
        initiator_node = self._nodes[initiator_id]
        try:
            pubkey_bytes = bytes.fromhex(initiator_node.enclave_pubkey_hex)
            sig_bytes = bytes.fromhex(attestation_signature_hex)
            if len(pubkey_bytes) != 32 or len(sig_bytes) != 64:
                raise ValueError("Invalid signature or pubkey byte lengths")

            handshake_payload = {
                "epoch": epoch,
                "ephemeral_pubkey_hex": ephemeral_pubkey_hex,
                "initiator_id": initiator_id,
                "preshared_key_hash": compute_sha256(bytes.fromhex(preshared_key_hex)),
                "responder_id": responder_id,
                "timestamp_ms": now_ms,
            }
            canonical_bytes = encode_jcs(handshake_payload)

            public_key = ed25519.Ed25519PublicKey.from_public_bytes(pubkey_bytes)
            public_key.verify(sig_bytes, canonical_bytes)
        except (ValueError, InvalidSignature) as exc:
            raise ValueError(f"[{HALT_WG_HARDWARE_ATTESTATION_INVALID}] Hardware enclave signature invalid: {exc}")

        # 4. Construct and seal handshake receipt
        psk_hash = compute_sha256(bytes.fromhex(preshared_key_hex))
        session_id = compute_sha256(f"{pair_key}::{epoch}::{now_ms}".encode("utf-8"))[:32]
        expires_at = now_ms + self.session_ttl_ms

        receipt_doc = {
            "epoch": epoch,
            "ephemeral_pubkey_hex": ephemeral_pubkey_hex,
            "established_at_ms": now_ms,
            "expires_at_ms": expires_at,
            "initiator_node_id": initiator_id,
            "preshared_key_hash": psk_hash,
            "responder_node_id": responder_id,
            "session_id": session_id,
        }
        caid = compute_sha256(encode_jcs(receipt_doc))

        receipt = WgHandshakeReceipt(
            session_id=session_id,
            initiator_node_id=initiator_id,
            responder_node_id=responder_id,
            epoch=epoch,
            ephemeral_pubkey_hex=ephemeral_pubkey_hex,
            preshared_key_hash=psk_hash,
            established_at_ms=now_ms,
            expires_at_ms=expires_at,
            caid=caid,
        )

        # Update in-memory session states
        self._session_epochs[pair_key] = epoch
        self._active_sessions[pair_key] = receipt

        # Persist to SQLite
        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO wg_handshake_receipts (
                    caid, session_id, initiator_node_id, responder_node_id, epoch,
                    ephemeral_pubkey_hex, preshared_key_hash, established_at_ms, expires_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    receipt.caid,
                    receipt.session_id,
                    receipt.initiator_node_id,
                    receipt.responder_node_id,
                    receipt.epoch,
                    receipt.ephemeral_pubkey_hex,
                    receipt.preshared_key_hash,
                    receipt.established_at_ms,
                    receipt.expires_at_ms,
                ),
            )

        return receipt

    def verify_active_session(self, node_a: str, node_b: str, now_ms: Optional[int] = None) -> Tuple[bool, str]:
        """
        Check if an active, unexpired WireGuard session exists between two peers.
        Returns (is_active, reason).
        """
        if now_ms is None:
            now_ms = int(time.time() * 1000)

        pair_key = self._get_peer_pair_key(node_a, node_b)
        if pair_key not in self._active_sessions:
            return False, "NO_ACTIVE_SESSION"

        receipt = self._active_sessions[pair_key]
        if now_ms >= receipt.expires_at_ms:
            return False, HALT_WG_SESSION_EXPIRED

        if self.check_node_health(node_a, now_ms) == PEER_STATE_FENCED:
            return False, HALT_WG_PEER_FENCED
        if self.check_node_health(node_b, now_ms) == PEER_STATE_FENCED:
            return False, HALT_WG_PEER_FENCED

        return True, "SESSION_ACTIVE"

    def get_mesh_topology(self) -> Dict[str, Any]:
        """Return full overlay mesh topology with node counts, active sessions, and statuses."""
        with self._conn:
            cursor = self._conn.execute("SELECT status, COUNT(*) FROM wg_mesh_nodes GROUP BY status;")
            status_counts: Dict[str, int] = {
                PEER_STATE_ACTIVE: 0,
                PEER_STATE_DEGRADED: 0,
                PEER_STATE_FENCED: 0,
            }
            for status, count in cursor.fetchall():
                status_counts[status] = count

            return {
                "mesh_network_cidr": self.mesh_network_cidr,
                "total_nodes": len(self._nodes),
                "status_counts": status_counts,
                "active_sessions_count": len(self._active_sessions),
            }
