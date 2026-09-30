#!/usr/bin/env python3
r"""
sqlite_probe_adapter.py — Real SQLite Out-of-Band (OOB) Outcome Probe Adapter
Sovereign Multi-Agent OS (SMAOS) / Agent Execution Integrity (AEIB)

Replaces synthetic probe mocks with direct queries to a local SQLite database
to establish true physical execution state after an ambiguous transport dropout (HTTP 504).
"""

import sqlite3
from datetime import datetime, timezone
from typing import Optional, Dict, Any


class SQLiteOutcomeProbeAdapter:
    """
    Authoritative out-of-band probe adapter querying downstream SQLite transactions.
    """

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._ensure_schema()

    def _get_connection(self) -> sqlite3.Connection:
        return self._conn

    def close(self) -> None:
        """Closes the underlying SQLite connection."""
        if self._conn:
            self._conn.close()

    def _ensure_schema(self) -> None:
        """Initializes the authoritative downstream transactions table."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS transactions (
                    idempotency_key TEXT PRIMARY KEY,
                    action_id TEXT,
                    payload_hash TEXT,
                    status TEXT,
                    response_code INTEGER,
                    created_at_utc TEXT
                )
                """
            )
            conn.commit()

    def record_transaction(
        self,
        idempotency_key: str,
        action_id: str,
        payload_hash: str,
        status: str = "COMMITTED",
        response_code: int = 200
    ) -> None:
        """Records a committed or attempted transaction downstream."""
        now_utc = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO transactions 
                (idempotency_key, action_id, payload_hash, status, response_code, created_at_utc)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (idempotency_key, action_id, payload_hash, status, response_code, now_utc)
            )
            conn.commit()

    def probe(self, idempotency_key: str, expected_payload_hash: Optional[str] = None) -> str:
        """
        Queries the downstream ledger to verify if the transaction committed.
        Returns:
            - OUTCOME_VERIFIED: Record exists (and hash matches if checked)
            - RECONCILIATION_NOT_FOUND: Record is absent
            - RECONCILIATION_FAILED: Record exists with payload hash mismatch (tampering/collision)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT status, payload_hash, response_code 
                FROM transactions 
                WHERE idempotency_key = ?
                """,
                (idempotency_key,)
            )
            row = cursor.fetchone()

        if not row:
            # Transaction dropped before persistence
            return "RECONCILIATION_NOT_FOUND"

        status, stored_hash, response_code = row

        if expected_payload_hash is not None and stored_hash != expected_payload_hash:
            # Tampering or idempotency hash collision detected
            return "RECONCILIATION_FAILED"

        if status == "COMMITTED" and (response_code is None or response_code < 400):
            # Transaction exists and was committed downstream
            return "OUTCOME_VERIFIED"
        else:
            return "RECONCILIATION_FAILED"

    def probe_detailed(self, idempotency_key: str, expected_payload_hash: Optional[str] = None) -> Dict[str, Any]:
        """Detailed probe query returning full ledger record metadata."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT idempotency_key, action_id, payload_hash, status, response_code, created_at_utc 
                FROM transactions 
                WHERE idempotency_key = ?
                """,
                (idempotency_key,)
            )
            row = cursor.fetchone()

        if not row:
            return {
                "disposition": "RECONCILIATION_NOT_FOUND",
                "outcome_verified": False,
                "record": None
            }

        rec = {
            "idempotency_key": row[0],
            "action_id": row[1],
            "payload_hash": row[2],
            "status": row[3],
            "response_code": row[4],
            "created_at_utc": row[5]
        }

        disposition = self.probe(idempotency_key, expected_payload_hash)
        return {
            "disposition": disposition,
            "outcome_verified": (disposition == "OUTCOME_VERIFIED"),
            "record": rec
        }
