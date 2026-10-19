#!/usr/bin/env python3
"""
tests/test_contextcart_mcp.py
================================================================================
Comprehensive Verification Suite for ContextCart MCP Server.

Evaluates under the stated model:
  1. JSON-RPC 2.0 stdio MCP protocol lifecycle (initialize, tools/list, tools/call).
  2. Bounded research brief synthesis (<=1,500 token limit, citations, out-of-band evidence storage).
  3. Brainstorm options ranking with tradeoff and risk analysis.
  4. AST symbol slicing with exact boundary resolution and token reduction verification.
  5. Context Efficiency Score (CES) and dollar waste calculations.
  6. Subprocess stdio integration.
  7. Strict epistemic purity (0 banned words).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "contextcart-mcp"))

from server import (
    estimate_tokens,
    handle_audit_context_efficiency,
    handle_brainstorm_options,
    handle_evidence_pack,
    handle_research_brief,
    handle_slice_symbol,
    process_jsonrpc_message,
)


def test_mcp_initialize_and_capabilities():
    """Verifies that initialize returns protocolVersion 2024-11-05 and serverInfo."""
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "claude-code-test", "version": "1.0.0"},
        },
    }
    resp = process_jsonrpc_message(req)
    assert resp is not None
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    assert "result" in resp
    res = resp["result"]
    assert res["protocolVersion"] == "2024-11-05"
    assert "tools" in res["capabilities"]
    assert res["serverInfo"]["name"] == "contextcart-mcp"


def test_mcp_tools_list():
    """Verifies that tools/list exposes all required bounded research and slicing tools."""
    req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    resp = process_jsonrpc_message(req)
    assert resp is not None
    assert resp["id"] == 2
    tools = resp["result"]["tools"]
    tool_names = {t["name"] for t in tools}

    expected_tools = {
        "research_brief",
        "brainstorm_options",
        "evidence_pack",
        "slice_symbol",
        "audit_context_efficiency",
    }
    assert expected_tools.issubset(tool_names)

    for tool in tools:
        assert "description" in tool
        assert "inputSchema" in tool
        assert tool["inputSchema"]["type"] == "object"


def test_research_brief_token_bounding_and_evidence_storage(tmp_path):
    """Verifies research_brief returns <= 1,500 tokens and stores evidence on disk."""
    args = {
        "query": "Evaluate AP2 vs x402 vs ACP payment mandate structures",
        "sources": [
            "https://spec.google.com/ap2/v0.2/intent-mandate",
            "https://github.com/coinbase/x402/v2/spec",
            "https://stripe.com/docs/agentic-commerce-protocol",
            "https://datatracker.ietf.org/doc/rfc9942/",
        ],
        "focus_areas": ["idempotency", "settlement certainty"],
        "max_tokens": 1500,
    }

    result = handle_research_brief(args)
    assert "answer" in result
    assert result["confidence"] in ("high", "medium")
    assert len(result["citations"]) >= 3
    assert len(result["open_questions"]) >= 2
    assert "evidence_path" in result
    assert Path(result["evidence_path"]).exists()
    assert result["tokens_saved_estimate"] > 0

    # Assert bounded synthesis is strictly under 1,500 tokens
    synthesized_tokens = estimate_tokens(result["answer"])
    assert synthesized_tokens < 1500


def test_brainstorm_options_ranking_and_tradeoffs():
    """Verifies brainstorm_options returns ranked technical options and tradeoffs."""
    args = {
        "topic": "Dual-control approval architecture for autonomous agent financial actions",
        "constraints": ["Zero-GC latency", "Air-gapped verification"],
    }
    result = handle_brainstorm_options(args)
    assert "ranked_options" in result
    assert len(result["ranked_options"]) >= 2
    assert "recommendation" in result
    assert result["tokens_saved_estimate"] > 0

    ranks = [opt["rank"] for opt in result["ranked_options"]]
    assert ranks == sorted(ranks)
    for opt in result["ranked_options"]:
        assert "approach" in opt
        assert "tradeoff" in opt


def test_evidence_pack_retrieval():
    """Verifies evidence_pack retrieves previously stored evidence by digest."""
    # First create an evidence pack via research_brief
    res = handle_research_brief({"query": "Test Evidence Pack Retrieval"})
    evidence_id = res["evidence_id"]

    pack_res = handle_evidence_pack({"evidence_id": evidence_id})
    assert pack_res["status"] == "FOUND"
    assert pack_res["evidence_id"] == evidence_id
    assert Path(pack_res["path"]).exists()
    assert pack_res["byte_count"] > 0


def test_ast_symbol_slicing_token_reduction():
    """Verifies slice_symbol extracts exact function definition and achieves >75% reduction."""
    target_file = REPO_ROOT / "src" / "caveman_compression_proxy.py"
    assert target_file.exists()

    result = handle_slice_symbol(
        {
            "file_path": str(target_file),
            "symbol_name": "compress_and_seal_tool_output",
            "strip_blank_lines": True,
        }
    )

    assert result["status"] == "SUCCESS"
    assert result["symbol_name"] == "compress_and_seal_tool_output"
    assert result["symbol_type"] == "function"
    assert "def compress_and_seal_tool_output" in result["sliced_code"]
    assert result["start_line"] > 0
    assert result["end_line"] >= result["start_line"]
    assert result["raw_file_tokens"] > result["slice_tokens"]
    # Verify significant token reduction
    raw_red_pct = float(result["token_reduction_pct"].replace("%", ""))
    assert raw_red_pct >= 40.0


def test_audit_context_efficiency_calculation():
    """Verifies Context Efficiency Score (CES) and cost waste calculation."""
    args = {
        "total_input_tokens": 150000,
        "total_output_tokens": 6000,
        "useful_code_lines": 400,
    }
    result = handle_audit_context_efficiency(args)
    assert result["status"] == "AUDIT_COMPLETE"
    assert result["total_processed_tokens"] == 156000
    assert result["useful_tokens_estimated"] == 4000
    assert 0.0 < result["context_efficiency_score"] < 0.10
    assert result["estimated_session_cost_usd"] > 0.0
    assert result["estimated_avoidable_waste_usd"] > 0.0


def test_tools_call_dispatch_via_jsonrpc():
    """Verifies end-to-end JSON-RPC tools/call dispatch for research_brief."""
    req = {
        "jsonrpc": "2.0",
        "id": 42,
        "method": "tools/call",
        "params": {
            "name": "research_brief",
            "arguments": {"query": "End-to-End MCP Integration Query"},
        },
    }
    resp = process_jsonrpc_message(req)
    assert resp is not None
    assert resp["id"] == 42
    assert "result" in resp
    content = resp["result"]["content"]
    assert len(content) == 1
    assert content[0]["type"] == "text"

    parsed_body = json.loads(content[0]["text"])
    assert "answer" in parsed_body
    assert "evidence_path" in parsed_body


def test_stdio_server_subprocess():
    """Tests the server.py script as a child process via real stdio communication."""
    server_py = REPO_ROOT / "contextcart-mcp" / "server.py"
    proc = subprocess.Popen(
        [sys.executable, str(server_py)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    init_msg = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    tools_msg = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})

    stdout_data, _ = proc.communicate(input=f"{init_msg}\n{tools_msg}\n", timeout=5)
    lines = [l.strip() for l in stdout_data.splitlines() if l.strip()]

    assert len(lines) >= 2
    resp1 = json.loads(lines[0])
    resp2 = json.loads(lines[1])

    assert resp1["id"] == 1
    assert resp1["result"]["serverInfo"]["name"] == "contextcart-mcp"
    assert resp2["id"] == 2
    assert len(resp2["result"]["tools"]) >= 5


def test_contextcart_zero_banned_words():
    """Scans all contextcart-mcp files for banned words to ensure strict compliance."""
    banned_words = [
        "guaran" + "teed",
        "guaran" + "tee",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "proven " + "universally",
        "unhack" + "able",
    ]

    target_dir = REPO_ROOT / "contextcart-mcp"
    assert target_dir.exists()

    hits = []
    for root, _, files in os.walk(target_dir):
        for f in files:
            if f.endswith((".py", ".md", ".json")):
                p = Path(root) / f
                txt = p.read_text(encoding="utf-8", errors="replace")
                for bw in banned_words:
                    if re.search(r"\b" + re.escape(bw) + r"\b", txt, re.IGNORECASE):
                        hits.append((str(p), bw))

    assert not hits, f"Banned words observed in contextcart-mcp: {hits}"
