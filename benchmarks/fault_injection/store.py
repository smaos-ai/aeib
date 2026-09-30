#!/usr/bin/env python3
r"""
store.py — SQLite Atomic Store & Bitemporal Debit Ledger
Sovereign Multi-Agent OS (SMAOS) / Deterministic Fault-Injection Testbed

Provides strict ACID transactions, WAL mode, balance consistency,
and immutable commit logging for measuring the Safety Invariant:
  Safety: LedgerCommits(O) <= 1
"""

import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional


class AtomicDebitStore:
    """
    Thread-safe SQLite atomic ledger with WAL mode and shared memory caching.
    Maintains balance integrity and tracks logical operation commit counts.
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            env_db = os.environ.get("AEIB_LEDGER_DB")
            if env_db:
                self.db_path = env_db
                self._is_uri = env_db.startswith("file:")
            else:
                self.db_path = "file:aeib_ledger?mode=memory&cache=shared"
                self._is_uri = True
        else:
            self.db_path = db_path
            self._is_uri = db_path.startswith("file:")

        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, uri=self._is_uri, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

        if not self._is_uri and not self.db_path.startswith(":"):
            self._conn.execute("PRAGMA journal_mode = WAL;")
        self._conn.execute("PRAGMA synchronous = NORMAL;")
        self._conn.execute("PRAGMA busy_timeout = 5000;")

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        return self._conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._get_connection()
            conn.executescript(r"""
                CREATE TABLE IF NOT EXISTS accounts (
                    account_id TEXT PRIMARY KEY,
                    balance REAL NOT NULL,
                    updated_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS operations (
                    intent_id TEXT PRIMARY KEY,
                    logical_operation_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    amount REAL NOT NULL,
                    status TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS debit_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    logical_operation_id TEXT NOT NULL,
                    intent_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    amount REAL NOT NULL,
                    balance_after REAL NOT NULL,
                    committed_at_utc TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_ledger_op ON debit_ledger(logical_operation_id);
                CREATE INDEX IF NOT EXISTS idx_ledger_intent ON debit_ledger(intent_id);
            """)
            conn.commit()

            # Initialize default test account if empty
            cur = conn.execute("SELECT COUNT(*) as cnt FROM accounts WHERE account_id = 'acc_primary'")
            if cur.fetchone()["cnt"] == 0:
                now = datetime.now(timezone.utc).isoformat()
                conn.execute(
                    "INSERT INTO accounts (account_id, balance, updated_at_utc) VALUES (?, ?, ?)",
                    ("acc_primary", 10000.0, now)
                )
                conn.commit()

    def reset(self, initial_balance: float = 10000.0) -> None:
        """Flushes ledger and resets accounts for deterministic test isolation."""
        with self._lock:
            conn = self._get_connection()
            now = datetime.now(timezone.utc).isoformat()
            conn.executescript(r"""
                DELETE FROM debit_ledger;
                DELETE FROM operations;
                DELETE FROM accounts;
            """)
            conn.execute(
                "INSERT INTO accounts (account_id, balance, updated_at_utc) VALUES (?, ?, ?)",
                ("acc_primary", initial_balance, now)
            )
            conn.commit()

    def commit_debit(
        self,
        logical_operation_id: str,
        intent_id: str,
        account_id: str,
        amount: float,
    ) -> Dict[str, Any]:
        """
        Executes an atomic debit transaction against the target account.
        Appends an entry to the immutable debit ledger.
        """
        if amount <= 0:
            raise ValueError(f"Debit amount must be positive, got {amount}")

        with self._lock:
            conn = self._get_connection()
            now = datetime.now(timezone.utc).isoformat()

            # 1. Fetch current account balance with row lock
            cur = conn.execute(
                "SELECT balance FROM accounts WHERE account_id = ?",
                (account_id,)
            )
            row = cur.fetchone()
            if not row:
                raise KeyError(f"Account {account_id} not found")

            current_balance = row["balance"]
            if current_balance < amount:
                raise ValueError(f"Insufficient funds: balance {current_balance} < amount {amount}")

            new_balance = current_balance - amount

            # 2. Update account balance
            conn.execute(
                "UPDATE accounts SET balance = ?, updated_at_utc = ? WHERE account_id = ?",
                (new_balance, now, account_id)
            )

            # 3. Log operation attempt
            conn.execute(
                """
                INSERT OR REPLACE INTO operations (intent_id, logical_operation_id, account_id, amount, status, created_at_utc)
                VALUES (?, ?, ?, ?, 'COMMITTED', ?)
                """,
                (intent_id, logical_operation_id, account_id, amount, now)
            )

            # 4. Append to debit ledger
            cur = conn.execute(
                """
                INSERT INTO debit_ledger (logical_operation_id, intent_id, account_id, amount, balance_after, committed_at_utc)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (logical_operation_id, intent_id, account_id, amount, new_balance, now)
            )
            ledger_id = cur.lastrowid

            # 5. Count commits for this logical operation
            cur = conn.execute(
                "SELECT COUNT(*) as cnt FROM debit_ledger WHERE logical_operation_id = ?",
                (logical_operation_id,)
            )
            commit_count = cur.fetchone()["cnt"]

            conn.commit()

            return {
                "ledger_id": ledger_id,
                "logical_operation_id": logical_operation_id,
                "intent_id": intent_id,
                "account_id": account_id,
                "amount": amount,
                "balance_after": new_balance,
                "committed_at_utc": now,
                "commit_count_for_operation": commit_count,
            }

    def get_operation_status(self, identifier: str) -> Dict[str, Any]:
        """
        Authoritative out-of-band reconciliation query.
        Matches by logical_operation_id or intent_id.
        """
        with self._lock:
            conn = self._get_connection()
            # Query ledger commits
            cur = conn.execute(
                """
                SELECT id, logical_operation_id, intent_id, account_id, amount, balance_after, committed_at_utc
                FROM debit_ledger
                WHERE logical_operation_id = ? OR intent_id = ?
                ORDER BY id ASC
                """,
                (identifier, identifier)
            )
            rows = [dict(r) for r in cur.fetchall()]

            # Fetch account balance
            cur_acc = conn.execute("SELECT balance FROM accounts WHERE account_id = 'acc_primary'")
            acc_row = cur_acc.fetchone()
            current_balance = acc_row["balance"] if acc_row else 0.0

            commit_count = len(rows)
            is_committed = commit_count > 0
            is_duplicate = commit_count > 1

            return {
                "identifier": identifier,
                "committed": is_committed,
                "commit_count": commit_count,
                "is_duplicate_violation": is_duplicate,
                "current_balance": current_balance,
                "commits": rows,
            }

    def get_total_ledger_commits(self, logical_operation_id: str) -> int:
        """Returns total side-effect commit count for the given logical operation."""
        with self._lock:
            conn = self._get_connection()
            cur = conn.execute(
                "SELECT COUNT(*) as cnt FROM debit_ledger WHERE logical_operation_id = ?",
                (logical_operation_id,)
            )
            return cur.fetchone()["cnt"]
