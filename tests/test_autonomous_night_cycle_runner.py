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
tests/test_autonomous_night_cycle_runner.py
================================================================================
Verification Suite for `src/autonomous_night_cycle_runner.py`.
Evaluates:
1. Worktree allocation and teardown in real Git environment.
2. Nominal multi-candidate night cycle selecting optimal branch and committing.
3. Rejection of cheating candidates attempting to tamper with invariant core.
4. Fail-closed behavior on empty pools, non-git directories, and git errors.
5. Immutability and serialization of dataclasses.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from src.autonomous_night_cycle_runner import (
    AutonomousNightCycleRunner,
    NightCycleRunReceipt,
)
from src.evolutionary_orchestrator import CandidateBranch


@pytest.fixture
def real_git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "night_repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@sovereign.local"], cwd=repo, check=True, capture_output=True)

    # Initial structure
    (repo / "src").mkdir()
    (repo / "tests").mkdir()
    (repo / "src" / "worker.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "tests" / "test_worker.py").write_text("assert True\n", encoding="utf-8")

    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo, check=True, capture_output=True)
    return repo


def test_1_worktree_allocation_and_teardown(real_git_repo: Path) -> None:
    # Check default workers count
    default_runner = AutonomousNightCycleRunner(repo_root=str(real_git_repo))
    assert default_runner.max_parallel_workers == 4

    runner = AutonomousNightCycleRunner(repo_root=str(real_git_repo), max_parallel_workers=2)
    assert runner.max_parallel_workers == 2

    # Verify _run_git_cmd returns clean output
    out = runner._run_git_cmd(["rev-parse", "--is-inside-work-tree"])
    assert out == "true"

    # Allocate worktree
    wt_path, commit = runner.allocate_worktree("HEAD")
    assert os.path.exists(wt_path)
    assert (Path(wt_path) / "src" / "worker.py").exists()

    # Teardown worktree
    runner.teardown_worktree(wt_path)
    assert not os.path.exists(wt_path)

    # Allocate invalid commit must clean up and raise
    with pytest.raises(RuntimeError, match="ERR_GIT_COMMAND_FAILED"):
        runner.allocate_worktree("non_existent_commit_12345")


def test_2_nominal_night_cycle_selects_winner_and_applies(real_git_repo: Path) -> None:
    runner = AutonomousNightCycleRunner(repo_root=str(real_git_repo))

    candidates = [
        CandidateBranch(
            branch_id="cand_opt_12",
            target_file="src/worker.py",
            proposed_code="x = 100\ndef compute(): return x * 2\n",
            tests_passed=True,
            mutation_kill_bps=9500,
            latency_reduction_bps=1200,
        ),
        CandidateBranch(
            branch_id="cand_opt_20",
            target_file="src/worker.py",
            proposed_code="x = 200\ndef compute(): return x * 4\n",
            tests_passed=True,
            mutation_kill_bps=9600,
            latency_reduction_bps=2000,
        ),
    ]

    receipt = runner.execute_night_cycle(
        task_id="task_refactor_worker",
        candidates=candidates,
    )

    assert receipt.status == "COMPLETED_WINNER_SELECTED"
    assert receipt.winner_branch_id == "cand_opt_20"
    assert receipt.winning_score_bps == 11600  # 9600 + 2000
    assert receipt.evaluated_candidates_count == 2
    assert receipt.worktrees_created == 0
    assert receipt.worktrees_cleaned == 0
    assert receipt.receipt_caid.startswith("sha256:")

    # Verify winning code applied to repo
    applied_content = (real_git_repo / "src" / "worker.py").read_text(encoding="utf-8")
    assert "x = 200" in applied_content

    # Now run with apply_winner_to_repo=False; disk content must NOT change to x = 500
    candidates_no_apply = [
        CandidateBranch(
            branch_id="cand_opt_30",
            target_file="src/worker.py",
            proposed_code="x = 500\n",
            tests_passed=True,
            mutation_kill_bps=9500,
            latency_reduction_bps=1500,
        )
    ]
    receipt_no_apply = runner.execute_night_cycle(
        task_id="task_no_apply",
        candidates=candidates_no_apply,
        apply_winner_to_repo=False,
    )
    assert receipt_no_apply.status == "COMPLETED_WINNER_SELECTED"
    assert receipt_no_apply.winner_branch_id == "cand_opt_30"
    content_after = (real_git_repo / "src" / "worker.py").read_text(encoding="utf-8")
    assert "x = 200" in content_after  # Unchanged!


def test_3_night_cycle_rejects_cheating_and_failing_candidates(real_git_repo: Path) -> None:
    runner = AutonomousNightCycleRunner(repo_root=str(real_git_repo))

    candidates = [
        # Attempt to tamper with test suite
        CandidateBranch(
            branch_id="cand_cheat",
            target_file="src/worker.py",
            proposed_code="with open('tests/test_worker.py', 'w') as f: f.write('assert True')",
            tests_passed=True,
            mutation_kill_bps=9900,
            latency_reduction_bps=5000,
        ),
        # Failed tests
        CandidateBranch(
            branch_id="cand_failed_tests",
            target_file="src/worker.py",
            proposed_code="x = 300\n",
            tests_passed=False,
            mutation_kill_bps=9500,
            latency_reduction_bps=1000,
        ),
    ]

    receipt = runner.execute_night_cycle(
        task_id="task_adversarial",
        candidates=candidates,
        apply_winner_to_repo=True,
    )

    assert receipt.status == "COMPLETED_NO_ELIGIBLE_WINNER"
    assert receipt.winner_branch_id is None
    assert receipt.winning_score_bps == 0


def test_4_input_validation_and_git_errors(real_git_repo: Path) -> None:
    # 1. Missing git anchor even when a pre-built orchestrator is passed
    dummy_orch = AutonomousNightCycleRunner(repo_root=str(real_git_repo)).orchestrator
    with tempfile.TemporaryDirectory() as empty_dir:
        with pytest.raises(ValueError, match="HALT_WORKSPACE_MISSING_GIT_ANCHOR"):
            AutonomousNightCycleRunner(repo_root=empty_dir, orchestrator=dummy_orch)

    runner = AutonomousNightCycleRunner(repo_root=str(real_git_repo))

    # 2. Empty task ID
    with pytest.raises(ValueError, match="ERR_EMPTY_TASK_ID"):
        runner.execute_night_cycle(task_id="", candidates=[])

    # 3. Empty candidate pool
    with pytest.raises(ValueError, match="ERR_EMPTY_CANDIDATE_POOL"):
        runner.execute_night_cycle(task_id="task_valid", candidates=[])

    # 4. Git command error
    with pytest.raises(RuntimeError, match="ERR_GIT_COMMAND_FAILED"):
        runner._run_git_cmd(["checkout", "non_existent_branch_xyz"])

    # 5. Check _now_epoch_ms calculation
    import time
    now_ms = AutonomousNightCycleRunner._now_epoch_ms()
    expected = int(time.time() * 1000)
    assert abs(now_ms - expected) < 2000


def test_5_dataclass_methods_and_immutability() -> None:
    from src.autonomous_night_cycle_runner import NightCycleWorkerSpec

    # 1. NightCycleWorkerSpec immutability
    spec = NightCycleWorkerSpec(
        worker_id="w1",
        worktree_path="/tmp/w1",
        target_file="src/x.py",
        prompt="do work",
    )
    assert spec.worker_id == "w1"
    with pytest.raises(Exception):
        spec.worker_id = "w2"  # type: ignore

    # 2. NightCycleRunReceipt immutability and to_dict
    receipt = NightCycleRunReceipt(
        run_id="run_1",
        task_id="t1",
        winner_branch_id="b1",
        winning_score_bps=10000,
        evaluated_candidates_count=2,
        worktrees_created=2,
        worktrees_cleaned=2,
        status="COMPLETED_WINNER_SELECTED",
        consensus_caid="sha256:111",
        receipt_caid="sha256:222",
    )
    d = receipt.to_dict()
    assert d["run_id"] == "run_1"
    assert d["winner_branch_id"] == "b1"
    assert d["winning_score_bps"] == 10000
    assert d["evaluated_candidates_count"] == 2
    assert d["worktrees_created"] == 2
    assert d["worktrees_cleaned"] == 2
    assert d["status"] == "COMPLETED_WINNER_SELECTED"
    assert d["consensus_caid"] == "sha256:111"
    assert d["receipt_caid"] == "sha256:222"

    with pytest.raises(Exception):
        receipt.status = "MUTATED"  # type: ignore

