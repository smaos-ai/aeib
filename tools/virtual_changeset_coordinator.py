#!/usr/bin/env python3
"""
tools/virtual_changeset_coordinator.py
================================================================================
Server-Centric Virtual Changeset Coordinator (Scion-Lite Mode for Move 1).

Inspired by Anthropic Scion (server-side WAL changesets replacing heavy local Git checkouts).

Evaluates under the stated model:
  1. Manages Path-Scoped Leases (lease_paths: [...]) in an in-memory/SQLite WAL
     to enforce Disjoint Write Sets:
        A_i ∩ A_j = ∅
     failing closed with HALT_OVERLAPPING_WRITE_SET_COLLISION on contention.
  2. Eliminates full 25GB repository disk clones across 20+ concurrent workers.
  3. Enforces temporal activity leases (heartbeat TTL) to automatically release hung workers.
  4. Records immutable changeset commits with RFC 8785 JCS digests and Ed25519 signatures.
"""

from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs


def sha256_prefixed(data: bytes) -> str:
    """Computes a SHA-256 digest with standard prefix."""
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


class VirtualChangesetCoordinator:
    """
    Coordinates disjoint write leases and server-side virtual changesets across subagents.
    """

    def __init__(
        self,
        coordinator_privkey: ed25519.Ed25519PrivateKey,
        db_path: Optional[Path] = None,
        default_ttl_sec: float = 90.0,
    ) -> None:
        self._privkey = coordinator_privkey
        self.default_ttl_sec = default_ttl_sec
        self._lock = threading.Lock()
        self.db_path = db_path or Path("/tmp/virtual_changeset_wal.sqlite")
        self._init_db()

    @property
    def public_key(self) -> ed25519.Ed25519PublicKey:
        return self._privkey.public_key()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE;")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS path_leases (
                        path TEXT PRIMARY KEY,
                        subagent_id TEXT NOT NULL,
                        expires_at REAL NOT NULL
                    );
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS virtual_changesets (
                        changeset_id TEXT PRIMARY KEY,
                        subagent_id TEXT NOT NULL,
                        target_paths TEXT NOT NULL,
                        patch_caid TEXT NOT NULL,
                        signature_b64 TEXT NOT NULL,
                        committed_at REAL NOT NULL
                    );
                    """
                )
                conn.execute("COMMIT;")
            finally:
                conn.close()

    def acquire_path_lease(
        self,
        subagent_id: str,
        paths: List[str],
        ttl_sec: Optional[float] = None,
        now_ts: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Attempts to acquire an exclusive path lease. Enforces A_i ∩ A_j = ∅.
        """
        if now_ts is None:
            now_ts = time.time()
        if ttl_sec is None:
            ttl_sec = self.default_ttl_sec

        expires_at = now_ts + ttl_sec

        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE;")
                # Clean up expired leases
                conn.execute("DELETE FROM path_leases WHERE expires_at < ?", (now_ts,))

                # Check for overlapping paths held by other subagents
                conflicts = []
                for p in paths:
                    row = conn.execute(
                        "SELECT subagent_id, expires_at FROM path_leases WHERE path = ?", (p,)
                    ).fetchone()
                    if row and row[0] != subagent_id:
                        conflicts.append({"path": p, "held_by": row[0], "expires_at": row[1]})

                if conflicts:
                    conn.execute("ROLLBACK;")
                    return {
                        "granted": False,
                        "status": "HALT_OVERLAPPING_WRITE_SET_COLLISION",
                        "conflicting_paths": conflicts,
                    }

                # Register/renew leases
                for p in paths:
                    conn.execute(
                        """
                        INSERT INTO path_leases (path, subagent_id, expires_at)
                        VALUES (?, ?, ?)
                        ON CONFLICT(path) DO UPDATE SET
                            subagent_id = excluded.subagent_id,
                            expires_at = excluded.expires_at;
                        """,
                        (p, subagent_id, expires_at),
                    )

                conn.execute("COMMIT;")
                return {
                    "granted": True,
                    "status": "LEASE_GRANTED",
                    "subagent_id": subagent_id,
                    "leased_paths": paths,
                    "expires_at": expires_at,
                }
            except Exception as exc:
                conn.execute("ROLLBACK;")
                return {"granted": False, "status": "HALT_DATABASE_EXCEPTION", "error": str(exc)}
            finally:
                conn.close()

    def release_path_lease(self, subagent_id: str, paths: Optional[List[str]] = None) -> Dict[str, Any]:
        """Releases path leases held by a subagent."""
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE;")
                if paths:
                    for p in paths:
                        conn.execute("DELETE FROM path_leases WHERE path = ? AND subagent_id = ?", (p, subagent_id))
                else:
                    conn.execute("DELETE FROM path_leases WHERE subagent_id = ?", (subagent_id,))
                conn.execute("COMMIT;")
                return {"status": "LEASES_RELEASED", "subagent_id": subagent_id}
            finally:
                conn.close()

    def commit_virtual_changeset(
        self,
        subagent_id: str,
        changeset_id: str,
        patch_payload: Dict[str, Any],
        now_ts: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Commits a virtual changeset, verifying active path lease ownership.
        """
        if now_ts is None:
            now_ts = time.time()

        target_paths = patch_payload.get("target_paths", [])
        patch_caid = sha256_prefixed(encode_jcs(patch_payload))

        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE;")
                # Clean up expired
                conn.execute("DELETE FROM path_leases WHERE expires_at < ?", (now_ts,))

                # Verify all target paths are leased by this subagent
                for p in target_paths:
                    row = conn.execute(
                        "SELECT subagent_id FROM path_leases WHERE path = ?", (p,)
                    ).fetchone()
                    if not row or row[0] != subagent_id:
                        conn.execute("ROLLBACK;")
                        return {
                            "committed": False,
                            "status": "HALT_UNLEASED_PATH_MODIFICATION",
                            "unleased_path": p,
                        }

                # Sign changeset receipt
                receipt_payload = {
                    "changeset_id": changeset_id,
                    "subagent_id": subagent_id,
                    "patch_caid": patch_caid,
                    "target_paths": target_paths,
                    "timestamp": now_ts,
                }
                sig_bytes = self._privkey.sign(encode_jcs(receipt_payload))
                sig_b64 = base64.b64encode(sig_bytes).decode("ascii")

                conn.execute(
                    """
                    INSERT INTO virtual_changesets (changeset_id, subagent_id, target_paths, patch_caid, signature_b64, committed_at)
                    VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    (changeset_id, subagent_id, json.dumps(target_paths), patch_caid, sig_b64, now_ts),
                )

                conn.execute("COMMIT;")
                return {
                    "committed": True,
                    "status": "CHANGESET_COMMITTED",
                    "changeset_id": changeset_id,
                    "patch_caid": patch_caid,
                    "signature_b64": sig_b64,
                }
            except Exception as exc:
                conn.execute("ROLLBACK;")
                return {"committed": False, "status": "HALT_DATABASE_EXCEPTION", "error": str(exc)}
            finally:
                conn.close()
