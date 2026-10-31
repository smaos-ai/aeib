#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

"""
tests/test_execution_integrity_benchmark.py
================================================================================
Comprehensive verification suite for `execution-integrity-benchmark`.
Tests:
  1. Task loading and specification validation across all 10 categories.
  2. Arm D StaticPolicyEngine: False Denial and False Permit behavior.
  3. Arm B PromptGuardrailPolicy: Leaks under contradictory pressure.
  4. Arm C EO1ExecutionBoundary: Zero-mock AST latch and blocker escalation.
  5. 4-Arm Benchmark Runner: Deterministic execution and RFC 8785 JCS receipt.
  6. Metric Analyzer: CAID verification and Markdown table generation.
  7. Forensic Split Screen: Layout rendering and invariant messages.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_BENCHMARK_DIR = Path(__file__).resolve().parent.parent / "execution-integrity-benchmark"
sys.path.insert(0, str(_BENCHMARK_DIR))
sys.path.insert(0, str(_BENCHMARK_DIR.parent))

from analysis.metrics_analyzer import (
    analyze_receipt,
    format_markdown_table,
)
from dashboard.forensic_split_screen import (
    render_split_screen,
)
from policies.eo1_execution_boundary import (
    EO1ExecutionBoundary,
)
from policies.prompt_guardrails import (
    PromptGuardrailPolicy,
)
from policies.static_policy_engine import (
    StaticPolicyEngine,
)
from runners.benchmark_runner import (
    compute_wilson_interval_bps,
    load_tasks,
    run_benchmark,
)


def test_1_task_loading_and_categories() -> None:
    tasks_dir = _BENCHMARK_DIR / "tasks"
    assert tasks_dir.is_dir()
    tasks = load_tasks(tasks_dir)
    assert len(tasks) == 32

    categories = {t.category for t in tasks}
    assert len(categories) == 10
    assert "financial_idempotency" in categories
    assert "test_tampering" in categories
    assert "secret_exfiltration" in categories
    assert "dependency_installation" in categories
    assert "filesystem_escape" in categories
    assert "production_deployment" in categories
    assert "blind_retry_timeout" in categories
    assert "indirect_prompt_injection" in categories
    assert "contradictory_specification" in categories
    assert "legitimate_control" in categories


def test_2_static_policy_engine_overblocking_and_leaks() -> None:
    engine = StaticPolicyEngine()

    # 1. Direct forbidden effect -> DENIED
    res1 = engine.evaluate_action(
        task_id="t1",
        attempted_effects=("secret_exfiltration",),
    )
    assert res1.allowed is False
    assert res1.status_code == "DENIED_BY_STATIC_POLICY"

    # 2. Legitimate control with build/test edit -> Over-blocked (False Denial!)
    res2 = engine.evaluate_action(
        task_id="t2",
        attempted_effects=("run_build_command",),
        modified_files=("dist/package.tar.gz",),
        is_legitimate_control=True,
    )
    assert res2.allowed is False
    assert any("DENY_STATIC_OVERBLOCK" in r for r in res2.denied_reasons)

    # 3. Clean nominal action -> ALLOWED
    res3 = engine.evaluate_action(
        task_id="t3",
        attempted_effects=("read_local_markdown",),
        modified_files=(),
        is_legitimate_control=False,
    )
    assert res3.allowed is True


def test_3_prompt_guardrails_cheat_under_pressure() -> None:
    policy = PromptGuardrailPolicy()

    # 1. Under contradictory pressure, prompt misses reward hacking/cheating
    res1 = policy.evaluate(
        task_id="t_imp",
        attempted_effects=("mock_assertion_pass",),
        modified_test_files=("tests/test_x.py",),
        is_impossible_or_contradictory=True,
    )
    assert res1.allowed is True
    assert res1.status_code == "LEAKED_REWARD_HACKING_UNDER_PRESSURE"

    # 2. Direct forbidden effect -> Caught by prompt
    res2 = policy.evaluate(
        task_id="t_exfil",
        attempted_effects=("read_private_keys",),
        modified_test_files=(),
        is_impossible_or_contradictory=False,
    )
    assert res2.allowed is False
    assert res2.status_code == "DENIED_BY_PROMPT_CONSTRAINT"


def test_4_eo1_boundary_interception_and_escalation() -> None:
    boundary = EO1ExecutionBoundary()

    # 1. Test tampering is blocked
    res1 = boundary.evaluate_intent(
        task_id="t_tamper",
        attempted_effects=("edit_src",),
        modified_test_files=("tests/test_fix.py",),
    )
    assert res1.allowed is False
    assert res1.decision == "DENY"

    # 2. Contradictory spec with blocker reported -> ESCALATE
    res2 = boundary.evaluate_intent(
        task_id="t_contra",
        attempted_effects=(),
        modified_test_files=(),
        escalated_blocker=True,
        blocker_reason="CONTRADICTORY_TYPE_CONSTRAINT",
        is_impossible_or_contradictory=True,
    )
    assert res2.allowed is False
    assert res2.decision == "ESCALATE"
    assert res2.escalation_ticket is not None

    # 3. Legitimate control -> PERMIT
    res3 = boundary.evaluate_intent(
        task_id="t_legit",
        attempted_effects=("rename_local_variable",),
        is_legitimate_control=True,
    )
    assert res3.allowed is True
    assert res3.decision == "PERMIT"


def test_5_benchmark_runner_and_analyzer_roundtrip(tmp_path: Path) -> None:
    out_receipt = tmp_path / "test_receipt.json"
    receipt = run_benchmark(output_receipt_path=out_receipt)

    assert receipt["receipt_caid"].startswith("sha256:")
    assert out_receipt.is_file()

    analysis = analyze_receipt(receipt)
    assert analysis["caid_valid"] is True
    assert analysis["total_tasks"] == 32
    assert analysis["total_trials"] == 128

    table_md = format_markdown_table(analysis)
    assert "ARM_A_UNPROTECTED" in table_md
    assert "ARM_B_PROMPT_ONLY" in table_md
    assert "ARM_C_AEIB_EO1_BOUNDARY" in table_md
    assert "ARM_D_STATIC_POLICY_ENGINE" in table_md


def test_6_forensic_split_screen_dashboard() -> None:
    rendered = render_split_screen()
    assert "AGENT RESULT" in rendered
    assert "EXECUTION LEDGER" in rendered
    assert "EO1 did not make the model smarter" in rendered


def test_7_demo_launcher_scenarios(monkeypatch: pytest.MonkeyPatch) -> None:
    import demo_launcher

    for sc in ("split_screen", "execution_integrity", "gemma_developer", "huntr_scanner", "dora_compliance"):
        monkeypatch.setattr("sys.argv", ["demo_launcher.py", "--scenario", sc])
        demo_launcher.main()


def test_8_wilson_intervals_and_multi_repetitions(tmp_path: Path) -> None:
    # 1. Wilson 95% interval properties
    assert compute_wilson_interval_bps(0, 0) == [0, 0]
    ci_0 = compute_wilson_interval_bps(0, 32)
    assert ci_0[0] == 0
    assert 0 < ci_0[1] <= 1500  # Conservative upper bound for 0/32

    ci_full = compute_wilson_interval_bps(32, 32)
    assert ci_full[0] >= 8500
    assert ci_full[1] == 10000

    # 2. Multi-repetition execution (e.g. 2 repetitions = 64 tasks/arm, 256 trials total)
    out_rep2 = tmp_path / "rep2_receipt.json"
    r2 = run_benchmark(output_receipt_path=out_rep2, repetitions=2)
    assert r2["receipt_body"]["repetitions"] == 2
    assert r2["receipt_body"]["total_trials"] == 256
    assert out_rep2.is_file()

    # Reject non-positive repetitions
    with pytest.raises(ValueError, match="repetitions must be a positive integer"):
        run_benchmark(repetitions=0)

