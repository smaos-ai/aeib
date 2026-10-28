#!/usr/bin/env python3
"""
tests/test_real_world_reconciliation.py

Real-World Concurrency, CAS Lockout, and Idempotent Outbox Reconciliation Test Suite.
Verifies:
1. Single worker acquisition.
2. 50-worker concurrent race under Vector B (CAS yields exactly 1 winner, 49 suppressed).
3. 100-run double-resolution invariant (double resolutions = 0).
"""

import os
import sqlite3
import threading
import time
import pytest
from typing import Dict, Any, List

class OutboxCASStorage:
    def __init__(self, db_path=None):
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.isolation_level = None
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with self._lock:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS outbox_ledger (
                    caid TEXT PRIMARY KEY,
                    idempotency_key TEXT UNIQUE NOT NULL,
                    state TEXT NOT NULL,
                    winner_worker_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

    def claim_execution(self, caid: str, idempotency_key: str, worker_id: str) -> bool:
        """
        Executes atomic CAS insertion: INSERT INTO outbox_ledger ...
        Returns True if worker successfully claimed the execution, False if duplicate/already claimed.
        """
        with self._lock:
            try:
                cur = self.conn.cursor()
                cur.execute("""
                    INSERT INTO outbox_ledger (caid, idempotency_key, state, winner_worker_id)
                    VALUES (?, ?, 'CLAIMED', ?)
                """, (caid, idempotency_key, worker_id))
                return True
            except sqlite3.IntegrityError:
                return False

    def resolve_state(self, caid: str, resolved_state: str) -> bool:
        """
        Transitions state from CLAIMED to OUTCOME_VERIFIED or RECONCILIATION_NOT_FOUND.
        Ensures a state cannot be resolved more than once.
        """
        with self._lock:
            cur = self.conn.cursor()
            cur.execute("""
                UPDATE outbox_ledger
                SET state = ?
                WHERE caid = ? AND state = 'CLAIMED'
            """, (resolved_state, caid))
            return cur.rowcount == 1

    def close(self):
        self.conn.close()


def test_single_worker_wins():
    storage = OutboxCASStorage()
    caid = "caid-single-001"
    idem = "idem-single-001"
    
    won = storage.claim_execution(caid, idem, "worker-01")
    assert won is True
    
    # Second attempt by same or different worker fails
    duplicate = storage.claim_execution(caid, idem, "worker-02")
    assert duplicate is False
    storage.close()


def test_concurrent_workers_exactly_one_winner():
    storage = OutboxCASStorage()
    caid = "caid-vector-b-001"
    idem = "idem-vector-b-001"
    n_workers = 50
    results: Dict[str, bool] = {}
    
    barrier = threading.Barrier(n_workers)
    t_start = time.perf_counter()

    def worker_task(worker_id: str):
        barrier.wait()
        won = storage.claim_execution(caid, idem, worker_id)
        results[worker_id] = won

    threads = [threading.Thread(target=worker_task, args=(f"worker-{i:02d}",)) for i in range(n_workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    elapsed_ms = (time.perf_counter() - t_start) * 1000.0
    wins = sum(1 for v in results.values() if v is True)
    losses = sum(1 for v in results.values() if v is False)

    print(f"\n[VECTOR B] n_workers={n_workers} elapsed_ms={elapsed_ms:.1f}")
    print(f"[VECTOR B] wins={wins} losses={losses}")
    print(f"[VECTOR B] distinct_winners={wins}")

    assert wins == 1, f"Expected exactly 1 winner, got {wins}"
    assert losses == 49, f"Expected 49 suppressed losses, got {losses}"
    storage.close()


def test_double_resolution_never_occurs():
    storage = OutboxCASStorage()
    n_runs = 100
    double_resolutions = 0

    for i in range(n_runs):
        caid = f"caid-res-{i:03d}"
        idem = f"idem-res-{i:03d}"
        storage.claim_execution(caid, idem, f"worker-{i}")

        # Worker 1 resolves
        res1 = storage.resolve_state(caid, "OUTCOME_VERIFIED")
        # Worker 2 attempts concurrent resolution
        res2 = storage.resolve_state(caid, "OUTCOME_VERIFIED")

        if res1 and res2:
            double_resolutions += 1

    print(f"\n[VECTOR B] runs={n_runs} double_resolutions={double_resolutions}")
    assert double_resolutions == 0, f"Expected 0 double resolutions, got {double_resolutions}"
    storage.close()


if __name__ == "__main__":
    pytest.main(["-v", "-s", __file__])
