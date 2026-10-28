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
tests/test_idempotent_mcp_proxy.py — Pytest suite for Hardened Idempotent MCP Proxy Middleware.

Verifies:
1. 30/30 Golden Conformance Vectors pass cleanly against HardenedIdempotentMcpProxy.
2. Content-Addressed Action Identifier (CAID) collision detection and tool isolation.
3. Disambiguation of CAID intent from operation identity (conflict escalation).
4. Timeout 504, 5xx, and ambiguous 408/429 error durable uncertainty latching (EFFECT_INDETERMINATE).
5. MCP tool-level isError: true in 200 response routes to uncertainty latch.
6. TTL safety invariant: unresolved indeterminate records escalate to UNRESOLVED_ESCALATED and are never erased.
7. Policy epoch rotation preserves latched uncertainty without silent erasure.
8. Definitive 4xx client errors mark REFUTED.
9. Blind retry blocking under uncertainty (HALT_BLIND_RETRY_PROHIBITED_UNDER_UNCERTAINTY).
10. Authoritative tools/status reconciliation loop.
11. Server-crash SQLite WAL recovery across process restarts.
12. Thundering herd concurrent serialization (exactly 1 upstream execution).
13. Storage I/O failure and capability expiration fail closed without upstream dispatch.
14. CLI execution and epistemic purity.
"""

from __future__ import annotations

import concurrent.futures
import importlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import adapters.mcp.idempotent_mcp_proxy as mcp_mod
from adapters.mcp.idempotent_mcp_proxy import (
    HardenedIdempotentMcpProxy,
    run_conformance_suite_vectors,
)


def test_module_sys_path_bootstrap() -> None:
    """Verifies REPO_ROOT sys.path bootstrap when missing."""
    global HardenedIdempotentMcpProxy, run_conformance_suite_vectors
    repo_str = str(mcp_mod.REPO_ROOT)
    orig_path = list(sys.path)
    try:
        sys.path = [p for p in sys.path if p != repo_str]
        importlib.reload(mcp_mod)
        assert sys.path[0] == repo_str
    finally:
        sys.path = orig_path
        HardenedIdempotentMcpProxy = mcp_mod.HardenedIdempotentMcpProxy
        run_conformance_suite_vectors = mcp_mod.run_conformance_suite_vectors


def test_idempotent_mcp_proxy_all_30_conformance_vectors(tmp_path: Path):
    """Evaluates all 30 vectors in conformance/vectors/mcp_idempotency.vectors.v1.json and inspects transport."""
    vectors_path = REPO_ROOT / "conformance" / "vectors" / "mcp_idempotency.vectors.v1.json"

    status_error_codes = []
    rpc_calls = []
    steps_seen = []
    orig_proxy_cls = mcp_mod.HardenedIdempotentMcpProxy
    orig_executor_cls = mcp_mod.concurrent.futures.ThreadPoolExecutor

    class _InspectingProxy(orig_proxy_cls):  # type: ignore[valid-type,misc]
        def __init__(self, upstream_transport_fn, *args, **kwargs):
            def _wrapped_upstream(req):
                resp = upstream_transport_fn(req)
                if req.get("method") == "tools/status" and isinstance(resp, dict) and "error" in resp:
                    status_error_codes.append(resp["error"].get("code"))
                return resp

            super().__init__(_wrapped_upstream, *args, **kwargs)

        def handle_json_rpc(self, request_frame):
            rpc_calls.append(request_frame)
            res = super().handle_json_rpc(request_frame)
            if isinstance(res, dict) and isinstance(res.get("result"), dict) and "step" in res["result"]:
                steps_seen.append(res["result"]["step"])
            return res

    class _InspectingExecutor(orig_executor_cls):  # type: ignore[valid-type,misc]
        def __init__(self, max_workers=None, *args, **kwargs):
            super().__init__(max_workers=max_workers, *args, **kwargs)
            self._mw = max_workers
            self._submitted = 0

        def submit(self, fn, *args, **kwargs):
            self._submitted += 1
            def _checked():
                res = fn(*args, **kwargs)
                if not isinstance(res, dict):
                    raise RuntimeError("Worker returned non-dict")
                return res
            return super().submit(_checked)

        def __exit__(self, exc_type, exc_val, exc_tb):
            res = super().__exit__(exc_type, exc_val, exc_tb)
            if self._mw == 10 and self._submitted != 10:
                raise RuntimeError(f"Expected 10 submitted tasks, got {self._submitted}")
            return res

    try:
        mcp_mod.HardenedIdempotentMcpProxy = _InspectingProxy
        mcp_mod.concurrent.futures.ThreadPoolExecutor = _InspectingExecutor
        report = run_conformance_suite_vectors(vectors_path, db_dir=tmp_path)
    finally:
        mcp_mod.HardenedIdempotentMcpProxy = orig_proxy_cls
        mcp_mod.concurrent.futures.ThreadPoolExecutor = orig_executor_cls

    assert report["total"] == 30
    assert report["passed"] == 30
    assert report["failed"] == 0
    assert report["pass_rate_pct"] == 100.0
    assert status_error_codes == [-(326 * 100 + 1)]
    v15_key = [
        v["idempotency_key"]
        for v in json.loads(vectors_path.read_text(encoding="utf-8"))["vectors"]
        if v["vector_id"] == "mcp-vec-015"
    ][0]
    vec15_calls = [
        c for c in rpc_calls
        if isinstance(c.get("params"), dict) and c["params"].get("idempotency_key") == v15_key
    ]
    assert len(vec15_calls) == 10
    assert all(c["params"]["arguments"]["amount_minor"] == 10 * 100 for c in vec15_calls)
    assert 0 in steps_seen and 1 in steps_seen


def test_idempotent_mcp_proxy_defaults_caid_refuted_and_main(tmp_path: Path):
    """Verifies constructor defaults, -32600/-32601 classification, CAID REFUTED -32011 code, and main()."""
    proxy = HardenedIdempotentMcpProxy(upstream_transport_fn=lambda _r: {"error": {"code": 400, "message": "Bad"}})
    assert proxy.uncertainty_deadline_sec == 3 * 100
    assert proxy.tool_pin_guard.learn_mode is False
    assert proxy._classify_upstream_response(-(326 * 100), {}) == ("REFUTED", "definitive_client_rejection")
    assert proxy._classify_upstream_response(-(326 * 100 + 1), {}) == ("REFUTED", "definitive_client_rejection")

    # StrictJSONError via handle_raw_frame (duplicate keys)
    res_dup = proxy.handle_raw_frame('{"a": 1, "a": 2}')
    assert isinstance(res_dup, dict) and res_dup["error"]["code"] == -(327 * 100)

    # 1st call with k-ref-1 is REFUTED (400)
    res1 = proxy.handle_json_rpc(
        {
            "method": "tools/call",
            "params": {"name": "refund.create", "arguments": {"amt": 55}, "idempotency_key": "k-ref-1"},
        }
    )
    assert "error" in res1

    # Re-submitting same idempotency_key k-ref-1 hits state == REFUTED (-32011 at L410)
    res1_same = proxy.handle_json_rpc(
        {
            "method": "tools/call",
            "params": {"name": "refund.create", "arguments": {"amt": 55}, "idempotency_key": "k-ref-1"},
        }
    )
    assert res1_same["error"]["code"] == -(320 * 100 + 11)

    # 2nd call with different idempotency_key k-ref-2 but same CAID hits c_state == REFUTED (-32011 at L484)
    res2 = proxy.handle_json_rpc(
        {
            "method": "tools/call",
            "params": {"name": "refund.create", "arguments": {"amt": 55}, "idempotency_key": "k-ref-2"},
        }
    )
    assert res2["error"]["code"] == -(320 * 100 + 11)
    proxy.close()

    # Negative-control check for mcp-vec-001/002/010/018/019 (kills BOOL_SWAP on and -> or and except passed=False)
    suite_data = json.loads((REPO_ROOT / "conformance" / "vectors" / "mcp_idempotency.vectors.v1.json").read_text())
    neg_ids = {"mcp-vec-001", "mcp-vec-002", "mcp-vec-010", "mcp-vec-018", "mcp-vec-019"}
    neg_vecs = {"conformance_suite": "sub", "vectors": [v for v in suite_data["vectors"] if v["vector_id"] in neg_ids]}
    neg_file = tmp_path / "neg_vecs.json"
    neg_file.write_text(json.dumps(neg_vecs), encoding="utf-8")

    orig_proxy_cls = mcp_mod.HardenedIdempotentMcpProxy

    class _NegControlProxy(orig_proxy_cls):  # type: ignore[valid-type,misc]
        def handle_json_rpc(self, request_frame):
            if "mcp_mcp-vec-001.db" in self.db_path:
                raise RuntimeError("boom")
            if "mcp_mcp-vec-010.db" in self.db_path or "mcp_mcp-vec-018.db" in self.db_path:
                return {"error": {"code": -1, "message": "WRONG_MSG"}}
            if "mcp_mcp-vec-019.db" in self.db_path:
                return {"result": {"state": "WRONG_STATE"}}
            res = super().handle_json_rpc(request_frame)
            if isinstance(res, dict) and "meta" in res:
                res["meta"]["replay"] = False
            return res

    try:
        mcp_mod.HardenedIdempotentMcpProxy = _NegControlProxy
        rep_neg = run_conformance_suite_vectors(neg_file, db_dir=tmp_path)
    finally:
        mcp_mod.HardenedIdempotentMcpProxy = orig_proxy_cls
    assert rep_neg["passed"] == 0

    # Test main() missing vectors_path (returns 1) and normal execution (indent=2)
    orig_root = mcp_mod.REPO_ROOT
    try:
        mcp_mod.REPO_ROOT = tmp_path / "nonexistent_repo"
        rc_fail = mcp_mod.main()
        assert rc_fail == 1 and isinstance(rc_fail, int)
    finally:
        mcp_mod.REPO_ROOT = orig_root

    rc_ok = mcp_mod.main()
    assert rc_ok == 0
    report_txt = (REPO_ROOT / "output" / "mcp-conformance-report.json").read_text(encoding="utf-8")
    assert '\n  "' in report_txt
    assert '\n   "' not in report_txt


def test_idempotent_mcp_proxy_caid_content_addressing_and_tool_isolation():
    """Verifies that semantically identical payloads produce identical CAID, while distinct tools do not collide."""
    proxy = HardenedIdempotentMcpProxy(upstream_transport_fn=lambda r: {"result": "ok"})

    args_1 = {"amount_minor": 15000, "recipient": "iban:FR761234"}
    args_2 = {"recipient": "iban:FR761234", "amount_minor": 15000}

    caid_1 = proxy.compute_caid(args_1, tool_name="refund.create")
    caid_2 = proxy.compute_caid(args_2, tool_name="refund.create")
    caid_other_tool = proxy.compute_caid(args_1, tool_name="payment.send")

    assert caid_1 == caid_2
    assert caid_1.startswith("sha256:")
    assert caid_1 != caid_other_tool  # Distinct tools produce distinct CAIDs
    proxy.close()


def test_idempotent_mcp_proxy_blind_retry_blocked_under_indeterminate(tmp_path: Path):
    """Verifies that an uncertain in-flight or timed-out call blocks blind retries."""
    call_count = [0]
    db_file = tmp_path / "indeterminate_test.db"

    def simulated_upstream(req: dict) -> dict:
        call_count[0] += 1
        raise TimeoutError("Simulated 504 Gateway Timeout")

    proxy = HardenedIdempotentMcpProxy(upstream_transport_fn=simulated_upstream, db_path=db_file)

    # First call: Times out
    req = {
        "method": "tools/call",
        "params": {
            "name": "refund.create",
            "arguments": {"amount_minor": 10000},
            "idempotency_key": "k-retry-test",
        },
    }
    res1 = proxy.handle_json_rpc(req)
    assert "error" in res1
    assert "ERR_EFFECT_INDETERMINATE_LATCHED" in res1["error"]["message"]

    # Second call (blind retry): Blocked without hitting upstream
    res2 = proxy.handle_json_rpc(req)
    assert "error" in res2
    assert "HALT_BLIND_RETRY_PROHIBITED_UNDER_UNCERTAINTY" in res2["error"]["message"]
    assert call_count[0] == 1  # Upstream was not called a second time
    proxy.close()


def test_idempotent_mcp_proxy_reconciliation_cycle(tmp_path: Path):
    """Verifies the reconciliation loop: timeout -> indeterminate -> tools/status probe -> confirmed."""
    server_state = ["PENDING"]
    db_file = tmp_path / "recon_cycle.db"

    def simulated_upstream(req: dict) -> dict:
        method = req.get("method")
        if method == "tools/call":
            raise TimeoutError("Dropped wire connection")
        elif method == "tools/status":
            return {"result": {"state": server_state[0]}}
        return {"error": {"code": -32601, "message": "Method not found"}}

    proxy = HardenedIdempotentMcpProxy(upstream_transport_fn=simulated_upstream, db_path=db_file)

    # 1. Dispatch times out
    call_req = {
        "method": "tools/call",
        "params": {
            "name": "refund.create",
            "arguments": {"amount_minor": 10000},
            "idempotency_key": "k-recon-01",
        },
    }
    res_call = proxy.handle_json_rpc(call_req)
    assert int(res_call["error"]["code"]) == -32504

    # 2. Server settles the transaction out-of-band
    server_state[0] = "CONFIRMED"

    # 3. Probe tools/status
    probe_req = {
        "method": "tools/status",
        "params": {"idempotency_key": "k-recon-01"},
    }
    res_probe = proxy.handle_json_rpc(probe_req)
    assert res_probe["result"]["state"] == "CONFIRMED"

    # 4. Subsequent tools/call returns cached result
    res_replay = proxy.handle_json_rpc(call_req)
    assert "result" in res_replay
    assert res_replay.get("meta", {}).get("replay") is True
    proxy.close()


def test_idempotent_mcp_proxy_sqlite_wal_persistence_and_recovery(tmp_path: Path):
    """Verifies SQLite WAL persistence across proxy reboots."""
    db_file = tmp_path / "persisted_mcp.db"

    def simulated_upstream(req: dict) -> dict:
        return {"result": {"status": "DISPATCHED_AND_COMMITTED"}}

    # Create proxy instance 1, execute call
    proxy_1 = HardenedIdempotentMcpProxy(
        upstream_transport_fn=simulated_upstream,
        db_path=db_file,
    )
    req = {
        "method": "tools/call",
        "params": {
            "name": "wire.disburse",
            "arguments": {"amount_minor": 50000},
            "idempotency_key": "k-wal-persisted",
        },
    }
    res_1 = proxy_1.handle_json_rpc(req)
    assert "result" in res_1
    proxy_1.close()

    # Boot proxy instance 2 pointing to the same SQLite WAL database
    proxy_2 = HardenedIdempotentMcpProxy(
        upstream_transport_fn=lambda r: {"error": "SHOULD_NOT_EXECUTE"},
        db_path=db_file,
    )

    # Query status from new proxy
    status_req = {
        "method": "tools/status",
        "params": {"idempotency_key": "k-wal-persisted"},
    }
    res_status = proxy_2.handle_json_rpc(status_req)
    assert res_status["result"]["state"] == "CONFIRMED"

    # Replay returns cached result without hitting upstream
    res_2 = proxy_2.handle_json_rpc(req)
    assert "result" in res_2
    assert res_2.get("meta", {}).get("replay") is True
    proxy_2.close()


def test_idempotent_mcp_proxy_thundering_herd_concurrency(tmp_path: Path):
    """Fires 20 parallel threads on the same key; verifies SQLite lock serializes and only 1 reaches upstream."""
    db_file = tmp_path / "thundering_herd.db"
    upstream_calls = [0]

    def slow_upstream(req: dict) -> dict:
        upstream_calls[0] += 1
        time.sleep(0.02)  # simulate network roundtrip
        return {"result": {"status": "SUCCESS"}}

    proxy = HardenedIdempotentMcpProxy(upstream_transport_fn=slow_upstream, db_path=db_file)

    def worker():
        return proxy.handle_json_rpc(
            {
                "method": "tools/call",
                "params": {
                    "name": "payment.send",
                    "arguments": {"amount": 5000},
                    "idempotency_key": "k-thunder-shared",
                },
            }
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(worker) for _ in range(20)]
        results = [f.result() for f in futures]

    assert upstream_calls[0] == 1  # Exactly 1 reached upstream!
    assert len(results) == 20
    proxy.close()


def test_idempotent_mcp_proxy_error_code_boundaries(tmp_path: Path):
    """Verifies that 4xx errors mark REFUTED, while 5xx errors remain EFFECT_INDETERMINATE."""
    db_file = tmp_path / "error_boundaries.db"

    def client_error_upstream(req: dict) -> dict:
        return {"error": {"code": 400, "message": "Bad Request: negative amount"}}

    def server_error_upstream(req: dict) -> dict:
        return {"error": {"code": 500, "message": "Internal Server Error"}}

    proxy_client = HardenedIdempotentMcpProxy(upstream_transport_fn=client_error_upstream, db_path=db_file)
    res_client = proxy_client.handle_json_rpc(
        {
            "method": "tools/call",
            "params": {"name": "test.act", "arguments": {}, "idempotency_key": "k-400"},
        }
    )
    row_400 = proxy_client.conn.execute("SELECT state FROM mcp_idempotency WHERE idem_key = 'k-400';").fetchone()
    assert row_400[0] == "REFUTED"
    proxy_client.close()

    db_file_500 = tmp_path / "error_500.db"
    proxy_server = HardenedIdempotentMcpProxy(upstream_transport_fn=server_error_upstream, db_path=db_file_500)
    res_server = proxy_server.handle_json_rpc(
        {
            "method": "tools/call",
            "params": {"name": "test.act", "arguments": {}, "idempotency_key": "k-500"},
        }
    )
    row_500 = proxy_server.conn.execute("SELECT state FROM mcp_idempotency WHERE idem_key = 'k-500';").fetchone()
    assert row_500[0] == "EFFECT_INDETERMINATE"
    proxy_server.close()


def test_idempotent_mcp_proxy_tool_level_is_error_indeterminate(tmp_path: Path):
    """Verifies that tool-level isError: true inside 200 does not mark CONFIRMED and routes to uncertainty latch."""
    db_file = tmp_path / "tool_error.db"

    def tool_error_upstream(req: dict) -> dict:
        return {
            "result": {
                "isError": True,
                "content": [{"type": "text", "text": "Temporary backend lock; lock unavailable"}],
            }
        }

    proxy = HardenedIdempotentMcpProxy(upstream_transport_fn=tool_error_upstream, db_path=db_file)
    res = proxy.handle_json_rpc(
        {
            "method": "tools/call",
            "params": {
                "name": "refund.create",
                "arguments": {"amount": 2500},
                "idempotency_key": "k-tool-err",
            },
        }
    )
    assert "error" in res
    assert res["error"]["code"] == -(320 * 100 + 21)
    assert res["error"]["message"] == "TOOL_ERROR_REQUIRES_RECONCILIATION"
    row = proxy.conn.execute("SELECT state FROM mcp_idempotency WHERE idem_key = 'k-tool-err';").fetchone()
    assert row[0] == "EFFECT_INDETERMINATE"  # Must NOT be CONFIRMED!
    proxy.close()


def test_idempotent_mcp_proxy_caid_vs_operation_identity_conflict(tmp_path: Path):
    """Verifies that identical CAID with different explicit operation_id triggers conflict escalation."""
    db_file = tmp_path / "conflict.db"

    def timeout_upstream(req: dict) -> dict:
        raise TimeoutError("Wire drop")

    proxy = HardenedIdempotentMcpProxy(upstream_transport_fn=timeout_upstream, db_path=db_file)

    # Op 1: times out
    res1 = proxy.handle_json_rpc(
        {
            "method": "tools/call",
            "params": {
                "name": "refund.create",
                "arguments": {"amount": 5000},
                "idempotency_key": "k-first",
                "operation_id": "op-alpha",
            },
        }
    )
    assert "error" in res1

    # Op 2: same tool and arguments, but distinct operation_id
    res2 = proxy.handle_json_rpc(
        {
            "method": "tools/call",
            "params": {
                "name": "refund.create",
                "arguments": {"amount": 5000},
                "idempotency_key": "k-second",
                "operation_id": "op-beta",
            },
        }
    )
    assert "error" in res2
    assert "HALT_CAID_OPERATION_IDENTITY_CONFLICT" in res2["error"]["message"]
    proxy.close()


def test_idempotent_mcp_proxy_ttl_preserves_indeterminate_and_escalates(tmp_path: Path):
    """Verifies that TTL expiration never erases indeterminate records; it escalates them to UNRESOLVED_ESCALATED."""
    db_file = tmp_path / "ttl_escalate.db"
    proxy = HardenedIdempotentMcpProxy(upstream_transport_fn=lambda r: {"result": "ok"}, db_path=db_file, ttl_sec=10)

    # Insert an indeterminate record created 100 seconds ago
    old_time = time.time() - 100
    proxy.conn.execute(
        """
        INSERT INTO mcp_idempotency 
        (idem_key, tenant_id, principal, operation_id, tool_name, caid, state, policy_epoch, created_at, uncertainty_resolution_deadline)
        VALUES ('k-old-indet', 'default_tenant', 'default_principal', 'op-old', 'refund.create', 'sha256:old', 'EFFECT_INDETERMINATE', 'epoch-2026-Q4', ?, ?);
        """,
        (old_time, old_time + 10),
    )

    # Call with same key triggers eviction check
    res = proxy.handle_json_rpc(
        {
            "method": "tools/call",
            "params": {
                "name": "refund.create",
                "arguments": {},
                "idempotency_key": "k-old-indet",
                "caid": "sha256:old",
            },
        }
    )
    assert "error" in res
    assert "OPERATION_UNRESOLVED_REQUIRES_RECONCILIATION" in res["error"]["message"]

    # Verify record still exists in database and is escalated
    row = proxy.conn.execute("SELECT state FROM mcp_idempotency WHERE idem_key = 'k-old-indet';").fetchone()
    assert row is not None
    assert row[0] == "UNRESOLVED_ESCALATED"
    proxy.close()


def test_idempotent_mcp_proxy_ambiguous_http_codes_408_429(tmp_path: Path):
    """Verifies that HTTP 408 (Request Timeout) and 429 (Rate Limited) are classified as EFFECT_INDETERMINATE."""
    db_file = tmp_path / "ambiguous_http.db"

    responses = [{"error": {"code": 408, "message": "Request Timeout"}}]

    def dynamic_upstream(req: dict) -> dict:
        return responses[0]

    proxy = HardenedIdempotentMcpProxy(upstream_transport_fn=dynamic_upstream, db_path=db_file)

    # Test 408
    proxy.handle_json_rpc(
        {
            "method": "tools/call",
            "params": {"name": "test.act", "arguments": {"code": 408}, "idempotency_key": "k-408"},
        }
    )
    row_408 = proxy.conn.execute("SELECT state FROM mcp_idempotency WHERE idem_key = 'k-408';").fetchone()
    assert row_408[0] == "EFFECT_INDETERMINATE"

    # Test 429
    responses[0] = {"error": {"code": 429, "message": "Too Many Requests"}}
    proxy.handle_json_rpc(
        {
            "method": "tools/call",
            "params": {"name": "test.act", "arguments": {"code": 429}, "idempotency_key": "k-429"},
        }
    )
    row_429 = proxy.conn.execute("SELECT state FROM mcp_idempotency WHERE idem_key = 'k-429';").fetchone()
    assert row_429[0] == "EFFECT_INDETERMINATE"
    proxy.close()


def test_idempotent_mcp_proxy_epoch_rotation_preserves_indeterminate(tmp_path: Path):
    """Verifies that rotating policy epoch does not silently erase indeterminate records."""
    db_file = tmp_path / "epoch_preserves.db"
    proxy = HardenedIdempotentMcpProxy(
        upstream_transport_fn=lambda r: {"error": "SHOULD_NOT_EXECUTE"},
        db_path=db_file,
    )

    # Latch an indeterminate under old epoch
    proxy.conn.execute(
        """
        INSERT INTO mcp_idempotency 
        (idem_key, tenant_id, principal, operation_id, tool_name, caid, state, policy_epoch, created_at, uncertainty_resolution_deadline)
        VALUES ('k-epoch-test', 'default_tenant', 'default_principal', 'op-ep', 'refund.create', 'sha256:epoch_caid', 'EFFECT_INDETERMINATE', 'epoch-2026-Q3', ?, ?);
        """,
        (time.time(), time.time() + 300),
    )

    # New request with new epoch must NOT erase the record
    res = proxy.handle_json_rpc(
        {
            "method": "tools/call",
            "params": {
                "name": "refund.create",
                "arguments": {},
                "idempotency_key": "k-epoch-test",
                "caid": "sha256:epoch_caid",
                "policy_epoch": "epoch-2026-Q4",
            },
        }
    )
    assert "error" in res
    assert "HALT_BLIND_RETRY_PROHIBITED_UNDER_UNCERTAINTY" in res["error"]["message"]

    # Record still in database
    row = proxy.conn.execute("SELECT state FROM mcp_idempotency WHERE idem_key = 'k-epoch-test';").fetchone()
    assert row[0] == "EFFECT_INDETERMINATE"
    proxy.close()


def test_idempotent_mcp_proxy_storage_io_failure_fails_closed():
    """Verifies that SQLite write errors fail closed without dispatching upstream."""
    upstream_called = [False]

    def upstream(req: dict) -> dict:
        upstream_called[0] = True
        return {"result": "ok"}

    proxy = HardenedIdempotentMcpProxy(upstream_transport_fn=upstream, db_path=":memory:")
    # Break SQLite connection
    proxy.conn.close()

    res = proxy.handle_json_rpc(
        {
            "method": "tools/call",
            "params": {"name": "refund.create", "arguments": {}, "idempotency_key": "k-io-fail"},
        }
    )
    assert "error" in res
    assert "HALT_STORAGE_IO_FAILURE_FAILED_CLOSED" in res["error"]["message"]
    assert upstream_called[0] is False  # Upstream NEVER called


def test_idempotent_mcp_proxy_capability_expiration_blocks_dispatch():
    """Verifies that expired capability tokens fail closed without upstream dispatch."""
    upstream_called = [False]

    def upstream(req: dict) -> dict:
        upstream_called[0] = True
        return {"result": "ok"}

    proxy = HardenedIdempotentMcpProxy(upstream_transport_fn=upstream, db_path=":memory:")
    res = proxy.handle_json_rpc(
        {
            "method": "tools/call",
            "params": {
                "name": "refund.create",
                "arguments": {},
                "idempotency_key": "k-expired",
                "expires_at": 100,  # Far in the past
            },
        }
    )
    assert "error" in res
    assert "HALT_CAPABILITY_EXPIRED" in res["error"]["message"]
    assert upstream_called[0] is False
    proxy.close()


def test_idempotent_mcp_proxy_cli_execution():
    """Verifies CLI execution of adapters/mcp/idempotent_mcp_proxy.py."""
    cmd = [sys.executable, str(REPO_ROOT / "adapters" / "mcp" / "idempotent_mcp_proxy.py")]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0
    assert "Pass Rate:       100.0%" in proc.stdout
    assert "Total Vectors:   30" in proc.stdout
    assert "Passed:          30" in proc.stdout


def test_epistemic_purity():
    """Scans adapters/mcp/idempotent_mcp_proxy.py and this test file for banned words."""
    banned = [
        "guaran" + "teed",
        "guaran" + "tee",
        "proven universal" + "ly",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "unassail" + "able",
        "immu" + "ne",
        "unhack" + "able",
    ]
    files_to_check = [
        REPO_ROOT / "adapters" / "mcp" / "idempotent_mcp_proxy.py",
        REPO_ROOT / "tests" / "test_idempotent_mcp_proxy.py",
    ]
    for fpath in files_to_check:
        content = fpath.read_text(encoding="utf-8").lower()
        for b in banned:
            assert b not in content, f"Banned word '{b}' found in {fpath.name}"


# ---------------------------------------------------------------------------
# Behavioural coverage added for mutation adequacy (real SQLite, real vector
# files written to tmp_path; no test doubles).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status, payload, expected", [
    (-32600, {}, "REFUTED"), (-32601, {}, "REFUTED"), (-32602, {}, "REFUTED"),
    (-32700, {}, "REFUTED"), (400, {}, "REFUTED"), (404, {}, "REFUTED"),
    (422, {}, "REFUTED"), (418, {}, "REFUTED"),
    (-32000, {}, "EFFECT_INDETERMINATE"), (500, {}, "EFFECT_INDETERMINATE"),
    (408, {}, "EFFECT_INDETERMINATE"), (425, {}, "EFFECT_INDETERMINATE"),
    (429, {}, "EFFECT_INDETERMINATE"),
    (200, {"isError": True}, "EFFECT_INDETERMINATE"),
    (200, {"isError": "true"}, "CONFIRMED"), (200, {}, "CONFIRMED"),
])
def test_classify_upstream_response_table(status, payload, expected):
    proxy = HardenedIdempotentMcpProxy(upstream_transport_fn=lambda r: {"result": {}})
    try:
        assert proxy._classify_upstream_response(status, payload)[0] == expected
    finally:
        proxy.close()


def _call(key, args=None, **extra):
    params = {"name": "refund.create", "arguments": args or {"amount_minor": 1}, "idempotency_key": key}
    params.update(extra)
    return {"jsonrpc": "2.0", "method": "tools/call", "params": params}


def test_refuted_operation_is_not_retried_by_key_or_by_intent():
    calls = []

    def upstream(req):
        calls.append(req)
        return {"jsonrpc": "2.0", "error": {"code": 400, "message": "Bad Request"}}

    proxy = HardenedIdempotentMcpProxy(upstream_transport_fn=upstream)
    try:
        first = proxy.handle_json_rpc(_call("k-r1"))
        assert first["error"]["code"] == 400
        by_key = proxy.handle_json_rpc(_call("k-r1"))
        assert by_key["error"] == {"code": -32011, "message": "OPERATION_PREVIOUSLY_REFUTED",
                                   "data": {"state": "REFUTED", "idempotency_key": "k-r1"}}
        by_intent = proxy.handle_json_rpc(_call("k-r2"))
        assert by_intent["error"]["code"] == -32011
        assert by_intent["error"]["data"]["idempotency_key"] == "k-r1"
        assert len(calls) == 1
    finally:
        proxy.close()


def test_tool_level_is_error_latches_indeterminate_with_typed_error():
    proxy = HardenedIdempotentMcpProxy(
        upstream_transport_fn=lambda r: {"jsonrpc": "2.0", "result": {"isError": True, "content": []}})
    try:
        resp = proxy.handle_json_rpc(_call("k-e1"))
        assert resp["error"]["code"] == -32021
        assert resp["error"]["message"] == "TOOL_ERROR_REQUIRES_RECONCILIATION"
        assert resp["error"]["data"]["state"] == "EFFECT_INDETERMINATE"
        assert resp["error"]["data"]["tool_result"] == {"isError": True, "content": []}
        retry = proxy.handle_json_rpc(_call("k-e1"))
        assert retry["error"]["code"] == -32009
    finally:
        proxy.close()


def _run_vectors(tmp_path: Path, vectors):
    path = tmp_path / "vectors.json"
    path.write_text(json.dumps({"conformance_suite": "crafted", "vectors": vectors}), encoding="utf-8")
    return run_conformance_suite_vectors(path, db_dir=tmp_path / "dbs")


def test_conformance_runner_reports_exceptions_as_failures(tmp_path: Path):
    report = _run_vectors(tmp_path, [{"vector_id": "mcp-vec-001", "name": "missing_input"}])
    assert report["suite"] == "crafted"
    assert (report["total"], report["passed"], report["failed"]) == (1, 0, 1)
    assert report["results"][0] == {"vector_id": "mcp-vec-001", "name": "missing_input",
                                    "passed": False, "reason": "'input'"}
    assert report["pass_rate_pct"] == 0.0


def test_conformance_runner_uses_per_step_upstream_behaviour(tmp_path: Path):
    seq = [dict(_call("k-seq"), simulate_upstream="NORMAL_200"),
           dict(_call("k-seq"), simulate_upstream="TIMEOUT")]
    report = _run_vectors(tmp_path, [{"vector_id": "mcp-vec-002", "name": "steps", "sequence": seq}])
    assert report["results"][0]["passed"] is True
    flipped = [dict(seq[0], simulate_upstream="TIMEOUT"), seq[1]]
    report2 = _run_vectors(tmp_path, [{"vector_id": "mcp-vec-002", "name": "steps", "sequence": flipped}])
    assert report2["results"][0]["passed"] is False


def test_conformance_runner_checks_exact_error_and_state(tmp_path: Path):
    expired = {"method": "tools/call", "params": {"name": "x", "idempotency_key": "k", "expires_at": 1}}
    call_ok = _call("k-019")
    wrong_payload = {"method": "tools/call",
                     "params": {"name": "refund.create", "idempotency_key": "k-010", "caid": "sha256:other"}}
    same_payload = {"method": "tools/call",
                    "params": {"name": "refund.create", "idempotency_key": "k-010", "caid": "sha256:1010"}}
    report = _run_vectors(tmp_path, [
        {"vector_id": "mcp-vec-018", "name": "expired_not_invalid_params", "input": expired},
        {"vector_id": "mcp-vec-019", "name": "result_without_state", "input": call_ok},
        {"vector_id": "mcp-vec-010", "name": "reboot_other_payload", "input": wrong_payload},
        {"vector_id": "mcp-vec-010", "name": "reboot_same_payload", "input": same_payload},
    ])
    assert [r["passed"] for r in report["results"]] == [False, False, False, True]


# ---------------------------------------------------------------------------
# Effect-key CAID + settle-before-retry (ACRFence regenerated retry, arXiv:2603.20625)
# ---------------------------------------------------------------------------

import hashlib  # noqa: E402
import threading  # noqa: E402

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from adapters.mcp.idempotent_mcp_proxy import (  # noqa: E402
    PROBE_APPLIED,
    PROBE_NOT_APPLIED,
    PROBE_UNKNOWN,
    SETTLEMENT_RECEIPT_TYPE,
    STATE_SUPERSEDED_NOT_APPLIED,
    verify_settlement_receipt,
)
from src.eo1_effect_key import (  # noqa: E402
    EffectClass,
    EffectKeySchema,
    EffectKeySchemaRegistry,
    IdentityField,
    bind_effect_key,
)

PAY_TOOL = "payments.transfer"


def _pay_registry() -> EffectKeySchemaRegistry:
    return EffectKeySchemaRegistry([EffectKeySchema(
        tool=PAY_TOOL, schema_id="payments.transfer.effect", schema_version="1",
        effect_class=EffectClass.IRREVERSIBLE,
        identity_fields=(IdentityField("recipient", "casefold_nfc"), IdentityField("amount_minor", "minor_units"),
                         IdentityField("currency", "currency_iso4217"), IdentityField("business_ref", "exact_nfc")),
    )])


def _pay_args(memo: str = "Invoice 42", client_request_id: str = "uuid-original") -> dict:
    return {"recipient": "acct-7781", "amount_minor": 125000, "currency": "EUR", "business_ref": "INV-42",
            "memo": memo, "client_request_id": client_request_id}


def _pay_call(key, args) -> dict:
    params = {"name": PAY_TOOL, "arguments": args}
    if key is not None:
        params["idempotency_key"] = key
    return {"jsonrpc": "2.0", "method": "tools/call", "params": params}


class _EffectTarget:
    """
    In-process upstream that commits effects into a ledger keyed by the forwarded CAID.
    first_call: "commit_then_timeout" (ack lost after commit) or "timeout_before_commit".
    read_back(): APPLIED / NOT_APPLIED from that ledger, or UNKNOWN when read-back is unavailable.
    """

    def __init__(self, first_call: str, readback_available: bool = True):
        self.first_call = first_call
        self.readback_available = readback_available
        self.calls: list = []
        self.effects: list = []
        self.probes: list = []
        self.hold = None  # threading.Event: when set, non-first calls block until released
        self.fences: dict = {}  # caid -> lowest attempt number the target still accepts
        self.refused_by_fence: list = []

    def fence(self, tool_name: str, caid: str, attempt_no: int) -> bool:
        """Target-side fence: from now on refuse attempts of this effect below attempt_no."""
        self.fences[caid] = max(attempt_no, self.fences.get(caid, 0))
        return True

    def transport(self, req: dict) -> dict:
        if req.get("method") != "tools/call":
            return {"error": {"code": -32601, "message": "Method not found"}}
        params = req["params"]
        self.calls.append(params)
        if len(self.calls) == 1 and self.first_call == "timeout_before_commit":
            raise TimeoutError("upstream timed out before commit")
        if self.hold is not None and len(self.calls) > 1:
            self.hold.wait(timeout=10)
        attempt = params.get("_meta", {}).get("aeib_attempt_no", 0)
        if attempt < self.fences.get(params.get("caid"), 0):
            self.refused_by_fence.append(attempt)
            return {"jsonrpc": "2.0", "error": {"code": 409, "message": "attempt fenced"}}
        self.effects.append(params.get("caid"))
        if len(self.calls) == 1 and self.first_call == "commit_then_timeout":
            raise TimeoutError("upstream committed, acknowledgement lost")
        return {"jsonrpc": "2.0", "result": {"status": "SUCCESS", "effect_no": len(self.effects)}}

    def read_back(self, tool_name: str, caid: str, arguments: dict) -> str:
        self.probes.append((tool_name, caid, dict(arguments)))
        if not self.readback_available:
            return PROBE_UNKNOWN
        return PROBE_APPLIED if caid in self.effects else PROBE_NOT_APPLIED


def _row(proxy, key):
    return proxy.conn.execute(
        "SELECT state, caid, raw_payload_digest, settlement_receipt FROM mcp_idempotency WHERE idem_key = ?;",
        (key,)).fetchone()


def _ek_proxy(target, probe=True, **kw):
    return HardenedIdempotentMcpProxy(
        upstream_transport_fn=target.transport, effect_key_registry=_pay_registry(),
        reconcile_probe_fn=target.read_back if probe else None, **kw)


def _first_attempt_latches(proxy, target):
    first = proxy.handle_json_rpc(_pay_call("idem-uuid-1", _pay_args()))
    assert first["error"]["code"] == -32504
    state, caid, raw, receipt = _row(proxy, "idem-uuid-1")
    binding = bind_effect_key(PAY_TOOL, _pay_args(), _pay_registry())
    assert (state, caid, raw, receipt) == ("EFFECT_INDETERMINATE", binding.effect_caid, binding.raw_payload_digest,
                                           None)
    assert target.calls[0]["caid"] == binding.effect_caid  # forwarded for target-side read-back
    return binding


REGEN_ARGS = _pay_args(memo="Re-sending payment for invoice 42", client_request_id="uuid-regenerated")


def test_case_a_regenerated_retry_applied_blocks_duplicate():
    target = _EffectTarget("commit_then_timeout")
    proxy = _ek_proxy(target)
    try:
        b1 = _first_attempt_latches(proxy, target)
        b2 = bind_effect_key(PAY_TOOL, REGEN_ARGS, _pay_registry())
        retry = proxy.handle_json_rpc(_pay_call("idem-uuid-2", REGEN_ARGS))
        err = retry["error"]
        assert err["code"] == -32012
        assert err["message"] == "OPERATION_RECONCILED_CONFIRMED_DUPLICATE_BLOCKED"
        assert err["data"]["effect_caid"] == b1.effect_caid == b2.effect_caid
        assert err["data"]["raw_payload_digest"] == b1.raw_payload_digest
        assert err["data"]["retry_raw_payload_digest"] == b2.raw_payload_digest != b1.raw_payload_digest
        assert err["data"]["reconciled_state"] == "CONFIRMED"
        assert err["data"]["existing_idempotency_key"] == "idem-uuid-1"
        assert len(target.calls) == 1 and len(target.effects) == 1  # 0 duplicates
        assert target.probes == [(PAY_TOOL, b1.effect_caid, REGEN_ARGS)]
        state, _, raw, receipt_json = _row(proxy, "idem-uuid-1")
        assert state == "CONFIRMED" and raw == b1.raw_payload_digest
        receipt = json.loads(receipt_json)
        assert receipt == err["data"]["settlement_receipt"]
        assert receipt["settled_state"] == "CONFIRMED" and receipt["probe_outcome"] == PROBE_APPLIED
        assert (receipt["settlement_basis"], receipt["settled_attempt_no"], receipt["next_attempt_no"]) == (
            "read_back_applied", 1, 0)
        assert receipt["receipt_type"] == SETTLEMENT_RECEIPT_TYPE
        assert receipt["raw_payload_digest"] == b1.raw_payload_digest
        assert verify_settlement_receipt(receipt, proxy.receipt_public_key()) is True
        assert _row(proxy, "idem-uuid-2") is None
        # A further regenerated retry replays the settled record; still no upstream call.
        again = proxy.handle_json_rpc(_pay_call("idem-uuid-3", _pay_args(memo="third wording")))
        assert again["meta"] == {"replay": True, "caid": b1.effect_caid}
        assert again["result"]["reconciled_state"] == "CONFIRMED"
        assert len(target.calls) == 1 and len(target.probes) == 1
    finally:
        proxy.close()


def test_case_b_regenerated_retry_not_applied_dispatches_once():
    """Wave 5: NOT_APPLIED unlocks the fresh attempt here because the target acked a fence."""
    target = _EffectTarget("timeout_before_commit")
    proxy = _ek_proxy(target, fence_probe_fn=target.fence)
    try:
        b1 = _first_attempt_latches(proxy, target)
        b2 = bind_effect_key(PAY_TOOL, REGEN_ARGS, _pay_registry())
        retry = proxy.handle_json_rpc(_pay_call("idem-uuid-2", REGEN_ARGS))
        assert retry["result"] == {"status": "SUCCESS", "effect_no": 1}
        assert len(target.calls) == 2 and len(target.effects) == 1
        assert target.effects == [b1.effect_caid]
        assert target.calls[1]["idempotency_key"] == "idem-uuid-2"
        old_state, _, old_raw, old_receipt = _row(proxy, "idem-uuid-1")
        assert old_state == STATE_SUPERSEDED_NOT_APPLIED and old_raw == b1.raw_payload_digest
        r = json.loads(old_receipt)
        assert r["settled_state"] == STATE_SUPERSEDED_NOT_APPLIED and r["probe_outcome"] == PROBE_NOT_APPLIED
        assert (r["settlement_basis"], r["settled_attempt_no"], r["next_attempt_no"]) == ("fence", 1, 2)
        assert target.fences == {b1.effect_caid: 2}
        assert [c["_meta"]["aeib_attempt_no"] for c in target.calls] == [1, 2]
        assert verify_settlement_receipt(r, proxy.receipt_public_key())
        new_state, new_caid, new_raw, new_receipt = _row(proxy, "idem-uuid-2")
        assert (new_state, new_caid, new_raw) == ("CONFIRMED", b1.effect_caid, b2.raw_payload_digest)
        assert json.loads(new_receipt) == r  # the settlement that authorised this attempt
        # Retrying with the superseded key resolves by intent: replay, no further dispatch.
        old_key_retry = proxy.handle_json_rpc(_pay_call("idem-uuid-1", _pay_args()))
        assert old_key_retry["meta"]["replay"] is True
        assert old_key_retry["result"] == {"status": "SUCCESS", "effect_no": 1}
        third = proxy.handle_json_rpc(_pay_call("idem-uuid-3", _pay_args(memo="x")))
        assert third["meta"]["replay"] is True
        assert len(target.calls) == 2 and len(target.effects) == 1
    finally:
        proxy.close()


def test_case_c_unknown_or_failing_probe_keeps_latch():
    target = _EffectTarget("commit_then_timeout", readback_available=False)
    proxy = _ek_proxy(target)
    try:
        b1 = _first_attempt_latches(proxy, target)
        retry = proxy.handle_json_rpc(_pay_call("idem-uuid-2", REGEN_ARGS))
        err = retry["error"]
        assert err["code"] == -32009 and err["message"] == "EXECUTION_HALTED_INDETERMINATE_LATCH"
        assert err["data"] == {"state": "EFFECT_INDETERMINATE", "idempotency_key": "idem-uuid-1",
                               "caid": b1.effect_caid, "probe_outcome": PROBE_UNKNOWN, "probe_detail": "probe_answer"}
        assert len(target.calls) == 1 and len(target.probes) == 1
        assert _row(proxy, "idem-uuid-1")[0] == "EFFECT_INDETERMINATE"
    finally:
        proxy.close()

    def raising_probe(tool, caid, args):
        raise ConnectionRefusedError("read-back endpoint down")

    for probe, detail in ((raising_probe, "probe_raised:ConnectionRefusedError"),
                          (lambda t, c, a: "applied", "probe_answer_unrecognised"),
                          (lambda t, c, a: True, "probe_answer_unrecognised"),
                          (lambda t, c, a: None, "probe_answer_unrecognised")):
        target = _EffectTarget("commit_then_timeout")
        proxy = HardenedIdempotentMcpProxy(upstream_transport_fn=target.transport,
                                           effect_key_registry=_pay_registry(), reconcile_probe_fn=probe)
        try:
            _first_attempt_latches(proxy, target)
            err = proxy.handle_json_rpc(_pay_call("idem-uuid-2", REGEN_ARGS))["error"]
            assert (err["code"], err["data"]["probe_outcome"], err["data"]["probe_detail"]) == (
                -32009, PROBE_UNKNOWN, detail)
            assert len(target.calls) == 1
            assert _row(proxy, "idem-uuid-1")[0] == "EFFECT_INDETERMINATE"
        finally:
            proxy.close()


def test_same_key_retry_settles_through_probe():
    for first_call, expected_calls, expected_code in (("commit_then_timeout", 1, -32012),
                                                      ("timeout_before_commit", 2, None)):
        target = _EffectTarget(first_call)
        proxy = _ek_proxy(target, fence_probe_fn=target.fence)
        try:
            _first_attempt_latches(proxy, target)
            resp = proxy.handle_json_rpc(_pay_call("idem-uuid-1", REGEN_ARGS))
            if expected_code is None:
                assert resp["result"]["status"] == "SUCCESS"
                state, _, raw, receipt = _row(proxy, "idem-uuid-1")
                assert state == "CONFIRMED"
                assert raw == bind_effect_key(PAY_TOOL, REGEN_ARGS, _pay_registry()).raw_payload_digest
                assert json.loads(receipt)["settled_state"] == STATE_SUPERSEDED_NOT_APPLIED
            else:
                assert resp["error"]["code"] == expected_code
                assert _row(proxy, "idem-uuid-1")[0] == "CONFIRMED"
            assert len(target.calls) == expected_calls and len(target.effects) == 1
        finally:
            proxy.close()


def test_effect_key_schema_rejections_fail_closed():
    target = _EffectTarget("commit_then_timeout")
    proxy = _ek_proxy(target)
    try:
        cases = [
            ({"name": "unknown.tool", "idempotency_key": "k1", "arguments": _pay_args()}, "UnknownToolSchemaError"),
            ({"name": PAY_TOOL, "idempotency_key": "k2",
              "arguments": {k: v for k, v in _pay_args().items() if k != "business_ref"}}, "MissingIdentityFieldError"),
            ({"name": PAY_TOOL, "idempotency_key": "k3", "arguments": {**_pay_args(), "amount_minor": 1250.0}},
             "InvalidIdentityValueError"),
            ({"name": PAY_TOOL, "idempotency_key": "k4", "arguments": ["not", "an", "object"]},
             "InvalidIdentityValueError"),
        ]
        for params, reason in cases:
            resp = proxy.handle_json_rpc({"jsonrpc": "2.0", "method": "tools/call", "params": params})
            assert resp["error"]["code"] == -32095
            assert resp["error"]["message"] == "EFFECT_KEY_SCHEMA_REJECTED"
            assert resp["error"]["data"]["reason"] == reason
            assert resp["error"]["data"]["tool"] == params["name"]
            assert resp["error"]["data"]["detail"]
        assert target.calls == []
        assert proxy.conn.execute("SELECT COUNT(*) FROM mcp_idempotency;").fetchone()[0] == 0
    finally:
        proxy.close()


def test_without_effect_key_regenerated_retry_duplicates_negative_control():
    """Gap reproduced: full-payload CAID + new idempotency_key -> second upstream effect."""
    target = _EffectTarget("commit_then_timeout")
    proxy = HardenedIdempotentMcpProxy(upstream_transport_fn=target.transport, reconcile_probe_fn=target.read_back)
    try:
        assert proxy.handle_json_rpc(_pay_call("idem-uuid-1", _pay_args()))["error"]["code"] == -32504
        retry = proxy.handle_json_rpc(_pay_call("idem-uuid-2", REGEN_ARGS))
        assert retry["result"]["status"] == "SUCCESS"
        assert len(target.effects) == 2  # duplicate side effect
        assert target.probes == []  # nothing matched, so nothing was probed
        assert _row(proxy, "idem-uuid-1")[2] is None  # raw digest only stored in effect-key mode
    finally:
        proxy.close()


def test_effect_key_without_probe_blocks_with_existing_halt():
    target = _EffectTarget("commit_then_timeout")
    proxy = _ek_proxy(target, probe=False)
    try:
        b1 = _first_attempt_latches(proxy, target)
        err = proxy.handle_json_rpc(_pay_call("idem-uuid-2", REGEN_ARGS))["error"]
        assert err["code"] == -32009 and err["message"] == "HALT_BLIND_RETRY_PROHIBITED_UNDER_UNCERTAINTY"
        assert err["data"]["caid"] == b1.effect_caid and err["data"]["idempotency_key"] == "idem-uuid-1"
        assert len(target.calls) == 1
    finally:
        proxy.close()


def test_effect_key_derives_key_and_ignores_caller_caid():
    target = _EffectTarget("none")
    proxy = _ek_proxy(target)
    try:
        b1 = bind_effect_key(PAY_TOOL, _pay_args(), _pay_registry())
        call = _pay_call(None, _pay_args())
        call["params"]["caid"] = "sha256:attacker-chosen"
        first = proxy.handle_json_rpc(call)
        assert first["result"]["status"] == "SUCCESS"
        assert _row(proxy, f"effect:{b1.effect_caid}")[:2] == ("CONFIRMED", b1.effect_caid)
        assert target.calls[0]["caid"] == b1.effect_caid
        assert target.calls[0]["idempotency_key"] == f"effect:{b1.effect_caid}"
        replay = proxy.handle_json_rpc(_pay_call(None, REGEN_ARGS))
        assert replay["meta"] == {"replay": True, "caid": b1.effect_caid}
        assert len(target.calls) == 1
        # A genuinely different effect (other business reference) is dispatched.
        other = proxy.handle_json_rpc(_pay_call(None, {**_pay_args(), "business_ref": "INV-43"}))
        assert other["result"]["status"] == "SUCCESS" and len(target.calls) == 2
        # Same idempotency key reused for a different effect is still refused.
        reuse = proxy.handle_json_rpc(_pay_call(f"effect:{b1.effect_caid}", {**_pay_args(), "amount_minor": 1}))
        assert reuse["error"]["message"] == "IDEMPOTENCY_KEY_REUSE_WITH_DIFFERENT_PAYLOAD"
    finally:
        proxy.close()
    plain = HardenedIdempotentMcpProxy(upstream_transport_fn=_EffectTarget("none").transport)
    try:
        assert plain.handle_json_rpc(_pay_call(None, _pay_args()))["error"]["code"] == -32602
    finally:
        plain.close()


def test_in_flight_attempt_is_never_settled_by_probe():
    """Red-team: a concurrent regenerated retry must not probe (and supersede) an attempt still in flight."""
    target = _EffectTarget("timeout_before_commit")
    target.hold = threading.Event()
    proxy = _ek_proxy(target, fence_probe_fn=target.fence)
    try:
        _first_attempt_latches(proxy, target)
        results = {}
        t = threading.Thread(target=lambda: results.setdefault(
            "r1", proxy.handle_json_rpc(_pay_call("idem-uuid-2", REGEN_ARGS))))
        t.start()
        for _ in range(500):
            if len(target.calls) == 2:
                break
            time.sleep(0.01)
        assert len(target.calls) == 2  # retry 1 settled the first attempt NOT_APPLIED and is now in flight
        r2 = proxy.handle_json_rpc(_pay_call("idem-uuid-3", _pay_args(memo="third")))
        assert r2["error"]["code"] == -32009
        assert r2["error"]["data"]["probe_detail"] == "not_probed_attempt_in_flight"
        assert r2["error"]["data"]["idempotency_key"] == "idem-uuid-2"
        assert len(target.probes) == 1
        target.hold.set()
        t.join(timeout=10)
        assert results["r1"]["result"]["status"] == "SUCCESS"
        assert len(target.calls) == 2 and len(target.effects) == 1
        assert proxy._in_flight_keys == set()
    finally:
        target.hold.set()
        proxy.close()


def test_concurrent_regenerated_retries_settle_once():
    target = _EffectTarget("commit_then_timeout")
    proxy = _ek_proxy(target)
    try:
        _first_attempt_latches(proxy, target)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            outs = list(pool.map(lambda i: proxy.handle_json_rpc(
                _pay_call(f"idem-regen-{i}", _pay_args(memo=f"wording {i}", client_request_id=f"u{i}"))), range(8)))
        codes = [o["error"]["code"] if "error" in o else "replay" for o in outs]
        assert codes.count(-32012) == 1 and codes.count("replay") == 7
        assert len(target.calls) == 1 and len(target.probes) == 1
    finally:
        proxy.close()


def test_settlement_receipt_verification_rejects_tampering():
    target = _EffectTarget("commit_then_timeout")
    key = Ed25519PrivateKey.generate()
    proxy = _ek_proxy(target, receipt_signing_key=key)
    try:
        _first_attempt_latches(proxy, target)
        receipt = proxy.handle_json_rpc(_pay_call("idem-uuid-2", REGEN_ARGS))["error"]["data"]["settlement_receipt"]
        pub = key.public_key()
        assert proxy.receipt_public_key().public_bytes_raw() == pub.public_bytes_raw()
        assert verify_settlement_receipt(receipt, pub) is True
        assert verify_settlement_receipt(receipt, Ed25519PrivateKey.generate().public_key()) is False
        for field_name, value in (("settled_state", "NOT_APPLIED"), ("effect_caid", "0" * 64),
                                  ("settlement_basis", "fence"), ("settled_attempt_no", 9),
                                  ("raw_payload_digest", "f" * 64), ("settled_at_ms", 1),
                                  ("receipt_type", "OTHER"), ("signature_b64", "!!notbase64!!"),
                                  ("signature_b64", "AAAA")):
            assert verify_settlement_receipt({**receipt, field_name: value}, pub) is False, field_name
        forged_key = Ed25519PrivateKey.generate()
        forged = {**receipt, "signer_public_key_hex": forged_key.public_key().public_bytes_raw().hex()}
        assert verify_settlement_receipt(forged, pub) is False
        assert verify_settlement_receipt({k: v for k, v in receipt.items() if k != "probe_outcome"}, pub) is False
        assert verify_settlement_receipt(None, pub) is False
        assert verify_settlement_receipt(receipt, "not-a-key") is False
    finally:
        proxy.close()


def test_old_database_is_migrated_with_new_columns(tmp_path: Path):
    db = tmp_path / "old.db"
    conn = sqlite3.connect(db)
    conn.execute("""CREATE TABLE mcp_idempotency (idem_key TEXT PRIMARY KEY, tenant_id TEXT, principal TEXT,
                    operation_id TEXT, tool_name TEXT, caid TEXT, state TEXT, policy_epoch TEXT, created_at REAL,
                    uncertainty_resolution_deadline REAL, cached_response TEXT);""")
    conn.execute("INSERT INTO mcp_idempotency VALUES ('old-k', 'default_tenant', 'default_principal', 'old-k', "
                 "'refund.create', 'sha256:x', 'CONFIRMED', 'epoch-2026-Q4', ?, ?, '{\"ok\": 1}');",
                 (time.time(), time.time()))
    conn.commit()
    conn.close()
    proxy = HardenedIdempotentMcpProxy(upstream_transport_fn=lambda r: {"result": {"status": "SUCCESS"}}, db_path=db)
    try:
        cols = {r[1] for r in proxy.conn.execute("PRAGMA table_info(mcp_idempotency);")}
        assert {"raw_payload_digest", "settlement_receipt", "attempt_no", "not_after_ms"} <= cols
        replay = proxy.handle_json_rpc({"method": "tools/call", "params": {
            "name": "refund.create", "idempotency_key": "old-k", "caid": "sha256:x"}})
        assert replay["result"] == {"ok": 1} and replay["meta"]["replay"] is True
    finally:
        proxy.close()
    # Re-opening an already migrated database does not try to add the columns again.
    again = HardenedIdempotentMcpProxy(upstream_transport_fn=lambda r: {"result": {}}, db_path=db)
    again.close()


def test_superseded_records_are_purged_after_retention_ttl():
    target = _EffectTarget("timeout_before_commit")
    proxy = _ek_proxy(target, ttl_sec=1000, trust_not_applied_without_fence=True)
    try:
        _first_attempt_latches(proxy, target)
        proxy.handle_json_rpc(_pay_call("idem-uuid-2", REGEN_ARGS))
        assert _row(proxy, "idem-uuid-1")[0] == STATE_SUPERSEDED_NOT_APPLIED
        proxy._evict_stale_records(time.time() + 999)
        assert _row(proxy, "idem-uuid-1") is not None
        proxy._evict_stale_records(time.time() + 1001)
        assert _row(proxy, "idem-uuid-1") is None
    finally:
        proxy.close()


# ---------------------------------------------------------------------------
# Oracle gaps found by the mutation gate on pre-existing proxy code
# ---------------------------------------------------------------------------


def test_identity_key_uses_operation_id_or_caid_fallback():
    proxy = HardenedIdempotentMcpProxy(upstream_transport_fn=lambda r: {"result": {}})
    try:
        canon = b'{"a":1}'
        digest = hashlib.sha256(canon).hexdigest()
        assert proxy._compute_identity_key("t", "p", "op-1", "tool", canon) == f"t:p:op-1:tool:{digest}"
        assert proxy._compute_identity_key("t", "p", "", "tool", canon) == (
            f"t:p:caid_fallback_{digest[:16]}:tool:{digest}")
    finally:
        proxy.close()


def test_tools_status_with_non_object_params_is_invalid_params():
    proxy = HardenedIdempotentMcpProxy(upstream_transport_fn=lambda r: {"result": {}})
    try:
        for bad in (None, [], "k"):
            resp = proxy.handle_json_rpc({"jsonrpc": "2.0", "method": "tools/status", "params": bad})
            assert resp["error"] == {"code": -32602, "message": "Missing required idempotency_key"}
    finally:
        proxy.close()


def test_conformance_runner_top_level_remote_status_and_vec012_state(tmp_path: Path):
    call = {"method": "tools/call", "params": {"name": "refund.create", "arguments": {"amount_minor": 1},
                                               "idempotency_key": "k-026", "caid": "sha256:2626"},
            "simulate_upstream": "TIMEOUT"}
    status = {"method": "tools/status", "params": {"idempotency_key": "k-026"}}
    unknown = {"vector_id": "mcp-vec-026", "name": "top_unknown", "sequence": [call, status],
               "simulate_remote_status": {"state": "UNKNOWN"}}
    confirmed = dict(unknown, name="top_confirmed", simulate_remote_status={"state": "CONFIRMED"})
    ok_012 = {"method": "tools/call", "params": {"name": "refund.create", "arguments": {},
                                                 "idempotency_key": "k-012", "caid": "sha256:1212"}}
    report = _run_vectors(tmp_path, [
        unknown, confirmed,
        {"vector_id": "mcp-vec-012", "name": "settles_confirmed_not_indeterminate", "input": ok_012},
    ])
    assert [r["passed"] for r in report["results"]] == [True, False, False]


def test_main_can_run_twice_with_existing_output_dir():
    assert mcp_mod.main() == 0
    assert mcp_mod.main() == 0
    assert (mcp_mod.REPO_ROOT / "output" / "mcp-conformance-report.json").is_file()


# ---------------------------------------------------------------------------
# Wave 5: late-commit fail-closed (LIMBO arXiv:2609.29095 Prop. 1; MCP #3394 row C)
# ---------------------------------------------------------------------------


class _LateCommitTarget:
    """
    Real in-process target whose FIRST request is still in flight when the client times out:
    a worker thread commits it later (when release() is called). Later requests commit at once.
    The target enforces a fence (refuses attempt numbers below the fenced one) and a not-after
    deadline (refuses to execute after _meta.aeib_not_after_ms), both read from the forwarded _meta.
    """

    def __init__(self, fence_mode: str = "ack"):
        self.fence_mode = fence_mode
        self.lock = threading.Lock()
        self.calls: list = []
        self.effects: list = []
        self.refused: list = []
        self.fences: dict = {}
        self.fence_requests: list = []
        self._release = threading.Event()
        self._threads: list = []

    def _commit(self, caid, attempt, not_after_ms) -> bool:
        with self.lock:
            if attempt < self.fences.get(caid, 0):
                self.refused.append(("fence", attempt))
                return False
            if not_after_ms is not None and int(time.time() * 1000) > not_after_ms:
                self.refused.append(("deadline", attempt))
                return False
            self.effects.append((caid, attempt))
            return True

    def transport(self, req: dict) -> dict:
        params = req["params"]
        meta = params.get("_meta", {})
        args = (params.get("caid"), meta.get("aeib_attempt_no", 0), meta.get("aeib_not_after_ms"))
        with self.lock:
            self.calls.append(params)
            first = len(self.calls) == 1
        if first:
            worker = threading.Thread(target=lambda: (self._release.wait(timeout=10), self._commit(*args)))
            worker.start()
            self._threads.append(worker)
            raise TimeoutError("client timeout; request still in flight at the target")
        if self._commit(*args):
            return {"jsonrpc": "2.0", "result": {"status": "SUCCESS", "attempt": args[1]}}
        return {"jsonrpc": "2.0", "error": {"code": 409, "message": "refused by target"}}

    def read_back(self, tool_name: str, caid: str, arguments: dict) -> str:
        with self.lock:
            return PROBE_APPLIED if any(c == caid for c, _ in self.effects) else PROBE_NOT_APPLIED

    def fence(self, tool_name: str, caid: str, attempt_no: int):
        self.fence_requests.append((tool_name, caid, attempt_no))
        if self.fence_mode == "raise":
            raise OSError("fence endpoint unreachable")
        if self.fence_mode == "nack":
            return False
        if self.fence_mode == "truthy":
            return "yes"
        with self.lock:
            self.fences[caid] = max(attempt_no, self.fences.get(caid, 0))
        return True

    def release_late_commit(self) -> None:
        self._release.set()
        for t in self._threads:
            t.join(timeout=10)


def _late_proxy(target, **kw):
    return HardenedIdempotentMcpProxy(upstream_transport_fn=target.transport, effect_key_registry=_pay_registry(),
                                      reconcile_probe_fn=target.read_back, **kw)


def test_wave5_default_not_applied_is_blocked_unfenced():
    target = _LateCommitTarget()
    proxy = _late_proxy(target)
    try:
        assert proxy.handle_json_rpc(_pay_call("idem-1", _pay_args()))["error"]["code"] == -32504
        err = proxy.handle_json_rpc(_pay_call("idem-2", REGEN_ARGS))["error"]
        assert err["code"] == -32009 and err["message"] == "EXECUTION_HALTED_INDETERMINATE_LATCH"
        assert err["data"]["reason"] == "NOT_APPLIED_UNFENCED"
        assert err["data"]["probe_outcome"] == PROBE_NOT_APPLIED
        assert err["data"]["fence_detail"] == "no_fence_probe_configured"
        assert err["data"]["settled_attempt_no"] == 1
        assert len(target.calls) == 1
        assert _row(proxy, "idem-1")[0] == "EFFECT_INDETERMINATE" and _row(proxy, "idem-2") is None
        target.release_late_commit()  # the in-flight request commits late
        assert len(target.effects) == 1
        # Now the read-back sees the late commit: settled CONFIRMED, still one effect.
        assert proxy.handle_json_rpc(_pay_call("idem-3", REGEN_ARGS))["error"]["code"] == -32012
        assert len(target.calls) == 1 and len(target.effects) == 1
    finally:
        target.release_late_commit()
        proxy.close()


def test_wave5_unsafe_opt_in_with_late_commit_duplicates_negative_control():
    """Documents the risk: opting in to trust NOT_APPLIED without a fence duplicates on a late commit."""
    target = _LateCommitTarget()
    proxy = _late_proxy(target, trust_not_applied_without_fence=True)
    try:
        proxy.handle_json_rpc(_pay_call("idem-1", _pay_args()))
        retry = proxy.handle_json_rpc(_pay_call("idem-2", REGEN_ARGS))
        assert retry["result"] == {"status": "SUCCESS", "attempt": 2}
        target.release_late_commit()
        assert [a for _, a in target.effects] == [2, 1]  # duplicate side effect reproduced
        receipt = json.loads(_row(proxy, "idem-1")[3])
        assert receipt["settlement_basis"] == "unsafe_opt_in"
        assert verify_settlement_receipt(receipt, proxy.receipt_public_key())
    finally:
        target.release_late_commit()
        proxy.close()


def test_wave5_fence_acked_late_commit_refused_single_effect():
    target = _LateCommitTarget()
    proxy = _late_proxy(target, fence_probe_fn=target.fence)
    try:
        b = bind_effect_key(PAY_TOOL, _pay_args(), _pay_registry())
        proxy.handle_json_rpc(_pay_call("idem-1", _pay_args()))
        retry = proxy.handle_json_rpc(_pay_call("idem-2", REGEN_ARGS))
        assert retry["result"] == {"status": "SUCCESS", "attempt": 2}
        assert target.fence_requests == [(PAY_TOOL, b.effect_caid, 2)]
        target.release_late_commit()
        assert target.effects == [(b.effect_caid, 2)]
        assert target.refused == [("fence", 1)]
        receipt = json.loads(_row(proxy, "idem-1")[3])
        assert (receipt["settlement_basis"], receipt["settled_attempt_no"], receipt["next_attempt_no"]) == (
            "fence", 1, 2)
        assert verify_settlement_receipt(receipt, proxy.receipt_public_key())
        assert [c["_meta"]["aeib_attempt_no"] for c in target.calls] == [1, 2]
        assert all(c["_meta"]["aeib_caid"] == b.effect_caid for c in target.calls)
    finally:
        target.release_late_commit()
        proxy.close()


@pytest.mark.parametrize("mode,detail", [("nack", "fence_not_acked"), ("raise", "fence_raised:OSError"),
                                         ("truthy", "fence_not_acked")])
def test_wave5_fence_failure_keeps_latch(mode, detail):
    target = _LateCommitTarget(fence_mode=mode)
    proxy = _late_proxy(target, fence_probe_fn=target.fence)
    try:
        proxy.handle_json_rpc(_pay_call("idem-1", _pay_args()))
        err = proxy.handle_json_rpc(_pay_call("idem-2", REGEN_ARGS))["error"]
        assert (err["code"], err["data"]["reason"], err["data"]["fence_detail"]) == (
            -32009, "NOT_APPLIED_UNFENCED", detail)
        assert len(target.calls) == 1 and len(target.fence_requests) == 1
        assert _row(proxy, "idem-1")[0] == "EFFECT_INDETERMINATE"
        target.release_late_commit()
        assert len(target.effects) == 1
    finally:
        target.release_late_commit()
        proxy.close()


def test_wave5_deadline_path():
    target = _LateCommitTarget()
    proxy = _late_proxy(target, dispatch_not_after_ms=150, deadline_skew_ms=100)
    try:
        t0_ms = int(time.time() * 1000)
        proxy.handle_json_rpc(_pay_call("idem-1", _pay_args()))
        not_after = target.calls[0]["_meta"]["aeib_not_after_ms"]
        assert t0_ms + 150 <= not_after <= int(time.time() * 1000) + 150
        assert proxy.conn.execute("SELECT not_after_ms, attempt_no FROM mcp_idempotency WHERE idem_key='idem-1';"
                                  ).fetchone() == (not_after, 1)
        # Before not-after + skew: no basis -> blocked.
        early = proxy.handle_json_rpc(_pay_call("idem-2", REGEN_ARGS))["error"]
        assert early["data"]["reason"] == "NOT_APPLIED_UNFENCED"
        while int(time.time() * 1000) <= not_after + 100:
            time.sleep(0.02)
        target.release_late_commit()  # arrives after the deadline: the target refuses it
        assert target.refused == [("deadline", 1)] and target.effects == []
        retry = proxy.handle_json_rpc(_pay_call("idem-3", REGEN_ARGS))
        assert retry["result"] == {"status": "SUCCESS", "attempt": 2}
        assert len(target.effects) == 1
        assert json.loads(_row(proxy, "idem-1")[3])["settlement_basis"] == "deadline"
    finally:
        target.release_late_commit()
        proxy.close()


def test_wave5_deadline_skew_boundary_and_constructor_validation():
    target = _LateCommitTarget()
    proxy = _late_proxy(target, dispatch_not_after_ms=60_000, deadline_skew_ms=0)
    try:
        proxy.handle_json_rpc(_pay_call("idem-1", _pay_args()))
        not_after = target.calls[0]["_meta"]["aeib_not_after_ms"]
        assert proxy._not_applied_basis(PAY_TOOL, "c", 2, not_after, not_after / 1000.0) == (
            None, "no_fence_probe_configured")
        assert proxy._not_applied_basis(PAY_TOOL, "c", 2, not_after, (not_after + 1) / 1000.0)[0] == "deadline"
        proxy.deadline_skew_ms = 5
        assert proxy._not_applied_basis(PAY_TOOL, "c", 2, not_after, (not_after + 5) / 1000.0)[0] is None
        assert proxy._not_applied_basis(PAY_TOOL, "c", 2, not_after, (not_after + 6) / 1000.0)[0] == "deadline"
        assert proxy._not_applied_basis(PAY_TOOL, "c", 2, None, 10.0 ** 12)[0] is None
    finally:
        target.release_late_commit()
        proxy.close()
    for kwargs in ({"dispatch_not_after_ms": 0}, {"dispatch_not_after_ms": -5}, {"dispatch_not_after_ms": True},
                   {"dispatch_not_after_ms": 1.5}, {"deadline_skew_ms": -1}, {"deadline_skew_ms": True},
                   {"deadline_skew_ms": 0.5}):
        with pytest.raises(ValueError):
            HardenedIdempotentMcpProxy(upstream_transport_fn=lambda r: {"result": {}}, **kwargs)
    ok = HardenedIdempotentMcpProxy(upstream_transport_fn=lambda r: {"result": {}}, dispatch_not_after_ms=1,
                                    trust_not_applied_without_fence="yes")
    assert ok.trust_not_applied_without_fence is False  # only the literal True opts in
    ok.close()


def test_wave5_attempt_meta_merges_caller_meta_and_non_registry_mode():
    seen = []
    proxy = HardenedIdempotentMcpProxy(upstream_transport_fn=lambda r: (seen.append(r["params"]) or
                                                                        {"result": {"status": "SUCCESS"}}),
                                       fence_probe_fn=lambda t, c, n: True)
    try:
        call = {"method": "tools/call", "params": {"name": "refund.create", "idempotency_key": "k-meta",
                                                   "arguments": {"a": 1}, "_meta": {"progressToken": "p1"}}}
        assert proxy.handle_json_rpc(call)["result"]["status"] == "SUCCESS"
        meta = seen[0]["_meta"]
        assert meta["progressToken"] == "p1" and meta["aeib_attempt_no"] == 1
        assert meta["aeib_caid"] == proxy.compute_caid({"a": 1}, tool_name="refund.create")
        assert "aeib_not_after_ms" not in meta
        assert call["params"]["_meta"] == {"progressToken": "p1"}  # caller's frame not mutated
    finally:
        proxy.close()
    plain_seen = []
    plain = HardenedIdempotentMcpProxy(upstream_transport_fn=lambda r: (plain_seen.append(r["params"]) or
                                                                        {"result": {}}))
    try:
        plain.handle_json_rpc({"method": "tools/call", "params": {"name": "x", "idempotency_key": "k"}})
        assert "_meta" not in plain_seen[0]  # default configuration forwards params unchanged
    finally:
        plain.close()


def test_conformance_runner_unknown_vector_and_vec021_conditions(tmp_path: Path):
    tool_err = {"isError": True, "content": []}
    call_021 = {"method": "tools/call", "params": {"name": "refund.create", "arguments": {"amount_minor": 1},
                                                   "idempotency_key": "k-021", "caid": "sha256:2121"}}
    other_key = {"method": "tools/call", "params": {"name": "refund.create", "arguments": {"amount_minor": 1},
                                                    "idempotency_key": "k-other", "caid": "sha256:2122"}}
    report = _run_vectors(tmp_path, [
        {"vector_id": "mcp-vec-999", "name": "unknown_vector_never_passes", "input": call_021},
        {"vector_id": "mcp-vec-021", "name": "ok", "input": call_021, "simulate_tool_is_error": tool_err},
        {"vector_id": "mcp-vec-021", "name": "row_missing", "input": other_key, "simulate_tool_is_error": tool_err},
        {"vector_id": "mcp-vec-021", "name": "no_tool_error", "input": call_021},
    ])
    assert [r["passed"] for r in report["results"]] == [False, True, False, False]


def test_main_returns_one_when_a_vector_fails(tmp_path: Path):
    vec_dir = tmp_path / "conformance" / "vectors"
    vec_dir.mkdir(parents=True)
    (vec_dir / "mcp_idempotency.vectors.v1.json").write_text(json.dumps({
        "conformance_suite": "crafted",
        "vectors": [{"vector_id": "mcp-vec-999", "name": "fails"}]}), encoding="utf-8")
    orig_root = mcp_mod.REPO_ROOT
    try:
        mcp_mod.REPO_ROOT = tmp_path
        assert mcp_mod.main() == 1
        report = json.loads((tmp_path / "output" / "mcp-conformance-report.json").read_text(encoding="utf-8"))
        assert report["failed"] == 1
    finally:
        mcp_mod.REPO_ROOT = orig_root
