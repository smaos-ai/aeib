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
src/zero_allocation_admission.py
================================================================================
AEIB Zero-Allocation Admission Hook (Gap 5: TA-14 SCGA Admissible Computation).
Evaluated under the stated model. Preserves strict epistemic lock.

Objective:
  Evaluates caller identity, standing, and target allowlists in O(1) time
  BEFORE allocating memory or committing CPU cycles to RFC 8785 JCS canonicalization
  or Ed25519 asymmetric cryptography.

Mitigates:
  CPU and memory exhaustion denial-of-service from unauthenticated flood traffic.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Optional, Set


DEFAULT_BENCHMARK_ITERATIONS: int = 10000
DEFAULT_UNAUTHORIZED_HEADER: Dict[str, Any] = {
    "agent_id": "malicious-bot-flood",
    "tool_name": "arbitrary_eval",
    "target_host": "attacker.xyz",
    "policy_epoch": 999,
    "authority_id": "revoked-grant",
}


@dataclass(frozen=True)
class AdmissionVerdict:
    admitted: bool
    rejection_code: Optional[str]
    latency_ns: int
    eval_epoch: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "admitted": self.admitted,
            "eval_epoch": self.eval_epoch,
            "latency_ns": self.latency_ns,
            "rejection_code": self.rejection_code,
        }


class ZeroAllocationAdmissionHook:
    """
    High-performance pre-JCS admission gate operating on in-memory sets and bitmasks.
    """

    def __init__(
        self,
        allowed_agents: FrozenSet[str],
        allowed_tools: FrozenSet[str],
        allowed_hosts: FrozenSet[str],
        active_policy_epoch: int,
        revoked_authorities: Optional[Set[str]] = None,
    ):
        self.allowed_agents: FrozenSet[str] = frozenset(allowed_agents)
        self.allowed_tools: FrozenSet[str] = frozenset(allowed_tools)
        self.allowed_hosts: FrozenSet[str] = frozenset(allowed_hosts)
        self.active_policy_epoch: int = active_policy_epoch
        self.revoked_authorities: Set[str] = set(revoked_authorities or ())

    def evaluate_admissibility(self, candidate_headers: Dict[str, Any]) -> AdmissionVerdict:
        """
        Evaluates admissibility in microseconds using fast set lookups and integer comparisons.
        Zero serialization or cryptographic operations are committed to non-admissible requests.
        """
        t0 = time.perf_counter_ns()

        # 1. Agent Registration Check
        agent_id = candidate_headers.get("agent_id")
        if not agent_id or agent_id not in self.allowed_agents:
            t1 = time.perf_counter_ns()
            return AdmissionVerdict(
                admitted=False,
                rejection_code="UNREGISTERED_AGENT",
                latency_ns=t1 - t0,
                eval_epoch=self.active_policy_epoch,
            )

        # 2. Tool Capability Allowlist Check
        tool_name = candidate_headers.get("tool_name")
        if not tool_name or tool_name not in self.allowed_tools:
            t1 = time.perf_counter_ns()
            return AdmissionVerdict(
                admitted=False,
                rejection_code="UNALLOWLISTED_TOOL",
                latency_ns=t1 - t0,
                eval_epoch=self.active_policy_epoch,
            )

        # 3. Target Host / Audience Check
        target_host = candidate_headers.get("target_host")
        if not target_host or target_host not in self.allowed_hosts:
            t1 = time.perf_counter_ns()
            return AdmissionVerdict(
                admitted=False,
                rejection_code="HOST_AUDIENCE_MISMATCH",
                latency_ns=t1 - t0,
                eval_epoch=self.active_policy_epoch,
            )

        # 4. Policy Epoch Monotonicity Check
        policy_epoch = candidate_headers.get("policy_epoch")
        if policy_epoch != self.active_policy_epoch:
            t1 = time.perf_counter_ns()
            return AdmissionVerdict(
                admitted=False,
                rejection_code="STALE_OR_SPOOFED_EPOCH",
                latency_ns=t1 - t0,
                eval_epoch=self.active_policy_epoch,
            )

        # 5. Revocation List Check
        authority_id = candidate_headers.get("authority_id")
        if authority_id and authority_id in self.revoked_authorities:
            t1 = time.perf_counter_ns()
            return AdmissionVerdict(
                admitted=False,
                rejection_code="AUTHORITY_REVOKED",
                latency_ns=t1 - t0,
                eval_epoch=self.active_policy_epoch,
            )

        t1 = time.perf_counter_ns()
        return AdmissionVerdict(
            admitted=True,
            rejection_code=None,
            latency_ns=t1 - t0,
            eval_epoch=self.active_policy_epoch,
        )

    def benchmark_rejection_throughput(self, iterations: int = DEFAULT_BENCHMARK_ITERATIONS) -> Dict[str, float]:
        """
        Measures the rejection evaluation overhead over a flood of unauthorized requests.
        """
        unauthorized_header = DEFAULT_UNAUTHORIZED_HEADER

        latencies_ns = []
        for _ in range(iterations):
            verdict = self.evaluate_admissibility(unauthorized_header)
            latencies_ns.append(verdict.latency_ns)

        mean_latency_ns = sum(latencies_ns) / len(latencies_ns)
        mean_latency_us = mean_latency_ns / 1000.0

        return {
            "iterations": float(iterations),
            "mean_latency_ns": mean_latency_ns,
            "mean_latency_us": mean_latency_us,
            "ops_per_second": 1_000_000_000.0 / max(1.0, mean_latency_ns),
        }
