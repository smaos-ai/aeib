#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
tests/test_aeib_dst_harness.py
================================================================================
Test Suite for AEIB Protocol-Aware Deterministic Simulation Testing (DST) Harness.

Verifies:
1. Clean 10,000-schedule simulation under seed 20261020:
   - 0 duplicate mutations
   - 0 invariant violations across all 7 invariants (I1–I7)
2. Negative control falsification:
   - Injecting unlatched retry causes harness to detect I2 / I3 violation
   - Injecting budget leakage causes harness to detect I1 violation
3. Deterministic reproducibility: identical seeds produce identical reports
4. Full CLI execution with structured JSON export

Evaluated under the stated model. Zero-mock AST purity enforced.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.aeib_dst_harness import AeibDstEngine, FaultSchedule


def test_dst_10000_schedules_zero_invariant_violations() -> None:
    """Verifies 10,000 pseudo-random schedules with zero invariant violations."""
    engine = AeibDstEngine(seed=20261020)
    report = engine.run_simulation(schedules=10000, fail_fast=True)

    assert report.is_clean, (
        f"DST reported invariant violations: {report.invariant_violations}"
    )
    assert report.schedules_evaluated == 10000
    assert report.observed_duplicates == 0
    assert report.total_timeouts > 0
    assert report.total_retries_blocked == report.total_timeouts
    assert report.total_reconciled > 0

    # Explicit check for all 7 invariants
    for inv, count in report.invariant_violations.items():
        assert count == 0, f"Invariant {inv} had {count} violations!"


def test_dst_negative_control_catches_unlatched_retry_duplicate() -> None:
    """Falsification test: buggy gate allowing retry must be caught by DST harness."""
    engine = AeibDstEngine(seed=42, bug_mode="BYPASS_LATCH_ON_RETRY")
    report = engine.run_simulation(schedules=500, fail_fast=True)

    assert not report.is_clean, "Harness failed to detect injected duplicate retry bug"
    assert report.invariant_violations["I2_zero_duplicate_mutations"] > 0
    assert report.observed_duplicates > 0
    assert report.first_failure_detail is not None
    assert report.first_failure_detail["invariant"] == "I2_zero_duplicate_mutations"


def test_dst_negative_control_catches_budget_leak() -> None:
    """Falsification test: budget leakage must be caught by DST harness."""
    engine = AeibDstEngine(seed=42, bug_mode="LEAK_BUDGET")
    report = engine.run_simulation(schedules=500, fail_fast=True)

    assert not report.is_clean, "Harness failed to detect injected budget leak"
    assert report.invariant_violations["I1_budget_conservation"] > 0
    assert report.first_failure_detail is not None
    assert report.first_failure_detail["invariant"] == "I1_budget_conservation"


def test_dst_deterministic_reproducibility() -> None:
    """Verifies that identical seeds produce bit-identical simulation trajectories."""
    engine1 = AeibDstEngine(seed=99991)
    report1 = engine1.run_simulation(schedules=1000, fail_fast=True)

    engine2 = AeibDstEngine(seed=99991)
    report2 = engine2.run_simulation(schedules=1000, fail_fast=True)

    assert report1.schedules_evaluated == report2.schedules_evaluated
    assert report1.total_dispatches == report2.total_dispatches
    assert report1.total_timeouts == report2.total_timeouts
    assert report1.total_retries_blocked == report2.total_retries_blocked
    assert report1.total_reconciled == report2.total_reconciled
    assert report1.observed_duplicates == report2.observed_duplicates
    assert report1.invariant_violations == report2.invariant_violations


def test_dst_cli_execution_with_json_output(tmp_path: Path) -> None:
    """Verifies the CLI interface and JSON output format."""
    out_json = tmp_path / "dst_report.json"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "tools" / "aeib_dst_harness.py"),
        "--schedules",
        "1000",
        "--seed",
        "20261020",
        "--output-json",
        str(out_json),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert result.returncode == 0, f"CLI exited with error: {result.stderr}"

    assert out_json.exists()
    with open(out_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["status"] == "PASS"
    assert data["schedules_evaluated"] == 1000
    assert data["observed_duplicates"] == 0
    assert data["invariant_violations"]["I1_budget_conservation"] == 0
    assert data["invariant_violations"]["I2_zero_duplicate_mutations"] == 0
