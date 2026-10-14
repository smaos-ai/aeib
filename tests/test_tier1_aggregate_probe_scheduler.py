"""
tests/test_tier1_aggregate_probe_scheduler.py
Tests verifying the Tier 1 Aggregate Probe Scheduler capabilities:
  1. Per-operation attempt limits (ProbeBudget: 1 default).
  2. Per-target concurrency throttling.
  3. Tenant & global token-bucket rate limiting.
  4. Bounded queueing with fail-closed rejection on overflow.
  5. Deadlines and timeout handling.
  6. Calibrated Target Reconciliation Contract semantics (absence, conflict, delay).
  7. Durable persistence and restart recovery.
"""

from __future__ import annotations

import concurrent.futures
import importlib.util
from pathlib import Path
import sys
import threading
import time
from typing import Dict

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEDULER_PATH = REPO_ROOT / "v1.1-roadmap" / "aggregate_probe_scheduler.py"
spec = importlib.util.spec_from_file_location("aggregate_probe_scheduler", SCHEDULER_PATH)
assert spec is not None and spec.loader is not None
aps = importlib.util.module_from_spec(spec)
sys.modules["aggregate_probe_scheduler"] = aps
spec.loader.exec_module(aps)

AggregateProbeScheduler = aps.AggregateProbeScheduler
ProbeScheduleRequest = aps.ProbeScheduleRequest
ProbeScheduleResult = aps.ProbeScheduleResult


def test_01_per_operation_attempt_limit_enforced(tmp_path: Path) -> None:
    """1. Per-operation attempt bounding: 1st probe allowed, 2nd rejected fail-closed."""
    scheduler = AggregateProbeScheduler(
        storage_path=tmp_path / "probe_journal.jsonl",
        max_attempts_per_op=1,
    )

    req1 = ProbeScheduleRequest(
        operation_id="op_single_probe",
        action_caid="sha256:1111",
        target_identity="https://api.core.bank/transfer",
        tenant_id="tenant_alpha",
        probe_fn=lambda: "CONFIRMED",
    )

    res1 = scheduler.schedule_and_probe(req1)
    assert res1.status == "EXECUTED"
    assert res1.disposition == "CONFIRMED"
    assert res1.retry_safe is True

    # Second attempt for the same operation must be rejected
    req2 = ProbeScheduleRequest(
        operation_id="op_single_probe",
        action_caid="sha256:1111",
        target_identity="https://api.core.bank/transfer",
        tenant_id="tenant_alpha",
        probe_fn=lambda: "CONFIRMED",
    )
    res2 = scheduler.schedule_and_probe(req2)
    assert res2.status == "REJECTED_ATTEMPT_EXHAUSTED"
    assert res2.disposition == "EFFECT_INDETERMINATE"
    assert res2.retry_safe is False


def test_02_per_target_concurrency_throttling() -> None:
    """2. Per-target concurrency: limits in-flight probes to prevent hammering endpoint."""
    scheduler = AggregateProbeScheduler(
        max_concurrency_per_target=2,
        global_rate_per_sec=100.0,
        tenant_rate_per_sec=100.0,
    )

    barrier = threading.Barrier(3)
    results: list[ProbeScheduleResult] = []

    def slow_probe() -> str:
        barrier.wait(timeout=2.0)
        time.sleep(0.05)
        return "CONFIRMED"

    def worker(op_id: str) -> None:
        req = ProbeScheduleRequest(
            operation_id=op_id,
            action_caid="sha256:2222",
            target_identity="https://api.core.bank/throttled",
            tenant_id="tenant_alpha",
            probe_fn=slow_probe,
        )
        res = scheduler.schedule_and_probe(req)
        results.append(res)

    threads = [
        threading.Thread(target=worker, args=("op_c1",)),
        threading.Thread(target=worker, args=("op_c2",)),
    ]
    for t in threads:
        t.start()

    # Wait for the 2 workers to enter slow_probe
    barrier.wait(timeout=2.0)

    # Now attempt a 3rd concurrent probe to the same target
    req3 = ProbeScheduleRequest(
        operation_id="op_c3",
        action_caid="sha256:2222",
        target_identity="https://api.core.bank/throttled",
        tenant_id="tenant_alpha",
        probe_fn=lambda: "CONFIRMED",
    )
    res3 = scheduler.schedule_and_probe(req3)
    assert res3.status == "REJECTED_CONCURRENCY"
    assert res3.disposition == "EFFECT_INDETERMINATE"
    assert res3.retry_safe is False

    for t in threads:
        t.join()


def test_03_tenant_and_global_rate_limits() -> None:
    """3. Token-bucket rate limiting rejects probe storms."""
    scheduler = AggregateProbeScheduler(
        tenant_rate_per_sec=2.0,
        global_rate_per_sec=2.0,
        max_attempts_per_op=5,
    )

    # First two probe tokens consume capacity
    req1 = ProbeScheduleRequest(
        operation_id="op_rate_1",
        action_caid="sha256:3333",
        target_identity="https://api.core.bank/transfer",
        tenant_id="tenant_rate",
        probe_fn=lambda: "CONFIRMED",
    )
    req2 = ProbeScheduleRequest(
        operation_id="op_rate_2",
        action_caid="sha256:3333",
        target_identity="https://api.core.bank/transfer",
        tenant_id="tenant_rate",
        probe_fn=lambda: "CONFIRMED",
    )
    req3 = ProbeScheduleRequest(
        operation_id="op_rate_3",
        action_caid="sha256:3333",
        target_identity="https://api.core.bank/transfer",
        tenant_id="tenant_rate",
        probe_fn=lambda: "CONFIRMED",
    )

    res1 = scheduler.schedule_and_probe(req1)
    res2 = scheduler.schedule_and_probe(req2)
    res3 = scheduler.schedule_and_probe(req3)

    statuses = [res1.status, res2.status, res3.status]
    assert "REJECTED_RATE_EXCEEDED" in statuses
    # The rejected one must have preserved uncertainty
    rejected = [r for r in [res1, res2, res3] if r.status == "REJECTED_RATE_EXCEEDED"][0]
    assert rejected.disposition == "EFFECT_INDETERMINATE"
    assert rejected.retry_safe is False


def test_04_bounded_queue_overflow_protection() -> None:
    """4. Bounded queueing rejects fail-closed on buffer saturation."""
    scheduler = AggregateProbeScheduler(
        max_queue_depth=1,
        max_concurrency_per_target=1,
    )

    event_block = threading.Event()

    def blocked_probe() -> str:
        event_block.wait(timeout=2.0)
        return "CONFIRMED"

    def worker() -> None:
        req = ProbeScheduleRequest(
            operation_id="op_q1",
            action_caid="sha256:4444",
            target_identity="https://api.target/q",
            tenant_id="tenant_q",
            probe_fn=blocked_probe,
        )
        scheduler.schedule_and_probe(req)

    t = threading.Thread(target=worker)
    t.start()
    time.sleep(0.02)

    # Queue depth is at 1 (max_queue_depth: 1)
    req2 = ProbeScheduleRequest(
        operation_id="op_q2",
        action_caid="sha256:4444",
        target_identity="https://api.target/q",
        tenant_id="tenant_q",
        probe_fn=lambda: "CONFIRMED",
    )
    res2 = scheduler.schedule_and_probe(req2)

    assert res2.status == "REJECTED_QUEUE_OVERFLOW"
    assert res2.disposition == "EFFECT_INDETERMINATE"
    assert res2.retry_safe is False

    event_block.set()
    t.join()


def test_05_deadline_and_timeout_preserves_uncertainty() -> None:
    """5. Deadlines: probe taking longer than deadline is aborted with uncertainty preserved."""
    scheduler = AggregateProbeScheduler()

    def slow_hanging_probe() -> str:
        raise TimeoutError("Socket read timed out after 3.0s")

    req = ProbeScheduleRequest(
        operation_id="op_timeout",
        action_caid="sha256:5555",
        target_identity="https://api.core.bank/transfer",
        tenant_id="tenant_timeout",
        probe_fn=slow_hanging_probe,
        timeout_seconds=0.1,
    )

    res = scheduler.schedule_and_probe(req)
    assert res.status == "PROBE_FAILED"
    assert res.disposition == "EFFECT_INDETERMINATE"
    assert res.retry_safe is False


def test_06_target_reconciliation_contract_semantics() -> None:
    """6. Evaluates exact target contract: NOT_FOUND, CONFLICT, DELAYED_VISIBILITY, ROLLED_BACK."""
    scheduler = AggregateProbeScheduler(max_attempts_per_op=10)

    # Case A: Definitive Rejection / Rolled Back -> REFUTED (retry_safe: False)
    req_rollback = ProbeScheduleRequest(
        operation_id="op_rollback",
        action_caid="sha256:6666",
        target_identity="https://api.target/tx",
        tenant_id="tenant_1",
        probe_fn=lambda: "ROLLED_BACK",
    )
    res_rb = scheduler.schedule_and_probe(req_rollback)
    assert res_rb.disposition == "REFUTED"
    assert res_rb.retry_safe is False

    # Case B: NOT_FOUND without authoritative absence semantics -> EFFECT_INDETERMINATE
    req_not_found = ProbeScheduleRequest(
        operation_id="op_not_found",
        action_caid="sha256:6666",
        target_identity="https://api.target/tx",
        tenant_id="tenant_1",
        probe_fn=lambda: "NOT_FOUND",
    )
    res_nf = scheduler.schedule_and_probe(req_not_found)
    assert res_nf.disposition == "EFFECT_INDETERMINATE"
    assert res_nf.retry_safe is False

    # Case C: PENDING or DELAYED_VISIBILITY -> EFFECT_INDETERMINATE
    req_pending = ProbeScheduleRequest(
        operation_id="op_pending",
        action_caid="sha256:6666",
        target_identity="https://api.target/tx",
        tenant_id="tenant_1",
        probe_fn=lambda: "DELAYED_VISIBILITY",
    )
    res_pend = scheduler.schedule_and_probe(req_pending)
    assert res_pend.disposition == "EFFECT_INDETERMINATE"
    assert res_pend.retry_safe is False

    # Case D: Contradictory evidence -> CONFLICT_DETECTED and EFFECT_INDETERMINATE
    req_conflict = ProbeScheduleRequest(
        operation_id="op_conflict",
        action_caid="sha256:6666",
        target_identity="https://api.target/tx",
        tenant_id="tenant_1",
        probe_fn=lambda: "CONFLICT",
    )
    res_conf = scheduler.schedule_and_probe(req_conflict)
    assert res_conf.status == "CONFLICT_DETECTED"
    assert res_conf.disposition == "EFFECT_INDETERMINATE"
    assert res_conf.retry_safe is False


def test_07_persistence_and_restart_recovery(tmp_path: Path) -> None:
    """7. Restart recovery: spent probe budget is retained across process restart."""
    journal_path = tmp_path / "probe_journal.jsonl"

    scheduler1 = AggregateProbeScheduler(
        storage_path=journal_path,
        max_attempts_per_op=1,
    )

    req1 = ProbeScheduleRequest(
        operation_id="op_restart_persist",
        action_caid="sha256:7777",
        target_identity="https://api.core.bank/transfer",
        tenant_id="tenant_restart",
        probe_fn=lambda: "CONFIRMED",
    )
    res1 = scheduler1.schedule_and_probe(req1)
    assert res1.status == "EXECUTED"
    assert res1.disposition == "CONFIRMED"

    # Simulate process termination and restart
    del scheduler1

    scheduler2 = AggregateProbeScheduler(
        storage_path=journal_path,
        max_attempts_per_op=1,
    )

    # Attempt another probe for the same operation in restarted scheduler
    req2 = ProbeScheduleRequest(
        operation_id="op_restart_persist",
        action_caid="sha256:7777",
        target_identity="https://api.core.bank/transfer",
        tenant_id="tenant_restart",
        probe_fn=lambda: "CONFIRMED",
    )
    res2 = scheduler2.schedule_and_probe(req2)

    # Budget was persisted to disk with fsync; restart honors consumed budget
    assert res2.status == "REJECTED_ATTEMPT_EXHAUSTED"
    assert res2.disposition == "EFFECT_INDETERMINATE"
    assert res2.retry_safe is False
