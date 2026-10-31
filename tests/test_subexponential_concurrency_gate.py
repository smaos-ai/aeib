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
tests/test_subexponential_concurrency_gate.py
================================================================================
Verification Suite for `src/subexponential_concurrency_gate.py`.
Evaluates:
1. Deadlock-free linear lock acquisition across concurrent subagents.
2. Circular wait detection across 2-agent and 3-agent dependency cycles.
3. Canonical lexicographical schedule re-ordering.
4. Static AST resource extraction.
5. Dataclass immutability and serialization.
"""

from __future__ import annotations

import pytest

from src.subexponential_concurrency_gate import (
    AgentResourcePlan,
    ConcurrencySafetyVerdict,
    SubexponentialConcurrencyGate,
)


def test_1_nominal_deadlock_free_concurrency() -> None:
    plans = [
        AgentResourcePlan(
            agent_id="agent_alpha",
            task_id="task_1",
            declared_resources=("db_accounts", "db_transactions"),
            priority_bps=8000,
        ),
        AgentResourcePlan(
            agent_id="agent_beta",
            task_id="task_2",
            declared_resources=("db_accounts", "db_audit_log"),
            priority_bps=7000,
        ),
    ]

    verdict = SubexponentialConcurrencyGate.evaluate_concurrency_safety(plans)
    assert verdict.is_deadlock_free is True
    assert verdict.status_code == "OK_DEADLOCK_FREE_CONCURRENCY"
    assert len(verdict.detected_cycles) == 0
    assert verdict.involved_agents_count == 2
    assert verdict.verdict_caid.startswith("sha256:")

    # Re-ordered schedules are lexicographically canonical
    assert verdict.reordered_schedules["agent_alpha"] == ("db_accounts", "db_transactions")
    assert verdict.reordered_schedules["agent_beta"] == ("db_accounts", "db_audit_log")


def test_2_two_agent_circular_wait_detection() -> None:
    # Classic deadlock: Agent 1 acquires A then B; Agent 2 acquires B then A
    plans = [
        AgentResourcePlan(
            agent_id="agent_1",
            task_id="t1",
            declared_resources=("resource_A", "resource_B"),
            priority_bps=5000,
        ),
        AgentResourcePlan(
            agent_id="agent_2",
            task_id="t2",
            declared_resources=("resource_B", "resource_A"),
            priority_bps=5000,
        ),
    ]

    verdict = SubexponentialConcurrencyGate.evaluate_concurrency_safety(plans)
    assert verdict.is_deadlock_free is False
    assert verdict.status_code == "HALT_CIRCULAR_WAIT_DETECTED_REORDER_REQUIRED"
    assert len(verdict.detected_cycles) == 1
    assert verdict.detected_cycles[0] == ("resource_A", "resource_B")

    # Canonical re-ordering resolves the cycle by enforcing alphabetical lock order
    assert verdict.reordered_schedules["agent_1"] == ("resource_A", "resource_B")
    assert verdict.reordered_schedules["agent_2"] == ("resource_A", "resource_B")


def test_3_three_agent_circular_wait_detection() -> None:
    # 3-Node cycle: A -> B, B -> C, C -> A
    plans = [
        AgentResourcePlan(
            agent_id="agent_x",
            task_id="tx",
            declared_resources=("res_alpha", "res_beta"),
            priority_bps=9000,
        ),
        AgentResourcePlan(
            agent_id="agent_y",
            task_id="ty",
            declared_resources=("res_beta", "res_gamma"),
            priority_bps=8500,
        ),
        AgentResourcePlan(
            agent_id="agent_z",
            task_id="tz",
            declared_resources=("res_gamma", "res_alpha"),
            priority_bps=8000,
        ),
    ]

    verdict = SubexponentialConcurrencyGate.evaluate_concurrency_safety(plans)
    assert verdict.is_deadlock_free is False
    assert len(verdict.detected_cycles) == 1
    assert verdict.detected_cycles[0] == ("res_alpha", "res_beta", "res_gamma")


def test_4_static_ast_resource_extraction() -> None:
    code = (
        "import os\n"
        "from pathlib import Path\n"
        "def work():\n"
        "    with open('data/config.json', 'r') as f: data = f.read()\n"
        "    read_file('single.txt')\n"
        "    lock_key()\n"  # 0 args
        "    open(42)\n"  # non-string
        "    open('')\n"  # empty string
        "    Path('logs/audit.log').write_text('done')\n"
        "    Path().write_text('no_path')\n"
        "    Path(99).write_text('num_path')\n"
        "    Path('data/config.json').write_text('updated')\n"
    )

    resources = SubexponentialConcurrencyGate.extract_resources_from_ast(code)
    assert resources == ("data/config.json", "single.txt", "logs/audit.log")

    # Direct test on _ResourceVisitor
    from src.subexponential_concurrency_gate import _ResourceVisitor
    assert _ResourceVisitor._extract_first_arg_str([]) is None

    # Syntax error returns empty tuple
    bad_code = "def broken(:"
    assert SubexponentialConcurrencyGate.extract_resources_from_ast(bad_code) == ()


def test_6_linear_three_resource_plan_and_self_loops() -> None:
    # 3-step linear acquisition: res_1 -> res_2 -> res_3
    # Also includes self-repeating resource ("res_1", "res_1")
    plans = [
        AgentResourcePlan(
            agent_id="agent_linear",
            task_id="t_lin",
            declared_resources=("res_1", "res_1", "res_2", "res_3"),
            priority_bps=5000,
        ),
        AgentResourcePlan(
            agent_id="agent_linear_2",
            task_id="t_lin_2",
            declared_resources=("res_2", "res_3"),
            priority_bps=4000,
        ),
    ]
    verdict = SubexponentialConcurrencyGate.evaluate_concurrency_safety(plans)
    assert verdict.is_deadlock_free is True
    assert verdict.reordered_schedules["agent_linear"] == ("res_1", "res_2", "res_3")

    # Cycle with multi-element resource list: A -> B -> C and C -> A
    # Asserts that the cycle contains all three nodes, killing reverse arithmetic mutants
    plans_cycle = [
        AgentResourcePlan(
            agent_id="a1",
            task_id="t1",
            declared_resources=("A", "B", "C"),
            priority_bps=0,  # Boundary test: 0 bps
        ),
        AgentResourcePlan(
            agent_id="a2",
            task_id="t2",
            declared_resources=("C", "A"),
            priority_bps=10000,  # Boundary test: 10000 bps
        ),
    ]
    verdict_cycle = SubexponentialConcurrencyGate.evaluate_concurrency_safety(plans_cycle)
    assert verdict_cycle.is_deadlock_free is False
    assert len(verdict_cycle.detected_cycles) == 1
    assert verdict_cycle.detected_cycles[0] == ("A", "B", "C")

    # Test Tarjan index helpers directly
    assert SubexponentialConcurrencyGate._init_tarjan_index() == 0
    assert SubexponentialConcurrencyGate._tarjan_step(0) == 1
    assert SubexponentialConcurrencyGate._tarjan_step(5) == 6


def test_5_input_validation_and_dataclass_methods() -> None:
    # 1. Empty plans
    with pytest.raises(ValueError, match="ERR_EMPTY_PLANS"):
        SubexponentialConcurrencyGate.evaluate_concurrency_safety([])

    # 2. Invalid AgentResourcePlan fields
    with pytest.raises(ValueError, match="ERR_EMPTY_AGENT_ID"):
        AgentResourcePlan(agent_id="", task_id="t", declared_resources=("k",), priority_bps=100)

    with pytest.raises(ValueError, match="ERR_EMPTY_TASK_ID"):
        AgentResourcePlan(agent_id="a", task_id=" ", declared_resources=("k",), priority_bps=100)

    with pytest.raises(ValueError, match="ERR_EMPTY_DECLARED_RESOURCES"):
        AgentResourcePlan(agent_id="a", task_id="t", declared_resources=(), priority_bps=100)

    with pytest.raises(ValueError, match="ERR_INVALID_RESOURCE_NAME"):
        AgentResourcePlan(agent_id="a", task_id="t", declared_resources=(" ",), priority_bps=100)

    with pytest.raises(ValueError, match="ERR_INVALID_PRIORITY_BPS"):
        AgentResourcePlan(agent_id="a", task_id="t", declared_resources=("k",), priority_bps=-1)

    with pytest.raises(ValueError, match="ERR_INVALID_PRIORITY_BPS"):
        AgentResourcePlan(agent_id="a", task_id="t", declared_resources=("k",), priority_bps=10001)

    # 3. Immutability & to_dict
    plan = AgentResourcePlan(agent_id="a", task_id="t", declared_resources=("k",), priority_bps=5000)
    with pytest.raises(Exception):
        plan.priority_bps = 6000  # type: ignore

    verdict = ConcurrencySafetyVerdict(
        is_deadlock_free=True,
        status_code="OK",
        detected_cycles=(),
        reordered_schedules={"a": ("k",)},
        involved_agents_count=1,
        verdict_caid="sha256:123",
    )
    vd = verdict.to_dict()
    assert vd["is_deadlock_free"] is True
    assert vd["involved_agents_count"] == 1
    assert vd["reordered_schedules"]["a"] == ["k"]

    with pytest.raises(Exception):
        verdict.is_deadlock_free = False  # type: ignore
