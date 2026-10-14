#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
#
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
v1.1-roadmap/configurable_reconciliation_engine.py
================================================================================
AEIB Policy-Bound Target Reconciliation Engine (Milestone 4 Prototype).

Evaluates target-specific reconciliation policies replacing static single-probe
limits with bounded, configurable parameters:
  - max_attempts: Bounded integer (default: 3, hard system ceiling: 5)
  - max_concurrent_probes: Fenced single-flight concurrency
  - deadline_ms: Bounded execution window
  - backoff_strategy: exponential_jitter | linear | constant
  - circuit_breaker: Automatic quarantine on repeated downstream outages
  - on_deadline_exceeded: Fails closed to PRESERVE_UNCERTAINTY (never blind retry)
"""

import time
import math
import random
import threading
from dataclasses import dataclass, field
from fnmatch import fnmatch
from typing import Dict, Any, Optional, Tuple, Callable, List

# Core Epistemic Dispositions
DISPOSITION_CONFIRMED = "CONFIRMED"
DISPOSITION_REFUTED = "REFUTED"
DISPOSITION_EFFECT_INDETERMINATE = "EFFECT_INDETERMINATE"
DISPOSITION_PRESERVED_UNCERTAINTY = "PRESERVED_UNCERTAINTY"
DISPOSITION_CIRCUIT_TRIPPED = "CIRCUIT_TRIPPED"


@dataclass(frozen=True)
class TargetReconciliationPolicy:
    """
    Operator-configured reconciliation policy bound to a target URI pattern.
    """
    target_pattern: str
    max_attempts: int = 3
    max_concurrent_probes: int = 1
    deadline_ms: int = 2500
    initial_backoff_ms: int = 100
    backoff_strategy: str = "exponential_jitter"  # exponential_jitter | linear | constant
    max_backoff_ms: int = 1000
    circuit_breaker_threshold: int = 5
    circuit_quarantine_seconds: float = 60.0
    evidence_required: str = "RFC8785_JCS_STATUS_PROOF"

    def __post_init__(self):
        # Enforce hard system safety invariants under the stated model
        if self.max_attempts < 1 or self.max_attempts > 5:
            raise ValueError(f"INVALID_POLICY: max_attempts must be in range [1, 5], got {self.max_attempts}")
        if self.max_concurrent_probes != 1:
            raise ValueError(f"CONCURRENCY_VIOLATION: max_concurrent_probes must be 1 to prevent probe storms.")
        if self.deadline_ms < 50 or self.deadline_ms > 30000:
            raise ValueError(f"INVALID_DEADLINE: deadline_ms must be in range [50, 30000], got {self.deadline_ms}")


@dataclass
class CircuitBreakerState:
    consecutive_outages: int = 0
    quarantined_until: float = 0.0
    tripped: bool = False


@dataclass
class ReconciliationExecutionResult:
    action_id: str
    operation_id: str
    disposition: str
    retry_safe: bool
    reconciliation_attempts: int
    elapsed_ms: float
    downstream_commit_count: int
    diagnostic: str
    evidence_payload: Optional[Dict[str, Any]] = None


class ConfigurableReconciliationEngine:
    """
    Executes policy-bound reconciliation loops against target endpoints.
    Enforces concurrency fencing, backoff jitter, deadlines, and circuit tripping.
    """
    def __init__(self, policies: Optional[List[TargetReconciliationPolicy]] = None):
        self.policies = policies or [
            TargetReconciliationPolicy(target_pattern="https://api.bank.internal/v1/*")
        ]
        self._circuit_breakers: Dict[str, CircuitBreakerState] = {}
        self._inflight_locks: Dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()

    def _get_matching_policy(self, target_uri: str) -> TargetReconciliationPolicy:
        for p in self.policies:
            if fnmatch(target_uri, p.target_pattern):
                return p
        # Default fallback policy with safe bounds
        return TargetReconciliationPolicy(target_pattern="*")

    def _get_inflight_lock(self, operation_id: str) -> threading.Lock:
        with self._global_lock:
            if operation_id not in self._inflight_locks:
                self._inflight_locks[operation_id] = threading.Lock()
            return self._inflight_locks[operation_id]

    def _calculate_backoff_seconds(self, policy: TargetReconciliationPolicy, attempt: int) -> float:
        base_ms = policy.initial_backoff_ms
        if policy.backoff_strategy == "exponential_jitter":
            factor = 2 ** (attempt - 1)
            raw_ms = min(base_ms * factor, policy.max_backoff_ms)
            jitter_ms = random.uniform(0.5 * raw_ms, raw_ms)
            return jitter_ms / 1000.0
        elif policy.backoff_strategy == "linear":
            raw_ms = min(base_ms * attempt, policy.max_backoff_ms)
            return raw_ms / 1000.0
        else:
            return base_ms / 1000.0

    def reconcile_target(
        self,
        *,
        action_id: str,
        operation_id: str,
        idempotency_key: str,
        target_uri: str,
        probe_fn: Callable[[str, str], Tuple[int, Dict[str, Any]]],
        sleep_fn: Callable[[float], None] = time.sleep
    ) -> ReconciliationExecutionResult:
        """
        Executes bounded reconciliation loop according to policy for target_uri.
        """
        policy = self._get_matching_policy(target_uri)
        op_lock = self._get_inflight_lock(operation_id)

        # Enforce single-flight concurrency: if probe for this operation_id is already running, wait
        acquired = op_lock.acquire(blocking=True, timeout=policy.deadline_ms / 1000.0)
        if not acquired:
            return ReconciliationExecutionResult(
                action_id=action_id,
                operation_id=operation_id,
                disposition=DISPOSITION_PRESERVED_UNCERTAINTY,
                retry_safe=False,
                reconciliation_attempts=0,
                elapsed_ms=0.0,
                downstream_commit_count=0,
                diagnostic="CONCURRENCY_DEADLINE_EXCEEDED: Could not acquire probe single-flight lock."
            )

        try:
            # Check Circuit Breaker
            now = time.time()
            cb = self._circuit_breakers.setdefault(policy.target_pattern, CircuitBreakerState())
            if cb.tripped:
                if now < cb.quarantined_until:
                    return ReconciliationExecutionResult(
                        action_id=action_id,
                        operation_id=operation_id,
                        disposition=DISPOSITION_CIRCUIT_TRIPPED,
                        retry_safe=False,
                        reconciliation_attempts=0,
                        elapsed_ms=0.0,
                        downstream_commit_count=0,
                        diagnostic=f"CIRCUIT_BREAKER_ACTIVE: Target quarantined until {cb.quarantined_until}"
                    )
                else:
                    # Half-open state
                    cb.tripped = False
                    cb.consecutive_outages = 0

            start_time = time.time()
            deadline_seconds = policy.deadline_ms / 1000.0
            attempts_made = 0

            while attempts_made < policy.max_attempts:
                elapsed = time.time() - start_time
                if elapsed >= deadline_seconds:
                    break

                attempts_made += 1
                try:
                    status_code, probe_data = probe_fn(operation_id, idempotency_key)
                except Exception as exc:
                    status_code, probe_data = 503, {"error": str(exc), "status": "CLIENT_EXCEPTION"}

                # Evaluate response disposition
                if status_code == 200 and probe_data.get("status") == "COMMITTED":
                    cb.consecutive_outages = 0
                    return ReconciliationExecutionResult(
                        action_id=action_id,
                        operation_id=operation_id,
                        disposition=DISPOSITION_CONFIRMED,
                        retry_safe=False,  # Already committed -> never retry
                        reconciliation_attempts=attempts_made,
                        elapsed_ms=(time.time() - start_time) * 1000.0,
                        downstream_commit_count=probe_data.get("commit_count", 1),
                        diagnostic="COMMITTED: Primary status endpoint verified transaction execution.",
                        evidence_payload=probe_data
                    )

                elif status_code == 404:
                    cb.consecutive_outages = 0
                    return ReconciliationExecutionResult(
                        action_id=action_id,
                        operation_id=operation_id,
                        disposition=DISPOSITION_REFUTED,
                        retry_safe=True,  # Confirmed absent -> safe to retry or abandon
                        reconciliation_attempts=attempts_made,
                        elapsed_ms=(time.time() - start_time) * 1000.0,
                        downstream_commit_count=0,
                        diagnostic="REFUTED: Primary status endpoint confirms transaction was not committed.",
                        evidence_payload=probe_data
                    )

                elif status_code == 409 or probe_data.get("status") == "CONFLICT":
                    cb.consecutive_outages = 0
                    return ReconciliationExecutionResult(
                        action_id=action_id,
                        operation_id=operation_id,
                        disposition="RECONCILIATION_CONFLICT",
                        retry_safe=False,
                        reconciliation_attempts=attempts_made,
                        elapsed_ms=(time.time() - start_time) * 1000.0,
                        downstream_commit_count=probe_data.get("commit_count", 0),
                        diagnostic="CONFLICT: Target detected idempotency key or parameter mismatch.",
                        evidence_payload=probe_data
                    )

                # Transient failure (503 / 504 / timeout during probe) -> execute backoff if attempts remain
                if attempts_made < policy.max_attempts:
                    backoff = self._calculate_backoff_seconds(policy, attempts_made)
                    # Don't sleep past deadline
                    remaining = deadline_seconds - (time.time() - start_time)
                    if remaining <= 0:
                        break
                    sleep_duration = min(backoff, remaining)
                    sleep_fn(sleep_duration)

            # All attempts or deadline exhausted without definitive resolution
            cb.consecutive_outages += 1
            if cb.consecutive_outages >= policy.circuit_breaker_threshold:
                cb.tripped = True
                cb.quarantined_until = time.time() + policy.circuit_quarantine_seconds

            return ReconciliationExecutionResult(
                action_id=action_id,
                operation_id=operation_id,
                disposition=DISPOSITION_PRESERVED_UNCERTAINTY,
                retry_safe=False,
                reconciliation_attempts=attempts_made,
                elapsed_ms=(time.time() - start_time) * 1000.0,
                downstream_commit_count=0,
                diagnostic=f"PRESERVED_UNCERTAINTY: Exhausted {attempts_made} attempts without definitive status. Escalating to human authority."
            )

        finally:
            op_lock.release()
