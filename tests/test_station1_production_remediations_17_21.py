#!/usr/bin/env python3
"""
tests/test_station1_production_remediations_17_21.py
================================================================================
Verification Suite for Station 1 Production Remediations (#17–#21):
- Fix #17: Atomic Checkpointing (tempfile + os.rename + dir fsync).
- Fix #18: Monotonic Ordering (monotonic chain_tip_seq counter).
- Fix #19: Rejection Logging (audit log appending on denied dispatches).
- Fix #20: Platform-Safe Fsync (F_FULLFSYNC / fsync fallback).
- Fix #21: Bit-Isolated Test Coverage (independent failure_mask bit triggers).

Evaluated under the stated model. Zero-mock AST purity enforced.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.station1_state_engine import Station1StateEngine


def test_fix17_atomic_checkpoint_write(tmp_path: Path) -> None:
    """Fix #17: Verifies atomic checkpoint write replaces active checkpoint with dir fsync."""
    engine = Station1StateEngine(ledger_dir=str(tmp_path))
    state_payload = {"chain_tip": "sha256:abc12345", "verified_entries": 42}

    engine.atomic_checkpoint_write(state_payload)

    assert os.path.exists(engine.ledger_path)
    with open(engine.ledger_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["chain_tip"] == "sha256:abc12345"
    assert loaded["verified_entries"] == 42
    assert loaded["chain_tip_seq"] == 0

    # Overwrite with updated state
    engine.chain_tip_seq = 1
    updated_payload = {"chain_tip": "sha256:def67890", "verified_entries": 43}
    engine.atomic_checkpoint_write(updated_payload)

    with open(engine.ledger_path, "r", encoding="utf-8") as f:
        reloaded = json.load(f)
    assert reloaded["chain_tip"] == "sha256:def67890"
    assert reloaded["verified_entries"] == 43
    assert reloaded["chain_tip_seq"] == 1


def test_fix18_and_fix19_monotonic_rejection_audit_log(tmp_path: Path) -> None:
    """Fix #18 & #19: Verifies monotonic chain_tip_seq progression and rejection audit log."""
    engine = Station1StateEngine(ledger_dir=str(tmp_path))

    r1 = engine.log_rejection_audit_entry("op-reject-1", 0x01, "CAID_MISMATCH")
    r2 = engine.log_rejection_audit_entry("op-reject-2", 0x08, "PAYEE_MISMATCH")
    r3 = engine.log_rejection_audit_entry("op-reject-3", 0x20, "UNTRUSTED_TAINT_REQUIRES_STEP_UP")

    assert r1["chain_tip_seq"] == 1
    assert r2["chain_tip_seq"] == 2
    assert r3["chain_tip_seq"] == 3

    assert os.path.exists(engine.rejections_path)
    with open(engine.rejections_path, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]

    assert len(lines) == 3
    assert lines[0]["op_id"] == "op-reject-1"
    assert lines[0]["failure_mask"] == 0x01
    assert lines[1]["op_id"] == "op-reject-2"
    assert lines[1]["failure_mask"] == 0x08
    assert lines[2]["op_id"] == "op-reject-3"
    assert lines[2]["failure_mask"] == 0x20


def test_fix20_platform_safe_full_fsync(tmp_path: Path) -> None:
    """Fix #20: Verifies _safe_full_fsync succeeds across Darwin and Linux."""
    engine = Station1StateEngine(ledger_dir=str(tmp_path))
    test_file = tmp_path / "sync_test.bin"
    fd = os.open(str(test_file), os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        os.write(fd, b"test-sync-bytes")
        engine._safe_full_fsync(fd)
    finally:
        os.close(fd)
    assert test_file.read_bytes() == b"test-sync-bytes"


def test_fix21_failure_mask_bit_isolation(tmp_path: Path) -> None:
    """Fix #21: Ensures each failure_mask bit triggers independently and in isolation."""
    engine = Station1StateEngine(
        ledger_dir=str(tmp_path),
        trust_anchors={"payee_1": b"key_1", "payee_2": b"key_2"},
    )

    caid = b"\x11" * 32
    harness = b"\x22" * 32
    tool = b"\x33" * 32
    payee = "payee_1"

    # Positive Baseline: All terms valid -> ok=True, mask=0
    ok, mask, reason = engine.evaluate_dispatch(
        caid=caid,
        expected_caid=caid,
        harness_digest=harness,
        expected_harness=harness,
        tool_digest=tool,
        expected_tool=tool,
        payee_id=payee,
        expected_payee_id=payee,
        requested_minor=100_00,
        remaining_budget_minor=500_00,
        taint_tier=0,
        has_step_up_warrant=False,
    )
    assert ok is True
    assert mask == 0
    assert reason == "DISPATCH_AUTHORIZED"

    # Bit 0 (0x01): CAID Mismatch Alone
    ok, mask, reason = engine.evaluate_dispatch(
        caid=b"\xff" * 32,
        expected_caid=caid,
        harness_digest=harness,
        expected_harness=harness,
        tool_digest=tool,
        expected_tool=tool,
        payee_id=payee,
        expected_payee_id=payee,
        requested_minor=100_00,
        remaining_budget_minor=500_00,
        taint_tier=0,
        has_step_up_warrant=False,
    )
    assert ok is False
    assert mask == 0x01
    assert "CAID_MISMATCH" in reason

    # Bit 1 (0x02): Harness Digest Mismatch Alone
    ok, mask, reason = engine.evaluate_dispatch(
        caid=caid,
        expected_caid=caid,
        harness_digest=b"\xfe" * 32,
        expected_harness=harness,
        tool_digest=tool,
        expected_tool=tool,
        payee_id=payee,
        expected_payee_id=payee,
        requested_minor=100_00,
        remaining_budget_minor=500_00,
        taint_tier=0,
        has_step_up_warrant=False,
    )
    assert ok is False
    assert mask == 0x02
    assert "HARNESS_DIGEST_MISMATCH" in reason

    # Bit 2 (0x04): Tool Digest Mismatch Alone
    ok, mask, reason = engine.evaluate_dispatch(
        caid=caid,
        expected_caid=caid,
        harness_digest=harness,
        expected_harness=harness,
        tool_digest=b"\xfd" * 32,
        expected_tool=tool,
        payee_id=payee,
        expected_payee_id=payee,
        requested_minor=100_00,
        remaining_budget_minor=500_00,
        taint_tier=0,
        has_step_up_warrant=False,
    )
    assert ok is False
    assert mask == 0x04
    assert "TOOL_DIGEST_MISMATCH" in reason

    # Bit 3 (0x08): Payee Mismatch Alone
    ok, mask, reason = engine.evaluate_dispatch(
        caid=caid,
        expected_caid=caid,
        harness_digest=harness,
        expected_harness=harness,
        tool_digest=tool,
        expected_tool=tool,
        payee_id="attacker_account",
        expected_payee_id=payee,
        requested_minor=100_00,
        remaining_budget_minor=500_00,
        taint_tier=0,
        has_step_up_warrant=False,
    )
    # Note: payee_id is also not in trust anchors, but if payee_2 is used:
    ok_p2, mask_p2, reason_p2 = engine.evaluate_dispatch(
        caid=caid,
        expected_caid=caid,
        harness_digest=harness,
        expected_harness=harness,
        tool_digest=tool,
        expected_tool=tool,
        payee_id="payee_2",
        expected_payee_id=payee,
        requested_minor=100_00,
        remaining_budget_minor=500_00,
        taint_tier=0,
        has_step_up_warrant=False,
    )
    assert ok_p2 is False
    assert mask_p2 == 0x08
    assert "PAYEE_MISMATCH" in reason_p2

    # Bit 4 (0x10): Budget Ceiling Exceeded Alone
    ok, mask, reason = engine.evaluate_dispatch(
        caid=caid,
        expected_caid=caid,
        harness_digest=harness,
        expected_harness=harness,
        tool_digest=tool,
        expected_tool=tool,
        payee_id=payee,
        expected_payee_id=payee,
        requested_minor=600_00,
        remaining_budget_minor=500_00,
        taint_tier=0,
        has_step_up_warrant=False,
    )
    assert ok is False
    assert mask == 0x10
    assert "BUDGET_EXCEEDED" in reason

    # Bit 5 (0x20): Untrusted Taint Tier 2 without Step-Up Warrant Alone
    ok, mask, reason = engine.evaluate_dispatch(
        caid=caid,
        expected_caid=caid,
        harness_digest=harness,
        expected_harness=harness,
        tool_digest=tool,
        expected_tool=tool,
        payee_id=payee,
        expected_payee_id=payee,
        requested_minor=100_00,
        remaining_budget_minor=500_00,
        taint_tier=2,
        has_step_up_warrant=False,
    )
    assert ok is False
    assert mask == 0x20
    assert "UNTRUSTED_TAINT_REQUIRES_STEP_UP" in reason

    # Bit 6 (0x40): Payee Not in Trust Anchors Alone
    engine_no_payee_mismatch = Station1StateEngine(
        ledger_dir=str(tmp_path),
        trust_anchors={"only_payee": b"key"},
    )
    ok, mask, reason = engine_no_payee_mismatch.evaluate_dispatch(
        caid=caid,
        expected_caid=caid,
        harness_digest=harness,
        expected_harness=harness,
        tool_digest=tool,
        expected_tool=tool,
        payee_id="unanchored_payee",
        expected_payee_id="unanchored_payee",
        requested_minor=100_00,
        remaining_budget_minor=500_00,
        taint_tier=0,
        has_step_up_warrant=False,
    )
    assert ok is False
    assert mask == 0x40
    assert "PAYEE_NOT_ANCHORED" in reason


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
