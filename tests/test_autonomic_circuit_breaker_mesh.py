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
tests/test_autonomic_circuit_breaker_mesh.py
================================================================================
Verification Suite for AutonomicCircuitBreakerMesh.

Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model.

Tests:
1. CircuitBreakerReceipt validations, boundaries, and frozen immutability.
2. CAID generation across str, bytes, and dictionary payloads.
3. Mesh initialization parameters and invalid argument rejection.
4. Nominal CLOSED state execution flow and permitted dispatch.
5. Consecutive error threshold trip boundary (5 errors -> OPEN state).
6. Short-circuit fail-closed rejection when circuit is OPEN.
7. Sliding window error rate trip boundary (>= 1500 bps).
8. Token burn rate cap trip boundary (>= 50000 tokens/min).
9. Cooldown expiration and HALF_OPEN probe state transition.
10. HALF_OPEN recovery on successful probe -> CLOSED.
11. HALF_OPEN trip back to OPEN on failed probe.
12. SQLite-WAL persistence and durable ledger queries.
13. Exact mutation boundaries and Wilson 95% confidence interval verification.
"""

from __future__ import annotations

import math
from pathlib import Path
import sqlite3
import time
from typing import Any, Dict, List, Tuple

import pytest

from src.autonomic_circuit_breaker_mesh import (
    CIRCUIT_STATE_CLOSED,
    CIRCUIT_STATE_HALF_OPEN,
    CIRCUIT_STATE_OPEN,
    DEFAULT_COOLDOWN_SECONDS,
    ERROR_RATE_THRESHOLD_BPS,
    MAX_CONSECUTIVE_ERRORS,
    OUTCOME_PERMITTED,
    OUTCOME_PROBE_PERMITTED,
    OUTCOME_SHORT_CIRCUITED,
    TOKEN_BURN_RATE_CAP_PER_MIN,
    AutonomicCircuitBreakerMesh,
    CircuitBreakerReceipt,
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
    return str(tmp_path / "test_circuit_mesh.db")


@pytest.fixture
def mesh() -> AutonomicCircuitBreakerMesh:
    return AutonomicCircuitBreakerMesh(mesh_id="mesh-test-01", cooldown_seconds=10)


def test_01_receipt_dataclass_validations() -> None:
    valid_args: Dict[str, Any] = {
        "event_id": "evt-01",
        "target_id": "tool-payments-api",
        "previous_state": CIRCUIT_STATE_CLOSED,
        "current_state": CIRCUIT_STATE_OPEN,
        "outcome": OUTCOME_SHORT_CIRCUITED,
        "reason": "Exceeded consecutive errors",
        "receipt_caid": "sha256:11223344556677889900aabbccddeeff11223344556677889900aabbccddeeff",
        "timestamp_ms": 1700000000000,
    }
    r = CircuitBreakerReceipt(**valid_args)
    assert r.event_id == "evt-01"

    # Frozen immutability
    with pytest.raises(Exception):
        r.current_state = CIRCUIT_STATE_CLOSED  # type: ignore

    # Validation errors
    for f in ["event_id", "target_id", "previous_state", "current_state", "outcome", "reason"]:
        bad = dict(valid_args)
        bad[f] = ""
        with pytest.raises(ValueError, match=f"{f} must be a non-empty string"):
            CircuitBreakerReceipt(**bad)

    bad_caid = dict(valid_args)
    bad_caid["receipt_caid"] = "bad"
    with pytest.raises(ValueError, match="receipt_caid must be a valid sha256 prefix string"):
        CircuitBreakerReceipt(**bad_caid)

    bad_ts = dict(valid_args)
    bad_ts["timestamp_ms"] = 0
    with pytest.raises(ValueError, match="timestamp_ms must be a positive integer"):
        CircuitBreakerReceipt(**bad_ts)


def test_02_caid_generation() -> None:
    c1 = compute_sha256_caid("circuit_payload")
    c2 = compute_sha256_caid(b"circuit_payload")
    assert c1 == c2
    assert c1.startswith("sha256:")

    d1 = {"b": 2, "a": 1}
    d2 = {"a": 1, "b": 2}
    assert compute_sha256_caid(d1) == compute_sha256_caid(d2)


def test_03_mesh_initialization_parameters() -> None:
    m = AutonomicCircuitBreakerMesh(
        mesh_id="mesh-custom",
        max_consecutive_errors=3,
        error_rate_threshold_bps=2000,
        token_burn_cap_per_min=10000,
        cooldown_seconds=15,
    )
    assert m.mesh_id == "mesh-custom"
    assert m.max_consecutive_errors == 3
    assert m.error_rate_threshold_bps == 2000
    assert m.token_burn_cap_per_min == 10000
    assert m.cooldown_seconds == 15
    m.close()

    # Exact boundary check: cooldown_seconds = 1
    m_b1 = AutonomicCircuitBreakerMesh(cooldown_seconds=1)
    assert m_b1.cooldown_seconds == 1
    m_b1.close()

    with pytest.raises(ValueError, match="mesh_id must be a non-empty string"):
        AutonomicCircuitBreakerMesh(mesh_id="")
    with pytest.raises(ValueError, match="max_consecutive_errors must be a positive integer"):
        AutonomicCircuitBreakerMesh(max_consecutive_errors=0)
    with pytest.raises(ValueError, match="error_rate_threshold_bps must be a positive integer"):
        AutonomicCircuitBreakerMesh(error_rate_threshold_bps=0)
    with pytest.raises(ValueError, match="token_burn_cap_per_min must be a positive integer"):
        AutonomicCircuitBreakerMesh(token_burn_cap_per_min=0)
    with pytest.raises(ValueError, match="cooldown_seconds must be a positive integer"):
        AutonomicCircuitBreakerMesh(cooldown_seconds=0)


def test_04_nominal_closed_state_dispatch(mesh: AutonomicCircuitBreakerMesh) -> None:
    # Target starts closed
    assert mesh.get_state("svc-1") == CIRCUIT_STATE_CLOSED

    permitted, r_before = mesh.before_call("svc-1", now_ms=1000)
    assert permitted is True
    assert r_before.outcome == OUTCOME_PERMITTED
    assert r_before.current_state == CIRCUIT_STATE_CLOSED

    # Call succeeds with 100 tokens consumed
    r_after = mesh.after_call("svc-1", is_error=False, tokens_consumed=100, now_ms=1050)
    assert r_after.current_state == CIRCUIT_STATE_CLOSED
    assert r_after.outcome == OUTCOME_PERMITTED
    assert mesh.get_state("svc-1") == CIRCUIT_STATE_CLOSED

    # Default now_ms handling (testing exact 1000 scaling)
    t_start = int(time.time() * 1000)
    perm_def, r_before_def = mesh.before_call("svc-time-test")
    r_after_def = mesh.after_call("svc-time-test", is_error=False)
    t_end = int(time.time() * 1000)
    assert perm_def is True
    assert t_start <= r_before_def.timestamp_ms <= t_end + 100
    assert t_start <= r_after_def.timestamp_ms <= t_end + 100


def test_05_trip_on_consecutive_errors(mesh: AutonomicCircuitBreakerMesh) -> None:
    # Trigger 5 consecutive errors
    for i in range(MAX_CONSECUTIVE_ERRORS - 1):
        mesh.after_call("svc-err", is_error=True, now_ms=2000 + i * 100)
        assert mesh.get_state("svc-err", now_ms=2000 + i * 100) == CIRCUIT_STATE_CLOSED

    # 5th error trips the circuit open!
    r_trip = mesh.after_call("svc-err", is_error=True, now_ms=2500)
    assert r_trip.current_state == CIRCUIT_STATE_OPEN
    assert r_trip.outcome == OUTCOME_SHORT_CIRCUITED
    assert "Consecutive errors" in r_trip.reason
    assert mesh.get_state("svc-err", now_ms=2500) == CIRCUIT_STATE_OPEN


def test_06_short_circuit_rejection_when_open(mesh: AutonomicCircuitBreakerMesh) -> None:
    # Trip circuit
    for _ in range(MAX_CONSECUTIVE_ERRORS):
        mesh.after_call("svc-dead", is_error=True, now_ms=3000)
    assert mesh.get_state("svc-dead", now_ms=3000) == CIRCUIT_STATE_OPEN

    # Next call fails-closed before execution
    permitted, r_block = mesh.before_call("svc-dead", now_ms=3100)
    assert permitted is False
    assert r_block.outcome == OUTCOME_SHORT_CIRCUITED
    assert r_block.current_state == CIRCUIT_STATE_OPEN


def test_07_trip_on_sliding_window_error_rate(mesh: AutonomicCircuitBreakerMesh) -> None:
    # Execute 10 calls: 8 ok, 2 errors (2 / 10 = 20.00% = 2000 bps > 1500 bps threshold)
    now_ms = 4000
    # Calls 1..7: OK
    for i in range(7):
        mesh.after_call("svc-rate", is_error=False, now_ms=now_ms + i * 100)
    # Call 8: Error
    mesh.after_call("svc-rate", is_error=True, now_ms=now_ms + 800)
    # Call 9: OK
    mesh.after_call("svc-rate", is_error=False, now_ms=now_ms + 900)
    assert mesh.get_state("svc-rate") == CIRCUIT_STATE_CLOSED

    # Call 10: Error (2 errors out of 10 calls = 2000 bps >= 1500 bps)
    r_trip = mesh.after_call("svc-rate", is_error=True, now_ms=now_ms + 1000)
    assert r_trip.current_state == CIRCUIT_STATE_OPEN
    assert "Error rate" in r_trip.reason


def test_08_trip_on_token_burn_cap(mesh: AutonomicCircuitBreakerMesh) -> None:
    now_ms = 5000
    # 2 calls consuming 30,000 tokens each = 60,000 tokens >= 50,000 cap
    mesh.after_call("svc-tokens", is_error=False, tokens_consumed=30000, now_ms=now_ms)
    assert mesh.get_state("svc-tokens") == CIRCUIT_STATE_CLOSED

    r_trip = mesh.after_call("svc-tokens", is_error=False, tokens_consumed=30000, now_ms=now_ms + 1000)
    assert r_trip.current_state == CIRCUIT_STATE_OPEN
    assert "Token burn" in r_trip.reason


def test_09_cooldown_and_half_open_probe_transition(mesh: AutonomicCircuitBreakerMesh) -> None:
    now_ms = 6000
    # Trip circuit at t=6000
    for _ in range(MAX_CONSECUTIVE_ERRORS):
        mesh.after_call("svc-cooldown", is_error=True, now_ms=now_ms)
    assert mesh.get_state("svc-cooldown", now_ms=now_ms) == CIRCUIT_STATE_OPEN

    # 5 seconds elapsed (cooldown is 10s) -> Still OPEN
    assert mesh.get_state("svc-cooldown", now_ms=now_ms + 5000) == CIRCUIT_STATE_OPEN

    # 10 seconds elapsed -> Transitions to HALF_OPEN
    assert mesh.get_state("svc-cooldown", now_ms=now_ms + 10000) == CIRCUIT_STATE_HALF_OPEN

    # Probe call permitted
    permitted, r_probe = mesh.before_call("svc-cooldown", now_ms=now_ms + 10000)
    assert permitted is True
    assert r_probe.outcome == OUTCOME_PROBE_PERMITTED
    assert r_probe.current_state == CIRCUIT_STATE_HALF_OPEN


def test_10_half_open_recovery_success(mesh: AutonomicCircuitBreakerMesh) -> None:
    now_ms = 7000
    for _ in range(MAX_CONSECUTIVE_ERRORS):
        mesh.after_call("svc-recov", is_error=True, now_ms=now_ms)
    assert mesh.get_state("svc-recov", now_ms=now_ms + 10000) == CIRCUIT_STATE_HALF_OPEN

    # Probe call succeeds
    r_success = mesh.after_call("svc-recov", is_error=False, now_ms=now_ms + 10100)
    assert r_success.current_state == CIRCUIT_STATE_CLOSED
    assert "restored to closed state" in r_success.reason
    assert mesh.get_state("svc-recov") == CIRCUIT_STATE_CLOSED


def test_11_half_open_recovery_failure(mesh: AutonomicCircuitBreakerMesh) -> None:
    now_ms = 8000
    for _ in range(MAX_CONSECUTIVE_ERRORS):
        mesh.after_call("svc-failprobe", is_error=True, now_ms=now_ms)
    assert mesh.get_state("svc-failprobe", now_ms=now_ms + 10000) == CIRCUIT_STATE_HALF_OPEN

    # Probe call fails -> trips right back to OPEN
    r_fail = mesh.after_call("svc-failprobe", is_error=True, now_ms=now_ms + 10100)
    assert r_fail.current_state == CIRCUIT_STATE_OPEN
    assert "returned to open state" in r_fail.reason
    assert mesh.get_state("svc-failprobe", now_ms=now_ms + 10100) == CIRCUIT_STATE_OPEN


def test_12_sqlite_persistence_and_queries(temp_db: str) -> None:
    m = AutonomicCircuitBreakerMesh(mesh_id="mesh-sql", db_path=temp_db)
    m.before_call("svc-db", now_ms=1700000000000)
    m.after_call("svc-db", is_error=False, tokens_consumed=50, now_ms=1700000000100)

    # Trigger a state transition so previous_state != current_state
    for i in range(5):
        m.after_call("svc-diff", is_error=True, now_ms=1700000000200 + i * 10)

    records = m.get_ledger_records(limit=10)
    assert len(records) == 7

    # The latest record is the trip event where previous != current
    trip_record = records[0]
    assert trip_record["target_id"] == "svc-diff"
    assert trip_record["previous_state"] == CIRCUIT_STATE_CLOSED
    assert trip_record["current_state"] == CIRCUIT_STATE_OPEN
    assert trip_record["previous_state"] != trip_record["current_state"]
    assert trip_record["outcome"] == OUTCOME_SHORT_CIRCUITED
    assert "Consecutive errors" in trip_record["reason"]
    assert trip_record["receipt_caid"].startswith("sha256:")

    # Earlier nominal records
    nom_after = [r for r in records if r["target_id"] == "svc-db" and r["timestamp_ms"] == 1700000000100][0]
    assert nom_after["previous_state"] == CIRCUIT_STATE_CLOSED
    assert nom_after["current_state"] == CIRCUIT_STATE_CLOSED
    assert nom_after["outcome"] == OUTCOME_PERMITTED
    assert nom_after["reason"] == "Execution processed within nominal thresholds"
    assert nom_after["receipt_caid"].startswith("sha256:")

    nom_before = [r for r in records if r["target_id"] == "svc-db" and r["timestamp_ms"] == 1700000000000][0]
    assert nom_before["previous_state"] == CIRCUIT_STATE_CLOSED
    assert nom_before["current_state"] == CIRCUIT_STATE_CLOSED
    assert nom_before["outcome"] == OUTCOME_PERMITTED
    assert nom_before["reason"] == "Circuit closed: nominal dispatch admitted"
    assert nom_before["receipt_caid"].startswith("sha256:")
    m.close()

    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute("SELECT outcome, current_state FROM circuit_breaker_events_ledger ORDER BY timestamp_ms ASC")
    rows = cur.fetchall()
    assert rows[0][0] == OUTCOME_PERMITTED
    assert rows[0][1] == CIRCUIT_STATE_CLOSED
    conn.close()


def test_13_exact_mutation_boundaries(temp_db: str) -> None:
    # Test configuration constants
    assert MAX_CONSECUTIVE_ERRORS == 5
    assert ERROR_RATE_THRESHOLD_BPS == 1500
    assert TOKEN_BURN_RATE_CAP_PER_MIN == 50000
    assert DEFAULT_COOLDOWN_SECONDS == 30

    m = AutonomicCircuitBreakerMesh(mesh_id="mesh-bound", db_path=temp_db)

    # Input validations
    with pytest.raises(ValueError, match="target_id must be a non-empty string"):
        m.before_call("")
    with pytest.raises(ValueError, match="target_id must be a non-empty string"):
        m.after_call("", is_error=False)
    with pytest.raises(ValueError, match="is_error must be a boolean"):
        m.after_call("t", is_error="yes")  # type: ignore
    with pytest.raises(ValueError, match="tokens_consumed must be a non-negative integer"):
        m.after_call("t", is_error=False, tokens_consumed=-1)

    # Test limit=1 query and dictionary mapping
    m.before_call("target-f", now_ms=1000)
    records = m.get_ledger_records(limit=1)
    assert len(records) == 1
    r = records[0]
    assert r["event_id"].startswith("evt-")
    assert r["target_id"] == "target-f"
    assert r["previous_state"] == CIRCUIT_STATE_CLOSED
    assert r["current_state"] == CIRCUIT_STATE_CLOSED
    assert r["outcome"] == OUTCOME_PERMITTED
    assert "Circuit closed" in r["reason"]
    assert r["receipt_caid"].startswith("sha256:")
    assert r["timestamp_ms"] == 1000

    # Test previous_state != current_state in ledger record
    for i in range(MAX_CONSECUTIVE_ERRORS):
        m.after_call("target-trip", is_error=True, now_ms=2000 + i)
    trip_record = m.get_ledger_records(limit=1)[0]
    assert trip_record["previous_state"] == CIRCUIT_STATE_CLOSED
    assert trip_record["current_state"] == CIRCUIT_STATE_OPEN

    # Test timestamp_ms <= 0 boundary
    valid_args: Dict[str, Any] = {
        "event_id": "evt-01",
        "target_id": "tool-payments-api",
        "previous_state": CIRCUIT_STATE_CLOSED,
        "current_state": CIRCUIT_STATE_OPEN,
        "outcome": OUTCOME_SHORT_CIRCUITED,
        "reason": "Exceeded consecutive errors",
        "receipt_caid": "sha256:11223344556677889900aabbccddeeff11223344556677889900aabbccddeeff",
        "timestamp_ms": 0,
    }
    with pytest.raises(ValueError, match="timestamp_ms must be a positive integer"):
        CircuitBreakerReceipt(**valid_args)

    m.close()


def test_14_wilson_ci_bounds() -> None:
    low, high = compute_wilson_ci_bps(30, 30)
    assert low > 8500
    assert high == 10000
