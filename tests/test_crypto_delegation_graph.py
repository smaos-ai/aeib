#!/usr/bin/env python3
"""
Falsification & Conformance Suite for src/crypto_delegation_graph.py.
Evaluated under the stated model with zero mocks and real Ed25519 signatures.
"""

from __future__ import annotations

from pathlib import Path
import re
import time

from cryptography.hazmat.primitives.asymmetric import ed25519
import pytest

from src.crypto_delegation_graph import (
    CryptoDelegationGraph,
    DelegationToken,
    ScopeBoundary,
)


def _sign(payload_bytes: bytes, priv_key: ed25519.Ed25519PrivateKey) -> str:
    return priv_key.sign(payload_bytes).hex()


def test_1_monotonic_scope_and_chain_of_custody() -> None:
    human_priv = ed25519.Ed25519PrivateKey.generate()
    agent_a_priv = ed25519.Ed25519PrivateKey.generate()
    agent_b_priv = ed25519.Ed25519PrivateKey.generate()

    trust_store = {
        "spiffe://human/root": human_priv.public_key(),
        "spiffe://agent/a": agent_a_priv.public_key(),
        "spiffe://agent/b": agent_b_priv.public_key(),
    }
    graph = CryptoDelegationGraph(trust_store)
    now = int(time.time())

    # 1. Human issues root token to Agent A
    scope_a = ScopeBoundary(
        allowed_egress_hosts=("api.stripe.com", "db.internal"),
        allowed_tools=("http_post", "db_query"),
        max_financial_minor=10000,
        max_blast_radius_bps=5000,
    )
    token_a_unsigned = DelegationToken(
        issuer_spiffe_id="spiffe://human/root",
        subject_spiffe_id="spiffe://agent/a",
        scope=scope_a,
        issued_at_epoch_sec=now,
        expires_at_epoch_sec=now + 3600,
        parent_token_caid="GENESIS",
    )
    token_a = token_a_unsigned.with_signature(
        _sign(token_a_unsigned.canonical_bytes(), human_priv)
    )
    caid_a = graph.register_token(token_a)

    # 2. Agent A delegates to Agent B (monotonic subset)
    scope_b = ScopeBoundary(
        allowed_egress_hosts=("api.stripe.com",),
        allowed_tools=("http_post",),
        max_financial_minor=5000,
        max_blast_radius_bps=2000,
    )
    token_b_unsigned = DelegationToken(
        issuer_spiffe_id="spiffe://agent/a",
        subject_spiffe_id="spiffe://agent/b",
        scope=scope_b,
        issued_at_epoch_sec=now + 10,
        expires_at_epoch_sec=now + 1800,
        parent_token_caid=caid_a,
    )
    token_b = token_b_unsigned.with_signature(
        _sign(token_b_unsigned.canonical_bytes(), agent_a_priv)
    )
    caid_b = graph.register_token(token_b)

    # 3. Valid action within scope & TTL succeeds
    v_ok = graph.evaluate_action(
        "spiffe://agent/b",
        caid_b,
        "api.stripe.com",
        "http_post",
        4000,
        now + 20,
        blast_radius_bps=1000,
    )
    assert v_ok.authorized is True
    assert v_ok.to_dict()["authorized"] is True

    # 4. Authorization laundering (host, tool, amount, or blast radius outside scope) is blocked
    v_bad_host = graph.evaluate_action(
        "spiffe://agent/b", caid_b, "evil.com", "http_post", 1000, now + 20
    )
    assert v_bad_host.authorized is False and "HALT_HOST_DENIED" in v_bad_host.reason_code

    v_bad_tool = graph.evaluate_action(
        "spiffe://agent/b", caid_b, "api.stripe.com", "db_query", 1000, now + 20
    )
    assert v_bad_tool.authorized is False and "HALT_TOOL_DENIED" in v_bad_tool.reason_code

    v_bad_amount = graph.evaluate_action(
        "spiffe://agent/b", caid_b, "api.stripe.com", "http_post", 9000, now + 20
    )
    assert v_bad_amount.authorized is False and "HALT_AMOUNT_EXCEEDED" in v_bad_amount.reason_code

    v_bad_blast = graph.evaluate_action(
        "spiffe://agent/b",
        caid_b,
        "api.stripe.com",
        "http_post",
        1000,
        now + 20,
        blast_radius_bps=3500,
    )
    assert (
        v_bad_blast.authorized is False
        and "HALT_BLAST_RADIUS_EXCEEDED" in v_bad_blast.reason_code
    )

    # 5. Child attempting to outlive Parent TTL is rejected at registration
    token_b_outlive_unsigned = DelegationToken(
        issuer_spiffe_id="spiffe://agent/a",
        subject_spiffe_id="spiffe://agent/b",
        scope=scope_b,
        issued_at_epoch_sec=now + 10,
        expires_at_epoch_sec=now + 7200,
        parent_token_caid=caid_a,
    )
    token_b_outlive = token_b_outlive_unsigned.with_signature(
        _sign(token_b_outlive_unsigned.canonical_bytes(), agent_a_priv)
    )
    with pytest.raises(ValueError, match="HALT_CHILD_OUTLIVES_PARENT_TTL"):
        graph.register_token(token_b_outlive)


def test_2_temporal_expiration_and_error_branches() -> None:
    human_priv = ed25519.Ed25519PrivateKey.generate()
    agent_a_priv = ed25519.Ed25519PrivateKey.generate()
    trust_store = {
        "spiffe://human/root": human_priv.public_key(),
        "spiffe://agent/a": agent_a_priv.public_key(),
    }
    graph = CryptoDelegationGraph(trust_store)
    now = 1_800_000_000

    with pytest.raises(ValueError, match="ERR_NEGATIVE_FINANCIAL_MINOR"):
        ScopeBoundary(("h",), ("t",), -1, 1000)
    with pytest.raises(ValueError, match="ERR_INVALID_BLAST_RADIUS_BPS"):
        ScopeBoundary(("h",), ("t",), 10, 10001)

    scope = ScopeBoundary(("api.com",), ("get",), 100, 1000)
    token_unsigned = DelegationToken(
        "spiffe://human/root", "spiffe://agent/a", scope, now - 100, now - 50, "GENESIS"
    )
    token = token_unsigned.with_signature(_sign(token_unsigned.canonical_bytes(), human_priv))
    caid = graph.register_token(token)

    # Expired token rejected
    v_exp = graph.evaluate_action("spiffe://agent/a", caid, "api.com", "get", 10, now)
    assert v_exp.authorized is False and v_exp.reason_code == "HALT_TOKEN_EXPIRED"

    # Premature evaluation (current_time < issued_at)
    v_prem = graph.evaluate_action("spiffe://agent/a", caid, "api.com", "get", 10, now - 200)
    assert v_prem.authorized is False and v_prem.reason_code == "HALT_TOKEN_NOT_YET_VALID"

    # Subject mismatch & unknown token
    v_sub = graph.evaluate_action("spiffe://agent/wrong", caid, "api.com", "get", 10, now - 80)
    assert v_sub.authorized is False and v_sub.reason_code == "HALT_SUBJECT_MISMATCH"
    v_unk = graph.evaluate_action("spiffe://agent/a", "sha256:missing", "api.com", "get", 10, now)
    assert v_unk.authorized is False and v_unk.reason_code == "HALT_UNKNOWN_LEAF_TOKEN"

    # Registration failures: unknown issuer, bad signature, orphan parent, issuer mismatch, scope escalation
    with pytest.raises(ValueError, match="HALT_UNKNOWN_ISSUER"):
        graph.register_token(
            DelegationToken("spiffe://unknown", "spiffe://agent/a", scope, now, now + 10, "GENESIS")
        )
    with pytest.raises(ValueError, match="HALT_INVALID_DELEGATION_SIGNATURE"):
        graph.register_token(token_unsigned.with_signature("00" * 64))
    with pytest.raises(ValueError, match="HALT_INVALID_TOKEN_TTL_WINDOW"):
        t_ttl = DelegationToken(
            "spiffe://human/root", "spiffe://agent/a", scope, now + 50, now + 10, "GENESIS"
        )
        graph.register_token(t_ttl.with_signature(_sign(t_ttl.canonical_bytes(), human_priv)))
    with pytest.raises(ValueError, match="HALT_ORPHAN_TOKEN"):
        t_orph = DelegationToken(
            "spiffe://agent/a", "spiffe://agent/b", scope, now, now + 10, "sha256:none"
        )
        graph.register_token(t_orph.with_signature(_sign(t_orph.canonical_bytes(), agent_a_priv)))

    # Register valid parent at [now, now + 100]
    p_un = DelegationToken(
        "spiffe://human/root", "spiffe://agent/a", scope, now, now + 100, "GENESIS"
    )
    p_caid = graph.register_token(p_un.with_signature(_sign(p_un.canonical_bytes(), human_priv)))

    # Issuer mismatch (human/root trying to issue child of p_caid whose subject is agent/a)
    with pytest.raises(ValueError, match="HALT_DELEGATION_CHAIN_ISSUER_MISMATCH"):
        t_mis = DelegationToken(
            "spiffe://human/root", "spiffe://agent/b", scope, now + 5, now + 50, p_caid
        )
        graph.register_token(t_mis.with_signature(_sign(t_mis.canonical_bytes(), human_priv)))

    # Issued before parent
    with pytest.raises(ValueError, match="HALT_ISSUED_BEFORE_PARENT"):
        t_bef = DelegationToken(
            "spiffe://agent/a", "spiffe://agent/b", scope, now - 5, now + 50, p_caid
        )
        graph.register_token(t_bef.with_signature(_sign(t_bef.canonical_bytes(), agent_a_priv)))

    # Parent expired at issuance
    with pytest.raises(ValueError, match="HALT_PARENT_EXPIRED_AT_ISSUANCE"):
        t_exp_p = DelegationToken(
            "spiffe://agent/a", "spiffe://agent/b", scope, now + 200, now + 250, p_caid
        )
        graph.register_token(t_exp_p.with_signature(_sign(t_exp_p.canonical_bytes(), agent_a_priv)))

    # Scope monotonicity violation at registration
    bad_scope = ScopeBoundary(("api.com", "extra.com"), ("get",), 100, 1000)
    with pytest.raises(ValueError, match="HALT_SCOPE_MONOTONICITY_VIOLATION"):
        t_esc = DelegationToken(
            "spiffe://agent/a", "spiffe://agent/b", bad_scope, now + 5, now + 50, p_caid
        )
        graph.register_token(t_esc.with_signature(_sign(t_esc.canonical_bytes(), agent_a_priv)))

    # Broken ancestor chain at evaluation time (if parent evicted from registry)
    c_un = DelegationToken(
        "spiffe://agent/a", "spiffe://agent/b", scope, now + 5, now + 50, p_caid
    )
    c_caid = graph.register_token(
        c_un.with_signature(_sign(c_un.canonical_bytes(), agent_a_priv))
    )
    del graph._token_registry[p_caid]
    v_broken = graph.evaluate_action("spiffe://agent/b", c_caid, "api.com", "get", 10, now + 10)
    assert v_broken.authorized is False and v_broken.reason_code == "HALT_BROKEN_ANCESTOR_CHAIN"

    # Scope subset false branches (host, tool, amount, blast_radius)
    assert ScopeBoundary(("evil.com",), ("get",), 100, 1000).is_subset_of(scope) is False
    assert ScopeBoundary(("api.com",), ("post",), 100, 1000).is_subset_of(scope) is False
    assert ScopeBoundary(("api.com",), ("get",), 200, 1000).is_subset_of(scope) is False
    assert ScopeBoundary(("api.com",), ("get",), 100, 2000).is_subset_of(scope) is False


def test_4_zero_blast_radius_default_and_boundary() -> None:
    import inspect

    sig = inspect.signature(CryptoDelegationGraph.evaluate_action)
    assert sig.parameters["blast_radius_bps"].default == 0

    human_priv = ed25519.Ed25519PrivateKey.generate()
    agent_priv = ed25519.Ed25519PrivateKey.generate()
    trust_store = {
        "spiffe://human/root": human_priv.public_key(),
        "spiffe://agent/worker": agent_priv.public_key(),
    }
    graph = CryptoDelegationGraph(trust_store)
    now = int(time.time())
    zero_scope = ScopeBoundary(
        allowed_egress_hosts=("api.internal",),
        allowed_tools=("read_only",),
        max_financial_minor=0,
        max_blast_radius_bps=0,
    )
    t_un = DelegationToken(
        issuer_spiffe_id="spiffe://human/root",
        subject_spiffe_id="spiffe://agent/worker",
        scope=zero_scope,
        issued_at_epoch_sec=now,
        expires_at_epoch_sec=now + 60,
        parent_token_caid="GENESIS",
    )
    t = t_un.with_signature(_sign(t_un.canonical_bytes(), human_priv))
    caid = graph.register_token(t)

    # Calling without blast_radius_bps must evaluate with default 0 bps and succeed
    v_def = graph.evaluate_action(
        "spiffe://agent/worker",
        caid,
        "api.internal",
        "read_only",
        0,
        now,
    )
    assert v_def.authorized is True
    assert v_def.reason_code == "OK_AUTHORITY_VERIFIED"


def test_3_epistemic_purity_no_banned_words() -> None:
    banned = [
        r"\bguarant[e]e\b",
        r"\bguarant[e]ed\b",
        r"\bbullet[p]roof\b",
        r"\benterprise-[g]rade\b",
        r"\bproduction-[s]afe\b",
        r"\b100% [s]ecure\b",
    ]
    for fpath in (
        Path("src/crypto_delegation_graph.py"),
        Path("tests/test_crypto_delegation_graph.py"),
    ):
        text = fpath.read_text(encoding="utf-8")
        for pat in banned:
            assert not re.findall(pat, text, re.IGNORECASE)
