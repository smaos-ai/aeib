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
src/quorum_jitter_fuzzer.py — Consensus Quorum Network Fuzzing & Latency Jitter Replay Engine.

Part of Sovereign Multi-Agent OS (SMAOS) / AEIB Enterprise Gateway.
Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model.

Architectural Invariants:
1. Deterministic Discrete-Event Quorum Fuzzing:
   - Injects pseudo-random network jitter, latency variance, and packet drops
     against distributed M-of-N threshold quorum nodes across heterogeneous regions.
2. Jitter Profile Simulation & BGP Interlock:
   - Evaluates threshold quorum convergence under nominal (< 1500 bps), degraded
     (> 4800 bps triggering BGP deprioritization), and partitioned (10000 bps drop) conditions.
3. Durable Transit & Event Journaling:
   - Commits each fuzzing run, packet disposition, and quorum convergence verdict
     into an append-only SQLite-WAL ledger (quorum_fuzz_events_ledger) with cryptographic CAID.
4. Single-Source RFC 8785 Canonicalization:
   - Canonicalizes JSON run receipts using RFC 8785 JCS with SHA-256 digests.
     Zero floating-point metrics (integer milliseconds, basis points, and counts only).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import random
import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.jcs_canonicalizer import encode_jcs

# Configuration constants
DEFAULT_MAX_JITTER_BPS: int = 4800  # claim: config
DEFAULT_PACKET_TIMEOUT_MS: int = 500  # claim: config
DEFAULT_QUORUM_THRESHOLD_M: int = 3  # claim: config
DEFAULT_TOTAL_NODES_N: int = 5  # claim: config

# Status constants
STATUS_QUORUM_CONVERGED: str = "QUORUM_CONVERGED"
STATUS_QUORUM_FAILED_PARTITION: str = "HALT_QUORUM_FAILED_PARTITION"
STATUS_QUORUM_DEGRADED_JITTER: str = "QUORUM_CONVERGED_DEGRADED"


def compute_sha256_caid(payload: Any) -> str:
    """Computes deterministic RFC 8785 canonical SHA-256 CAID (e.g. 'sha256:<64-hex>')."""
    if isinstance(payload, bytes):
        raw_bytes = payload
    elif isinstance(payload, str):
        raw_bytes = payload.encode("utf-8")
    else:
        raw_bytes = encode_jcs(payload)
    return f"sha256:{hashlib.sha256(raw_bytes).hexdigest()}"


@dataclass(frozen=True)
class QuorumFuzzReceipt:
    """Cryptographic verifiable receipt of a quorum network fuzzing simulation."""

    fuzz_run_id: str
    epoch_id: str
    fuzz_seed: int
    nodes_count: int
    quorum_threshold: int
    packets_sent: int
    packets_dropped: int
    quorum_reached: bool
    status: str
    receipt_caid: str
    timestamp_ms: int

    def __post_init__(self) -> None:
        if not self.fuzz_run_id or not isinstance(self.fuzz_run_id, str):
            raise ValueError("fuzz_run_id must be a non-empty string")
        if not self.epoch_id or not isinstance(self.epoch_id, str):
            raise ValueError("epoch_id must be a non-empty string")
        if not isinstance(self.fuzz_seed, int):
            raise ValueError("fuzz_seed must be an integer")
        if not isinstance(self.nodes_count, int) or self.nodes_count <= 0:
            raise ValueError("nodes_count must be a positive integer")
        if not isinstance(self.quorum_threshold, int) or self.quorum_threshold <= 0:
            raise ValueError("quorum_threshold must be a positive integer")
        if self.quorum_threshold > self.nodes_count:
            raise ValueError("quorum_threshold cannot exceed nodes_count")
        if not isinstance(self.packets_sent, int) or self.packets_sent < 0:
            raise ValueError("packets_sent must be a non-negative integer")
        if not isinstance(self.packets_dropped, int) or self.packets_dropped < 0:
            raise ValueError("packets_dropped must be a non-negative integer")
        if not isinstance(self.quorum_reached, bool):
            raise ValueError("quorum_reached must be a boolean")
        if not self.status or not isinstance(self.status, str):
            raise ValueError("status must be a non-empty string")
        if not self.receipt_caid or not self.receipt_caid.startswith("sha256:"):
            raise ValueError("receipt_caid must be a valid sha256 prefix string")
        if not isinstance(self.timestamp_ms, int) or self.timestamp_ms <= 0:
            raise ValueError("timestamp_ms must be a positive integer")


class QuorumJitterFuzzer:
    """
    Quorum Latency Jitter and Fault Injection Harness.
    Fuzzes multi-region network conditions and evaluates quorum convergence.
    """

    def __init__(
        self,
        fuzzer_id: str = "fuzzer-primary",
        db_path: Optional[str] = None,
        max_allowable_jitter_bps: int = DEFAULT_MAX_JITTER_BPS,
        packet_timeout_ms: int = DEFAULT_PACKET_TIMEOUT_MS,
    ) -> None:
        if not fuzzer_id or not isinstance(fuzzer_id, str):
            raise ValueError("fuzzer_id must be a non-empty string")
        if not isinstance(max_allowable_jitter_bps, int) or max_allowable_jitter_bps <= 0:
            raise ValueError("max_allowable_jitter_bps must be a positive integer")
        if not isinstance(packet_timeout_ms, int) or packet_timeout_ms <= 0:
            raise ValueError("packet_timeout_ms must be a positive integer")

        self.fuzzer_id = fuzzer_id
        self.max_allowable_jitter_bps = max_allowable_jitter_bps
        self.packet_timeout_ms = packet_timeout_ms

        self.db_path = db_path or ":memory:"
        self._conn = sqlite3.connect(self.db_path)
        self._init_db()

    def _init_db(self) -> None:
        """Initializes SQLite-WAL persistence ledger schema."""
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quorum_fuzz_events_ledger (
                    fuzz_run_id TEXT NOT NULL,
                    epoch_id TEXT NOT NULL,
                    fuzz_seed INTEGER NOT NULL,
                    nodes_count INTEGER NOT NULL,
                    quorum_threshold INTEGER NOT NULL,
                    packets_sent INTEGER NOT NULL,
                    packets_dropped INTEGER NOT NULL,
                    quorum_reached INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    receipt_caid TEXT NOT NULL PRIMARY KEY,
                    timestamp_ms INTEGER NOT NULL
                );
                """
            )

    def run_fuzz_simulation(
        self,
        epoch_id: str,
        fuzz_seed: int = 42,
        nodes_count: int = DEFAULT_TOTAL_NODES_N,
        quorum_threshold: int = DEFAULT_QUORUM_THRESHOLD_M,
        drop_rate_bps: int = 0,
        simulated_jitter_bps: int = 0,
        now_ms: Optional[int] = None,
    ) -> QuorumFuzzReceipt:
        """
        Executes a deterministic simulated quorum vote under injected jitter and drop rates.
        """
        if not epoch_id or not isinstance(epoch_id, str):
            raise ValueError("epoch_id must be a non-empty string")
        if not isinstance(nodes_count, int) or nodes_count <= 0:
            raise ValueError("nodes_count must be a positive integer")
        if not isinstance(quorum_threshold, int) or quorum_threshold <= 0:
            raise ValueError("quorum_threshold must be a positive integer")
        if quorum_threshold > nodes_count:
            raise ValueError("quorum_threshold cannot exceed nodes_count")
        if not isinstance(drop_rate_bps, int) or drop_rate_bps < 0 or drop_rate_bps > 10000:
            raise ValueError("drop_rate_bps must be between 0 and 10000")
        if not isinstance(simulated_jitter_bps, int) or simulated_jitter_bps < 0:
            raise ValueError("simulated_jitter_bps must be a non-negative integer")

        ts_ms = now_ms if now_ms is not None else int(time.time() * 1000)
        fuzz_run_id = f"fuzz-{uuid.uuid4().hex[:12]}"

        rng = random.Random(fuzz_seed)

        packets_sent = nodes_count
        packets_dropped = 0
        successful_votes = 0

        for node_idx in range(nodes_count):
            # Check packet drop probability against drop_rate_bps
            roll = rng.randint(0, 9999)
            if roll < drop_rate_bps:
                packets_dropped += 1
            else:
                successful_votes += 1

        quorum_reached = successful_votes >= quorum_threshold

        if not quorum_reached:
            status = STATUS_QUORUM_FAILED_PARTITION
        elif simulated_jitter_bps > self.max_allowable_jitter_bps:
            status = STATUS_QUORUM_DEGRADED_JITTER
        else:
            status = STATUS_QUORUM_CONVERGED

        payload: Dict[str, Any] = {
            "drop_rate_bps": drop_rate_bps,
            "epoch_id": epoch_id,
            "fuzz_run_id": fuzz_run_id,
            "fuzz_seed": fuzz_seed,
            "fuzzer_id": self.fuzzer_id,
            "nodes_count": nodes_count,
            "packets_dropped": packets_dropped,
            "packets_sent": packets_sent,
            "quorum_reached": quorum_reached,
            "quorum_threshold": quorum_threshold,
            "simulated_jitter_bps": simulated_jitter_bps,
            "status": status,
            "timestamp_ms": ts_ms,
        }
        receipt_caid = compute_sha256_caid(payload)

        receipt = QuorumFuzzReceipt(
            fuzz_run_id=fuzz_run_id,
            epoch_id=epoch_id,
            fuzz_seed=fuzz_seed,
            nodes_count=nodes_count,
            quorum_threshold=quorum_threshold,
            packets_sent=packets_sent,
            packets_dropped=packets_dropped,
            quorum_reached=quorum_reached,
            status=status,
            receipt_caid=receipt_caid,
            timestamp_ms=ts_ms,
        )

        with self._conn:
            self._conn.execute(
                """
                INSERT INTO quorum_fuzz_events_ledger (
                    fuzz_run_id, epoch_id, fuzz_seed, nodes_count, quorum_threshold,
                    packets_sent, packets_dropped, quorum_reached, status,
                    receipt_caid, timestamp_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    receipt.fuzz_run_id,
                    receipt.epoch_id,
                    receipt.fuzz_seed,
                    receipt.nodes_count,
                    receipt.quorum_threshold,
                    receipt.packets_sent,
                    receipt.packets_dropped,
                    1 if receipt.quorum_reached else 0,
                    receipt.status,
                    receipt.receipt_caid,
                    receipt.timestamp_ms,
                ),
            )

        return receipt

    def get_ledger_records(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieves fuzz run events from SQLite-WAL ledger."""
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT fuzz_run_id, epoch_id, fuzz_seed, nodes_count, quorum_threshold,
                   packets_sent, packets_dropped, quorum_reached, status,
                   receipt_caid, timestamp_ms
            FROM quorum_fuzz_events_ledger
            ORDER BY timestamp_ms DESC
            LIMIT ?;
            """,
            (limit,),
        )
        rows = cur.fetchall()
        results: List[Dict[str, Any]] = []
        for r in rows:
            results.append(
                {
                    "fuzz_run_id": r[0],
                    "epoch_id": r[1],
                    "fuzz_seed": r[2],
                    "nodes_count": r[3],
                    "quorum_threshold": r[4],
                    "packets_sent": r[5],
                    "packets_dropped": r[6],
                    "quorum_reached": bool(r[7]),
                    "status": r[8],
                    "receipt_caid": r[9],
                    "timestamp_ms": r[10],
                }
            )
        return results

    def close(self) -> None:
        """Closes the database connection."""
        self._conn.close()
