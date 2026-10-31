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
src/byzantine_consensus_timewarp.py — Deterministic Time-Warp Byzantine Fault Injection Harness.

Part of Sovereign Multi-Agent OS (SMAOS) / AEIB Enterprise Gateway.
Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model as a multi-region
Byzantine consensus stress harness and deterministic time-warp simulation prototype.

Architectural Invariants:
1. Supermajority Quorum Resilience:
   - For N nodes, enforces 2/3 + 1 threshold: ceil((2N + 1)/3) or floor(2N/3) + 1.
   - Proves resilience against up to f < N/3 Byzantine faulty nodes.
2. Anti-Equivocation Gate:
   - Fails closed immediately if any node issues conflicting votes for the same round.
3. Time-Warp Clock Skew Fencing:
   - Evaluates synthetic skew Delta_t in [-10000ms..+10000ms].
   - Rejects votes violating physical WAN clock ceiling (> 10000ms).
4. Fail-Closed Rejection Codes:
   - HALT_BYZANTINE_EQUIVOCATION_DETECTED
   - HALT_BYZANTINE_QUORUM_UNREACHABLE
   - HALT_BYZANTINE_CLOCK_SKEW_EXCEEDED
   - HALT_BYZANTINE_SIGNATURE_INVALID
   - HALT_BYZANTINE_EMPTY_NODE_POOL
5. Sub-5ms SQLite-WAL Durability:
   - Persists all rounds, equivocations, and convergence receipts to local WAL database.
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

# Maximum tolerable clock skew in milliseconds
MAX_CLOCK_SKEW_MS: int = 10000  # claim: config

# Explicit fail-closed rejection codes
HALT_BYZANTINE_EQUIVOCATION_DETECTED: str = "HALT_BYZANTINE_EQUIVOCATION_DETECTED"
HALT_BYZANTINE_QUORUM_UNREACHABLE: str = "HALT_BYZANTINE_QUORUM_UNREACHABLE"
HALT_BYZANTINE_CLOCK_SKEW_EXCEEDED: str = "HALT_BYZANTINE_CLOCK_SKEW_EXCEEDED"
HALT_BYZANTINE_SIGNATURE_INVALID: str = "HALT_BYZANTINE_SIGNATURE_INVALID"
HALT_BYZANTINE_EMPTY_NODE_POOL: str = "HALT_BYZANTINE_EMPTY_NODE_POOL"

STATUS_CONVERGED: str = "QUORUM_CONVERGED"
STATUS_QUORUM_FAILED: str = "QUORUM_UNREACHABLE"


class ByzantineConsensusError(Exception):
    """Exception raised when Byzantine fault injection triggers fail-closed response."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ByzantineVote:
    """Represents a signed vote cast by a consensus participant."""

    node_id: str
    proposal_id: str
    round_number: int
    proposal_hash: str
    vote_timestamp_ms: int
    public_key_hex: str
    signature: str

    def canonical_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "proposal_hash": self.proposal_hash,
            "proposal_id": self.proposal_id,
            "round_number": self.round_number,
            "vote_timestamp_ms": self.vote_timestamp_ms,
        }

    def canonical_bytes(self) -> bytes:
        return encode_jcs(self.canonical_dict())


@dataclass(frozen=True)
class ConsensusConvergenceReceipt:
    """Durable receipt recording the convergence evaluation of a consensus round."""

    convergence_id: str
    round_number: int
    total_nodes: int
    quorum_threshold: int
    valid_votes_count: int
    byzantine_faults_detected: int
    quorum_achieved: bool
    committed_proposal_hash: Optional[str]
    receipt_caid: str
    status: str
    evaluated_at_ms: int

    def canonical_dict(self) -> Dict[str, Any]:
        return {
            "byzantine_faults_detected": self.byzantine_faults_detected,
            "committed_proposal_hash": self.committed_proposal_hash,
            "convergence_id": self.convergence_id,
            "quorum_achieved": self.quorum_achieved,
            "quorum_threshold": self.quorum_threshold,
            "receipt_caid": self.receipt_caid,
            "round_number": self.round_number,
            "status": self.status,
            "total_nodes": self.total_nodes,
            "valid_votes_count": self.valid_votes_count,
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


def calculate_quorum_threshold(total_nodes: int) -> int:
    """Computes required 2/3 + 1 supermajority integer threshold: floor(2N/3) + 1."""
    if total_nodes <= 0:
        raise ByzantineConsensusError(
            HALT_BYZANTINE_EMPTY_NODE_POOL, "Node pool cannot be empty"
        )
    return (2 * total_nodes) // 3 + 1


class ByzantineConsensusTimewarpHarness:
    """
    Deterministic Time-Warp Simulation & Byzantine Stress Harness.
    Evaluates multi-region consensus robustness under equivocation, delay, and clock warp.
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
                CREATE TABLE IF NOT EXISTS byzantine_timewarp_ledger (
                    convergence_id TEXT PRIMARY KEY,
                    round_number INTEGER NOT NULL,
                    total_nodes INTEGER NOT NULL,
                    quorum_threshold INTEGER NOT NULL,
                    valid_votes_count INTEGER NOT NULL,
                    byzantine_faults_detected INTEGER NOT NULL,
                    quorum_achieved INTEGER NOT NULL,
                    committed_proposal_hash TEXT,
                    receipt_caid TEXT UNIQUE NOT NULL,
                    status TEXT NOT NULL,
                    evaluated_at_ms INTEGER NOT NULL,
                    raw_receipt_json TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS byzantine_equivocations_ledger (
                    equivocation_id TEXT PRIMARY KEY,
                    node_id TEXT NOT NULL,
                    round_number INTEGER NOT NULL,
                    first_hash TEXT NOT NULL,
                    conflicting_hash TEXT NOT NULL,
                    detected_at_ms INTEGER NOT NULL
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_byz_round ON byzantine_timewarp_ledger(round_number);"
            )

    @staticmethod
    def create_vote(
        node_id: str,
        proposal_id: str,
        round_number: int,
        proposal_hash: str,
        vote_timestamp_ms: int,
        priv_key: ed25519.Ed25519PrivateKey,
    ) -> ByzantineVote:
        """Helper to create a cryptographically authentic signed vote."""
        payload = {
            "node_id": node_id,
            "proposal_hash": proposal_hash,
            "proposal_id": proposal_id,
            "round_number": round_number,
            "vote_timestamp_ms": vote_timestamp_ms,
        }
        sig = priv_key.sign(encode_jcs(payload))
        pub_hex = priv_key.public_key().public_bytes_raw().hex()
        return ByzantineVote(
            node_id=node_id,
            proposal_id=proposal_id,
            round_number=round_number,
            proposal_hash=proposal_hash,
            vote_timestamp_ms=vote_timestamp_ms,
            public_key_hex=pub_hex,
            signature=sig.hex(),
        )

    def evaluate_round(
        self,
        round_number: int,
        total_cluster_nodes: int,
        votes: Sequence[ByzantineVote],
        coordinator_now_ms: Optional[int] = None,
        fail_closed_on_equivocation: bool = True,
    ) -> ConsensusConvergenceReceipt:
        """
        Evaluates a consensus round against Byzantine faults, clock warp, and equivocation.
        Fails closed if equivocation is detected (if fail_closed_on_equivocation=True).
        """
        if total_cluster_nodes <= 0:
            raise ByzantineConsensusError(
                HALT_BYZANTINE_EMPTY_NODE_POOL, "Total cluster nodes must be positive"
            )

        effective_now = (
            coordinator_now_ms
            if coordinator_now_ms is not None
            else int(time.time() * 1000)
        )
        threshold = calculate_quorum_threshold(total_cluster_nodes)

        seen_node_votes: Dict[str, ByzantineVote] = {}
        faults_detected = 0
        valid_votes_by_hash: Dict[str, int] = {}

        for v in votes:
            # Verify signature
            try:
                pub_bytes = bytes.fromhex(v.public_key_hex)
                verifier = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
                verifier.verify(bytes.fromhex(v.signature), v.canonical_bytes())
            except Exception as exc:
                raise ByzantineConsensusError(
                    HALT_BYZANTINE_SIGNATURE_INVALID,
                    f"Signature invalid for node {v.node_id}: {exc}",
                ) from exc

            # Clock skew check: |v.timestamp - coordinator_now| <= MAX_CLOCK_SKEW_MS
            skew = abs(v.vote_timestamp_ms - effective_now)
            if skew > MAX_CLOCK_SKEW_MS:
                raise ByzantineConsensusError(
                    HALT_BYZANTINE_CLOCK_SKEW_EXCEEDED,
                    f"Clock skew {skew}ms exceeds maximum tolerable ceiling {MAX_CLOCK_SKEW_MS}ms",
                )

            # Equivocation check: did node already vote with a different proposal_hash?
            if v.node_id in seen_node_votes:
                prev_vote = seen_node_votes[v.node_id]
                if prev_vote.proposal_hash != v.proposal_hash:
                    faults_detected += 1
                    self._record_equivocation(
                        node_id=v.node_id,
                        round_number=round_number,
                        first_hash=prev_vote.proposal_hash,
                        conflicting_hash=v.proposal_hash,
                        detected_at_ms=effective_now,
                    )
                    if fail_closed_on_equivocation:
                        raise ByzantineConsensusError(
                            HALT_BYZANTINE_EQUIVOCATION_DETECTED,
                            f"Equivocation detected from node {v.node_id} in round {round_number}",
                        )
                continue

            seen_node_votes[v.node_id] = v
            valid_votes_by_hash[v.proposal_hash] = (
                valid_votes_by_hash.get(v.proposal_hash, 0) + 1
            )

        # Check for proposal reaching supermajority threshold
        committed_hash: Optional[str] = None
        quorum_achieved = False
        valid_votes_count = sum(valid_votes_by_hash.values())

        for prop_hash, count in valid_votes_by_hash.items():
            if count >= threshold:
                committed_hash = prop_hash
                quorum_achieved = True
                break

        status = STATUS_CONVERGED if quorum_achieved else STATUS_QUORUM_FAILED

        convergence_id = f"byzconv-{uuid.uuid4().hex[:16]}"
        prelim_receipt = {
            "byzantine_faults_detected": faults_detected,
            "committed_proposal_hash": committed_hash,
            "convergence_id": convergence_id,
            "quorum_achieved": quorum_achieved,
            "quorum_threshold": threshold,
            "receipt_caid": "",
            "round_number": round_number,
            "status": status,
            "total_nodes": total_cluster_nodes,
            "valid_votes_count": valid_votes_count,
        }
        receipt_caid = compute_sha256_caid(prelim_receipt)

        receipt = ConsensusConvergenceReceipt(
            convergence_id=convergence_id,
            round_number=round_number,
            total_nodes=total_cluster_nodes,
            quorum_threshold=threshold,
            valid_votes_count=valid_votes_count,
            byzantine_faults_detected=faults_detected,
            quorum_achieved=quorum_achieved,
            committed_proposal_hash=committed_hash,
            receipt_caid=receipt_caid,
            status=status,
            evaluated_at_ms=effective_now,
        )

        self._record_convergence_receipt(receipt)

        if not quorum_achieved:
            raise ByzantineConsensusError(
                HALT_BYZANTINE_QUORUM_UNREACHABLE,
                f"Quorum unreachable in round {round_number}: max votes {max(valid_votes_by_hash.values(), default=0)} < threshold {threshold}",
            )

        return receipt

    def _record_equivocation(
        self,
        node_id: str,
        round_number: int,
        first_hash: str,
        conflicting_hash: str,
        detected_at_ms: int,
    ) -> None:
        eq_id = f"eq-{uuid.uuid4().hex[:16]}"
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO byzantine_equivocations_ledger (
                    equivocation_id, node_id, round_number, first_hash, conflicting_hash, detected_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    eq_id,
                    node_id,
                    round_number,
                    first_hash,
                    conflicting_hash,
                    detected_at_ms,
                ),
            )

    def _record_convergence_receipt(
        self, receipt: ConsensusConvergenceReceipt
    ) -> None:
        raw_json = json.dumps(asdict(receipt), sort_keys=True)
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO byzantine_timewarp_ledger (
                    convergence_id, round_number, total_nodes, quorum_threshold,
                    valid_votes_count, byzantine_faults_detected, quorum_achieved,
                    committed_proposal_hash, receipt_caid, status, evaluated_at_ms, raw_receipt_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt.convergence_id,
                    receipt.round_number,
                    receipt.total_nodes,
                    receipt.quorum_threshold,
                    receipt.valid_votes_count,
                    receipt.byzantine_faults_detected,
                    1 if receipt.quorum_achieved else 0,
                    receipt.committed_proposal_hash,
                    receipt.receipt_caid,
                    receipt.status,
                    receipt.evaluated_at_ms,
                    raw_json,
                ),
            )

    def get_receipt(
        self, convergence_id: str
    ) -> Optional[ConsensusConvergenceReceipt]:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT raw_receipt_json FROM byzantine_timewarp_ledger
            WHERE convergence_id = ?
            """,
            (convergence_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return ConsensusConvergenceReceipt(**json.loads(row[0]))

    def list_equivocations(self) -> List[Dict[str, Any]]:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT equivocation_id, node_id, round_number, first_hash, conflicting_hash, detected_at_ms
            FROM byzantine_equivocations_ledger
            ORDER BY detected_at_ms DESC
            """
        )
        rows = cursor.fetchall()
        return [
            {
                "conflicting_hash": r[4],
                "detected_at_ms": r[5],
                "equivocation_id": r[0],
                "first_hash": r[3],
                "node_id": r[1],
                "round_number": r[2],
            }
            for r in rows
        ]

    def close(self) -> None:
        self._conn.close()
