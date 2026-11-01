#!/usr/bin/env python3
"""
Comprehensive Verification & Falsification Suite for src/mcp_action_firewall.py.

Status: INTERNAL PREVIEW COMMISSIONED
Evaluated under the stated model with real SQLite-WAL persistence, real Ed25519
signatures, RFC 8785 JCS canonicalization, and zero mocks.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
import sqlite3
from typing import Tuple

from cryptography.hazmat.primitives.asymmetric import ed25519
import pytest

from src.crypto_delegation_graph import (
    CryptoDelegationGraph,
    DelegationToken,
    ScopeBoundary,
)
from src.mcp_action_firewall import (
    AEIBReceiptLedger,
    ActionAuditSample,
    EffectReconciler,
    MCPActionFirewall,
    ResearchContextLedger,
    SignedIntent,
    compute_accountable_action_coverage_bps,
)
from src.temporal_authority_guard import (
    IntentScope,
    TemporalAuthorityGuard,
)


def _mint_delegation_token(
    issuer_key: ed25519.Ed25519PrivateKey,
    issuer_id: str,
    subject_id: str,
    scope: ScopeBoundary,
    issued_at: int,
    expires_at: int,
    parent_caid: str = "GENESIS",
) -> DelegationToken:
    unsigned = DelegationToken(
        issuer_spiffe_id=issuer_id,
        subject_spiffe_id=subject_id,
        scope=scope,
        issued_at_epoch_sec=issued_at,
        expires_at_epoch_sec=expires_at,
        parent_token_caid=parent_caid,
    )
    sig = issuer_key.sign(unsigned.canonical_bytes()).hex()
    return unsigned.with_signature(sig)


def test_1_aeib_receipt_ledger_wal_chain_and_tamper_detection(tmp_path: Path) -> None:
    db_file = tmp_path / "receipts.sqlite"
    op_key = ed25519.Ed25519PrivateKey.generate()
    wrong_key = ed25519.Ed25519PrivateKey.generate()

    ledger = AEIBReceiptLedger(db_file, op_key)

    # Empty ledger verifies cleanly with count 0
    ok_empty, msg_empty, cnt_empty = ledger.verify_ledger_and_replay(op_key.public_key())
    assert ok_empty is True
    assert msg_empty == "LEDGER_REPLAY_VERIFIED"
    assert cnt_empty == 0

    r0 = ledger.append_receipt(
        act_caid="sha256:act_0",
        actor_spiffe_id="spiffe://sovereign.nexus/agent/alpha",
        tool_id="mcp_read_doc",
        egress_host="docs.internal",
        decision="ALLOW",
        status_code="ALLOW_ACTION_AUTHORIZED",
        evaluated_at_epoch_sec=1_800_000_001,
    )
    assert r0.seq_index == 0
    assert r0.prev_receipt_caid == "GENESIS"
    assert r0.to_dict()["receipt_caid"] == r0.receipt_caid
    assert r0.to_dict()["signature_hex"] == r0.signature_hex
    with pytest.raises(dataclasses.FrozenInstanceError):
        r0.decision = "TAMPERED"  # type: ignore

    r1 = ledger.append_receipt(
        act_caid="sha256:act_1",
        actor_spiffe_id="spiffe://sovereign.nexus/agent/alpha",
        tool_id="mcp_delete_prod",
        egress_host="db.internal",
        decision="ESCALATE",
        status_code="ESCALATE_HUMAN_APPROVAL_REQUIRED",
        evaluated_at_epoch_sec=1_800_000_002,
    )
    assert r1.seq_index == 1
    assert r1.prev_receipt_caid == r0.receipt_caid

    r2 = ledger.append_receipt(
        act_caid="sha256:act_2",
        actor_spiffe_id="spiffe://sovereign.nexus/agent/alpha",
        tool_id="mcp_unlisted",
        egress_host="evil.example",
        decision="DENY",
        status_code="DENY_UNREGISTERED_MCP_TOOL:mcp_unlisted",
        evaluated_at_epoch_sec=1_800_000_003,
    )
    assert r2.seq_index == 2
    assert r2.prev_receipt_caid == r1.receipt_caid

    ok_full, msg_full, cnt_full = ledger.verify_ledger_and_replay(op_key.public_key())
    assert ok_full is True
    assert msg_full == "LEDGER_REPLAY_VERIFIED"
    assert cnt_full == 3

    # Wrong operator public key fails at row 0
    ok_wrong_key, msg_wrong_key, idx_wrong_key = ledger.verify_ledger_and_replay(
        wrong_key.public_key()
    )
    assert ok_wrong_key is False
    assert msg_wrong_key == "TAMPER_INVALID_OPERATOR_SIGNATURE"
    assert idx_wrong_key == 0

    # Tamper 1: Mutate decision column on row 1 -> receipt_caid mismatch
    raw_conn = sqlite3.connect(str(db_file))
    raw_conn.execute("UPDATE action_receipts SET decision = 'ALLOW' WHERE seq_index = 1")
    raw_conn.commit()
    ok_t1, msg_t1, idx_t1 = ledger.verify_ledger_and_replay(op_key.public_key())
    assert ok_t1 is False
    assert "TAMPER_RECEIPT_CAID_MISMATCH" in msg_t1
    assert idx_t1 == 1

    # Restore decision and tamper prev_receipt_caid on row 2 -> chain break
    raw_conn.execute("UPDATE action_receipts SET decision = 'ESCALATE' WHERE seq_index = 1")
    raw_conn.execute(
        "UPDATE action_receipts SET prev_receipt_caid = 'sha256:forged_prev' WHERE seq_index = 2"
    )
    raw_conn.commit()
    ok_t2, msg_t2, idx_t2 = ledger.verify_ledger_and_replay(op_key.public_key())
    assert ok_t2 is False
    assert "TAMPER_PREV_CAID_CHAIN_BREAK" in msg_t2
    assert idx_t2 == 2

    # Restore prev_receipt_caid and delete row 1 -> seq_index gap at index 1
    raw_conn.execute(
        "UPDATE action_receipts SET prev_receipt_caid = ? WHERE seq_index = 2",
        (r1.receipt_caid,),
    )
    raw_conn.execute("DELETE FROM action_receipts WHERE seq_index = 1")
    raw_conn.commit()
    ok_t3, msg_t3, idx_t3 = ledger.verify_ledger_and_replay(op_key.public_key())
    assert ok_t3 is False
    assert "TAMPER_SEQ_INDEX_GAP" in msg_t3
    assert idx_t3 == 1

    raw_conn.close()
    ledger.close()


def test_2_effect_reconciler_timeout_latch_and_probe_transitions() -> None:
    reconciler = EffectReconciler()
    eff_caid = "sha256:effect_stripe_charge_001"

    assert reconciler.get_effect_state(eff_caid) == "NONE"
    can_go, reason = reconciler.can_dispatch(eff_caid)
    assert can_go is True
    assert reason == "ALLOW_FRESH_OR_ABORTED_RETRY"

    # Timeout latches EFFECT_INDETERMINATE and blocks blind retry
    latched = reconciler.record_timeout_or_indeterminate(
        eff_caid, "stripe_charge", "spiffe://sovereign.nexus/agent/pay"
    )
    assert latched == "EFFECT_INDETERMINATE"
    assert reconciler.get_effect_state(eff_caid) == "EFFECT_INDETERMINATE"

    can_retry, deny_reason = reconciler.can_dispatch(eff_caid)
    assert can_retry is False
    assert deny_reason == "DENY_INDETERMINATE_EFFECT_PENDING_RECONCILIATION"

    # Invalid provider status raises ValueError
    with pytest.raises(ValueError, match="ERR_INVALID_PROVIDER_PROBE_STATUS"):
        reconciler.reconcile_with_provider_probe(eff_caid, "STILL_GUESSING")

    # Provider probe confirms ABORTED -> retry is now permitted
    new_state = reconciler.reconcile_with_provider_probe(eff_caid, "CONFIRMED_ABORTED")
    assert new_state == "CONFIRMED_ABORTED"
    can_after_abort, abort_reason = reconciler.can_dispatch(eff_caid)
    assert can_after_abort is True
    assert abort_reason == "ALLOW_FRESH_OR_ABORTED_RETRY"

    # Timeout again, then provider probe confirms COMMITTED -> duplicate retry blocked
    reconciler.record_timeout_or_indeterminate(
        eff_caid, "stripe_charge", "spiffe://sovereign.nexus/agent/pay"
    )
    committed_state = reconciler.reconcile_with_provider_probe(
        eff_caid, "CONFIRMED_COMMITTED"
    )
    assert committed_state == "CONFIRMED_COMMITTED"
    can_after_commit, commit_reason = reconciler.can_dispatch(eff_caid)
    assert can_after_commit is False
    assert commit_reason == "DENY_ALREADY_COMMITTED_IDEMPOTENT_REPLAY"


def test_3_research_context_ledger_deduplication_and_line_deltas() -> None:
    ctx_ledger = ResearchContextLedger()
    doc_v1 = "line alpha\nline beta\nline gamma\n"
    res1 = ctx_ledger.ingest_artifact(
        raw_text=doc_v1,
        tags=["security", "mcp"],
        parent_artifact_caid="NONE",
        cached_decision="ADOPT_SIDE_CAR_FIREWALL",
    )
    assert res1["status"] == "INGESTED_NEW_ARTIFACT"
    assert res1["line_delta_count"] == 3
    caid_v1 = res1["artifact_caid"]

    stored = ctx_ledger.get_artifact(caid_v1)
    assert stored is not None
    assert stored.tags == ("security", "mcp")
    assert stored.cached_decision == "ADOPT_SIDE_CAR_FIREWALL"

    # Re-ingesting the same paste skips re-evaluation and returns cached decision
    res_dup = ctx_ledger.ingest_artifact(
        raw_text=doc_v1,
        tags=["duplicate_paste"],
        parent_artifact_caid="NONE",
        cached_decision="IGNORED_NEW_DECISION",
    )
    assert res_dup == {
        "status": "DUPLICATE_ARTIFACT_SKIPPED",
        "artifact_caid": caid_v1,
        "cached_decision": "ADOPT_SIDE_CAR_FIREWALL",
    }

    # Ingesting child artifact computes exact new line delta against parent
    doc_v2 = "line alpha\nline beta\nline gamma\nline delta\nline epsilon\n"
    res2 = ctx_ledger.ingest_artifact(
        raw_text=doc_v2,
        tags=["security", "mcp", "v2"],
        parent_artifact_caid=caid_v1,
        cached_decision="ADD_STEP_UP_WARRANT",
    )
    assert res2["status"] == "INGESTED_NEW_ARTIFACT"
    assert res2["line_delta_count"] == 2

    # Ingesting with non-existent parent falls back to full line count
    doc_v3 = "standalone one\nstandalone two\n"
    res3 = ctx_ledger.ingest_artifact(
        raw_text=doc_v3,
        tags=["standalone"],
        parent_artifact_caid="sha256:nonexistent_parent",
    )
    assert res3["status"] == "INGESTED_NEW_ARTIFACT"
    assert res3["line_delta_count"] == 2


def test_4_mcp_action_firewall_end_to_end_enforcement(tmp_path: Path) -> None:
    op_key = ed25519.Ed25519PrivateKey.generate()
    pub_key = ed25519.Ed25519PrivateKey.generate()
    human_key = ed25519.Ed25519PrivateKey.generate()
    root_key = ed25519.Ed25519PrivateKey.generate()
    sub_key = ed25519.Ed25519PrivateKey.generate()

    root_id = "spiffe://sovereign.nexus/agent/orchestrator"
    sub_id = "spiffe://sovereign.nexus/agent/sub_worker"
    t0 = 1_800_000_000

    trust_store = {
        root_id: root_key.public_key(),
        sub_id: sub_key.public_key(),
    }
    ledger = AEIBReceiptLedger(tmp_path / "firewall.sqlite", op_key)
    graph = CryptoDelegationGraph(trust_store)
    temp_guard = TemporalAuthorityGuard(trust_store, active_session_id="sess_01")
    reconciler = EffectReconciler()

    firewall = MCPActionFirewall(
        receipt_ledger=ledger,
        delegation_graph=graph,
        temporal_guard=temp_guard,
        effect_reconciler=reconciler,
        human_approver_public_key=human_key.public_key(),
    )

    # Register GENESIS root token and narrowing child token for sub_worker
    root_scope = ScopeBoundary(
        allowed_egress_hosts=("api.github.com", "api.stripe.com"),
        allowed_tools=("github_create_issue", "stripe_payout", "github_read_pr"),
        max_financial_minor=50000,
        max_blast_radius_bps=5000,
    )
    root_tok = _mint_delegation_token(
        root_key, root_id, root_id, root_scope, t0, t0 + 3600, "GENESIS"
    )
    root_caid = graph.register_token(root_tok)

    sub_scope = ScopeBoundary(
        allowed_egress_hosts=("api.github.com",),
        allowed_tools=("github_create_issue", "github_read_pr"),
        max_financial_minor=1000,
        max_blast_radius_bps=2000,
    )
    sub_tok = _mint_delegation_token(
        root_key, root_id, sub_id, sub_scope, t0 + 1, t0 + 1800, root_caid
    )
    sub_caid = graph.register_token(sub_tok)

    # Tool manifest registration boundary checks
    with pytest.raises(ValueError, match="ERR_INVALID_MAX_TAINT_BPS"):
        firewall.register_signed_tool_manifest(
            "bad_low", ("api.github.com",), False, -1, pub_key.public_key(), "00"
        )
    with pytest.raises(ValueError, match="ERR_INVALID_MAX_TAINT_BPS"):
        firewall.register_signed_tool_manifest(
            "bad_high", ("api.github.com",), False, 10001, pub_key.public_key(), "00"
        )
    with pytest.raises(ValueError, match="HALT_INVALID_TOOL_MANIFEST_SIGNATURE"):
        firewall.register_signed_tool_manifest(
            "forged_tool",
            ("api.github.com",),
            False,
            0,
            pub_key.public_key(),
            "00" * 64,
        )

    # Register boundary max_taint_bps=0 and max_taint_bps=10000 and standard tools
    sig_zero = MCPActionFirewall.sign_tool_manifest_payload(
        "github_read_pr", ("api.github.com",), False, 0, pub_key
    )
    m_zero = firewall.register_signed_tool_manifest(
        "github_read_pr", ("api.github.com",), False, 0, pub_key.public_key(), sig_zero
    )
    assert m_zero.max_taint_bps == 0

    sig_max = MCPActionFirewall.sign_tool_manifest_payload(
        "doc_ping", ("api.github.com",), False, 10000, pub_key
    )
    m_max = firewall.register_signed_tool_manifest(
        "doc_ping", ("api.github.com",), False, 10000, pub_key.public_key(), sig_max
    )
    assert m_max.max_taint_bps == 10000

    sig_issue = MCPActionFirewall.sign_tool_manifest_payload(
        "github_create_issue", ("api.github.com",), False, 3000, pub_key
    )
    firewall.register_signed_tool_manifest(
        "github_create_issue",
        ("api.github.com",),
        False,
        3000,
        pub_key.public_key(),
        sig_issue,
    )

    sig_payout = MCPActionFirewall.sign_tool_manifest_payload(
        "stripe_payout", ("api.stripe.com",), True, 1000, pub_key
    )
    firewall.register_signed_tool_manifest(
        "stripe_payout",
        ("api.stripe.com",),
        True,
        1000,
        pub_key.public_key(),
        sig_payout,
    )

    # Case A: Unregistered tool -> default-deny and latches intent_caid
    res_unreg = firewall.evaluate_mcp_tool_call(
        actor_spiffe_id=sub_id,
        tool_id="sh_exec_arbitrary",
        egress_host="api.github.com",
        amount_minor=0,
        blast_radius_bps=100,
        context_taint_bps=0,
        intent_caid="sha256:intent_unreg_1",
        leaf_token_caid=sub_caid,
        effect_idempotency_caid="sha256:eff_unreg_1",
        current_time=t0 + 10,
    )
    assert res_unreg.decision == "DENY"
    assert res_unreg.status_code == "DENY_UNREGISTERED_MCP_TOOL:sh_exec_arbitrary"

    # Replaying the same intent_caid even on an allowed tool is blocked by terminal latch
    res_unreg_replay = firewall.evaluate_mcp_tool_call(
        actor_spiffe_id=sub_id,
        tool_id="github_create_issue",
        egress_host="api.github.com",
        amount_minor=0,
        blast_radius_bps=100,
        context_taint_bps=0,
        intent_caid="sha256:intent_unreg_1",
        leaf_token_caid=sub_caid,
        effect_idempotency_caid="sha256:eff_unreg_2",
        current_time=t0 + 20,
    )
    assert res_unreg_replay.decision == "DENY"
    assert res_unreg_replay.status_code == "DENY_TERMINAL_PRIOR_INTENT_LATCHED"

    # Case B: Forbidden host in manifest -> denied
    res_bad_host = firewall.evaluate_mcp_tool_call(
        actor_spiffe_id=sub_id,
        tool_id="github_create_issue",
        egress_host="exfil.attacker.io",
        amount_minor=0,
        blast_radius_bps=100,
        context_taint_bps=0,
        intent_caid="sha256:intent_bad_host",
        leaf_token_caid=sub_caid,
        effect_idempotency_caid="sha256:eff_bad_host",
        current_time=t0 + 10,
    )
    assert res_bad_host.decision == "DENY"
    assert res_bad_host.status_code == "DENY_MANIFEST_HOST_FORBIDDEN:exfil.attacker.io"

    # Case C: Over-privileged sub-agent attempting stripe_payout -> denied by delegation graph
    res_overpriv = firewall.evaluate_mcp_tool_call(
        actor_spiffe_id=sub_id,
        tool_id="stripe_payout",
        egress_host="api.stripe.com",
        amount_minor=500,
        blast_radius_bps=500,
        context_taint_bps=0,
        intent_caid="sha256:intent_overpriv",
        leaf_token_caid=sub_caid,
        effect_idempotency_caid="sha256:eff_overpriv",
        current_time=t0 + 10,
    )
    assert res_overpriv.decision == "DENY"
    assert "HALT_HOST_DENIED" in res_overpriv.status_code

    # Case D: 402 Payment Required at T0 latches terminal denial
    res_402 = firewall.evaluate_mcp_tool_call(
        actor_spiffe_id=sub_id,
        tool_id="github_create_issue",
        egress_host="api.github.com",
        amount_minor=100,
        blast_radius_bps=100,
        context_taint_bps=0,
        intent_caid="sha256:intent_402",
        leaf_token_caid=sub_caid,
        effect_idempotency_caid="sha256:eff_402",
        current_time=t0 + 10,
        payment_402_required=True,
    )
    assert res_402.decision == "DENY"
    assert res_402.status_code == "DENY_402_PAYMENT_REQUIRED_TERMINAL"

    res_402_later = firewall.evaluate_mcp_tool_call(
        actor_spiffe_id=sub_id,
        tool_id="github_create_issue",
        egress_host="api.github.com",
        amount_minor=100,
        blast_radius_bps=100,
        context_taint_bps=0,
        intent_caid="sha256:intent_402",
        leaf_token_caid=sub_caid,
        effect_idempotency_caid="sha256:eff_402_retry",
        current_time=t0 + 500,
        payment_402_required=False,
    )
    assert res_402_later.decision == "DENY"
    assert res_402_later.status_code == "DENY_TERMINAL_PRIOR_INTENT_LATCHED"

    # Case E: Reversible tool at exact max_taint_bps boundary (3000 == 3000) -> ALLOW without human approval
    res_boundary_ok = firewall.evaluate_mcp_tool_call(
        actor_spiffe_id=sub_id,
        tool_id="github_create_issue",
        egress_host="api.github.com",
        amount_minor=100,
        blast_radius_bps=500,
        context_taint_bps=3000,
        intent_caid="sha256:intent_bound_ok",
        leaf_token_caid=sub_caid,
        effect_idempotency_caid="sha256:eff_bound_ok",
        current_time=t0 + 15,
    )
    assert res_boundary_ok.decision == "ALLOW"
    assert res_boundary_ok.status_code == "ALLOW_ACTION_AUTHORIZED"

    # Duplicate replay of committed effect_idempotency_caid is denied
    res_dup_eff = firewall.evaluate_mcp_tool_call(
        actor_spiffe_id=sub_id,
        tool_id="github_create_issue",
        egress_host="api.github.com",
        amount_minor=100,
        blast_radius_bps=500,
        context_taint_bps=3000,
        intent_caid="sha256:intent_bound_ok_dup",
        leaf_token_caid=sub_caid,
        effect_idempotency_caid="sha256:eff_bound_ok",
        current_time=t0 + 16,
    )
    assert res_dup_eff.decision == "DENY"
    assert res_dup_eff.status_code == "DENY_ALREADY_COMMITTED_IDEMPOTENT_REPLAY"

    # Case F: Reversible tool exceeding max_taint_bps (3001 > 3000) without human warrant -> ESCALATE
    res_taint_esc = firewall.evaluate_mcp_tool_call(
        actor_spiffe_id=sub_id,
        tool_id="github_create_issue",
        egress_host="api.github.com",
        amount_minor=100,
        blast_radius_bps=500,
        context_taint_bps=3001,
        intent_caid="sha256:intent_taint_esc",
        leaf_token_caid=sub_caid,
        effect_idempotency_caid="sha256:eff_taint_esc",
        current_time=t0 + 17,
    )
    assert res_taint_esc.decision == "ESCALATE"
    assert res_taint_esc.status_code == "ESCALATE_HUMAN_APPROVAL_REQUIRED"

    # Case G: Irreversible tool (stripe_payout) by root_id without human warrant -> ESCALATE,
    # with forged human warrant -> ESCALATE, with valid human warrant -> ALLOW
    res_irrev_no_sig = firewall.evaluate_mcp_tool_call(
        actor_spiffe_id=root_id,
        tool_id="stripe_payout",
        egress_host="api.stripe.com",
        amount_minor=5000,
        blast_radius_bps=1000,
        context_taint_bps=0,
        intent_caid="sha256:intent_payout_1",
        leaf_token_caid=root_caid,
        effect_idempotency_caid="sha256:eff_payout_1",
        current_time=t0 + 20,
    )
    assert res_irrev_no_sig.decision == "ESCALATE"

    res_irrev_bad_sig = firewall.evaluate_mcp_tool_call(
        actor_spiffe_id=root_id,
        tool_id="stripe_payout",
        egress_host="api.stripe.com",
        amount_minor=5000,
        blast_radius_bps=1000,
        context_taint_bps=0,
        intent_caid="sha256:intent_payout_1",
        leaf_token_caid=root_caid,
        effect_idempotency_caid="sha256:eff_payout_1",
        current_time=t0 + 21,
        human_approval_signature_hex="ff" * 64,
    )
    assert res_irrev_bad_sig.decision == "ESCALATE"

    valid_warrant_sig = MCPActionFirewall.sign_human_step_up_warrant(
        act_caid=res_irrev_no_sig.act_caid,
        subject_spiffe_id=root_id,
        tool_id="stripe_payout",
        human_private_key=human_key,
    )
    res_irrev_ok = firewall.evaluate_mcp_tool_call(
        actor_spiffe_id=root_id,
        tool_id="stripe_payout",
        egress_host="api.stripe.com",
        amount_minor=5000,
        blast_radius_bps=1000,
        context_taint_bps=0,
        intent_caid="sha256:intent_payout_1",
        leaf_token_caid=root_caid,
        effect_idempotency_caid="sha256:eff_payout_1",
        current_time=t0 + 22,
        human_approval_signature_hex=valid_warrant_sig,
    )
    assert res_irrev_ok.decision == "ALLOW"
    assert res_irrev_ok.status_code == "ALLOW_ACTION_AUTHORIZED"

    # Case H: Registered SignedIntent (TemporalIntentEnvelope) in TemporalAuthorityGuard
    unsigned_intent = SignedIntent(
        actor_spiffe_id=sub_id,
        effect_class="GITHUB_MUTATION",
        idempotency_key="idem_gh_01",
        policy_version="eo1@2026",
        session_id="sess_01",
        issued_at_epoch_sec=t0,
        not_before_epoch_sec=t0 + 30,
        expires_at_epoch_sec=t0 + 600,
        max_retries=1,
        delegation_chain=(root_caid, sub_caid),
        taint_level=0,
        scope=IntentScope(("api.github.com",), ("github_create_issue",), 1000, 2000),
        preconditions={"quota_ok": True},
        payload={"issue": 42},
    )
    signed_intent = unsigned_intent.with_signature(
        sub_key.sign(unsigned_intent.canonical_unsigned_bytes()).hex()
    )
    temp_guard.register_intent(signed_intent)

    # Premature dispatch at t0 + 10 (< not_before t0 + 30) denies without terminal latch
    res_premature = firewall.evaluate_mcp_tool_call(
        actor_spiffe_id=sub_id,
        tool_id="github_create_issue",
        egress_host="api.github.com",
        amount_minor=100,
        blast_radius_bps=200,
        context_taint_bps=0,
        intent_caid=signed_intent.intent_caid,
        leaf_token_caid=sub_caid,
        effect_idempotency_caid="sha256:eff_temp_ok",
        current_time=t0 + 10,
        live_preconditions={"quota_ok": True},
    )
    assert res_premature.decision == "DENY"
    assert "HALT_INTENT_PREMATURE" in res_premature.status_code

    # Dispatch at t0 + 35 with satisfied preconditions succeeds
    res_temp_ok = firewall.evaluate_mcp_tool_call(
        actor_spiffe_id=sub_id,
        tool_id="github_create_issue",
        egress_host="api.github.com",
        amount_minor=100,
        blast_radius_bps=200,
        context_taint_bps=0,
        intent_caid=signed_intent.intent_caid,
        leaf_token_caid=sub_caid,
        effect_idempotency_caid="sha256:eff_temp_ok",
        current_time=t0 + 35,
        live_preconditions={"quota_ok": True},
    )
    assert res_temp_ok.decision == "ALLOW"

    # Precondition failure on another registered intent latches DENIED_TERMINAL
    unsigned_fail = SignedIntent(
        actor_spiffe_id=sub_id,
        effect_class="GITHUB_MUTATION",
        idempotency_key="idem_gh_02",
        policy_version="eo1@2026",
        session_id="sess_01",
        issued_at_epoch_sec=t0,
        not_before_epoch_sec=t0,
        expires_at_epoch_sec=t0 + 600,
        max_retries=1,
        delegation_chain=(root_caid, sub_caid),
        taint_level=0,
        scope=IntentScope(("api.github.com",), ("github_create_issue",), 1000, 2000),
        preconditions={"quota_ok": True},
        payload={"issue": 43},
    )
    signed_fail = unsigned_fail.with_signature(
        sub_key.sign(unsigned_fail.canonical_unsigned_bytes()).hex()
    )
    temp_guard.register_intent(signed_fail)

    res_pre_fail = firewall.evaluate_mcp_tool_call(
        actor_spiffe_id=sub_id,
        tool_id="github_create_issue",
        egress_host="api.github.com",
        amount_minor=100,
        blast_radius_bps=200,
        context_taint_bps=0,
        intent_caid=signed_fail.intent_caid,
        leaf_token_caid=sub_caid,
        effect_idempotency_caid="sha256:eff_temp_fail",
        current_time=t0 + 40,
        live_preconditions={"quota_ok": False},
    )
    assert res_pre_fail.decision == "DENY"
    assert "HALT_PRECONDITION_DENIED_TERMINAL" in res_pre_fail.status_code

    # Verify the entire SQLite receipt ledger replays and verifies every evaluation
    ok_ledger, msg_ledger, total_receipts = ledger.verify_ledger_and_replay(
        op_key.public_key()
    )
    assert ok_ledger is True
    assert msg_ledger == "LEDGER_REPLAY_VERIFIED"
    assert total_receipts == 15
    ledger.close()


def test_5_accountable_action_coverage_ciso_metric_and_boundaries() -> None:
    # Empty sequence fails closed at 0 bps
    empty_rep = compute_accountable_action_coverage_bps([])
    assert empty_rep.accountable_count == 0
    assert empty_rep.total_count == 0
    assert empty_rep.coverage_bps == 0
    assert empty_rep.wilson_low_bps == 0
    assert empty_rep.wilson_high_bps == 0

    # N=1 extreme point: 1/1 accountable
    full_sample = ActionAuditSample(
        action_id="act_full",
        identity_bound=True,
        policy_evaluated=True,
        receipt_recorded=True,
        replay_verified=True,
        reconcilable=True,
    )
    rep_one = compute_accountable_action_coverage_bps([full_sample])
    assert rep_one.accountable_count == 1
    assert rep_one.total_count == 1
    assert rep_one.coverage_bps == 10000
    assert rep_one["wilson_high_bps"] == 10000
    assert 0 < rep_one["wilson_low_bps"] < 10000

    # Verify each of the 5 boolean flags is individually required for accountability
    flag_names: Tuple[str, ...] = (
        "identity_bound",
        "policy_evaluated",
        "receipt_recorded",
        "replay_verified",
        "reconcilable",
    )
    single_drop_samples = []
    for idx, flag in enumerate(flag_names):
        kwargs = {
            "action_id": f"act_drop_{idx}",
            "identity_bound": True,
            "policy_evaluated": True,
            "receipt_recorded": True,
            "replay_verified": True,
            "reconcilable": True,
        }
        kwargs[flag] = False
        s = ActionAuditSample(**kwargs)
        assert s.is_accountable is False
        single_drop_samples.append(s)

    # Non-trivial fraction: 5 accountable out of 7 total -> 50000 // 7 = 7142 bps
    seven_samples = [full_sample] * 5 + single_drop_samples[:2]
    rep_5_7 = compute_accountable_action_coverage_bps(seven_samples)
    assert rep_5_7.accountable_count == 5
    assert rep_5_7.total_count == 7
    assert rep_5_7.coverage_bps == 7142
    assert rep_5_7.wilson_low_bps == 3589
    assert rep_5_7.wilson_high_bps == 9178
    assert rep_5_7.to_dict()["coverage_bps"] == 7142
