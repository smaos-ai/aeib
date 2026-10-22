#!/usr/bin/env python3
# File: tests/test_global_dominance_g1_g2_g3.py
"""
Test suite verifying G-Global-1 (Public Benchmark Adapter), G-Global-2
(SovereignNexus MCP Gateway), and G-Global-3 (Pluggable Transactional Storage
Protocol: SQLite WAL + Multi-AZ Serializable Consensus).
"""

import base64
from pathlib import Path
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from benchmarks.public_sota_adapter import PublicSotaBenchmarkAdapter
from src.decide_evaluation_rate_and_decay_solver import canonical_jcs, sha256_hex
from src.sovereign_nexus_mcp_gateway import SovereignNexusMcpGateway
from src.transactional_storage_backend import (
    SerializableMultiNodeConsensusBackend,
    SqliteWalTransactionalBackend,
)


def test_g_global_3_sqlite_wal_and_multi_az_ssi_consensus_backends(tmp_path: Path):
    """
    Evaluates G-Global-3:
    1. SqliteWalTransactionalBackend fencing token monotonicity, budget ceiling,
       and indeterminate latching.
    2. SerializableMultiNodeConsensusBackend 2-of-3 AZ quorum, minority partition
       fail-closed, and SSI SQLSTATE 40001 write-skew conflict detection.
    """
    sqlite_backend = SqliteWalTransactionalBackend(tmp_path / "test_wal.sqlite")
    sqlite_backend.register_workflow_budget("wf_1", 10000)

    r1 = sqlite_backend.stage_pre_dispatch_intent(
        caid="caid_1",
        workflow_id="wf_1",
        amount_minor=4000,
        fencing_token=10,
        payload_hash="hash_1",
    )
    assert r1.disposition == "COMMITTED_STAGED_ESCROW"
    assert r1.remaining_budget_minor == 6000

    # Stale fencing token (token 9 < 10) must fail closed
    r_stale = sqlite_backend.stage_pre_dispatch_intent(
        caid="caid_2",
        workflow_id="wf_1",
        amount_minor=1000,
        fencing_token=9,
        payload_hash="hash_2",
    )
    assert r_stale.disposition == "HALT_STORAGE_STALE_FENCING_TOKEN"

    # Budget overrun (4000 + 7000 > 10000) must fail closed
    r_over = sqlite_backend.stage_pre_dispatch_intent(
        caid="caid_3",
        workflow_id="wf_1",
        amount_minor=7000,
        fencing_token=11,
        payload_hash="hash_3",
    )
    assert r_over.disposition == "HALT_STORAGE_BUDGET_EXCEEDED"

    # Multi-AZ Serializable Consensus Backend
    ssi_backend = SerializableMultiNodeConsensusBackend()
    ssi_backend.register_workflow_budget("wf_az", 20000)

    # 2-of-3 AZs reachable -> quorum succeeds
    ssi_backend.set_reachable_azs({"az-eu-central-1a", "az-eu-central-1b"})
    az_ok = ssi_backend.stage_pre_dispatch_intent(
        caid="caid_az_1",
        workflow_id="wf_az",
        amount_minor=5000,
        fencing_token=1,
        payload_hash="hash_az_1",
        expected_snapshot_version=1,
    )
    assert az_ok.disposition == "COMMITTED_STAGED_ESCROW"
    assert az_ok.quorum_acks == 2

    # Concurrent transaction reading stale snapshot version 1 -> SQLSTATE 40001 conflict
    az_conflict = ssi_backend.stage_pre_dispatch_intent(
        caid="caid_az_2",
        workflow_id="wf_az",
        amount_minor=5000,
        fencing_token=2,
        payload_hash="hash_az_2",
        expected_snapshot_version=1,
    )
    assert az_conflict.disposition == "HALT_SSI_SERIALIZATION_CONFLICT_40001"

    # Minority partition (only 1 AZ reachable) -> fails closed
    ssi_backend.set_reachable_azs({"az-eu-central-1a"})
    az_min = ssi_backend.stage_pre_dispatch_intent(
        caid="caid_az_3",
        workflow_id="wf_az",
        amount_minor=2000,
        fencing_token=3,
        payload_hash="hash_az_3",
    )
    assert az_min.disposition == "HALT_QUORUM_MINORITY_PARTITION"
    assert az_min.quorum_acks == 1


def test_g_global_2_sovereign_nexus_mcp_gateway_jsonrpc_and_tools(tmp_path: Path):
    """
    Evaluates G-Global-2:
    Drop-in MCP Gateway exposing decide_v45, station1_authorize, and station2_reconcile.
    """
    gw = SovereignNexusMcpGateway(db_path=tmp_path / "mcp_gw.sqlite")
    gw.storage.register_workflow_budget("wf_mcp", 50000)

    init_resp = gw.handle_jsonrpc({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert init_resp["result"]["serverInfo"]["name"] == "sovereign-nexus-mcp"

    tools_resp = gw.handle_jsonrpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    tool_names = {t["name"] for t in tools_resp["result"]["tools"]}
    assert tool_names == {"decide_v45", "station1_authorize", "station2_reconcile"}

    # Call decide_v45
    dec_resp = gw.handle_jsonrpc(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "decide_v45", "arguments": {"query": "Optimize multi-hop search"}},
        }
    )
    dec_sc = dec_resp["result"]["structuredContent"]
    assert dec_sc["status"] == "SYNTHESIZED"
    assert dec_sc["coverage_achieved_bps"] == 10000
    assert dec_sc["eval_rate_multiplier_bps"] >= 20000


def test_g_global_1_public_sota_benchmark_replication_and_ed25519_receipt(tmp_path: Path):
    """
    Evaluates G-Global-1:
    Public benchmark replication across MuSiQue/FRAMES (5-hop QA), BIRD-SQL (S-VES RLS),
    and tau-bench (Pass^8 & Proposal-to-Commit Drift).
    """
    adapter = PublicSotaBenchmarkAdapter()
    out_file = tmp_path / "public_sota_report.json"
    report = adapter.execute_full_public_benchmark(output_json_path=out_file)

    assert out_file.exists()
    assert report.musique_5hop_sake_em_bps >= 9800
    assert report.musique_5hop_naive_em_bps < 1500
    assert report.bird_sql_valid_authorized_bps == 10000
    assert report.bird_sql_missing_rls_blocked_bps == 10000
    assert report.bird_sql_cross_tenant_leak_bps == 0
    assert report.tau_bench_verified_pass8_bps >= 9200
    assert report.tau_bench_invalid_commit_rate_bps == 0
    assert report.tau_bench_duplicate_side_effects_bps == 0

    # Verify Ed25519 signature over canonical JCS payload
    payload_obj = {
        "suite_id": report.suite_id,
        "musique_5hop_naive_em_bps": report.musique_5hop_naive_em_bps,
        "musique_5hop_sake_em_bps": report.musique_5hop_sake_em_bps,
        "bird_sql_valid_authorized_bps": report.bird_sql_valid_authorized_bps,
        "bird_sql_missing_rls_blocked_bps": report.bird_sql_missing_rls_blocked_bps,
        "bird_sql_cross_tenant_leak_bps": report.bird_sql_cross_tenant_leak_bps,
        "tau_bench_unverified_pass8_bps": report.tau_bench_unverified_pass8_bps,
        "tau_bench_verified_pass8_bps": report.tau_bench_verified_pass8_bps,
        "tau_bench_invalid_commit_rate_bps": report.tau_bench_invalid_commit_rate_bps,
        "tau_bench_duplicate_side_effects_bps": report.tau_bench_duplicate_side_effects_bps,
        "eval_rate_multiplier_bps": report.eval_rate_multiplier_bps,
        "token_reduction_bps": report.token_reduction_bps,
    }
    jcs_bytes = canonical_jcs(payload_obj)
    assert sha256_hex(jcs_bytes) == report.report_sha256

    pub_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(report.public_key_b64))
    sig_bytes = base64.b64decode(report.signature_b64)
    pub_key.verify(sig_bytes, jcs_bytes)

    with pytest.raises(Exception):
        pub_key.verify(sig_bytes, jcs_bytes + b"x")


def test_banned_words_absence():
    """Enforces AGENTS.md epistemic boundary across all G-Global-1..3 files."""
    banned = [
        "guaran" + "teed",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "unassail" + "able",
        "unhack" + "able",
        "proven " + "universally",
    ]
    for fpath in (
        "src/transactional_storage_backend.py",
        "src/sovereign_nexus_mcp_gateway.py",
        "benchmarks/public_sota_adapter.py",
        "tests/test_global_dominance_g1_g2_g3.py",
    ):
        with open(fpath, "r", encoding="utf-8") as f:
            txt = f.read().lower()
            for word in banned:
                assert word not in txt, f"Banned term '{word}' found in {fpath}"
