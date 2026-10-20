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
tests/test_idempotent_mcp_proxy.py — Pytest suite for Reference Idempotent MCP Proxy Middleware.

Verifies:
1. 20/20 Golden Conformance Vectors pass cleanly against IdempotentMcpProxyMiddleware.
2. Content-Addressed Action Identifier (CAID) collision detection and caching.
3. Timeout 504 durable uncertainty latching (EFFECT_INDETERMINATE).
4. Blind retry blocking under uncertainty (HALT_BLIND_RETRY_PROHIBITED_UNDER_UNCERTAINTY).
5. Authoritative tools/status reconciliation loop.
6. Server-crash WAL rehydration and recovery across restarts.
7. CLI execution and epistemic purity.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapters.mcp.idempotent_mcp_proxy import (
    IdempotentMcpProxyMiddleware,
    run_conformance_suite_vectors,
)


def test_idempotent_mcp_proxy_all_20_conformance_vectors():
    """Evaluates all 20 vectors in conformance/vectors/mcp_idempotency.vectors.v1.json."""
    vectors_path = REPO_ROOT / "conformance" / "vectors" / "mcp_idempotency.vectors.v1.json"
    report = run_conformance_suite_vectors(vectors_path)

    assert report["total"] == 20
    assert report["passed"] == 20
    assert report["failed"] == 0
    assert report["pass_rate_pct"] == 100.0


def test_idempotent_mcp_proxy_caid_content_addressing():
    """Verifies that semantically identical payloads produce identical CAID regardless of key order."""
    proxy = IdempotentMcpProxyMiddleware(upstream_transport_fn=lambda r: {"result": "ok"})

    args_1 = {"amount_minor": 15000, "recipient": "iban:FR761234"}
    args_2 = {"recipient": "iban:FR761234", "amount_minor": 15000}

    caid_1 = proxy.compute_caid(args_1)
    caid_2 = proxy.compute_caid(args_2)

    assert caid_1 == caid_2
    assert caid_1.startswith("sha256:")


def test_idempotent_mcp_proxy_blind_retry_blocked_under_indeterminate():
    """Verifies that an uncertain in-flight or timed-out call blocks blind retries."""
    call_count = [0]

    def simulated_upstream(req: dict) -> dict:
        call_count[0] += 1
        raise TimeoutError("Simulated 504 Gateway Timeout")

    proxy = IdempotentMcpProxyMiddleware(upstream_transport_fn=simulated_upstream)

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


def test_idempotent_mcp_proxy_reconciliation_cycle():
    """Verifies the reconciliation loop: timeout -> indeterminate -> tools/status probe -> confirmed."""
    server_state = ["PENDING"]

    def simulated_upstream(req: dict) -> dict:
        method = req.get("method")
        if method == "tools/call":
            raise TimeoutError("Dropped wire connection")
        elif method == "tools/status":
            return {"result": {"state": server_state[0]}}
        return {"error": {"code": -32601, "message": "Method not found"}}

    proxy = IdempotentMcpProxyMiddleware(upstream_transport_fn=simulated_upstream)

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


def test_idempotent_mcp_proxy_wal_persistence_and_recovery(tmp_path: Path):
    """Verifies WAL persistence across proxy reboots."""
    wal_file = tmp_path / "test_mcp_wal.jsonl"

    def simulated_upstream(req: dict) -> dict:
        return {"result": {"status": "DISPATCHED_AND_COMMITTED"}}

    # Create proxy instance 1, execute call
    proxy_1 = IdempotentMcpProxyMiddleware(
        upstream_transport_fn=simulated_upstream,
        wal_path=wal_file,
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

    # Verify WAL file exists and contains entries
    assert wal_file.exists()
    assert wal_file.stat().st_size > 0

    # Boot proxy instance 2 pointing to the same WAL file
    proxy_2 = IdempotentMcpProxyMiddleware(
        upstream_transport_fn=lambda r: {"error": "SHOULD_NOT_EXECUTE"},
        wal_path=wal_file,
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


def test_idempotent_mcp_proxy_cli_execution():
    """Verifies CLI execution of adapters/mcp/idempotent_mcp_proxy.py."""
    cmd = [sys.executable, str(REPO_ROOT / "adapters" / "mcp" / "idempotent_mcp_proxy.py")]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0
    assert "Pass Rate:       100.0%" in proc.stdout
    assert "Total Vectors:   20" in proc.stdout
    assert "Passed:          20" in proc.stdout


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
