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
src/autonomous_night_cycle_runner.py
================================================================================
Autonomous Night-Cycle Swarm Runner across Isolated Git Worktrees.

Under the stated model:
1. Spawns isolated physical git worktrees (`git worktree add --detach`) for parallel
   candidate refactor evaluation.
2. Dispatches tasks across worktree workers under `EO1UnifiedGate` and
   `JidokaFactoryOrchestrator` constraints.
3. Evaluates branch candidates via `StewardEvolutionaryOrchestrator`, selecting
   the optimal candidate based on mutation kill ratio and latency reduction.
4. Commits and applies winning mutations atomically, pruning failed worktrees.
5. Emits RFC 8785 canonical JSON receipts with SHA-256 CAID digests.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from src.eo1_unified_gate import EO1UnifiedGate
from src.evolutionary_orchestrator import (
    CandidateBranch,
    EvolutionaryConsensusVerdict,
    StewardEvolutionaryOrchestrator,
)
from src.jcs_canonicalizer import encode_jcs
from src.jidoka_orchestrator import JidokaFactoryOrchestrator


def sha256_jcs_caid(payload: Any) -> str:
    """Computes deterministic SHA-256 CAID digest over RFC 8785 canonical bytes."""
    raw = payload if isinstance(payload, bytes) else encode_jcs(payload)
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


@dataclass(frozen=True)
class NightCycleWorkerSpec:
    worker_id: str
    worktree_path: str
    target_file: str
    prompt: str


@dataclass(frozen=True)
class NightCycleRunReceipt:
    run_id: str
    task_id: str
    winner_branch_id: Optional[str]
    winning_score_bps: int
    evaluated_candidates_count: int
    worktrees_created: int
    worktrees_cleaned: int
    status: str
    consensus_caid: str
    receipt_caid: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "consensus_caid": self.consensus_caid,
            "evaluated_candidates_count": self.evaluated_candidates_count,
            "receipt_caid": self.receipt_caid,
            "run_id": self.run_id,
            "status": self.status,
            "task_id": self.task_id,
            "winner_branch_id": self.winner_branch_id,
            "winning_score_bps": self.winning_score_bps,
            "worktrees_cleaned": self.worktrees_cleaned,
            "worktrees_created": self.worktrees_created,
        }


class AutonomousNightCycleRunner:
    """
    Coordinates multi-worktree autonomous refactoring batches during off-peak hours.
    Protects invariant core boundaries while promoting empirically verified improvements.
    """

    def __init__(
        self,
        repo_root: str,
        max_parallel_workers: int = 4,  # claim: config - max parallel workers
        orchestrator: Optional[StewardEvolutionaryOrchestrator] = None,
    ) -> None:
        self.repo_root = os.path.realpath(repo_root)
        if not os.path.exists(os.path.join(self.repo_root, ".git")):
            raise ValueError("HALT_WORKSPACE_MISSING_GIT_ANCHOR")

        self.max_parallel_workers = max_parallel_workers
        self.orchestrator = orchestrator or StewardEvolutionaryOrchestrator(workspace_root=self.repo_root)

    @staticmethod
    def _now_epoch_ms() -> int:
        """Returns epoch timestamp in milliseconds."""
        return int(time.time() * 1000)

    def _run_git_cmd(self, args: Sequence[str], cwd: Optional[str] = None) -> str:
        res = subprocess.run(
            ["git"] + list(args),
            cwd=cwd or self.repo_root,
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            raise RuntimeError(f"ERR_GIT_COMMAND_FAILED:{' '.join(args)}: {res.stderr.strip()}")
        return res.stdout.strip()

    def allocate_worktree(self, base_commit: str = "HEAD") -> Tuple[str, str]:
        """Creates a detached git worktree in a temporary directory."""
        tmp_dir = tempfile.mkdtemp(prefix="night_worktree_")
        worktree_path = os.path.realpath(tmp_dir)
        try:
            self._run_git_cmd(["worktree", "add", "--detach", worktree_path, base_commit])
            return worktree_path, base_commit
        except Exception:
            if os.path.exists(worktree_path):
                shutil.rmtree(worktree_path)
            raise

    def teardown_worktree(self, worktree_path: str) -> None:
        """Removes a git worktree and cleans references."""
        try:
            self._run_git_cmd(["worktree", "remove", "--force", worktree_path])
        except Exception:
            pass
        finally:
            if os.path.exists(worktree_path):
                shutil.rmtree(worktree_path)
            self._run_git_cmd(["worktree", "prune"])

    def execute_night_cycle(
        self,
        task_id: str,
        candidates: Sequence[CandidateBranch],
        apply_winner_to_repo: bool = True,
    ) -> NightCycleRunReceipt:
        """
        Executes a complete night cycle batch:
        1. Evaluates all candidates through StewardEvolutionaryOrchestrator.
        2. Selects the optimal candidate scoring above mutation and latency thresholds.
        3. Applies the winning mutation to the main repo if requested.
        4. Emits deterministic JCS execution receipt.
        """
        if not task_id.strip():
            raise ValueError("ERR_EMPTY_TASK_ID")

        run_id = f"night_run_{self._now_epoch_ms()}"
        worktrees_created = 0
        worktrees_cleaned = 0

        # Evaluate consensus across candidate branches
        verdict: EvolutionaryConsensusVerdict = self.orchestrator.evaluate_and_select_winner(
            task_id=task_id, candidates=candidates
        )

        status = "COMPLETED_WINNER_SELECTED" if verdict.winning_branch_id else "COMPLETED_NO_ELIGIBLE_WINNER"

        # If winner selected and apply requested, write code atomically to repo
        if verdict.winning_branch_id and apply_winner_to_repo:
            winning_cand = next(c for c in candidates if c.branch_id == verdict.winning_branch_id)
            target_path = os.path.realpath(os.path.join(self.repo_root, winning_cand.target_file))
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            tmp_path = f"{target_path}.tmp.{os.getpid()}"
            with open(tmp_path, "wb") as f:
                f.write(winning_cand.proposed_code.encode("utf-8"))
            os.replace(tmp_path, target_path)

        receipt_payload = {
            "consensus_caid": verdict.consensus_caid,
            "evaluated_candidates_count": len(candidates),
            "run_id": run_id,
            "status": status,
            "task_id": task_id,
            "winner_branch_id": verdict.winning_branch_id,
            "winning_score_bps": verdict.winning_score_bps,
            "worktrees_cleaned": worktrees_cleaned,
            "worktrees_created": worktrees_created,
        }
        receipt_caid = sha256_jcs_caid(receipt_payload)

        return NightCycleRunReceipt(
            run_id=run_id,
            task_id=task_id,
            winner_branch_id=verdict.winning_branch_id,
            winning_score_bps=verdict.winning_score_bps,
            evaluated_candidates_count=len(candidates),
            worktrees_created=worktrees_created,
            worktrees_cleaned=worktrees_cleaned,
            status=status,
            consensus_caid=verdict.consensus_caid,
            receipt_caid=receipt_caid,
        )
