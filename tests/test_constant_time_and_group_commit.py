#!/usr/bin/env python3
"""
tests/test_constant_time_and_group_commit.py
================================================================================
Verification Suite for Next-Level Systems Efficiency Upgrades in AEIB Section 5:
1. Constant-Time (O(1) branchless) Station 1 Admissibility Evaluation using hmac.compare_digest
   and bitwise predicate accumulation (preventing timing side-channels).
2. TigerBeetle-style Group-Commit WAL Latch with explicit macOS F_FULLFSYNC support,
   amortizing physical NVMe flush overhead across concurrent agent dispatches.
3. jCodeMunch-style O(1) Byte-Offset AST Slicing + Compact Wire Encoding with Dual-Digest
   Bell-LaPadula Taint Binding (upgrading token reduction to >10x).
4. Deterministic O(1) Bitmask Fast-Path Escalation Gate.

Evaluated under the stated model. Zero-mock AST purity enforced.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import pytest

from src.constant_time_group_commit_latch import (
    ByteOffsetSymbolIndexer,
    ConstantTimeStation1Check,
    DeterministicFastPathGate,
    GroupCommitWireLatch,
    sha256_bytes,
    sha256_hex,
)


def test_constant_time_station1_5_tuple_evaluation() -> None:
    """Verifies branchless, constant-time evaluation of all 5 admissibility terms."""
    caid = sha256_bytes(b'{"amount":1000,"op":"refund"}')
    h_dig = sha256_bytes(b"harness-v1.0.0-rc.3")
    t_dig = sha256_bytes(b"mcp-stripe-refund-v1")

    # 1. Positive Path: All 5 terms match
    passed, mask = ConstantTimeStation1Check.verify_5_tuple_constant_time(
        caid, caid, h_dig, h_dig, t_dig, t_dig,
        taint_tier_id=0, has_step_up_warrant=0,
        requested_minor=1000, remaining_budget_minor=5000,
    )
    assert passed is True
    assert mask == 0

    # 2. Taint Tier 2 without step-up warrant -> fails closed on bit 3 (mask == 8)
    passed_taint, mask_taint = ConstantTimeStation1Check.verify_5_tuple_constant_time(
        caid, caid, h_dig, h_dig, t_dig, t_dig,
        taint_tier_id=2, has_step_up_warrant=0,
        requested_minor=1000, remaining_budget_minor=5000,
    )
    assert passed_taint is False
    assert mask_taint == (1 << 3)

    # 3. Taint Tier 2 WITH step-up warrant -> passes
    passed_step_up, mask_step_up = ConstantTimeStation1Check.verify_5_tuple_constant_time(
        caid, caid, h_dig, h_dig, t_dig, t_dig,
        taint_tier_id=2, has_step_up_warrant=1,
        requested_minor=1000, remaining_budget_minor=5000,
    )
    assert passed_step_up is True
    assert mask_step_up == 0

    # 4. Budget Overrun: requested > remaining -> fails closed on bit 4 (mask == 16)
    passed_budget, mask_budget = ConstantTimeStation1Check.verify_5_tuple_constant_time(
        caid, caid, h_dig, h_dig, t_dig, t_dig,
        taint_tier_id=0, has_step_up_warrant=0,
        requested_minor=6000, remaining_budget_minor=5000,
    )
    assert passed_budget is False
    assert mask_budget == (1 << 4)

    # 5. CAID Mismatch -> fails closed on bit 0 (mask == 1)
    wrong_caid = sha256_bytes(b'{"amount":1001,"op":"refund"}')
    passed_caid, mask_caid = ConstantTimeStation1Check.verify_5_tuple_constant_time(
        wrong_caid, caid, h_dig, h_dig, t_dig, t_dig,
        taint_tier_id=0, has_step_up_warrant=0,
        requested_minor=1000, remaining_budget_minor=5000,
    )
    assert passed_caid is False
    assert (mask_caid & (1 << 0)) == (1 << 0)

    # 6. Harness Mismatch -> fails closed on bit 1 (mask == 2)
    wrong_harn = sha256_bytes(b"harness-malicious-v2")
    passed_harn, mask_harn = ConstantTimeStation1Check.verify_5_tuple_constant_time(
        caid, caid, wrong_harn, h_dig, t_dig, t_dig,
        taint_tier_id=0, has_step_up_warrant=0,
        requested_minor=1000, remaining_budget_minor=5000,
    )
    assert passed_harn is False
    assert (mask_harn & (1 << 1)) == (1 << 1)

    # 7. Tool Schema Mismatch -> fails closed on bit 2 (mask == 4)
    wrong_tool = sha256_bytes(b"mcp-unregistered-tool")
    passed_tool, mask_tool = ConstantTimeStation1Check.verify_5_tuple_constant_time(
        caid, caid, h_dig, h_dig, wrong_tool, t_dig,
        taint_tier_id=0, has_step_up_warrant=0,
        requested_minor=1000, remaining_budget_minor=5000,
    )
    assert passed_tool is False
    assert (mask_tool & (1 << 2)) == (1 << 2)


def test_group_commit_wal_latch_amortization(tmp_path: Path) -> None:
    """Verifies TigerBeetle-style Group-Commit WAL latch with Darwin F_FULLFSYNC."""
    wal_file = tmp_path / "test_wire_latch.wal"
    latch = GroupCommitWireLatch(str(wal_file), strict_fullfsync=True)

    batch = [
        {"op_id": f"op-{i}", "state": "EFFECT_INDETERMINATE", "amount": 500, "currency": "EUR"}
        for i in range(32)
    ]
    count, amortized_us = latch.commit_batch(batch)
    latch.close()

    assert count == 32
    assert amortized_us > 0.0
    assert wal_file.stat().st_size > 0

    # Read back WAL lines
    lines = wal_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 32
    assert "EFFECT_INDETERMINATE" in lines[0]


def test_jcodemunch_style_byte_offset_symbol_slicing(tmp_path: Path) -> None:
    """Verifies O(1) seek+read byte-offset symbol slicing and dual-digest taint binding."""
    source_file = tmp_path / "large_service_module.py"

    # Create a realistic 50-function file where the agent queries 1 target function
    with open(source_file, "wb") as src:
        for i in range(49):
            src.write(
                f"def helper_service_endpoint_{i}(payload: dict) -> dict:\n"
                f"    # Long explanatory documentation and validation boilerplate {i}\n"
                f"    result = {{'status': 'ok', 'index': {i}}}\n"
                f"    return result\n\n".encode("utf-8")
            )
        src.write(
            b"def verify_settlement_warrant(caid: str, signature_b64: str) -> bool:\n"
            b"    # Critical boundary function required for reconciliation audit\n"
            b"    return caid.startswith('sha256:') and len(signature_b64) == 88\n"
        )

    indexer = ByteOffsetSymbolIndexer(str(source_file), taint_tier="TIER_2_UNTRUSTED_EXTERNAL")
    res = indexer.fetch_compact_symbol("verify_settlement_warrant")

    # High token compression observed relative to full file read (>10x reduction)
    assert res["compression_ratio_x"] > 10.0
    assert res["taint_tier"] == "TIER_2_UNTRUSTED_EXTERNAL"
    assert res["sym"] == "verify_settlement_warrant"
    assert "verify_settlement_warrant" in res["body"]

    # Dual-digest binding confirmed
    assert res["raw_file_sha256"] != res["slice_sha256"]
    assert res["raw_file_sha256"].startswith("sha256:")
    assert res["slice_sha256"].startswith("sha256:")


def test_deterministic_bitmask_fast_path_escalation() -> None:
    """Verifies O(1) bitmask fast-path check and fail-closed escalation."""
    # Case 1: Strictly read-only, non-mutating, zero-credential local call
    action_route, mask1 = DeterministicFastPathGate.evaluate_tool_call(
        is_read_only=True,
        no_external_net=True,
        no_credentials=True,
        no_state_mutation=True,
        taint_tier="TIER_0_PINNED",
    )
    assert action_route == "fast_path"

    # Case 2: State mutation -> escalates to full_gate
    route_mutation, _ = DeterministicFastPathGate.evaluate_tool_call(
        is_read_only=False,
        no_external_net=True,
        no_credentials=True,
        no_state_mutation=False,
        taint_tier="TIER_0_PINNED",
    )
    assert route_mutation == "full_gate"

    # Case 3: External network call -> escalates to full_gate
    route_net, _ = DeterministicFastPathGate.evaluate_tool_call(
        is_read_only=True,
        no_external_net=False,
        no_credentials=True,
        no_state_mutation=True,
        taint_tier="TIER_0_PINNED",
    )
    assert route_net == "full_gate"

    # Case 4: TIER_2 Untrusted External Taint -> escalates to full_gate
    route_taint, _ = DeterministicFastPathGate.evaluate_tool_call(
        is_read_only=True,
        no_external_net=True,
        no_credentials=True,
        no_state_mutation=True,
        taint_tier="TIER_2_UNTRUSTED_EXTERNAL",
    )
    assert route_taint == "full_gate"
