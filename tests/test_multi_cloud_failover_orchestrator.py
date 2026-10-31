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
tests/test_multi_cloud_failover_orchestrator.py
================================================================================
Verification Suite for MultiCloudFailoverOrchestrator.

Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model.

Tests:
1. Orchestrator policy constants and cluster dispositions.
2. Initialization, quorum validation, primary candidate election, and database state.
3. Immutability of dataclass models and dictionary mappings.
4. Nominal heartbeat evaluation, health maintenance, and epoch millisecond bounds.
5. Automated failover on consecutive heartbeat timeouts and event return value.
6. Automated failover on excessive error rate (>5000 bps).
7. Fail-closed halt when quorum is lost (<N/2 + 1 nodes).
8. Monotonic cluster epoch fencing (rejection of stale epochs).
9. Failover audit receipt generation, zero-float validation, and CAID sealing.
10. SQLite-WAL file-backed persistence and durability across connection lifecycle.
"""

from __future__ import annotations

import dataclasses
import hashlib
import sqlite3
from pathlib import Path
from typing import Any, Dict

import pytest

from src.jcs_canonicalizer import encode_jcs
from src.multi_cloud_failover_orchestrator import (
    CLUSTER_DISPOSITION_FAILOVER_COMMITTED,
    CLUSTER_DISPOSITION_NOMINAL,
    CLUSTER_DISPOSITION_QUORUM_LOST,
    DEFAULT_HEARTBEAT_TIMEOUT_MS,
    MAX_CONSECUTIVE_TIMEOUTS,
    MAX_ERROR_RATE_BPS,
    NODE_STATUS_DEGRADED,
    NODE_STATUS_FENCED,
    NODE_STATUS_HEALTHY,
    NODE_STATUS_UNREACHABLE,
    TOTAL_BASIS_POINTS,
    CloudNodeProfile,
    FailoverEvent,
    HeartbeatTelemetry,
    MultiCloudFailoverOrchestrator,
    MultiCloudFailoverReceipt,
    sha256_jcs_caid,
)


def _assert_zero_floats(obj: Any) -> None:
    """Recursively asserts that no float values exist in the object graph."""
    if isinstance(obj, float):
        raise AssertionError(f"Found float value: {obj}")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _assert_zero_floats(k)
            _assert_zero_floats(v)
    elif isinstance(obj, (list, tuple, set, frozenset)):
        for item in obj:
            _assert_zero_floats(item)


def test_constants_and_defaults() -> None:
    """Evaluates strict policy constants and status enumerations."""
    assert DEFAULT_HEARTBEAT_TIMEOUT_MS == 2000
    assert MAX_CONSECUTIVE_TIMEOUTS == 3
    assert MAX_ERROR_RATE_BPS == 5000
    assert TOTAL_BASIS_POINTS == 10000
    assert NODE_STATUS_HEALTHY == "HEALTHY"
    assert NODE_STATUS_DEGRADED == "DEGRADED"
    assert NODE_STATUS_UNREACHABLE == "UNREACHABLE"
    assert NODE_STATUS_FENCED == "FENCED"
    assert CLUSTER_DISPOSITION_NOMINAL == "NOMINAL_STABLE"
    assert CLUSTER_DISPOSITION_FAILOVER_COMMITTED == "FAILOVER_COMMITTED"
    assert CLUSTER_DISPOSITION_QUORUM_LOST == "QUORUM_LOST"


def test_orchestrator_initialization_and_validation() -> None:
    """Evaluates cluster initialization, minimum quorum requirement, and primary assignment."""
    n1 = CloudNodeProfile("node-aws", "AWS", "us-east-1", "https://aws.example.com", 1, True)
    n2 = CloudNodeProfile("node-gcp", "GCP", "europe-west3", "https://gcp.example.com", 2, False)
    n3 = CloudNodeProfile("node-azure", "AZURE", "eastus2", "https://azure.example.com", 3, False)

    orch = MultiCloudFailoverOrchestrator("cluster-01", [n1, n2, n3])
    assert orch.cluster_id == "cluster-01"
    assert orch.active_primary_node == "node-aws"
    assert orch.active_epoch_id == 1
    assert orch.total_failovers_executed == 0
    assert orch.cluster_disposition == CLUSTER_DISPOSITION_NOMINAL
    assert len(orch.nodes) == 3

    # Verify database initial records for is_active_primary (1 for primary, 0 for standbys)
    cursor = orch._conn.execute(
        "SELECT node_id, is_active_primary FROM cloud_node_registry ORDER BY node_id"
    )
    rows = cursor.fetchall()
    reg_map = {r[0]: r[1] for r in rows}
    assert reg_map["node-aws"] == 1
    assert reg_map["node-gcp"] == 0
    assert reg_map["node-azure"] == 0

    orch.close()

    # Automatic primary election when none flagged
    n1_no_pri = CloudNodeProfile("node-aws", "AWS", "us-east-1", "https://aws.example.com", 1, False)
    orch_auto = MultiCloudFailoverOrchestrator("cluster-auto", [n2, n1_no_pri, n3])
    assert orch_auto.active_primary_node == "node-aws"  # priority 1 elected
    orch_auto.close()

    with pytest.raises(ValueError, match="ERR_EMPTY_CLUSTER_ID"):
        MultiCloudFailoverOrchestrator("", [n1, n2, n3])

    with pytest.raises(ValueError, match="ERR_INSUFFICIENT_NODES"):
        MultiCloudFailoverOrchestrator("cluster-01", [n1, n2])

    with pytest.raises(ValueError, match="ERR_DUPLICATE_NODE_ID"):
        MultiCloudFailoverOrchestrator("cluster-01", [n1, n1, n2])

    n2_dup_pri = CloudNodeProfile("node-gcp", "GCP", "europe-west3", "https://gcp.example.com", 2, True)
    with pytest.raises(ValueError, match="ERR_MULTIPLE_PRIMARIES_SPECIFIED"):
        MultiCloudFailoverOrchestrator("cluster-01", [n1, n2_dup_pri, n3])


def test_frozen_dataclasses_immutability() -> None:
    """Evaluates frozen immutability across all orchestrator dataclasses."""
    profile = CloudNodeProfile("node-1", "AWS", "us-east-1", "https://aws.example.com", 1, True)
    with pytest.raises(dataclasses.FrozenInstanceError):
        profile.priority_rank = 2  # type: ignore
    assert profile.to_dict()["node_id"] == "node-1"

    telem = HeartbeatTelemetry("node-1", 45, False, 100, 1760000000)
    with pytest.raises(dataclasses.FrozenInstanceError):
        telem.latency_ms = 99  # type: ignore
    assert telem.to_dict()["node_id"] == "node-1"

    event = FailoverEvent("fo-1", "node-1", "node-2", 1, 2, "TIMEOUT", 2, True, 1, 1760000000)
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.new_epoch_id = 3  # type: ignore
    assert event.to_dict()["failover_id"] == "fo-1"

    receipt = MultiCloudFailoverReceipt(
        receipt_caid="sha256:abc",
        cluster_disposition=CLUSTER_DISPOSITION_NOMINAL,
        active_epoch_id=1,
        active_primary_node="node-1",
        registered_nodes_count=3,
        healthy_nodes_count=3,
        total_failovers_executed=0,
        active_failover_id=None,
        created_epoch_ms=1760000000,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        receipt.active_epoch_id = 2  # type: ignore
    assert receipt.to_dict()["receipt_caid"] == "sha256:abc"


def test_nominal_heartbeat_and_health_maintenance() -> None:
    """Evaluates healthy heartbeat processing, timestamp magnitude, and state stability."""
    n1 = CloudNodeProfile("node-aws", "AWS", "us-east-1", "https://aws.example.com", 1, True)
    n2 = CloudNodeProfile("node-gcp", "GCP", "europe-west3", "https://gcp.example.com", 2, False)
    n3 = CloudNodeProfile("node-azure", "AZURE", "eastus2", "https://azure.example.com", 3, False)

    orch = MultiCloudFailoverOrchestrator("cluster-nominal", [n1, n2, n3])

    # Timestamp must be in epoch milliseconds
    now_ms = orch._now_epoch_ms()
    assert now_ms > 1_700_000_000_000  # validates epoch milliseconds calculation

    t1 = HeartbeatTelemetry("node-aws", 25, False, 100, now_ms)
    healthy = orch.evaluate_heartbeat(t1)
    assert healthy is True
    assert orch.node_status["node-aws"] == NODE_STATUS_HEALTHY
    assert orch.consecutive_timeouts["node-aws"] == 0
    assert orch.active_epoch_id == 1

    t_unreg = HeartbeatTelemetry("node-unknown", 25, False, 0, now_ms)
    with pytest.raises(ValueError, match="ERR_UNREGISTERED_NODE"):
        orch.evaluate_heartbeat(t_unreg)

    orch.close()


def test_failover_on_consecutive_timeouts() -> None:
    """Evaluates automated failover when primary misses MAX_CONSECUTIVE_TIMEOUTS heartbeats."""
    n1 = CloudNodeProfile("node-aws", "AWS", "us-east-1", "https://aws.example.com", 1, True)
    n2 = CloudNodeProfile("node-gcp", "GCP", "europe-west3", "https://gcp.example.com", 2, False)
    n3 = CloudNodeProfile("node-azure", "AZURE", "eastus2", "https://azure.example.com", 3, False)

    orch = MultiCloudFailoverOrchestrator("cluster-fo-timeout", [n1, n2, n3])

    # 1st timeout
    h1 = orch.evaluate_heartbeat(HeartbeatTelemetry("node-aws", 2000, True, 0, 1760000010))
    assert h1 is True
    assert orch.consecutive_timeouts["node-aws"] == 1
    assert orch.active_primary_node == "node-aws"

    # 2nd timeout
    h2 = orch.evaluate_heartbeat(HeartbeatTelemetry("node-aws", 2000, True, 0, 1760000020))
    assert h2 is True
    assert orch.consecutive_timeouts["node-aws"] == 2

    # 3rd timeout: triggers failover!
    h3 = orch.evaluate_heartbeat(HeartbeatTelemetry("node-aws", 2000, True, 0, 1760000030))
    assert h3 is False
    assert orch.active_primary_node == "node-gcp"  # priority 2 standby elected
    assert orch.active_epoch_id == 2
    assert orch.total_failovers_executed == 1
    assert orch.cluster_disposition == CLUSTER_DISPOSITION_FAILOVER_COMMITTED
    assert orch.node_status["node-aws"] == NODE_STATUS_FENCED
    assert orch.nodes["node-gcp"].is_active_primary is True
    assert orch.nodes["node-aws"].is_active_primary is False
    assert orch.nodes["node-azure"].is_active_primary is False
    assert orch.active_failover_event is not None
    assert orch.active_failover_event.failover_id.startswith("fo-cluster-fo-timeout-1-")
    assert orch.active_failover_event.trigger_reason == "CONSECUTIVE_HEARTBEAT_TIMEOUTS_EXCEEDED"
    assert orch.active_failover_event.prior_primary_node == "node-aws"
    assert orch.active_failover_event.new_primary_node == "node-gcp"
    assert orch.active_failover_event.quorum_confirmed is True
    assert orch.active_failover_event.commit_duration_ms >= 0

    # Test explicit direct return of _trigger_quorum_failover
    ev = orch._trigger_quorum_failover("TEST_DIRECT_TRIGGER")
    assert isinstance(ev, FailoverEvent)
    assert ev.failover_id.startswith("fo-cluster-fo-timeout-2-")
    assert ev.trigger_reason == "TEST_DIRECT_TRIGGER"
    assert ev.quorum_confirmed is True
    assert ev.commit_duration_ms >= 0
    assert orch.active_failover_event == ev

    orch.close()


def test_failover_on_excessive_error_rate() -> None:
    """Evaluates automated failover when primary breaches MAX_ERROR_RATE_BPS (5000 bps)."""
    n1 = CloudNodeProfile("node-aws", "AWS", "us-east-1", "https://aws.example.com", 1, True)
    n2 = CloudNodeProfile("node-gcp", "GCP", "europe-west3", "https://gcp.example.com", 2, False)
    n3 = CloudNodeProfile("node-azure", "AZURE", "eastus2", "https://azure.example.com", 3, False)

    orch = MultiCloudFailoverOrchestrator("cluster-fo-err", [n1, n2, n3])

    t = HeartbeatTelemetry("node-aws", 120, False, 5500, 1760000040)  # 5500 > 5000 bps
    h = orch.evaluate_heartbeat(t)
    assert h is False
    assert orch.active_primary_node == "node-gcp"
    assert orch.active_epoch_id == 2
    assert orch.active_failover_event is not None
    assert orch.active_failover_event.trigger_reason == "EXCESSIVE_ERROR_RATE_EXCEEDED"

    orch.close()


def test_quorum_loss_prevention() -> None:
    """Evaluates fail-closed halt when healthy node count drops below quorum (< N/2 + 1)."""
    n1 = CloudNodeProfile("node-aws", "AWS", "us-east-1", "https://aws.example.com", 1, True)
    n2 = CloudNodeProfile("node-gcp", "GCP", "europe-west3", "https://gcp.example.com", 2, False)
    n3 = CloudNodeProfile("node-azure", "AZURE", "eastus2", "https://azure.example.com", 3, False)

    orch = MultiCloudFailoverOrchestrator("cluster-quorum-loss", [n1, n2, n3])

    # Mark node-gcp degraded/unreachable first
    orch.evaluate_heartbeat(HeartbeatTelemetry("node-gcp", 100, False, 6000, 1760000050))
    assert orch.node_status["node-gcp"] == NODE_STATUS_DEGRADED

    # Mark node-azure degraded/unreachable as well
    orch.evaluate_heartbeat(HeartbeatTelemetry("node-azure", 100, False, 6000, 1760000051))
    assert orch.node_status["node-azure"] == NODE_STATUS_DEGRADED

    # Now primary node-aws fails, but no healthy standbys exist (0 < 2 required quorum)
    with pytest.raises(RuntimeError, match="ERR_QUORUM_LOST"):
        orch.evaluate_heartbeat(HeartbeatTelemetry("node-aws", 100, False, 6000, 1760000052))

    assert orch.cluster_disposition == CLUSTER_DISPOSITION_QUORUM_LOST
    orch.close()


def test_monotonic_epoch_fencing() -> None:
    """Evaluates anti-split-brain epoch fencing against stale and future epochs."""
    n1 = CloudNodeProfile("node-aws", "AWS", "us-east-1", "https://aws.example.com", 1, True)
    n2 = CloudNodeProfile("node-gcp", "GCP", "europe-west3", "https://gcp.example.com", 2, False)
    n3 = CloudNodeProfile("node-azure", "AZURE", "eastus2", "https://azure.example.com", 3, False)

    orch = MultiCloudFailoverOrchestrator("cluster-epoch", [n1, n2, n3])

    # Active epoch is 1
    assert orch.validate_mutation_epoch(1) is True

    with pytest.raises(ValueError, match="ERR_STALE_CLUSTER_EPOCH"):
        orch.validate_mutation_epoch(0)

    with pytest.raises(ValueError, match="ERR_FUTURE_CLUSTER_EPOCH"):
        orch.validate_mutation_epoch(2)

    # Trigger failover to epoch 2
    orch.evaluate_heartbeat(HeartbeatTelemetry("node-aws", 100, False, 6000, 1760000060))
    assert orch.active_epoch_id == 2

    # Now epoch 1 must be rejected as stale
    with pytest.raises(ValueError, match="ERR_STALE_CLUSTER_EPOCH"):
        orch.validate_mutation_epoch(1)

    assert orch.validate_mutation_epoch(2) is True

    orch.close()


def test_failover_receipt_zero_floats_and_caid() -> None:
    """Evaluates receipt generation, RFC 8785 canonicalization, and zero-float invariant."""
    n1 = CloudNodeProfile("node-aws", "AWS", "us-east-1", "https://aws.example.com", 1, True)
    n2 = CloudNodeProfile("node-gcp", "GCP", "europe-west3", "https://gcp.example.com", 2, False)
    n3 = CloudNodeProfile("node-azure", "AZURE", "eastus2", "https://azure.example.com", 3, False)

    orch = MultiCloudFailoverOrchestrator("cluster-receipt", [n1, n2, n3])

    receipt = orch.generate_failover_receipt()
    assert isinstance(receipt, MultiCloudFailoverReceipt)
    assert receipt.receipt_caid.startswith("sha256:")
    assert receipt.cluster_disposition == CLUSTER_DISPOSITION_NOMINAL
    assert receipt.active_epoch_id == 1
    assert receipt.active_primary_node == "node-aws"
    assert receipt.registered_nodes_count == 3
    assert receipt.healthy_nodes_count == 3
    assert receipt.total_failovers_executed == 0
    assert receipt.active_failover_id is None
    assert receipt.created_epoch_ms > 1_700_000_000_000

    _assert_zero_floats(receipt.to_dict())

    # Re-verify CAID digest
    body = {
        "active_epoch_id": receipt.active_epoch_id,
        "active_failover_id": receipt.active_failover_id,
        "active_primary_node": receipt.active_primary_node,
        "cluster_disposition": receipt.cluster_disposition,
        "created_epoch_ms": receipt.created_epoch_ms,
        "healthy_nodes_count": receipt.healthy_nodes_count,
        "registered_nodes_count": receipt.registered_nodes_count,
        "total_failovers_executed": receipt.total_failovers_executed,
    }
    recomputed_caid = f"sha256:{hashlib.sha256(encode_jcs(body)).hexdigest()}"
    assert receipt.receipt_caid == recomputed_caid

    # Verify sha256_jcs_caid helper on bytes and str
    assert sha256_jcs_caid(b"test-bytes").startswith("sha256:")
    assert sha256_jcs_caid("test-str").startswith("sha256:")

    orch.close()


def test_file_backed_sqlite_wal_persistence(tmp_path: Path) -> None:
    """Evaluates file-backed SQLite-WAL ledger initialization, persistence, and recovery."""
    db_file = tmp_path / "failover_test.db"

    n1 = CloudNodeProfile("node-aws", "AWS", "us-east-1", "https://aws.example.com", 1, True)
    n2 = CloudNodeProfile("node-gcp", "GCP", "europe-west3", "https://gcp.example.com", 2, False)
    n3 = CloudNodeProfile("node-azure", "AZURE", "eastus2", "https://azure.example.com", 3, False)

    orch = MultiCloudFailoverOrchestrator(
        "cluster-wal",
        [n1, n2, n3],
        db_path=str(db_file),
    )

    # Verify WAL journal mode
    cursor = orch._conn.execute("PRAGMA journal_mode;")
    mode = cursor.fetchone()[0]
    assert mode.lower() == "wal"

    # Trigger failover
    orch.evaluate_heartbeat(HeartbeatTelemetry("node-aws", 100, False, 6000, 1760000070))
    event = orch.active_failover_event
    assert event is not None
    assert event.commit_duration_ms >= 0

    orch.close()

    # Reopen file directly and verify ledger state
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()

    cur.execute("SELECT node_id, is_active_primary FROM cloud_node_registry WHERE is_active_primary = 1;")
    row = cur.fetchone()
    assert row[0] == "node-gcp"
    assert row[1] == 1

    cur.execute(
        "SELECT failover_id, prior_primary_node, new_primary_node, new_epoch_id, quorum_confirmed FROM failover_events_ledger;"
    )
    fo_row = cur.fetchone()
    assert fo_row[0] == event.failover_id
    assert fo_row[1] == "node-aws"
    assert fo_row[2] == "node-gcp"
    assert fo_row[3] == 2
    assert fo_row[4] == 1

    conn.close()
