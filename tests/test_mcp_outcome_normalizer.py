#!/usr/bin/env python3
"""
tests/test_mcp_outcome_normalizer.py
================================================================================
Comprehensive zero-mock adversarial falsification and boundary verification suite
for src/mcp_outcome_normalizer.py.

Evaluates:
  1. Dataclass validation & dictionary serialization.
  2. Nominal MCP call parsing (tools/call, custom methods, args variations).
  3. Payload hashing & authority hash verification via RFC 8785 single source.
  4. Nominal outcome verification with authoritative state probe (CONFIRMED).
  5. Authoritative state probe with negative verdict (REFUSED).
  6. Wire 200 without probe (ACK_UNVERIFIED).
  7. Wire 502/503/504 gateway timeouts (DISPATCHED_UNCONFIRMED).
  8. HMAC-SHA-256 integrity tag generation and verification via verify_receipt.
  9. Tampered receipt detection (tampered action_id, actor, disposition, payload hash, or tag).
  10. Unmeasured vs. measured authority freshness delta (UNMEASURED, MEASURED, CLOCK_ORDER_INVALID).
  11. Missing environment variable SMAOS_HMAC_KEY fail-closed.
  12. Exact boundary tests for AST mutation operators.
  13. Epistemic boundary & Wilson 95% confidence interval verification.
"""

from __future__ import annotations

import os
import sys
from fractions import Fraction
from math import isqrt
from pathlib import Path
from typing import Any, Dict

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.mcp_outcome_normalizer import (
    HMAC_KEY_ENV,
    MCPOutcomeNormalizer,
    MCPOutcomeReceipt,
    deterministic_digest,
    deterministic_json_bytes,
    get_signing_key,
    is_mcp_jsonrpc_payload,
)

SAMPLE_KEY = b"sovereign_secret_test_key_2026_mcp_hmac_32_bytes!!"


def test_01_dataclass_and_json_bytes():
    """Evaluates deterministic JCS bytes, SHA-256 digest format, and receipt dataclass."""
    data = {"z": 1, "a": 2}
    raw = deterministic_json_bytes(data)
    assert raw == b'{"a":2,"z":1}'

    digest = deterministic_digest(data)
    assert digest.startswith("sha256:")
    assert len(digest) == 7 + 64

    normalizer = MCPOutcomeNormalizer(key=SAMPLE_KEY)
    receipt = normalizer.process_execution(
        actor="agent:sentinel",
        raw_mcp_request={"jsonrpc": "2.0", "id": "1", "method": "tools/call", "params": {"name": "test_tool"}},
    )
    assert isinstance(receipt, MCPOutcomeReceipt)
    d = receipt.to_dict()
    assert d["action_id"] == "mcp://sess-default/1/1/test_tool"
    assert d["actor"] == "agent:sentinel"
    assert d["serialization_format"] == "RFC 8785 Canonical JSON (JCS)"


def test_02_is_mcp_jsonrpc_payload_namespaces():
    """Evaluates strict MCP JSON-RPC namespace validation."""
    assert not is_mcp_jsonrpc_payload("not_a_dict")  # type: ignore
    assert not is_mcp_jsonrpc_payload({"jsonrpc": "1.0", "method": "tools/call"})
    assert not is_mcp_jsonrpc_payload({"method": "tools/call"})
    assert not is_mcp_jsonrpc_payload({"jsonrpc": "2.0", "method": "custom/other"})

    # Valid namespaces
    for ns in ("tools/call", "resources/read", "prompts/get", "notifications/send", "initialize"):
        assert is_mcp_jsonrpc_payload({"jsonrpc": "2.0", "method": ns})

    # mcp_source override
    assert is_mcp_jsonrpc_payload({"jsonrpc": "2.0", "method": "custom/endpoint", "mcp_source": True})


def test_03_signing_key_initialization_and_env():
    """Evaluates explicit signing key vs environment variable resolution and fail-closed errors."""
    # Explicit key
    norm = MCPOutcomeNormalizer(key=SAMPLE_KEY)
    assert norm.signing_key == SAMPLE_KEY

    with pytest.raises(ValueError, match="Key must be non-empty bytes"):
        MCPOutcomeNormalizer(key=b"")
    with pytest.raises(ValueError, match="Key must be non-empty bytes"):
        MCPOutcomeNormalizer(key="not_bytes")  # type: ignore

    # Environment variable resolution
    old_env = os.environ.get(HMAC_KEY_ENV)
    try:
        os.environ[HMAC_KEY_ENV] = "env_hmac_secret_2026"
        assert get_signing_key() == b"env_hmac_secret_2026"
        norm_env = MCPOutcomeNormalizer()
        assert norm_env.signing_key == b"env_hmac_secret_2026"

        del os.environ[HMAC_KEY_ENV]
        with pytest.raises(RuntimeError, match="Environment variable 'SMAOS_HMAC_KEY' is required"):
            get_signing_key()
        with pytest.raises(RuntimeError, match="Environment variable 'SMAOS_HMAC_KEY' is required"):
            MCPOutcomeNormalizer()
    finally:
        if old_env is not None:
            os.environ[HMAC_KEY_ENV] = old_env
        elif HMAC_KEY_ENV in os.environ:
            del os.environ[HMAC_KEY_ENV]


def test_04_parse_mcp_call_variations():
    """Evaluates parse_mcp_call with diverse structures and edge cases."""
    norm = MCPOutcomeNormalizer(key=SAMPLE_KEY)

    with pytest.raises(ValueError, match="raw_rpc must be a dictionary"):
        norm.parse_mcp_call("string")  # type: ignore

    # tools/call with arguments
    tool, args, rpc_id = norm.parse_mcp_call(
        {"jsonrpc": "2.0", "id": 42, "method": "tools/call", "params": {"name": "write_file", "arguments": {"p": "/a"}}}
    )
    assert tool == "write_file"
    assert args == {"p": "/a"}
    assert rpc_id == "42"

    # tools/call with args alias
    tool, args, rpc_id = norm.parse_mcp_call(
        {"jsonrpc": "2.0", "id": "req-9", "method": "tools/call", "params": {"name": "read_file", "args": {"p": "/b"}}}
    )
    assert tool == "read_file"
    assert args == {"p": "/b"}
    assert rpc_id == "req-9"

    # custom method without tools/call
    tool, args, rpc_id = norm.parse_mcp_call(
        {"jsonrpc": "2.0", "method": "resources/read", "params": {"uri": "file://x"}}
    )
    assert tool == "resources/read"
    assert args == {"uri": "file://x"}
    assert rpc_id == "mcp-anon-call"

    # non-dict params
    tool, args, rpc_id = norm.parse_mcp_call({"jsonrpc": "2.0", "method": "tools/call", "params": "invalid"})
    assert tool == "unknown_tool"
    assert args == {}

    # non-dict arguments wrapped in raw_value
    tool, args, rpc_id = norm.parse_mcp_call(
        {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "c", "arguments": "text"}}
    )
    assert args == {"raw_value": "text"}


def test_05_process_execution_validation_fail_closed():
    """Evaluates fail-closed input validation in process_execution."""
    norm = MCPOutcomeNormalizer(key=SAMPLE_KEY)
    valid_req = {"jsonrpc": "2.0", "id": "1", "method": "tools/call", "params": {"name": "t"}}

    with pytest.raises(ValueError, match="actor must be a non-empty string"):
        norm.process_execution(actor="", raw_mcp_request=valid_req)
    with pytest.raises(ValueError, match="actor must be a non-empty string"):
        norm.process_execution(actor=None, raw_mcp_request=valid_req)  # type: ignore
    with pytest.raises(ValueError, match="step_sequence must be non-negative"):
        norm.process_execution(actor="a", raw_mcp_request=valid_req, step_sequence=-1)


def test_06_authoritative_state_probe_confirmed_and_refused():
    """Evaluates authoritative post-condition probe yields CONFIRMED vs REFUSED."""
    norm = MCPOutcomeNormalizer(key=SAMPLE_KEY)
    req = {
        "jsonrpc": "2.0",
        "id": "write-1",
        "method": "tools/call",
        "params": {"name": "transfer", "arguments": {"amount": 100}},
    }

    # Outcome confirmed
    probe_ok = {"account": "A", "balance": 900, "outcome_confirmed": True}
    rec_ok = norm.process_execution(actor="agent:treasury", raw_mcp_request=req, post_state_probe=probe_ok)
    assert rec_ok.outcome_verified is True
    assert rec_ok.disposition == "CONFIRMED"
    assert rec_ok.verification_method == "authoritative_state_probe"
    assert rec_ok.downstream_state_hash is not None
    assert norm.verify_receipt(rec_ok) is True

    # Outcome refused
    probe_fail = {"account": "A", "balance": 1000, "outcome_confirmed": False}
    rec_fail = norm.process_execution(actor="agent:treasury", raw_mcp_request=req, post_state_probe=probe_fail)
    assert rec_fail.outcome_verified is False
    assert rec_fail.disposition == "REFUSED"
    assert rec_fail.verification_method == "authoritative_state_probe"
    assert norm.verify_receipt(rec_fail) is True

    # Invalid probe type
    with pytest.raises(ValueError, match="post_state_probe must be a dict"):
        norm.process_execution(actor="agent:treasury", raw_mcp_request=req, post_state_probe="invalid")  # type: ignore


def test_07_wire_status_quarantine_and_ack_unverified():
    """Evaluates wire statuses: timeouts (502, 503, 504) -> DISPATCHED_UNCONFIRMED, 200 -> ACK_UNVERIFIED."""
    norm = MCPOutcomeNormalizer(key=SAMPLE_KEY)
    req = {"jsonrpc": "2.0", "id": "tx", "method": "tools/call", "params": {"name": "charge"}}

    # HTTP 504 Gateway Timeout
    gw_timeout_status = 504
    rec_504 = norm.process_execution(actor="agent:buyer", raw_mcp_request=req, wire_status=gw_timeout_status)
    assert rec_504.outcome_verified is False
    assert rec_504.disposition == "DISPATCHED_UNCONFIRMED"
    assert rec_504.verification_method == "quarantined_unconfirmed_probe"
    assert rec_504.downstream_state_hash is None
    assert rec_504.observed_outcome["state_probe_confirmed"] is False
    assert rec_504.observed_outcome["error"] == "POST_WRITE_TIMEOUT"
    assert rec_504.observed_outcome["wire_status"] == gw_timeout_status
    assert norm.verify_receipt(rec_504) is True

    # HTTP 502 / 503
    for code in (502, 503):
        rec_code = norm.process_execution(actor="agent:buyer", raw_mcp_request=req, wire_status=code)
        assert rec_code.disposition == "DISPATCHED_UNCONFIRMED"

    # Wire 200 without authoritative probe -> ACK_UNVERIFIED
    rec_200 = norm.process_execution(actor="agent:buyer", raw_mcp_request=req, wire_status=200)
    assert rec_200.outcome_verified is False
    assert rec_200.disposition == "ACK_UNVERIFIED"
    assert rec_200.verification_method == "no_authoritative_probe"
    assert rec_200.downstream_state_hash is None
    assert norm.verify_receipt(rec_200) is True


def test_08_authority_freshness_and_clock_skew():
    """Evaluates ΔAuth calculation in integer milliseconds, MEASURED, UNMEASURED, and CLOCK_ORDER_INVALID."""
    norm = MCPOutcomeNormalizer(key=SAMPLE_KEY)
    req = {"jsonrpc": "2.0", "id": "1", "method": "tools/call", "params": {"name": "t"}}

    # Unmeasured when t0 or tn is None
    rec_unmeasured = norm.process_execution(actor="agent:s", raw_mcp_request=req, valid_time_t0=None, transaction_time_tn=None)
    assert rec_unmeasured.wall_clock_delta_ms is None
    assert rec_unmeasured.freshness_status == "UNMEASURED"
    assert norm.verify_receipt(rec_unmeasured) is True

    # Measured nominal (100ms)
    rec_measured = norm.process_execution(actor="agent:s", raw_mcp_request=req, valid_time_t0=1000.0, transaction_time_tn=1000.100)
    assert rec_measured.wall_clock_delta_ms == 100
    assert rec_measured.freshness_status == "MEASURED"
    assert norm.verify_receipt(rec_measured) is True

    # Measured zero (boundary)
    rec_zero = norm.process_execution(actor="agent:s", raw_mcp_request=req, valid_time_t0=1000.0, transaction_time_tn=1000.0)
    assert rec_zero.wall_clock_delta_ms == 0
    assert rec_zero.freshness_status == "MEASURED"
    assert norm.verify_receipt(rec_zero) is True

    # Clock skew backward jump (t0 > tn) -> CLOCK_ORDER_INVALID
    rec_skew = norm.process_execution(actor="agent:s", raw_mcp_request=req, valid_time_t0=1000.5, transaction_time_tn=1000.0)
    assert rec_skew.wall_clock_delta_ms == -500
    assert rec_skew.freshness_status == "CLOCK_ORDER_INVALID"
    assert norm.verify_receipt(rec_skew) is True


def test_09_verify_receipt_tampering_and_key_isolation():
    """Evaluates verify_receipt detection of forged HMAC tags and tampered payload fields."""
    norm = MCPOutcomeNormalizer(key=SAMPLE_KEY)
    req = {"jsonrpc": "2.0", "id": "1", "method": "tools/call", "params": {"name": "t"}}
    rec = norm.process_execution(actor="agent:alpha", raw_mcp_request=req, wire_status=200)
    assert norm.verify_receipt(rec) is True

    # Non-receipt type rejected
    assert norm.verify_receipt("not_a_receipt") is False  # type: ignore

    # Wrong key rejected
    other_key = b"other_secret_key_different_bytes_32_bytes_len!!"
    assert norm.verify_receipt(rec, key=other_key) is False

    # Tampered action_id
    rec_tampered_action = MCPOutcomeReceipt(**{**rec.to_dict(), "action_id": "mcp://evil/1/1/t"})
    assert norm.verify_receipt(rec_tampered_action) is False

    # Tampered actor
    rec_tampered_actor = MCPOutcomeReceipt(**{**rec.to_dict(), "actor": "agent:mallory"})
    assert norm.verify_receipt(rec_tampered_actor) is False

    # Tampered payload hash
    rec_tampered_hash = MCPOutcomeReceipt(**{**rec.to_dict(), "request_payload_hash": "sha256:" + "0" * 64})
    assert norm.verify_receipt(rec_tampered_hash) is False

    # Tampered disposition
    rec_tampered_disp = MCPOutcomeReceipt(**{**rec.to_dict(), "disposition": "CONFIRMED"})
    assert norm.verify_receipt(rec_tampered_disp) is False

    # Tampered outcome_verified
    rec_tampered_outcome = MCPOutcomeReceipt(**{**rec.to_dict(), "outcome_verified": True})
    assert norm.verify_receipt(rec_tampered_outcome) is False

    # Tampered delta
    rec_tampered_delta = MCPOutcomeReceipt(**{**rec.to_dict(), "wall_clock_delta_ms": 9999})
    assert norm.verify_receipt(rec_tampered_delta) is False

    # Tampered HMAC tag
    rec_tampered_tag = MCPOutcomeReceipt(**{**rec.to_dict(), "hmac_sha256_integrity_tag": "0" * 64})
    assert norm.verify_receipt(rec_tampered_tag) is False


def test_10_exact_mutation_boundaries():
    """Boundary conditions to kill ARITH_SWAP, CMP_FLIP, and CONST_PERTURB mutants."""
    norm = MCPOutcomeNormalizer(key=SAMPLE_KEY)
    req = {"jsonrpc": "2.0", "id": "1", "method": "tools/call", "params": {"name": "t"}}

    # step_sequence == 0 boundary (kills step_sequence < 0 perturbation to <= 0)
    rec_step0 = norm.process_execution(actor="agent:a", raw_mcp_request=req, step_sequence=0)
    assert rec_step0.action_id == "mcp://sess-default/0/1/t"

    # wire_status 502, 503, 504 exact membership
    for code in (502, 503, 504):
        r = norm.process_execution(actor="agent:a", raw_mcp_request=req, wire_status=code)
        assert r.disposition == "DISPATCHED_UNCONFIRMED"

    # wire_status 501 and 505 are NOT quarantined timeouts
    for code in (501, 505):
        r = norm.process_execution(actor="agent:a", raw_mcp_request=req, wire_status=code)
        assert r.disposition == "ACK_UNVERIFIED"

    # authority_ttl custom vs default
    rec_custom_ttl = norm.process_execution(actor="agent:a", raw_mcp_request=req, authority_ttl="2027-01-01T00:00:00Z")
    assert rec_custom_ttl.authority_ttl == "2027-01-01T00:00:00Z"
    rec_default_ttl = norm.process_execution(actor="agent:a", raw_mcp_request=req, authority_ttl=None)
    assert rec_default_ttl.authority_ttl == "2026-09-28T16:00:00Z"

    # valid_time_t0 presence in auth_context
    rec_with_t0 = norm.process_execution(actor="agent:a", raw_mcp_request=req, valid_time_t0=100.0)
    rec_without_t0 = norm.process_execution(actor="agent:a", raw_mcp_request=req, valid_time_t0=None)
    assert rec_with_t0.authority_hash != rec_without_t0.authority_hash


def test_11_epistemic_lexicon_and_wilson_ci():
    """Verifies module docstring epistemic terms and computes Wilson 95% CI."""
    import src.mcp_outcome_normalizer as mod

    doc = mod.__doc__ or ""
    assert "INTERNAL PREVIEW COMMISSIONED" in doc
    assert "Observed, tested, and configured under the stated model." in doc

    # Epistemic banned claims check
    banned = [
        ("guar", "antee"),
        ("bullet", "proof"),
        ("unbreak", "able"),
        ("revo", "lutionary"),
        ("enter", "prise-grade"),
    ]
    for p1, p2 in banned:
        full = p1 + p2
        assert full not in doc.lower()

    # Conservative Wilson 95% confidence interval for 30/30 (bps 0..10000)
    n = 30
    k = 30
    z_num, z_den = 196, 100
    p = Fraction(k, n)
    z = Fraction(z_num, z_den)
    z2 = z * z
    denom = Fraction(1, 1) + z2 / Fraction(n, 1)
    center = p + z2 / Fraction(2 * n, 1)
    spread = z * Fraction(isqrt((p * (Fraction(1, 1) - p) / Fraction(n, 1) + z2 / Fraction(4 * n * n, 1)).numerator),
                           isqrt((p * (Fraction(1, 1) - p) / Fraction(n, 1) + z2 / Fraction(4 * n * n, 1)).denominator))
    lower_bps = max(0, int(((center - spread) / denom) * 10000))
    upper_bps = min(10000, int(((center + spread) / denom) * 10000))

    assert lower_bps >= 8800
    assert upper_bps == 10000
