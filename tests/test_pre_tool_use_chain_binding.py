#!/usr/bin/env python3
"""
Regression tests: T3 approval must be bound to the exact act, including arguments
(post-approval substitution), and to a pinned issuer key. Real Ed25519, no mocks.
"""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.biometric_hitl_gate import BiometricTelemetry, CircadianPhase
from src.pre_tool_use_chain import PreToolUseHookChain, ToolCallIntent

TEL = BiometricTelemetry(
    hrv_ms=60.0,
    cognitive_load_bps=3000,
    circadian_phase=CircadianPhase.NORMAL,
    keystroke_entropy=3.0,
    timestamp_ns=1_700_000_000_000,
)


def _intent(amount: int, recipient: str = "acct-A", capability: str = "pay.v1") -> ToolCallIntent:
    return ToolCallIntent(
        tool_name="dispatch_transfer",
        arguments={"amount_minor": amount, "recipient": recipient},
        tenant_id="t1",
        risk_tier="T3",
        is_write=True,
        agent_id="bot-1",
        capability_id=capability,
    )


def _approve(chain: PreToolUseHookChain, intent: ToolCallIntent):
    ok, reason, receipt = chain.check_approval(intent, telemetry=TEL, timestamp_ns=1)
    assert ok is True, reason
    return receipt


def test_digest_covers_every_act_field() -> None:
    base = _intent(100)
    d = base.canonical_act_digest()
    assert d.startswith("sha256:") and len(d) == 7 + 64
    assert _intent(100).canonical_act_digest() == d
    assert _intent(101).canonical_act_digest() != d
    assert _intent(100, recipient="acct-B").canonical_act_digest() != d
    assert _intent(100, capability="pay.v2").canonical_act_digest() != d
    variants = [
        ToolCallIntent("other_tool", base.arguments, "t1", "T3", True, "bot-1", "pay.v1"),
        ToolCallIntent(base.tool_name, base.arguments, "t2", "T3", True, "bot-1", "pay.v1"),
        ToolCallIntent(base.tool_name, base.arguments, "t1", "T2", True, "bot-1", "pay.v1"),
        ToolCallIntent(base.tool_name, base.arguments, "t1", "T3", False, "bot-1", "pay.v1"),
        ToolCallIntent(base.tool_name, base.arguments, "t1", "T3", True, "bot-2", "pay.v1"),
    ]
    assert len({v.canonical_act_digest() for v in variants} | {d}) == 6


def test_approved_act_dispatches() -> None:
    key = Ed25519PrivateKey.generate()
    pub = key.public_key().public_bytes_raw().hex()
    chain = PreToolUseHookChain(signing_key=key, historical_urgency_rate=0.2)
    intent = _intent(100)
    receipt = _approve(chain, intent)
    assert receipt.action_digest == intent.canonical_act_digest()
    assert chain.verify_dispatch_binding(intent, receipt, pub) == (
        True,
        "OK_DISPATCH_BOUND_TO_APPROVED_ACT",
    )


def test_argument_substitution_after_approval_is_blocked() -> None:
    # On the old code the digest omitted `arguments`, so these digests collided.
    key = Ed25519PrivateKey.generate()
    pub = key.public_key().public_bytes_raw().hex()
    chain = PreToolUseHookChain(signing_key=key, historical_urgency_rate=0.2)
    receipt = _approve(chain, _intent(100))
    swapped = _intent(9_999_999, recipient="attacker")
    assert chain.verify_dispatch_binding(swapped, receipt, pub) == (
        False,
        "HALT_POST_APPROVAL_SUBSTITUTION",
    )


def test_receipt_from_unpinned_key_is_blocked() -> None:
    trusted = Ed25519PrivateKey.generate()
    rogue = Ed25519PrivateKey.generate()
    rogue_chain = PreToolUseHookChain(signing_key=rogue, historical_urgency_rate=0.2)
    intent = _intent(100)
    receipt = _approve(rogue_chain, intent)
    assert receipt.verify_signature() is True  # self-consistent, but wrong issuer
    ok, reason = PreToolUseHookChain.verify_dispatch_binding(
        intent, receipt, trusted.public_key().public_bytes_raw().hex()
    )
    assert (ok, reason) == (False, "HALT_UNPINNED_RECEIPT_ISSUER")


def test_missing_halted_and_tampered_receipts_fail_closed() -> None:
    key = Ed25519PrivateKey.generate()
    pub = key.public_key().public_bytes_raw().hex()
    chain = PreToolUseHookChain(signing_key=key, historical_urgency_rate=0.2)
    intent = _intent(100)
    assert chain.verify_dispatch_binding(intent, None, pub) == (False, "HALT_MISSING_APPROVAL_RECEIPT")

    ok, _, halted = chain.check_approval(intent, telemetry=None, timestamp_ns=1)
    assert ok is False
    assert chain.verify_dispatch_binding(intent, halted, pub) == (False, "HALT_RECEIPT_NOT_ALLOW")

    good = _approve(chain, intent)
    import dataclasses

    forged = dataclasses.replace(good, timestamp_ns=good.timestamp_ns + 1)
    assert chain.verify_dispatch_binding(intent, forged, pub) == (False, "HALT_RECEIPT_SIGNATURE_INVALID")

    unsigned_chain = PreToolUseHookChain(signing_key=None, historical_urgency_rate=0.2)
    unsigned = _approve(unsigned_chain, intent)
    assert unsigned_chain.verify_dispatch_binding(intent, unsigned, pub) == (
        False,
        "HALT_UNPINNED_RECEIPT_ISSUER",
    )


def test_review_script_shows_act_digest() -> None:
    intent = _intent(100)
    review = PreToolUseHookChain().generate_pre_execution_review(intent)
    assert f"# Act digest: {intent.canonical_act_digest()}" in review


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
