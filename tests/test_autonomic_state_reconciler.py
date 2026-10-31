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
tests/test_autonomic_state_reconciler.py
================================================================================
Verification Suite for AutonomicStateReconciler.

Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model.

Tests:
1. DesiredStateSpec dataclass validations, defaults, boundaries, and frozen immutability.
2. ObservedStateObservation dataclass validations, boundaries, and frozen immutability.
3. ReconciliationReceipt dataclass validations, boundaries, and frozen immutability.
4. CAID generation across str, bytes, and dictionary payloads.
5. Reconciler initialization with custom/default parameters and parameter validation.
6. Epoch reset and remediation budget replenishment.
7. Discrepancy determination and deterministic remediation action mapping.
8. Component reconciliation with budget consumption and budget exhaustion halting.
9. Unsupported drift detection and emergency linestop handling.
10. Batch reconciliation cycles with missing observation fallbacks.
11. SQLite-WAL append-only persistence and receipt retrieval.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
import sqlite3
import time
from typing import Any, Dict, List

import pytest

from src.autonomic_state_reconciler import (
    ACTION_CHECKPOINT_WAL,
    ACTION_DRAIN_CANARY,
    ACTION_EMERGENCY_HALT,
    ACTION_NONE,
    ACTION_REAPPLY_EBPF,
    ACTION_RECLAIM_FD,
    ACTION_ROTATE_LEASE,
    MAX_REMEDIATIONS_PER_EPOCH,
    STATUS_BUDGET_EXHAUSTED,
    STATUS_CONVERGED,
    STATUS_REMEDIATED,
    STATUS_UNSUPPORTED_DRIFT,
    AutonomicStateReconciler,
    DesiredStateSpec,
    ObservedStateObservation,
    ReconciliationReceipt,
    compute_sha256_caid,
)


@pytest.fixture
def temp_db(tmp_path: Path) -> str:
    return str(tmp_path / "test_autonomic_reconciler.db")


@pytest.fixture
def reconciler() -> AutonomicStateReconciler:
    return AutonomicStateReconciler(
        reconciler_id="test-reconciler-01",
        max_remediations_per_epoch=5,
        current_epoch_id="epoch-100",
    )


def test_01_desired_state_spec_validations() -> None:
    # Valid spec with defaults
    spec = DesiredStateSpec(component_id="ebpf_socket_guard", expected_typestate="FILTER_ACTIVE")
    assert spec.component_id == "ebpf_socket_guard"
    assert spec.expected_typestate == "FILTER_ACTIVE"
    assert spec.max_allowable_drift_bps == 0
    assert spec.parameters == {}

    # Exact boundary validation
    spec_b = DesiredStateSpec(
        component_id="comp-1",
        expected_typestate="STATE_OK",
        max_allowable_drift_bps=0,
    )
    assert spec_b.max_allowable_drift_bps == 0

    # Frozen immutability
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.expected_typestate = "MUTATED"  # type: ignore

    # Invalid fields
    with pytest.raises(ValueError, match="component_id must be a non-empty string"):
        DesiredStateSpec(component_id="", expected_typestate="STATE_OK")
    with pytest.raises(ValueError, match="component_id must be a non-empty string"):
        DesiredStateSpec(component_id=None, expected_typestate="STATE_OK")  # type: ignore
    with pytest.raises(ValueError, match="expected_typestate must be a non-empty string"):
        DesiredStateSpec(component_id="comp-1", expected_typestate="")
    with pytest.raises(ValueError, match="expected_typestate must be a non-empty string"):
        DesiredStateSpec(component_id="comp-1", expected_typestate=None)  # type: ignore
    with pytest.raises(ValueError, match="max_allowable_drift_bps must be a non-negative integer"):
        DesiredStateSpec(component_id="comp-1", expected_typestate="STATE_OK", max_allowable_drift_bps=-1)
    with pytest.raises(ValueError, match="max_allowable_drift_bps must be a non-negative integer"):
        DesiredStateSpec(component_id="comp-1", expected_typestate="STATE_OK", max_allowable_drift_bps=10.5)  # type: ignore


def test_02_observed_state_observation_validations() -> None:
    # Valid observation with defaults
    obs = ObservedStateObservation(component_id="ebpf_socket_guard", observed_typestate="FILTER_ACTIVE")
    assert obs.component_id == "ebpf_socket_guard"
    assert obs.observed_typestate == "FILTER_ACTIVE"
    assert obs.drift_bps == 0
    assert obs.is_healthy is True
    assert obs.details == {}

    # Exact boundary check
    obs_b = ObservedStateObservation(
        component_id="comp-1",
        observed_typestate="STATE_OK",
        drift_bps=0,
    )
    assert obs_b.drift_bps == 0

    # Frozen immutability
    with pytest.raises(dataclasses.FrozenInstanceError):
        obs.observed_typestate = "MUTATED"  # type: ignore

    # Invalid fields
    with pytest.raises(ValueError, match="component_id must be a non-empty string"):
        ObservedStateObservation(component_id="", observed_typestate="STATE_OK")
    with pytest.raises(ValueError, match="component_id must be a non-empty string"):
        ObservedStateObservation(component_id=None, observed_typestate="STATE_OK")  # type: ignore
    with pytest.raises(ValueError, match="observed_typestate must be a non-empty string"):
        ObservedStateObservation(component_id="comp-1", observed_typestate="")
    with pytest.raises(ValueError, match="observed_typestate must be a non-empty string"):
        ObservedStateObservation(component_id="comp-1", observed_typestate=None)  # type: ignore
    with pytest.raises(ValueError, match="drift_bps must be a non-negative integer"):
        ObservedStateObservation(component_id="comp-1", observed_typestate="STATE_OK", drift_bps=-1)
    with pytest.raises(ValueError, match="drift_bps must be a non-negative integer"):
        ObservedStateObservation(component_id="comp-1", observed_typestate="STATE_OK", drift_bps=5.5)  # type: ignore
    with pytest.raises(ValueError, match="is_healthy must be a boolean"):
        ObservedStateObservation(component_id="comp-1", observed_typestate="STATE_OK", is_healthy="not_bool")  # type: ignore


def test_03_reconciliation_receipt_validations() -> None:
    valid_args: Dict[str, Any] = {
        "cycle_id": "cycle-001",
        "epoch_id": "epoch-001",
        "component_id": "comp-001",
        "status": STATUS_CONVERGED,
        "action_taken": ACTION_NONE,
        "budget_remaining": 5,
        "receipt_caid": "sha256:" + "0" * 64,
        "timestamp_ms": 1700000000000,
    }

    receipt = ReconciliationReceipt(**valid_args)
    assert receipt.cycle_id == "cycle-001"

    # Exact boundary validations
    receipt_b0 = ReconciliationReceipt(**dict(valid_args, budget_remaining=0))
    assert receipt_b0.budget_remaining == 0

    receipt_ts1 = ReconciliationReceipt(**dict(valid_args, timestamp_ms=1))
    assert receipt_ts1.timestamp_ms == 1

    # Frozen immutability
    with pytest.raises(dataclasses.FrozenInstanceError):
        receipt.status = "MUTATED"  # type: ignore

    # Invalid fields
    with pytest.raises(ValueError, match="cycle_id must be a non-empty string"):
        ReconciliationReceipt(**dict(valid_args, cycle_id=""))
    with pytest.raises(ValueError, match="epoch_id must be a non-empty string"):
        ReconciliationReceipt(**dict(valid_args, epoch_id=""))
    with pytest.raises(ValueError, match="component_id must be a non-empty string"):
        ReconciliationReceipt(**dict(valid_args, component_id=""))
    with pytest.raises(ValueError, match="status must be a non-empty string"):
        ReconciliationReceipt(**dict(valid_args, status=""))
    with pytest.raises(ValueError, match="action_taken must be a non-empty string"):
        ReconciliationReceipt(**dict(valid_args, action_taken=""))
    with pytest.raises(ValueError, match="budget_remaining must be a non-negative integer"):
        ReconciliationReceipt(**dict(valid_args, budget_remaining=-1))
    with pytest.raises(ValueError, match="budget_remaining must be a non-negative integer"):
        ReconciliationReceipt(**dict(valid_args, budget_remaining=2.5))  # type: ignore
    with pytest.raises(ValueError, match="receipt_caid must be a valid sha256 prefix string"):
        ReconciliationReceipt(**dict(valid_args, receipt_caid="bad_caid"))
    with pytest.raises(ValueError, match="receipt_caid must be a valid sha256 prefix string"):
        ReconciliationReceipt(**dict(valid_args, receipt_caid=""))
    with pytest.raises(ValueError, match="timestamp_ms must be a positive integer"):
        ReconciliationReceipt(**dict(valid_args, timestamp_ms=0))
    with pytest.raises(ValueError, match="timestamp_ms must be a positive integer"):
        ReconciliationReceipt(**dict(valid_args, timestamp_ms=-1))
    with pytest.raises(ValueError, match="timestamp_ms must be a positive integer"):
        ReconciliationReceipt(**dict(valid_args, timestamp_ms=10.5))  # type: ignore


def test_04_caid_computation() -> None:
    c_bytes = compute_sha256_caid(b"reconciler_payload")
    c_str = compute_sha256_caid("reconciler_payload")
    c_dict = compute_sha256_caid({"status": "RECONCILED"})

    assert c_bytes.startswith("sha256:")
    assert c_str.startswith("sha256:")
    assert c_dict.startswith("sha256:")
    assert c_bytes == c_str


def test_05_reconciler_initialization() -> None:
    # Default initialization
    rec = AutonomicStateReconciler()
    assert rec.reconciler_id == "reconciler-primary"
    assert rec.current_epoch_id == "epoch-001"
    assert rec.max_remediations_per_epoch == MAX_REMEDIATIONS_PER_EPOCH
    assert rec.remediation_budget_remaining == MAX_REMEDIATIONS_PER_EPOCH
    rec.close()

    # Exact boundary check (kills boundary mutant max_remediations_per_epoch <= 1)
    rec_b1 = AutonomicStateReconciler(max_remediations_per_epoch=1)
    assert rec_b1.max_remediations_per_epoch == 1
    assert rec_b1.remediation_budget_remaining == 1
    rec_b1.close()

    # Invalid arguments
    with pytest.raises(ValueError, match="reconciler_id must be a non-empty string"):
        AutonomicStateReconciler(reconciler_id="")
    with pytest.raises(ValueError, match="reconciler_id must be a non-empty string"):
        AutonomicStateReconciler(reconciler_id=None)  # type: ignore
    with pytest.raises(ValueError, match="current_epoch_id must be a non-empty string"):
        AutonomicStateReconciler(current_epoch_id="")
    with pytest.raises(ValueError, match="max_remediations_per_epoch must be a positive integer"):
        AutonomicStateReconciler(max_remediations_per_epoch=0)
    with pytest.raises(ValueError, match="max_remediations_per_epoch must be a positive integer"):
        AutonomicStateReconciler(max_remediations_per_epoch=-1)
    with pytest.raises(ValueError, match="max_remediations_per_epoch must be a positive integer"):
        AutonomicStateReconciler(max_remediations_per_epoch=5.5)  # type: ignore


def test_06_epoch_reset(reconciler: AutonomicStateReconciler) -> None:
    # Consume budget
    reconciler.remediation_budget_remaining = 1
    reconciler.reset_epoch("epoch-200")
    assert reconciler.current_epoch_id == "epoch-200"
    assert reconciler.remediation_budget_remaining == reconciler.max_remediations_per_epoch

    # Invalid new epoch
    with pytest.raises(ValueError, match="new_epoch_id must be a non-empty string"):
        reconciler.reset_epoch("")
    with pytest.raises(ValueError, match="new_epoch_id must be a non-empty string"):
        reconciler.reset_epoch(None)  # type: ignore


def test_07_determine_remediation_mapping(reconciler: AutonomicStateReconciler) -> None:
    # Component mismatch
    spec = DesiredStateSpec("comp_a", "STATE_OK")
    obs = ObservedStateObservation("comp_b", "STATE_OK")
    with pytest.raises(ValueError, match="Component mismatch"):
        reconciler.determine_remediation(spec, obs)

    # Converged (no action)
    spec_ok = DesiredStateSpec("comp_a", "STATE_OK", max_allowable_drift_bps=100)
    obs_ok = ObservedStateObservation("comp_a", "STATE_OK", drift_bps=50, is_healthy=True)
    needs, action = reconciler.determine_remediation(spec_ok, obs_ok)
    assert needs is False
    assert action == ACTION_NONE

    # Mapping rules
    test_cases = [
        ("ebpf_filter_rule", ACTION_REAPPLY_EBPF),
        ("socket_interceptor", ACTION_REAPPLY_EBPF),
        ("ingress_canary", ACTION_DRAIN_CANARY),
        ("canary_traffic_gate", ACTION_DRAIN_CANARY),
        ("sqlite_wal_checkpoint", ACTION_CHECKPOINT_WAL),
        ("database_core", ACTION_CHECKPOINT_WAL),
        ("credential_lease", ACTION_ROTATE_LEASE),
        ("token_auth", ACTION_ROTATE_LEASE),
        ("fd_leak_monitor", ACTION_RECLAIM_FD),
        ("descriptor_pool", ACTION_RECLAIM_FD),
        ("unknown_custom_device", ACTION_EMERGENCY_HALT),
    ]

    for comp_name, expected_action in test_cases:
        s = DesiredStateSpec(comp_name, "EXPECTED")
        o = ObservedStateObservation(comp_name, "DRIFTED", drift_bps=1000)
        n, act = reconciler.determine_remediation(s, o)
        assert n is True
        assert act == expected_action


def test_08_reconcile_component_and_budget_exhaustion(reconciler: AutonomicStateReconciler) -> None:
    # 1. Nominal convergence
    spec_ok = DesiredStateSpec("ebpf_guard", "ACTIVE")
    obs_ok = ObservedStateObservation("ebpf_guard", "ACTIVE", drift_bps=0, is_healthy=True)
    r_ok = reconciler.reconcile_component(spec_ok, obs_ok, now_ms=1700000001000)
    assert r_ok.status == STATUS_CONVERGED
    assert r_ok.action_taken == ACTION_NONE
    assert r_ok.budget_remaining == 5

    # 2. Remediation execution
    obs_drift = ObservedStateObservation("ebpf_guard", "DRIFTED", drift_bps=100)
    r_rem = reconciler.reconcile_component(spec_ok, obs_drift, now_ms=1700000002000)
    assert r_rem.status == STATUS_REMEDIATED
    assert r_rem.action_taken == ACTION_REAPPLY_EBPF
    assert r_rem.budget_remaining == 4

    # 3. Exhaust the remaining 4 budget units
    for i in range(4):
        rec_step = reconciler.reconcile_component(spec_ok, obs_drift)
        assert rec_step.status == STATUS_REMEDIATED

    assert reconciler.remediation_budget_remaining == 0

    # 4. Next remediation trips budget exhaustion halt
    r_exhausted = reconciler.reconcile_component(spec_ok, obs_drift)
    assert r_exhausted.status == STATUS_BUDGET_EXHAUSTED
    assert r_exhausted.action_taken == ACTION_EMERGENCY_HALT
    assert r_exhausted.budget_remaining == 0


def test_09_unsupported_drift_handling(reconciler: AutonomicStateReconciler) -> None:
    # Component with unsupported name pattern -> ACTION_EMERGENCY_HALT
    spec = DesiredStateSpec("mysterious_subsystem", "STATE_OK")
    obs = ObservedStateObservation("mysterious_subsystem", "FAULTY", drift_bps=5000)

    receipt = reconciler.reconcile_component(spec, obs)
    assert receipt.status == STATUS_UNSUPPORTED_DRIFT
    assert receipt.action_taken == ACTION_EMERGENCY_HALT


def test_10_batch_reconciliation_cycle(reconciler: AutonomicStateReconciler) -> None:
    specs = [
        DesiredStateSpec("ebpf_socket", "FILTER_ACTIVE"),
        DesiredStateSpec("canary_ingress", "WEIGHT_10"),
        DesiredStateSpec("database_wal", "CHECKPOINT_OK"),
    ]

    # database_wal is missing from observations
    observations = [
        ObservedStateObservation("ebpf_socket", "FILTER_ACTIVE", drift_bps=0),
        ObservedStateObservation("canary_ingress", "WEIGHT_99", drift_bps=8900),
    ]

    receipts = reconciler.run_reconciliation_cycle(specs, observations, now_ms=1700000010000)
    assert len(receipts) == 3

    # ebpf_socket: converged
    assert receipts[0].component_id == "ebpf_socket"
    assert receipts[0].status == STATUS_CONVERGED

    # canary_ingress: remediated
    assert receipts[1].component_id == "canary_ingress"
    assert receipts[1].status == STATUS_REMEDIATED
    assert receipts[1].action_taken == ACTION_DRAIN_CANARY

    # database_wal: missing observation treated as degraded -> remediated
    assert receipts[2].component_id == "database_wal"
    assert receipts[2].status == STATUS_REMEDIATED
    assert receipts[2].action_taken == ACTION_CHECKPOINT_WAL


def test_11_sqlite_persistence_and_receipt_retrieval(temp_db: str) -> None:
    rec = AutonomicStateReconciler(db_path=temp_db, reconciler_id="rec-db-test")
    spec = DesiredStateSpec("ebpf_socket", "FILTER_ACTIVE")
    obs = ObservedStateObservation("ebpf_socket", "FILTER_ACTIVE", drift_bps=0)

    t_now = int(time.time() * 1000)
    receipt = rec.reconcile_component(spec, obs)

    # Verify default timestamp generation
    assert receipt.timestamp_ms >= t_now
    assert receipt.timestamp_ms <= int(time.time() * 1000) + 5000
    assert receipt.timestamp_ms > 1_000_000_000_000

    # Retrieve ledger receipts
    items = rec.get_ledger_receipts(limit=10)
    assert len(items) == 1
    assert items[0]["cycle_id"] == receipt.cycle_id
    assert items[0]["component_id"] == "ebpf_socket"
    assert items[0]["status"] == STATUS_CONVERGED
    assert items[0]["receipt_caid"] == receipt.receipt_caid

    rec.close()

    # Verify direct SQLite schema
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute("SELECT status, action_taken, budget_remaining FROM autonomic_reconciler_ledger WHERE cycle_id = ?", (receipt.cycle_id,))
    row = cur.fetchone()
    assert row is not None
    assert row[0] == STATUS_CONVERGED
    assert row[1] == ACTION_NONE
    assert row[2] == MAX_REMEDIATIONS_PER_EPOCH
    conn.close()
