#!/usr/bin/env python3
"""
tests/test_soak_test_long_haul.py
Unit tests for AEGIS long-haul soak runner & FL-004 stability gate.
Zero mocks.
"""

import sys
import ast
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from benchmarks.soak_test_long_haul import (
    AuthoritativeBankLedger,
    SoakTestRunner,
    MemoryLeakDetected,
    get_current_rss_kb
)


def test_zero_mock_ast_purity():
    soak_path = ROOT / "benchmarks" / "soak_test_long_haul.py"
    tree = ast.parse(soak_path.read_text(encoding="utf-8"))
    banned = {"mock", "unittest.mock", "MagicMock"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in banned, f"Banned import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            assert node.module not in banned, f"Banned module: {node.module}"


def test_fl004_invariant_zero_duplicates(tmp_path):
    csv_file = tmp_path / "soak_test.csv"
    runner = SoakTestRunner(
        duration_seconds=0.0,
        fault_rate=0.30,
        csv_output_path=csv_file
    )
    summary = runner.run(max_iterations=60)
    assert summary["fl004_invariant_satisfied"] is True
    assert summary["duplicate_count"] == 0
    assert summary["status"] == "PASSED"
    assert csv_file.exists()
    lines = csv_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 61  # header + 60 entries
    assert lines[0] == "timestamp_utc,caid,target_endpoint,latency_ms,rss_mb,fault_injected,disposition,duplicate_detected"


def test_authoritative_bank_ledger():
    ledger = AuthoritativeBankLedger(":memory:")
    # First transfer
    ok1, status1 = ledger.execute_transfer("idem_1", "caid_1", "acct_alpha", 500)
    assert ok1 is True
    assert status1 == "COMMITTED"
    assert ledger.get_account_balance("acct_alpha") == 999500

    # Duplicate transfer with same idempotency key
    ok2, status2 = ledger.execute_transfer("idem_1", "caid_1", "acct_alpha", 500)
    assert ok2 is True
    assert status2 == "ALREADY_COMMITTED"
    # Balance must NOT be debited twice
    assert ledger.get_account_balance("acct_alpha") == 999500
    assert ledger.count_transactions_for_caid("caid_1") == 1


def test_memory_leak_evaluator():
    runner = SoakTestRunner(duration_seconds=0.0)

    # 1. Non-leaking stable profile
    stable_samples = [(float(i), 30000 + (i % 50)) for i in range(100)]
    slope_stable, leak_stable = runner._evaluate_memory_drift(stable_samples)
    assert leak_stable is False

    # 2. Aggressive unconstrained leak profile (>500 KB/sec and >50% growth)
    leaking_samples = [(float(i), 20000 + (i * 1000)) for i in range(100)]
    slope_leak, leak_detected = runner._evaluate_memory_drift(leaking_samples)
    assert leak_detected is True
    assert slope_leak > 500.0
