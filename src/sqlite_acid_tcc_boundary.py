#!/usr/bin/env python3
"""
src/sqlite_acid_tcc_boundary.py — Enterprise Microservices TCC + ACID Outbox Boundary

Implements Enterprise Microservices TCC (Try-Confirm-Cancel) + ACID Outbox using
SQLite WAL and `BEGIN IMMEDIATE` serialized transactions to coordinate parallel AI subagents.

Directly addresses and defeats:
1. Parallel Budget Overrun Anomaly (Trofimov & Novikov, arXiv:2609.15397):
   Pre-socket atomic TCC `Try` reservation across all parallel subagent branches prevents
   over-allocation before any irreversible external HTTP mutation can execute.
2. Proposition 1 Late-Commit + NoSQL Read-Replica Lag (Jiapeng Li, arXiv:2609.29095):
   Transactional outbox with Visibility-Lag Fencing (`t_reconcile >= t_dispatch + delta_max + lambda_max`)
   prevents premature read-back retries on stale read replicas.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
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
