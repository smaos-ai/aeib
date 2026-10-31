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
tests/test_multi_region_canary_ingress.py
================================================================================
Verification Suite for MultiRegionCanaryIngressController.

Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model.

Tests:
1. Controller initialization, defaults, frozen dataclasses, and boundary validation.
2. Deterministic traffic splitting (canary vs production) and ledger auditing.
3. Live eBPF telemetry nominal ingestion and metric tracking.
4. Region mismatch fail-closed interception.
5. Automated rollback on unauthorized socket egress and ledger verification.
6. Automated rollback on excessive trajectory drift (>4000 bps).
7. Automated rollback on excessive blast radius (>3000 bps).
8. Automated rollback on excessive network jitter (>4800 bps).
9. Verification receipt RFC 8785 deterministic JCS, zero-float validation, and arithmetic checks.
10. SQLite-WAL file-backed edge persistence and durability across re-opening.
"""

from __future__ import annotations

import dataclasses
import hashlib
import sqlite3
from pathlib import Path
from typing import Any, Dict

import pytest

from src.jcs_canonicalizer import encode_jcs
from src.multi_region_canary_ingress import (
    DEFAULT_CANARY_WEIGHT_BPS,
    DEFAULT_PRODUCTION_WEIGHT_BPS,
    MAX_BLAST_RADIUS_BPS,
    MAX_JITTER_BPS,
    MAX_TRAJECTORY_DRIFT_BPS,
    STATUS_HEALTHY_PROGRESSION,
    STATUS_PINNED_STABLE,
    STATUS_ROLLED_BACK,
    TARGET_CANARY,
    TARGET_PRODUCTION,
    TOTAL_WEIGHT_BPS,
    CanaryRollbackEvent,
    CanaryRoutingDecision,
    CanaryVerificationReceipt,
    EbpfSocketTelemetry,
    MultiRegionCanaryIngressController,
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


def test_canary_ingress_constants_and_defaults() -> None:
    """Evaluates strict policy constants and default configurations."""
    assert DEFAULT_CANARY_WEIGHT_BPS == 1000
    assert DEFAULT_PRODUCTION_WEIGHT_BPS == 9000
    assert TOTAL_WEIGHT_BPS == 10000
    assert MAX_TRAJECTORY_DRIFT_BPS == 4000
    assert MAX_BLAST_RADIUS_BPS == 3000
    assert MAX_JITTER_BPS == 4800
    assert STATUS_HEALTHY_PROGRESSION == "HEALTHY_PROGRESSION"
    assert STATUS_ROLLED_BACK == "ROLLED_BACK"
    assert STATUS_PINNED_STABLE == "PINNED_STABLE"
    assert TARGET_CANARY == "CANARY"
    assert TARGET_PRODUCTION == "PRODUCTION"


def test_canary_ingress_initialization_and_validation() -> None:
    """Evaluates controller initialization, defaults, and parameter boundary checks."""
    ctrl = MultiRegionCanaryIngressController(
        region="us-east-1",
        canary_weight_bps=1200,
        max_drift_bps=3800,
        max_blast_radius_bps=2800,
        max_jitter_bps=4500,
    )
    assert ctrl.region == "us-east-1"
    assert ctrl.initial_canary_weight_bps == 1200
    assert ctrl.current_canary_weight_bps == 1200
    assert ctrl.max_drift_bps == 3800
    assert ctrl.max_blast_radius_bps == 2800
    assert ctrl.max_jitter_bps == 4500
    assert ctrl.status == STATUS_HEALTHY_PROGRESSION
    assert ctrl.active_rollback_event is None
    assert ctrl.total_requests_routed == 0
    assert ctrl.canary_requests_routed == 0
    assert ctrl.production_requests_routed == 0
    assert ctrl.telemetry_events_count == 0
    assert ctrl.max_drift_observed == 0
    assert ctrl.max_blast_radius_observed == 0
    assert ctrl.max_jitter_observed == 0
    ctrl.close()

    ctrl2 = MultiRegionCanaryIngressController(region="us-east-1", canary_weight_bps=1500)
    assert ctrl2.current_canary_weight_bps == 1500
    ctrl2.close()

    with pytest.raises(ValueError, match="ERR_EMPTY_REGION"):
        MultiRegionCanaryIngressController(region="")

    with pytest.raises(ValueError, match="ERR_INVALID_CANARY_WEIGHT"):
        MultiRegionCanaryIngressController(region="us-east-1", canary_weight_bps=-1)

    with pytest.raises(ValueError, match="ERR_INVALID_CANARY_WEIGHT"):
        MultiRegionCanaryIngressController(region="us-east-1", canary_weight_bps=10001)


def test_frozen_dataclasses_immutability() -> None:
    """Evaluates that all telemetry, routing, and receipt dataclasses are frozen."""
    decision = CanaryRoutingDecision(
        request_id="r1",
        region="us-east-1",
        destination_target=TARGET_PRODUCTION,
        routing_hash_value=5000,
        canary_weight_bps=1000,
        assigned_endpoint="prod-gateway",
        timestamp_epoch_ms=100,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.routing_hash_value = 9999  # type: ignore

    assert decision.to_dict()["request_id"] == "r1"

    telem = EbpfSocketTelemetry(
        event_id="e1",
        pod_id="p1",
        region="us-east-1",
        function_name="sys_enter_connect",
        target_host="10.0.0.1",
        target_port=15001,
        observed_latency_ms=10,
        observed_jitter_bps=500,
        trajectory_drift_bps=200,
        blast_radius_bps=100,
        is_unauthorized_egress=False,
        timestamp_epoch_ms=100,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        telem.observed_latency_ms = 999  # type: ignore

    assert telem.to_dict()["event_id"] == "e1"

    rb = CanaryRollbackEvent(
        rollback_id="rb1",
        region="us-east-1",
        trigger_reason="TEST",
        violating_metric="drift",
        metric_value_bps=5000,
        threshold_value_bps=4000,
        prior_canary_weight_bps=1000,
        new_canary_weight_bps=0,
        db_commit_duration_ms=1,
        timestamp_epoch_ms=100,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        rb.new_canary_weight_bps = 500  # type: ignore

    assert rb.to_dict()["rollback_id"] == "rb1"


def test_deterministic_traffic_splitting_and_weight_distribution() -> None:
    """Evaluates deterministic hash routing across production and canary."""
    ctrl = MultiRegionCanaryIngressController(region="eu-west-1", canary_weight_bps=5000)

    decisions = []
    for i in range(100):
        req_id = f"req-{i:03d}"
        decision = ctrl.route_request(req_id)
        assert isinstance(decision, CanaryRoutingDecision)
        assert decision.region == "eu-west-1"
        assert decision.request_id == req_id
        assert 0 <= decision.routing_hash_value < TOTAL_WEIGHT_BPS
        decisions.append(decision)

    assert ctrl.total_requests_routed == 100
    assert ctrl.canary_requests_routed + ctrl.production_requests_routed == 100
    assert ctrl.canary_requests_routed > 0
    assert ctrl.production_requests_routed > 0

    with pytest.raises(ValueError, match="ERR_EMPTY_REQUEST_ID"):
        ctrl.route_request("")

    ctrl.close()


def test_ebpf_telemetry_nominal_progression() -> None:
    """Evaluates nominal telemetry ingestion without threshold violations."""
    ctrl = MultiRegionCanaryIngressController(region="us-west-2")

    telem1 = EbpfSocketTelemetry(
        event_id="evt-001",
        pod_id="pod-canary-01",
        region="us-west-2",
        function_name="sys_enter_connect",
        target_host="10.96.0.10",
        target_port=15001,
        observed_latency_ms=12,
        observed_jitter_bps=1200,
        trajectory_drift_bps=800,
        blast_radius_bps=1500,
        is_unauthorized_egress=False,
        timestamp_epoch_ms=1760000000,
    )

    healthy, rb_event = ctrl.ingest_ebpf_telemetry(telem1)
    assert healthy is True
    assert rb_event is None
    assert ctrl.telemetry_events_count == 1
    assert ctrl.max_drift_observed == 800
    assert ctrl.max_blast_radius_observed == 1500
    assert ctrl.max_jitter_observed == 1200
    assert ctrl.status == STATUS_HEALTHY_PROGRESSION

    # Verify SQL record for nominal telemetry has is_unauthorized_egress == 0
    cursor = ctrl._conn.execute(
        "SELECT is_unauthorized_egress FROM canary_telemetry_ledger WHERE event_id = ?",
        ("evt-001",),
    )
    assert cursor.fetchone()[0] == 0

    ctrl.close()


def test_ebpf_telemetry_region_mismatch() -> None:
    """Evaluates fail-closed rejection on cross-region telemetry contamination."""
    ctrl = MultiRegionCanaryIngressController(region="us-east-1")
    telem = EbpfSocketTelemetry(
        event_id="evt-mismatch",
        pod_id="pod-01",
        region="eu-central-1",
        function_name="sys_enter_connect",
        target_host="10.96.0.10",
        target_port=15001,
        observed_latency_ms=10,
        observed_jitter_bps=500,
        trajectory_drift_bps=200,
        blast_radius_bps=100,
        is_unauthorized_egress=False,
        timestamp_epoch_ms=1760000000,
    )

    with pytest.raises(ValueError, match="ERR_REGION_MISMATCH"):
        ctrl.ingest_ebpf_telemetry(telem)

    ctrl.close()


def test_automated_rollback_on_unauthorized_egress() -> None:
    """Evaluates immediate fail-closed rollback on un-blinded unauthorized socket bypass."""
    ctrl = MultiRegionCanaryIngressController(region="eu-central-1", canary_weight_bps=2000)

    telem = EbpfSocketTelemetry(
        event_id="evt-unauth-01",
        pod_id="pod-canary-02",
        region="eu-central-1",
        function_name="sys_enter_connect",
        target_host="198.51.100.25",  # unauthorized direct external IP bypass
        target_port=443,
        observed_latency_ms=45,
        observed_jitter_bps=600,
        trajectory_drift_bps=100,
        blast_radius_bps=200,
        is_unauthorized_egress=True,
        timestamp_epoch_ms=1760000050,
    )

    healthy, rb_event = ctrl.ingest_ebpf_telemetry(telem)
    assert healthy is False
    assert rb_event is not None
    assert rb_event.trigger_reason == "UNAUTHORIZED_EGRESS_INTERCEPTED"
    assert rb_event.violating_metric == "is_unauthorized_egress"
    assert rb_event.metric_value_bps == 10000
    assert rb_event.threshold_value_bps == 0
    assert rb_event.prior_canary_weight_bps == 2000
    assert rb_event.new_canary_weight_bps == 0
    assert ctrl.current_canary_weight_bps == 0
    assert ctrl.status == STATUS_ROLLED_BACK

    # Verify SQL record for telemetry has is_unauthorized_egress == 1
    cursor = ctrl._conn.execute(
        "SELECT is_unauthorized_egress FROM canary_telemetry_ledger WHERE event_id = ?",
        ("evt-unauth-01",),
    )
    assert cursor.fetchone()[0] == 1

    # Verify SQL record in rollback ledger has new_canary_weight_bps == 0
    cursor_rb = ctrl._conn.execute(
        "SELECT new_canary_weight_bps, threshold_value_bps FROM canary_rollback_ledger WHERE rollback_id = ?",
        (rb_event.rollback_id,),
    )
    row_rb = cursor_rb.fetchone()
    assert row_rb[0] == 0
    assert row_rb[1] == 0

    # Subsequent requests must route strictly to PRODUCTION
    decision = ctrl.route_request("post-rollback-req")
    assert decision.destination_target == TARGET_PRODUCTION
    assert decision.canary_weight_bps == 0

    ctrl.close()


def test_automated_rollback_on_excessive_drift() -> None:
    """Evaluates rollback when trajectory drift breaches MAX_TRAJECTORY_DRIFT_BPS (4000 bps)."""
    ctrl = MultiRegionCanaryIngressController(region="ap-northeast-1", canary_weight_bps=1000)

    telem = EbpfSocketTelemetry(
        event_id="evt-drift-01",
        pod_id="pod-canary-tokyo",
        region="ap-northeast-1",
        function_name="sys_enter_connect",
        target_host="10.96.0.10",
        target_port=15001,
        observed_latency_ms=15,
        observed_jitter_bps=500,
        trajectory_drift_bps=4050,  # exceeds 4000 bps limit
        blast_radius_bps=1200,
        is_unauthorized_egress=False,
        timestamp_epoch_ms=1760000100,
    )

    healthy, rb_event = ctrl.ingest_ebpf_telemetry(telem)
    assert healthy is False
    assert rb_event is not None
    assert rb_event.trigger_reason == "TRAJECTORY_DRIFT_EXCEEDED"
    assert rb_event.violating_metric == "trajectory_drift_bps"
    assert rb_event.metric_value_bps == 4050
    assert rb_event.threshold_value_bps == MAX_TRAJECTORY_DRIFT_BPS
    assert ctrl.current_canary_weight_bps == 0
    assert ctrl.status == STATUS_ROLLED_BACK

    ctrl.close()


def test_automated_rollback_on_excessive_blast_radius() -> None:
    """Evaluates rollback when blast radius breaches MAX_BLAST_RADIUS_BPS (3000 bps)."""
    ctrl = MultiRegionCanaryIngressController(region="us-east-1", canary_weight_bps=1000)

    telem = EbpfSocketTelemetry(
        event_id="evt-blast-01",
        pod_id="pod-canary-va",
        region="us-east-1",
        function_name="sys_enter_connect",
        target_host="10.96.0.10",
        target_port=15001,
        observed_latency_ms=8,
        observed_jitter_bps=400,
        trajectory_drift_bps=1200,
        blast_radius_bps=3200,  # exceeds 3000 bps limit
        is_unauthorized_egress=False,
        timestamp_epoch_ms=1760000200,
    )

    healthy, rb_event = ctrl.ingest_ebpf_telemetry(telem)
    assert healthy is False
    assert rb_event is not None
    assert rb_event.trigger_reason == "BLAST_RADIUS_EXCEEDED"
    assert rb_event.violating_metric == "blast_radius_bps"
    assert rb_event.metric_value_bps == 3200
    assert rb_event.threshold_value_bps == MAX_BLAST_RADIUS_BPS

    ctrl.close()


def test_automated_rollback_on_excessive_jitter() -> None:
    """Evaluates rollback when observed network jitter breaches MAX_JITTER_BPS (4800 bps)."""
    ctrl = MultiRegionCanaryIngressController(region="us-west-2", canary_weight_bps=1000)

    telem = EbpfSocketTelemetry(
        event_id="evt-jitter-01",
        pod_id="pod-canary-or",
        region="us-west-2",
        function_name="sys_enter_connect",
        target_host="10.96.0.10",
        target_port=15001,
        observed_latency_ms=90,
        observed_jitter_bps=5200,  # exceeds 4800 bps limit
        trajectory_drift_bps=1100,
        blast_radius_bps=1400,
        is_unauthorized_egress=False,
        timestamp_epoch_ms=1760000300,
    )

    healthy, rb_event = ctrl.ingest_ebpf_telemetry(telem)
    assert healthy is False
    assert rb_event is not None
    assert rb_event.trigger_reason == "NETWORK_JITTER_EXCEEDED"
    assert rb_event.violating_metric == "observed_jitter_bps"
    assert rb_event.metric_value_bps == 5200
    assert rb_event.threshold_value_bps == MAX_JITTER_BPS

    ctrl.close()


def test_canary_verification_receipt_zero_floats_and_caid() -> None:
    """Evaluates verification receipt generation, RFC 8785 canonicalization, and zero-float invariant."""
    ctrl = MultiRegionCanaryIngressController(region="eu-west-1", canary_weight_bps=1000)

    ctrl.route_request("req-01")
    ctrl.route_request("req-02")

    receipt = ctrl.generate_verification_receipt()
    assert isinstance(receipt, CanaryVerificationReceipt)
    assert receipt.receipt_caid.startswith("sha256:")
    assert receipt.region == "eu-west-1"
    assert receipt.status == STATUS_HEALTHY_PROGRESSION
    assert receipt.total_requests_routed == 2
    assert receipt.current_canary_weight_bps == 1000
    assert receipt.current_production_weight_bps == TOTAL_WEIGHT_BPS - receipt.current_canary_weight_bps
    assert receipt.current_canary_weight_bps + receipt.current_production_weight_bps == TOTAL_WEIGHT_BPS
    assert receipt.rollback_occurred is False
    assert receipt.active_rollback_id is None

    # Verify zero-float invariant
    receipt_dict = receipt.to_dict()
    _assert_zero_floats(receipt_dict)

    # Re-verify deterministic hash consistency
    body = {
        "active_rollback_id": receipt.active_rollback_id,
        "canary_requests_routed": receipt.canary_requests_routed,
        "created_epoch_ms": receipt.created_epoch_ms,
        "current_canary_weight_bps": receipt.current_canary_weight_bps,
        "current_production_weight_bps": receipt.current_production_weight_bps,
        "max_observed_blast_radius_bps": receipt.max_observed_blast_radius_bps,
        "max_observed_drift_bps": receipt.max_observed_drift_bps,
        "max_observed_jitter_bps": receipt.max_observed_jitter_bps,
        "production_requests_routed": receipt.production_requests_routed,
        "region": receipt.region,
        "rollback_occurred": receipt.rollback_occurred,
        "status": receipt.status,
        "telemetry_events_ingested": receipt.telemetry_events_ingested,
        "total_requests_routed": receipt.total_requests_routed,
    }
    recomputed_caid = f"sha256:{hashlib.sha256(encode_jcs(body)).hexdigest()}"
    assert receipt.receipt_caid == recomputed_caid

    # Verify string representation and helper
    assert sha256_jcs_caid(b"abc").startswith("sha256:")
    assert sha256_jcs_caid("def").startswith("sha256:")

    ctrl.close()


def test_sqlite_wal_file_backed_persistence(tmp_path: Path) -> None:
    """Evaluates file-backed SQLite-WAL ledger initialization, persistence, and recovery."""
    db_file = tmp_path / "canary_test.db"

    ctrl = MultiRegionCanaryIngressController(
        region="us-east-1",
        canary_weight_bps=2000,
        db_path=str(db_file),
    )

    # Verify PRAGMA journal_mode is WAL
    cursor = ctrl._conn.execute("PRAGMA journal_mode;")
    mode = cursor.fetchone()[0]
    assert mode.lower() == "wal"

    ctrl.route_request("req-wal-01")

    # Ingest violating telemetry to trigger rollback
    telem = EbpfSocketTelemetry(
        event_id="evt-wal-fail",
        pod_id="pod-wal",
        region="us-east-1",
        function_name="sys_enter_connect",
        target_host="192.0.2.1",
        target_port=443,
        observed_latency_ms=25,
        observed_jitter_bps=5000,  # exceeds 4800 limit
        trajectory_drift_bps=100,
        blast_radius_bps=100,
        is_unauthorized_egress=False,
        timestamp_epoch_ms=1760000500,
    )
    healthy, rb_event = ctrl.ingest_ebpf_telemetry(telem)
    assert healthy is False
    assert rb_event is not None
    assert rb_event.db_commit_duration_ms >= 0

    ctrl.close()

    # Reopen database directly and verify recorded records
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM canary_routing_ledger;")
    assert cur.fetchone()[0] == 1

    cur.execute("SELECT COUNT(*) FROM canary_telemetry_ledger;")
    assert cur.fetchone()[0] == 1

    cur.execute("SELECT rollback_id, trigger_reason, prior_canary_weight_bps FROM canary_rollback_ledger;")
    row = cur.fetchone()
    assert row[0] == rb_event.rollback_id
    assert row[1] == "NETWORK_JITTER_EXCEEDED"
    assert row[2] == 2000
    conn.close()
