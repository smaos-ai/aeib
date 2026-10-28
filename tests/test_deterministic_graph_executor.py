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
tests/test_deterministic_graph_executor.py
================================================================================
Verification & Falsification Suite for DeterministicGraphExecutor.
"""

from __future__ import annotations

import dataclasses
import pytest

from src.deterministic_graph_executor import (
    DeterministicGraphExecutor,
    GraphNode,
)


def test_default_ci_edges_resolve_deterministically() -> None:
    executor = DeterministicGraphExecutor()
    assert executor.edge_count() == 4

    # lint_pass -> run_unit_tests
    step1 = executor.resolve_next_step("lint_pass", "SUCCESS")
    assert step1 == "run_unit_tests"

    # unit_tests_pass -> run_integration_tests
    step2 = executor.resolve_next_step("unit_tests_pass", "SUCCESS")
    assert step2 == "run_integration_tests"

    # integration_tests_pass -> build_docker_image
    step3 = executor.resolve_next_step("integration_tests_pass", "SUCCESS")
    assert step3 == "build_docker_image"

    # build_docker_image_pass -> deploy_to_staging
    step4 = executor.resolve_next_step("build_docker_image_pass", "SUCCESS")
    assert step4 == "deploy_to_staging"


def test_failed_precondition_halts_and_escalates() -> None:
    executor = DeterministicGraphExecutor()
    halt_step = executor.resolve_next_step("lint_pass", "FAILED")
    assert halt_step == "HALT_AND_ESCALATE"

    halt_step_err = executor.resolve_next_step("unit_tests_pass", "ERROR")
    assert halt_step_err == "HALT_AND_ESCALATE"


def test_forced_llm_flag_bypasses_graph() -> None:
    executor = DeterministicGraphExecutor()
    # When is_llm_required is True, graph returns None regardless of edge presence
    res = executor.resolve_next_step("lint_pass", "SUCCESS", is_llm_required=True)
    assert res is None


def test_unmapped_action_falls_back_to_none() -> None:
    executor = DeterministicGraphExecutor()
    res = executor.resolve_next_step("unknown_novel_task", "SUCCESS")
    assert res is None


def test_custom_edge_addition() -> None:
    executor = DeterministicGraphExecutor()
    executor.add_edge("custom_compile", "custom_verify", expected_precondition="PASS")
    assert executor.edge_count() == 5

    res = executor.resolve_next_step("custom_compile", "PASS")
    assert res == "custom_verify"

    halt = executor.resolve_next_step("custom_compile", "FAIL")
    assert halt == "HALT_AND_ESCALATE"


def test_graph_node_frozen_immutability() -> None:
    node = GraphNode(
        action_name="act",
        expected_precondition="SUCCESS",
        next_deterministic_action="next_act",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        node.action_name = "mutated"  # type: ignore
