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
tests/test_bgp_anycast_routing_interlock.py
================================================================================
Verification Suite for BgpAnycastRoutingInterlock.

Engineering Status: INTERNAL PREVIEW COMMISSIONED
Epistemic Boundary: Observed, tested, evaluated under the stated model.

Tests:
1. BgpEdgeNodeConfig dataclass bounds and validation.
2. BgpRouteAnnouncementReceipt dataclass bounds, frozen immutability, and boundary values.
3. CAID computation across bytes, str, and dict payloads.
4. BgpAnycastRoutingInterlock initialization and monotonic epoch advances.
5. Edge node registration and duplicate prevention.
6. Telemetry evaluation: Nominal primary state (jitter <= 4800 bps).
7. Telemetry evaluation: Deprioritized state (jitter > 4800 bps, AS-Path prepended).
8. Telemetry evaluation: Consecutive heartbeat timeout withdrawal and reset.
9. Telemetry evaluation: Hard eBPF socket bypass withdrawal.
10. Global route panic linestop on total multi-region failure.
11. Cryptographic receipt verification and SQLite-WAL persistence.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
import sqlite3
import time
from typing import Any, Dict

import pytest

from src.bgp_anycast_routing_interlock import (
    DEFAULT_ANYCAST_PREFIX,
    MAX_ALLOWABLE_JITTER_BPS,
    MAX_CONSECUTIVE_TIMEOUTS,
    ROUTE_STATE_ANNOUNCED_DEPRIORITIZED,
    ROUTE_STATE_ANNOUNCED_PRIMARY,
    ROUTE_STATE_SUSPENDED_MANUAL,
    ROUTE_STATE_WITHDRAWN_FAULT,
    BgpAnycastRoutingInterlock,
    BgpEdgeNodeConfig,
    BgpRouteAnnouncementReceipt,
    compute_sha256_caid,
)


@pytest.fixture
def temp_db(tmp_path: Path) -> str:
    return str(tmp_path / "test_bgp_ledger.db")


@pytest.fixture
def sample_node() -> BgpEdgeNodeConfig:
    return BgpEdgeNodeConfig(
        node_id="node-us-east-1a",
        cloud_provider="AWS",
        autonomous_system_number=16509,
        anycast_prefix="198.51.100.0/24",
        bgp_neighbor_ip="192.0.2.1",
    )


def test_01_config_validations() -> None:
    # Valid config
    cfg = BgpEdgeNodeConfig("node-1", "GCP", 15169, "198.51.100.0/24", "192.0.2.2")
    assert cfg.node_id == "node-1"
    assert cfg.cloud_provider == "GCP"
    assert cfg.autonomous_system_number == 15169

    # Boundary ASNs
    cfg_min = BgpEdgeNodeConfig("node-1", "GCP", 1, "198.51.100.0/24", "192.0.2.2")
    assert cfg_min.autonomous_system_number == 1
    cfg_max = BgpEdgeNodeConfig("node-1", "GCP", 4294967295, "198.51.100.0/24", "192.0.2.2")
    assert cfg_max.autonomous_system_number == 4294967295

    # Frozen immutability
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.cloud_provider = "MUTATED"  # type: ignore

    # Invalid node_id
    with pytest.raises(ValueError, match="ERR_INVALID_NODE_ID"):
        BgpEdgeNodeConfig("", "GCP", 15169, "198.51.100.0/24", "192.0.2.2")
    with pytest.raises(ValueError, match="ERR_INVALID_NODE_ID"):
        BgpEdgeNodeConfig("   ", "GCP", 15169, "198.51.100.0/24", "192.0.2.2")

    # Invalid cloud_provider
    with pytest.raises(ValueError, match="ERR_INVALID_CLOUD_PROVIDER"):
        BgpEdgeNodeConfig("node-1", "", 15169, "198.51.100.0/24", "192.0.2.2")

    # Invalid ASN
    with pytest.raises(ValueError, match="ERR_INVALID_ASN"):
        BgpEdgeNodeConfig("node-1", "GCP", 0, "198.51.100.0/24", "192.0.2.2")
    with pytest.raises(ValueError, match="ERR_INVALID_ASN"):
        BgpEdgeNodeConfig("node-1", "GCP", 4294967296, "198.51.100.0/24", "192.0.2.2")
    with pytest.raises(ValueError, match="ERR_INVALID_ASN"):
        BgpEdgeNodeConfig("node-1", "GCP", 15169.5, "198.51.100.0/24", "192.0.2.2")  # type: ignore

    # Invalid anycast_prefix
    with pytest.raises(ValueError, match="ERR_INVALID_ANYCAST_PREFIX"):
        BgpEdgeNodeConfig("node-1", "GCP", 15169, "198.51.100.0", "192.0.2.2")

    # Invalid neighbor_ip
    with pytest.raises(ValueError, match="ERR_INVALID_NEIGHBOR_IP"):
        BgpEdgeNodeConfig("node-1", "GCP", 15169, "198.51.100.0/24", "")


def test_02_receipt_validations() -> None:
    valid_args: Dict[str, Any] = {
        "receipt_id": "r-01",
        "node_id": "node-1",
        "anycast_prefix": "198.51.100.0/24",
        "route_epoch_id": 1,
        "route_state": ROUTE_STATE_ANNOUNCED_PRIMARY,
        "local_preference": 200,
        "as_path_prepend_count": 0,
        "trigger_reason": "NOMINAL",
        "sealed_at_epoch_ms": 1700000000000,
        "receipt_caid": "sha256:" + "0" * 64,
    }

    receipt = BgpRouteAnnouncementReceipt(**valid_args)
    assert receipt.receipt_id == "r-01"

    # Exact boundary validations
    receipt_epoch_1 = BgpRouteAnnouncementReceipt(**dict(valid_args, route_epoch_id=1))
    assert receipt_epoch_1.route_epoch_id == 1

    receipt_pref_0 = BgpRouteAnnouncementReceipt(**dict(valid_args, local_preference=0))
    assert receipt_pref_0.local_preference == 0

    receipt_as_0 = BgpRouteAnnouncementReceipt(**dict(valid_args, as_path_prepend_count=0))
    assert receipt_as_0.as_path_prepend_count == 0

    receipt_ms_1 = BgpRouteAnnouncementReceipt(**dict(valid_args, sealed_at_epoch_ms=1))
    assert receipt_ms_1.sealed_at_epoch_ms == 1

    # Frozen immutability
    with pytest.raises(dataclasses.FrozenInstanceError):
        receipt.local_preference = 100  # type: ignore

    # Invalid fields
    with pytest.raises(ValueError, match="ERR_INVALID_RECEIPT_ID"):
        BgpRouteAnnouncementReceipt(**dict(valid_args, receipt_id=""))
    with pytest.raises(ValueError, match="ERR_INVALID_NODE_ID"):
        BgpRouteAnnouncementReceipt(**dict(valid_args, node_id=""))
    with pytest.raises(ValueError, match="ERR_INVALID_ANYCAST_PREFIX"):
        BgpRouteAnnouncementReceipt(**dict(valid_args, anycast_prefix="invalid"))
    with pytest.raises(ValueError, match="ERR_INVALID_ROUTE_EPOCH_ID"):
        BgpRouteAnnouncementReceipt(**dict(valid_args, route_epoch_id=0))
    with pytest.raises(ValueError, match="ERR_INVALID_ROUTE_EPOCH_ID"):
        BgpRouteAnnouncementReceipt(**dict(valid_args, route_epoch_id=1.5))
    with pytest.raises(ValueError, match="ERR_INVALID_ROUTE_STATE"):
        BgpRouteAnnouncementReceipt(**dict(valid_args, route_state="INVALID_STATE"))
    with pytest.raises(ValueError, match="ERR_INVALID_LOCAL_PREFERENCE"):
        BgpRouteAnnouncementReceipt(**dict(valid_args, local_preference=-1))
    with pytest.raises(ValueError, match="ERR_INVALID_LOCAL_PREFERENCE"):
        BgpRouteAnnouncementReceipt(**dict(valid_args, local_preference=50.5))
    with pytest.raises(ValueError, match="ERR_INVALID_AS_PATH_PREPEND_COUNT"):
        BgpRouteAnnouncementReceipt(**dict(valid_args, as_path_prepend_count=-1))
    with pytest.raises(ValueError, match="ERR_INVALID_AS_PATH_PREPEND_COUNT"):
        BgpRouteAnnouncementReceipt(**dict(valid_args, as_path_prepend_count=2.5))
    with pytest.raises(ValueError, match="ERR_INVALID_TRIGGER_REASON"):
        BgpRouteAnnouncementReceipt(**dict(valid_args, trigger_reason=""))
    with pytest.raises(ValueError, match="ERR_INVALID_SEALED_AT_EPOCH_MS"):
        BgpRouteAnnouncementReceipt(**dict(valid_args, sealed_at_epoch_ms=0))
    with pytest.raises(ValueError, match="ERR_INVALID_SEALED_AT_EPOCH_MS"):
        BgpRouteAnnouncementReceipt(**dict(valid_args, sealed_at_epoch_ms=10.5))
    with pytest.raises(ValueError, match="ERR_INVALID_RECEIPT_CAID"):
        BgpRouteAnnouncementReceipt(**dict(valid_args, receipt_caid="bad_caid"))


def test_03_caid_computation() -> None:
    c_bytes = compute_sha256_caid(b"sample_payload")
    c_str = compute_sha256_caid("sample_payload")
    c_dict = compute_sha256_caid({"key": "value"})

    assert c_bytes.startswith("sha256:")
    assert c_str.startswith("sha256:")
    assert c_dict.startswith("sha256:")
    assert c_bytes == c_str


def test_04_interlock_initialization_and_epoch() -> None:
    interlock = BgpAnycastRoutingInterlock(anycast_prefix="10.0.0.0/16", initial_route_epoch_id=2)
    assert interlock.anycast_prefix == "10.0.0.0/16"
    assert interlock.route_epoch_id == 2
    assert interlock.registered_nodes_count == 0

    # Monotonic epoch advances
    interlock.advance_route_epoch(3)
    assert interlock.route_epoch_id == 3

    with pytest.raises(ValueError, match="ERR_NON_MONOTONIC_EPOCH"):
        interlock.advance_route_epoch(3)
    with pytest.raises(ValueError, match="ERR_NON_MONOTONIC_EPOCH"):
        interlock.advance_route_epoch(2)

    # Invalid initialization
    with pytest.raises(ValueError, match="ERR_INVALID_ANYCAST_PREFIX"):
        BgpAnycastRoutingInterlock(anycast_prefix="no_slash")
    with pytest.raises(ValueError, match="ERR_INVALID_ROUTE_EPOCH_ID"):
        BgpAnycastRoutingInterlock(initial_route_epoch_id=0)


def test_05_node_registration_and_lookup(sample_node: BgpEdgeNodeConfig) -> None:
    interlock = BgpAnycastRoutingInterlock()
    interlock.register_edge_node(sample_node)
    assert interlock.registered_nodes_count == 1
    assert interlock.get_node_state(sample_node.node_id) == ROUTE_STATE_ANNOUNCED_PRIMARY

    # Duplicate registration
    with pytest.raises(KeyError, match="ERR_NODE_ALREADY_REGISTERED"):
        interlock.register_edge_node(sample_node)

    # Missing node lookup
    with pytest.raises(KeyError, match="ERR_NODE_NOT_FOUND"):
        interlock.get_node_state("nonexistent")


def test_06_telemetry_evaluation_nominal(sample_node: BgpEdgeNodeConfig) -> None:
    interlock = BgpAnycastRoutingInterlock()
    interlock.register_edge_node(sample_node)

    # Boundary jitter: 0 bps and exactly 4800 bps
    r0 = interlock.evaluate_edge_telemetry(
        node_id=sample_node.node_id,
        jitter_bps=0,
        socket_bypass_detected=False,
        heartbeat_timeout=False,
        now_ms=1700000001000,
    )
    assert r0.route_state == ROUTE_STATE_ANNOUNCED_PRIMARY
    assert r0.local_preference == 200
    assert r0.as_path_prepend_count == 0
    assert r0.trigger_reason == "TELEMETRY_NOMINAL_PRIMARY"

    r4800 = interlock.evaluate_edge_telemetry(
        node_id=sample_node.node_id,
        jitter_bps=MAX_ALLOWABLE_JITTER_BPS,
        socket_bypass_detected=False,
        heartbeat_timeout=False,
    )
    assert r4800.route_state == ROUTE_STATE_ANNOUNCED_PRIMARY
    assert r4800.local_preference == 200
    assert r4800.sealed_at_epoch_ms > 1_000_000_000_000

    # Nonexistent node
    with pytest.raises(KeyError, match="ERR_NODE_NOT_FOUND"):
        interlock.evaluate_edge_telemetry("unknown", 100, False, False)

    # Invalid jitter
    with pytest.raises(ValueError, match="ERR_INVALID_JITTER_BPS"):
        interlock.evaluate_edge_telemetry(sample_node.node_id, -1, False, False)
    with pytest.raises(ValueError, match="ERR_INVALID_JITTER_BPS"):
        interlock.evaluate_edge_telemetry(sample_node.node_id, 10.5, False, False)  # type: ignore


def test_07_telemetry_evaluation_deprioritized(sample_node: BgpEdgeNodeConfig) -> None:
    interlock = BgpAnycastRoutingInterlock()
    interlock.register_edge_node(sample_node)

    # Jitter exceeds 4800 bps -> 3x prepended, local pref 50
    receipt = interlock.evaluate_edge_telemetry(
        node_id=sample_node.node_id,
        jitter_bps=5000,
        socket_bypass_detected=False,
        heartbeat_timeout=False,
    )
    assert receipt.route_state == ROUTE_STATE_ANNOUNCED_DEPRIORITIZED
    assert receipt.local_preference == 50
    assert receipt.as_path_prepend_count == 3
    assert receipt.trigger_reason == "LATENCY_JITTER_EXCEEDED_5000_BPS"
    assert interlock.get_node_state(sample_node.node_id) == ROUTE_STATE_ANNOUNCED_DEPRIORITIZED


def test_08_telemetry_evaluation_heartbeat_timeout_and_reset(sample_node: BgpEdgeNodeConfig) -> None:
    interlock = BgpAnycastRoutingInterlock()
    interlock.register_edge_node(sample_node)

    # Timeout 1: still primary
    r1 = interlock.evaluate_edge_telemetry(sample_node.node_id, 1000, False, True)
    assert r1.route_state == ROUTE_STATE_ANNOUNCED_PRIMARY
    assert interlock._consecutive_timeouts[sample_node.node_id] == 1

    # Timeout 2: still primary
    r2 = interlock.evaluate_edge_telemetry(sample_node.node_id, 1000, False, True)
    assert r2.route_state == ROUTE_STATE_ANNOUNCED_PRIMARY
    assert interlock._consecutive_timeouts[sample_node.node_id] == 2

    # Reset: timeout is False -> counter resets to 0
    r_reset = interlock.evaluate_edge_telemetry(sample_node.node_id, 1000, False, False)
    assert r_reset.route_state == ROUTE_STATE_ANNOUNCED_PRIMARY
    assert interlock._consecutive_timeouts[sample_node.node_id] == 0

    # Retest to trigger withdrawal at threshold 3
    interlock.evaluate_edge_telemetry(sample_node.node_id, 1000, False, True)
    interlock.evaluate_edge_telemetry(sample_node.node_id, 1000, False, True)
    r3 = interlock.evaluate_edge_telemetry(sample_node.node_id, 1000, False, True)

    assert r3.route_state == ROUTE_STATE_WITHDRAWN_FAULT
    assert r3.local_preference == 0
    assert r3.as_path_prepend_count == 0
    assert "CONSECUTIVE_TIMEOUTS_EXCEEDED_3" in r3.trigger_reason
    assert interlock.get_node_state(sample_node.node_id) == ROUTE_STATE_WITHDRAWN_FAULT


def test_09_telemetry_evaluation_socket_bypass(sample_node: BgpEdgeNodeConfig) -> None:
    interlock = BgpAnycastRoutingInterlock()
    interlock.register_edge_node(sample_node)

    # Unauthorized eBPF LSM socket bypass -> immediate hard withdraw
    receipt = interlock.evaluate_edge_telemetry(
        node_id=sample_node.node_id,
        jitter_bps=100,
        socket_bypass_detected=True,
        heartbeat_timeout=False,
    )
    assert receipt.route_state == ROUTE_STATE_WITHDRAWN_FAULT
    assert receipt.local_preference == 0
    assert receipt.as_path_prepend_count == 0
    assert "UNAUTHORIZED_SOCKET_BYPASS_WITHDRAW_HARD" in receipt.trigger_reason
    assert interlock.get_node_state(sample_node.node_id) == ROUTE_STATE_WITHDRAWN_FAULT


def test_10_global_route_panic_linestop(sample_node: BgpEdgeNodeConfig) -> None:
    interlock = BgpAnycastRoutingInterlock()
    node2 = BgpEdgeNodeConfig("node-2", "GCP", 15169, "198.51.100.0/24", "192.0.2.2")
    interlock.register_edge_node(sample_node)
    interlock.register_edge_node(node2)

    # Withdraw first node: node2 is still active -> no global panic
    r1 = interlock.evaluate_edge_telemetry(sample_node.node_id, 0, True, False)
    assert r1.route_state == ROUTE_STATE_WITHDRAWN_FAULT
    assert "GLOBAL_ROUTE_PANIC_LINESTOP" not in r1.trigger_reason

    # Withdraw second node: all nodes withdrawn -> triggers GLOBAL_ROUTE_PANIC_LINESTOP
    r2 = interlock.evaluate_edge_telemetry(node2.node_id, 0, True, False)
    assert r2.route_state == ROUTE_STATE_WITHDRAWN_FAULT
    assert "GLOBAL_ROUTE_PANIC_LINESTOP" in r2.trigger_reason


def test_11_sqlite_persistence_and_receipt_verification(
    sample_node: BgpEdgeNodeConfig,
    temp_db: str,
) -> None:
    interlock = BgpAnycastRoutingInterlock(db_path=temp_db)
    interlock.register_edge_node(sample_node)

    receipt = interlock.evaluate_edge_telemetry(
        node_id=sample_node.node_id,
        jitter_bps=1200,
        socket_bypass_detected=False,
        heartbeat_timeout=False,
        now_ms=1700000005000,
    )

    # Verification passes on valid receipt
    assert interlock.verify_route_receipt(receipt) is True

    # Tampered receipt fails
    bad_receipt = dataclasses.replace(receipt, local_preference=999)
    assert interlock.verify_route_receipt(bad_receipt) is False

    interlock.close()

    # Query SQLite-WAL to verify persistence
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute(
        "SELECT receipt_id, node_id, route_state, local_preference, receipt_caid FROM bgp_route_receipts_ledger WHERE receipt_id = ?",
        (receipt.receipt_id,),
    )
    row = cur.fetchone()
    assert row is not None
    assert row[0] == receipt.receipt_id
    assert row[1] == sample_node.node_id
    assert row[2] == ROUTE_STATE_ANNOUNCED_PRIMARY
    assert row[3] == 200
    assert row[4] == receipt.receipt_caid
    conn.close()
