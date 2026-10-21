#!/usr/bin/env python3
"""
tests/test_local_system1_leviathan_daemon.py
================================================================================
Comprehensive Test Suite for System-1 Screener & Leviathan Memory Daemon.

Evaluated under the stated model.
Zero mock assertions; real SQLite FTS5 virtual tables, real SHA-256 digests.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Any

import pytest

from tools.local_system1_leviathan_daemon import (
    System1FastScreener,
    LeviathanMemoryDaemon,
    SCREEN_FAST_PASS,
    SCREEN_ROUTE_STATION1_LATCH,
    SCREEN_HALT_SUSPICIOUS,
    SUBAGENT_HANDBACK_TOKEN_CEILING,
    PARENT_MEMORY_TOKEN_CEILING,
    ZERO_WIDTH_CHARS,
    KNOWN_CANARY_PATTERNS,
)


def test_screener_read_only_fast_path() -> None:
    screener = System1FastScreener(use_fm_cli=False)
    queries = [
        ("get_transaction_status", {"tx_id": "tx_998877"}),
        ("lookup_vendor_kyc", {"vendor_id": "v_123"}),
        ("read_audit_receipt", {"receipt_hash": "a" * 64}),
        ("fetch_policy_manifest", {"epoch": "2026-Q4"}),
        ("query_inventory_level", {"sku": "ITEM-42"}),
    ]

    for tool_name, args in queries:
        res = screener.screen_candidate(tool_name, args)
        assert res.decision == SCREEN_FAST_PASS
        assert res.latency_ms < 10.0  # sub-10ms requirement


def test_screener_state_mutation_routing() -> None:
    screener = System1FastScreener(use_fm_cli=False)
    mutations = [
        ("transfer_funds", {"amount": 5000, "destination": "DE89370400440532013000"}),
        ("post_customer_refund", {"refund_id": "ref_11", "amount_minor": 1000}),
        ("execute_wire_dispatch", {"recipient": "Treasury"}),
        ("mutate_settlement_ledger", {"entry_id": "e_88"}),
        ("update_balance", {"account_id": "acc_1", "delta": -500}),
    ]

    for tool_name, args in mutations:
        res = screener.screen_candidate(tool_name, args)
        assert res.decision == SCREEN_ROUTE_STATION1_LATCH
        assert "STATION1" in res.reason


def test_screener_adversarial_honeypot_interception() -> None:
    screener = System1FastScreener(use_fm_cli=False)

    for canary in KNOWN_CANARY_PATTERNS:
        res = screener.screen_candidate("read_configuration", {"target": canary})
        assert res.decision == SCREEN_HALT_SUSPICIOUS
        assert res.reason == "HALT_HONEYPOT_CANARY_PROBE_DETECTED"


def test_screener_token_smuggling_interception() -> None:
    screener = System1FastScreener(use_fm_cli=False)

    for zw in ZERO_WIDTH_CHARS:
        tainted_arg = f"benign_action_{zw}_hidden_token"
        res = screener.screen_candidate("inspect_state", {"param": tainted_arg})
        assert res.decision == SCREEN_HALT_SUSPICIOUS
        assert res.reason == "HALT_ZERO_WIDTH_TOKEN_SMUGGLING_DETECTED"


def test_screener_path_traversal() -> None:
    screener = System1FastScreener(use_fm_cli=False)
    traversal_probes = [
        "../../etc/passwd",
        "/proc/self/environ",
        "~/.ssh/id_ed25519",
    ]

    for probe in traversal_probes:
        res = screener.screen_candidate("read_file", {"filepath": probe})
        assert res.decision == SCREEN_HALT_SUSPICIOUS
        assert res.reason == "HALT_PATH_TRAVERSAL_SUSPICIOUS"


def test_daemon_subagent_handback_bounding() -> None:
    daemon = LeviathanMemoryDaemon(":memory:")

    # Generate huge handback content (> 1,000 tokens)
    large_summary = "Subagent trace finding: " + ("integrity verification of node partition " * 60)
    assert len(large_summary) > 2000

    node_id = daemon.remember(large_summary, memory_type="subagent_handback")
    cur = daemon._conn.cursor()
    cur.execute("SELECT content, token_count FROM memory_nodes WHERE node_id = ?", (node_id,))
    row = cur.fetchone()

    assert row["token_count"] <= SUBAGENT_HANDBACK_TOKEN_CEILING
    assert "[HANDBACK BOUNDED TO 350 TOKENS]" in row["content"]
    daemon.close()


def test_daemon_parent_memory_ceiling_and_packing() -> None:
    daemon = LeviathanMemoryDaemon(":memory:")

    # Insert 10 entries of ~250 tokens each (total ~2,500 tokens)
    for i in range(10):
        content = f"Architecture component {i}: " + ("subsystem specification and isolation invariant " * 15)
        daemon.remember(content, memory_type="architecture_fact", scope="spec")

    # Recall with parent budget ceiling of 1,500 tokens
    res = daemon.recall("component subsystem specification", limit=10, token_budget=PARENT_MEMORY_TOKEN_CEILING)

    assert res["total_tokens"] <= PARENT_MEMORY_TOKEN_CEILING
    assert res["budget_utilization"] <= 1.0
    assert len(res["recalled_nodes"]) > 0
    # Must have packed fewer than all 10 entries due to budget limit
    assert len(res["recalled_nodes"]) < 10

    daemon.close()


def test_daemon_fts5_bm25_recall() -> None:
    daemon = LeviathanMemoryDaemon(":memory:")

    daemon.remember("TigerBeetle two-phase escrow reserves financial ledger balance.", memory_type="fact", scope="fin")
    daemon.remember("Cilium Tetragon eBPF LSM monitors socket connections at kernel level.", memory_type="fact", scope="sec")
    daemon.remember("SQLite WAL mode ensures atomic durability across concurrent processes.", memory_type="fact", scope="db")

    # Query specifically for eBPF kernel security
    res = daemon.recall("eBPF kernel socket", limit=1)
    assert len(res["recalled_nodes"]) == 1
    assert "Tetragon" in res["recalled_nodes"][0]["content"]
    assert res["recalled_nodes"][0]["scope"] == "sec"

    daemon.close()


def test_daemon_hawkes_temporal_decay() -> None:
    daemon = LeviathanMemoryDaemon(":memory:")

    t0 = 1000000.0
    daemon.remember("Short term cached finding.", memory_type="cache", half_life_seconds=3600.0, current_time=t0)

    # Immediately at t0: decay factor is 1.0
    res_immediate = daemon.recall("cached finding", limit=1, current_time=t0)
    assert len(res_immediate["recalled_nodes"]) == 1
    assert abs(res_immediate["recalled_nodes"][0]["decay_score"] - 1.0) < 0.05

    # After 3 half-lives (3 * 3600 = 10800s): decay factor should be ~ (0.5)^3 = 0.125
    t_decayed = t0 + 10800.0
    res_decayed = daemon.recall("cached finding", limit=1, current_time=t_decayed)
    assert len(res_decayed["recalled_nodes"]) == 1
    decay_score = res_decayed["recalled_nodes"][0]["decay_score"]
    assert 0.10 <= decay_score <= 0.15

    daemon.close()


def test_daemon_scoped_forgetting() -> None:
    daemon = LeviathanMemoryDaemon(":memory:")

    id1 = daemon.remember("Session A context alpha.", scope="session_A")
    id2 = daemon.remember("Session A context beta.", scope="session_A")
    id3 = daemon.remember("Session B context gamma.", scope="session_B")

    # Forget session A
    forgotten = daemon.forget(scope="session_A")
    assert forgotten == 2

    # Verify session A entries are gone from recall
    res_a = daemon.recall("context alpha", scope="session_A")
    assert len(res_a["recalled_nodes"]) == 0

    # Verify session B entry survives
    res_b = daemon.recall("context gamma", scope="session_B")
    assert len(res_b["recalled_nodes"]) == 1
    assert res_b["recalled_nodes"][0]["node_id"] == id3

    stats = daemon.get_stats()
    assert stats["total_nodes"] == 3
    assert stats["active_nodes"] == 1

    daemon.close()


def test_banned_words_absence() -> None:
    # Formulate banned substrings dynamically to avoid triggering scanners
    banned_terms = [
        "guaran" + "teed",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "unassail" + "able",
        "unhack" + "able",
        "bank-" + "grade",
        "production-" + "ready",
    ]

    target_files = [
        Path("tools/local_system1_leviathan_daemon.py"),
        Path("tests/test_local_system1_leviathan_daemon.py"),
    ]

    for fpath in target_files:
        assert fpath.exists(), f"Target file does not exist: {fpath}"
        content = fpath.read_text(encoding="utf-8")
        for term in banned_terms:
            assert term not in content.lower(), f"Forbidden word '{term}' found in {fpath}"
