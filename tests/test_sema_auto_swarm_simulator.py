#!/usr/bin/env python3
"""
tests/test_sema_auto_swarm_simulator.py — Zero-Mock 100-Agent Swarm Verification Suite

Verifies:
1. 100-Agent Tree Topology Integrity (1 Root, 5 Leads, 20 Tasks, 74 Leaves).
2. Monotonic Taint Cascade (irreversible propagation from Leads/Tasks to Leaves).
3. Scope Confinement (100% containment of unauthorized egress attempts).
4. SEMA-Auto Trajectory Drift Interception in Multi-Agent Swarm.
5. Unified JCS Merkle Root Attestation.
"""

from __future__ import annotations

import pytest

from src.a2a_trajectory_interlock import A2ATrajectoryInterlock
from src.sema_auto_swarm_simulator import (
    SemaAutoSwarmSimulator,
    SwarmAgentNode,
    SwarmExecutionSummary,
)


class AdversarialLeakingInterlock(A2ATrajectoryInterlock):
    """Subclass of interlock to simulate adversarial edge cases with real objects and zero mocks."""

    def __init__(
        self,
        target_spiffe_leak: str,
        leak_mode: str,
        max_drift_threshold_bps: int = 4000,
    ) -> None:
        super().__init__(max_drift_threshold_bps=max_drift_threshold_bps)
        self.target_spiffe_leak = target_spiffe_leak
        self.leak_mode = leak_mode

    def validate_delegated_egress(
        self,
        child_spiffe_id: str,
        target_host: str,
        action_caid: str,
    ) -> tuple[bool, str]:
        if child_spiffe_id == self.target_spiffe_leak:
            if self.leak_mode == "STEP2_LEAK":
                return False, "HALT_UNKNOWN_FAILURE_TRIGGERING_LEAK"
            if self.leak_mode == "STEP3_LEAK":
                if target_host == "api.unauthorized-exfil.org":
                    return True, "AUTHORIZED_UNCONTAINED_EXFIL"
                return True, "OK_DELEGATED_EGRESS_PERMITTED"
        return super().validate_delegated_egress(child_spiffe_id, target_host, action_caid)


def test_1_swarm_topology_structure_and_tiers() -> None:
    sim = SemaAutoSwarmSimulator(max_drift_threshold_bps=4000)

    # 1. Total agents must be exactly 100
    assert len(sim.nodes) == 100

    root = sim.nodes[SemaAutoSwarmSimulator.ROOT_ID]
    assert root.tier == 0
    assert root.parent_id == ""

    # Count by tier
    tiers = {0: 0, 1: 0, 2: 0, 3: 0}
    for node in sim.nodes.values():
        tiers[node.tier] += 1

    assert tiers[0] == 1   # 1 Root
    assert tiers[1] == 5   # 5 Leads
    assert tiers[2] == 20  # 20 Task Agents
    assert tiers[3] == 74  # 74 Leaf Workers

    # Verify all parents exist in topology
    for node in sim.nodes.values():
        if node.tier > 0:
            assert node.parent_id in sim.nodes
            parent = sim.nodes[node.parent_id]
            assert parent.tier == node.tier - 1


def test_2_swarm_stress_benchmark_and_zero_leak_containment() -> None:
    sim = SemaAutoSwarmSimulator(max_drift_threshold_bps=4000)

    # Run benchmark: lead_00 tainted, task_05 compromised
    summary: SwarmExecutionSummary = sim.run_full_swarm_stress_benchmark(
        taint_injection_lead="lead_00",
        compromised_task="task_05",
    )

    # 1. High-level containment assertions
    assert summary.total_agents == 100
    assert summary.uncontained_leaks_count == 0  # Zero leaks!

    # 2. Scope confinement: 10/10 illegal host escalations halted
    assert summary.halted_escalations_count == 10

    # 3. SEMA-Auto drift: 50/50 hijacked turns halted
    assert summary.halted_drift_count == 50

    # 4. Taint distribution verified
    # Compromised: task_05 + its assigned leaf workers
    assert summary.compromised_agents_count > 0

    # Tainted: lead_00 + its 4 tasks + their leaf workers
    assert summary.tainted_agents_count > 0

    # Clean: remaining unexposed branches
    assert summary.clean_agents_count > 0

    # Total subordinate tokens must equal 99 (all except root)
    assert summary.clean_agents_count + summary.tainted_agents_count + summary.compromised_agents_count == 99

    # 5. Merkle root integrity
    assert summary.swarm_merkle_root.startswith("sha256:")
    assert len(summary.swarm_merkle_root) == 71  # sha256: + 64 hex chars


def test_3_monotonic_taint_cascade_invariant() -> None:
    """Verifies that no leaf node under a tainted lead can ever have taint_level 0."""
    sim = SemaAutoSwarmSimulator(max_drift_threshold_bps=4000)

    # Inject taint only into lead_00
    sim.run_full_swarm_stress_benchmark(
        taint_injection_lead="lead_00",
        compromised_task="task_05",
    )

    lead_00_token = sim.tokens["lead_00"]
    assert lead_00_token.taint_level == 1

    # Find all tasks under lead_00
    tasks_under_lead_00 = [n.agent_id for n in sim.nodes.values() if n.parent_id == "lead_00"]
    assert len(tasks_under_lead_00) == 4

    for task_id in tasks_under_lead_00:
        task_token = sim.tokens[task_id]
        # Must have inherited taint >= 1
        assert task_token.taint_level >= 1

        # Find leaves under this task
        leaves_under_task = [n.agent_id for n in sim.nodes.values() if n.parent_id == task_id]
        for leaf_id in leaves_under_task:
            leaf_token = sim.tokens[leaf_id]
            # Must also have inherited taint >= 1 (irreversible cascade)
            assert leaf_token.taint_level >= 1


def test_4_dataclass_immutability_and_exact_topology_slicing() -> None:
    from dataclasses import FrozenInstanceError

    sim = SemaAutoSwarmSimulator(max_drift_threshold_bps=4000)

    # 1. Immutability of SwarmAgentNode and SwarmExecutionSummary
    node = sim.nodes[SemaAutoSwarmSimulator.ROOT_ID]
    with pytest.raises(FrozenInstanceError):
        node.tier = 99  # type: ignore

    summary = sim.run_full_swarm_stress_benchmark("lead_00", "task_05")
    with pytest.raises(FrozenInstanceError):
        summary.total_agents = 500  # type: ignore

    # 2. Exact Task Host Slicing: task nodes must only have exactly 1 host (subset of lead's 2 hosts)
    assert len(sim.nodes["lead_00"].allowed_hosts) == 2
    assert len(sim.nodes["task_00"].allowed_hosts) == 1
    assert sim.nodes["task_00"].allowed_hosts == ("api.github.com",)

    # 3. Exact Leaf-to-Task Parent Mapping
    assert sim.nodes["leaf_00"].parent_id == "task_00"
    assert sim.nodes["leaf_20"].parent_id == "task_00"
    assert sim.nodes["leaf_21"].parent_id == "task_01"

    # 4. Exact Taint Level Invariant Checks
    assert sim.nodes[SemaAutoSwarmSimulator.ROOT_ID].tier == 0
    assert sim.nodes["leaf_00"].initial_taint == 0
    assert sim.tokens["lead_00"].taint_level == 1
    assert sim.tokens["lead_00"].taint_level != 2
    assert sim.tokens["task_05"].taint_level == 3
    assert sim.tokens["task_05"].taint_level != 2



def test_5_swarm_leak_counter_and_delegation_count() -> None:
    # 1. Test exact delegation count and root initial taint
    sim = SemaAutoSwarmSimulator(max_drift_threshold_bps=4000)
    assert sim.nodes[SemaAutoSwarmSimulator.ROOT_ID].initial_taint == 0
    del_count = sim.delegate_swarm(set(), set())
    assert del_count == 99

    # 2. Test uncontained leak detection path in step 2 (kills line 227 CONST_PERTURB)
    sim_step2 = SemaAutoSwarmSimulator(max_drift_threshold_bps=4000)
    leaf25_spiffe = sim_step2.nodes["leaf_25"].spiffe_id
    sim_step2.interlock = AdversarialLeakingInterlock(
        target_spiffe_leak=leaf25_spiffe,
        leak_mode="STEP2_LEAK",
        max_drift_threshold_bps=4000,
    )
    sim_step2.interlock.register_root_authority(sim_step2.ROOT_SPIFFE, sim_step2.ROOT_HOSTS)
    summary_step2 = sim_step2.run_full_swarm_stress_benchmark(
        taint_injection_lead="lead_00",
        compromised_task="task_05",
    )
    assert summary_step2.uncontained_leaks_count == 1

    # 3. Test uncontained leak detection path in step 3 (kills line 242 CONST_PERTURB)
    sim_step3 = SemaAutoSwarmSimulator(max_drift_threshold_bps=4000)
    leaf10_spiffe = sim_step3.nodes["leaf_10"].spiffe_id
    sim_step3.interlock = AdversarialLeakingInterlock(
        target_spiffe_leak=leaf10_spiffe,
        leak_mode="STEP3_LEAK",
        max_drift_threshold_bps=4000,
    )
    sim_step3.interlock.register_root_authority(sim_step3.ROOT_SPIFFE, sim_step3.ROOT_HOSTS)
    summary_step3 = sim_step3.run_full_swarm_stress_benchmark(
        taint_injection_lead="lead_00",
        compromised_task="task_05",
    )
    assert summary_step3.uncontained_leaks_count == 1
