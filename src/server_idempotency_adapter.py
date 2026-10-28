#!/usr/bin/env python3
r"""
server_idempotency_adapter.py — Downstream Server-Side Idempotency Enforcement Engine
Sovereign Multi-Agent OS (SMAOS) / Agent Execution Integrity (AEIB)

Implements the downstream server-side contract required for deterministic UUIDv5
idempotency keys, preventing double-execution and suppressing concurrent race conditions.

Key Contract Invariants:
  1. Atomic In-Progress Lock: Concurrent duplicate dispatches block or return 409 Conflict.
  2. Idempotent Replay: Retrying an identical key with an identical payload returns the
     cached outcome without re-executing business logic.
  3. Tamper Rejection: Replaying an identical key with an altered payload hash is strictly
     rejected with 422 Unprocessable Entity (IDEMPOTENCY_PAYLOAD_MISMATCH).
  4. Authoritative State Probe Interface: Downstream registers can be queried out-of-band
     by the SMAOS StateProber to verify physical execution state after a transport drop.
"""

import os
import sys
import json
import time
import sqlite3
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass, asdict
from pathlib import Path


def compute_payload_hash(payload: Any) -> str:
    """Computes deterministic SHA-256 digest of request payload via RFC 8785 JCS."""
    try:
        from src.jcs_canonicalizer import encode_jcs
    except ImportError:
        from jcs_canonicalizer import encode_jcs
    serialized = encode_jcs(payload)
    return f"sha256:{hashlib.sha256(serialized).hexdigest()}"


@dataclass
class IdempotencyRecord:
    idempotency_key: str
    action_id: str
    payload_hash: str
    status: str  # "IN_PROGRESS", "COMMITTED", "REJECTED"
    created_at_utc: str
    updated_at_utc: str
    response_code: Optional[int] = None
    response_body_json: Optional[str] = None
    execution_duration_ms: Optional[float] = None


class ServerIdempotencyAdapter:
    """
    Downstream middleware enforcing the server-side idempotency contract.
    Backed by persistent or in-memory SQLite storage.
    """

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS server_idempotency_ledger (
                idempotency_key TEXT PRIMARY KEY,
                action_id TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at_utc TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL,
                response_code INTEGER,
                response_body_json TEXT,
                execution_duration_ms REAL
            )
        """)
        self.conn.commit()

    def execute_idempotent(
        self,
        idempotency_key: str,
        action_id: str,
        payload: Dict[str, Any],
        business_handler: Callable[..., Tuple[int, Dict[str, Any]]]
    ) -> Tuple[int, Dict[str, Any], bool]:
        """
        Executes business handler under the server idempotency contract.
        Returns: (http_status_code, response_dict, is_cached_replay)
        """
        payload_hash = compute_payload_hash(payload)
        now_iso = datetime.now(timezone.utc).isoformat()

        # Step 1: Check existing record
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT idempotency_key, action_id, payload_hash, status, response_code, response_body_json FROM server_idempotency_ledger WHERE idempotency_key = ?",
            (idempotency_key,)
        )
        row = cursor.fetchone()

        if row is not None:
            _, rec_action_id, rec_payload_hash, rec_status, rec_code, rec_body_json = row

            # Invariant 3: Payload drift detection
            if rec_payload_hash != payload_hash:
                err_resp = {
                    "error": "IDEMPOTENCY_PAYLOAD_MISMATCH",
                    "status_code": 422,
                    "message": "Request payload diverged from previously registered payload for this idempotency key.",
                    "registered_payload_hash": rec_payload_hash,
                    "attempted_payload_hash": payload_hash,
                    "action_id": action_id
                }
                return 422, err_resp, False

            # Invariant 1: In-flight race condition / concurrency lock
            if rec_status == "IN_PROGRESS":
                err_resp = {
                    "error": "CONCURRENT_REQUEST_IN_FLIGHT",
                    "status_code": 409,
                    "message": "A request with this idempotency key is already currently being processed.",
                    "action_id": action_id,
                    "retry_after_ms": 1000  # claim: config
                }
                return 409, err_resp, False

            # Invariant 2: Idempotent replay of previously committed result
            if rec_status == "COMMITTED" and rec_body_json:
                cached_data = json.loads(rec_body_json)
                return rec_code or 200, cached_data, True

        # Step 2: Atomic acquire lock (IN_PROGRESS)
        try:
            self.conn.execute(
                "INSERT INTO server_idempotency_ledger (idempotency_key, action_id, payload_hash, status, created_at_utc, updated_at_utc) VALUES (?, ?, ?, ?, ?, ?)",
                (idempotency_key, action_id, payload_hash, "IN_PROGRESS", now_iso, now_iso)
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            # Race condition: another thread inserted between select and insert
            err_resp = {
                "error": "CONCURRENT_REQUEST_IN_FLIGHT",
                "status_code": 409,
                "message": "Lock collision: simultaneous execution detected for idempotency key.",
                "action_id": action_id
            }
            return 409, err_resp, False

        # Step 3: Execute actual business handler
        t0 = time.perf_counter()
        try:
            status_code, handler_result = business_handler(payload)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            # Step 4: Finalize commit
            final_status = "COMMITTED" if status_code < 400 else "REJECTED"
            update_iso = datetime.now(timezone.utc).isoformat()
            self.conn.execute(
                "UPDATE server_idempotency_ledger SET status = ?, response_code = ?, response_body_json = ?, updated_at_utc = ?, execution_duration_ms = ? WHERE idempotency_key = ?",
                (final_status, status_code, json.dumps(handler_result), update_iso, elapsed_ms, idempotency_key)
            )
            self.conn.commit()
            return status_code, handler_result, False

        except Exception as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            update_iso = datetime.now(timezone.utc).isoformat()
            err_payload = {"error": "HANDLER_EXECUTION_EXCEPTION", "exception": str(e)}
            self.conn.execute(
                "UPDATE server_idempotency_ledger SET status = ?, response_code = ?, response_body_json = ?, updated_at_utc = ?, execution_duration_ms = ? WHERE idempotency_key = ?",
                ("REJECTED", 500, json.dumps(err_payload), update_iso, elapsed_ms, idempotency_key)
            )
            self.conn.commit()
            raise e

    def probe_state(self, idempotency_key: str, expected_payload_hash: str) -> Dict[str, Any]:
        """
        Out-of-band state probe interface queried by SMAOS StateProber.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT idempotency_key, action_id, payload_hash, status, response_code, response_body_json, updated_at_utc FROM server_idempotency_ledger WHERE idempotency_key = ?",
            (idempotency_key,)
        )
        row = cursor.fetchone()

        if not row:
            return {
                "disposition": "RECONCILIATION_NOT_FOUND",
                "outcome_verified": False,
                "downstream_state_hash": None,
                "record": None
            }

        rec = {
            "idempotency_key": row[0],
            "action_id": row[1],
            "payload_hash": row[2],
            "status": row[3],
            "response_code": row[4],
            "response_body": row[5],
            "updated_at_utc": row[6]
        }
        state_hash = compute_payload_hash(rec)

        if rec["payload_hash"] != expected_payload_hash:
            return {
                "disposition": "RECONCILIATION_FAILED",
                "outcome_verified": False,
                "downstream_state_hash": state_hash,
                "reason": "Payload hash mismatch against server register (tampering/drift)",
                "record": rec
            }

        if rec["status"] == "COMMITTED" and (rec["response_code"] or 0) < 400:
            return {
                "disposition": "OUTCOME_VERIFIED",
                "outcome_verified": True,
                "downstream_state_hash": state_hash,
                "record": rec
            }
        else:
            return {
                "disposition": "RECONCILIATION_FAILED",
                "outcome_verified": False,
                "downstream_state_hash": state_hash,
                "record": rec
            }


if __name__ == "__main__":
    adapter = ServerIdempotencyAdapter()
    idem_key = "test-uuidv5-contract-01"
    action = "mcp://test/1/1/demo.action"
    sample_payload = {"account": "CZ-991", "amount": 1000}

    def dummy_handler(p):
        return 200, {"tx_id": "TX-1001", "settled": True}

    # First execution
    code1, res1, cached1 = adapter.execute_idempotent(idem_key, action, sample_payload, dummy_handler)
    print(f"Call 1: Code={code1}, Cached={cached1}, Result={res1}")

    # Second execution (Replay with same payload)
    code2, res2, cached2 = adapter.execute_idempotent(idem_key, action, sample_payload, dummy_handler)
    print(f"Call 2: Code={code2}, Cached={cached2}, Result={res2}")

    # Third execution (Altered payload tampering)
    tampered_payload = {"account": "CZ-991", "amount": 999999}
    code3, res3, cached3 = adapter.execute_idempotent(idem_key, action, tampered_payload, dummy_handler)
    print(f"Call 3 (Tampered): Code={code3}, Result={res3['error']}")
