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
src/kiro_1000pr_and_cube_wal_simulator.py
================================================================================
Durable SQLite-WAL Cube/Substrate Auto-Pause Interlock & Kiro 1,000-PR Simulator.

Status: INTERNAL PREVIEW COMMISSIONED.
Evaluated under the stated model:
  1. Durable SQLite-WAL Cube/Substrate Auto-Pause Interlock (`DurableCubeAutoPauseInterlock`).
     Fixes in-flight ambiguity: Persists in-flight egress attempts and `INDETERMINATE`
     Auto-Pause states in a SQLite WAL database (`PRAGMA synchronous=FULL`) so state
     survives KVM snapshot suspend/resume across physical worker pods.
  2. Cumulative-Epoch Kiro 1,000-PR Blast-Radius & Anti-Smurfing Simulator (`Kiro1000PRSimulator`).
     Simulates a 1,000-PR/week autonomous software factory with cumulative epoch tracking,
     containing leaf PRs, core fan-in PRs, over-eager single PRs, and multi-PR smurfing attacks.
  3. Single-source RFC 8785 JCS canonicalization with zero floats.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Tuple

from src.hypergraph_blast_radius import (
    HypergraphBlastRadiusGovernor,
    PRDiffSpec,
    sha256_jcs_caid,
)


class DurableCubeAutoPauseInterlock:
    """
    Persists in-flight egress attempts and `INDETERMINATE` Auto-Pause states
    inside a SQLite WAL database (`synchronous=FULL`) so state survives KVM
    snapshot suspend/resume across physical worker nodes.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS egress_wal (
                idempotency_key TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                caid TEXT NOT NULL,
                target_api TEXT NOT NULL,
                state TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def register_egress_attempt(
        self, agent_id: str, caid: str, idempotency_key: str, target_api: str
    ) -> str:
        row = self._conn.execute(
            "SELECT state FROM egress_wal WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()

        if row is not None:
            existing_state = str(row[0])
            if existing_state == "COMMITTED":
                return "HALT_DUPLICATE_COMMITTED_BLOCKED"
            if existing_state == "INDETERMINATE":
                return "HALT_INDETERMINATE_AWAITING_PROBE"

        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO egress_wal (idempotency_key, agent_id, caid, target_api, state)
                VALUES (?, ?, ?, ?, 'IN_FLIGHT')
                """,
                (idempotency_key, agent_id, caid, target_api),
            )
        return "LATCHED_IN_FLIGHT"

    def pre_suspend_flush(self, agent_id: str) -> int:
        """
        Cube Sandbox / Agent Substrate Pre-Suspend Hook:
        Atomically transitions all `IN_FLIGHT` requests for `agent_id` to `INDETERMINATE`
        and flushes the SQLite WAL prior to KVM memory freeze.
        """
        with self._conn:
            cursor = self._conn.execute(
                """
                UPDATE egress_wal SET state = 'INDETERMINATE'
                WHERE agent_id = ? AND state = 'IN_FLIGHT'
                """,
                (agent_id,),
            )
            return int(cursor.rowcount)

    def post_resume_reconcile(
        self,
        agent_id: str,
        probe_fn: Callable[[str, str], str],
    ) -> Dict[str, str]:
        """
        Post-Resume Reconciliation Hook:
        Queries authoritative provider status for every `INDETERMINATE` entry.
        Fails closed (`RuntimeError`) if any target remains `INDETERMINATE`.
        """
        rows = self._conn.execute(
            """
            SELECT idempotency_key, caid, target_api FROM egress_wal
            WHERE agent_id = ? AND state = 'INDETERMINATE'
            ORDER BY idempotency_key
            """,
            (agent_id,),
        ).fetchall()

        results: Dict[str, str] = {}
        for idem_key, caid, target_api in rows:
            resolved_state = probe_fn(target_api, idem_key)
            if resolved_state not in ("COMMITTED", "REJECTED"):
                raise RuntimeError(
                    f"HALT_RECONCILIATION_FAILED: CAID {caid} ({idem_key}) remains INDETERMINATE"
                )

            with self._conn:
                self._conn.execute(
                    "UPDATE egress_wal SET state = ? WHERE idempotency_key = ?",
                    (resolved_state, idem_key),
                )
            results[caid] = resolved_state

        return results


@dataclass(frozen=True)
class Kiro1000PRSimulationSummary:
    total_prs_evaluated: int
    auto_merged_count: int
    human_escalated_count: int
    halted_single_scope_creep_count: int
    halted_cumulative_smurfing_count: int
    uncontained_high_risk_merges: int
    simulation_caid: str


class Kiro1000PRSimulator:
    """
    Simulates a 1,000-PR/week autonomous software factory with cumulative epoch tracking
    (defending against Split-PR Smurfing).
    """

    def __init__(
        self,
        repo_sources: Mapping[str, str],
        max_auto_merge_radius_bps: int = 3000,
        max_single_pr_lines: int = 50,
        max_epoch_cumulative_lines: int = 50,
    ) -> None:
        self.governor = HypergraphBlastRadiusGovernor(
            repo_sources=repo_sources,
            max_auto_merge_radius_bps=max_auto_merge_radius_bps,
            max_lines_changed=max_single_pr_lines,
            max_files_touched=3,
        )
        self.max_epoch_cumulative_lines = max_epoch_cumulative_lines
        self._epoch_lines_used: Dict[str, int] = {}

    def evaluate_pr_with_epoch_guard(
        self, task_epoch_id: str, pr: PRDiffSpec
    ) -> Tuple[str, int]:
        verdict = self.governor.evaluate_pr(pr)
        if verdict.action != "AUTO_MERGE":
            return verdict.action, verdict.blast_radius_bps

        # Check Cumulative Epoch Line Budget (Defends against Split-PR Smurfing)
        pr_lines = pr.lines_added + pr.lines_deleted
        prior_lines = self._epoch_lines_used.get(task_epoch_id, 0)
        if prior_lines + pr_lines > self.max_epoch_cumulative_lines:
            return "HALT_CUMULATIVE_SCOPE_CREEP", verdict.blast_radius_bps

        self._epoch_lines_used[task_epoch_id] = prior_lines + pr_lines
        return "AUTO_MERGE", verdict.blast_radius_bps

    def run_1000_pr_stress_test(self) -> Kiro1000PRSimulationSummary:
        auto_merged = 0
        human_escalated = 0
        halted_single_creep = 0
        halted_smurfing = 0
        uncontained_high_risk = 0

        # 1. 750 Legitimate Leaf-Node Micro-PRs (<= 50 lines, 0 bps blast radius)
        for i in range(1, 751):
            pr = PRDiffSpec(
                pr_id=f"pr_leaf_{i:04d}",
                intent_caid=f"sha256:leaf_{i:04d}",
                changed_files=("src/leaf_formatter.py",),
                lines_added=10,
                lines_deleted=2,
            )
            action, radius_bps = self.evaluate_pr_with_epoch_guard(f"epoch_leaf_{i}", pr)
            if action == "AUTO_MERGE":
                auto_merged += 1
            elif radius_bps > 3000:
                uncontained_high_risk += 1

        # 2. 100 High-Fan-In Core Architecture PRs (`src/core_auth.py` -> 6000 bps blast radius)
        for i in range(1, 101):
            pr = PRDiffSpec(
                pr_id=f"pr_core_{i:04d}",
                intent_caid=f"sha256:core_{i:04d}",
                changed_files=("src/core_auth.py",),
                lines_added=4,
                lines_deleted=2,
            )
            action, radius_bps = self.evaluate_pr_with_epoch_guard(f"epoch_core_{i}", pr)
            if action == "HUMAN_ESCALATE":
                human_escalated += 1
            elif action == "AUTO_MERGE" and radius_bps > 3000:
                uncontained_high_risk += 1

        # 3. 100 Over-Eager Single-PR Subsystem Rewrites (90 lines > 50-line cap)
        for i in range(1, 101):
            pr = PRDiffSpec(
                pr_id=f"pr_creep_{i:04d}",
                intent_caid=f"sha256:creep_{i:04d}",
                changed_files=("src/leaf_formatter.py",),
                lines_added=70,
                lines_deleted=20,
            )
            action, _ = self.evaluate_pr_with_epoch_guard(f"epoch_creep_{i}", pr)
            if action == "HALT_SCOPE_CREEP":
                halted_single_creep += 1

        # 4. 50 Split-PR Smurfing PRs (all sharing ONE `epoch_smurf_attack` task ID, 10 lines each)
        # First 5 PRs (5 * 10 = 50 lines) are within the 50-line epoch budget;
        # Remaining 45 PRs exceed the 50-line cumulative epoch budget and are halted!
        for i in range(1, 51):
            pr = PRDiffSpec(
                pr_id=f"pr_smurf_{i:04d}",
                intent_caid=f"sha256:smurf_{i:04d}",
                changed_files=("src/leaf_formatter.py",),
                lines_added=8,
                lines_deleted=2,  # 10 lines per micro-PR
            )
            action, _ = self.evaluate_pr_with_epoch_guard("epoch_smurf_attack", pr)
            if action == "AUTO_MERGE":
                auto_merged += 1
            elif action == "HALT_CUMULATIVE_SCOPE_CREEP":
                halted_smurfing += 1

        total = 750 + 100 + 100 + 50
        payload = {
            "auto_merged_count": auto_merged,
            "halted_cumulative_smurfing_count": halted_smurfing,
            "halted_single_scope_creep_count": halted_single_creep,
            "human_escalated_count": human_escalated,
            "total_prs_evaluated": total,
            "uncontained_high_risk_merges": uncontained_high_risk,
        }

        return Kiro1000PRSimulationSummary(
            total_prs_evaluated=total,
            auto_merged_count=auto_merged,
            human_escalated_count=human_escalated,
            halted_single_scope_creep_count=halted_single_creep,
            halted_cumulative_smurfing_count=halted_smurfing,
            uncontained_high_risk_merges=uncontained_high_risk,
            simulation_caid=sha256_jcs_caid(payload),
        )
