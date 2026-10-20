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
adapters/mcp/idempotent_mcp_proxy.py — Hardened Idempotent MCP Proxy Middleware.

Lifts Station 1 (schema + Content-Addressed Action Identifier) and Station 2
(SQLite Write-Ahead Log + uncertainty latch) directly into the Model Context Protocol (MCP)
JSON-RPC transport and tool call lifecycle.

Core Functions:
1. Intercepts JSON-RPC `tools/call` and `tools/status` requests.
2. Computes Content-Addressed Action Identifiers (CAID) via RFC 8785 JCS canonicalization.
3. Disambiguates request-intent digest (CAID) from operation identity (composite key).
4. Enforces write-before-execute intent logging into a durable SQLite WAL with `BEGIN IMMEDIATE`.
5. Serializes concurrent requests on identical keys/CAID to defeat thundering herd races.
6. Latches ambiguous network transport drops, 5xx, and ambiguous 408/429 errors into `EFFECT_INDETERMINATE`.
7. Inspects MCP tool-level `isError: true` in 200 responses and routes to uncertainty latch.
8. Enforces separate retention TTL and uncertainty resolution deadlines (never purges unresolved uncertainty).
9. Halts blind retries under uncertainty and drives authoritative `tools/status` reconciliation.
10. Preserves latched uncertainty across policy epoch rotations.
"""

from __future__ import annotations

import concurrent.futures
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.jcs_canonicalizer import encode_jcs


def canonical_json_v1(obj: Any) -> bytes:
    """Canonicalizes JSON objects according to RFC 8785 (UTF-8, sorted keys, strict formatting)."""
    return encode_jcs(obj)


@dataclass
class McpProxyStateRecord:
    idempotency_key: str
    caid: str
    tool_name: str
    state: str  # CONFIRMED, EFFECT_INDETERMINATE, REFUTED, UNRESOLVED_ESCALATED, NOT_FOUND
    tenant_id: str = "default_tenant"
    principal: str = "default_principal"
    operation_id: Optional[str] = None
    cached_response: Optional[Dict[str, Any]] = None
    policy_epoch: str = "epoch-2026-Q4"
    created_at: float = field(default_factory=time.time)
    uncertainty_resolution_deadline: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class HardenedIdempotentMcpProxy:
    """
    Sits between the agent client and the upstream MCP server.
    Owns the idempotency SQLite WAL and enforces uncertainty state-machine rules.
    """

    def __init__(
        self,
        upstream_transport_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
        db_path: str | Path = ":memory:",
        ttl_sec: int = 86400,
        uncertainty_deadline_sec: int = 300,
        active_policy_epoch: str = "epoch-2026-Q4",
    ) -> None:
        self.upstream = upstream_transport_fn
        self.db_path = str(db_path)
        self.ttl_sec = ttl_sec
        self.uncertainty_deadline_sec = uncertainty_deadline_sec
        self.active_policy_epoch = active_policy_epoch
        self.lock = threading.Lock()

        # If disk path provided, ensure parent directory exists
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        # Initialize SQLite database with WAL mode and immediate locking
        self.conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            isolation_level=None,  # Autocommit mode, manual BEGIN/COMMIT
        )
        if self.db_path != ":memory:":
            self.conn.execute("PRAGMA journal_mode=WAL;")
            self.conn.execute("PRAGMA synchronous=FULL;")

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS mcp_idempotency (
                idem_key TEXT PRIMARY KEY,
                tenant_id TEXT,
                principal TEXT,
                operation_id TEXT,
                tool_name TEXT,
                caid TEXT,
                state TEXT, -- CONFIRMED, EFFECT_INDETERMINATE, REFUTED, UNRESOLVED_ESCALATED
                policy_epoch TEXT,
                created_at REAL,
                uncertainty_resolution_deadline REAL,
                cached_response TEXT
            );
        """)
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tenant_caid ON mcp_idempotency(tenant_id, principal, tool_name, caid);"
        )
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_caid_tool ON mcp_idempotency(caid, tool_name);")

    def compute_caid(self, arguments: Dict[str, Any], tool_name: str = "") -> str:
        """Computes deterministic Content-Addressed Action Identifier over canonical arguments."""
        canonical = canonical_json_v1({"tool": tool_name, "arguments": arguments})
        return f"sha256:{hashlib.sha256(canonical).hexdigest()}"

    def handle_json_rpc(self, request_frame: Dict[str, Any]) -> Dict[str, Any]:
        """Routes inbound JSON-RPC frame based on method."""
        method = request_frame.get("method")
        params = request_frame.get("params")

        if method == "tools/call":
            if not isinstance(params, dict):
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32602,
                        "message": "Invalid params: expected object",
                    },
                }
            return self._handle_tools_call(params)
        elif method == "tools/status":
            if not isinstance(params, dict):
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32602,
                        "message": "Missing required idempotency_key",
                    },
                }
            return self._handle_tools_status(params)
        else:
            # Pass-through for non-consequential inspection methods (e.g., tools/list, resources/list)
            return self.upstream(request_frame)

    def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        now = time.time()

        # Capability expiration check
        expires_at = params.get("expires_at")
        if expires_at is not None and expires_at < now:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32029,
                    "message": "HALT_CAPABILITY_EXPIRED",
                    "data": {"expires_at": expires_at, "now": now},
                },
            }

        key = params.get("idempotency_key")
        op_id = params.get("operation_id") or key
        tenant_id = params.get("tenant_id", "default_tenant")
        principal = params.get("principal", "default_principal")
        tool_name = params.get("name", "")
        args = params.get("arguments", {})
        caid = params.get("caid") or self.compute_caid(args, tool_name=tool_name)
        epoch = params.get("policy_epoch", self.active_policy_epoch)

        if not key:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32602,
                    "message": "Missing required idempotency_key",
                },
            }

        # Concurrency Lock + Atomic Transaction (Defeats Thundering Herd)
        with self.lock:
            try:
                self.conn.execute("BEGIN IMMEDIATE;")

                # Eviction & Escalation:
                # 1. Any EFFECT_INDETERMINATE record whose resolution deadline or TTL expired
                # MUST transition to UNRESOLVED_ESCALATED, never silently deleted!
                self.conn.execute(
                    """
                    UPDATE mcp_idempotency 
                    SET state = 'UNRESOLVED_ESCALATED' 
                    WHERE state = 'EFFECT_INDETERMINATE' 
                      AND (? - created_at > ? OR ? > uncertainty_resolution_deadline);
                    """,
                    (now, self.ttl_sec, now),
                )

                # 2. Only settled records (CONFIRMED, REFUTED) may be purged after retention TTL
                self.conn.execute(
                    """
                    DELETE FROM mcp_idempotency 
                    WHERE state IN ('CONFIRMED', 'REFUTED') 
                      AND ? - created_at > ?;
                    """,
                    (now, self.ttl_sec),
                )

                # Query matching record by idempotency_key
                row = self.conn.execute(
                    """
                    SELECT idem_key, tenant_id, principal, operation_id, tool_name, caid, state, cached_response, policy_epoch, created_at, uncertainty_resolution_deadline
                    FROM mcp_idempotency 
                    WHERE idem_key = ?;
                    """,
                    (key,),
                ).fetchone()

                if row:
                    r_key, r_tenant, r_principal, r_op_id, r_tool, r_caid, state, cached_resp, old_epoch, created_at, deadline = row

                    # Payload consistency check: reject reuse of same key with different arguments
                    if r_caid != caid:
                        self.conn.execute("COMMIT;")
                        return {
                            "jsonrpc": "2.0",
                            "error": {
                                "code": -32602,
                                "message": "IDEMPOTENCY_KEY_REUSE_WITH_DIFFERENT_PAYLOAD",
                                "data": {"idempotency_key": key, "existing_caid": r_caid, "new_caid": caid},
                            },
                        }

                    # Epoch check: if policy epoch rotated and epoch != "unknown"
                    if old_epoch != epoch and epoch != "unknown":
                        if state in ("EFFECT_INDETERMINATE", "UNRESOLVED_ESCALATED"):
                            # Uncertainty must be preserved across epoch rotation; never silently erased!
                            pass
                        else:
                            # Settled records from old epoch may be cleared
                            self.conn.execute(
                                "DELETE FROM mcp_idempotency WHERE idem_key = ?;",
                                (key,),
                            )
                            row = None

                    if row is not None:
                        if state == "CONFIRMED":
                            self.conn.execute("COMMIT;")
                            cached_data = json.loads(cached_resp) if cached_resp else {}
                            return {
                                "jsonrpc": "2.0",
                                "result": cached_data,
                                "meta": {"replay": True, "caid": caid},
                            }
                        elif state == "EFFECT_INDETERMINATE":
                            self.conn.execute("COMMIT;")
                            return {
                                "jsonrpc": "2.0",
                                "error": {
                                    "code": -32009,
                                    "message": "HALT_BLIND_RETRY_PROHIBITED_UNDER_UNCERTAINTY",
                                    "data": {
                                        "state": "EFFECT_INDETERMINATE",
                                        "idempotency_key": key,
                                        "caid": caid,
                                    },
                                },
                            }
                        elif state == "UNRESOLVED_ESCALATED":
                            self.conn.execute("COMMIT;")
                            return {
                                "jsonrpc": "2.0",
                                "error": {
                                    "code": -32010,
                                    "message": "OPERATION_UNRESOLVED_REQUIRES_RECONCILIATION",
                                    "data": {"idempotency_key": key, "state": "UNRESOLVED_ESCALATED"},
                                },
                            }
                        elif state == "REFUTED":
                            self.conn.execute("COMMIT;")
                            return {
                                "jsonrpc": "2.0",
                                "error": {
                                    "code": -32011,
                                    "message": "OPERATION_PREVIOUSLY_REFUTED",
                                    "data": {"state": "REFUTED", "idempotency_key": key},
                                },
                            }

                if row is None:
                    # Query by composite request intent (tenant_id, principal, tool_name, caid)
                    caid_row = self.conn.execute(
                        """
                        SELECT idem_key, operation_id, state, cached_response, policy_epoch
                        FROM mcp_idempotency
                        WHERE tenant_id = ? AND principal = ? AND tool_name = ? AND caid = ?;
                        """,
                        (tenant_id, principal, tool_name, caid),
                    ).fetchone()

                    if caid_row:
                        c_key, c_op_id, c_state, c_resp, c_epoch = caid_row
                        # Disambiguate request-intent digest (CAID) from operation identity
                        has_explicit_op_id = bool(params.get("operation_id"))
                        if (has_explicit_op_id and c_op_id and c_op_id != params.get("operation_id")) or params.get("require_distinct_operation"):
                            self.conn.execute("COMMIT;")
                            return {
                                "jsonrpc": "2.0",
                                "error": {
                                    "code": -32012,
                                    "message": "HALT_CAID_OPERATION_IDENTITY_CONFLICT",
                                    "data": {
                                        "caid": caid,
                                        "existing_idem_key": c_key,
                                        "existing_operation_id": c_op_id,
                                        "new_operation_id": op_id,
                                        "action": "CONFLICT_RESOLUTION_REQUIRED",
                                    },
                                },
                            }
                        elif c_state == "CONFIRMED":
                            self.conn.execute("COMMIT;")
                            cached_data = json.loads(c_resp) if c_resp else {}
                            return {
                                "jsonrpc": "2.0",
                                "result": cached_data,
                                "meta": {"replay": True, "caid": caid},
                            }
                        elif c_state == "EFFECT_INDETERMINATE":
                            self.conn.execute("COMMIT;")
                            return {
                                "jsonrpc": "2.0",
                                "error": {
                                    "code": -32009,
                                    "message": "HALT_BLIND_RETRY_PROHIBITED_UNDER_UNCERTAINTY",
                                    "data": {
                                        "state": "EFFECT_INDETERMINATE",
                                        "idempotency_key": c_key,
                                        "caid": caid,
                                    },
                                },
                            }
                        elif c_state == "UNRESOLVED_ESCALATED":
                            self.conn.execute("COMMIT;")
                            return {
                                "jsonrpc": "2.0",
                                "error": {
                                    "code": -32010,
                                    "message": "OPERATION_UNRESOLVED_REQUIRES_RECONCILIATION",
                                    "data": {"idempotency_key": c_key},
                                },
                            }
                        elif c_state == "REFUTED":
                            self.conn.execute("COMMIT;")
                            return {
                                "jsonrpc": "2.0",
                                "error": {
                                    "code": -32011,
                                    "message": "OPERATION_PREVIOUSLY_REFUTED",
                                    "data": {"state": "REFUTED", "idempotency_key": c_key},
                                },
                            }

                # Latch fresh intent as EFFECT_INDETERMINATE before network call (Write-Before-Execute)
                deadline = now + self.uncertainty_deadline_sec
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO mcp_idempotency 
                    (idem_key, tenant_id, principal, operation_id, tool_name, caid, state, policy_epoch, created_at, uncertainty_resolution_deadline, cached_response) 
                    VALUES (?, ?, ?, ?, ?, ?, 'EFFECT_INDETERMINATE', ?, ?, ?, NULL);
                    """,
                    (key, tenant_id, principal, op_id, tool_name, caid, epoch, now, deadline),
                )
                self.conn.execute("COMMIT;")
            except sqlite3.Error as io_err:
                try:
                    self.conn.execute("ROLLBACK;")
                except Exception:
                    pass
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32027,
                        "message": "HALT_STORAGE_IO_FAILURE_FAILED_CLOSED",
                        "data": {"detail": str(io_err)},
                    },
                }
            except Exception:
                try:
                    self.conn.execute("ROLLBACK;")
                except Exception:
                    pass
                raise

        # Dispatch upstream OUTSIDE the SQLite lock to prevent thread starvation
        try:
            resp = self.upstream(
                {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": params,
                }
            )

            if "result" in resp:
                result_payload = resp["result"]
                is_tool_error = False
                if isinstance(result_payload, dict):
                    is_tool_error = bool(result_payload.get("isError", False))

                if is_tool_error:
                    # Tool-level error within JSON-RPC 200: do not mark CONFIRMED!
                    is_refuted = False
                    if result_payload.get("error_classification") == "REFUTED":
                        is_refuted = True
                    content = result_payload.get("content", [])
                    if isinstance(content, list):
                        for item in content:
                            text = item.get("text", "") if isinstance(item, dict) else str(item)
                            if any(k in text.lower() for k in ["invalid argument", "schema error", "not allowed", "validation error"]):
                                is_refuted = True
                                break

                    target_state = "REFUTED" if is_refuted else "EFFECT_INDETERMINATE"
                    self._update_state(key, target_state, result_payload)
                    return {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32021 if target_state == "EFFECT_INDETERMINATE" else -32011,
                            "message": "TOOL_ERROR_REQUIRES_RECONCILIATION" if target_state == "EFFECT_INDETERMINATE" else "OPERATION_REFUTED",
                            "data": {
                                "state": target_state,
                                "idempotency_key": key,
                                "caid": caid,
                                "tool_result": result_payload,
                            },
                        },
                    }
                else:
                    self._update_state(key, "CONFIRMED", result_payload)
                    return resp
            elif "error" in resp:
                err_code = resp["error"].get("code", 500)
                # Only definitive client/validation errors (4xx equivalent) mark REFUTED
                # Exclude 408 (Request Timeout) and 429 (Rate Limited) which are ambiguous
                if err_code in (-32601, -32602, 400, 401, 403, 404, 422):
                    self._update_state(key, "REFUTED", resp.get("error"))
                else:
                    # 408, 429, 5xx and server errors remain indeterminate
                    self._update_state(key, "EFFECT_INDETERMINATE", None)
                return resp
            else:
                self._update_state(key, "EFFECT_INDETERMINATE", None)
                return resp

        except (TimeoutError, ConnectionResetError, IOError) as exc:
            self._update_state(key, "EFFECT_INDETERMINATE", None)
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32504,
                    "message": "ERR_EFFECT_INDETERMINATE_LATCHED",
                    "data": {
                        "idempotency_key": key,
                        "caid": caid,
                        "action": "PROBE_REQUIRED",
                        "detail": str(exc),
                    },
                },
            }

    def _update_state(self, key: str, state: str, result_obj: Optional[Dict[str, Any]]) -> None:
        """Updates the state and cached response for an idempotency key in SQLite WAL."""
        with self.lock:
            try:
                resp_str = json.dumps(result_obj) if result_obj is not None else None
                self.conn.execute(
                    "UPDATE mcp_idempotency SET state = ?, cached_response = ? WHERE idem_key = ?;",
                    (state, resp_str, key),
                )
            except Exception:
                pass

    def _handle_tools_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Probes status for an idempotency key to reconcile indeterminate state."""
        key = params.get("idempotency_key")
        if not key:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32602,
                    "message": "Missing required idempotency_key",
                },
            }

        with self.lock:
            row = self.conn.execute(
                "SELECT state, cached_response, caid FROM mcp_idempotency WHERE idem_key = ?;",
                (key,),
            ).fetchone()

        if not row:
            return {
                "jsonrpc": "2.0",
                "result": {"state": "NOT_FOUND", "idempotency_key": key},
            }

        current_state, cached_resp, caid = row

        # If already settled (CONFIRMED or REFUTED), return settled state directly
        if current_state in ("CONFIRMED", "REFUTED"):
            cached_data = json.loads(cached_resp) if cached_resp else None
            return {
                "jsonrpc": "2.0",
                "result": {
                    "state": current_state,
                    "idempotency_key": key,
                    "caid": caid,
                    "cached_response": cached_data,
                },
            }

        # Attempt remote verification if target supports tools/status
        try:
            status_resp = self.upstream(
                {
                    "jsonrpc": "2.0",
                    "method": "tools/status",
                    "params": {"idempotency_key": key},
                }
            )
            if "result" in status_resp:
                remote_state = status_resp["result"].get("state")
                if remote_state in ("CONFIRMED", "REFUTED"):
                    self._update_state(key, remote_state, status_resp["result"].get("response"))
                    current_state = remote_state
                elif remote_state in ("CONTRADICTORY_CONFLICT", "CONFLICT", "UNKNOWN"):
                    # Contradictory probe response preserves uncertainty
                    current_state = "EFFECT_INDETERMINATE"
            elif "error" in status_resp:
                # Upstream error (e.g. METHOD_NOT_FOUND) -> retain EFFECT_INDETERMINATE
                pass
        except Exception:
            # If status probe fails or isn't supported, retain local indeterminate state
            pass

        return {
            "jsonrpc": "2.0",
            "result": {"state": current_state, "idempotency_key": key, "caid": caid},
        }

    def close(self) -> None:
        """Closes the underlying SQLite database connection."""
        try:
            self.conn.close()
        except Exception:
            pass


# Backwards compatibility alias
IdempotentMcpProxyMiddleware = HardenedIdempotentMcpProxy


def run_conformance_suite_vectors(
    vectors_file: Path,
    db_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Evaluates the 30-vector conformance suite against HardenedIdempotentMcpProxy.
    Returns structured pass/fail results per vector.
    """
    with open(vectors_file, "r", encoding="utf-8") as f:
        suite_data = json.load(f)

    vectors = suite_data.get("vectors", [])
    results: List[Dict[str, Any]] = []

    base_dir = db_dir or (REPO_ROOT / "output" / "mcp_conformance_dbs")
    base_dir.mkdir(parents=True, exist_ok=True)

    for v in vectors:
        v_id = v["vector_id"]
        v_name = v.get("name", "")

        call_counter = [0]
        upstream_log: List[Dict[str, Any]] = []

        def make_simulated_upstream(vector_def: Dict[str, Any]):
            def simulated_transport(req: Dict[str, Any]) -> Dict[str, Any]:
                upstream_log.append(req)
                method = req.get("method")
                behavior = vector_def.get("simulate_upstream") or vector_def.get("server_behavior")

                if method == "tools/call":
                    call_counter[0] += 1
                    # Sequence-based behavior
                    if "sequence" in vector_def:
                        seq_idx = min(call_counter[0] - 1, len(vector_def["sequence"]) - 1)
                        step = vector_def["sequence"][seq_idx]
                        step_sim = step.get("simulate_upstream") or step.get("server_behavior", "NORMAL_200")
                        if step_sim == "TIMEOUT":
                            raise TimeoutError("Simulated upstream 504 Gateway Timeout")
                        elif step_sim == "UPSTREAM_ERROR_400":
                            return {"error": {"code": 400, "message": "Bad Request"}}
                        elif step_sim == "UPSTREAM_ERROR_408":
                            return {"error": {"code": 408, "message": "Request Timeout"}}
                        elif step_sim == "UPSTREAM_ERROR_429":
                            return {"error": {"code": 429, "message": "Too Many Requests"}}
                        elif "simulate_tool_is_error" in step:
                            return {"result": step["simulate_tool_is_error"]}
                        return {"result": {"status": "SUCCESS", "step": seq_idx}}

                    if behavior == "TIMEOUT":
                        raise TimeoutError("Simulated upstream 504 Gateway Timeout")
                    elif "simulate_tool_is_error" in vector_def:
                        return {"result": vector_def["simulate_tool_is_error"]}
                    elif "simulate_upstream_error" in vector_def:
                        return {"error": vector_def["simulate_upstream_error"]}
                    return {"result": {"status": "SUCCESS"}}

                elif method == "tools/status":
                    if "sequence" in vector_def:
                        for s in vector_def["sequence"]:
                            if s.get("method") == "tools/status" and "simulate_remote_status" in s:
                                resp = s["simulate_remote_status"]
                                if "error" in resp:
                                    return {"error": {"code": -32601, "message": resp["error"]}}
                                return {"result": resp}
                    if "simulate_remote_status" in vector_def:
                        resp = vector_def["simulate_remote_status"]
                        if "error" in resp:
                            return {"error": {"code": -32601, "message": resp["error"]}}
                        return {"result": resp}
                    return {"result": {"state": "CONFIRMED"}}

                elif method == "tools/list":
                    return {"result": {"tools": [{"name": "refund.create"}]}}

                return {"error": {"code": -32601, "message": "Method not found"}}

            return simulated_transport

        db_file = base_dir / f"mcp_{v_id}.db"
        if db_file.exists():
            db_file.unlink()

        proxy = HardenedIdempotentMcpProxy(
            upstream_transport_fn=make_simulated_upstream(v),
            db_path=db_file,
        )

        passed = False
        reason = ""

        try:
            if v_id == "mcp-vec-001":
                res = proxy.handle_json_rpc(v["input"])
                passed = "result" in res and res["result"].get("status") == "SUCCESS"

            elif v_id == "mcp-vec-002":
                res1 = proxy.handle_json_rpc(v["sequence"][0])
                res2 = proxy.handle_json_rpc(v["sequence"][1])
                passed = (
                    "result" in res2
                    and res2.get("meta", {}).get("replay") is True
                    and len(upstream_log) == 1
                )

            elif v_id == "mcp-vec-003":
                res1 = proxy.handle_json_rpc(v["sequence"][0])
                res2 = proxy.handle_json_rpc(v["sequence"][1])
                passed = (
                    "result" in res2
                    and res2.get("meta", {}).get("replay") is True
                    and len(upstream_log) == 1
                )

            elif v_id == "mcp-vec-004":
                res = proxy.handle_json_rpc(v["input"])
                passed = (
                    "error" in res
                    and "ERR_EFFECT_INDETERMINATE_LATCHED" in res["error"]["message"]
                )

            elif v_id == "mcp-vec-005":
                res1 = proxy.handle_json_rpc(v["sequence"][0])
                res2 = proxy.handle_json_rpc(v["sequence"][1])
                passed = (
                    "error" in res2
                    and "HALT_BLIND_RETRY_PROHIBITED_UNDER_UNCERTAINTY" in res2["error"]["message"]
                )

            elif v_id == "mcp-vec-006":
                res1 = proxy.handle_json_rpc(v["sequence"][0])
                res2 = proxy.handle_json_rpc(v["sequence"][1])
                passed = "result" in res2 and res2["result"].get("state") == "CONFIRMED"

            elif v_id == "mcp-vec-007":
                res1 = proxy.handle_json_rpc(v["sequence"][0])
                res2 = proxy.handle_json_rpc(v["sequence"][1])
                passed = "result" in res2 and res2["result"].get("state") == "REFUTED"

            elif v_id == "mcp-vec-008":
                res1 = proxy.handle_json_rpc(v["sequence"][0])
                res2 = proxy.handle_json_rpc(v["sequence"][1])
                passed = (
                    "result" in res2
                    and res2["result"].get("state") == "EFFECT_INDETERMINATE"
                )

            elif v_id == "mcp-vec-009":
                # Pre-populate expired record from previous epoch
                old_now = time.time() - 100000
                proxy.conn.execute(
                    """
                    INSERT INTO mcp_idempotency (idem_key, caid, tool_name, state, policy_epoch, created_at, cached_response)
                    VALUES (?, ?, ?, 'CONFIRMED', ?, ?, ?);
                    """,
                    ("k-009", "sha256:old", "refund.create", v["simulate_expired_record_with_epoch"], old_now, json.dumps({"status": "OLD"})),
                )
                proxy.ttl_sec = 1000
                res = proxy.handle_json_rpc(v["input"])
                passed = "result" in res and res["result"].get("status") == "SUCCESS"

            elif v_id == "mcp-vec-010":
                # Server crash recovery simulation
                # 1. First proxy run writes in-flight record to SQLite WAL
                proxy.conn.execute(
                    """
                    INSERT INTO mcp_idempotency (idem_key, caid, tool_name, state, policy_epoch, created_at)
                    VALUES (?, ?, ?, 'EFFECT_INDETERMINATE', 'epoch-2026-Q4', ?);
                    """,
                    ("k-010", "sha256:1010", "refund.create", time.time()),
                )
                proxy.close()

                # 2. Reboot new proxy pointing to same SQLite database
                proxy_reboot = HardenedIdempotentMcpProxy(
                    upstream_transport_fn=make_simulated_upstream(v),
                    db_path=db_file,
                )
                # Attempt retry on rebooted proxy
                res = proxy_reboot.handle_json_rpc(v["input"])
                passed = (
                    "error" in res
                    and "HALT_BLIND_RETRY_PROHIBITED_UNDER_UNCERTAINTY" in res["error"]["message"]
                )
                proxy_reboot.close()

            elif v_id == "mcp-vec-011":
                res = proxy.handle_json_rpc(v["input"])
                passed = "error" in res and res["error"]["code"] == -32602

            elif v_id == "mcp-vec-012":
                res = proxy.handle_json_rpc(v["input"])
                row = proxy.conn.execute("SELECT state FROM mcp_idempotency WHERE idem_key = 'k-012';").fetchone()
                passed = row is not None and row[0] == "EFFECT_INDETERMINATE"

            elif v_id == "mcp-vec-013":
                res = proxy.handle_json_rpc(v["input"])
                row = proxy.conn.execute("SELECT state FROM mcp_idempotency WHERE idem_key = 'k-013';").fetchone()
                passed = row is not None and row[0] == "REFUTED"

            elif v_id == "mcp-vec-014":
                res = proxy.handle_json_rpc(v["input"])
                passed = "error" in res and res["error"]["code"] == -32602

            elif v_id == "mcp-vec-015":
                # Concurrency stress test: 10 concurrent threads
                def worker():
                    return proxy.handle_json_rpc(
                        {
                            "method": "tools/call",
                            "params": {
                                "name": "refund.create",
                                "arguments": {"amount_minor": 1000},
                                "idempotency_key": v["idempotency_key"],
                            },
                        }
                    )

                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                    futures = [executor.submit(worker) for _ in range(10)]
                    responses = [f.result() for f in futures]

                # Exactly 1 should have reached upstream
                passed = len(upstream_log) == 1

            elif v_id == "mcp-vec-016":
                res1 = proxy.handle_json_rpc(v["sequence"][0])
                res2 = proxy.handle_json_rpc(v["sequence"][1])
                passed = len(upstream_log) == 2

            elif v_id == "mcp-vec-017":
                res = proxy.handle_json_rpc(v["input"])
                passed = "result" in res and "tools" in res["result"]

            elif v_id == "mcp-vec-018":
                res = proxy.handle_json_rpc(v["input"])
                passed = "error" in res and res["error"]["code"] == -32602

            elif v_id == "mcp-vec-019":
                res = proxy.handle_json_rpc(v["input"])
                passed = "result" in res and res["result"].get("state") == "NOT_FOUND"

            elif v_id == "mcp-vec-020":
                res1 = proxy.handle_json_rpc(v["sequence"][0])
                res2 = proxy.handle_json_rpc(v["sequence"][1])
                passed = "result" in res2 and res2["result"].get("status") == "SUCCESS"

            elif v_id == "mcp-vec-021":
                res = proxy.handle_json_rpc(v["input"])
                row = proxy.conn.execute("SELECT state FROM mcp_idempotency WHERE idem_key = 'k-021';").fetchone()
                passed = (
                    "error" in res
                    and res["error"].get("message") == "TOOL_ERROR_REQUIRES_RECONCILIATION"
                    and row is not None
                    and row[0] == "EFFECT_INDETERMINATE"
                )

            elif v_id == "mcp-vec-022":
                res1 = proxy.handle_json_rpc(v["sequence"][0])
                res2 = proxy.handle_json_rpc(v["sequence"][1])
                passed = (
                    "error" in res2
                    and "HALT_CAID_OPERATION_IDENTITY_CONFLICT" in res2["error"].get("message", "")
                )

            elif v_id == "mcp-vec-023":
                # Pre-populate expired indeterminate record
                old_time = time.time() - 100000
                proxy.conn.execute(
                    """
                    INSERT INTO mcp_idempotency 
                    (idem_key, tenant_id, principal, operation_id, tool_name, caid, state, policy_epoch, created_at, uncertainty_resolution_deadline)
                    VALUES (?, 'default_tenant', 'default_principal', 'op-023', 'refund.create', 'sha256:2323', 'EFFECT_INDETERMINATE', 'epoch-2026-Q4', ?, ?);
                    """,
                    ("k-023", old_time, old_time + 60),
                )
                proxy.ttl_sec = 1000
                res = proxy.handle_json_rpc(v["input"])
                row = proxy.conn.execute("SELECT state FROM mcp_idempotency WHERE idem_key = 'k-023';").fetchone()
                passed = (
                    "error" in res
                    and "OPERATION_UNRESOLVED_REQUIRES_RECONCILIATION" in res["error"]["message"]
                    and row is not None
                    and row[0] == "UNRESOLVED_ESCALATED"
                )

            elif v_id == "mcp-vec-024":
                res1 = proxy.handle_json_rpc(v["sequence"][0])
                res2 = proxy.handle_json_rpc(v["sequence"][1])
                row = proxy.conn.execute("SELECT state FROM mcp_idempotency WHERE idem_key = 'k-024';").fetchone()
                passed = (
                    "error" in res2
                    and "HALT_BLIND_RETRY_PROHIBITED_UNDER_UNCERTAINTY" in res2["error"]["message"]
                    and row is not None
                    and row[0] == "EFFECT_INDETERMINATE"
                )

            elif v_id == "mcp-vec-025":
                res1 = proxy.handle_json_rpc(v["sequence"][0])
                res2 = proxy.handle_json_rpc(v["sequence"][1])
                forwarded_keys = [
                    req.get("params", {}).get("idempotency_key")
                    for req in upstream_log
                    if "params" in req
                ]
                passed = (
                    len(forwarded_keys) >= 2
                    and all(k == "k-025-stable" for k in forwarded_keys)
                    and "result" in res2
                    and res2["result"].get("state") == "CONFIRMED"
                )

            elif v_id == "mcp-vec-026":
                res1 = proxy.handle_json_rpc(v["sequence"][0])
                res2 = proxy.handle_json_rpc(v["sequence"][1])
                passed = (
                    "result" in res2
                    and res2["result"].get("state") == "EFFECT_INDETERMINATE"
                )

            elif v_id == "mcp-vec-027":
                proxy.conn.close()
                class BrokenConn:
                    def execute(self, *args, **kwargs):
                        raise sqlite3.OperationalError("disk I/O error or filesystem full")
                proxy.conn = BrokenConn()
                res = proxy.handle_json_rpc(v["input"])
                passed = (
                    "error" in res
                    and "HALT_STORAGE_IO_FAILURE_FAILED_CLOSED" in res["error"]["message"]
                    and len(upstream_log) == 0
                )

            elif v_id == "mcp-vec-028":
                future_time = time.time() + 1000
                target_caid = proxy.compute_caid(v["input"]["params"]["arguments"], tool_name="refund.create")
                proxy.conn.execute(
                    """
                    INSERT INTO mcp_idempotency 
                    (idem_key, tenant_id, principal, operation_id, tool_name, caid, state, policy_epoch, created_at, uncertainty_resolution_deadline)
                    VALUES (?, 'default_tenant', 'default_principal', 'op-028', 'refund.create', ?, 'EFFECT_INDETERMINATE', 'epoch-2026-Q4', ?, ?);
                    """,
                    ("k-028", target_caid, future_time, future_time + 300),
                )
                res = proxy.handle_json_rpc(v["input"])
                passed = (
                    "error" in res
                    and "HALT_BLIND_RETRY_PROHIBITED_UNDER_UNCERTAINTY" in res["error"]["message"]
                )

            elif v_id == "mcp-vec-029":
                res = proxy.handle_json_rpc(v["input"])
                passed = (
                    "error" in res
                    and "HALT_CAPABILITY_EXPIRED" in res["error"]["message"]
                    and len(upstream_log) == 0
                )

            elif v_id == "mcp-vec-030":
                def worker():
                    return proxy.handle_json_rpc(
                        {
                            "method": "tools/call",
                            "params": {
                                "name": "refund.create",
                                "arguments": {"amount_minor": 1000},
                                "idempotency_key": v["idempotency_key"],
                            },
                        }
                    )

                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                    futures = [executor.submit(worker) for _ in range(8)]
                    responses = [f.result() for f in futures]

                passed = len(upstream_log) == 1 and all("result" in r or "error" in r for r in responses)

        except Exception as exc:
            passed = False
            reason = str(exc)
        finally:
            proxy.close()
            if db_file.exists():
                try:
                    db_file.unlink()
                except Exception:
                    pass

        results.append(
            {
                "vector_id": v_id,
                "name": v_name,
                "passed": passed,
                "reason": reason if not passed else "OK",
            }
        )

    passed_count = sum(1 for r in results if r["passed"])
    return {
        "suite": suite_data.get("conformance_suite", "mcp_idempotency.vectors.v1"),
        "total": len(results),
        "passed": passed_count,
        "failed": len(results) - passed_count,
        "pass_rate_pct": round((passed_count / max(1, len(results))) * 100.0, 2),
        "results": results,
    }


def main() -> int:
    vectors_path = REPO_ROOT / "conformance" / "vectors" / "mcp_idempotency.vectors.v1.json"
    if not vectors_path.exists():
        print(f"Error: Conformance vectors not found at {vectors_path}", file=sys.stderr)
        return 1

    report = run_conformance_suite_vectors(vectors_path)
    print("================================================================================")
    print("       HARDENED IDEMPOTENT MCP PROXY — CONFORMANCE SUITE REPORT               ")
    print("================================================================================")
    print(f"Suite:           {report['suite']}")
    print(f"Total Vectors:   {report['total']}")
    print(f"Passed:          {report['passed']}")
    print(f"Failed:          {report['failed']}")
    print(f"Pass Rate:       {report['pass_rate_pct']}%")
    print("--------------------------------------------------------------------------------")
    for r in report["results"]:
        status = "PASSED" if r["passed"] else "FAILED"
        print(f"[{status}] {r['vector_id']:<14} : {r['name']}")
    print("================================================================================")

    # Write output artifact
    out_dir = REPO_ROOT / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "mcp-conformance-report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
