#!/usr/bin/env python3
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
tests/test_multi_region_edge_latch_mesh.py
================================================================================
Verification Suite for `src/multi_region_edge_latch_mesh.py`.
Evaluates:
1. Edge-local intent latching bypassing WAN latency overhead (<5ms vs 150ms).
2. Asynchronous RFC 8785 Merkle batch derivation across multi-region quorums.
3. Fail-closed `EFFECT_INDETERMINATE` freeze during simulated WAN partition.
4. Out-of-band reconciliation probe resolving indeterminate mutations.
5. Exact parameter validation, deterministic hashing, and dataclass serialization.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
import pytest

from src.multi_region_edge_latch_mesh import (
    CrossRegionMerkleSyncReceipt,
    EdgeLocalLatchReceipt,
    MultiRegionEdgeLatchMesh,
    sha256_jcs_caid,
)


def test_1_nominal_edge_local_latch_bypasses_wan_latency() -> None:
    mesh = MultiRegionEdgeLatchMesh(
        local_node_id="edge_worker_us_east_01",
        local_region="us-east-1",
        remote_regions=["us-west-2", "eu-central-1"],
        db_path=":memory:",
        simulated_wan_rtt_ms=220,  # claim: config
    )

    payload = {"account_id": "acc_123", "amount_cents": 5000, "currency": "EUR"}
    receipt = mesh.dispatch_edge_intent(
        target_host="api.stripe.com",
        business_payload=payload,
    )

    assert receipt.disposition == "LOCALLY_COMMITTED"
    assert receipt.node_id == "edge_worker_us_east_01"
    assert receipt.region == "us-east-1"
    assert receipt.target_host == "api.stripe.com"
    assert receipt.intent_caid.startswith("sha256:")
    assert receipt.receipt_caid.startswith("sha256:")
    assert receipt.simulated_wan_penalty_ms == 220
    # Edge-local write completes in <25ms, saving over 150ms
    assert receipt.saved_latency_ms >= 150
    assert receipt.local_latch_duration_ms < receipt.simulated_wan_penalty_ms


def test_2_asynchronous_merkle_batch_sync() -> None:
    mesh = MultiRegionEdgeLatchMesh(
        local_node_id="edge_worker_eu_west_01",
        local_region="eu-west-1",
        remote_regions=["us-east-1", "ap-southeast-1"],
        db_path=":memory:",
    )

    # Empty sync returns None
    assert mesh.sync_merkle_batch() is None

    # Dispatch 3 distinct intents
    for i in range(3):
        mesh.dispatch_edge_intent(
            target_host="api.external.com",
            business_payload={"batch_item": i, "token": f"tok_{i}"},
        )

    sync_receipt = mesh.sync_merkle_batch()
    assert sync_receipt is not None
    assert sync_receipt.intents_synced_count == 3
    assert sync_receipt.source_region == "eu-west-1"
    assert "us-east-1" in sync_receipt.target_regions
    assert sync_receipt.merkle_root.startswith("sha256:")
    assert sync_receipt.batch_caid.startswith("sha256:")

    # Re-syncing immediately returns None (already marked synced)
    assert mesh.sync_merkle_batch() is None


def test_3_partition_triggers_fail_closed_indeterminate_state() -> None:
    mesh = MultiRegionEdgeLatchMesh(
        local_node_id="edge_worker_01",
        local_region="us-east-1",
        remote_regions=["us-west-2"],
        db_path=":memory:",
    )

    mesh.trigger_wan_partition()
    assert mesh.partition_active is True

    # Under partition, sync is blocked
    assert mesh.sync_merkle_batch() is None

    # In-flight dispatch freezes to EFFECT_INDETERMINATE
    payload = {"action": "delete_customer", "customer_id": "cust_999"}
    r = mesh.dispatch_edge_intent("api.internal.vault", payload)
    assert r.disposition == "EFFECT_INDETERMINATE"

    # Out-of-band reconciliation
    reconciled = mesh.reconcile_indeterminate_records({r.intent_caid: "COMMITTED"})
    assert reconciled == 1

    # Invalid disposition ignored
    ignored = mesh.reconcile_indeterminate_records({r.intent_caid: "INVALID_STATE"})
    assert ignored == 0

    mesh.heal_wan_partition()
    assert mesh.partition_active is False


def test_4_input_validation_and_edge_cases() -> None:
    with pytest.raises(ValueError, match="ERR_EMPTY_NODE_ID"):
        MultiRegionEdgeLatchMesh(local_node_id="", local_region="us-east-1", remote_regions=["us-west-2"])

    with pytest.raises(ValueError, match="ERR_EMPTY_LOCAL_REGION"):
        MultiRegionEdgeLatchMesh(local_node_id="node_01", local_region="", remote_regions=["us-west-2"])

    with pytest.raises(ValueError, match="ERR_EMPTY_REMOTE_REGIONS"):
        MultiRegionEdgeLatchMesh(local_node_id="node_01", local_region="us-east-1", remote_regions=[])

    mesh = MultiRegionEdgeLatchMesh(local_node_id="node_01", local_region="us-east-1", remote_regions=["us-west-2"])
    with pytest.raises(ValueError, match="ERR_EMPTY_TARGET_HOST"):
        mesh.dispatch_edge_intent("", {"foo": "bar"})

    # Merkle root over empty list
    empty_root = MultiRegionEdgeLatchMesh._compute_merkle_root([])
    assert empty_root.startswith("sha256:")

    # Single leaf Merkle root equals the leaf itself
    single_root = MultiRegionEdgeLatchMesh._compute_merkle_root(["sha256:leaf_01"])
    assert single_root == "sha256:leaf_01"

    # Dataclass serialization
    receipt = EdgeLocalLatchReceipt(
        receipt_caid="sha256:rcpt",
        intent_caid="sha256:intent",
        node_id="n1",
        region="r1",
        target_host="h1",
        local_latch_duration_ms=2,
        simulated_wan_penalty_ms=150,
        saved_latency_ms=148,
        disposition="LOCALLY_COMMITTED",
        created_epoch_ms=1793400000000,
    )
    d = receipt.to_dict()
    assert d["saved_latency_ms"] == 148

    # Verify frozen immutability
    with pytest.raises(Exception):
        receipt.disposition = "MUTATED"  # type: ignore[misc]

    # Merkle tree with odd count leaves (3 leaves and 5 leaves) to test level step & concatenation
    leaves_3 = ["sha256:leaf_a", "sha256:leaf_b", "sha256:leaf_c"]
    root_3 = MultiRegionEdgeLatchMesh._compute_merkle_root(leaves_3)
    assert root_3.startswith("sha256:")

    leaves_5 = [f"sha256:leaf_{i}" for i in range(5)]
    root_5 = MultiRegionEdgeLatchMesh._compute_merkle_root(leaves_5)
    assert root_5.startswith("sha256:")
    assert root_5 != root_3

    sync_r = CrossRegionMerkleSyncReceipt(
        batch_caid="sha256:b1",
        merkle_root="sha256:m1",
        source_region="r1",
        target_regions=("r2", "r3"),
        intents_synced_count=5,
        sync_epoch_ms=1793400000000,
    )
    d_sync = sync_r.to_dict()
    assert d_sync["intents_synced_count"] == 5

    with pytest.raises(Exception):
        sync_r.batch_caid = "MUTATED"  # type: ignore[misc]


def test_5_exact_merkle_root_and_timestamp_mutation_killers() -> None:
    import hashlib

    # 1. Kill line 163: verify millisecond timestamp precision (> 1.7e12)
    ms = MultiRegionEdgeLatchMesh._now_epoch_ms()
    assert ms > 1700000000000
    assert isinstance(ms, int)

    # 2. Kill line 299: empty leaf list
    empty_root = MultiRegionEdgeLatchMesh._compute_merkle_root([])
    assert empty_root == sha256_jcs_caid([])

    # 3. Kill line 301 & 302: single leaf (length 1 should not loop)
    single_leaf = "sha256:1111111111111111111111111111111111111111111111111111111111111111"
    assert MultiRegionEdgeLatchMesh._compute_merkle_root([single_leaf]) == single_leaf

    # 4. Kill lines 304, 305, 306: two leaves (exact combined SHA-256)
    leaf_a = "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    leaf_b = "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    expected_pair_digest = f"sha256:{hashlib.sha256(leaf_a.encode('utf-8') + leaf_b.encode('utf-8')).hexdigest()}"
    root_2 = MultiRegionEdgeLatchMesh._compute_merkle_root([leaf_a, leaf_b])
    assert root_2 == expected_pair_digest

    # 5. Kill odd leaf duplication (3 leaves)
    leaf_c = "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
    # Level 1: pair(a, b), pair(c, c)
    c_pair_digest = f"sha256:{hashlib.sha256(leaf_c.encode('utf-8') + leaf_c.encode('utf-8')).hexdigest()}"
    level1 = [expected_pair_digest, c_pair_digest]
    expected_root_3 = f"sha256:{hashlib.sha256(level1[0].encode('utf-8') + level1[1].encode('utf-8')).hexdigest()}"
    root_3 = MultiRegionEdgeLatchMesh._compute_merkle_root([leaf_a, leaf_b, leaf_c])
    assert root_3 == expected_root_3

    # 6. Verify dataclass to_dict serializations
    mesh = MultiRegionEdgeLatchMesh(
        local_node_id="node_x",
        local_region="us-east-1",
        remote_regions=["eu-west-1"],
        db_path=":memory:",
    )
    receipt = mesh.dispatch_edge_intent("api.target.com", {"k": "v"})
    r_dict = receipt.to_dict()
    assert r_dict["node_id"] == "node_x"
    assert r_dict["target_host"] == "api.target.com"
    assert "saved_latency_ms" in r_dict

    sync = mesh.sync_merkle_batch()
    assert sync is not None
    s_dict = sync.to_dict()
    assert s_dict["source_region"] == "us-east-1"
    assert s_dict["target_regions"] == ["eu-west-1"]
    assert s_dict["intents_synced_count"] == 1
