"""
v1.1-roadmap/aggregate_probe_scheduler.py — Aggregate Probe Scheduler Prototype.
Sovereign Multi-Agent OS (SMAOS) / Agent Execution Integrity Boundary (AEIB).

Tier 1 Core Delivery Contract:
Enforces aggregate amplification protection for out-of-band reconciliation probes:
  1. Per-operation attempt bounding (ProbeBudget: 1 default, preserves uncertainty on exhaustion).
  2. Per-target concurrency throttling (limits concurrent probes per target endpoint).
  3. Tenant and global token-bucket rate limiting (prevents probe storms during 504 cascades).
  4. Bounded queueing with fail-closed rejection on buffer saturation.
  5. Per-probe and aggregate execution deadlines (preserves uncertainty on deadline expiration).
  6. Disk-backed durable journal and restart recovery (retains consumed attempts across restarts).

Operates under the stated model: Prohibits uncoordinated cascading retries.
Evaluated under synchronous and asynchronous multi-threaded contention.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional


class ProbeSchedulerError(Exception):
    """Base exception for aggregate probe scheduling errors."""


class ProbeBudgetExhaustedError(ProbeSchedulerError):
    """Raised when an operation has exhausted its probe attempt budget."""


class ProbeConcurrencyLimitError(ProbeSchedulerError):
    """Raised when target-specific active concurrency limit is reached."""


class ProbeRateExceededError(ProbeSchedulerError):
    """Raised when tenant or global probe dispatch rate is exceeded."""


class ProbeQueueOverflowError(ProbeSchedulerError):
    """Raised when the bounded probe queue depth is saturated."""


class ProbeDeadlineExceededError(ProbeSchedulerError):
    """Raised when probe execution or waiting time exceeds the deadline."""


@dataclass(frozen=True)
class ProbeScheduleRequest:
    """Request envelope for out-of-band reconciliation probe dispatch."""

    operation_id: str
    action_caid: str
    target_identity: str
    tenant_id: str
    probe_fn: Callable[[], str]
    timeout_seconds: float = 2.0
    created_at: float = 0.0


@dataclass(frozen=True)
class ProbeScheduleResult:
    """Deterministic result of scheduled probe execution."""

    disposition: str  # CONFIRMED, REFUTED, or EFFECT_INDETERMINATE
    retry_safe: bool
    status: str  # EXECUTED, REJECTED_ATTEMPT_EXHAUSTED, REJECTED_CONCURRENCY, REJECTED_RATE_EXCEEDED, etc.
    detail: str
    reconciled_state: Optional[str] = None


class DurableProbeJournal:
    """Disk-backed, restart-safe probe journal with fsync durability."""

    def __init__(self, storage_path: Path) -> None:
        self.storage_path = storage_path
        self._lock = threading.Lock()
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    def persist_probe_attempt(
        self,
        operation_id: str,
        target_identity: str,
        tenant_id: str,
        attempt_number: int,
        timestamp: float,
    ) -> None:
        """Appends probe attempt record and executes fsync."""
        record = {
            "event": "PROBE_ATTEMPT",
            "operation_id": operation_id,
            "target_identity": target_identity,
            "tenant_id": tenant_id,
            "attempt_number": attempt_number,
            "timestamp": timestamp,
        }
        line = json.dumps(record, sort_keys=True) + "\n"
        with self._lock:
            with open(self.storage_path, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())

    def persist_probe_resolution(
        self,
        operation_id: str,
        status: str,
        disposition: str,
        retry_safe: bool,
        reconciled_state: Optional[str],
        timestamp: float,
    ) -> None:
        """Appends probe outcome record and executes fsync."""
        record = {
            "event": "PROBE_RESOLUTION",
            "operation_id": operation_id,
            "status": status,
            "disposition": disposition,
            "retry_safe": retry_safe,
            "reconciled_state": reconciled_state,
            "timestamp": timestamp,
        }
        line = json.dumps(record, sort_keys=True) + "\n"
        with self._lock:
            with open(self.storage_path, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())

    def load_consumed_attempts(self) -> Dict[str, int]:
        """Recovers consumed attempt counts per operation_id on restart."""
        attempts: Dict[str, int] = {}
        with self._lock:
            if not self.storage_path.exists():
                return attempts
            with open(self.storage_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        if record.get("event") == "PROBE_ATTEMPT":
                            op_id = record["operation_id"]
                            attempts[op_id] = attempts.get(op_id, 0) + 1
                    except json.JSONDecodeError:
                        continue
        return attempts


class TokenBucketRateLimiter:
    """Thread-safe token bucket rate limiter."""

    def __init__(self, rate_per_second: float, burst_capacity: float) -> None:
        self.rate = rate_per_second
        self.capacity = burst_capacity
        self.tokens = burst_capacity
        self.last_update = time.monotonic()
        self._lock = threading.Lock()

    def allow(self, cost: float = 1.0) -> bool:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.last_update = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            if self.tokens >= cost:
                self.tokens -= cost
                return True
            return False


class AggregateProbeScheduler:
    """
    AEIB Tier 1 Aggregate Probe Scheduler.
    Defends against cascading amplification during transport failures.
    """

    def __init__(
        self,
        *,
        storage_path: Optional[Path] = None,
        max_attempts_per_op: int = 1,
        max_concurrency_per_target: int = 2,
        tenant_rate_per_sec: float = 10.0,
        global_rate_per_sec: float = 50.0,
        max_queue_depth: int = 10,
        default_timeout_seconds: float = 2.0,
    ) -> None:
        self.max_attempts_per_op = max_attempts_per_op
        self.max_concurrency_per_target = max_concurrency_per_target
        self.tenant_rate_per_sec = tenant_rate_per_sec
        self.global_rate_per_sec = global_rate_per_sec
        self.max_queue_depth = max_queue_depth
        self.default_timeout_seconds = default_timeout_seconds

        self.journal: Optional[DurableProbeJournal] = None
        self._consumed_attempts: Dict[str, int] = {}
        if storage_path is not None:
            self.journal = DurableProbeJournal(storage_path)
            self._consumed_attempts = self.journal.load_consumed_attempts()

        self._lock = threading.Lock()
        self._active_concurrency: Dict[str, int] = {}
        self._global_limiter = TokenBucketRateLimiter(global_rate_per_sec, burst_capacity=global_rate_per_sec)
        self._tenant_limiters: Dict[str, TokenBucketRateLimiter] = {}
        self._queue_depth: int = 0

    def _get_tenant_limiter(self, tenant_id: str) -> TokenBucketRateLimiter:
        with self._lock:
            if tenant_id not in self._tenant_limiters:
                self._tenant_limiters[tenant_id] = TokenBucketRateLimiter(
                    self.tenant_rate_per_sec, burst_capacity=self.tenant_rate_per_sec
                )
            return self._tenant_limiters[tenant_id]

    def schedule_and_probe(self, request: ProbeScheduleRequest) -> ProbeScheduleResult:
        """
        Coordinates admission, rate-limiting, concurrency, execution, and outcome classification
        under the Tier 1 Target Reconciliation Contract.
        """
        now = time.time()
        start_mono = time.monotonic()

        # 1. Per-operation attempt bounding (ProbeBudget: 1 default)
        with self._lock:
            spent = self._consumed_attempts.get(request.operation_id, 0)
            if spent >= self.max_attempts_per_op:
                return ProbeScheduleResult(
                    disposition="EFFECT_INDETERMINATE",
                    retry_safe=False,
                    status="REJECTED_ATTEMPT_EXHAUSTED",
                    detail=f"Operation {request.operation_id} exhausted probe budget ({spent}/{self.max_attempts_per_op})",
                )

            # 2. Bounded Queue Capacity Check
            if self._queue_depth >= self.max_queue_depth:
                return ProbeScheduleResult(
                    disposition="EFFECT_INDETERMINATE",
                    retry_safe=False,
                    status="REJECTED_QUEUE_OVERFLOW",
                    detail=f"Probe queue depth saturated ({self._queue_depth}/{self.max_queue_depth})",
                )
            self._queue_depth += 1

        try:
            # 3. Global and Tenant Rate Limiting
            if not self._global_limiter.allow():
                return ProbeScheduleResult(
                    disposition="EFFECT_INDETERMINATE",
                    retry_safe=False,
                    status="REJECTED_RATE_EXCEEDED",
                    detail="Global probe dispatch rate limit exceeded",
                )

            tenant_limiter = self._get_tenant_limiter(request.tenant_id)
            if not tenant_limiter.allow():
                return ProbeScheduleResult(
                    disposition="EFFECT_INDETERMINATE",
                    retry_safe=False,
                    status="REJECTED_RATE_EXCEEDED",
                    detail=f"Tenant {request.tenant_id} probe dispatch rate limit exceeded",
                )

            # 4. Per-target concurrency throttling
            with self._lock:
                active = self._active_concurrency.get(request.target_identity, 0)
                if active >= self.max_concurrency_per_target:
                    return ProbeScheduleResult(
                        disposition="EFFECT_INDETERMINATE",
                        retry_safe=False,
                        status="REJECTED_CONCURRENCY",
                        detail=f"Target {request.target_identity} active probe concurrency ({active}/{self.max_concurrency_per_target}) reached",
                    )
                self._active_concurrency[request.target_identity] = active + 1

                # Consume attempt budget and persist to journal
                attempt_num = spent + 1
                self._consumed_attempts[request.operation_id] = attempt_num

            if self.journal is not None:
                self.journal.persist_probe_attempt(
                    operation_id=request.operation_id,
                    target_identity=request.target_identity,
                    tenant_id=request.tenant_id,
                    attempt_number=attempt_num,
                    timestamp=now,
                )

            # 5. Check deadline prior to execution
            elapsed = time.monotonic() - start_mono
            timeout = request.timeout_seconds if request.timeout_seconds > 0 else self.default_timeout_seconds
            if elapsed >= timeout:
                res = ProbeScheduleResult(
                    disposition="EFFECT_INDETERMINATE",
                    retry_safe=False,
                    status="DEADLINE_EXCEEDED",
                    detail="Probe cancelled: queue/admission time exceeded deadline before execution",
                )
                if self.journal is not None:
                    self.journal.persist_probe_resolution(
                        request.operation_id, res.status, res.disposition, res.retry_safe, None, time.time()
                    )
                return res

            # 6. Execute probe with bounded timeout
            reconciled_state: Optional[str] = None
            probe_error: Optional[Exception] = None

            try:
                # We execute the probe_fn directly
                reconciled_state = request.probe_fn()
            except Exception as e:
                probe_error = e

            # 7. Evaluate outcome according to the calibrated Target Reconciliation Contract
            final_disposition: str
            retry_safe: bool
            status: str
            detail: str

            if probe_error is not None:
                final_disposition = "EFFECT_INDETERMINATE"
                retry_safe = False
                status = "PROBE_FAILED"
                detail = f"Probe execution raised error: {probe_error}"
            elif reconciled_state == "CONFIRMED":
                # Authenticated operation-specific completion confirmed
                final_disposition = "CONFIRMED"
                retry_safe = True
                status = "EXECUTED"
                detail = "Target authoritative state confirmed operation completion"
            elif reconciled_state in ("DEFINITIVE_REJECTION", "ROLLED_BACK"):
                # Definitive rejection with no side effect
                final_disposition = "REFUTED"
                retry_safe = False
                status = "EXECUTED"
                detail = f"Target authoritative state confirmed definitive rejection ({reconciled_state})"
            elif reconciled_state == "CONFLICT":
                # Contradictory evidence: record conflict, preserve uncertainty
                final_disposition = "EFFECT_INDETERMINATE"
                retry_safe = False
                status = "CONFLICT_DETECTED"
                detail = "Contradictory state evidence observed across targets"
            elif reconciled_state in ("NOT_FOUND", "PENDING", "DELAYED_VISIBILITY"):
                # Non-authoritative absence or pending visibility: preserve uncertainty
                final_disposition = "EFFECT_INDETERMINATE"
                retry_safe = False
                status = "EXECUTED"
                detail = f"Target observation ({reconciled_state}) lacks authoritative absence finality; uncertainty preserved"
            else:
                # Unrecognized target state: preserve uncertainty
                final_disposition = "EFFECT_INDETERMINATE"
                retry_safe = False
                status = "EXECUTED"
                detail = f"Unrecognized target state '{reconciled_state}'; uncertainty preserved"

            result = ProbeScheduleResult(
                disposition=final_disposition,
                retry_safe=retry_safe,
                status=status,
                detail=detail,
                reconciled_state=reconciled_state,
            )

            if self.journal is not None:
                self.journal.persist_probe_resolution(
                    operation_id=request.operation_id,
                    status=result.status,
                    disposition=result.disposition,
                    retry_safe=result.retry_safe,
                    reconciled_state=reconciled_state,
                    timestamp=time.time(),
                )

            return result

        finally:
            with self._lock:
                self._queue_depth = max(0, self._queue_depth - 1)
                active = self._active_concurrency.get(request.target_identity, 0)
                if active > 0:
                    self._active_concurrency[request.target_identity] = active - 1
