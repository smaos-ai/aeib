#!/usr/bin/env python3
"""
src/sqlite_acid_tcc_boundary.py — Enterprise Microservices TCC + ACID Outbox + StructuredTaskScope Boundary

Implements Enterprise Distributed Systems Patterns for Autonomous AI Agents:
1. TCC (Try-Confirm-Cancel) & Pessimistic Escrow (arXiv:2609.15397):
   Pre-socket atomic TCC `Try` reservation across parallel subagent branches prevents
   budget overrun before external HTTP mutations can execute.
2. Transactional Outbox & Temporal Fencing (arXiv:2609.29095):
   Transactional outbox with Visibility-Lag Fencing (`t_reconcile >= t_dispatch + delta_max + lambda_max`)
   prevents premature read-back retries on stale read replicas.
3. Java 21+ StructuredTaskScope (JEP 480) & Immutable DTO Contracts (arXiv:2610.10263):
   Lexically scoped execution with ShutdownOnFailure, deadlines, spec_caid contract verification,
   and automatic TCC reservation rollback on sibling abort.
4. Optimistic Concurrency Control (OCC) with @Version & CAS (AT31/AT50):
   Compare-And-Swap mutations binding policy_epoch and context_manifest_hash to defeat world state drift.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.jcs_canonicalizer import encode_jcs


def sha256_prefixed(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


class SqliteAcidTccBoundary:
    """
    Implements Enterprise Microservices TCC (Try-Confirm-Cancel) + ACID Outbox
    using SQLite WAL and `BEGIN IMMEDIATE` serialized transactions.
    """

    def __init__(self, db_path: Path, workflow_id: str, budget_minor: int) -> None:
        self.db_path = db_path
        self.workflow_id = workflow_id
        self._init_db(budget_minor)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=FULL;")
        return conn

    def _init_db(self, budget_minor: int) -> None:
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_budget (
                    workflow_id TEXT PRIMARY KEY,
                    budget_minor INTEGER NOT NULL,
                    reserved_minor INTEGER NOT NULL,
                    confirmed_minor INTEGER NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tcc_outbox_journal (
                    operation_id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    amount_minor INTEGER NOT NULL,
                    compensatable INTEGER NOT NULL,
                    tcc_state TEXT NOT NULL,
                    dispatch_ts INTEGER NOT NULL,
                    visibility_bound_sec INTEGER NOT NULL,
                    action_caid TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS occ_entity_state (
                    entity_id TEXT PRIMARY KEY,
                    version INTEGER NOT NULL,
                    policy_epoch INTEGER NOT NULL,
                    context_manifest_hash TEXT NOT NULL,
                    state_payload_jcs TEXT NOT NULL,
                    updated_at INTEGER NOT NULL
                );
                """
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO workflow_budget VALUES (?, ?, 0, 0);
                """,
                (self.workflow_id, budget_minor),
            )
            conn.execute("COMMIT;")
        except Exception:
            conn.execute("ROLLBACK;")
            raise
        finally:
            conn.close()

    def tcc_try_reserve_all_or_nothing(
        self,
        branch_ops: List[Tuple[str, int, bool]],
        now_ts: int,
        visibility_bound_sec: int = 5,
        action_payloads: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, str]:
        """
        Pre-Socket TCC `Try` Phase:
        Atomically reserves budget across all parallel subagent branches in a single ACID
        transaction BEFORE any irreversible external HTTP call is permitted.
        """
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            row = conn.execute(
                "SELECT budget_minor, reserved_minor, confirmed_minor FROM workflow_budget WHERE workflow_id = ?;",
                (self.workflow_id,),
            ).fetchone()
            if row is None:
                conn.execute("ROLLBACK;")
                return False, "HALT_WORKFLOW_NOT_FOUND"

            budget, reserved, confirmed = int(row[0]), int(row[1]), int(row[2])
            requested_total = sum(op[1] for op in branch_ops)

            if (reserved + confirmed + requested_total) > budget:
                conn.execute("ROLLBACK;")
                return False, "HALT_TCC_PRE_COMMIT_BUDGET_INVARIANT_VIOLATION"

            for op_id, amt, comp in branch_ops:
                caid = "sha256:unspecified"
                if action_payloads and op_id in action_payloads:
                    caid = sha256_prefixed(encode_jcs(action_payloads[op_id]))

                conn.execute(
                    """
                    INSERT INTO tcc_outbox_journal VALUES (?, ?, ?, ?, 'TRY_RESERVED', ?, ?, ?);
                    """,
                    (
                        op_id,
                        self.workflow_id,
                        amt,
                        1 if comp else 0,
                        now_ts,
                        visibility_bound_sec,
                        caid,
                    ),
                )

            conn.execute(
                """
                UPDATE workflow_budget SET reserved_minor = reserved_minor + ? WHERE workflow_id = ?;
                """,
                (requested_total, self.workflow_id),
            )
            conn.execute("COMMIT;")
            return True, "TRY_RESERVED_OK"
        except Exception:
            conn.execute("ROLLBACK;")
            raise
        finally:
            conn.close()

    def latch_indeterminate_on_timeout(self, operation_id: str) -> None:
        """
        Latches an ambiguous transport result (HTTP 504 / TCP RST) into `EFFECT_INDETERMINATE`.
        Spend reservation remains locked in escrow.
        """
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            conn.execute(
                """
                UPDATE tcc_outbox_journal SET tcc_state = 'EFFECT_INDETERMINATE' WHERE operation_id = ?;
                """,
                (operation_id,),
            )
            conn.execute("COMMIT;")
        except Exception:
            conn.execute("ROLLBACK;")
            raise
        finally:
            conn.close()

    def attempt_reconcile_or_retry(
        self,
        operation_id: str,
        now_ts: int,
        authoritative_primary_committed: bool,
    ) -> Tuple[str, str]:
        """
        Defeats Proposition 1 (arXiv:2609.29095):
        1. Blocks any read-back decision while `now_ts < dispatch_ts + visibility_bound_sec` (delta + lambda).
        2. After the visibility bound elapses, reconciles ONLY against the authoritative primary.
        """
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            row = conn.execute(
                """
                SELECT amount_minor, tcc_state, dispatch_ts, visibility_bound_sec
                FROM tcc_outbox_journal WHERE operation_id = ?;
                """,
                (operation_id,),
            ).fetchone()
            if row is None:
                conn.execute("ROLLBACK;")
                return "NOT_FOUND", "HALT_OPERATION_NOT_FOUND"

            amt, state, disp_ts, vis_bound = int(row[0]), str(row[1]), int(row[2]), int(row[3])

            if now_ts < (disp_ts + vis_bound):
                conn.execute("COMMIT;")
                return state, "BLOCKED_VISIBILITY_LAG_FENCE_ACTIVE"

            if authoritative_primary_committed:
                conn.execute(
                    """
                    UPDATE tcc_outbox_journal SET tcc_state = 'CONFIRMED' WHERE operation_id = ?;
                    """,
                    (operation_id,),
                )
                conn.execute(
                    """
                    UPDATE workflow_budget
                    SET reserved_minor = reserved_minor - ?, confirmed_minor = confirmed_minor + ?
                    WHERE workflow_id = ?;
                    """,
                    (amt, amt, self.workflow_id),
                )
                conn.execute("COMMIT;")
                return "CONFIRMED", "RECONCILED_ALREADY_COMMITTED_NO_RETRY"
            else:
                conn.execute(
                    """
                    UPDATE tcc_outbox_journal SET tcc_state = 'CANCELLED_REFUTED' WHERE operation_id = ?;
                    """,
                    (operation_id,),
                )
                conn.execute(
                    """
                    UPDATE workflow_budget SET reserved_minor = reserved_minor - ? WHERE workflow_id = ?;
                    """,
                    (amt, self.workflow_id),
                )
                conn.execute("COMMIT;")
                return "CANCELLED_REFUTED", "SAFE_TO_ISSUE_NEW_ATTEMPT"
        except Exception:
            conn.execute("ROLLBACK;")
            raise
        finally:
            conn.close()

    def get_budget_state(self) -> Dict[str, int]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT budget_minor, reserved_minor, confirmed_minor FROM workflow_budget WHERE workflow_id = ?;",
                (self.workflow_id,),
            ).fetchone()
            if row is None:
                return {"budget_minor": 0, "reserved_minor": 0, "confirmed_minor": 0}
            return {
                "budget_minor": int(row[0]),
                "reserved_minor": int(row[1]),
                "confirmed_minor": int(row[2]),
            }
        finally:
            conn.close()

    def occ_register_entity(
        self,
        entity_id: str,
        initial_payload: Dict[str, Any],
        policy_epoch: int,
        context_manifest_hash: str,
        now_ts: int,
    ) -> bool:
        """
        Registers an entity for Optimistic Concurrency Control (OCC) tracking
        with an initial version index of 1.
        """
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            conn.execute(
                """
                INSERT OR REPLACE INTO occ_entity_state
                VALUES (?, 1, ?, ?, ?, ?);
                """,
                (
                    entity_id,
                    policy_epoch,
                    context_manifest_hash,
                    encode_jcs(initial_payload).decode("utf-8"),
                    now_ts,
                ),
            )
            conn.execute("COMMIT;")
            return True
        except Exception:
            conn.execute("ROLLBACK;")
            raise
        finally:
            conn.close()

    def occ_cas_mutate(
        self,
        entity_id: str,
        expected_version: int,
        expected_policy_epoch: int,
        expected_context_manifest_hash: str,
        new_payload: Dict[str, Any],
        now_ts: int,
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Optimistic Concurrency Control (OCC) Compare-And-Swap (CAS) Mutation:
        Atomically evaluates version, policy_epoch, and context_manifest_hash before
        applying the state update.
        Defeats world state drift and context poisoning (AT31/AT50).
        """
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            row = conn.execute(
                """
                SELECT version, policy_epoch, context_manifest_hash
                FROM occ_entity_state WHERE entity_id = ?;
                """,
                (entity_id,),
            ).fetchone()

            if row is None:
                conn.execute("ROLLBACK;")
                return False, "HALT_OCC_ENTITY_NOT_FOUND", None

            curr_ver, curr_epoch, curr_manifest = int(row[0]), int(row[1]), str(row[2])

            if curr_ver != expected_version:
                conn.execute("ROLLBACK;")
                return False, "HALT_OCC_VERSION_CONFLICT", curr_ver

            if curr_epoch != expected_policy_epoch:
                conn.execute("ROLLBACK;")
                return False, "HALT_OCC_POLICY_EPOCH_STALE", curr_ver

            if curr_manifest != expected_context_manifest_hash:
                conn.execute("ROLLBACK;")
                return False, "HALT_OCC_CONTEXT_MANIFEST_DRIFT", curr_ver

            cursor = conn.execute(
                """
                UPDATE occ_entity_state
                SET version = version + 1,
                    policy_epoch = ?,
                    context_manifest_hash = ?,
                    state_payload_jcs = ?,
                    updated_at = ?
                WHERE entity_id = ? AND version = ? AND policy_epoch = ? AND context_manifest_hash = ?;
                """,
                (
                    expected_policy_epoch,
                    expected_context_manifest_hash,
                    encode_jcs(new_payload).decode("utf-8"),
                    now_ts,
                    entity_id,
                    expected_version,
                    expected_policy_epoch,
                    expected_context_manifest_hash,
                ),
            )

            if cursor.rowcount == 0:
                conn.execute("ROLLBACK;")
                return False, "HALT_OCC_CAS_RACE_LOST", curr_ver

            new_ver = expected_version + 1
            conn.execute("COMMIT;")
            return True, "OCC_MUTATION_COMMITTED", new_ver
        except Exception:
            conn.execute("ROLLBACK;")
            raise
        finally:
            conn.close()

    def occ_get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT version, policy_epoch, context_manifest_hash, state_payload_jcs, updated_at
                FROM occ_entity_state WHERE entity_id = ?;
                """,
                (entity_id,),
            ).fetchone()
            if row is None:
                return None
            raw_payload = row[3].decode("utf-8") if isinstance(row[3], bytes) else str(row[3])
            return {
                "entity_id": entity_id,
                "version": int(row[0]),
                "policy_epoch": int(row[1]),
                "context_manifest_hash": str(row[2]),
                "payload": json.loads(raw_payload),
                "updated_at": int(row[4]),
            }
        finally:
            conn.close()


class TaskScopeCancellation(Exception):
    """Raised when a subtask is canceled due to sibling failure under ShutdownOnFailure."""
    pass


class TaskScopeFailure(Exception):
    """Raised when a structured scope join observes a subtask failure."""
    pass


class AgentStructuredTaskScope:
    """
    StructuredTaskScope (JEP 480 model) for autonomous AI agent subtasks.
    Implements lexical scoping, ShutdownOnFailure, deadline enforcement,
    spec_caid DTO contract verification, and automatic TCC reservation rollback on sibling abort.
    """

    def __init__(
        self,
        scope_name: str,
        timeout_sec: float = 30.0,
        tcc_boundary: Optional[SqliteAcidTccBoundary] = None,
    ) -> None:
        self.scope_name = scope_name
        self.timeout_sec = timeout_sec
        self.tcc_boundary = tcc_boundary
        self._executor = concurrent.futures.ThreadPoolExecutor(thread_name_prefix=f"scope-{scope_name}")
        self._futures: Dict[str, concurrent.futures.Future] = {}
        self._specs: Dict[str, str] = {}
        self._reservations: List[str] = []
        self._failed = False
        self._failure_reason: Optional[str] = None
        self._closed = False
        self._lock = threading.Lock()
        self._cancel_event = threading.Event()

    def __enter__(self) -> "AgentStructuredTaskScope":
        return self

    def fork(
        self,
        task_id: str,
        spec_caid: str,
        callable_fn: Any,
        *args: Any,
        tcc_op_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        if self._closed:
            raise RuntimeError("Cannot fork into closed task scope")
        if self._failed:
            return

        with self._lock:
            self._specs[task_id] = spec_caid
            if tcc_op_id:
                self._reservations.append(tcc_op_id)

            def wrapped() -> Any:
                if self._cancel_event.is_set():
                    raise TaskScopeCancellation(f"Task {task_id} canceled due to sibling failure")
                res = callable_fn(*args, **kwargs)
                if self._cancel_event.is_set():
                    raise TaskScopeCancellation(f"Task {task_id} canceled due to sibling failure")
                res_caid = sha256_prefixed(encode_jcs(res))
                if res_caid != spec_caid:
                    raise ValueError(f"HALT_DTO_CONTRACT_VIOLATION: result CAID {res_caid} != expected {spec_caid}")
                return res

            future = self._executor.submit(wrapped)
            self._futures[task_id] = future

    def join_until(self, deadline_ts: Optional[float] = None) -> "AgentStructuredTaskScope":
        timeout = self.timeout_sec
        if deadline_ts is not None:
            timeout = max(0.01, deadline_ts - time.time())

        done, not_done = concurrent.futures.wait(
            self._futures.values(),
            timeout=timeout,
            return_when=concurrent.futures.FIRST_EXCEPTION,
        )

        for task_id, fut in self._futures.items():
            if fut in done:
                exc = fut.exception()
                if exc:
                    self._trigger_shutdown_on_failure(f"{type(exc).__name__}: {exc}")
                    break

        if not self._failed and not_done:
            done2, not_done2 = concurrent.futures.wait(
                not_done,
                timeout=0.01,
                return_when=concurrent.futures.FIRST_EXCEPTION,
            )
            if not_done2:
                self._trigger_shutdown_on_failure("HALT_TASK_SCOPE_DEADLINE_EXCEEDED")

        return self

    def _trigger_shutdown_on_failure(self, reason: str) -> None:
        with self._lock:
            if not self._failed:
                self._failed = True
                self._failure_reason = reason
                self._cancel_event.set()
                for fut in self._futures.values():
                    fut.cancel()

    def throwIfFailed(self) -> None:
        if self._failed:
            if self.tcc_boundary and self._reservations:
                self._rollback_tcc_reservations()
            raise TaskScopeFailure(self._failure_reason)

    def _rollback_tcc_reservations(self) -> None:
        if not self.tcc_boundary:
            return
        conn = self.tcc_boundary._connect()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            for op_id in self._reservations:
                row = conn.execute(
                    "SELECT amount_minor, tcc_state FROM tcc_outbox_journal WHERE operation_id = ?;",
                    (op_id,),
                ).fetchone()
                if row and row[1] == "TRY_RESERVED":
                    amt = int(row[0])
                    conn.execute(
                        "UPDATE tcc_outbox_journal SET tcc_state = 'CANCELLED_SCOPE_ABORT' WHERE operation_id = ?;",
                        (op_id,),
                    )
                    conn.execute(
                        "UPDATE workflow_budget SET reserved_minor = reserved_minor - ? WHERE workflow_id = ?;",
                        (amt, self.tcc_boundary.workflow_id),
                    )
            conn.execute("COMMIT;")
        except Exception:
            conn.execute("ROLLBACK;")
            raise
        finally:
            conn.close()

    def results(self) -> Dict[str, Any]:
        self.throwIfFailed()
        return {tid: fut.result() for tid, fut in self._futures.items()}

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_val is not None:
            self._trigger_shutdown_on_failure(f"ScopeContextExit: {exc_val}")
            if self.tcc_boundary and self._reservations:
                self._rollback_tcc_reservations()
        self._executor.shutdown(wait=False, cancel_futures=True)
        self._closed = True
