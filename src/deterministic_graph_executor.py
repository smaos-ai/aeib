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
src/deterministic_graph_executor.py
================================================================================
Deterministic Graph Executor (Scaffold).

Evaluated under the stated model (scaffold):
Bypasses LLM inference for known, deterministic state transitions to eliminate
token expenditure and prevent out-of-scope intent drift.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class GraphNode:
    """Represents a deterministic state transition node in the execution graph."""

    action_name: str
    expected_precondition: str
    next_deterministic_action: Optional[str]


class DeterministicGraphExecutor:
    """
    Evaluates state transitions against an in-memory deterministic graph.
    Routes deterministic workflows at O(1) complexity and 0 LLM token cost.
    """

    def __init__(self) -> None:
        self._graph: Dict[str, GraphNode] = {}
        self._register_default_edges()

    def _register_default_edges(self) -> None:
        self.add_edge("lint_pass", "run_unit_tests")
        self.add_edge("unit_tests_pass", "run_integration_tests")
        self.add_edge("integration_tests_pass", "build_docker_image")
        self.add_edge("build_docker_image_pass", "deploy_to_staging")

    def add_edge(
        self,
        current_action: str,
        next_action: str,
        expected_precondition: str = "SUCCESS",
    ) -> None:
        """Registers a deterministic transition edge in the graph."""
        self._graph[current_action] = GraphNode(
            action_name=current_action,
            expected_precondition=expected_precondition,
            next_deterministic_action=next_action,
        )

    def edge_count(self) -> int:
        return len(self._graph)

    def resolve_next_step(
        self,
        last_action: str,
        action_result: str,
        is_llm_required: bool = False,
    ) -> Optional[str]:
        """
        Resolves the next action in the execution sequence:
        - If is_llm_required is True: returns None (forces LLM fallback).
        - If action_result does not match expected_precondition: returns 'HALT_AND_ESCALATE'.
        - If a deterministic edge is matched: returns next action name.
        - If unmapped: returns None (fallback to MoM Router).
        """
        if is_llm_required:
            return

        node = self._graph.get(last_action)
        if node is None:
            return

        if action_result != node.expected_precondition:
            return "HALT_AND_ESCALATE"

        return node.next_deterministic_action
