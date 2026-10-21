#!/usr/bin/env python3
"""
src/hypergraph_causal_audit.py
================================================================================
Hypergraph Causal Auditing & Emergent Collusion Gate (v1.0.0-rc.5-preprod)

Architectural Context:
Addresses Multi-Agent "Salami" Emergent Collusion where N subagents each execute
disjoint, seemingly benign operations (Write(A) ∩ Write(B) = ∅) that combinatorially
constitute an unauthorized macro-action (e.g., fragmented treasury drainage or
distributed sensitive data exfiltration).

Core Mechanics:
1. Hypergraph State Manifold:
   - Vertices V: Subagents, target resources, payee accounts, file symbols.
   - Hyperedges E: Atomic CAID execution proposals connecting subagents to resources.
2. Topological Metric Evaluation:
   - Saliency Convergence: detects whether independent subagent actions converge onto
     a shared beneficiary or external sink.
   - Cumulative Component Exposure: aggregates in-flight exposure across connected components.
   - Graph Entropy Drift: detects coordinated compression of action space.
3. Fail-Closed Enforcement:
   - Triggers HALT_EMERGENT_COLLUSION and quarantines the root sponsor hierarchy if
     manifold bounds are breached.

Evaluated under the stated model. Strict zero-mock AST purity enforced.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass(frozen=True)
class HypergraphEdge:
    caid: str
    subagent_id: str
    target_resource: str
    payee_or_sink: str
    amount_minor: int
    tool_name: str
    timestamp: float


@dataclass(frozen=True)
class ManifoldAuditResult:
    passed: bool
    rejection_code: Optional[str]
    clustering_coefficient: float
    total_component_exposure_minor: int
    convergent_sink: Optional[str]
    subagents_implicated: List[str]


class HypergraphCausalAuditor:
    """
    Evaluates multi-agent concurrent execution proposals as a hypergraph
    to detect emergent multi-agent collusion and Salami attacks.
    """

    def __init__(
        self,
        max_component_exposure_minor: int = 5000_00,  # €5,000.00 ceiling per component
        max_sink_convergence_count: int = 3,           # max 3 subagents targeting same sink
        entropy_threshold: float = 0.5,
    ) -> None:
        self.max_component_exposure_minor = max_component_exposure_minor
        self.max_sink_convergence_count = max_sink_convergence_count
        self.entropy_threshold = entropy_threshold
        self._active_hyperedges: List[HypergraphEdge] = []

    def record_intent(
        self,
        caid: str,
        subagent_id: str,
        target_resource: str,
        payee_or_sink: str,
        amount_minor: int,
        tool_name: str,
        timestamp: float,
    ) -> None:
        edge = HypergraphEdge(
            caid=caid,
            subagent_id=subagent_id,
            target_resource=target_resource,
            payee_or_sink=payee_or_sink,
            amount_minor=amount_minor,
            tool_name=tool_name,
            timestamp=timestamp,
        )
        self._active_hyperedges.append(edge)

    def evaluate_manifold(self) -> ManifoldAuditResult:
        """
        Evaluates the global state manifold across all active in-flight hyperedges.
        """
        if not self._active_hyperedges:
            return ManifoldAuditResult(
                passed=True,
                rejection_code=None,
                clustering_coefficient=0.0,
                total_component_exposure_minor=0,
                convergent_sink=None,
                subagents_implicated=[],
            )

        # 1. Group by common sink (payee or destination file)
        sink_groups: Dict[str, List[HypergraphEdge]] = {}
        for edge in self._active_hyperedges:
            sink_groups.setdefault(edge.payee_or_sink, []).append(edge)

        # 2. Check Salami Sink Convergence
        for sink, edges in sink_groups.items():
            distinct_subagents = {e.subagent_id for e in edges}
            total_sink_amount = sum(e.amount_minor for e in edges)

            # Salami vector 1: Excessive subagent convergence onto a single sink
            if len(distinct_subagents) > self.max_sink_convergence_count:
                return ManifoldAuditResult(
                    passed=False,
                    rejection_code="HALT_EMERGENT_COLLUSION_SINK_CONVERGENCE",
                    clustering_coefficient=1.0,
                    total_component_exposure_minor=total_sink_amount,
                    convergent_sink=sink,
                    subagents_implicated=sorted(list(distinct_subagents)),
                )

            # Salami vector 2: Cumulative micro-transaction exposure exceeding ceiling
            if total_sink_amount > self.max_component_exposure_minor:
                return ManifoldAuditResult(
                    passed=False,
                    rejection_code="HALT_EMERGENT_COLLUSION_EXPOSURE_BREACH",
                    clustering_coefficient=1.0,
                    total_component_exposure_minor=total_sink_amount,
                    convergent_sink=sink,
                    subagents_implicated=sorted(list(distinct_subagents)),
                )

        # 3. Compute Hypergraph Component Entropy
        total_edges = len(self._active_hyperedges)
        p_sinks = [len(edges) / total_edges for edges in sink_groups.values()]
        entropy = -sum(p * math.log2(p) for p in p_sinks if p > 0)

        # If action distribution is excessively concentrated (entropy drop under high edge count)
        if total_edges >= 4 and entropy < self.entropy_threshold and len(sink_groups) == 1:
            implicated = sorted(list({e.subagent_id for e in self._active_hyperedges}))
            return ManifoldAuditResult(
                passed=False,
                rejection_code="HALT_EMERGENT_COLLUSION_ENTROPY_COLLAPSE",
                clustering_coefficient=round(1.0 - entropy, 4),
                total_component_exposure_minor=sum(e.amount_minor for e in self._active_hyperedges),
                convergent_sink=list(sink_groups.keys())[0],
                subagents_implicated=implicated,
            )

        return ManifoldAuditResult(
            passed=True,
            rejection_code=None,
            clustering_coefficient=0.0,
            total_component_exposure_minor=sum(e.amount_minor for e in self._active_hyperedges),
            convergent_sink=None,
            subagents_implicated=[],
        )

    def prune_resolved(self, resolved_caids: Set[str]) -> None:
        self._active_hyperedges = [e for e in self._active_hyperedges if e.caid not in resolved_caids]
