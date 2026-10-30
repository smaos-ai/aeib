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
tests/test_kiro_1000pr_and_cube_wal.py — Verification Suite

Evaluates:
  1. Durable SQLite-WAL Cube/Substrate Auto-Pause Interlock (`DurableCubeAutoPauseInterlock`)
  2. 1,000-PR Kiro Factory Blast-Radius & Anti-Smurfing Stress Simulation (`Kiro1000PRSimulator`)

Status: INTERNAL PREVIEW COMMISSIONED.
Zero mocks, zero floats, deterministic cryptographic validation.
"""

from __future__ import annotations

import pytest

from src.hypergraph_blast_radius import PRDiffSpec
from src.kiro_1000pr_and_cube_wal_simulator import (
    DurableCubeAutoPauseInterlock,
    Kiro1000PRSimulator,
)
from tests.test_substrate_cube_and_blast_radius import _sample_repo_graph


def test_1_durable_sqlite_wal_auto_pause_blocks_zombie_double_spend() -> None:
    interlock = DurableCubeAutoPauseInterlock(":memory:")
    agent_id = "spiffe://sovereign.nexus/ns/prod/actor/fin_01"

    # 1. Latch outbound payment before KVM suspend
    status = interlock.register_egress_attempt(
        agent_id=agent_id,
        caid="sha256:pay_500",
        idempotency_key="idem_txn_500",
        target_api="https://api.stripe.com/v1/charges",
    )
    assert status == "LATCHED_IN_FLIGHT"

    # 2. Trigger Cube Auto-Pause before HTTP ACK returns
    frozen = interlock.pre_suspend_flush(agent_id)
    assert frozen == 1

    # 3. If resumed agent attempts a blind retry BEFORE reconciliation probe -> BLOCKED!
    blind_retry = interlock.register_egress_attempt(
        agent_id=agent_id,
        caid="sha256:pay_500",
        idempotency_key="idem_txn_500",
        target_api="https://api.stripe.com/v1/charges",
    )
    assert blind_retry == "HALT_INDETERMINATE_AWAITING_PROBE"

    # 4. Run post-resume reconciliation probe confirming Stripe executed the charge
    reconciled = interlock.post_resume_reconcile(
        agent_id,
        probe_fn=lambda api, key: "COMMITTED" if key == "idem_txn_500" else "INDETERMINATE",
    )
    assert reconciled["sha256:pay_500"] == "COMMITTED"

    # 5. Any subsequent retry with the committed idempotency key is permanently blocked
    post_commit_retry = interlock.register_egress_attempt(
        agent_id=agent_id,
        caid="sha256:pay_500",
        idempotency_key="idem_txn_500",
        target_api="https://api.stripe.com/v1/charges",
    )
    assert post_commit_retry == "HALT_DUPLICATE_COMMITTED_BLOCKED"


def test_2_kiro_1000_pr_factory_simulation_contains_all_high_risk_and_smurfing_prs() -> None:
    sim = Kiro1000PRSimulator(
        repo_sources=_sample_repo_graph(),
        max_auto_merge_radius_bps=3000,
        max_single_pr_lines=50,
        max_epoch_cumulative_lines=50,
    )
    summary = sim.run_1000_pr_stress_test()

    assert summary.total_prs_evaluated == 1000
    assert summary.auto_merged_count == 755          # 750 legitimate leaf PRs + first 5 micro-PRs (50 lines)
    assert summary.human_escalated_count == 100      # 100 high-blast-radius core_auth PRs
    assert summary.halted_single_scope_creep_count == 100  # 100 single-PR >50-line subsystem rewrites
    assert summary.halted_cumulative_smurfing_count == 45  # 45 split-PR smurfing attempts caught!
    assert summary.uncontained_high_risk_merges == 0
    assert summary.simulation_caid.startswith("sha256:")


def test_3_reconciliation_fails_closed_when_indeterminate_remains() -> None:
    """Verifies that reconciliation strictly raises RuntimeError when probe is non-terminal."""
    interlock = DurableCubeAutoPauseInterlock(":memory:")
    agent_id = "spiffe://sovereign.nexus/ns/prod/actor/reconcile_test"

    interlock.register_egress_attempt(
        agent_id=agent_id,
        caid="sha256:rec_01",
        idempotency_key="idem_rec_01",
        target_api="https://api.test.org/charge",
    )
    interlock.pre_suspend_flush(agent_id)

    # Probe returns unresolved "INDETERMINATE" -> must fail closed
    with pytest.raises(RuntimeError, match="HALT_RECONCILIATION_FAILED"):
        interlock.post_resume_reconcile(
            agent_id=agent_id,
            probe_fn=lambda api, key: "INDETERMINATE",
        )

    # Probe returns valid "REJECTED" -> resolves cleanly
    reconciled = interlock.post_resume_reconcile(
        agent_id=agent_id,
        probe_fn=lambda api, key: "REJECTED",
    )
    assert reconciled["sha256:rec_01"] == "REJECTED"


def test_4_exact_boundary_conditions_and_multi_file_creep() -> None:
    """Tests exact lines/files limits and multi-file scope creep in Kiro simulator."""
    sim = Kiro1000PRSimulator(
        repo_sources=_sample_repo_graph(),
        max_auto_merge_radius_bps=3000,
        max_single_pr_lines=50,
        max_epoch_cumulative_lines=50,
    )

    # 4A: Exactly 50 lines (30 + 20) in 1 file -> AUTO_MERGE
    pr_50 = PRDiffSpec(
        pr_id="pr_boundary_50",
        intent_caid="sha256:bound_50",
        changed_files=("src/leaf_formatter.py",),
        lines_added=30,
        lines_deleted=20,
    )
    act_50, _ = sim.evaluate_pr_with_epoch_guard("epoch_bound_50", pr_50)
    assert act_50 == "AUTO_MERGE"

    # 4B: Exactly 51 lines (31 + 20) in 1 file -> HALT_SCOPE_CREEP
    pr_51 = PRDiffSpec(
        pr_id="pr_boundary_51",
        intent_caid="sha256:bound_51",
        changed_files=("src/leaf_formatter.py",),
        lines_added=31,
        lines_deleted=20,
    )
    act_51, _ = sim.evaluate_pr_with_epoch_guard("epoch_bound_51", pr_51)
    assert act_51 == "HALT_SCOPE_CREEP"

    # 4C: 4 files touched (> 3 max_files_touched limit) with only 12 lines -> HALT_SCOPE_CREEP
    pr_4files = PRDiffSpec(
        pr_id="pr_4files",
        intent_caid="sha256:4files",
        changed_files=(
            "src/leaf_formatter.py",
            "src/core_auth.py",
            "src/session.py",
            "src/api_router.py",
        ),
        lines_added=8,
        lines_deleted=4,
    )
    act_4files, _ = sim.evaluate_pr_with_epoch_guard("epoch_4files", pr_4files)
    assert act_4files == "HALT_SCOPE_CREEP"


def test_5_high_blast_radius_threshold_detection() -> None:
    """Tests simulation detection when max_auto_merge_radius_bps is perturbed."""
    # When max_auto_merge_radius_bps is set to 7000 bps, core_auth (6000 bps) auto-merges,
    # and uncontained_high_risk is flagged because radius_bps (6000) > 3000!
    permissive_sim = Kiro1000PRSimulator(
        repo_sources=_sample_repo_graph(),
        max_auto_merge_radius_bps=7000,
        max_single_pr_lines=50,
        max_epoch_cumulative_lines=50,
    )
    summary = permissive_sim.run_1000_pr_stress_test()
    # All 100 core architecture PRs (6000 bps) are uncontained high-risk merges!
    assert summary.uncontained_high_risk_merges == 100
    assert summary.human_escalated_count == 0
