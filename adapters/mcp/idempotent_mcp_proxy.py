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
adapters/mcp/idempotent_mcp_proxy.py — Reference Idempotent MCP Proxy Middleware.

Lifts Station 1 (schema + Content-Addressed Action Identifier) and Station 2
(Write-Ahead Log + uncertainty latch) directly into the Model Context Protocol (MCP)
JSON-RPC transport and tool call lifecycle.

Core Functions:
1. Intercepts JSON-RPC `tools/call` and `tools/status` requests.
2. Computes Content-Addressed Action Identifiers (CAID) via RFC 8785 JCS canonicalization.
3. Enforces write-before-execute intent logging into an append-only WAL.
4. Latches ambiguous network transport drops (504/timeout/RST) into `EFFECT_INDETERMINATE`.
5. Halts blind retries under uncertainty and drives authoritative `tools/status` reconciliation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
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
    state: str  # CONFIRMED, EFFECT_INDETERMINATE, REFUTED, UNRESOLVED_ESCALATED, NOT_FOUND
    cached_response: Optional[Dict[str, Any]] = None
    policy_epoch: str = "epoch-2026-Q4"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class IdempotentMcpProxyMiddleware:
    """
    Sits between the agent client and the upstream MCP server.
    Owns the idempotency WAL and enforces uncertainty state-machine rules.
    """

    def __init__(
        self,
        upstream_transport_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
        ttl_sec: int = 86400,
        wal_path: Optional[Path | str] = None,
        active_policy_epoch: str = "epoch-2026-Q4",
    ) -> None:
        self.upstream_transport_fn = upstream_transport_fn
        self.ttl_sec = ttl_sec
        self.wal_path = Path(wal_path) if wal_path else None
        self.active_policy_epoch = active_policy_epoch
        self._lock = threading.Lock()
        self.store: Dict[str, McpProxyStateRecord] = {}
        self.caid_index: Dict[str, str] = {}  # caid -> idempotency_key

        if self.wal_path and self.wal_path.exists():
            self._recover_wal()

    def compute_caid(self, arguments: Dict[str, Any]) -> str:
        """Computes deterministic Content-Addressed Action Identifier over canonical arguments."""
        canonical = canonical_json_v1(arguments)
        return f"sha256:{hashlib.sha256(canonical).hexdigest()}"

    def _append_wal(self, record: McpProxyStateRecord) -> None:
        """Appends state transition record to on-disk WAL."""
        if not self.wal_path:
            return
        self.wal_path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(record)
        line = json.dumps(payload, ensure_ascii=False) + "\n"
        with open(self.wal_path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass

    def _recover_wal(self) -> None:
        """Rehydrates proxy state records from disk WAL upon initialization."""
        if not self.wal_path or not self.wal_path.exists():
            return
        with open(self.wal_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    rec = McpProxyStateRecord(
                        idempotency_key=data["idempotency_key"],
                        caid=data["caid"],
                        state=data["state"],
                        cached_response=data.get("cached_response"),
                        policy_epoch=data.get("policy_epoch", "epoch-2026-Q4"),
                        created_at=data.get("created_at", time.time()),
                        updated_at=data.get("updated_at", time.time()),
                    )
                    self.store[rec.idempotency_key] = rec
                    self.caid_index[rec.caid] = rec.idempotency_key
                except Exception:
                    continue

    def handle_json_rpc(self, request_frame: Dict[str, Any]) -> Dict[str, Any]:
        """Routes inbound JSON-RPC frame based on method."""
        method = request_frame.get("method")
        params = request_frame.get("params", {})

        if method == "tools/call":
            return self._handle_tools_call(params)
        elif method == "tools/status":
            return self._handle_tools_status(params)
        else:
            # Pass-through for non-consequential inspection methods (e.g., tools/list, resources/list)
            return self.upstream_transport_fn(request_frame)

    def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        key = params.get("idempotency_key")
        args = params.get("arguments", {})
        caid = params.get("caid") or self.compute_caid(args)
        epoch = params.get("policy_epoch", self.active_policy_epoch)

        if not key:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32602,
                    "message": "Missing required idempotency_key",
                },
            }

        with self._lock:
            # 1. Check CAID index or key store for prior state
            active_key = self.caid_index.get(caid) or key
            record = self.store.get(active_key)

            if record:
                # Check for TTL expiry and policy epoch rotation
                is_expired = (time.time() - record.created_at) > self.ttl_sec
                epoch_rotated = epoch != record.policy_epoch

                if is_expired and epoch_rotated:
                    # TTL expired under a new policy epoch; purge stale record and allow fresh intent
                    del self.store[active_key]
                    if caid in self.caid_index:
                        del self.caid_index[caid]
                    record = None
                else:
                    if record.state == "CONFIRMED":
                        return {
                            "jsonrpc": "2.0",
                            "result": record.cached_response,
                            "meta": {"replay": True, "caid": record.caid},
                        }
                    elif record.state == "EFFECT_INDETERMINATE":
                        return {
                            "jsonrpc": "2.0",
                            "error": {
                                "code": -32009,
                                "message": "HALT_BLIND_RETRY_PROHIBITED_UNDER_UNCERTAINTY",
                                "data": {
                                    "state": "EFFECT_INDETERMINATE",
                                    "idempotency_key": active_key,
                                    "caid": record.caid,
                                },
                            },
                        }
                    elif record.state == "UNRESOLVED_ESCALATED":
                        return {
                            "jsonrpc": "2.0",
                            "error": {
                                "code": -32010,
                                "message": "OPERATION_UNRESOLVED_REQUIRES_RECONCILIATION",
                                "data": {"idempotency_key": active_key},
                            },
                        }
                    elif record.state == "REFUTED":
                        return {
                            "jsonrpc": "2.0",
                            "error": {
                                "code": -32011,
                                "message": "OPERATION_PREVIOUSLY_REFUTED",
                                "data": {"state": "REFUTED", "idempotency_key": active_key},
                            },
                        }

            # 2. Register fresh intent in WAL as in-flight / pending execution (Write-Before-Execute)
            new_record = McpProxyStateRecord(
                idempotency_key=key,
                caid=caid,
                state="EFFECT_INDETERMINATE",
                policy_epoch=epoch,
            )
            self.store[key] = new_record
            self.caid_index[caid] = key
            self._append_wal(new_record)

        # 3. Dispatch to upstream MCP server outside the critical section lock
        try:
            upstream_resp = self.upstream_transport_fn(
                {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": params,
                }
            )

            with self._lock:
                if "result" in upstream_resp:
                    new_record.state = "CONFIRMED"
                    new_record.cached_response = upstream_resp["result"]
                    new_record.updated_at = time.time()
                    self._append_wal(new_record)
                    return upstream_resp
                elif "error" in upstream_resp:
                    new_record.state = "REFUTED"
                    new_record.cached_response = upstream_resp.get("error")
                    new_record.updated_at = time.time()
                    self._append_wal(new_record)
                    return upstream_resp
                else:
                    return upstream_resp

        except (TimeoutError, ConnectionResetError, IOError) as exc:
            with self._lock:
                # Transport dropped / timed out -> state remains strictly EFFECT_INDETERMINATE
                new_record.state = "EFFECT_INDETERMINATE"
                new_record.updated_at = time.time()
                self._append_wal(new_record)
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

    def _handle_tools_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Probes status for an idempotency key to reconcile indeterminate state."""
        key = params.get("idempotency_key")
        with self._lock:
            record = self.store.get(key)
            if not record:
                return {
                    "jsonrpc": "2.0",
                    "result": {"state": "NOT_FOUND", "idempotency_key": key},
                }

            # If the record is already settled (CONFIRMED or REFUTED), return settled state directly
            if record.state in ("CONFIRMED", "REFUTED"):
                return {
                    "jsonrpc": "2.0",
                    "result": {
                        "state": record.state,
                        "idempotency_key": key,
                        "caid": record.caid,
                        "cached_response": record.cached_response,
                    },
                }

        # Query upstream tools/status if available
        try:
            status_resp = self.upstream_transport_fn(
                {
                    "jsonrpc": "2.0",
                    "method": "tools/status",
                    "params": {"idempotency_key": key},
                }
            )

            with self._lock:
                if "result" in status_resp:
                    remote_state = status_resp["result"].get("state")
                    if remote_state in ("CONFIRMED", "REFUTED"):
                        record.state = remote_state
                        record.updated_at = time.time()
                        self._append_wal(record)
                elif "error" in status_resp:
                    # Endpoint unsupported or returned error -> escalate
                    record.state = "UNRESOLVED_ESCALATED"
                    record.updated_at = time.time()
                    self._append_wal(record)
        except Exception:
            with self._lock:
                record.state = "UNRESOLVED_ESCALATED"
                record.updated_at = time.time()
                self._append_wal(record)

        with self._lock:
            return {
                "jsonrpc": "2.0",
                "result": {"state": record.state, "idempotency_key": key, "caid": record.caid},
            }


def run_conformance_suite_vectors(
    vectors_file: Path,
) -> Dict[str, Any]:
    """
    Evaluates the 20-vector conformance suite against IdempotentMcpProxyMiddleware.
    Returns structured pass/fail results per vector.
    """
    with open(vectors_file, "r", encoding="utf-8") as f:
        suite_data = json.load(f)

    vectors = suite_data.get("vectors", [])
    results: List[Dict[str, Any]] = []

    for v in vectors:
        v_id = v["vector_id"]
        v_name = v.get("name", "")

        # Set up a simulated upstream based on vector parameters
        call_counter = [0]
        upstream_log: List[Dict[str, Any]] = []

        def make_simulated_upstream(vector_def: Dict[str, Any]):
            def simulated_transport(req: Dict[str, Any]) -> Dict[str, Any]:
                upstream_log.append(req)
                method = req.get("method")
                behavior = vector_def.get("server_behavior")

                if method == "tools/call":
                    call_counter[0] += 1
                    # Sequence-based behavior
                    if "sequence" in vector_def:
                        seq_idx = min(call_counter[0] - 1, len(vector_def["sequence"]) - 1)
                        step = vector_def["sequence"][seq_idx]
                        step_behavior = step.get("server_behavior", "NORMAL_200")
                        if step_behavior == "TIMEOUT_504_BUT_COMMITTED":
                            raise TimeoutError("Simulated upstream 504 Gateway Timeout")
                        elif step_behavior == "TIMEOUT_504_ABORTED":
                            raise TimeoutError("Simulated upstream 504 Aborted")
                        elif step_behavior == "CONNECTION_RESET":
                            raise ConnectionResetError("Simulated TCP RST")
                        elif step_behavior == "UPSTREAM_ERROR_400":
                            return {"error": {"code": 400, "message": "Bad Request"}}
                        elif step_behavior == "SHOULD_NOT_EXECUTE":
                            raise AssertionError("Upstream should not have been called!")
                        return {"result": {"status": "SUCCESS", "step": seq_idx}}

                    if behavior == "TIMEOUT_504_BUT_COMMITTED":
                        raise TimeoutError("Simulated upstream 504 Gateway Timeout")
                    elif behavior == "CONNECTION_RESET":
                        raise ConnectionResetError("Simulated TCP RST")
                    elif behavior == "UPSTREAM_ERROR_400":
                        return {"error": {"code": 400, "message": "Bad Request"}}
                    return {"result": {"status": "SUCCESS"}}

                elif method == "tools/status":
                    # Check for sequence-level server_status_response
                    if "sequence" in vector_def:
                        for s in vector_def["sequence"]:
                            if s.get("method") == "tools/status" and "server_status_response" in s:
                                resp = s["server_status_response"]
                                if "error" in resp:
                                    return {"error": {"code": -32601, "message": resp["error"]}}
                                return {"result": resp}
                    return {"result": {"state": "CONFIRMED"}}

                elif method == "tools/list":
                    return {"result": {"tools": [{"name": "refund.create"}]}}

                return {"error": {"code": -32601, "message": "Method not found"}}

            return simulated_transport

        # Run vector
        proxy = IdempotentMcpProxyMiddleware(upstream_transport_fn=make_simulated_upstream(v))

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
                    "result" in res2 and res2["result"].get("state") == "UNRESOLVED_ESCALATED"
                )

            elif v_id == "mcp-vec-009":
                # Pre-populate expired record from previous epoch
                old_rec = McpProxyStateRecord(
                    idempotency_key="key-009",
                    caid="sha256:old",
                    state="CONFIRMED",
                    policy_epoch=v["expired_record_epoch"],
                    created_at=time.time() - 100000,
                )
                proxy.store["key-009"] = old_rec
                proxy.ttl_sec = 1000
                res = proxy.handle_json_rpc(
                    {
                        "method": "tools/call",
                        "params": {
                            "name": "refund.create",
                            "arguments": {"amount_minor": 10000},
                            "idempotency_key": "key-009",
                            "policy_epoch": v["input"]["policy_epoch"],
                        },
                    }
                )
                passed = "result" in res and res["result"].get("status") == "SUCCESS"

            elif v_id == "mcp-vec-010":
                # Server crash recovery simulation
                wal_tmp = REPO_ROOT / "output" / "mcp_test_wal.jsonl"
                wal_tmp.parent.mkdir(parents=True, exist_ok=True)
                if wal_tmp.exists():
                    wal_tmp.unlink()

                proxy_pre = IdempotentMcpProxyMiddleware(
                    upstream_transport_fn=make_simulated_upstream(v),
                    wal_path=wal_tmp,
                )
                # In-flight record before crash
                rec_inflight = McpProxyStateRecord(
                    idempotency_key="key-010",
                    caid="sha256:1010",
                    state="EFFECT_INDETERMINATE",
                )
                proxy_pre._append_wal(rec_inflight)

                # Boot new proxy instance on same WAL
                proxy_reboot = IdempotentMcpProxyMiddleware(
                    upstream_transport_fn=make_simulated_upstream(v),
                    wal_path=wal_tmp,
                )
                passed = (
                    "key-010" in proxy_reboot.store
                    and proxy_reboot.store["key-010"].state == "EFFECT_INDETERMINATE"
                )
                if wal_tmp.exists():
                    wal_tmp.unlink()

            elif v_id == "mcp-vec-011":
                res = proxy.handle_json_rpc(v["input"])
                passed = "error" in res and res["error"]["code"] == -32602

            elif v_id == "mcp-vec-012":
                res = proxy.handle_json_rpc(v["input"])
                passed = "result" in res and len(proxy.store) == 0

            elif v_id == "mcp-vec-013":
                res = proxy.handle_json_rpc(v["sequence"][0])
                passed = "error" in res and proxy.store.get("key-013", None) is not None
                if passed:
                    passed = proxy.store["key-013"].state == "REFUTED"

            elif v_id == "mcp-vec-014":
                caid_a = proxy.compute_caid(v["input_a"])
                caid_b = proxy.compute_caid(v["input_b"])
                passed = caid_a == caid_b

            elif v_id == "mcp-vec-015":
                res = proxy.handle_json_rpc(v["input"])
                passed = (
                    "error" in res
                    and "ERR_EFFECT_INDETERMINATE_LATCHED" in res["error"]["message"]
                )

            elif v_id == "mcp-vec-016":
                proxy.store["key-016"] = McpProxyStateRecord(
                    idempotency_key="key-016",
                    caid="sha256:1616",
                    state="UNRESOLVED_ESCALATED",
                )
                res = proxy.handle_json_rpc(v["input"])
                passed = "error" in res and res["error"]["code"] == -32010

            elif v_id == "mcp-vec-017":
                res1 = proxy.handle_json_rpc(v["sequence"][0])
                res2 = proxy.handle_json_rpc(v["sequence"][1])
                passed = (
                    "result" in res1
                    and "result" in res2
                    and res2.get("meta", {}).get("replay") is True
                    and len(upstream_log) == 1
                )

            elif v_id == "mcp-vec-018":
                wal_tmp = REPO_ROOT / "output" / "mcp_test_wal_018.jsonl"
                wal_tmp.parent.mkdir(parents=True, exist_ok=True)
                if wal_tmp.exists():
                    wal_tmp.unlink()

                proxy_w = IdempotentMcpProxyMiddleware(
                    upstream_transport_fn=make_simulated_upstream(v),
                    wal_path=wal_tmp,
                )
                rec = McpProxyStateRecord(
                    idempotency_key="key-018",
                    caid="sha256:1818",
                    state="CONFIRMED",
                    cached_response={"status": "PAID"},
                )
                proxy_w._append_wal(rec)

                proxy_r = IdempotentMcpProxyMiddleware(
                    upstream_transport_fn=make_simulated_upstream(v),
                    wal_path=wal_tmp,
                )
                status_res = proxy_r.handle_json_rpc(
                    {"method": "tools/status", "params": {"idempotency_key": "key-018"}}
                )
                passed = (
                    "result" in status_res
                    and status_res["result"].get("state") == "CONFIRMED"
                )
                if wal_tmp.exists():
                    wal_tmp.unlink()

            elif v_id == "mcp-vec-019":
                res = proxy.handle_json_rpc(v["input"])
                passed = "result" in res and res["result"].get("state") == "NOT_FOUND"

            elif v_id == "mcp-vec-020":
                # Sequence: Call 1 (timeout) -> Call 2 (blind retry blocked) -> Status probe (confirmed) -> Call 3 (cached replay)
                s = v["sequence"]
                res1 = proxy.handle_json_rpc(s[0])
                res2 = proxy.handle_json_rpc(s[1])
                res3 = proxy.handle_json_rpc(s[2])
                res4 = proxy.handle_json_rpc(s[3])

                passed = (
                    "error" in res1
                    and "ERR_EFFECT_INDETERMINATE_LATCHED" in res1["error"]["message"]
                    and "error" in res2
                    and "HALT_BLIND_RETRY_PROHIBITED_UNDER_UNCERTAINTY" in res2["error"]["message"]
                    and "result" in res3
                    and res3["result"].get("state") == "CONFIRMED"
                    and "result" in res4
                    and res4.get("meta", {}).get("replay") is True
                )

        except Exception as exc:
            passed = False
            reason = str(exc)

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
    print("       IDEMPOTENT MCP PROXY — CONFORMANCE SUITE EVALUATION REPORT             ")
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
