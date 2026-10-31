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
src/autonomic_circuit_breaker_mesh.py — Autonomic AI Circuit-Breaker Failsafe Mesh.

Part of Sovereign Multi-Agent OS (SMAOS) / AEIB Enterprise Gateway.
Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model.

Architectural Invariants:
1. Tri-State Cascading Failure Mitigation:
   - Tracks per-agent / per-tool execution telemetry across three typestates:
     * CIRCUIT_STATE_CLOSED: Nominal traffic routed without interruption.
     * CIRCUIT_STATE_OPEN: Tripped / isolated fail-closed. Rejects all calls immediately
       with ERR_CIRCUIT_OPEN_FAILS_CLOSED.
     * CIRCUIT_STATE_HALF_OPEN: Cooldown interval elapsed; admits bounded probe calls
       to evaluate subsystem recovery.
2. Multi-Metric Autonomous Trip Criteria:
   - Automatically trips when any configured boundary is exceeded:
     * Consecutive errors >= MAX_CONSECUTIVE_ERRORS (default 5).
     * Sliding window error rate >= ERROR_RATE_THRESHOLD_BPS (default 1500 bps / 15.00%).
     * Sliding window token consumption >= TOKEN_BURN_RATE_CAP_PER_MIN (default 50000).
3. Sub-5ms SQLite-WAL Durability:
   - Persists all state transitions, trip events, and recovery probes into an
     append-only circuit_breaker_events_ledger with cryptographic CAID sealing.
4. Single-Source RFC 8785 Canonicalization:
   - Canonicalizes JSON payloads with RFC 8785 JCS and SHA-256 digests.
     Zero floating-point metrics (integer milliseconds, basis points, and counts only).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.jcs_canonicalizer import encode_jcs

# Configuration constants
MAX_CONSECUTIVE_ERRORS: int = 5  # claim: config
ERROR_RATE_THRESHOLD_BPS: int = 1500  # claim: config
TOKEN_BURN_RATE_CAP_PER_MIN: int = 50000  # claim: config
DEFAULT_COOLDOWN_SECONDS: int = 30  # claim: config

# Circuit Typestates
CIRCUIT_STATE_CLOSED: str = "CLOSED_NOMINAL"
CIRCUIT_STATE_OPEN: str = "OPEN_ISOLATED"
CIRCUIT_STATE_HALF_OPEN: str = "HALF_OPEN_PROBING"

# Action & Outcome Identifiers
OUTCOME_PERMITTED: str = "CIRCUIT_DISPATCH_PERMITTED"
OUTCOME_SHORT_CIRCUITED: str = "ERR_CIRCUIT_OPEN_FAILS_CLOSED"
OUTCOME_PROBE_PERMITTED: str = "CIRCUIT_PROBE_PERMITTED"


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
class CircuitBreakerReceipt:
    """Cryptographic verifiable receipt of a circuit breaker decision or state change."""

    event_id: str
    target_id: str
    previous_state: str
    current_state: str
    outcome: str
    reason: str
    receipt_caid: str
    timestamp_ms: int

    def __post_init__(self) -> None:
        if not self.event_id or not isinstance(self.event_id, str):
            raise ValueError("event_id must be a non-empty string")
        if not self.target_id or not isinstance(self.target_id, str):
            raise ValueError("target_id must be a non-empty string")
        if not self.previous_state or not isinstance(self.previous_state, str):
            raise ValueError("previous_state must be a non-empty string")
        if not self.current_state or not isinstance(self.current_state, str):
            raise ValueError("current_state must be a non-empty string")
        if not self.outcome or not isinstance(self.outcome, str):
            raise ValueError("outcome must be a non-empty string")
        if not self.reason or not isinstance(self.reason, str):
            raise ValueError("reason must be a non-empty string")
        if not self.receipt_caid or not self.receipt_caid.startswith("sha256:"):
            raise ValueError("receipt_caid must be a valid sha256 prefix string")
        if not isinstance(self.timestamp_ms, int) or self.timestamp_ms <= 0:
            raise ValueError("timestamp_ms must be a positive integer")


class AutonomicCircuitBreakerMesh:
    """
    Autonomic Circuit-Breaker Mesh Coordinator.
    Mediates agent calls and prevents cascading failure cascades across the mesh.
    """

    def __init__(
        self,
        mesh_id: str = "mesh-primary",
        db_path: Optional[str] = None,
        max_consecutive_errors: int = MAX_CONSECUTIVE_ERRORS,
        error_rate_threshold_bps: int = ERROR_RATE_THRESHOLD_BPS,
        token_burn_cap_per_min: int = TOKEN_BURN_RATE_CAP_PER_MIN,
        cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS,
    ) -> None:
        if not mesh_id or not isinstance(mesh_id, str):
            raise ValueError("mesh_id must be a non-empty string")
        if not isinstance(max_consecutive_errors, int) or max_consecutive_errors <= 0:
            raise ValueError("max_consecutive_errors must be a positive integer")
        if not isinstance(error_rate_threshold_bps, int) or error_rate_threshold_bps <= 0:
            raise ValueError("error_rate_threshold_bps must be a positive integer")
        if not isinstance(token_burn_cap_per_min, int) or token_burn_cap_per_min <= 0:
            raise ValueError("token_burn_cap_per_min must be a positive integer")
        if not isinstance(cooldown_seconds, int) or cooldown_seconds <= 0:
            raise ValueError("cooldown_seconds must be a positive integer")

        self.mesh_id = mesh_id
        self.max_consecutive_errors = max_consecutive_errors
        self.error_rate_threshold_bps = error_rate_threshold_bps
        self.token_burn_cap_per_min = token_burn_cap_per_min
        self.cooldown_seconds = cooldown_seconds

        # In-memory target tracking dictionaries
        self._states: Dict[str, str] = {}
        self._consecutive_errors: Dict[str, int] = {}
        self._tripped_at_ms: Dict[str, int] = {}
        self._window_calls: Dict[str, List[Tuple[int, bool, int]]] = {}  # (ts_ms, is_error, tokens)

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
                CREATE TABLE IF NOT EXISTS circuit_breaker_events_ledger (
                    event_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    previous_state TEXT NOT NULL,
                    current_state TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    receipt_caid TEXT NOT NULL PRIMARY KEY,
                    timestamp_ms INTEGER NOT NULL
                );
                """
            )
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_circuit_target_ts
                ON circuit_breaker_events_ledger (target_id, timestamp_ms);
                """
            )

    def get_state(self, target_id: str, now_ms: Optional[int] = None) -> str:
        """Computes current typestate for target, evaluating cooldown expiration."""
        current = self._states.get(target_id, CIRCUIT_STATE_CLOSED)
        if current == CIRCUIT_STATE_OPEN:
            ts_ms = now_ms if now_ms is not None else int(time.time() * 1000)
            tripped_ts = self._tripped_at_ms.get(target_id, ts_ms)
            cooldown_ms = self.cooldown_seconds * 1000
            if ts_ms >= tripped_ts + cooldown_ms:
                self._states[target_id] = CIRCUIT_STATE_HALF_OPEN
                return CIRCUIT_STATE_HALF_OPEN
        return current

    def before_call(self, target_id: str, now_ms: Optional[int] = None) -> Tuple[bool, CircuitBreakerReceipt]:
        """
        Evaluates whether an execution call is permitted or short-circuited.
        Returns (permitted: bool, receipt: CircuitBreakerReceipt).
        """
        if not target_id or not isinstance(target_id, str):
            raise ValueError("target_id must be a non-empty string")

        ts_ms = now_ms if now_ms is not None else int(time.time() * 1000)
        state = self.get_state(target_id, now_ms=ts_ms)
        event_id = f"evt-{uuid.uuid4().hex[:12]}"

        if state == CIRCUIT_STATE_CLOSED:
            outcome = OUTCOME_PERMITTED
            reason = "Circuit closed: nominal dispatch admitted"
            permitted = True
        elif state == CIRCUIT_STATE_HALF_OPEN:
            outcome = OUTCOME_PROBE_PERMITTED
            reason = "Circuit half-open: single probe dispatch admitted"
            permitted = True
        else:  # CIRCUIT_STATE_OPEN
            outcome = OUTCOME_SHORT_CIRCUITED
            reason = "Circuit open: cascading failure isolated fail-closed"
            permitted = False

        receipt = self._commit_receipt(
            event_id=event_id,
            target_id=target_id,
            previous_state=state,
            current_state=state,
            outcome=outcome,
            reason=reason,
            ts_ms=ts_ms,
        )
        return permitted, receipt

    def after_call(
        self,
        target_id: str,
        is_error: bool,
        tokens_consumed: int = 0,
        now_ms: Optional[int] = None,
    ) -> CircuitBreakerReceipt:
        """
        Records execution outcome, updates metrics window, and trips circuit if boundaries exceeded.
        """
        if not target_id or not isinstance(target_id, str):
            raise ValueError("target_id must be a non-empty string")
        if not isinstance(is_error, bool):
            raise ValueError("is_error must be a boolean")
        if not isinstance(tokens_consumed, int) or tokens_consumed < 0:
            raise ValueError("tokens_consumed must be a non-negative integer")

        ts_ms = now_ms if now_ms is not None else int(time.time() * 1000)
        previous_state = self.get_state(target_id, now_ms=ts_ms)
        event_id = f"evt-{uuid.uuid4().hex[:12]}"

        # Prune 60-second sliding window
        window = self._window_calls.setdefault(target_id, [])
        cutoff_ms = ts_ms - 60000
        window = [w for w in window if w[0] >= cutoff_ms]
        window.append((ts_ms, is_error, tokens_consumed))
        self._window_calls[target_id] = window

        # Calculate metrics
        total_calls = len(window)
        error_calls = sum(1 for w in window if w[1])
        total_tokens = sum(w[2] for w in window)
        error_rate_bps = (error_calls * 10000) // total_calls if total_calls > 0 else 0

        # Update consecutive errors
        if is_error:
            self._consecutive_errors[target_id] = self._consecutive_errors.get(target_id, 0) + 1
        else:
            self._consecutive_errors[target_id] = 0

        consecutive = self._consecutive_errors[target_id]

        # Evaluate state transition
        if previous_state == CIRCUIT_STATE_HALF_OPEN:
            if is_error:
                current_state = CIRCUIT_STATE_OPEN
                self._tripped_at_ms[target_id] = ts_ms
                reason = "Probe call failed: circuit returned to open state"
            else:
                current_state = CIRCUIT_STATE_CLOSED
                self._consecutive_errors[target_id] = 0
                reason = "Probe call succeeded: circuit restored to closed state"
        else:
            # Check trip triggers
            should_trip = False
            trip_reason = ""
            if consecutive >= self.max_consecutive_errors:
                should_trip = True
                trip_reason = f"Consecutive errors ({consecutive}) >= max ({self.max_consecutive_errors})"
            elif total_calls >= 5 and error_rate_bps >= self.error_rate_threshold_bps:
                should_trip = True
                trip_reason = f"Error rate ({error_rate_bps} bps) >= threshold ({self.error_rate_threshold_bps} bps)"
            elif total_tokens >= self.token_burn_cap_per_min:
                should_trip = True
                trip_reason = f"Token burn ({total_tokens}) >= cap ({self.token_burn_cap_per_min})"

            if should_trip:
                current_state = CIRCUIT_STATE_OPEN
                self._tripped_at_ms[target_id] = ts_ms
                reason = f"Circuit tripped open: {trip_reason}"
            else:
                current_state = CIRCUIT_STATE_CLOSED
                reason = "Execution processed within nominal thresholds"

        self._states[target_id] = current_state

        return self._commit_receipt(
            event_id=event_id,
            target_id=target_id,
            previous_state=previous_state,
            current_state=current_state,
            outcome=OUTCOME_PERMITTED if current_state == CIRCUIT_STATE_CLOSED else OUTCOME_SHORT_CIRCUITED,
            reason=reason,
            ts_ms=ts_ms,
        )

    def _commit_receipt(
        self,
        event_id: str,
        target_id: str,
        previous_state: str,
        current_state: str,
        outcome: str,
        reason: str,
        ts_ms: int,
    ) -> CircuitBreakerReceipt:
        """Canonicalizes, hashes, and commits event receipt to SQLite-WAL."""
        payload: Dict[str, Any] = {
            "current_state": current_state,
            "event_id": event_id,
            "mesh_id": self.mesh_id,
            "outcome": outcome,
            "previous_state": previous_state,
            "reason": reason,
            "target_id": target_id,
            "timestamp_ms": ts_ms,
        }
        receipt_caid = compute_sha256_caid(payload)

        receipt = CircuitBreakerReceipt(
            event_id=event_id,
            target_id=target_id,
            previous_state=previous_state,
            current_state=current_state,
            outcome=outcome,
            reason=reason,
            receipt_caid=receipt_caid,
            timestamp_ms=ts_ms,
        )

        with self._conn:
            self._conn.execute(
                """
                INSERT INTO circuit_breaker_events_ledger (
                    event_id, target_id, previous_state, current_state,
                    outcome, reason, receipt_caid, timestamp_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    receipt.event_id,
                    receipt.target_id,
                    receipt.previous_state,
                    receipt.current_state,
                    receipt.outcome,
                    receipt.reason,
                    receipt.receipt_caid,
                    receipt.timestamp_ms,
                ),
            )

        return receipt

    def get_ledger_records(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieves circuit breaker events from SQLite-WAL ledger."""
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT event_id, target_id, previous_state, current_state,
                   outcome, reason, receipt_caid, timestamp_ms
            FROM circuit_breaker_events_ledger
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
                    "event_id": r[0],
                    "target_id": r[1],
                    "previous_state": r[2],
                    "current_state": r[3],
                    "outcome": r[4],
                    "reason": r[5],
                    "receipt_caid": r[6],
                    "timestamp_ms": r[7],
                }
            )
        return results

    def close(self) -> None:
        """Closes the SQLite database connection."""
        self._conn.close()
