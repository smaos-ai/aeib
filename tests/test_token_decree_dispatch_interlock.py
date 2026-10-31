#!/usr/bin/env python3
"""
Unit and regression test suite for TokenDecreeDispatchInterlock.
Evaluated under the stated model with zero mocks and real Ed25519 signatures.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path
from typing import Dict, Any

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.token_decree_dispatch_interlock import (
    TokenDecreeDispatchInterlock,
    TokenDecreeWarrant,
    DISPOSITION_ADMISSIBLE,
    DISPOSITION_HALTED_REPETITIVE_LOOP,
    DISPOSITION_REJECTED_PREFIX_CONTAMINATED,
    DISPOSITION_REJECTED_SAVINGS_FLOOR_UNMET,
)
from src.sovereign_token_decree import TokenEconomizerGovernor


def _sample_tools() -> Dict[str, Dict[str, Any]]:
    return {
        "read_code_file": {"description": "Reads python source file from repository."},
        "run_ast_linter": {"description": "Executes AST linter on modified python files."},
        "send_slack_message": {"description": "Posts diagnostic alerts to slack channel."},
        "query_remote_database": {"description": "Executes SQL query against external database."},
        "report_unsolvable_blocker": {"description": "Halts execution on unsolvable invariant failure."},
    }


def test_1_admissible_dispatch_seals_valid_ed25519_warrant() -> None:
    interlock = TokenDecreeDispatchInterlock(minimum_savings_floor_bps=0)

    old_code = "def f(x):\n    return x + 1\ndef g(y):\n    return y * 2\n"
    new_code = "def f(x):\n    return x + 42\ndef g(y):\n    return y * 2\n"
    test_log = "PASSED test_1\nPASSED test_2\nFAILED test_3\nE   AssertionError: expected 43 got 42\n"

    disp, payload, warrant = interlock.dispatch_and_seal(
        task_id="task-401",
        model_id="claude-3-7-sonnet",
        static_system_prefix="You are an autonomous engineering verifier under strict epistemic bounds.",
        task_description="fix ast calculation in f(x) and check test log",
        all_tool_schemas=_sample_tools(),
        old_file_code=old_code,
        new_file_code=new_code,
        raw_test_log=test_log,
    )

    assert disp == DISPOSITION_ADMISSIBLE
    assert warrant is not None
    assert warrant.task_id == "task-401"
    assert warrant.model_id == "claude-3-7-sonnet"
    assert isinstance(warrant.savings_bps, int)
    assert not isinstance(warrant.savings_bps, bool)
    assert warrant.savings_bps >= 0

    valid, reason = interlock.verify_warrant(warrant, payload)
    assert valid is True
    assert reason == "OK"


def test_2_halt_repetitive_error_loop() -> None:
    gov = TokenEconomizerGovernor(max_identical_error_repeats=2)
    interlock = TokenDecreeDispatchInterlock(governor=gov)

    error_log = "FAILED test_fail\nE   RuntimeError: database deadlocked\n"

    disp1, _, w1 = interlock.dispatch_and_seal(
        task_id="task-loop",
        model_id="model-a",
        static_system_prefix="Static prompt prefix.",
        task_description="resolve deadlock",
        all_tool_schemas=_sample_tools(),
        old_file_code="def a(): pass",
        new_file_code="def a(): pass",
        raw_test_log=error_log,
    )
    assert disp1 == DISPOSITION_ADMISSIBLE
    assert w1 is not None

    disp2, _, w2 = interlock.dispatch_and_seal(
        task_id="task-loop",
        model_id="model-a",
        static_system_prefix="Static prompt prefix.",
        task_description="resolve deadlock",
        all_tool_schemas=_sample_tools(),
        old_file_code="def a(): pass",
        new_file_code="def a(): pass",
        raw_test_log=error_log,
    )
    assert disp2 == DISPOSITION_HALTED_REPETITIVE_LOOP
    assert w2 is None


def test_3_prefix_cache_contamination_rejection() -> None:
    interlock = TokenDecreeDispatchInterlock()
    assert interlock.enforce_prefix_cache_purity is True

    contaminated_prefix = "System prompt generated at 2026-10-31T12:00:00Z for session."
    disp, _, warrant = interlock.dispatch_and_seal(
        task_id="task-contam",
        model_id="model-a",
        static_system_prefix=contaminated_prefix,
        task_description="read code",
        all_tool_schemas=_sample_tools(),
        old_file_code="def a(): pass",
        new_file_code="def a(): pass",
        raw_test_log="PASSED test_ok\n",
    )
    assert disp == DISPOSITION_REJECTED_PREFIX_CONTAMINATED
    assert warrant is None


def test_4_savings_floor_enforcement() -> None:
    # Require 9999 bps (99.99%) savings, which will fail on typical payloads
    interlock = TokenDecreeDispatchInterlock(minimum_savings_floor_bps=9999)

    disp, _, warrant = interlock.dispatch_and_seal(
        task_id="task-floor",
        model_id="model-a",
        static_system_prefix="Static prefix.",
        task_description="read code file",
        all_tool_schemas=_sample_tools(),
        old_file_code="def a(): pass",
        new_file_code="def a(): pass",
        raw_test_log="FAILED err\n",
    )
    assert disp == DISPOSITION_REJECTED_SAVINGS_FLOOR_UNMET
    assert warrant is None


def test_5_tampered_payload_caid_verification_failure() -> None:
    interlock = TokenDecreeDispatchInterlock()
    disp, payload, warrant = interlock.dispatch_and_seal(
        task_id="task-tamper",
        model_id="model-a",
        static_system_prefix="Static prefix.",
        task_description="read code",
        all_tool_schemas=_sample_tools(),
        old_file_code="def a(): pass",
        new_file_code="def a(): pass",
        raw_test_log="PASSED ok\n",
    )
    assert disp == DISPOSITION_ADMISSIBLE
    assert warrant is not None

    tampered_payload = dict(payload)
    tampered_payload["task"] = "tampered task description"

    valid, reason = interlock.verify_warrant(warrant, tampered_payload)
    assert valid is False
    assert reason == "ERR_PAYLOAD_CAID_MISMATCH"


def test_6_forged_signature_verification_failure() -> None:
    interlock = TokenDecreeDispatchInterlock()
    disp, payload, warrant = interlock.dispatch_and_seal(
        task_id="task-forge",
        model_id="model-a",
        static_system_prefix="Static prefix.",
        task_description="read code",
        all_tool_schemas=_sample_tools(),
        old_file_code="def a(): pass",
        new_file_code="def a(): pass",
        raw_test_log="PASSED ok\n",
    )
    assert warrant is not None

    # Corrupt the signature hex
    corrupted_sig = "00" * 64
    forged_warrant = TokenDecreeWarrant(
        task_id=warrant.task_id,
        model_id=warrant.model_id,
        original_bytes=warrant.original_bytes,
        compacted_bytes=warrant.compacted_bytes,
        savings_bps=warrant.savings_bps,
        pruned_tool_count=warrant.pruned_tool_count,
        compacted_payload_caid=warrant.compacted_payload_caid,
        signer_pubkey_hex=warrant.signer_pubkey_hex,
        signature_hex=corrupted_sig,
        warrant_caid=warrant.warrant_caid,
    )

    valid, reason = interlock.verify_warrant(forged_warrant, payload)
    assert valid is False
    assert "ERR_CRYPTOGRAPHIC_VERIFICATION_FAILED" in reason


def test_8_edge_cases_boundary_validation_and_tampered_warrant_caid() -> None:
    interlock = TokenDecreeDispatchInterlock()

    # 1. Invalid minimum_savings_floor_bps values
    with pytest.raises(ValueError, match="ERR_INVALID_SAVINGS_FLOOR_BPS:-1"):
        TokenDecreeDispatchInterlock(minimum_savings_floor_bps=-1)
    with pytest.raises(ValueError, match="ERR_INVALID_SAVINGS_FLOOR_BPS:10001"):
        TokenDecreeDispatchInterlock(minimum_savings_floor_bps=10001)

    # 2. enforce_prefix_cache_purity=False allows dynamic prefix
    interlock_relaxed = TokenDecreeDispatchInterlock(enforce_prefix_cache_purity=False)
    disp, opt_payload, w = interlock_relaxed.dispatch_and_seal(
        task_id="task-dyn",
        model_id="m1",
        static_system_prefix="Dynamic header at 2026-10-31T12:00:00Z",
        task_description="test relaxed prefix",
        all_tool_schemas=_sample_tools(),
        old_file_code="def a(): pass",
        new_file_code="def a(): pass",
        raw_test_log="PASSED\n",
    )
    assert disp == DISPOSITION_ADMISSIBLE
    assert w is not None

    # 3. warrant.to_dict() serialization
    w_dict = w.to_dict()
    assert "compacted_bytes" in w_dict
    assert "warrant_caid" in w_dict
    assert w_dict["task_id"] == "task-dyn"

    # 4. Immutability of TokenDecreeWarrant
    with pytest.raises(dataclasses.FrozenInstanceError):
        w.savings_bps = 5000  # type: ignore

    # 5. Non-integer or bool savings_bps
    bad_warrant_bool = dataclasses.replace(w, savings_bps=True)  # type: ignore
    valid, err = interlock_relaxed.verify_warrant(bad_warrant_bool, {})
    assert valid is False
    assert err == "ERR_NON_INTEGER_SAVINGS_BPS"

    # 6. Tampered warrant_caid
    bad_caid_warrant = dataclasses.replace(w, warrant_caid="sha256:0000000000000000000000000000000000000000000000000000000000000000")
    valid_caid, err_caid = interlock_relaxed.verify_warrant(bad_caid_warrant, opt_payload)
    assert valid_caid is False
    assert err_caid == "ERR_WARRANT_CAID_MISMATCH"


def test_7_epistemic_purity_no_banned_words() -> None:
    banned_terms = [
        r"\bguarant[e]e\b",
        r"\bguarant[e]ed\b",
        r"\bbullet[p]roof\b",
        r"\benterprise-[g]rade\b",
        r"\bproduction-[s]afe\b",
        r"\b100% [s]ecure\b",
    ]
    files_to_scan = [
        Path("src/token_decree_dispatch_interlock.py"),
        Path("tests/test_token_decree_dispatch_interlock.py"),
    ]

    for fpath in files_to_scan:
        content = fpath.read_text(encoding="utf-8")
        for pat in banned_terms:
            matches = re.findall(pat, content, re.IGNORECASE)
            assert not matches, f"Banned pattern '{pat}' found in {fpath}: {matches}"
