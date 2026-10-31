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
src/subexponential_concurrency_gate.py
================================================================================
Subexponential Formal Concurrency Gate & Deadlock-Free Lock Re-Ordering Engine.

Evaluated under the stated model:
  - Multi-Agent Resource Allocation Graph (RAG) Analysis
  - Deterministic Subexponential Cycle Detection (Tarjan SCC / Coffman Conditions)
  - Canonical Lexicographical Lock Re-Ordering
  - Zero-Float RFC 8785 JCS Canonicalization with SHA-256 CAID Digests

Core Invariants:
  1. Deadlock Elimination at $0 Token Cost:
     Detects potential circular wait conditions (Coffman condition 4) across
     multi-agent tool/file access intents before spawning worktrees.
  2. Canonical Topological Re-Ordering:
     Enforces a deterministic global ordering over requested resources so all
     agents acquire shared locks strictly in the same sequence, mathematically
     precluding deadlocks.
  3. Static AST Resource Extraction:
     Parses candidate source code or intent declarations to extract required
     database keys, file paths, and external handles.
"""

from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple

from src.jcs_canonicalizer import encode_jcs


def sha256_jcs_caid(payload: Any) -> str:
    """Computes deterministic SHA-256 CAID digest over RFC 8785 canonical bytes."""
    raw = payload if isinstance(payload, bytes) else encode_jcs(payload)
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


@dataclass(frozen=True)
class AgentResourcePlan:
    """Resource intent plan declared by a concurrent subagent."""

    agent_id: str
    task_id: str
    declared_resources: Tuple[str, ...]
    priority_bps: int

    def __post_init__(self) -> None:
        if not self.agent_id.strip():
            raise ValueError("ERR_EMPTY_AGENT_ID")
        if not self.task_id.strip():
            raise ValueError("ERR_EMPTY_TASK_ID")
        if not self.declared_resources:
            raise ValueError("ERR_EMPTY_DECLARED_RESOURCES")
        if any(not r.strip() for r in self.declared_resources):
            raise ValueError("ERR_INVALID_RESOURCE_NAME")
        if type(self.priority_bps) is not int or self.priority_bps < 0 or self.priority_bps > 10000:
            raise ValueError("ERR_INVALID_PRIORITY_BPS")


@dataclass(frozen=True)
class ConcurrencySafetyVerdict:
    """Deterministic verdict on multi-agent concurrency plan."""

    is_deadlock_free: bool
    status_code: str
    detected_cycles: Tuple[Tuple[str, ...], ...]
    reordered_schedules: Dict[str, Tuple[str, ...]]
    involved_agents_count: int
    verdict_caid: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "detected_cycles": [list(c) for c in self.detected_cycles],
            "involved_agents_count": self.involved_agents_count,
            "is_deadlock_free": self.is_deadlock_free,
            "reordered_schedules": {
                k: list(v) for k, v in sorted(self.reordered_schedules.items())
            },
            "status_code": self.status_code,
            "verdict_caid": self.verdict_caid,
        }


class _ResourceVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.resources: List[str] = []

    @staticmethod
    def _extract_first_arg_str(args: Sequence[ast.expr]) -> Optional[str]:
        if not args:
            return None
        first = args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            val = first.value.strip()
            return val if val else None
        return None

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id in ("open", "read_file", "lock_key"):
            val = self._extract_first_arg_str(node.args)
            if val is not None:
                self.resources.append(val)
        elif isinstance(node.func, ast.Attribute) and node.func.attr in ("write_text", "acquire_lock"):
            if isinstance(node.func.value, ast.Call):
                val = self._extract_first_arg_str(node.func.value.args)
                if val is not None:
                    self.resources.append(val)
        self.generic_visit(node)


class SubexponentialConcurrencyGate:
    """
    Evaluates multi-agent resource acquisition plans to eliminate deadlocks.
    Employs deterministic cycle detection and canonical lock sequencing.
    """

    @staticmethod
    def extract_resources_from_ast(source_code: str) -> Tuple[str, ...]:
        """
        Statically inspects source AST to identify targeted file paths,
        table names, or locked key constants in lexical source order.
        """
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return ()

        visitor = _ResourceVisitor()
        visitor.visit(tree)
        return tuple(dict.fromkeys(visitor.resources))

    @staticmethod
    def _init_tarjan_index() -> int:
        return 0

    @staticmethod
    def _tarjan_step(current_index: int) -> int:
        return current_index + 1

    @classmethod
    def detect_wait_for_cycles(
        cls,
        plans: Sequence[AgentResourcePlan],
    ) -> Tuple[Tuple[str, ...], ...]:
        """
        Builds a directed Wait-For Graph (WFG) from the sequence of locks each agent
        declares (assuming lock A held while requesting lock B).
        Detects circular dependencies via Tarjan's SCC.
        """
        # Graph nodes: resource keys
        edges: Dict[str, Set[str]] = {}
        for plan in plans:
            res_list = plan.declared_resources
            for i in range(len(res_list) - 1):
                src = res_list[i]
                dst = res_list[i + 1]
                if src != dst:
                    edges.setdefault(src, set()).add(dst)

        # Tarjan's Strongly Connected Components algorithm
        index = cls._init_tarjan_index()
        indices: Dict[str, int] = {}
        lowlinks: Dict[str, int] = {}
        on_stack: Set[str] = set()
        stack: List[str] = []
        sccs: List[Tuple[str, ...]] = []

        all_nodes = set(edges.keys())
        for dsts in edges.values():
            all_nodes.update(dsts)

        def strongconnect(v: str) -> None:
            nonlocal index
            indices[v] = index
            lowlinks[v] = index
            index = cls._tarjan_step(index)
            stack.append(v)
            on_stack.add(v)

            for w in sorted(edges.get(v, ())):
                if w not in indices:
                    strongconnect(w)
                    lowlinks[v] = min(lowlinks[v], lowlinks[w])
                elif w in on_stack:
                    lowlinks[v] = min(lowlinks[v], indices[w])

            if lowlinks[v] == indices[v]:
                scc: List[str] = []
                while True:
                    w = stack.pop()
                    on_stack.remove(w)
                    scc.append(w)
                    if w == v:
                        break
                if len(scc) > 1:
                    sccs.append(tuple(sorted(scc)))

        for node in sorted(all_nodes):
            if node not in indices:
                strongconnect(node)

        return tuple(sorted(sccs))

    @classmethod
    def evaluate_concurrency_safety(
        cls, plans: Sequence[AgentResourcePlan]
    ) -> ConcurrencySafetyVerdict:
        """
        Adjudicates multi-agent resource plans:
        1. Identifies if the declared order contains circular wait cycles.
        2. Computes the canonical deadlock-free acquisition schedule for each agent.
        """
        if not plans:
            raise ValueError("ERR_EMPTY_PLANS")

        # 1. Detect cycles in raw declared order
        cycles = cls.detect_wait_for_cycles(plans)

        # 2. Compute canonical lexicographical schedule for every agent
        # (Enforces global linear order: Havender's hierarchical allocation)
        reordered: Dict[str, Tuple[str, ...]] = {}
        for plan in plans:
            # Deterministic sorted unique resource sequence
            canonical_seq = tuple(sorted(set(plan.declared_resources)))
            reordered[plan.agent_id] = canonical_seq

        is_free = len(cycles) == 0
        status = "OK_DEADLOCK_FREE_CONCURRENCY" if is_free else "HALT_CIRCULAR_WAIT_DETECTED_REORDER_REQUIRED"

        payload = {
            "detected_cycles": [list(c) for c in cycles],
            "involved_agents_count": len(plans),
            "is_deadlock_free": is_free,
            "reordered_schedules": {k: list(v) for k, v in sorted(reordered.items())},
            "status_code": status,
        }
        verdict_caid = sha256_jcs_caid(payload)

        return ConcurrencySafetyVerdict(
            is_deadlock_free=is_free,
            status_code=status,
            detected_cycles=cycles,
            reordered_schedules=reordered,
            involved_agents_count=len(plans),
            verdict_caid=verdict_caid,
        )
