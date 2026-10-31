#!/usr/bin/env python3
"""
Complete 14-Item Conformance & Falsification Suite for src/temporal_authority_guard.py.
Evaluated under the stated model with zero mocks and real Ed25519 signatures.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
import re
from typing import Dict, Optional, Tuple

from cryptography.hazmat.primitives.asymmetric import ed25519
import pytest

from src.temporal_authority_guard import (
    IntentScope,
    TemporalAuthorityGuard,
    TemporalIntentEnvelope,
    sha256_caid,
)


def _mint_signed_envelope(
    key: ed25519.Ed25519PrivateKey,
    actor_id: str,
    idem_key: str,
    t0: int,
    ttl: int = 60,
    not_before_offset: int = 0,
    session_id: str = "session_live_01",
    max_retries: int = 0,
    delegation_chain: Tuple[str, ...] = ("sha256:root",),
    taint_level: int = 0,
    scope: Optional[IntentScope] = None,
    preconditions: Optional[Dict[str, bool]] = None,
) -> TemporalIntentEnvelope:
    sc = scope or IntentScope(
        allowed_hosts=("api.stripe.com",),
        allowed_tools=("charge_card",),
        max_amount_minor=10000,
        max_blast_radius_bps=3000,
    )
    pre = (
        preconditions
        if preconditions is not None
        else {"balance_sufficient": True, "network_allowed": True}
    )
    unsigned = TemporalIntentEnvelope(
        actor_spiffe_id=actor_id,
        effect_class="PAYMENT_CHARGE",
        idempotency_key=idem_key,
        policy_version="eo1-policy@2026-10-31",
        session_id=session_id,
        issued_at_epoch_sec=t0,
        not_before_epoch_sec=t0 + not_before_offset,
        expires_at_epoch_sec=t0 + ttl,
        max_retries=max_retries,
        delegation_chain=delegation_chain,
        taint_level=taint_level,
        scope=sc,
        preconditions=pre,
        payload={"amount_minor": 5000},
    )
    sig = key.sign(unsigned.canonical_unsigned_bytes()).hex()
    return unsigned.with_signature(sig)


def test_matrix_1_to_3_denied_at_t0_cannot_execute_later_and_snapshot_expiry() -> None:
    key = ed25519.Ed25519PrivateKey.generate()
    actor = "spiffe://sovereign.nexus/ns/prod/actor/worker_1"
    guard = TemporalAuthorityGuard({actor: key.public_key()})
    t0 = 1_800_000_000

    # Test 1: Intent denied at T0 (due to insufficient balance) is latched to DENIED_TERMINAL.
    # Even if credits replenish at T0 + 3600s, replay is blocked.
    env_denied = _mint_signed_envelope(key, actor, "idem_denied_t0", t0, ttl=7200)
    reg = guard.register_intent(env_denied)
    assert reg.authorized is True
    assert guard.get_intent_state(env_denied.intent_caid) == "INTENT_REGISTERED"

    v_t0 = guard.evaluate_temporal_dispatch(
        env_denied.intent_caid,
        current_epoch_sec=t0 + 1,
        live_preconditions={"balance_sufficient": False, "network_allowed": True},
        requested_host="api.stripe.com",
        requested_tool="charge_card",
        requested_amount_minor=5000,
    )
    assert v_t0.authorized is False
    assert v_t0.state == "DENIED_TERMINAL"
    assert "HALT_PRECONDITION_DENIED_TERMINAL:balance_sufficient" in v_t0.status_code

    # Credits reset at T0 + 3600s (1 hour later); agent tries to replay the same intent -> BLOCKED
    v_t1h = guard.evaluate_temporal_dispatch(
        env_denied.intent_caid,
        current_epoch_sec=t0 + 3600,
        live_preconditions={"balance_sufficient": True, "network_allowed": True},
        requested_host="api.stripe.com",
        requested_tool="charge_card",
        requested_amount_minor=5000,
    )
    assert v_t1h.authorized is False
    assert v_t1h.status_code == "HALT_PRIOR_DENIAL_IS_TERMINAL:REAUTH_REQUIRED"

    # Tests 2 & 3: Snapshot suspended at T0 + 10s, resumed after expiry (T0 + 120s > T0 + 60s)
    env_snap = _mint_signed_envelope(key, actor, "idem_snap_exp", t0, ttl=60)
    guard.register_intent(env_snap)
    assert guard.suspend_intent(env_snap.intent_caid) == "FROZEN_INDETERMINATE"

    # Attempting dispatch while frozen fails closed
    v_frozen = guard.evaluate_temporal_dispatch(
        env_snap.intent_caid,
        current_epoch_sec=t0 + 20,
        live_preconditions={"balance_sufficient": True, "network_allowed": True},
        requested_host="api.stripe.com",
        requested_tool="charge_card",
        requested_amount_minor=5000,
    )
    assert v_frozen.authorized is False
    assert v_frozen.status_code == "HALT_INDETERMINATE_REQUIRES_RECONCILIATION"

    v_resume_exp = guard.resume_and_reconcile_snapshot(
        env_snap.intent_caid,
        current_epoch_sec=t0 + 120,
        live_preconditions={"balance_sufficient": True, "network_allowed": True},
        reconciliation_probe_status="NOT_EXECUTED",
    )
    assert v_resume_exp.authorized is False
    assert v_resume_exp.status_code == "HALT_EXPIRED_SNAPSHOT_INTENT_REQUIRES_REAUTHORIZATION"


def test_matrix_4_to_6_persistence_and_detached_daemon_blocked() -> None:
    # Test 4: Cron, systemd, launchd, shell rc, and authorized_keys writes are denied
    for bad_path in (
        "/etc/cron.d/backdoor",
        "/var/spool/cron/crontabs/root",
        "/etc/systemd/system/agent.service",
        "/Users/dev/Library/LaunchAgents/com.agent.plist",
        "/Users/dev/Library/LaunchDaemons/com.agent.plist",
        "/home/user/.bashrc",
        "/home/user/.zshrc",
        "/home/user/.ssh/authorized_keys",
    ):
        allowed, reason = TemporalAuthorityGuard.evaluate_persistence_write(bad_path)
        assert allowed is False
        assert "HALT_PERSISTENCE_WRITE_DENIED" in reason

    ok_path, ok_reason = TemporalAuthorityGuard.evaluate_persistence_write("src/business_logic.py")
    assert ok_path is True
    assert ok_reason == "OK_STORAGE_WRITE_PERMITTED"

    # Test 5: Detached child processes, timers, schedulers, and time.sleep blocked
    for snippet, expected_marker in (
        ("import os\nos.setsid()\n", "HALT_FORBIDDEN_ASYNC_INVOCATION:setsid"),
        ("import os\nos.fork()\n", "HALT_FORBIDDEN_ASYNC_INVOCATION:fork"),
        (
            "import threading\nt = threading.Thread(target=fn, daemon=True)\n",
            "HALT_DETACHED_PROCESS_KEYWORD:daemon",
        ),
        ("import subprocess\nsubprocess.Popen(['sh'])\n", "HALT_FORBIDDEN_ASYNC_MODULE:subprocess"),
        ("from schedule import every\n", "HALT_FORBIDDEN_ASYNC_MODULE:schedule"),
        ("import time\ntime.sleep(3600)\n", "HALT_DEFERRED_SLEEP_BLOCKED"),
        ("Timer(10, fn)\n", "HALT_FORBIDDEN_ASYNC_INVOCATION:Timer"),
        ("def broken(:\n", "HALT_SYNTAX_ERROR"),
    ):
        ok_ast, code_reason = TemporalAuthorityGuard.audit_ast_for_async_daemons(snippet)
        assert ok_ast is False
        assert expected_marker in code_reason

    ok_clean, reason_clean = TemporalAuthorityGuard.audit_ast_for_async_daemons(
        "def compute(x: int) -> int:\n    return x * 2\n"
    )
    assert ok_clean is True
    assert reason_clean == "OK_AST_CLEAN"


def test_matrix_7_to_9_dns_tunneling_and_raw_udp_icmp_blocked() -> None:
    guard = TemporalAuthorityGuard({}, dns_max_queries_per_window=3)
    actor = "spiffe://sovereign.nexus/ns/prod/actor/net_worker"
    allowlist = frozenset({"api.stripe.com"})

    # Test 9: Raw UDP and ICMP egress are denied unconditionally
    ok_udp, r_udp = guard.evaluate_network_and_dns_egress(actor, "UDP", "api.stripe.com", allowlist)
    assert ok_udp is False and r_udp == "HALT_RAW_PROTOCOL_DENIED:UDP"
    ok_icmp, r_icmp = guard.evaluate_network_and_dns_egress(
        actor, "ICMP", "api.stripe.com", allowlist
    )
    assert ok_icmp is False and r_icmp == "HALT_RAW_PROTOCOL_DENIED:ICMP"

    # Test 7: DNS tunneling via TXT record, oversized query (>128 bytes), or long subdomain label
    ok_txt, r_txt = guard.evaluate_network_and_dns_egress(
        actor, "DNS", "api.stripe.com", allowlist, dns_record_type="TXT", dns_query_wire_len=64
    )
    assert ok_txt is False and r_txt == "HALT_DNS_RECORD_TYPE_DENIED:TXT"

    ok_long, r_long = guard.evaluate_network_and_dns_egress(
        actor, "DNS", "api.stripe.com", allowlist, dns_record_type="A", dns_query_wire_len=200
    )
    assert ok_long is False and "HALT_DNS_TUNNEL_OVERSIZED_QUERY" in r_long

    high_entropy_host = ("a" * 55) + ".stripe.com"
    ok_lbl, r_lbl = guard.evaluate_network_and_dns_egress(
        actor, "DNS", high_entropy_host, allowlist, dns_record_type="A", dns_query_wire_len=70
    )
    assert ok_lbl is False and r_lbl == "HALT_DNS_TUNNEL_HIGH_ENTROPY_SUBDOMAIN"

    ok_unlisted, r_unlisted = guard.evaluate_network_and_dns_egress(
        actor, "DNS", "evil.example.com", allowlist, dns_record_type="A", dns_query_wire_len=32
    )
    assert ok_unlisted is False and "HALT_DNS_DOMAIN_NOT_ALLOWLISTED" in r_unlisted

    # Test 8: DNS tunneling via repeated small queries is rate-limited after 3 queries
    for _ in range(3):
        ok_q, _ = guard.evaluate_network_and_dns_egress(
            actor, "DNS", "api.stripe.com", allowlist, dns_record_type="A", dns_query_wire_len=32
        )
        assert ok_q is True
    ok_burst, r_burst = guard.evaluate_network_and_dns_egress(
        actor, "DNS", "api.stripe.com", allowlist, dns_record_type="A", dns_query_wire_len=32
    )
    assert ok_burst is False and "HALT_DNS_TUNNEL_RATE_LIMIT_EXCEEDED" in r_burst

    # Test 6: TCP egress allowlist enforcement
    ok_tcp, _ = guard.evaluate_network_and_dns_egress(actor, "TCP", "api.stripe.com", allowlist)
    assert ok_tcp is True
    bad_tcp, r_tcp = guard.evaluate_network_and_dns_egress(actor, "TCP", "evil.com", allowlist)
    assert bad_tcp is False and "HALT_EGRESS_DESTINATION_DENIED" in r_tcp

    bad_proto, r_proto = guard.evaluate_network_and_dns_egress(
        actor, "SCTP", "api.stripe.com", allowlist
    )
    assert bad_proto is False and "HALT_UNKNOWN_PROTOCOL:SCTP" in r_proto


def test_matrix_10_to_14_delegation_session_persistence_and_indeterminate_reconcile() -> None:
    key_p = ed25519.Ed25519PrivateKey.generate()
    key_c = ed25519.Ed25519PrivateKey.generate()
    parent_id = "spiffe://sovereign.nexus/ns/prod/actor/parent"
    child_id = "spiffe://sovereign.nexus/ns/prod/actor/child"
    guard = TemporalAuthorityGuard(
        {parent_id: key_p.public_key(), child_id: key_c.public_key()},
        active_session_id="session_live_01",
    )
    t0 = 1_800_000_000

    parent_env = _mint_signed_envelope(key_p, parent_id, "idem_p", t0, ttl=600, taint_level=1)
    guard.register_intent(parent_env)

    # Valid monotonic child
    child_ok = _mint_signed_envelope(
        key_c,
        child_id,
        "idem_c_ok",
        t0 + 10,
        ttl=300,
        delegation_chain=("sha256:root", parent_env.intent_caid),
        taint_level=2,
    )
    assert guard.verify_delegation_monotonicity(parent_env, child_ok).authorized is True

    # Test 10: Delegated child cannot outlive parent
    child_outlive = _mint_signed_envelope(
        key_c,
        child_id,
        "idem_c_outlive",
        t0 + 10,
        ttl=1200,
        delegation_chain=("sha256:root", parent_env.intent_caid),
        taint_level=1,
    )
    v_outlive = guard.verify_delegation_monotonicity(parent_env, child_outlive)
    assert v_outlive.authorized is False
    assert "HALT_DELEGATION_EXPIRY_VIOLATION" in v_outlive.status_code

    # Test 11: Child cannot exceed parent scope or decrease taint
    child_taint_drop = _mint_signed_envelope(
        key_c,
        child_id,
        "idem_c_taint",
        t0 + 10,
        ttl=200,
        delegation_chain=("sha256:root", parent_env.intent_caid),
        taint_level=0,
    )
    v_taint = guard.verify_delegation_monotonicity(parent_env, child_taint_drop)
    assert v_taint.authorized is False
    assert "HALT_DELEGATION_TAINT_DECREASE" in v_taint.status_code

    child_scope_esc = _mint_signed_envelope(
        key_c,
        child_id,
        "idem_c_scope",
        t0 + 10,
        ttl=200,
        delegation_chain=("sha256:root", parent_env.intent_caid),
        taint_level=1,
        scope=IntentScope(("api.stripe.com",), ("charge_card",), max_amount_minor=99999),
    )
    v_scope = guard.verify_delegation_monotonicity(parent_env, child_scope_esc)
    assert v_scope.authorized is False
    assert "HALT_DELEGATION_SCOPE_VIOLATION" in v_scope.status_code

    # Test 12: Token persisted to disk from an old session cannot authorize a new session
    stale_session_env = _mint_signed_envelope(
        key_p, parent_id, "idem_stale_sess", t0, ttl=600, session_id="session_old_99"
    )
    guard.register_intent(stale_session_env)
    v_stale = guard.evaluate_temporal_dispatch(
        stale_session_env.intent_caid,
        current_epoch_sec=t0 + 5,
        live_preconditions={"balance_sufficient": True, "network_allowed": True},
        requested_host="api.stripe.com",
        requested_tool="charge_card",
        requested_amount_minor=1000,
    )
    assert v_stale.authorized is False
    assert "HALT_STALE_SESSION_TOKEN" in v_stale.status_code

    # Test 13: Concurrent/repeated dispatch attempts produce at most 1 commit
    once_env = _mint_signed_envelope(key_p, parent_id, "idem_once", t0, ttl=600, max_retries=0)
    guard.register_intent(once_env)
    v_first = guard.evaluate_temporal_dispatch(
        once_env.intent_caid,
        current_epoch_sec=t0 + 5,
        live_preconditions={"balance_sufficient": True, "network_allowed": True},
        requested_host="api.stripe.com",
        requested_tool="charge_card",
        requested_amount_minor=1000,
    )
    v_second = guard.evaluate_temporal_dispatch(
        once_env.intent_caid,
        current_epoch_sec=t0 + 6,
        live_preconditions={"balance_sufficient": True, "network_allowed": True},
        requested_host="api.stripe.com",
        requested_tool="charge_card",
        requested_amount_minor=1000,
    )
    assert v_first.authorized is True and v_first.state == "COMMITTED"
    assert v_second.authorized is False and v_second.status_code == "HALT_DUPLICATE_COMMITTED_INTENT"

    # Test 14: Unknown reconciliation probe keeps actor halted in FROZEN_INDETERMINATE
    indet_env = _mint_signed_envelope(key_p, parent_id, "idem_indet", t0, ttl=600)
    guard.register_intent(indet_env)
    guard.suspend_intent(indet_env.intent_caid)
    v_unk = guard.resume_and_reconcile_snapshot(
        indet_env.intent_caid,
        current_epoch_sec=t0 + 20,
        live_preconditions={"balance_sufficient": True, "network_allowed": True},
        reconciliation_probe_status="UNKNOWN",
    )
    assert v_unk.authorized is False
    assert v_unk.state == "FROZEN_INDETERMINATE"
    assert v_unk.status_code == "HALT_RECONCILIATION_UNKNOWN_KEEP_HALTED"

    # EXECUTED probe transitions to COMMITTED without duplicate execution
    v_exec = guard.resume_and_reconcile_snapshot(
        indet_env.intent_caid,
        current_epoch_sec=t0 + 25,
        live_preconditions={"balance_sufficient": True, "network_allowed": True},
        reconciliation_probe_status="EXECUTED",
    )
    assert v_exec.authorized is False
    assert v_exec.state == "COMMITTED"
    assert v_exec.status_code == "OK_RECONCILED_ALREADY_EXECUTED_NO_RETRY"


def test_5_boundary_and_error_branches_for_mutation_adequacy() -> None:
    key = ed25519.Ed25519PrivateKey.generate()
    actor = "spiffe://sovereign.nexus/ns/prod/actor/edge"
    guard = TemporalAuthorityGuard({actor: key.public_key()})
    t0 = 1_800_000_000

    # Invalid scope parameters
    with pytest.raises(ValueError, match="ERR_NEGATIVE_AMOUNT_MINOR"):
        IntentScope(("h",), ("t",), max_amount_minor=-1)
    with pytest.raises(ValueError, match="ERR_INVALID_BLAST_RADIUS_BPS"):
        IntentScope(("h",), ("t",), max_amount_minor=10, max_blast_radius_bps=10001)
    with pytest.raises(ValueError, match="ERR_INVALID_DNS_WINDOW"):
        TemporalAuthorityGuard({}, dns_max_queries_per_window=0)

    # Unknown issuer & bad signature
    env_unk_issuer = _mint_signed_envelope(key, "spiffe://unknown", "id1", t0)
    assert guard.register_intent(env_unk_issuer).authorized is False

    env_bad_sig = env_unk_issuer = dataclasses.replace(
        _mint_signed_envelope(key, actor, "id2", t0), signature_hex="00" * 64
    )
    assert guard.register_intent(env_bad_sig).status_code == "HALT_INVALID_INTENT_SIGNATURE"

    # Premature dispatch (now < not_before) and expired dispatch (now > expires_at)
    env_win = _mint_signed_envelope(key, actor, "id_win", t0, ttl=60, not_before_offset=10)
    guard.register_intent(env_win)
    v_prem = guard.evaluate_temporal_dispatch(
        env_win.intent_caid,
        current_epoch_sec=t0 + 5,
        live_preconditions={"balance_sufficient": True, "network_allowed": True},
        requested_host="api.stripe.com",
        requested_tool="charge_card",
        requested_amount_minor=1000,
    )
    assert v_prem.authorized is False and "HALT_INTENT_PREMATURE" in v_prem.status_code

    v_exp = guard.evaluate_temporal_dispatch(
        env_win.intent_caid,
        current_epoch_sec=t0 + 61,
        live_preconditions={"balance_sufficient": True, "network_allowed": True},
        requested_host="api.stripe.com",
        requested_tool="charge_card",
        requested_amount_minor=1000,
    )
    assert v_exp.authorized is False and "HALT_INTENT_EXPIRED" in v_exp.status_code
    assert v_exp.to_dict()["state"] == "EXPIRED_NEEDS_REAUTH"

    # Scope host, tool, and amount denials
    for idx, (host, tool, amt, expected) in enumerate(
        (
            ("evil.com", "charge_card", 100, "HALT_SCOPE_HOST_DENIED"),
            ("api.stripe.com", "drop_db", 100, "HALT_SCOPE_TOOL_DENIED"),
            ("api.stripe.com", "charge_card", 50000, "HALT_SCOPE_AMOUNT_EXCEEDED"),
        )
    ):
        e = _mint_signed_envelope(key, actor, f"id_sc_{idx}", t0)
        guard.register_intent(e)
        v = guard.evaluate_temporal_dispatch(
            e.intent_caid,
            current_epoch_sec=t0 + 1,
            live_preconditions={"balance_sufficient": True, "network_allowed": True},
            requested_host=host,
            requested_tool=tool,
            requested_amount_minor=amt,
        )
        assert v.authorized is False and expected in v.status_code

    # Resume NOT_EXECUTED permits single retry
    e_retry = _mint_signed_envelope(key, actor, "id_retry", t0, ttl=60)
    guard.register_intent(e_retry)
    guard.suspend_intent(e_retry.intent_caid)
    v_not_exec = guard.resume_and_reconcile_snapshot(
        e_retry.intent_caid,
        current_epoch_sec=t0 + 10,
        live_preconditions={"balance_sufficient": True, "network_allowed": True},
        reconciliation_probe_status="NOT_EXECUTED",
    )
    assert v_not_exec.authorized is True
    assert v_not_exec.state == "INTENT_REGISTERED"

    with pytest.raises(ValueError, match="ERR_INVALID_PROBE_STATUS"):
        guard.resume_and_reconcile_snapshot(
            e_retry.intent_caid,
            current_epoch_sec=t0 + 10,
            live_preconditions={"balance_sufficient": True, "network_allowed": True},
            reconciliation_probe_status="BAD_STATUS",
        )

    assert sha256_caid(b"raw") == sha256_caid("raw")


def test_6_epistemic_purity_no_banned_words() -> None:
    banned = [
        r"\bguarant[e]e\b",
        r"\bguarant[e]ed\b",
        r"\bbullet[p]roof\b",
        r"\benterprise-[g]rade\b",
        r"\bproduction-[s]afe\b",
        r"\b100% [s]ecure\b",
    ]
    for fpath in (
        Path("src/temporal_authority_guard.py"),
        Path("tests/test_temporal_authority_guard.py"),
    ):
        text = fpath.read_text(encoding="utf-8")
        for pat in banned:
            assert not re.findall(pat, text, re.IGNORECASE)
