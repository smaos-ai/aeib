#!/usr/bin/env python3
"""
Verification Suite for SovereignNexus Token Decree Governor
(tests/test_sovereign_token_decree.py).

Evaluated under the stated model with zero mocks, zero floats in JCS canonicalization,
and strict epistemic compliance.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Dict

import pytest

from src.jcs_canonicalizer import encode_jcs
from src.sovereign_token_decree import (
    AlibabaASTDiffSlicer,
    HeadroomLogCompactor,
    TokenCompactionReceipt,
    TokenEconomizerGovernor,
    sha256_caid,
)


def test_1_alibaba_ast_diff_slicer_preserves_only_modified_functions() -> None:
    """Verify that Alibaba OpenCodeReview AST-Diff Slicer collapses unchanged functions/classes to 1-line stubs."""
    old_src = "\n".join(
        [
            f"def helper_{i}(x: int) -> int:\n    \"\"\"Docstring for helper {i}.\"\"\"\n    val = x + {i}\n    val = val * 2\n    return val + 10\n"
            for i in range(20)
        ]
    ) + "\nclass ConfigModel:\n    timeout: int = 30\n"

    # Modify only helper_0 and leave ConfigModel untouched
    new_src = old_src.replace("return val + 10\n", "return val + 20\n", 1)

    sliced = AlibabaASTDiffSlicer.slice_modified_ast(old_src, new_src)
    assert sliced.count("[AST_UNCHANGED]") == 20  # 19 unchanged helpers + 1 unchanged ConfigModel
    assert "class ConfigModel(...): ...  # [AST_UNCHANGED]" in sliced
    assert "def helper_0(x: int) -> int:" in sliced
    assert "return val + 20" in sliced
    assert len(sliced) < len(new_src) // 2

    # Syntax error fallback
    bad_syntax = "def broken(:"
    assert AlibabaASTDiffSlicer.slice_modified_ast(bad_syntax, bad_syntax) == bad_syntax


def test_2_headroom_log_compactor_filters_noise_and_preserves_fatal_lines() -> None:
    """Verify that HeadroomLogCompactor strips passing test noise and preserves fatal lines."""
    passing_log = "\n".join([f"tests/test_x.py::test_{i} PASSED [ {i}%]" for i in range(50)])
    compacted_passing = HeadroomLogCompactor.compact_test_log(passing_log)
    assert "[HEADROOM_COMPACTED: 0 fatal lines out of 50 total lines]" in compacted_passing

    # Default max_lines (25) boundary check
    many_errors = "\n".join([f"FAILED test_{i}" for i in range(40)])
    assert len(HeadroomLogCompactor.compact_test_log(many_errors).splitlines()) == 25

    failing_log = (
        "platform darwin -- Python 3.14.3\n"
        "tests/test_a.py::test_pass PASSED [ 50%]\n"
        "tests/test_b.py::test_fail FAILED [100%]\n"
        "E   AssertionError: expected 10000 bps, got 0 bps\n"
        "short test summary info\n"
        "FAILED tests/test_b.py::test_fail\n"
    )
    compacted_failing = HeadroomLogCompactor.compact_test_log(failing_log, max_lines=5)
    assert "FAILED" in compacted_failing
    assert "E   AssertionError" in compacted_failing
    assert "PASSED" not in compacted_failing
    assert len(compacted_failing.splitlines()) <= 5


def test_3_token_economizer_pruning_and_pinned_tools() -> None:
    """Verify that TokenEconomizer prunes schemas to task keywords and preserves pinned tools."""
    # Test default instantiation values
    default_gov = TokenEconomizerGovernor()
    assert default_gov.max_tools_per_turn == 5
    assert default_gov.max_identical_error_repeats == 2

    gov = TokenEconomizerGovernor(
        pinned_core_tools=frozenset({"report_unsolvable_blocker"}),
        max_tools_per_turn=2,
    )

    all_tools = {
        "report_unsolvable_blocker": {"description": "Emergency halt"},
        "query_sqlite_fts5": {"description": "Search local provenance index"},
        "unused_network_tool": {"description": "Connect to external cluster"},
        "irrelevant_tool": {"description": "Misc actions"},
    }

    # Task description with exact 1 token overlap for query_sqlite_fts5 ('search')
    pruned = gov.prune_tools_for_task("search", all_tools)
    assert "report_unsolvable_blocker" in pruned  # Pinned tool has priority score 10000
    assert "query_sqlite_fts5" in pruned  # 1 token overlap
    assert "unused_network_tool" not in pruned
    assert len(pruned) == 2

    # Zero overlap for other tools
    zero_overlap = gov.prune_tools_for_task("nonexistentword", all_tools)
    assert "report_unsolvable_blocker" in zero_overlap
    assert len(zero_overlap) == 1  # Only pinned tool selected


def test_4_prefix_cache_purity_evaluator() -> None:
    """Verify DeepSeek / Claude prefix cache purity detector."""
    gov = TokenEconomizerGovernor()
    clean_prefix = "SYSTEM DIRECTIVE: Enforce RFC 8785 JCS canonicalization."
    assert gov.verify_prefix_cache_purity(clean_prefix) is True

    contaminated_ts = "SYSTEM: Executed at 2026-10-31T13:40:00Z"
    contaminated_uuid = "SESSION: uuidv4:550e8400-e29b-41d4-a716-446655440000"
    contaminated_nonce = "HEADER: nonce_abcdef12345"

    assert gov.verify_prefix_cache_purity(contaminated_ts) is False
    assert gov.verify_prefix_cache_purity(contaminated_uuid) is False
    assert gov.verify_prefix_cache_purity(contaminated_nonce) is False


def test_5_loop_breaker_halts_on_identical_consecutive_errors() -> None:
    """Verify that repetitive identical error logs trigger circuit breaking."""
    gov = TokenEconomizerGovernor(max_identical_error_repeats=2)
    task_id = "task_retry_loop_1"

    err_a = "E   AssertionError: line 42 failed"
    err_b = "E   ValueError: invalid input"

    assert gov.record_and_check_error_loop(task_id, err_a) is False
    assert gov.record_and_check_error_loop(task_id, err_b) is False
    assert gov.record_and_check_error_loop(task_id, err_b) is True  # Second consecutive err_b


def test_6_combined_turn_optimization_and_jcs_receipt_zero_floats() -> None:
    """Verify full turn context optimization, >70% savings, and strict zero-float JCS receipt."""
    gov = TokenEconomizerGovernor(max_tools_per_turn=3, max_identical_error_repeats=2)

    # 30 tool schemas simulating schema bloat
    all_tools: Dict[str, Dict[str, Any]] = {
        f"tool_{i:02d}": {"description": f"Generic enterprise utility {i}"} for i in range(30)
    }
    all_tools["query_sqlite_fts5"] = {"description": "Search SQLite FTS5 index"}
    all_tools["report_unsolvable_blocker"] = {"description": "Andon cord stop"}

    old_code = "\n".join(
        [f"def f_{i}(x: int) -> int:\n    return x + {i}\n" for i in range(25)]
    ) + "\ndef target(x: int) -> int:\n    return x * 10\n"

    new_code = old_code.replace("return x * 10", "return x * 20")

    verbose_log = (
        "\n".join([f"tests/test_{i}.py PASSED" for i in range(80)])
        + "\ntests/test_target.py FAILED\nE   AssertionError: expected 20, got 10\n"
    )

    clean_prefix = "SYSTEM CONSTITUTION: Enforce RFC 8785 JCS."

    opt_payload, receipt = gov.optimize_turn_context(
        task_id="t1",
        static_system_prefix=clean_prefix,
        task_description="Search SQLite FTS5 for target function",
        all_tool_schemas=all_tools,
        old_file_code=old_code,
        new_file_code=new_code,
        raw_test_log=verbose_log,
    )

    assert receipt.savings_bps >= 7000  # >= 70.00% reduction
    # Exact calculation check: savings_bps == ((orig - comp) * 10000) // orig
    expected_bps = ((receipt.original_bytes - receipt.compacted_bytes) * 10000) // receipt.original_bytes
    assert receipt.savings_bps == expected_bps

    # Exact arithmetic difference check for pruned_tool_count
    assert receipt.pruned_tool_count == len(all_tools) - len(opt_payload["pruned_tools"])
    assert receipt.pruned_tool_count >= 28

    assert receipt.prefix_cache_aligned is True
    assert receipt.loop_halted is False

    # Deep verification of receipt.to_dict() return value
    receipt_dict = receipt.to_dict()
    assert isinstance(receipt_dict, dict)
    assert receipt_dict["compacted_bytes"] == receipt.compacted_bytes
    assert receipt_dict["original_bytes"] == receipt.original_bytes
    assert receipt_dict["savings_bps"] == receipt.savings_bps
    assert receipt_dict["pruned_tool_count"] == receipt.pruned_tool_count
    assert receipt_dict["prefix_cache_aligned"] == receipt.prefix_cache_aligned
    assert receipt_dict["loop_halted"] == receipt.loop_halted
    assert receipt_dict["compacted_payload_caid"] == receipt.compacted_payload_caid

    def _assert_no_floats(obj: Any) -> None:
        if isinstance(obj, float):
            pytest.fail(f"Found forbidden float value: {obj}")
        elif isinstance(obj, dict):
            for k, val in obj.items():
                _assert_no_floats(val)
        elif isinstance(obj, list):
            for item in obj:
                _assert_no_floats(item)

    _assert_no_floats(receipt_dict)

    # Canonical JCS encoding
    raw_jcs = encode_jcs(receipt_dict)
    assert isinstance(raw_jcs, bytes)
    assert receipt.compacted_payload_caid.startswith("sha256:")

    # Negative savings edge case
    opt_payload_neg, receipt_neg = gov.optimize_turn_context(
        task_id="t2",
        static_system_prefix=clean_prefix,
        task_description="empty",
        all_tool_schemas={},
        old_file_code="",
        new_file_code="",
        raw_test_log="",
    )
    assert receipt_neg.savings_bps == 0


def test_7_epistemic_purity_no_banned_words() -> None:
    """Enforce strict epistemic boundary in sovereign_token_decree.py."""
    src_file = Path("src/sovereign_token_decree.py")
    test_file = Path(__file__)

    banned_patterns = [
        r"\bguaran[t]ee\b",
        r"\bguaran[t]eed\b",
        r"\bproven universal[l]y\b",
        r"\bbullet[p]roof\b",
        r"\benterprise-[g]rade\b",
        r"\bproduction-[s]afe\b",
        r"\b100% [s]ecure\b",
    ]

    for target in [src_file, test_file]:
        content = target.read_text(encoding="utf-8")
        for pat in banned_patterns:
            matches = re.findall(pat, content, re.IGNORECASE)
            assert len(matches) == 0, f"Banned pattern '{pat}' matched in {target}: {matches}"


def test_8_receipt_immutability_and_pinned_score_boundary() -> None:
    """Verify TokenCompactionReceipt is frozen and pinned score is exactly 10000."""
    import dataclasses

    receipt = TokenCompactionReceipt(
        original_bytes=100,
        compacted_bytes=50,
        savings_bps=5000,
        pruned_tool_count=2,
        prefix_cache_aligned=True,
        loop_halted=False,
        compacted_payload_caid="sha256:abcd",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        receipt.savings_bps = 0  # type: ignore

    # Exact 10000 score boundary check for pinned tools
    words = [f"tok{i}" for i in range(10000)]
    task_desc = " ".join(words)
    gov = TokenEconomizerGovernor(
        pinned_core_tools=frozenset(["z_pinned"]),
        max_tools_per_turn=1,
    )
    tools = {
        "a_matched": {"description": task_desc},
        "z_pinned": {"description": "none"},
    }
    res = gov.prune_tools_for_task(task_desc, tools)
    assert list(res.keys()) == ["a_matched"]

