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
tests/test_phase2_sovereign_evolution.py
================================================================================
Falsification Suite for Phase II Sovereign Evolution Modules:
1. `src/evolutionary_orchestrator.py` (STEWARD 5-Branch Evolutionary Worktree)
2. `src/semantic_two_phase_commit.py` (Tsinghua Semantic ACID 2PC Rollback)
3. `src/physical_typestate_enforcer.py` (LeHami Type-State Physics AST Gate)
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from src.evolutionary_orchestrator import (
    CandidateBranch,
    StewardEvolutionaryOrchestrator,
)
from src.physical_typestate_enforcer import (
    PhysicalEnvelopeSpec,
    PhysicalTypeStateEnforcer,
)
from src.semantic_two_phase_commit import (
    SemanticACIDCoordinator,
)


@pytest.fixture
def git_workspace(tmp_path: Path) -> Path:
    repo = tmp_path / "sovereign_repo"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / ".git").mkdir()
    (repo / "tests").mkdir()
    (repo / "src").mkdir()
    return repo


def test_1_steward_evolutionary_orchestrator_selects_optimal_and_blocks_cheaters(
    git_workspace: Path,
) -> None:
    orchestrator = StewardEvolutionaryOrchestrator(workspace_root=str(git_workspace))

    candidates = [
        # Branch 1: Cheater attempting to overwrite test suite
        CandidateBranch(
            branch_id="branch_cheat_tests",
            target_file="src/hyper_su_retrieval.py",
            proposed_code=(
                "def search():\n"
                "    with open('tests/test_search.py', 'w') as f:\n"
                "        f.write('assert True')\n"
            ),
            tests_passed=True,
            mutation_kill_bps=9900,
            latency_reduction_bps=5000,
        ),
        # Branch 2: Uses forbidden `eval` reflection
        CandidateBranch(
            branch_id="branch_reflection",
            target_file="src/hyper_su_retrieval.py",
            proposed_code="def search(q: str):\n    return eval(q)\n",
            tests_passed=True,
            mutation_kill_bps=9500,
            latency_reduction_bps=3000,
        ),
        # Branch 3: Honest refactor with weak mutation score (85.0% < 90.0% floor)
        CandidateBranch(
            branch_id="branch_weak_mutation",
            target_file="src/hyper_su_retrieval.py",
            proposed_code="def search(q: str) -> list:\n    return [q]\n",
            tests_passed=True,
            mutation_kill_bps=8500,
            latency_reduction_bps=2500,
        ),
        # Branch 4: Valid refactor (+12% faster, 92.0% mutation kill)
        CandidateBranch(
            branch_id="branch_valid_mid",
            target_file="src/hyper_su_retrieval.py",
            proposed_code="def search(q: str) -> list:\n    return [q.strip()]\n",
            tests_passed=True,
            mutation_kill_bps=9200,
            latency_reduction_bps=1200,
        ),
        # Branch 5: Winning refactor (+20% faster, 96.0% mutation kill)
        CandidateBranch(
            branch_id="branch_winning_fast",
            target_file="src/hyper_su_retrieval.py",
            proposed_code="def search(q: str) -> list:\n    return [q.lower().strip()]\n",
            tests_passed=True,
            mutation_kill_bps=9600,
            latency_reduction_bps=2000,
        ),
        # Branch 6: Failing tests
        CandidateBranch(
            branch_id="branch_tests_fail",
            target_file="src/hyper_su_retrieval.py",
            proposed_code="def search(q: str) -> list:\n    return []\n",
            tests_passed=False,
            mutation_kill_bps=9500,
            latency_reduction_bps=1000,
        ),
        # Branch 7: Latency regression (-1 bps slower)
        CandidateBranch(
            branch_id="branch_regression",
            target_file="src/hyper_su_retrieval.py",
            proposed_code="def search(q: str) -> list:\n    import time; time.sleep(0.01); return [q]\n",
            tests_passed=True,
            mutation_kill_bps=9500,
            latency_reduction_bps=-1,
        ),
        # Branch 8: Zero latency gain (neutral latency 0 bps)
        CandidateBranch(
            branch_id="branch_neutral_latency",
            target_file="src/hyper_su_retrieval.py",
            proposed_code="def search(q: str) -> list:\n    return [q]\n",
            tests_passed=True,
            mutation_kill_bps=9100,
            latency_reduction_bps=0,
        ),
    ]

    verdict = orchestrator.evaluate_and_select_winner(
        task_id="task_refactor_retrieval",
        candidates=candidates,
    )

    assert verdict.task_id == "task_refactor_retrieval"
    assert verdict.winning_branch_id == "branch_winning_fast"
    assert verdict.winning_score_bps == 9600 + 2000  # 11600 bps
    assert verdict.consensus_caid.startswith("sha256:")

    # Verify branch evaluation details
    eval_map = {b.branch_id: b for b in verdict.evaluated_branches}
    assert eval_map["branch_cheat_tests"].eligible is False
    assert eval_map["branch_cheat_tests"].composite_score_bps == 0
    assert "HALT_AST_OPEN_WRITE" in eval_map["branch_cheat_tests"].rejection_reason

    assert eval_map["branch_reflection"].eligible is False
    assert eval_map["branch_reflection"].composite_score_bps == 0
    assert "HALT_FORBIDDEN_REFLECTION:eval" in eval_map["branch_reflection"].rejection_reason

    assert eval_map["branch_weak_mutation"].eligible is False
    assert eval_map["branch_weak_mutation"].composite_score_bps == 0
    assert "HALT_MUTATION_BELOW_FLOOR:8500" in eval_map["branch_weak_mutation"].rejection_reason

    assert eval_map["branch_tests_fail"].eligible is False
    assert eval_map["branch_tests_fail"].composite_score_bps == 0
    assert eval_map["branch_tests_fail"].rejection_reason == "HALT_UNIT_TESTS_FAILED"

    assert eval_map["branch_regression"].eligible is False
    assert eval_map["branch_regression"].composite_score_bps == 0
    assert "HALT_LATENCY_REGRESSION:-1" in eval_map["branch_regression"].rejection_reason

    assert eval_map["branch_neutral_latency"].eligible is True
    assert eval_map["branch_neutral_latency"].composite_score_bps == 9100

    assert eval_map["branch_valid_mid"].eligible is True
    assert eval_map["branch_winning_fast"].eligible is True
    assert eval_map["branch_winning_fast"].composite_score_bps > eval_map["branch_valid_mid"].composite_score_bps

    # Dataclass immutability tests
    with pytest.raises((AttributeError, TypeError)):
        verdict.winning_score_bps = 99999  # type: ignore
    with pytest.raises((AttributeError, TypeError)):
        eval_map["branch_winning_fast"].composite_score_bps = 0  # type: ignore
    with pytest.raises((AttributeError, TypeError)):
        candidates[0].branch_id = "mutated"  # type: ignore

    # Verify to_dict serialization
    vd = verdict.to_dict()
    assert vd["winning_branch_id"] == "branch_winning_fast"
    assert vd["winning_score_bps"] == 11600
    assert len(vd["evaluated_branches"]) == 8

    b_dict = eval_map["branch_winning_fast"].to_dict()
    assert b_dict["eligible"] is True
    assert b_dict["composite_score_bps"] == 11600

    # Validation errors on orchestrator inputs
    with pytest.raises(ValueError, match="ERR_EMPTY_TASK_ID"):
        orchestrator.evaluate_and_select_winner("", candidates)

    with pytest.raises(ValueError, match="ERR_EMPTY_CANDIDATE_POOL"):
        orchestrator.evaluate_and_select_winner("task_1", [])

    # Validation errors on CandidateBranch
    with pytest.raises(ValueError, match="branch_id"):
        CandidateBranch("", "f.py", "x=1", True, 9000, 0)
    with pytest.raises(ValueError, match="target_file"):
        CandidateBranch("b1", "", "x=1", True, 9000, 0)
    with pytest.raises(ValueError, match="mutation_kill_bps"):
        CandidateBranch("b1", "f.py", "x=1", True, -1, 0)
    with pytest.raises(ValueError, match="mutation_kill_bps"):
        CandidateBranch("b1", "f.py", "x=1", True, 10001, 0)
    with pytest.raises(ValueError, match="latency_reduction_bps"):
        CandidateBranch("b1", "f.py", "x=1", True, 9000, "fast")  # type: ignore

    # Test all rejected scenario where no winner emerges
    rejected_verdict = orchestrator.evaluate_and_select_winner(
        "task_all_bad",
        [candidates[0]],  # only the cheater
    )
    assert rejected_verdict.winning_branch_id is None
    assert rejected_verdict.winning_score_bps == 0


def test_2_tsinghua_semantic_acid_two_phase_commit_and_rollback() -> None:
    initial_graph = {
        "knowledge_nodes": ["node_1", "node_2"],
        "effect_latch_status": "LATCHED_CLEAN",
        "version_epoch": 1,
    }
    coord = SemanticACIDCoordinator(initial_state=initial_graph)
    initial_caid = coord.current_state_caid()

    # 1. Isolation: Agent A acquires exclusive lock on knowledge_nodes
    err_a = coord.begin_transaction(
        tx_id="tx_agent_a",
        agent_id="agent_builder_1",
        target_keys=frozenset({"knowledge_nodes", "version_epoch"}),
    )
    assert err_a is None

    # Agent B attempts to acquire lock on the same keys -> Must fail closed
    err_b = coord.begin_transaction(
        tx_id="tx_agent_b",
        agent_id="agent_builder_2",
        target_keys=frozenset({"knowledge_nodes"}),
    )
    assert err_b is not None
    assert "HALT_LOCK_CONTENTION" in err_b.status

    # 2. Stage speculative writes under Transaction A
    coord.stage_write("tx_agent_a", "knowledge_nodes", ["node_1", "node_2", "speculative_node_3"])
    coord.stage_write("tx_agent_a", "version_epoch", 2)

    # 3. Simulate transport network drop (TCP RST / HTTP 504) -> Atomic Rollback
    rollback_receipt = coord.finalize_handoff(
        tx_id="tx_agent_a",
        transport_ok=False,
        monitor_verified=True,
    )
    assert "EFFECT_INDETERMINATE_ROLLED_BACK:TRANSPORT_DROP" in rollback_receipt.status
    assert rollback_receipt.post_state_caid == initial_caid

    # Verify 0.0% state drift after rollback
    assert coord.read_committed("knowledge_nodes") == ["node_1", "node_2"]
    assert coord.read_committed("version_epoch") == 1
    assert coord.current_state_caid() == initial_caid
    assert not coord.is_key_locked("knowledge_nodes")

    # 4. Now execute a clean, verified transaction to completion
    coord.begin_transaction(
        tx_id="tx_agent_c",
        agent_id="agent_builder_3",
        target_keys=frozenset({"knowledge_nodes", "version_epoch"}),
    )
    coord.stage_write("tx_agent_c", "knowledge_nodes", ["node_1", "node_2", "verified_node_3"])
    coord.stage_write("tx_agent_c", "version_epoch", 2)

    commit_receipt = coord.finalize_handoff(
        tx_id="tx_agent_c",
        transport_ok=True,
        monitor_verified=True,
    )
    assert commit_receipt.status == "COMMITTED"
    assert commit_receipt.post_state_caid != initial_caid
    assert coord.read_committed("knowledge_nodes") == ["node_1", "node_2", "verified_node_3"]
    assert coord.read_committed("version_epoch") == 2
    assert coord.read_committed("non_existent_key") is None

    # Test receipt serialization & immutability
    rd = commit_receipt.to_dict()
    assert rd["status"] == "COMMITTED"
    assert rd["tx_id"] == "tx_agent_c"
    with pytest.raises((AttributeError, TypeError)):
        commit_receipt.status = "MUTATED"  # type: ignore

    # 5. Test monitor verification rejection branch
    coord.begin_transaction(
        tx_id="tx_agent_d",
        agent_id="agent_builder_4",
        target_keys=frozenset({"version_epoch"}),
    )
    coord.stage_write("tx_agent_d", "version_epoch", 999)
    reject_receipt = coord.finalize_handoff(
        tx_id="tx_agent_d",
        transport_ok=True,
        monitor_verified=False,
    )
    assert "EFFECT_INDETERMINATE_ROLLED_BACK:MONITOR_REJECTED" in reject_receipt.status
    assert coord.read_committed("version_epoch") == 2  # preserved

    # 6. Validation error checking
    with pytest.raises(ValueError, match="ERR_EMPTY_TX_ID"):
        coord.begin_transaction("", "agent", frozenset({"k"}))

    with pytest.raises(ValueError, match="ERR_EMPTY_AGENT_ID"):
        coord.begin_transaction("tx", "", frozenset({"k"}))

    with pytest.raises(ValueError, match="ERR_EMPTY_TARGET_KEYS"):
        coord.begin_transaction("tx", "agent", frozenset())

    with pytest.raises(ValueError, match="ERR_UNKNOWN_TRANSACTION"):
        coord.stage_write("tx_ghost", "k", 1)

    coord.begin_transaction("tx_active", "agent_1", frozenset({"k1"}))
    with pytest.raises(ValueError, match="ERR_UNDECLARED_KEY_WRITE"):
        coord.stage_write("tx_active", "undeclared_k2", 1)

    with pytest.raises(ValueError, match="ERR_UNKNOWN_TRANSACTION"):
        coord.finalize_handoff("tx_ghost", True, True)

    coord.finalize_handoff("tx_active", False, False)


def test_3_lehami_physical_typestate_enforcer() -> None:
    envelopes = {
        "NewtonMeters": PhysicalEnvelopeSpec("NewtonMeters", min_value=0, max_value=200),
        "MinorUnitUSD": PhysicalEnvelopeSpec("MinorUnitUSD", min_value=0, max_value=1000000),
        "EpochSeconds": PhysicalEnvelopeSpec("EpochSeconds", min_value=0, max_value=2000000000),
    }
    enforcer = PhysicalTypeStateEnforcer(envelopes=envelopes)

    # 1. Hardware Actuator Limit Breach: 500 Nm exceeds joint limit of 200 Nm
    exceeded_torque_code = (
        "def drive_actuator():\n"
        "    joint_torque: NewtonMeters = 500\n"
        "    return joint_torque\n"
    )
    v1 = enforcer.verify_ast_physics(exceeded_torque_code)
    assert v1.passed is False
    assert "HALT_PHYSICAL_LAW_VIOLATION:BOUNDS_EXCEEDED:NewtonMeters=500" in v1.status_code
    assert v1.violating_symbol == "joint_torque"

    # 2. Re-assignment exceeding bounds
    reassign_code = (
        "def adjust():\n"
        "    torque: NewtonMeters = 100\n"
        "    torque = 250\n"
        "    return torque\n"
    )
    v2 = enforcer.verify_ast_physics(reassign_code)
    assert v2.passed is False
    assert "BOUNDS_EXCEEDED:NewtonMeters=250" in v2.status_code

    # 3. Dimensional Mismatch: Adding dollars to seconds, and subtraction mismatch
    dimensional_clash_code = (
        "def calculate_payout():\n"
        "    balance: MinorUnitUSD = 10000\n"
        "    deadline: EpochSeconds = 1700000000\n"
        "    result = balance + deadline\n"
        "    sub_diff = balance - deadline\n"
        "    return result, sub_diff\n"
    )
    v3 = enforcer.verify_ast_physics(dimensional_clash_code)
    assert v3.passed is False
    assert "HALT_PHYSICAL_LAW_VIOLATION:DIMENSIONAL_MISMATCH:MinorUnitUSD_vs_EpochSeconds" in v3.status_code

    # Negative value below min bound on negative literal
    negative_torque_code = (
        "def reverse_actuator():\n"
        "    joint_torque: NewtonMeters = -15\n"
        "    return joint_torque\n"
    )
    v_neg = enforcer.verify_ast_physics(negative_torque_code)
    assert v_neg.passed is False
    assert "BOUNDS_EXCEEDED:NewtonMeters=-15" in v_neg.status_code

    # Negative value on re-assignment below min bound
    reassign_neg_code = (
        "def reverse_adjust():\n"
        "    torque: NewtonMeters = 50\n"
        "    torque = -20\n"
        "    return torque\n"
    )
    v_reassign_neg = enforcer.verify_ast_physics(reassign_neg_code)
    assert v_reassign_neg.passed is False
    assert "BOUNDS_EXCEEDED:NewtonMeters=-20" in v_reassign_neg.status_code

    # SyntaxError in AST inspection
    v_syn = enforcer.verify_ast_physics("def broken(:")
    assert v_syn.passed is False
    assert v_syn.status_code == "HALT_SYNTAX_ERROR"

    # 4. Valid Physical & Financial Type-State Code
    valid_physics_code = (
        "def nominal_operation():\n"
        "    applied_torque: NewtonMeters = 150\n"
        "    deposit: MinorUnitUSD = 5000\n"
        "    bonus: MinorUnitUSD = 1000\n"
        "    total_deposit = deposit + bonus\n"
        "    remaining = total_deposit - deposit\n"
        "    return applied_torque, total_deposit, remaining\n"
    )
    v4 = enforcer.verify_ast_physics(valid_physics_code)
    assert v4.passed is True
    assert v4.status_code == "OK_PHYSICAL_TYPESTATE_VERIFIED"
    assert v4.verdict_caid.startswith("sha256:")

    v4_dict = v4.to_dict()
    assert v4_dict["passed"] is True
    assert v4_dict["status_code"] == "OK_PHYSICAL_TYPESTATE_VERIFIED"

    with pytest.raises((AttributeError, TypeError)):
        v4.passed = False  # type: ignore

    # Validation errors on PhysicalEnvelopeSpec
    with pytest.raises(ValueError, match="unit_type"):
        PhysicalEnvelopeSpec("", 0, 10)
    with pytest.raises(ValueError, match="min_value and max_value must be integers"):
        PhysicalEnvelopeSpec("Unit", "0", 10)  # type: ignore
    with pytest.raises(ValueError, match="min_value and max_value must be integers"):
        PhysicalEnvelopeSpec("Unit", 0, "10")  # type: ignore
    with pytest.raises(ValueError, match="min_value cannot exceed max_value"):
        PhysicalEnvelopeSpec("Unit", 20, 10)

    # Validation error on empty envelopes
    with pytest.raises(ValueError, match="ERR_EMPTY_PHYSICAL_ENVELOPES"):
        PhysicalTypeStateEnforcer({})
