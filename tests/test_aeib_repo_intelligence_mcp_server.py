"""Tests and falsification vectors for tools/aeib_repo_intelligence_mcp_server.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from src.accuracy_cascade_router import BASE_ORACLE_CHECKS, BPS_SCALE, T2_ORACLE_CHECKS
from src.jcs_canonicalizer import encode_jcs
from tools.aeib_repo_intelligence_mcp_server import AEIBRepoIntelligenceMCPServer

SAMPLE_REPO = {
    "src/refund_service.py": (
        "class RefundService:\n"
        "    def create_refund(self, op_id: str, amount_minor: int) -> str:\n"
        "        return op_id\n"
    ),
    "src/webhook_handler.py": (
        "from src.refund_service import RefundService\n\n"
        "class WebhookHandler:\n"
        "    def on_event(self, svc: RefundService, op_id: str) -> str:\n"
        "        return svc.create_refund(op_id, 500)\n"
    ),
}


def _call_tool(srv: AEIBRepoIntelligenceMCPServer, name: str, arguments: dict) -> dict:
    resp = srv.handle_jsonrpc(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}}
    )
    assert "result" in resp
    return resp["result"]


def test_mcp_initialize_tools_list_and_errors() -> None:
    srv = AEIBRepoIntelligenceMCPServer()
    init_resp = srv.handle_jsonrpc({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert init_resp["result"]["serverInfo"]["name"] == "aeib-repo-intelligence"

    list_resp = srv.handle_jsonrpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    tool_names = [t["name"] for t in list_resp["result"]["tools"]]
    assert tool_names == [
        "repo_map",
        "repo_slice",
        "blast_radius",
        "compress_test_output",
        "verify_diff",
        "escalation_pack",
        "behavioral_check",
    ]

    bad_req = srv.handle_jsonrpc({"jsonrpc": "1.0", "id": 3})
    assert bad_req["error"]["code"] == -(326 * 100)

    bad_method = srv.handle_jsonrpc({"jsonrpc": "2.0", "id": 4, "method": "unknown/method"})
    assert bad_method["error"]["code"] == -(326 * 100 + 1)

    bad_tool = srv.handle_jsonrpc(
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "no_such_tool"}}
    )
    assert bad_tool["error"]["code"] == -(326 * 100 + 1)


def test_repo_map_slice_and_blast_radius() -> None:
    srv = AEIBRepoIntelligenceMCPServer()
    rmap = _call_tool(srv, "repo_map", {"files": SAMPLE_REPO, "max_tokens": 2000})["structuredContent"]
    assert rmap["is_dag"] is True and len(rmap["modules"]) == 2

    rslice = _call_tool(
        srv,
        "repo_slice",
        {"files": SAMPLE_REPO, "target_file": "src/refund_service.py", "target_symbol": "create_refund"},
    )["structuredContent"]
    assert "src/webhook_handler.py" in rslice["reverse_caller_files"]
    assert rslice["slice_char4_tokens"] > 0 and rslice["recovery_manifest_sha256"].startswith("sha256:")

    blast = _call_tool(
        srv,
        "blast_radius",
        {"files": SAMPLE_REPO, "target_file": "src/refund_service.py", "target_symbol": "create_refund"},
    )["structuredContent"]
    assert blast["omitted_caller_count"] == 0

    # Falsification: tiny budget with fail_on_budget_overflow=True returns MCP tool isError=True
    overflow = _call_tool(
        srv,
        "blast_radius",
        {
            "files": SAMPLE_REPO,
            "target_file": "src/refund_service.py",
            "target_symbol": "create_refund",
            "token_budget": 2,
            "fail_on_budget_overflow": True,
        },
    )
    assert overflow["isError"] is True and "HALT_REVERSE_CALLER_BUDGET_OVERFLOW" in overflow["content"][0]["text"]


def test_compress_test_output_and_escalation_pack() -> None:
    srv = AEIBRepoIntelligenceMCPServer()
    verbose_log = (
        "collected 10 items\n"
        + ("PASS line output\n" * 200)
        + "E   AssertionError: duplicate refund executed\n"
        + "FAILED tests/test_refund.py::test_replay - AssertionError\n"
    )
    comp = _call_tool(srv, "compress_test_output", {"log": verbose_log, "budget_tokens": 60})["structuredContent"]
    assert comp["truncated"] is True
    assert comp["compressed_char4_tokens"] < comp["raw_char4_tokens"]
    assert any("AssertionError" in a for a in comp["failing_assertions"])

    esc = _call_tool(
        srv,
        "escalation_pack",
        {
            "task": {"id": "t-refund"},
            "contract": {"rule": "no_duplicate_refund"},
            "failed_candidate_diff": "--- a/src/refund_service.py\n+++ b/src/refund_service.py\n",
            "failed_checks": ["contract_tests_pass"],
            "failing_output": comp["summary"],
            "affected_symbols": ["src/refund_service.py::create_refund"],
            "reverse_callers": ["src/webhook_handler.py::on_event"],
            "constraints": ["C1: Idempotent refund"],
            "attempt": 1,
        },
    )["structuredContent"]
    assert esc["repair_budget"]["attempt"] == 1
    assert esc["affected_symbols"] == ["src/refund_service.py::create_refund"]


def test_verify_diff_and_behavioral_check() -> None:
    srv = AEIBRepoIntelligenceMCPServer()
    full_t2_ev = {c: True for c in BASE_ORACLE_CHECKS + T2_ORACLE_CHECKS}

    # 1. Falsification: signature changed without updating reverse caller -> rejected
    bad_diff = (
        "--- a/src/refund_service.py\n"
        "+++ b/src/refund_service.py\n"
        "@@ -2,2 +2,2 @@\n"
        "-    def create_refund(self, op_id: str, amount_minor: int) -> str:\n"
        "+    def create_refund(self, op_id: str, amount_minor: int, currency: str) -> str:\n"
    )
    v_bad = _call_tool(
        srv,
        "verify_diff",
        {
            "files": SAMPLE_REPO,
            "target_file": "src/refund_service.py",
            "target_symbol": "create_refund",
            "diff": bad_diff,
            "risk_tier": "T2",
            "evidence": full_t2_ev,
            "mutation_kill_ratio_bps": (29 * BPS_SCALE) // 30,
            "min_mutation_kill_bps": (27 * BPS_SCALE) // 30,
        },
    )["structuredContent"]
    assert v_bad["accepted"] is False
    assert "blast_radius_updated" in v_bad["failed_checks"]

    # Verify Ed25519 signature on MCP verification receipt
    pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(v_bad["public_key_hex"]))
    pub.verify(bytes.fromhex(v_bad["ed25519_signature_hex"]), encode_jcs(v_bad["jcs_receipt"]))

    # 2. Behavioral check: unattested wire_transfer + staircase dirty-revert trajectory
    b_res = _call_tool(
        srv,
        "behavioral_check",
        {
            "action_id": "act-1",
            "subject_agent_id": "agent-1",
            "tool_id": "bank_wire",
            "capability_id": "wire_transfer",
            "amount_minor": 5000,
            "unattended_steps": 1,
            "nlah_harness_digest": "sha256:nlah_v1",
            "initial_state_digest": "sha256:s0",
            "trajectory_digests": ["sha256:s1", "sha256:s0"],
        },
    )["structuredContent"]
    assert b_res["behavioral_allowed"] is False
    assert b_res["behavioral_reason"] == "HALT_ROGUE_AGENT_UNATTESTED_HIGH_STAKES"
    assert b_res["noop_valid"] is False
    assert b_res["noop_reason"] == "HALT_STAIRCASE_DERIVATIVE_DIVERGENCE"


def test_stdio_subprocess_roundtrip() -> None:
    """Verifies stdio JSON-RPC 2.0 round-trip execution in a separate interpreter."""
    server_path = Path("tools/aeib_repo_intelligence_mcp_server.py")
    stdin_payload = (
        json.dumps({"jsonrpc": "2.0", "id": 10, "method": "initialize"})
        + "\n"
        + json.dumps({"jsonrpc": "2.0", "id": 11, "method": "tools/list"})
        + "\n"
    )
    proc = subprocess.run(
        [sys.executable, str(server_path)],
        input=stdin_payload,
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    lines = [json.loads(line) for line in proc.stdout.strip().splitlines()]
    assert len(lines) == 2
    assert lines[0]["id"] == 10 and lines[0]["result"]["serverInfo"]["name"] == "aeib-repo-intelligence"
    assert lines[1]["id"] == 11 and len(lines[1]["result"]["tools"]) == 7
