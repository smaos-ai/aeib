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

from adapters.mcp.idempotent_mcp_proxy import (
    HardenedIdempotentMcpProxy,
    run_conformance_suite_vectors,
)


def test_idempotent_mcp_proxy_all_30_conformance_vectors(tmp_path: Path):
    """Evaluates all 30 vectors in conformance/vectors/mcp_idempotency.vectors.v1.json."""
    vectors_path = REPO_ROOT / "conformance" / "vectors" / "mcp_idempotency.vectors.v1.json"
    report = run_conformance_suite_vectors(vectors_path, db_dir=tmp_path)

    assert report["total"] == 30
    assert report["passed"] == 30
    assert report["failed"] == 0
    assert report["pass_rate_pct"] == 100.0


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
    assert res_call["error"]["code"] == -32504

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
