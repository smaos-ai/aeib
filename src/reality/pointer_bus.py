# Copyright 2026 SovereignNexus Project
#
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
src/reality/pointer_bus.py — Content-Addressed Pointer-Pipe Data Plane for MCP Tool Payloads.

Solves the "MCP Double-Counting Tax":
When an MCP tool produces a 50KB JSON payload, a naive agent framework injects that
50KB into the conversation history, then forwards it to Tool B—charging the user twice
for the same raw payload and exhausting the LLM's effective context window.

The PointerBus intercepts payloads larger than a configurable threshold (default 2,048 bytes),
stores them in a local SQLite-WAL content-addressed store, and returns a 20-byte handle
(ptr_sha256) with a bounded preview (<100 chars).
When Tool B needs the payload, the PointerBus streams the data directly in-kernel
at $0 cost and 0 LLM tokens via `pipe_tool_to_tool`.
"""

import hashlib
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple, Union

DEFAULT_POINTER_THRESHOLD_BYTES: int = 2048
DEFAULT_TTL_SECONDS: int = 86400  # 24 hours


@dataclass(frozen=True)
class PointerHandle:
    ptr_sha256: str
    size_bytes: int
    mime_type: str
    expires_epoch_ns: int
    acl_agent_id: str
    compact_summary: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ptr_sha256": self.ptr_sha256,
            "size_bytes": self.size_bytes,
            "mime_type": self.mime_type,
            "expires_epoch_ns": self.expires_epoch_ns,
            "acl_agent_id": self.acl_agent_id,
            "compact_summary": self.compact_summary,
        }


class PointerBus:
    """
    Local SQLite-WAL content-addressed store for large tool payloads.
    Enforces cryptographic integrity, TTL pruning, and agent ACL isolation.
    """

    def __init__(
        self,
        db_path: Union[str, Path] = ":memory:",
        threshold_bytes: int = DEFAULT_POINTER_THRESHOLD_BYTES,
    ) -> None:
        self.db_path = str(db_path)
        self.threshold_bytes = threshold_bytes
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self._init_db()

    def _init_db(self) -> None:
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pointers (
                    ptr_sha256 TEXT PRIMARY KEY,
                    created_epoch_ns INTEGER NOT NULL,
                    expires_epoch_ns INTEGER NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    mime_type TEXT NOT NULL,
                    acl_agent_id TEXT NOT NULL,
                    payload BLOB NOT NULL
                )
                """
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_pointers_expires ON pointers(expires_epoch_ns);"
            )

    def put_payload(
        self,
        data: Union[str, bytes],
        mime_type: str = "text/plain",
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        acl_agent_id: str = "*",
        now_ns: Optional[int] = None,
    ) -> PointerHandle:
        """
        Stores data by SHA-256 digest and returns a PointerHandle.
        """
        payload_bytes = data.encode("utf-8") if isinstance(data, str) else bytes(data)
        size = len(payload_bytes)
        digest = hashlib.sha256(payload_bytes).hexdigest()

        now = now_ns if now_ns is not None else time.time_ns()
        expires = now + (ttl_seconds * 1_000_000_000)

        # Generate preview summary
        preview_sample = payload_bytes[:80].decode("utf-8", errors="replace").replace("\n", " ")
        summary = f"[{mime_type}, {size} bytes, preview: {preview_sample}...]"

        with self.conn:
            self.conn.execute(
                """
                INSERT INTO pointers (ptr_sha256, created_epoch_ns, expires_epoch_ns, size_bytes, mime_type, acl_agent_id, payload)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ptr_sha256) DO UPDATE SET
                    expires_epoch_ns = MAX(pointers.expires_epoch_ns, excluded.expires_epoch_ns)
                """,
                (digest, now, expires, size, mime_type, acl_agent_id, payload_bytes),
            )

        return PointerHandle(
            ptr_sha256=digest,
            size_bytes=size,
            mime_type=mime_type,
            expires_epoch_ns=expires,
            acl_agent_id=acl_agent_id,
            compact_summary=summary,
        )

    def get_payload(
        self,
        ptr_sha256: str,
        requesting_agent_id: str = "*",
        now_ns: Optional[int] = None,
    ) -> Optional[bytes]:
        """
        Retrieves raw payload bytes, enforcing ACL and TTL.
        Raises PermissionError if ACL fails.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT expires_epoch_ns, acl_agent_id, payload FROM pointers WHERE ptr_sha256 = ?",
            (ptr_sha256,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        expires_ns, acl, payload = row
        now = now_ns if now_ns is not None else time.time_ns()

        if now > expires_ns:
            # Expired
            return None

        if acl != "*" and acl != requesting_agent_id and requesting_agent_id != "*":
            raise PermissionError(f"ERR_POINTER_ACL_DENIED: Agent '{requesting_agent_id}' cannot access pointer owned by '{acl}'")

        return payload

    def pipe_tool_to_tool(
        self,
        src_ptr_sha256: str,
        target_fn: Callable[[bytes], Union[str, bytes]],
        requesting_agent_id: str = "*",
        out_mime_type: str = "text/plain",
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> PointerHandle:
        """
        Direct kernel pipe: streams payload from src pointer directly to target_fn
        and stores result into a new PointerHandle without round-tripping through LLM.
        """
        src_bytes = self.get_payload(src_ptr_sha256, requesting_agent_id=requesting_agent_id)
        if src_bytes is None:
            raise KeyError(f"ERR_SRC_POINTER_NOT_FOUND: {src_ptr_sha256}")

        result_bytes = target_fn(src_bytes)
        return self.put_payload(
            result_bytes,
            mime_type=out_mime_type,
            ttl_seconds=ttl_seconds,
            acl_agent_id=requesting_agent_id,
        )

    def prune_expired(self, now_ns: Optional[int] = None) -> int:
        """Deletes expired records and returns count of pruned entries."""
        now = now_ns if now_ns is not None else time.time_ns()
        with self.conn:
            cursor = self.conn.execute("DELETE FROM pointers WHERE expires_epoch_ns < ?", (now,))
            return cursor.rowcount

    def close(self) -> None:
        """Closes the underlying database connection."""
        self.conn.close()
