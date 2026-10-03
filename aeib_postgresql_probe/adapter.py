# Copyright 2026 SovereignNexus. All Rights Reserved.
# PROPRIETARY AND TRADE SECRET — UNAUTHORIZED COPYING, DISTRIBUTION,
# OR DECOMPILATION STRICTLY PROHIBITED.
# Licensed under SovereignNexus Commercial License.

# EXPERIMENTAL / PROTOTYPE (PHASE 2 EXTENSION)
"""
aeib_postgresql_probe/adapter.py — Production PostgreSQL 16 Authoritative State Prober
Sovereign Multi-Agent OS (SMAOS) / AEIB Enterprise v1.0

Features & Invariants:
  1. Primary-Writer Fencing:
     - Enforces target_session_attrs=read-write.
     - Actively validates SHOW transaction_read_only == 'off' and pg_is_in_recovery() == false.
     - Immediately rejects read replicas with ReadOnlyReplicaRejectedError.
  2. Bounded Settlement & Repeated Probing:
     - Implements repeated probes over a bounded settlement horizon instead of a naive fixed sleep.
     - Transitions: DISPATCHED_UNCONFIRMED -> PROBE_PENDING -> VERIFIED / NOT_FOUND_AFTER_GRACE.
  3. Thundering Herd Mitigation:
     - Per-key probe coalescing (SingleFlight) collapses concurrent duplicate probes into a single DB query.
     - Circuit breaker trips to PROBE_UNAVAILABLE under connection starvation.
     - Invariant: Probe failure preserves retry prohibition (retry_allowed = False).
  4. Single-Authority Scope Boundary:
     - Explicitly tags evidence with authority_scope="single_authority:postgresql".
     - Disclaims multi-resource global atomicity.
  5. Zero-Mock Policy: Zero synthetic mocks; real psycopg2 pool handling.
"""

import os
import time
import json
import random
import hashlib
import threading
from enum import Enum
from typing import Optional, Dict, Any, List, Callable

try:
    import psycopg2
    from psycopg2.pool import ThreadedConnectionPool
    from psycopg2.errors import QueryCanceled
except ImportError:
    psycopg2 = None
    ThreadedConnectionPool = None
    QueryCanceled = Exception


class ProbeResult(Enum):
    OUTCOME_VERIFIED = "OUTCOME_VERIFIED"
    PROBE_PENDING = "PROBE_PENDING"
    NOT_FOUND_AFTER_GRACE = "NOT_FOUND_AFTER_GRACE"
    RECONCILIATION_NOT_FOUND = "RECONCILIATION_NOT_FOUND"
    RECONCILIATION_CONFLICT = "RECONCILIATION_CONFLICT"
    PROBE_UNAVAILABLE = "PROBE_UNAVAILABLE"
    READ_ONLY_REPLICA_REJECTED = "READ_ONLY_REPLICA_REJECTED"
    PROBE_TIMEOUT = "PROBE_TIMEOUT"


class ReadOnlyReplicaRejectedError(Exception):
    """Raised when an authoritative probe connects to a read-only replica instead of primary writer."""
    pass


class ProbeOutcome:
    def __init__(
        self,
        result: ProbeResult,
        evidence: Optional[Dict[str, Any]] = None,
        error_message: str = "",
        retry_allowed: bool = False,
        reconciliation_status: str = "PENDING",
        authority_scope: str = "single_authority:postgresql"
    ):
        self.result = result
        self.evidence = evidence or {}
        self.error_message = error_message
        self.retry_allowed = retry_allowed
        self.reconciliation_status = reconciliation_status
        self.authority_scope = authority_scope

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result": self.result.value,
            "evidence": self.evidence,
            "error_message": self.error_message,
            "retry_allowed": self.retry_allowed,
            "reconciliation_status": self.reconciliation_status,
            "authority_scope": self.authority_scope
        }


def project_canonical_json(data: Any) -> str:
    """Deterministic JSON serialization matching canonical RFC 8785 subset."""
    return json.dumps(data, separators=(',', ':'), sort_keys=True, default=str)


class ProbeCoalescer:
    """
    SingleFlight request coalescing for probe executions.
    Collapses concurrent identical idempotency_key lookups into a single execution.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._inflight: Dict[str, List[threading.Event]] = {}
        self._results: Dict[str, ProbeOutcome] = {}
        self.coalesced_queries_count = 0

    def execute(self, key: str, query_fn: Callable[[], ProbeOutcome]) -> ProbeOutcome:
        event = threading.Event()
        with self._lock:
            if key in self._inflight:
                self.coalesced_queries_count += 1
                self._inflight[key].append(event)
                is_leader = False
            else:
                self._inflight[key] = [event]
                is_leader = True

        if not is_leader:
            event.wait(timeout=10.0)
            with self._lock:
                return self._results.get(key, ProbeOutcome(ProbeResult.PROBE_TIMEOUT, error_message="Coalescing wait timeout"))

        # Leader executes the query
        try:
            outcome = query_fn()
        except Exception as e:
            outcome = ProbeOutcome(ProbeResult.PROBE_UNAVAILABLE, error_message=str(e), retry_allowed=False)

        with self._lock:
            self._results[key] = outcome
            waiters = self._inflight.pop(key, [])
            for w in waiters:
                if w != event:
                    w.set()

        return outcome


class ProbeCircuitBreaker:
    """
    Circuit breaker protecting the database from thundering herd saturation.
    Fails closed: when tripped, immediately returns PROBE_UNAVAILABLE (retry_allowed=False).
    """
    def __init__(self, failure_threshold: int = 5, recovery_timeout_sec: float = 10.0):
        self._lock = threading.Lock()
        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec
        self.failure_count = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.last_failure_time = 0.0
        self.trip_count = 0

    def can_execute(self) -> bool:
        with self._lock:
            if self.state == "CLOSED":
                return True
            if self.state == "OPEN":
                if time.time() - self.last_failure_time > self.recovery_timeout_sec:
                    self.state = "HALF_OPEN"
                    return True
                return False
            # HALF_OPEN allows a single probe attempt
            return True

    def record_success(self):
        with self._lock:
            self.failure_count = 0
            self.state = "CLOSED"

    def record_failure(self):
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                if self.state != "OPEN":
                    self.trip_count += 1
                self.state = "OPEN"


class PostgresProbeAdapter:
    """
    Production PostgreSQL Authoritative State Prober.
    Fences to primary writer, enforces bounded settlement windows, and coalesces concurrent probes.
    """
    def __init__(self, dsn: str, minconn: int = 1, maxconn: int = 10, lazy_init: bool = False):
        # Enforce target_session_attrs=read-write in DSN to target Primary Writer
        if "target_session_attrs" not in dsn:
            sep = "&" if "?" in dsn else "?"
            dsn = f"{dsn}{sep}target_session_attrs=read-write"
        self.dsn = dsn
        self.minconn = minconn
        self.maxconn = maxconn
        self.coalescer = ProbeCoalescer()
        self.circuit_breaker = ProbeCircuitBreaker(failure_threshold=5, recovery_timeout_sec=5.0)
        self.pool = None
        if not lazy_init and psycopg2:
            try:
                self.pool = ThreadedConnectionPool(minconn, maxconn, dsn)
            except Exception:
                self.pool = None

    def close(self):
        if self.pool:
            self.pool.closeall()

    def _safe_rollback(self, conn):
        try:
            conn.rollback()
        except Exception:
            pass

    def validate_primary_writer(self, conn) -> None:
        """
        Enforces that the checked-out connection is connected to the authoritative Primary Writer.
        Rejects read-only replicas or warm standby instances.
        """
        with conn.cursor() as cur:
            cur.execute("SHOW transaction_read_only;")
            row = cur.fetchone()
            if row and str(row[0]).strip().lower() in ["on", "true", "yes", "1"]:
                raise ReadOnlyReplicaRejectedError("Read-only replica rejected: authoritative probe requires primary writer.")

            cur.execute("SELECT pg_is_in_recovery();")
            rec_row = cur.fetchone()
            if rec_row and rec_row[0] is True:
                raise ReadOnlyReplicaRejectedError("Standby replica in recovery rejected: authoritative probe requires primary writer.")

    def _execute_single_query(self, idempotency_key: str, table_name: str, statement_timeout_ms: int) -> ProbeOutcome:
        if not self.pool:
            return ProbeOutcome(
                ProbeResult.PROBE_UNAVAILABLE,
                error_message="PostgreSQL driver or connection pool not initialized",
                retry_allowed=False
            )

        if not self.circuit_breaker.can_execute():
            return ProbeOutcome(
                ProbeResult.PROBE_UNAVAILABLE,
                error_message="Circuit breaker OPEN: PostgreSQL pool saturated or offline. Retries prohibited.",
                retry_allowed=False,
                reconciliation_status="PENDING"
            )

        conn = None
        try:
            conn = self.pool.getconn()
            self.validate_primary_writer(conn)

            with conn.cursor() as cur:
                cur.execute(f"SET statement_timeout = {int(statement_timeout_ms)}")
                if not table_name.replace("_", "").isalnum():
                    raise ValueError("Invalid table name")

                cur.execute(f"""
                    SELECT tx_id, intent_id, idempotency_key, amount, status, commit_timestamp 
                    FROM {table_name} 
                    WHERE idempotency_key = %s
                """, (idempotency_key,))
                
                rows = cur.fetchall()
                cols = [desc[0] for desc in cur.description]

                self.circuit_breaker.record_success()

                if len(rows) == 0:
                    return ProbeOutcome(
                        ProbeResult.RECONCILIATION_NOT_FOUND,
                        evidence={"idempotency_key": idempotency_key},
                        retry_allowed=False,
                        reconciliation_status="PENDING"
                    )

                if len(rows) > 1:
                    conflict_data = [dict(zip(cols, r)) for r in rows]
                    c_json = project_canonical_json(conflict_data)
                    c_hash = hashlib.sha256(c_json.encode("utf-8")).hexdigest()
                    return ProbeOutcome(
                        ProbeResult.RECONCILIATION_CONFLICT,
                        evidence={"row_count": len(rows), "conflict_hash": c_hash},
                        retry_allowed=False,
                        reconciliation_status="FAILED"
                    )

                row_dict = dict(zip(cols, rows[0]))
                r_json = project_canonical_json(row_dict)
                r_hash = hashlib.sha256(r_json.encode("utf-8")).hexdigest()
                return ProbeOutcome(
                    ProbeResult.OUTCOME_VERIFIED,
                    evidence={"row": row_dict, "row_hash": r_hash, "authority_scope": "single_authority:postgresql"},
                    retry_allowed=False,
                    reconciliation_status="VERIFIED"
                )

        except ReadOnlyReplicaRejectedError as e:
            if conn:
                self._safe_rollback(conn)
                self.pool.putconn(conn)
                conn = None
            return ProbeOutcome(
                ProbeResult.READ_ONLY_REPLICA_REJECTED,
                error_message=str(e),
                retry_allowed=False,
                reconciliation_status="PENDING"
            )
        except QueryCanceled as e:
            self.circuit_breaker.record_failure()
            if conn:
                self._safe_rollback(conn)
                self.pool.putconn(conn, close=True)
                conn = None
            return ProbeOutcome(
                ProbeResult.PROBE_TIMEOUT,
                error_message=f"Statement timeout exceeded: {e}",
                retry_allowed=False
            )
        except Exception as e:
            self.circuit_breaker.record_failure()
            if conn:
                self._safe_rollback(conn)
                self.pool.putconn(conn, close=True)
                conn = None
            return ProbeOutcome(
                ProbeResult.PROBE_UNAVAILABLE,
                error_message=f"Database probe error: {e}",
                retry_allowed=False
            )
        finally:
            if conn:
                self.pool.putconn(conn)

    def execute_probe(self, idempotency_key: str, table_name: str = "transactions", statement_timeout_ms: int = 5000) -> ProbeOutcome:
        """Executes probe using request coalescing (SingleFlight)."""
        return self.coalescer.execute(
            idempotency_key,
            lambda: self._execute_single_query(idempotency_key, table_name, statement_timeout_ms)
        )

    def execute_bounded_probe(
        self,
        idempotency_key: str,
        table_name: str = "transactions",
        settlement_window_ms: int = 500,
        max_attempts: int = 3,
        backoff_base_ms: int = 50
    ) -> ProbeOutcome:
        """
        Executes repeated probing over a bounded settlement horizon to close the in-flight commit window.
        Returns NOT_FOUND_AFTER_GRACE only after multiple independent probes over the full settlement window confirm absence.
        """
        t_start = time.perf_counter()
        deadline = t_start + (settlement_window_ms / 1000.0)
        attempts = 0

        last_outcome = None
        while time.perf_counter() < deadline and attempts < max_attempts:
            attempts += 1
            outcome = self.execute_probe(idempotency_key, table_name=table_name)
            last_outcome = outcome

            # Terminal confirmations
            if outcome.result in (ProbeResult.OUTCOME_VERIFIED, ProbeResult.RECONCILIATION_CONFLICT):
                return outcome

            # If authority is unavailable or replica rejected, fail closed immediately
            if outcome.result in (ProbeResult.PROBE_UNAVAILABLE, ProbeResult.READ_ONLY_REPLICA_REJECTED):
                return outcome

            # If not found yet, wait with exponential backoff + jitter before retrying
            sleep_duration = (backoff_base_ms * (2 ** (attempts - 1)) + random.randint(5, 25)) / 1000.0
            time.sleep(min(sleep_duration, max(0.01, deadline - time.perf_counter())))

        # If repeated probes across the full settlement window confirm no record:
        if last_outcome and last_outcome.result == ProbeResult.RECONCILIATION_NOT_FOUND:
            return ProbeOutcome(
                ProbeResult.NOT_FOUND_AFTER_GRACE,
                evidence={"idempotency_key": idempotency_key, "attempts": attempts, "settlement_window_ms": settlement_window_ms},
                retry_allowed=True,
                reconciliation_status="NOT_FOUND_AFTER_GRACE"
            )

        return last_outcome or ProbeOutcome(ProbeResult.PROBE_UNAVAILABLE, error_message="Settlement window expired", retry_allowed=False)
