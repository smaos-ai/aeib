"""
tests/test_vibe_coding_and_long_horizon_guard.py
================================================================================
Pytest suite for VibeCodingSecurityGate, GitAiDeterministicBisectResolver,
and IapsAgentHoneypotGuard.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.vibe_coding_and_long_horizon_guard import (
    AgentPatch,
    GitAiDeterministicBisectResolver,
    IapsAgentHoneypotGuard,
    VibeCodingSecurityGate,
)


def test_vibe_coding_missing_auth_and_rls_detection() -> None:
    vibe_python_code = """
@app.get("/health")
def health_check():
    return {"ok": True}

@app.post("/v1/new_transfer")
@require_auth
def new_transfer():
    return {"status": "ok"}

@app.post("/v1/legacy_admin_payout")
def legacy_admin_payout():
    return {"status": "leaked"}
"""
    vibe_sql = """
CREATE TABLE customer_wallets (id TEXT PRIMARY KEY, balance INT);
CREATE TABLE audit_logs (id TEXT PRIMARY KEY);
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
"""
    audit_res = VibeCodingSecurityGate.audit_backend_and_sql(
        vibe_python_code,
        vibe_sql,
        signed_public_routes={"health_check"},
    )
    assert audit_res.passed is False
    assert audit_res.unauthenticated_routes == ["legacy_admin_payout"]
    assert audit_res.tables_missing_rls == ["CUSTOMER_WALLETS"]
    assert audit_res.rejection_code == "HALT_VIBE_CODING_ACCESS_CONTROL_OR_RLS_MISSING"


def test_vibe_coding_clean_authenticated_and_rls_compliant() -> None:
    clean_python_code = """
@app.get("/health")
def health_check():
    return {"ok": True}

@app.post("/v1/orders")
@require_auth
def create_order():
    return {"status": "created"}
"""
    clean_sql = """
CREATE TABLE orders (id TEXT PRIMARY KEY, user_id TEXT);
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
"""
    audit_res = VibeCodingSecurityGate.audit_backend_and_sql(
        clean_python_code,
        clean_sql,
        signed_public_routes={"health_check"},
    )
    assert audit_res.passed is True
    assert audit_res.unauthenticated_routes == []
    assert audit_res.tables_missing_rls == []
    assert audit_res.rejection_code == "OK"


def test_gitai_bisect_isolates_breaking_patch() -> None:
    # 8 patches, patch 5 breaks verification
    patches = [
        AgentPatch(
            patch_id=f"p-{i}",
            agent_id=f"agent-{i}",
            touched_symbols={f"sym_{i}"},
            passes_verification=(i != 5),
        )
        for i in range(1, 9)
    ]
    merge_res = GitAiDeterministicBisectResolver.resolve_and_merge_batch(
        patches,
        lambda subset: all(p.passes_verification for p in subset),
    )
    assert merge_res["reverted_breaking_patch_ids"] == ["p-5"]
    assert len(merge_res["merged_patch_ids"]) == 7
    assert merge_res["verification_invocations"] <= 7


def test_gitai_disjoint_symbol_conflict_filtering() -> None:
    # Patches 1 and 2 touch the same symbol "shared_symbol"
    patches = [
        AgentPatch(
            patch_id="p-1",
            agent_id="agent-1",
            touched_symbols={"shared_symbol"},
            passes_verification=True,
        ),
        AgentPatch(
            patch_id="p-2",
            agent_id="agent-2",
            touched_symbols={"shared_symbol"},
            passes_verification=True,
        ),
        AgentPatch(
            patch_id="p-3",
            agent_id="agent-3",
            touched_symbols={"unique_symbol"},
            passes_verification=True,
        ),
    ]
    merge_res = GitAiDeterministicBisectResolver.resolve_and_merge_batch(
        patches,
        lambda subset: all(p.passes_verification for p in subset),
    )
    assert "p-2" in merge_res["conflicted_patch_ids"]
    assert "p-1" in merge_res["merged_patch_ids"]
    assert "p-3" in merge_res["merged_patch_ids"]


def test_iaps_agent_honeypot_detection_and_deterrence() -> None:
    honeypot = IapsAgentHoneypotGuard()

    # Clean request to allowed resource
    clean_res = honeypot.inspect_request(
        agent_id="agent-normal",
        root_sponsor_id="sponsor-bravo",
        target_resource="tool://user.read_profile",
        taint_tier="TIER_1_INTERNAL_DB",
        payload_bytes=b"{}",
    )
    assert clean_res["disposition"] == "AUTHORIZED"
    assert clean_res["code"] == "OK"

    # Tripwire touch: file://.env.production.canary
    trip_res = honeypot.inspect_request(
        agent_id="agent-malicious",
        root_sponsor_id="sponsor-bravo",
        target_resource="file://.env.production.canary",
        taint_tier="TIER_2_UNTRUSTED_EXTERNAL",
        payload_bytes=b"cat .env.production.canary",
    )
    assert trip_res["disposition"] == "NOT_DISPATCHED"
    assert trip_res["code"] == "HALT_HONEYPOT_TRIPWIRE_ENGAGED"
    assert "sha256:" in trip_res["incrimination_hash"]
    assert len(honeypot.forensic_log) == 1

    # Same sponsor quarantined for future requests
    quarantined_res = honeypot.inspect_request(
        agent_id="agent-peer",
        root_sponsor_id="sponsor-bravo",
        target_resource="tool://user.read_profile",
        taint_tier="TIER_1_INTERNAL_DB",
        payload_bytes=b"{}",
    )
    assert quarantined_res["disposition"] == "NOT_DISPATCHED"
    assert quarantined_res["code"] == "HALT_SPONSOR_QUARANTINED_BY_HONEYPOT"
