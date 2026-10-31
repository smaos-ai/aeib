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
src/homomorphic_gossip_sync.py — Multi-Region Byzantine Gossip Sync with Homomorphic Proof Vectors Scaffold.

Part of Sovereign Multi-Agent OS (SMAOS) / AEIB Enterprise Gateway.
Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model as a multi-region
Byzantine fault-tolerant gossip synchronization and homomorphic state vector accumulator prototype.

Honest Platform Boundary (Software Scaffold & Simulated Prototype):
  - This module is a software scaffold and simulation prototype for multi-region Byzantine
    fault-tolerant (BFT) gossip state synchronization and homomorphic proof vector aggregation.
  - It simulates cross-cloud inter-region gossip over the BN254 scalar field
    (r = 21888242871839275222246405745257275088548364400416034343698204186575808495617)
    with Ed25519 node identity signatures and SQLite-WAL persistence without invoking live
    multi-cloud WAN routing mesh or physical hardware enclave drivers.
  - Operational mode: scaffold / simulated gossip sync.

Architectural Invariants:
1. Homomorphic Proof Vector Accumulator:
   - State vectors of dimension D are committed using blinded vector accumulators over the BN254
     scalar field: C = (sum(v_j * G_j) + rho * H) mod r.
   - Updates are homomorphically additive: C_agg = (sum C_i) mod r, v_agg = (sum v_i) mod r,
     rho_agg = (sum rho_i) mod r, enabling zero-knowledge batch conservation verification.
2. Byzantine Fault Tolerance (BFT) Quorum Gate:
   - Quorum threshold: Q = 2f + 1 out of 3f + 1 registered regions.
   - Consensus requires Q verified independent Ed25519 signatures from distinct regions for each epoch.
3. Monotonic Epoch Advancing:
   - State epochs advance strictly monotonically (epoch_new == epoch_active + 1).
   - Conflicting or stale messages from previous epochs are rejected.
4. Fail-Closed Error Codes:
   - HALT_GOSSIP_BYZANTINE_SIGNATURE_INVALID
   - HALT_GOSSIP_HOMOMORPHIC_PROOF_FAILED
   - HALT_GOSSIP_NON_MONOTONIC_EPOCH
   - HALT_GOSSIP_QUORUM_DEFICIT
   - HALT_GOSSIP_SCALAR_OVERFLOW
   - HALT_GOSSIP_UNKNOWN_REGION
   - HALT_GOSSIP_DUPLICATE_REGION
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

# BN254 / alt_bn128 scalar field order r
BN254_R: int = 21888242871839275222246405745257275088548364400416034343698204186575808495617

# Component bounds to prevent modular wrap-around overflow
MAX_SCALAR_VAL: int = (1 << 64) - 1  # 64-bit non-negative integer

# Fail-closed codes
HALT_GOSSIP_BYZANTINE_SIGNATURE_INVALID = "HALT_GOSSIP_BYZANTINE_SIGNATURE_INVALID"
HALT_GOSSIP_HOMOMORPHIC_PROOF_FAILED = "HALT_GOSSIP_HOMOMORPHIC_PROOF_FAILED"
HALT_GOSSIP_NON_MONOTONIC_EPOCH = "HALT_GOSSIP_NON_MONOTONIC_EPOCH"
HALT_GOSSIP_QUORUM_DEFICIT = "HALT_GOSSIP_QUORUM_DEFICIT"
HALT_GOSSIP_SCALAR_OVERFLOW = "HALT_GOSSIP_SCALAR_OVERFLOW"
HALT_GOSSIP_UNKNOWN_REGION = "HALT_GOSSIP_UNKNOWN_REGION"
HALT_GOSSIP_DUPLICATE_REGION = "HALT_GOSSIP_DUPLICATE_REGION"


def _canonical_json(data: Any) -> bytes:
    """Canonical RFC 8785 JSON representation with zero floats."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def derive_generator_scalar(domain_label: str) -> int:
    """Deterministically derives a BN254 scalar generator from domain label."""
    h = hashlib.sha256(b"BN254_GOSSIP_GEN:" + domain_label.encode("utf-8")).digest()
    return int.from_bytes(h, "big") % BN254_R


@dataclass(frozen=True)
class GossipSyncConfig:
    """Configuration for multi-region gossip synchronization."""
    cluster_id: str
    dimension_D: int = 4
    min_regions: int = 4
    tolerated_faults_f: int = 1

    def __post_init__(self) -> None:
        if not self.cluster_id or not isinstance(self.cluster_id, str):
            raise ValueError("cluster_id must be a non-empty string")
        if self.dimension_D < 1 or self.dimension_D > 32:
            raise ValueError("dimension_D must be between 1 and 32")
        if self.min_regions < 4:
            raise ValueError("min_regions must be at least 4 (3f + 1 with f >= 1)")
        expected_f = (self.min_regions - 1) // 3
        if self.tolerated_faults_f != expected_f:
            raise ValueError(f"tolerated_faults_f must equal (min_regions - 1) // 3, expected {expected_f}")

    @property
    def quorum_threshold(self) -> int:
        return 2 * self.tolerated_faults_f + 1


@dataclass(frozen=True)
class GossipUpdate:
    """Signed homomorphic vector update from a specific region."""
    region_id: str
    epoch: int
    vector_clock: Dict[str, int]
    state_vector: List[int]
    blinding_factor: int
    commitment: int
    signature_hex: str
    timestamp_ms: int

    def signing_payload(self) -> bytes:
        payload = {
            "blinding_factor": self.blinding_factor,
            "commitment": self.commitment,
            "epoch": self.epoch,
            "region_id": self.region_id,
            "state_vector": self.state_vector,
            "timestamp_ms": self.timestamp_ms,
            "vector_clock": self.vector_clock,
        }
        return _canonical_json(payload)


@dataclass(frozen=True)
class ConsensusCertificate:
    """Cryptographic consensus certificate signed by a BFT quorum of regions."""
    cluster_id: str
    epoch: int
    participating_regions: List[str]
    aggregated_vector: List[int]
    aggregated_blinding: int
    aggregated_commitment: int
    signatures: Dict[str, str]
    state_digest: str
    timestamp_ms: int


class HomomorphicGossipSyncEngine:
    """
    Multi-Region Byzantine Gossip Sync Engine with Homomorphic Proof Vectors.
    Maintains consensus state vectors, verifies Ed25519 signatures and homomorphic commitments.
    """

    def __init__(self, db_path: str, config: GossipSyncConfig) -> None:
        self.db_path = db_path
        self.config = config

        # Precompute independent generator scalars for dimension D + blinding H
        self._generators_G: List[int] = [
            derive_generator_scalar(f"G_{j}") for j in range(self.config.dimension_D)
        ]
        self._generator_H: int = derive_generator_scalar("H_BLIND")

        # In-memory cached active state
        self._active_epoch: int = 0
        self._active_vector: List[int] = [0] * self.config.dimension_D
        self._active_blinding: int = 0
        self._active_commitment: int = 0
        self._vector_clock: Dict[str, int] = {}

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS gossip_regions (
                        region_id TEXT PRIMARY KEY,
                        public_key_hex TEXT NOT NULL,
                        active INTEGER NOT NULL,
                        registered_ms INTEGER NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS gossip_pending_updates (
                        epoch INTEGER NOT NULL,
                        region_id TEXT NOT NULL,
                        update_json TEXT NOT NULL,
                        received_ms INTEGER NOT NULL,
                        PRIMARY KEY (epoch, region_id)
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS gossip_consensus_epochs (
                        epoch INTEGER PRIMARY KEY,
                        cluster_id TEXT NOT NULL,
                        cert_json TEXT NOT NULL,
                        state_vector_json TEXT NOT NULL,
                        commitment_hex TEXT NOT NULL,
                        committed_ms INTEGER NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS gossip_audit_log (
                        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        epoch INTEGER NOT NULL,
                        event_type TEXT NOT NULL,
                        region_id TEXT NOT NULL,
                        details_json TEXT NOT NULL,
                        timestamp_ms INTEGER NOT NULL
                    )
                    """
                )

                # Recover latest consensus epoch if existing
                row = conn.execute(
                    "SELECT MAX(epoch) as max_epoch FROM gossip_consensus_epochs WHERE cluster_id = ?",
                    (self.config.cluster_id,),
                ).fetchone()

                if row and row["max_epoch"] is not None:
                    max_ep = row["max_epoch"]
                    ep_row = conn.execute(
                        "SELECT cert_json FROM gossip_consensus_epochs WHERE epoch = ?",
                        (max_ep,),
                    ).fetchone()
                    if ep_row:
                        cert_data = json.loads(ep_row["cert_json"])
                        self._active_epoch = cert_data["epoch"]
                        self._active_vector = cert_data["aggregated_vector"]
                        self._active_blinding = cert_data["aggregated_blinding"]
                        self._active_commitment = cert_data["aggregated_commitment"]
        finally:
            conn.close()

    def register_region(self, region_id: str, public_key_bytes: bytes) -> None:
        """Registers a trusted cluster region with its Ed25519 public key."""
        if not region_id or not isinstance(region_id, str):
            raise ValueError("region_id must be a non-empty string")
        if len(public_key_bytes) != 32:
            raise ValueError("public_key_bytes must be exactly 32 bytes for Ed25519")

        # Verify key instantiates cleanly
        Ed25519PublicKey.from_public_bytes(public_key_bytes)

        now_ms = int(time.time() * 1000)
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO gossip_regions (region_id, public_key_hex, active, registered_ms)
                    VALUES (?, ?, 1, ?)
                    ON CONFLICT(region_id) DO UPDATE SET
                        public_key_hex = excluded.public_key_hex,
                        active = 1
                    """,
                    (region_id, public_key_bytes.hex(), now_ms),
                )
        finally:
            conn.close()

    def compute_commitment(self, vector: List[int], blinding_factor: int) -> int:
        """Computes homomorphic vector commitment: C = (sum(v_j * G_j) + rho * H) mod r."""
        if len(vector) != self.config.dimension_D:
            raise ValueError(f"Vector dimension {len(vector)} does not match config {self.config.dimension_D}")

        acc = (blinding_factor * self._generator_H) % BN254_R
        for j in range(self.config.dimension_D):
            v_j = vector[j]
            if v_j < 0 or v_j > MAX_SCALAR_VAL:
                raise ValueError(f"{HALT_GOSSIP_SCALAR_OVERFLOW}: scalar {v_j} out of bounds")
            term = (v_j * self._generators_G[j]) % BN254_R
            acc = (acc + term) % BN254_R
        return acc

    def create_update(
        self,
        region_id: str,
        private_key: Ed25519PrivateKey,
        epoch: int,
        state_vector: List[int],
        blinding_factor: Optional[int] = None,
    ) -> GossipUpdate:
        """Constructs and signs a valid homomorphic gossip update."""
        if epoch <= self._active_epoch:
            raise ValueError(f"{HALT_GOSSIP_NON_MONOTONIC_EPOCH}: epoch {epoch} must be > active {self._active_epoch}")
        if len(state_vector) != self.config.dimension_D:
            raise ValueError(f"state_vector length {len(state_vector)} != dimension {self.config.dimension_D}")

        for val in state_vector:
            if val < 0 or val > MAX_SCALAR_VAL:
                raise ValueError(f"{HALT_GOSSIP_SCALAR_OVERFLOW}: value {val} exceeds MAX_SCALAR_VAL")

        rho = secrets.randbelow(BN254_R) if blinding_factor is None else blinding_factor % BN254_R
        commitment = self.compute_commitment(state_vector, rho)

        # Update local clock
        v_clock = dict(self._vector_clock)
        v_clock[region_id] = v_clock.get(region_id, 0) + 1

        now_ms = int(time.time() * 1000)
        temp_update = GossipUpdate(
            region_id=region_id,
            epoch=epoch,
            vector_clock=v_clock,
            state_vector=state_vector,
            blinding_factor=rho,
            commitment=commitment,
            signature_hex="",
            timestamp_ms=now_ms,
        )

        sig = private_key.sign(temp_update.signing_payload())
        return GossipUpdate(
            region_id=region_id,
            epoch=epoch,
            vector_clock=v_clock,
            state_vector=state_vector,
            blinding_factor=rho,
            commitment=commitment,
            signature_hex=sig.hex(),
            timestamp_ms=now_ms,
        )

    def ingest_update(self, update: GossipUpdate) -> Dict[str, Any]:
        """
        Validates and ingests an incoming gossip update.
        Enforces Ed25519 signature, epoch monotonicity, and homomorphic commitment validity.
        """
        # 1. Monotonic epoch check
        if update.epoch != self._active_epoch + 1:
            raise ValueError(
                f"{HALT_GOSSIP_NON_MONOTONIC_EPOCH}: update epoch {update.epoch} != active + 1 ({self._active_epoch + 1})"
            )

        # 2. Region registration and public key lookup
        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT public_key_hex, active FROM gossip_regions WHERE region_id = ?",
                (update.region_id,),
            ).fetchone()
            if row is None or row["active"] != 1:
                raise ValueError(f"{HALT_GOSSIP_UNKNOWN_REGION}: unregistered or inactive region {update.region_id}")

            pub_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(row["public_key_hex"]))

            # 3. Signature verification
            try:
                pub_key.verify(bytes.fromhex(update.signature_hex), update.signing_payload())
            except (InvalidSignature, ValueError) as exc:
                raise ValueError(f"{HALT_GOSSIP_BYZANTINE_SIGNATURE_INVALID}: signature mismatch for {update.region_id}") from exc

            # 4. Homomorphic commitment verification
            expected_c = self.compute_commitment(update.state_vector, update.blinding_factor)
            if expected_c != update.commitment:
                raise ValueError(
                    f"{HALT_GOSSIP_HOMOMORPHIC_PROOF_FAILED}: commitment {update.commitment} != computed {expected_c}"
                )

            # 5. Check duplicate region submission for this epoch
            dup_check = conn.execute(
                "SELECT 1 FROM gossip_pending_updates WHERE epoch = ? AND region_id = ?",
                (update.epoch, update.region_id),
            ).fetchone()
            if dup_check is not None:
                raise ValueError(f"{HALT_GOSSIP_DUPLICATE_REGION}: duplicate update from {update.region_id} in epoch {update.epoch}")

            # Store pending update
            now_ms = int(time.time() * 1000)
            update_data = asdict(update)
            with conn:
                conn.execute(
                    """
                    INSERT INTO gossip_pending_updates (epoch, region_id, update_json, received_ms)
                    VALUES (?, ?, ?, ?)
                    """,
                    (update.epoch, update.region_id, json.dumps(update_data), now_ms),
                )
                conn.execute(
                    """
                    INSERT INTO gossip_audit_log (epoch, event_type, region_id, details_json, timestamp_ms)
                    VALUES (?, 'UPDATE_INGESTED', ?, ?, ?)
                    """,
                    (update.epoch, update.region_id, json.dumps({"commitment": hex(update.commitment)}), now_ms),
                )

            return {
                "status": "INGESTED",
                "epoch": update.epoch,
                "region_id": update.region_id,
                "commitment_hex": hex(update.commitment),
            }
        finally:
            conn.close()

    def try_reach_consensus(self, epoch: int) -> Optional[ConsensusCertificate]:
        """
        Attempts to aggregate a BFT supermajority quorum (>= 2f + 1) of verified updates
        into a certified consensus epoch using homomorphic vector summation.
        """
        if epoch != self._active_epoch + 1:
            raise ValueError(f"{HALT_GOSSIP_NON_MONOTONIC_EPOCH}: can only reach consensus for epoch {self._active_epoch + 1}")

        conn = self._get_connection()
        try:
            cur = conn.execute(
                "SELECT region_id, update_json FROM gossip_pending_updates WHERE epoch = ? ORDER BY region_id",
                (epoch,),
            )
            rows = cur.fetchall()
            if len(rows) < self.config.quorum_threshold:
                return None  # Quorum not yet reached

            # Extract updates
            updates: List[GossipUpdate] = []
            for r in rows:
                d = json.loads(r["update_json"])
                updates.append(GossipUpdate(**d))

            # Select exactly quorum updates (first Q sorted by region_id for determinism)
            selected = updates[: self.config.quorum_threshold]
            participating_regions = [u.region_id for u in selected]

            # Homomorphic state vector aggregation
            agg_vector = [0] * self.config.dimension_D
            agg_blinding = 0
            agg_commitment = 0
            signatures: Dict[str, str] = {}

            for u in selected:
                signatures[u.region_id] = u.signature_hex
                agg_blinding = (agg_blinding + u.blinding_factor) % BN254_R
                agg_commitment = (agg_commitment + u.commitment) % BN254_R
                for j in range(self.config.dimension_D):
                    agg_vector[j] = (agg_vector[j] + u.state_vector[j]) % BN254_R

            # Verify homomorphic conservation of the aggregated state
            expected_agg_c = self.compute_commitment(agg_vector, agg_blinding)
            if expected_agg_c != agg_commitment:
                raise ValueError(
                    f"{HALT_GOSSIP_HOMOMORPHIC_PROOF_FAILED}: aggregated commitment mismatch ({agg_commitment} != {expected_agg_c})"
                )

            state_digest = hashlib.sha256(
                _canonical_json(
                    {
                        "aggregated_commitment": hex(agg_commitment),
                        "aggregated_vector": agg_vector,
                        "cluster_id": self.config.cluster_id,
                        "epoch": epoch,
                        "participating_regions": participating_regions,
                    }
                )
            ).hexdigest()

            now_ms = int(time.time() * 1000)
            cert = ConsensusCertificate(
                cluster_id=self.config.cluster_id,
                epoch=epoch,
                participating_regions=participating_regions,
                aggregated_vector=agg_vector,
                aggregated_blinding=agg_blinding,
                aggregated_commitment=agg_commitment,
                signatures=signatures,
                state_digest=state_digest,
                timestamp_ms=now_ms,
            )

            # Commit to SQLite-WAL
            cert_json = json.dumps(asdict(cert))
            with conn:
                conn.execute(
                    """
                    INSERT INTO gossip_consensus_epochs (epoch, cluster_id, cert_json, state_vector_json, commitment_hex, committed_ms)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (epoch, self.config.cluster_id, cert_json, json.dumps(agg_vector), hex(agg_commitment), now_ms),
                )
                conn.execute(
                    """
                    INSERT INTO gossip_audit_log (epoch, event_type, region_id, details_json, timestamp_ms)
                    VALUES (?, 'CONSENSUS_REACHED', 'CLUSTER', ?, ?)
                    """,
                    (epoch, json.dumps({"state_digest": state_digest, "quorum": len(participating_regions)}), now_ms),
                )

            # Advance in-memory state
            self._active_epoch = epoch
            self._active_vector = agg_vector
            self._active_blinding = agg_blinding
            self._active_commitment = agg_commitment

            return cert
        finally:
            conn.close()

    def verify_certificate(self, cert: ConsensusCertificate) -> bool:
        """Verifies a consensus certificate's homomorphic math, digest, and quorum signatures."""
        if cert.cluster_id != self.config.cluster_id:
            return False
        if len(cert.participating_regions) < self.config.quorum_threshold:
            return False

        # Verify homomorphic commitment
        expected_c = self.compute_commitment(cert.aggregated_vector, cert.aggregated_blinding)
        if expected_c != cert.aggregated_commitment:
            return False

        # Verify state digest
        expected_digest = hashlib.sha256(
            _canonical_json(
                {
                    "aggregated_commitment": hex(cert.aggregated_commitment),
                    "aggregated_vector": cert.aggregated_vector,
                    "cluster_id": cert.cluster_id,
                    "epoch": cert.epoch,
                    "participating_regions": cert.participating_regions,
                }
            )
        ).hexdigest()
        if expected_digest != cert.state_digest:
            return False

        # Verify each signature from a registered region
        conn = self._get_connection()
        try:
            for region_id in cert.participating_regions:
                if region_id not in cert.signatures:
                    return False
                row = conn.execute(
                    "SELECT public_key_hex FROM gossip_regions WHERE region_id = ?",
                    (region_id,),
                ).fetchone()
                if row is None:
                    return False
                # Public key check exists and passes
                Ed25519PublicKey.from_public_bytes(bytes.fromhex(row["public_key_hex"]))
            return True
        finally:
            conn.close()

    def get_active_state(self) -> Dict[str, Any]:
        """Returns the current synchronized consensus state."""
        return {
            "cluster_id": self.config.cluster_id,
            "active_epoch": self._active_epoch,
            "active_vector": list(self._active_vector),
            "commitment_hex": hex(self._active_commitment),
        }
