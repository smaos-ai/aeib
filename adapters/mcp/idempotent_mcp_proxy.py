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
3. Enforces write-before-execute intent logging into a durable SQLite WAL with `BEGIN IMMEDIATE`.
4. Serializes concurrent requests on identical keys/CAID to defeat thundering herd races.
5. Latches ambiguous network transport drops and 5xx errors into `EFFECT_INDETERMINATE`.
6. Halts blind retries under uncertainty and drives authoritative `tools/status` reconciliation.
7. Handles TTL eviction and policy epoch rotation.
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
    cached_response: Optional[Dict[str, Any]] = None
    policy_epoch: str = "epoch-2026-Q4"
    created_at: float = field(default_factory=time.time)
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
        active_policy_epoch: str = "epoch-2026-Q4",
    ) -> None:
        self.upstream = upstream_transport_fn
        self.db_path = str(db_path)
        self.ttl_sec = ttl_sec
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
                caid TEXT,
                tool_name TEXT,
                state TEXT, -- CONFIRMED, EFFECT_INDETERMINATE, REFUTED, UNRESOLVED_ESCALATED
                policy_epoch TEXT,
                created_at REAL,
                cached_response TEXT
            );
        """)
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
        key = params.get("idempotency_key")
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

        now = time.time()

        # Concurrency Lock + Atomic Transaction (Defeats Thundering Herd)
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE;")
            try:
                # Evict expired TTL entries
                self.conn.execute(
                    "DELETE FROM mcp_idempotency WHERE ? - created_at > ?;",
                    (now, self.ttl_sec),
                )

                # Query matching record by idempotency_key OR (caid AND tool_name)
                row = self.conn.execute(
                    """
                    SELECT idem_key, state, cached_response, policy_epoch, created_at 
                    FROM mcp_idempotency 
                    WHERE idem_key = ? OR (caid = ? AND tool_name = ?);
                    """,
                    (key, caid, tool_name),
                ).fetchone()

                if row:
                    old_key, state, cached_resp, old_epoch, created_at = row

                    # Epoch check: if policy epoch rotated and epoch != "unknown", allow fresh intent
                    if old_epoch != epoch and epoch != "unknown":
                        self.conn.execute(
                            "DELETE FROM mcp_idempotency WHERE idem_key = ?;",
                            (old_key,),
                        )
                    elif state == "CONFIRMED":
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
                                    "idempotency_key": old_key,
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
                                "data": {"idempotency_key": old_key},
                            },
                        }
                    elif state == "REFUTED":
                        self.conn.execute("COMMIT;")
                        return {
                            "jsonrpc": "2.0",
                            "error": {
                                "code": -32011,
                                "message": "OPERATION_PREVIOUSLY_REFUTED",
                                "data": {"state": "REFUTED", "idempotency_key": old_key},
                            },
                        }

                # Latch fresh intent as EFFECT_INDETERMINATE before network call (Write-Before-Execute)
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO mcp_idempotency 
                    (idem_key, caid, tool_name, state, policy_epoch, created_at, cached_response) 
                    VALUES (?, ?, ?, 'EFFECT_INDETERMINATE', ?, ?, NULL);
                    """,
                    (key, caid, tool_name, epoch, now),
                )
                self.conn.execute("COMMIT;")
            except Exception:
                self.conn.execute("ROLLBACK;")
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
                self._update_state(key, "CONFIRMED", resp["result"])
                return resp
            elif "error" in resp:
                err_code = resp["error"].get("code", 500)
                # Only definitive client/validation errors (4xx equivalent) mark REFUTED
                if err_code in (-32601, -32602, 400, 401, 403, 404, 422):
                    self._update_state(key, "REFUTED", resp.get("error"))
                else:
                    # 5xx and server errors remain indeterminate
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
            resp_str = json.dumps(result_obj) if result_obj is not None else None
            self.conn.execute(
                "UPDATE mcp_idempotency SET state = ?, cached_response = ? WHERE idem_key = ?;",
                (state, resp_str, key),
            )

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
    Evaluates the 20-vector conformance suite against HardenedIdempotentMcpProxy.
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
                        return {"result": {"status": "SUCCESS", "step": seq_idx}}

                    if behavior == "TIMEOUT":
                        raise TimeoutError("Simulated upstream 504 Gateway Timeout")
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

                # Exactly 1 should have reached upstream, others return cached response or in-flight latch
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

    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
