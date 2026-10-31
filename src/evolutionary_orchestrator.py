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
src/evolutionary_orchestrator.py
================================================================================
Scope 1: STEWARD Evolutionary Orchestrator.

Evaluates N parallel candidate refactor branches under strict Invariant Core confinement.
Selects the optimal surviving candidate by composite (mutation_kill_bps + latency_reduction_bps)
while halting any branch that touches protected files, fails tests, drops below mutation floor,
or attempts reflection/cheating.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from src.eo1_unified_gate import EO1UnifiedGate, sha256_jcs_caid
from src.jcs_canonicalizer import encode_jcs


@dataclass(frozen=True)
class CandidateBranch:
    """A parallel candidate branch proposing an architectural refactor."""

    branch_id: str
    target_file: str
    proposed_code: str
    tests_passed: bool
    mutation_kill_bps: int       # e.g., 9500 = 95.00%
    latency_reduction_bps: int   # e.g., 2000 = 20.00% faster

    def __post_init__(self) -> None:
        if not self.branch_id.strip():
            raise ValueError("branch_id must not be empty")
        if not self.target_file.strip():
            raise ValueError("target_file must not be empty")
        if not isinstance(self.mutation_kill_bps, int) or not (0 <= self.mutation_kill_bps <= 10000):
            raise ValueError("mutation_kill_bps must be integer in 0..10000 bps")
        if not isinstance(self.latency_reduction_bps, int):
            raise ValueError("latency_reduction_bps must be integer bps")


@dataclass(frozen=True)
class BranchEvaluationResult:
    """Evaluation receipt for a single candidate branch."""

    branch_id: str
    eligible: bool
    rejection_reason: str
    eo1_receipt_caid: str
    composite_score_bps: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "composite_score_bps": self.composite_score_bps,
            "eligible": self.eligible,
            "eo1_receipt_caid": self.eo1_receipt_caid,
            "rejection_reason": self.rejection_reason,
        }


@dataclass(frozen=True)
class EvolutionaryConsensusVerdict:
    """Deterministic consensus verdict selecting the surviving refactor candidate."""

    task_id: str
    winning_branch_id: Optional[str]
    winning_score_bps: int
    evaluated_branches: Tuple[BranchEvaluationResult, ...]
    consensus_caid: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "consensus_caid": self.consensus_caid,
            "evaluated_branches": [b.to_dict() for b in self.evaluated_branches],
            "task_id": self.task_id,
            "winning_branch_id": self.winning_branch_id,
            "winning_score_bps": self.winning_score_bps,
        }


class StewardEvolutionaryOrchestrator:
    """
    Orchestrates governed self-evolution across parallel worktree candidates.
    Enforces that safety assertions and invariant core cannot be weakened.
    """

    MIN_MUTATION_KILL_BPS: int = 9000  # claim: config - 90.00% mutation floor

    def __init__(self, workspace_root: str) -> None:
        self.gate = EO1UnifiedGate(workspace_root=workspace_root)

    def evaluate_and_select_winner(
        self,
        task_id: str,
        candidates: Sequence[CandidateBranch],
    ) -> EvolutionaryConsensusVerdict:
        if not task_id.strip():
            raise ValueError("ERR_EMPTY_TASK_ID")
        if not candidates:
            raise ValueError("ERR_EMPTY_CANDIDATE_POOL")

        results: List[BranchEvaluationResult] = []
        best_branch: Optional[CandidateBranch] = None
        best_score: Optional[int] = None

        for cand in candidates:
            sub_task_id = f"{task_id}:{cand.branch_id}"
            receipt = self.gate.validate_code_write(
                task_id=sub_task_id,
                file_path=cand.target_file,
                proposed_code=cand.proposed_code,
            )

            # 1. Invariant Core & Security Check
            if not receipt.allowed:
                results.append(
                    BranchEvaluationResult(
                        branch_id=cand.branch_id,
                        eligible=False,
                        rejection_reason=receipt.status_code,
                        eo1_receipt_caid=receipt.receipt_caid,
                        composite_score_bps=0,
                    )
                )
                continue

            # 2. Functional Unit Tests
            if not cand.tests_passed:
                results.append(
                    BranchEvaluationResult(
                        branch_id=cand.branch_id,
                        eligible=False,
                        rejection_reason="HALT_UNIT_TESTS_FAILED",
                        eo1_receipt_caid=receipt.receipt_caid,
                        composite_score_bps=0,
                    )
                )
                continue

            # 3. Mutation Floor Verification
            if cand.mutation_kill_bps < self.MIN_MUTATION_KILL_BPS:
                results.append(
                    BranchEvaluationResult(
                        branch_id=cand.branch_id,
                        eligible=False,
                        rejection_reason=f"HALT_MUTATION_BELOW_FLOOR:{cand.mutation_kill_bps}",
                        eo1_receipt_caid=receipt.receipt_caid,
                        composite_score_bps=0,
                    )
                )
                continue

            # 4. Latency Non-Regression Verification
            if cand.latency_reduction_bps < 0:
                results.append(
                    BranchEvaluationResult(
                        branch_id=cand.branch_id,
                        eligible=False,
                        rejection_reason=f"HALT_LATENCY_REGRESSION:{cand.latency_reduction_bps}",
                        eo1_receipt_caid=receipt.receipt_caid,
                        composite_score_bps=0,
                    )
                )
                continue

            # Deterministic integer score: mutation adequacy (0..10000) + latency gain (bps)
            score_bps = cand.mutation_kill_bps + cand.latency_reduction_bps
            results.append(
                BranchEvaluationResult(
                    branch_id=cand.branch_id,
                    eligible=True,
                    rejection_reason="OK_ELIGIBLE",
                    eo1_receipt_caid=receipt.receipt_caid,
                    composite_score_bps=score_bps,
                )
            )

            if best_score is None or score_bps > best_score:
                best_score = score_bps
                best_branch = cand

        winner_id = best_branch.branch_id if best_branch is not None else None
        final_score = best_score if best_score is not None else 0

        payload = {
            "evaluated_branches": [r.to_dict() for r in results],
            "task_id": task_id,
            "winning_branch_id": winner_id,
            "winning_score_bps": final_score,
        }

        return EvolutionaryConsensusVerdict(
            task_id=task_id,
            winning_branch_id=winner_id,
            winning_score_bps=final_score,
            evaluated_branches=tuple(results),
            consensus_caid=sha256_jcs_caid(payload),
        )
