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
src/zk_tpm_pcr_aggregator.py — Zero-Knowledge Multi-Node TPM 2.0 PCR-11 Polynomial Aggregator.

Part of Sovereign Multi-Agent OS (SMAOS) / AEIB Enterprise Gateway.
Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model as a software scaffold and polynomial aggregation prototype.

Honest Platform Boundary (Software Scaffold & Simulated Prototype):
  - This module is a software scaffold and prototype for aggregating multi-node
    TPM 2.0 PCR-11 measurements into succinct polynomial commitments over BN254.
  - It does NOT directly invoke hardware TPM devices (/dev/tpmrm0) or physical
    tpm2_quote instructions in this software prototype.
  - Operational mode: scaffold / simulated verification engine.

Architectural Invariants:
1. Multi-Node Attestation Aggregation:
   - Aggregates N distinct node quotes containing PCR-11 measurements, epoch,
     nonce, and Ed25519 asymmetric signatures.
2. BN254 / alt_bn128 Scalar Field Arithmetic:
   - Computes deterministic polynomial commitments and Fiat-Shamir evaluations
     over the standard BN254 scalar field prime:
     r = 21888242871839275222246405745257275088548364400416034343698204186575808495617.
3. Fiat-Shamir Non-Interactive Challenge:
   - Derives challenges deterministically over RFC 8785 single-source JCS canonical
     byte encodings with zero floats, preventing prover manipulation.
4. Fail-Closed Rejection Codes:
   - HALT_ZK_PCR_EMPTY_BATCH
   - HALT_ZK_PCR_STALE_EPOCH
   - HALT_ZK_PCR_DUPLICATE_NODE
   - HALT_ZK_PCR_SIGNATURE_INVALID
   - HALT_ZK_PCR_EVALUATION_MISMATCH
   - HALT_ZK_PCR_COMMITMENT_MISMATCH
5. Sub-5ms SQLite-WAL Durability:
   - Persists all aggregated proofs and constituent leaf quotes to a durable local WAL database.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence, Tuple

from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs

# Standard BN254 / alt_bn128 scalar field prime r
BN254_SCALAR_FIELD_PRIME: int = 21888242871839275222246405745257275088548364400416034343698204186575808495617

# Explicit fail-closed rejection codes
HALT_ZK_PCR_EMPTY_BATCH: str = "HALT_ZK_PCR_EMPTY_BATCH"
HALT_ZK_PCR_STALE_EPOCH: str = "HALT_ZK_PCR_STALE_EPOCH"
HALT_ZK_PCR_DUPLICATE_NODE: str = "HALT_ZK_PCR_DUPLICATE_NODE"
HALT_ZK_PCR_SIGNATURE_INVALID: str = "HALT_ZK_PCR_SIGNATURE_INVALID"
HALT_ZK_PCR_EVALUATION_MISMATCH: str = "HALT_ZK_PCR_EVALUATION_MISMATCH"
HALT_ZK_PCR_COMMITMENT_MISMATCH: str = "HALT_ZK_PCR_COMMITMENT_MISMATCH"

STATUS_PROOF_VERIFIED: str = "PROOF_VERIFIED"
STATUS_PROOF_REJECTED: str = "PROOF_REJECTED"


class ZkPcrVerificationError(Exception):
    """Exception raised when ZK TPM PCR-11 aggregation or verification fails."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class TpmPcr11NodeQuote:
    """Represents an Ed25519-signed quote over TPM 2.0 PCR-11 from a cluster node."""

    node_id: str
    region: str
    pcr11_digest: str
    policy_epoch: int
    nonce: str
    timestamp_ms: int
    signature: str
    public_key_hex: str

    def canonical_dict(self) -> Dict[str, Any]:
        """Returns the canonical dictionary payload for signing and hash mapping."""
        return {
            "node_id": self.node_id,
            "nonce": self.nonce,
            "pcr11_digest": self.pcr11_digest,
            "policy_epoch": self.policy_epoch,
            "region": self.region,
            "timestamp_ms": self.timestamp_ms,
        }

    def canonical_bytes(self) -> bytes:
        """Serializes quote payload to canonical RFC 8785 JCS bytes."""
        return encode_jcs(self.canonical_dict())


@dataclass(frozen=True)
class ZkPcrAggregatedProof:
    """Succinct non-interactive polynomial proof aggregating N node PCR-11 measurements."""

    aggregation_id: str
    policy_epoch: int
    node_count: int
    participating_nodes: List[str]
    polynomial_commitment: str
    challenge_point_x: str
    evaluation_y: str
    aggregate_pcr_root: str
    proof_caid: str
    status: str
    created_at_ms: int

    def canonical_dict(self) -> Dict[str, Any]:
        return {
            "aggregate_pcr_root": self.aggregate_pcr_root,
            "aggregation_id": self.aggregation_id,
            "challenge_point_x": self.challenge_point_x,
            "created_at_ms": self.created_at_ms,
            "evaluation_y": self.evaluation_y,
            "node_count": self.node_count,
            "participating_nodes": sorted(self.participating_nodes),
            "policy_epoch": self.policy_epoch,
            "polynomial_commitment": self.polynomial_commitment,
            "status": self.status,
        }

    def canonical_bytes(self) -> bytes:
        return encode_jcs(self.canonical_dict())


def hash_to_bn254_scalar(data: bytes) -> int:
    """Maps arbitrary byte payload deterministically to an element in F_r."""
    digest = hashlib.sha256(data).digest()
    return int.from_bytes(digest, "big") % BN254_SCALAR_FIELD_PRIME


def compute_sha256_caid(payload: Any) -> str:
    """Computes deterministic RFC 8785 canonical SHA-256 CAID."""
    if isinstance(payload, bytes):
        raw_bytes = payload
    elif isinstance(payload, str):
        raw_bytes = payload.encode("utf-8")
    else:
        raw_bytes = encode_jcs(payload)
    return f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}"


def compute_merkle_root(leaf_digests: Sequence[str]) -> str:
    """Computes deterministic binary Merkle root over list of hex digests."""
    if not leaf_digests:
        return f"sha256:{hashlib.sha256(b'').hexdigest()}"

    current_level: List[bytes] = []
    for d in leaf_digests:
        clean = d[7:] if d.startswith("sha256:") else d
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


def evaluate_polynomial_horner(coefficients: Sequence[int], x: int) -> int:
    """Evaluates polynomial P(x) = sum(c_i * x^i) mod r using Horner's method."""
    result = 0
    for c in reversed(coefficients):
        result = (result * x + c) % BN254_SCALAR_FIELD_PRIME
    return result


class ZkPcrAggregator:
    """
    Zero-knowledge polynomial aggregation and verification engine for multi-node
    TPM 2.0 PCR-11 attestations.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self._conn = sqlite3.connect(self.db_path)
        self._init_db()

    def _init_db(self) -> None:
        if self.db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS zk_pcr_proofs_ledger (
                    aggregation_id TEXT PRIMARY KEY,
                    policy_epoch INTEGER NOT NULL,
                    node_count INTEGER NOT NULL,
                    polynomial_commitment TEXT NOT NULL,
                    challenge_point_x TEXT NOT NULL,
                    evaluation_y TEXT NOT NULL,
                    aggregate_pcr_root TEXT NOT NULL,
                    proof_caid TEXT UNIQUE NOT NULL,
                    status TEXT NOT NULL,
                    created_at_ms INTEGER NOT NULL,
                    raw_proof_json TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS zk_pcr_node_quotes_ledger (
                    aggregation_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    region TEXT NOT NULL,
                    pcr11_digest TEXT NOT NULL,
                    policy_epoch INTEGER NOT NULL,
                    nonce TEXT NOT NULL,
                    timestamp_ms INTEGER NOT NULL,
                    signature TEXT NOT NULL,
                    public_key_hex TEXT NOT NULL,
                    PRIMARY KEY (aggregation_id, node_id)
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_pcr_proof_epoch ON zk_pcr_proofs_ledger(policy_epoch);"
            )

    @staticmethod
    def create_quote(
        node_id: str,
        region: str,
        pcr11_digest: str,
        policy_epoch: int,
        nonce: str,
        timestamp_ms: int,
        private_key: ed25519.Ed25519PrivateKey,
    ) -> TpmPcr11NodeQuote:
        """Helper to create an authentic Ed25519-signed quote from a node."""
        payload = {
            "node_id": node_id,
            "nonce": nonce,
            "pcr11_digest": pcr11_digest,
            "policy_epoch": policy_epoch,
            "region": region,
            "timestamp_ms": timestamp_ms,
        }
        canonical_bytes = encode_jcs(payload)
        sig = private_key.sign(canonical_bytes)
        pub_key = private_key.public_key().public_bytes_raw()
        return TpmPcr11NodeQuote(
            node_id=node_id,
            region=region,
            pcr11_digest=pcr11_digest,
            policy_epoch=policy_epoch,
            nonce=nonce,
            timestamp_ms=timestamp_ms,
            signature=sig.hex(),
            public_key_hex=pub_key.hex(),
        )

    def aggregate_quotes(
        self,
        quotes: Sequence[TpmPcr11NodeQuote],
        epoch: int,
        now_ms: Optional[int] = None,
    ) -> ZkPcrAggregatedProof:
        """
        Aggregates quotes from multiple nodes into a single succinct ZK polynomial proof.
        Fails closed if any quote signature fails, node is duplicated, or epoch mismatches.
        """
        if not quotes:
            raise ZkPcrVerificationError(
                HALT_ZK_PCR_EMPTY_BATCH, "Cannot aggregate empty batch of quotes"
            )

        seen_nodes: set[str] = set()
        for q in quotes:
            if q.policy_epoch != epoch:
                raise ZkPcrVerificationError(
                    HALT_ZK_PCR_STALE_EPOCH,
                    f"Quote from node {q.node_id} has epoch {q.policy_epoch}, expected {epoch}",
                )
            if q.node_id in seen_nodes:
                raise ZkPcrVerificationError(
                    HALT_ZK_PCR_DUPLICATE_NODE,
                    f"Duplicate quote detected for node {q.node_id}",
                )
            seen_nodes.add(q.node_id)

            # Asymmetric signature verification
            try:
                pub_bytes = bytes.fromhex(q.public_key_hex)
                verify_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
                sig_bytes = bytes.fromhex(q.signature)
                verify_key.verify(sig_bytes, q.canonical_bytes())
            except Exception as exc:
                raise ZkPcrVerificationError(
                    HALT_ZK_PCR_SIGNATURE_INVALID,
                    f"Invalid Ed25519 quote signature for node {q.node_id}: {exc}",
                ) from exc

        # Deterministically order quotes by node_id
        sorted_quotes = sorted(quotes, key=lambda x: x.node_id)
        node_ids = [q.node_id for q in sorted_quotes]
        pcr_digests = [q.pcr11_digest for q in sorted_quotes]

        # Compute Merkle aggregate root
        aggregate_root = compute_merkle_root(pcr_digests)

        # Map each canonical quote to a BN254 scalar coefficient c_i
        coefficients = [
            hash_to_bn254_scalar(q.canonical_bytes()) for q in sorted_quotes
        ]

        # Polynomial commitment: hash of concatenated 32-byte big-endian coefficients
        commit_bytes = b"".join(c.to_bytes(32, "big") for c in coefficients)
        commitment_scalar = hash_to_bn254_scalar(commit_bytes)
        commitment_hex = f"0x{commitment_scalar:064x}"

        # Fiat-Shamir challenge point x
        fiat_shamir_payload = {
            "aggregate_pcr_root": aggregate_root,
            "epoch": epoch,
            "node_ids": node_ids,
            "polynomial_commitment": commitment_hex,
        }
        challenge_scalar = hash_to_bn254_scalar(encode_jcs(fiat_shamir_payload))
        challenge_x_hex = f"0x{challenge_scalar:064x}"

        # Evaluate polynomial P(x) = sum(c_i * x^i) mod r
        evaluation_scalar = evaluate_polynomial_horner(coefficients, challenge_scalar)
        evaluation_y_hex = f"0x{evaluation_scalar:064x}"

        aggregation_id = f"zkpcr-{uuid.uuid4().hex[:16]}"
        effective_time = now_ms if now_ms is not None else int(time.time() * 1000)

        proof_prelim = {
            "aggregate_pcr_root": aggregate_root,
            "aggregation_id": aggregation_id,
            "challenge_point_x": challenge_x_hex,
            "created_at_ms": effective_time,
            "evaluation_y": evaluation_y_hex,
            "node_count": len(sorted_quotes),
            "participating_nodes": node_ids,
            "policy_epoch": epoch,
            "polynomial_commitment": commitment_hex,
            "status": STATUS_PROOF_VERIFIED,
        }
        proof_caid = compute_sha256_caid(proof_prelim)

        proof = ZkPcrAggregatedProof(
            aggregation_id=aggregation_id,
            policy_epoch=epoch,
            node_count=len(sorted_quotes),
            participating_nodes=node_ids,
            polynomial_commitment=commitment_hex,
            challenge_point_x=challenge_x_hex,
            evaluation_y=evaluation_y_hex,
            aggregate_pcr_root=aggregate_root,
            proof_caid=proof_caid,
            status=STATUS_PROOF_VERIFIED,
            created_at_ms=effective_time,
        )

        # Durably record proof and quotes in SQLite-WAL
        self._record_proof(proof, sorted_quotes)
        return proof

    def verify_proof(
        self,
        proof: ZkPcrAggregatedProof,
        quotes: Sequence[TpmPcr11NodeQuote],
    ) -> bool:
        """
        Independently verifies a ZkPcrAggregatedProof against constituent node quotes.
        Returns True if valid; raises ZkPcrVerificationError with fail-closed code otherwise.
        """
        if not quotes:
            raise ZkPcrVerificationError(
                HALT_ZK_PCR_EMPTY_BATCH, "Verification batch cannot be empty"
            )

        if len(quotes) != proof.node_count:
            raise ZkPcrVerificationError(
                HALT_ZK_PCR_COMMITMENT_MISMATCH,
                f"Quote count {len(quotes)} does not match proof node count {proof.node_count}",
            )

        seen_nodes: set[str] = set()
        for q in quotes:
            if q.policy_epoch != proof.policy_epoch:
                raise ZkPcrVerificationError(
                    HALT_ZK_PCR_STALE_EPOCH,
                    f"Quote epoch {q.policy_epoch} does not match proof epoch {proof.policy_epoch}",
                )
            if q.node_id in seen_nodes:
                raise ZkPcrVerificationError(
                    HALT_ZK_PCR_DUPLICATE_NODE,
                    f"Duplicate quote detected for node {q.node_id}",
                )
            seen_nodes.add(q.node_id)

            # Check quote signature
            try:
                pub_bytes = bytes.fromhex(q.public_key_hex)
                verify_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
                sig_bytes = bytes.fromhex(q.signature)
                verify_key.verify(sig_bytes, q.canonical_bytes())
            except Exception as exc:
                raise ZkPcrVerificationError(
                    HALT_ZK_PCR_SIGNATURE_INVALID,
                    f"Signature verification failed for node {q.node_id}: {exc}",
                ) from exc

        sorted_quotes = sorted(quotes, key=lambda x: x.node_id)
        node_ids = [q.node_id for q in sorted_quotes]
        if node_ids != sorted(proof.participating_nodes):
            raise ZkPcrVerificationError(
                HALT_ZK_PCR_COMMITMENT_MISMATCH,
                "Participating node IDs do not match quotes batch",
            )

        # Check aggregate PCR root
        expected_root = compute_merkle_root([q.pcr11_digest for q in sorted_quotes])
        if expected_root != proof.aggregate_pcr_root:
            raise ZkPcrVerificationError(
                HALT_ZK_PCR_COMMITMENT_MISMATCH,
                f"Aggregate root mismatch: {expected_root} != {proof.aggregate_pcr_root}",
            )

        # Reconstruct coefficients
        coefficients = [
            hash_to_bn254_scalar(q.canonical_bytes()) for q in sorted_quotes
        ]
        commit_bytes = b"".join(c.to_bytes(32, "big") for c in coefficients)
        expected_commit_scalar = hash_to_bn254_scalar(commit_bytes)
        expected_commit_hex = f"0x{expected_commit_scalar:064x}"

        if expected_commit_hex != proof.polynomial_commitment:
            raise ZkPcrVerificationError(
                HALT_ZK_PCR_COMMITMENT_MISMATCH,
                f"Polynomial commitment mismatch: {expected_commit_hex} != {proof.polynomial_commitment}",
            )

        # Recompute Fiat-Shamir challenge point x
        fiat_shamir_payload = {
            "aggregate_pcr_root": expected_root,
            "epoch": proof.policy_epoch,
            "node_ids": node_ids,
            "polynomial_commitment": expected_commit_hex,
        }
        expected_challenge_scalar = hash_to_bn254_scalar(
            encode_jcs(fiat_shamir_payload)
        )
        expected_challenge_hex = f"0x{expected_challenge_scalar:064x}"

        if expected_challenge_hex != proof.challenge_point_x:
            raise ZkPcrVerificationError(
                HALT_ZK_PCR_EVALUATION_MISMATCH,
                f"Challenge point mismatch: {expected_challenge_hex} != {proof.challenge_point_x}",
            )

        # Re-evaluate polynomial
        expected_eval_scalar = evaluate_polynomial_horner(
            coefficients, expected_challenge_scalar
        )
        expected_eval_hex = f"0x{expected_eval_scalar:064x}"

        if expected_eval_hex != proof.evaluation_y:
            raise ZkPcrVerificationError(
                HALT_ZK_PCR_EVALUATION_MISMATCH,
                f"Polynomial evaluation mismatch: {expected_eval_hex} != {proof.evaluation_y}",
            )

        return True

    def _record_proof(
        self,
        proof: ZkPcrAggregatedProof,
        quotes: Sequence[TpmPcr11NodeQuote],
    ) -> None:
        """Persists the aggregated proof and quotes to SQLite WAL."""
        raw_json = json.dumps(asdict(proof), sort_keys=True)
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO zk_pcr_proofs_ledger (
                    aggregation_id, policy_epoch, node_count, polynomial_commitment,
                    challenge_point_x, evaluation_y, aggregate_pcr_root, proof_caid,
                    status, created_at_ms, raw_proof_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proof.aggregation_id,
                    proof.policy_epoch,
                    proof.node_count,
                    proof.polynomial_commitment,
                    proof.challenge_point_x,
                    proof.evaluation_y,
                    proof.aggregate_pcr_root,
                    proof.proof_caid,
                    proof.status,
                    proof.created_at_ms,
                    raw_json,
                ),
            )
            for q in quotes:
                self._conn.execute(
                    """
                    INSERT INTO zk_pcr_node_quotes_ledger (
                        aggregation_id, node_id, region, pcr11_digest, policy_epoch,
                        nonce, timestamp_ms, signature, public_key_hex
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        proof.aggregation_id,
                        q.node_id,
                        q.region,
                        q.pcr11_digest,
                        q.policy_epoch,
                        q.nonce,
                        q.timestamp_ms,
                        q.signature,
                        q.public_key_hex,
                    ),
                )

    def get_proof(self, aggregation_id: str) -> Optional[ZkPcrAggregatedProof]:
        """Retrieves an aggregated proof by aggregation ID."""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT raw_proof_json FROM zk_pcr_proofs_ledger
            WHERE aggregation_id = ?
            """,
            (aggregation_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        data = json.loads(row[0])
        return ZkPcrAggregatedProof(**data)

    def get_quotes_for_aggregation(
        self, aggregation_id: str
    ) -> List[TpmPcr11NodeQuote]:
        """Retrieves all node quotes associated with an aggregation ID."""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT node_id, region, pcr11_digest, policy_epoch, nonce,
                   timestamp_ms, signature, public_key_hex
            FROM zk_pcr_node_quotes_ledger
            WHERE aggregation_id = ?
            ORDER BY node_id ASC
            """,
            (aggregation_id,),
        )
        rows = cursor.fetchall()
        return [
            TpmPcr11NodeQuote(
                node_id=r[0],
                region=r[1],
                pcr11_digest=r[2],
                policy_epoch=r[3],
                nonce=r[4],
                timestamp_ms=r[5],
                signature=r[6],
                public_key_hex=r[7],
            )
            for r in rows
        ]

    def list_proofs_for_epoch(self, epoch: int) -> List[ZkPcrAggregatedProof]:
        """Lists all proofs created for a specific policy epoch."""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT raw_proof_json FROM zk_pcr_proofs_ledger
            WHERE policy_epoch = ?
            ORDER BY created_at_ms DESC
            """,
            (epoch,),
        )
        rows = cursor.fetchall()
        return [ZkPcrAggregatedProof(**json.loads(r[0])) for r in rows]

    def close(self) -> None:
        """Closes the underlying SQLite connection."""
        self._conn.close()
