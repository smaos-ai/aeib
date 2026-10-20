#!/usr/bin/env python3
"""
benchmarks/run_parallel_burst_stress.py
================================================================================
Stress Benchmark: High-Speed Parallel Burst & Cross-Caller Group-Commit WAL Latch.

Simulates 500 to 1,000 concurrent parallel worker threads firing requests
simultaneously at the Station 1 group-commit latch.

Measures:
- Wall-clock duration and effective throughput (ops/sec)
- Latency percentiles: min, p50, p90, p95, p99, max (in milliseconds)
- Coalescing efficiency: number of hardware fsync system calls executed vs total operations
- Financial integrity verification: verifies 0 double-allocations and 0 lost updates
- Mathematical solvency invariant verification under extreme parallel contention

Evaluated under the stated model. Strict zero-mock AST purity enforced.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List

# Ensure repository root is on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.ncm_parallel_burst_latch import (
    CrossCallerGroupCommitLatch,
    DecisionCascadeFilter,
)


def run_parallel_burst_stress(
    num_threads: int = 500,
    flush_window_ms: float = 2.0,
    max_batch_size: int = 64,
    sprint_ceiling: int = 10_000_000,
    amount_per_op: int = 50,
    wal_dir: str | None = None,
) -> Dict[str, Any]:
    """
    Executes parallel burst stress benchmark across concurrent worker threads.
    Synchronizes thread launch via threading.Barrier to simulate a burst.
    """
    cleanup_temp = False
    if wal_dir is None:
        wal_dir = tempfile.mkdtemp(prefix="ncm_burst_stress_")
        cleanup_temp = True

    wal_path = os.path.join(wal_dir, f"burst_stress_{num_threads}th.wal")

    try:
        latch = CrossCallerGroupCommitLatch(
            wal_path=wal_path,
            sprint_ceiling=sprint_ceiling,
            flush_window_ms=flush_window_ms,
            max_batch_size=max_batch_size,
        )

        barrier = threading.Barrier(num_threads)
        latencies_ms: List[float] = []
        statuses: List[str] = []
        lock = threading.Lock()

        def worker(worker_id: int) -> None:
            payload = {
                "worker_id": worker_id,
                "action": "disburse_refund",
                "nonce": time.time_ns(),
                "trace_token": f"burst_{worker_id}_{os.getpid()}",
            }
            # Synchronize so all threads fire simultaneously
            barrier.wait()
            t0 = time.perf_counter()
            res = latch.submit_mutation(
                tool_name="POST /v1/refunds",
                payload=payload,
                amount_minor=amount_per_op,
            )
            elapsed = (time.perf_counter() - t0) * 1000.0

            with lock:
                latencies_ms.append(elapsed)
                statuses.append(res.status)

        t_start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker, i) for i in range(num_threads)]
            for f in concurrent.futures.as_completed(futures):
                f.result()
        wall_clock_sec = time.perf_counter() - t_start

        latencies_ms.sort()
        count = len(latencies_ms)
        p50 = latencies_ms[int(count * 0.50)]
        p90 = latencies_ms[int(count * 0.90)]
        p95 = latencies_ms[int(count * 0.95)]
        p99 = latencies_ms[int(count * 0.99)]
        min_lat = latencies_ms[0]
        max_lat = latencies_ms[-1]
        avg_lat = sum(latencies_ms) / max(1, count)

        stats = latch.get_stats()
        latch.close()

        successful_ops = sum(1 for s in statuses if s == "COMMITTED")
        rejected_ops = sum(1 for s in statuses if s != "COMMITTED")

        expected_confirmed = successful_ops * amount_per_op
        actual_confirmed = stats["confirmed"]
        double_allocations = max(0, actual_confirmed - expected_confirmed)
        lost_updates = max(0, expected_confirmed - actual_confirmed)

        solvency_held = (stats["escrowed"] + stats["confirmed"]) <= sprint_ceiling
        throughput = count / max(0.0001, wall_clock_sec)
        coalescing_ratio = float(count) / max(1, stats["fsync_count"])
        fsync_reduction_pct = (1.0 - (float(stats["fsync_count"]) / max(1, count))) * 100.0

        metrics = {
            "status": "PASS" if solvency_held and double_allocations == 0 and lost_updates == 0 else "FAIL",
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "configuration": {
                "thread_count": num_threads,
                "flush_window_ms": flush_window_ms,
                "max_batch_size": max_batch_size,
                "sprint_ceiling_minor": sprint_ceiling,
                "amount_per_op_minor": amount_per_op,
            },
            "execution": {
                "total_operations": count,
                "successful_operations": successful_ops,
                "rejected_operations": rejected_ops,
                "wall_clock_seconds": round(wall_clock_sec, 4),
                "throughput_ops_per_sec": round(throughput, 2),
            },
            "latency_ms": {
                "min": round(min_lat, 3),
                "avg": round(avg_lat, 3),
                "p50": round(p50, 3),
                "p90": round(p90, 3),
                "p95": round(p95, 3),
                "p99": round(p99, 3),
                "max": round(max_lat, 3),
            },
            "coalescing_efficiency": {
                "total_operations": count,
                "fsync_count": stats["fsync_count"],
                "coalescing_ratio": round(coalescing_ratio, 2),
                "fsync_reduction_pct": round(fsync_reduction_pct, 2),
            },
            "solvency_and_integrity": {
                "escrowed_minor": stats["escrowed"],
                "confirmed_minor": stats["confirmed"],
                "sprint_ceiling_minor": sprint_ceiling,
                "solvency_invariant_held": solvency_held,
                "double_allocations_detected": double_allocations,
                "lost_updates_detected": lost_updates,
            },
        }
        return metrics

    finally:
        if cleanup_temp:
            if os.path.exists(wal_path):
                try:
                    os.remove(wal_path)
                except OSError:
                    pass
            if os.path.exists(wal_dir):
                try:
                    os.rmdir(wal_dir)
                except OSError:
                    pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description="High-Speed Parallel Burst & Cross-Caller Group-Commit WAL Latch Stress Benchmark"
    )
    parser.add_argument("--threads", type=int, default=500, help="Concurrent worker threads (default: 500)")
    parser.add_argument("--flush-window-ms", type=float, default=2.0, help="Flush window in ms (default: 2.0)")
    parser.add_argument("--max-batch-size", type=int, default=64, help="Max requests per batch (default: 64)")
    parser.add_argument("--sprint-ceiling", type=int, default=10_000_000, help="Sprint budget ceiling in minor units")
    parser.add_argument("--amount-per-op", type=int, default=50, help="Minor units requested per mutation")
    parser.add_argument("--output", type=str, default="", help="Optional JSON output file path")
    parser.add_argument("--quiet", action="store_true", help="Suppress console summary table")

    args = parser.parse_args()

    metrics = run_parallel_burst_stress(
        num_threads=args.threads,
        flush_window_ms=args.flush_window_ms,
        max_batch_size=args.max_batch_size,
        sprint_ceiling=args.sprint_ceiling,
        amount_per_op=args.amount_per_op,
    )

    formatted_json = json.dumps(metrics, indent=2)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(formatted_json, encoding="utf-8")

    if not args.quiet:
        exec_info = metrics["execution"]
        lat_info = metrics["latency_ms"]
        coal_info = metrics["coalescing_efficiency"]
        solv_info = metrics["solvency_and_integrity"]

        print("=" * 72)
        print("PARALLEL BURST STRESS BENCHMARK RESULTS")
        print("=" * 72)
        print(f"Threads:            {args.threads}")
        print(f"Total Operations:   {exec_info['total_operations']}")
        print(f"Successful:         {exec_info['successful_operations']}")
        print(f"Wall Duration:      {exec_info['wall_clock_seconds']} s")
        print(f"Throughput:         {exec_info['throughput_ops_per_sec']} ops/sec")
        print("-" * 72)
        print("Latency (ms):")
        print(f"  p50:  {lat_info['p50']} ms | p90: {lat_info['p90']} ms | p95: {lat_info['p95']} ms | p99: {lat_info['p99']} ms")
        print(f"  min:  {lat_info['min']} ms | avg: {lat_info['avg']} ms | max: {lat_info['max']} ms")
        print("-" * 72)
        print("Group-Commit Coalescing Efficiency:")
        print(f"  Total fsync calls:  {coal_info['fsync_count']}")
        print(f"  Coalescing ratio:   {coal_info['coalescing_ratio']}x")
        print(f"  Fsync reduction:    {coal_info['fsync_reduction_pct']}%")
        print("-" * 72)
        print("Solvency & Financial Integrity:")
        print(f"  Ceiling:            {solv_info['sprint_ceiling_minor']}")
        print(f"  Confirmed:          {solv_info['confirmed_minor']}")
        print(f"  Escrowed:           {solv_info['escrowed_minor']}")
        print(f"  Solvency Invariant: {'HELD' if solv_info['solvency_invariant_held'] else 'VIOLATED'}")
        print(f"  Double-Allocations: {solv_info['double_allocations_detected']}")
        print(f"  Lost Updates:       {solv_info['lost_updates_detected']}")
        print("=" * 72)

    return 0 if metrics["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
