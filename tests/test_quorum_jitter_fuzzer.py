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
tests/test_quorum_jitter_fuzzer.py
================================================================================
Verification Suite for QuorumJitterFuzzer.

Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model.

Tests:
1. QuorumFuzzReceipt validations, boundaries, and frozen immutability.
2. CAID generation across str, bytes, and dictionary payloads.
3. Fuzzer initialization parameters and invalid argument rejection.
4. Nominal execution flow (0 drop, low jitter -> QUORUM_CONVERGED).
5. High jitter execution (> 4800 bps -> QUORUM_CONVERGED_DEGRADED).
6. Total partition execution (10000 bps drop -> HALT_QUORUM_FAILED_PARTITION).
7. Deterministic reproducibility across identical seeds.
8. Parameter validation checks (threshold > nodes, negative jitter, drop rate range).
9. SQLite-WAL persistence and durable ledger queries.
10. Exact mutation boundary testing and Wilson 95% confidence interval verification.
"""

from __future__ import annotations

import math
from pathlib import Path
import sqlite3
import time
from typing import Any, Dict, List, Tuple

import pytest

from src.quorum_jitter_fuzzer import (
    DEFAULT_MAX_JITTER_BPS,
    DEFAULT_PACKET_TIMEOUT_MS,
    DEFAULT_QUORUM_THRESHOLD_M,
    DEFAULT_TOTAL_NODES_N,
    STATUS_QUORUM_CONVERGED,
    STATUS_QUORUM_DEGRADED_JITTER,
    STATUS_QUORUM_FAILED_PARTITION,
    QuorumFuzzReceipt,
    QuorumJitterFuzzer,
    compute_sha256_caid,
)


def compute_wilson_ci_bps(k: int, n: int, z: float = 1.959963984540054) -> Tuple[int, int]:
    """Calculates conservative Wilson 95% confidence interval in basis points."""
    if n == 0:
        return (0, 10000)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    low = max(0.0, centre - half)
    high = min(1.0, centre + half)
    return (int(round(low * 10000)), int(round(high * 10000)))


@pytest.fixture
def temp_db(tmp_path: Path) -> str:
    return str(tmp_path / "test_fuzzer.db")


@pytest.fixture
def fuzzer() -> QuorumJitterFuzzer:
    return QuorumJitterFuzzer(fuzzer_id="fuzzer-test-01")


def test_01_receipt_dataclass_validations() -> None:
    valid_args: Dict[str, Any] = {
        "fuzz_run_id": "run-01",
        "epoch_id": "epoch-01",
        "fuzz_seed": 42,
        "nodes_count": 5,
        "quorum_threshold": 3,
        "packets_sent": 5,
        "packets_dropped": 1,
        "quorum_reached": True,
        "status": STATUS_QUORUM_CONVERGED,
        "receipt_caid": "sha256:11223344556677889900aabbccddeeff11223344556677889900aabbccddeeff",
        "timestamp_ms": 1700000000000,
    }
    r = QuorumFuzzReceipt(**valid_args)
    assert r.fuzz_run_id == "run-01"
    assert r.quorum_reached is True

    # Frozen immutability
    with pytest.raises(Exception):
        r.quorum_reached = False  # type: ignore

    # Validation errors
    for f in ["fuzz_run_id", "epoch_id", "status"]:
        bad = dict(valid_args)
        bad[f] = ""
        with pytest.raises(ValueError, match=f"{f} must be a non-empty string"):
            QuorumFuzzReceipt(**bad)

    bad_seed = dict(valid_args)
    bad_seed["fuzz_seed"] = "bad"  # type: ignore
    with pytest.raises(ValueError, match="fuzz_seed must be an integer"):
        QuorumFuzzReceipt(**bad_seed)

    bad_nodes = dict(valid_args)
    bad_nodes["nodes_count"] = 0
    with pytest.raises(ValueError, match="nodes_count must be a positive integer"):
        QuorumFuzzReceipt(**bad_nodes)

    bad_thresh = dict(valid_args)
    bad_thresh["quorum_threshold"] = 0
    with pytest.raises(ValueError, match="quorum_threshold must be a positive integer"):
        QuorumFuzzReceipt(**bad_thresh)

    bad_exceed = dict(valid_args)
    bad_exceed["quorum_threshold"] = 6
    with pytest.raises(ValueError, match="quorum_threshold cannot exceed nodes_count"):
        QuorumFuzzReceipt(**bad_exceed)

    bad_sent = dict(valid_args)
    bad_sent["packets_sent"] = -1
    with pytest.raises(ValueError, match="packets_sent must be a non-negative integer"):
        QuorumFuzzReceipt(**bad_sent)

    bad_dropped = dict(valid_args)
    bad_dropped["packets_dropped"] = -1
    with pytest.raises(ValueError, match="packets_dropped must be a non-negative integer"):
        QuorumFuzzReceipt(**bad_dropped)

    bad_reached = dict(valid_args)
    bad_reached["quorum_reached"] = "yes"  # type: ignore
    with pytest.raises(ValueError, match="quorum_reached must be a boolean"):
        QuorumFuzzReceipt(**bad_reached)

    bad_caid = dict(valid_args)
    bad_caid["receipt_caid"] = "bad"
    with pytest.raises(ValueError, match="receipt_caid must be a valid sha256 prefix string"):
        QuorumFuzzReceipt(**bad_caid)

    bad_ts = dict(valid_args)
    bad_ts["timestamp_ms"] = 0
    with pytest.raises(ValueError, match="timestamp_ms must be a positive integer"):
        QuorumFuzzReceipt(**bad_ts)


def test_02_caid_generation() -> None:
    c1 = compute_sha256_caid("fuzz_data")
    c2 = compute_sha256_caid(b"fuzz_data")
    assert c1 == c2
    assert c1.startswith("sha256:")

    d1 = {"b": 2, "a": 1}
    d2 = {"a": 1, "b": 2}
    assert compute_sha256_caid(d1) == compute_sha256_caid(d2)


def test_03_fuzzer_initialization_parameters() -> None:
    f = QuorumJitterFuzzer(fuzzer_id="fuzzer-custom", max_allowable_jitter_bps=5000, packet_timeout_ms=1000)
    assert f.fuzzer_id == "fuzzer-custom"
    assert f.max_allowable_jitter_bps == 5000
    assert f.packet_timeout_ms == 1000
    f.close()

    with pytest.raises(ValueError, match="fuzzer_id must be a non-empty string"):
        QuorumJitterFuzzer(fuzzer_id="")
    with pytest.raises(ValueError, match="max_allowable_jitter_bps must be a positive integer"):
        QuorumJitterFuzzer(max_allowable_jitter_bps=0)
    with pytest.raises(ValueError, match="packet_timeout_ms must be a positive integer"):
        QuorumJitterFuzzer(packet_timeout_ms=0)


def test_04_nominal_fuzz_simulation(fuzzer: QuorumJitterFuzzer) -> None:
    r = fuzzer.run_fuzz_simulation(
        epoch_id="epoch-100",
        fuzz_seed=42,
        nodes_count=5,
        quorum_threshold=3,
        drop_rate_bps=0,
        simulated_jitter_bps=500,
        now_ms=1700000000000,
    )
    assert r.status == STATUS_QUORUM_CONVERGED
    assert r.quorum_reached is True
    assert r.packets_sent == 5
    assert r.packets_dropped == 0
    assert r.receipt_caid.startswith("sha256:")


def test_05_high_jitter_degraded_quorum(fuzzer: QuorumJitterFuzzer) -> None:
    # Jitter = 6000 bps > 4800 bps threshold
    r = fuzzer.run_fuzz_simulation(
        epoch_id="epoch-100",
        fuzz_seed=42,
        nodes_count=5,
        quorum_threshold=3,
        drop_rate_bps=0,
        simulated_jitter_bps=6000,
    )
    assert r.status == STATUS_QUORUM_DEGRADED_JITTER
    assert r.quorum_reached is True


def test_06_complete_network_partition(fuzzer: QuorumJitterFuzzer) -> None:
    # 100% packet drop rate (10000 bps)
    r = fuzzer.run_fuzz_simulation(
        epoch_id="epoch-100",
        fuzz_seed=42,
        nodes_count=5,
        quorum_threshold=3,
        drop_rate_bps=10000,
    )
    assert r.status == STATUS_QUORUM_FAILED_PARTITION
    assert r.quorum_reached is False
    assert r.packets_dropped == 5


def test_07_deterministic_seed_reproducibility(fuzzer: QuorumJitterFuzzer) -> None:
    # 2 runs with identical seed 1337 and 40% drop rate
    r1 = fuzzer.run_fuzz_simulation("ep-1", fuzz_seed=1337, drop_rate_bps=4000, now_ms=1000)
    r2 = fuzzer.run_fuzz_simulation("ep-1", fuzz_seed=1337, drop_rate_bps=4000, now_ms=1000)

    assert r1.packets_dropped == r2.packets_dropped
    assert r1.quorum_reached == r2.quorum_reached
    assert r1.status == r2.status


def test_08_input_validations(fuzzer: QuorumJitterFuzzer) -> None:
    with pytest.raises(ValueError, match="epoch_id must be a non-empty string"):
        fuzzer.run_fuzz_simulation("")
    with pytest.raises(ValueError, match="nodes_count must be a positive integer"):
        fuzzer.run_fuzz_simulation("ep-1", nodes_count=0)
    with pytest.raises(ValueError, match="quorum_threshold must be a positive integer"):
        fuzzer.run_fuzz_simulation("ep-1", quorum_threshold=0)
    with pytest.raises(ValueError, match="quorum_threshold cannot exceed nodes_count"):
        fuzzer.run_fuzz_simulation("ep-1", nodes_count=3, quorum_threshold=4)
    with pytest.raises(ValueError, match="drop_rate_bps must be between 0 and 10000"):
        fuzzer.run_fuzz_simulation("ep-1", drop_rate_bps=-1)
    with pytest.raises(ValueError, match="drop_rate_bps must be between 0 and 10000"):
        fuzzer.run_fuzz_simulation("ep-1", drop_rate_bps=10001)
    with pytest.raises(ValueError, match="simulated_jitter_bps must be a non-negative integer"):
        fuzzer.run_fuzz_simulation("ep-1", simulated_jitter_bps=-5)


def test_09_sqlite_persistence_and_queries(temp_db: str) -> None:
    f = QuorumJitterFuzzer(fuzzer_id="fuzzer-sql", db_path=temp_db)
    r = f.run_fuzz_simulation("ep-sql", fuzz_seed=99, drop_rate_bps=0, now_ms=1700000000000)

    records = f.get_ledger_records(limit=10)
    assert len(records) == 1
    assert records[0]["fuzz_run_id"] == r.fuzz_run_id
    assert records[0]["status"] == STATUS_QUORUM_CONVERGED
    f.close()

    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute("SELECT status, quorum_reached, packets_sent FROM quorum_fuzz_events_ledger")
    row = cur.fetchone()
    assert row[0] == STATUS_QUORUM_CONVERGED
    assert row[1] == 1
    assert row[2] == 5
    conn.close()


def test_10_exact_mutation_boundaries(temp_db: str) -> None:
    # Test configuration constants
    assert DEFAULT_MAX_JITTER_BPS == 4800
    assert DEFAULT_PACKET_TIMEOUT_MS == 500
    assert DEFAULT_QUORUM_THRESHOLD_M == 3
    assert DEFAULT_TOTAL_NODES_N == 5

    f = QuorumJitterFuzzer(fuzzer_id="fuzzer-bound", db_path=temp_db)

    # Test default timestamp generation and run_id format
    r_def = f.run_fuzz_simulation("ep-def")
    assert r_def.timestamp_ms > 1_700_000_000_000
    assert r_def.fuzz_run_id.startswith("fuzz-")
    assert len(r_def.fuzz_run_id) == 17

    # Test drop_rate_bps=10000 exact boundary drops all packets
    r_all_drop = f.run_fuzz_simulation("ep-drop-all", drop_rate_bps=10000, nodes_count=4, quorum_threshold=2)
    assert r_all_drop.packets_dropped == 4
    assert r_all_drop.packets_sent == 4
    assert r_all_drop.quorum_reached is False

    # Test timestamp_ms <= 0 boundary
    valid_args: Dict[str, Any] = {
        "fuzz_run_id": "fuzz-1",
        "epoch_id": "ep-1",
        "fuzz_seed": 1,
        "nodes_count": 5,
        "quorum_threshold": 3,
        "packets_sent": 5,
        "packets_dropped": 0,
        "quorum_reached": True,
        "status": STATUS_QUORUM_CONVERGED,
        "receipt_caid": "sha256:" + "0" * 64,
        "timestamp_ms": 0,
    }
    with pytest.raises(ValueError, match="timestamp_ms must be a positive integer"):
        QuorumFuzzReceipt(**valid_args)

    with pytest.raises(ValueError, match="timestamp_ms must be a positive integer"):
        QuorumFuzzReceipt(**dict(valid_args, timestamp_ms=-1))

    # Query with limit=1 and verify exact dictionary fields
    records = f.get_ledger_records(limit=1)
    assert len(records) == 1
    rec = records[0]
    assert rec["fuzz_run_id"] == r_def.fuzz_run_id
    assert rec["epoch_id"] == "ep-def"
    assert rec["fuzz_seed"] == 42
    assert rec["nodes_count"] == 5
    assert rec["quorum_threshold"] == 3
    assert rec["packets_sent"] == 5
    assert rec["packets_dropped"] == 0
    assert rec["quorum_reached"] is True
    assert rec["status"] == STATUS_QUORUM_CONVERGED
    assert rec["receipt_caid"] == r_def.receipt_caid
    assert rec["timestamp_ms"] == r_def.timestamp_ms
    f.close()


def test_11_wilson_ci_bounds() -> None:
    low, high = compute_wilson_ci_bps(30, 30)
    assert low > 8500
    assert high == 10000
