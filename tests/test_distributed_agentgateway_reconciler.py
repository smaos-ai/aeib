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
tests/test_distributed_agentgateway_reconciler.py
================================================================================
Test suite for Cross-Region Latency Compensator & Distributed agentgateway Reconciler.
Zero mocks, zero floats, deterministic validation.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import pytest

from src.distributed_agentgateway_reconciler import (
    DistributedAgentgatewayReconciler,
    DistributedReconciliationReceipt,
    RegionalGatewayNode,
)

SAMPLE_ACTOR_SPIFFE = "spiffe://sovereign.nexus/ns/prod/sa/actor-lead"
SAMPLE_GW_SPIFFE = "spiffe://sovereign.nexus/ns/system/sa/agentgateway-us-east"
SAMPLE_EFFECT_KEY = "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


def test_init_and_node_registration() -> None:
    # Valid initialization
    rec = DistributedAgentgatewayReconciler(local_region="us-east-1", max_allowed_jitter_bps=4800)
    assert rec.local_region == "us-east-1"
    assert rec.max_allowed_jitter_bps == 4800

    # Exact boundary initialization
    rec0 = DistributedAgentgatewayReconciler(local_region="us-east-1", max_allowed_jitter_bps=0)
    assert rec0.max_allowed_jitter_bps == 0
    rec10k = DistributedAgentgatewayReconciler(local_region="us-east-1", max_allowed_jitter_bps=10000)
    assert rec10k.max_allowed_jitter_bps == 10000

    # Invalid local region
    with pytest.raises(ValueError, match="ERR_UNSUPPORTED_LOCAL_REGION"):
        DistributedAgentgatewayReconciler(local_region="ap-southeast-1")

    # Invalid jitter bounds
    with pytest.raises(ValueError, match="ERR_INVALID_JITTER_THRESHOLD_BPS"):
        DistributedAgentgatewayReconciler(local_region="us-east-1", max_allowed_jitter_bps=-1)
    with pytest.raises(ValueError, match="ERR_INVALID_JITTER_THRESHOLD_BPS"):
        DistributedAgentgatewayReconciler(local_region="us-east-1", max_allowed_jitter_bps=10001)

    # Valid node registration
    node_us = RegionalGatewayNode(
        region_id="us-east-1",
        gateway_spiffe_id=SAMPLE_GW_SPIFFE,
        observed_rtt_ms=20,
    )
    assert node_us.region_id == "us-east-1"
    assert node_us.observed_rtt_ms == 20
    rec.register_regional_node(node_us)

    # Invalid node inputs
    with pytest.raises(ValueError, match="ERR_UNSUPPORTED_REGION"):
        RegionalGatewayNode(region_id="bad-reg", gateway_spiffe_id=SAMPLE_GW_SPIFFE, observed_rtt_ms=10)
    with pytest.raises(ValueError, match="ERR_INVALID_GATEWAY_SPIFFE_ID"):
        RegionalGatewayNode(region_id="us-east-1", gateway_spiffe_id="bad-spiffe", observed_rtt_ms=10)
    with pytest.raises(ValueError, match="ERR_NEGATIVE_RTT"):
        RegionalGatewayNode(region_id="us-east-1", gateway_spiffe_id=SAMPLE_GW_SPIFFE, observed_rtt_ms=-5)


def test_compute_jitter_bps() -> None:
    rec = DistributedAgentgatewayReconciler(local_region="us-east-1")

    # Same region has 0 jitter
    assert rec.compute_jitter_bps("us-east-1") == 0

    # Missing nodes return maximum 10000 bps
    assert rec.compute_jitter_bps("eu-west-1") == 10000

    # Partial node registration (one registered, one missing)
    rec_part_target = DistributedAgentgatewayReconciler(local_region="us-east-1")
    rec_part_target.register_regional_node(RegionalGatewayNode("us-east-1", SAMPLE_GW_SPIFFE, observed_rtt_ms=20))
    assert rec_part_target.compute_jitter_bps("eu-west-1") == 10000

    rec_part_local = DistributedAgentgatewayReconciler(local_region="us-east-1")
    rec_part_local.register_regional_node(RegionalGatewayNode("eu-west-1", "spiffe://sovereign.nexus/ns/system/sa/gw-eu", observed_rtt_ms=20))
    assert rec_part_local.compute_jitter_bps("eu-west-1") == 10000

    # Zero local RTT floor check (local RTT = 0 ms -> local_rtt floored at 1 ms)
    rec_zero = DistributedAgentgatewayReconciler(local_region="us-east-1")
    rec_zero.register_regional_node(RegionalGatewayNode("us-east-1", SAMPLE_GW_SPIFFE, observed_rtt_ms=0))
    rec_zero.register_regional_node(RegionalGatewayNode("eu-west-1", "spiffe://sovereign.nexus/ns/system/sa/gw-eu", observed_rtt_ms=2))
    assert rec_zero.compute_jitter_bps("eu-west-1") == 10000

    # Equal RTT returns exactly 0 bps
    rec_eq = DistributedAgentgatewayReconciler(local_region="us-east-1")
    rec_eq.register_regional_node(RegionalGatewayNode("us-east-1", SAMPLE_GW_SPIFFE, observed_rtt_ms=25))
    rec_eq.register_regional_node(RegionalGatewayNode("us-west-2", "spiffe://sovereign.nexus/ns/system/sa/gw-west", observed_rtt_ms=25))
    assert rec_eq.compute_jitter_bps("us-west-2") == 0

    # Sub-basis-point delta floor (local 20000ms, target 20001ms -> 10000 // 20000 = 0 bps)
    rec_sub = DistributedAgentgatewayReconciler(local_region="us-east-1")
    rec_sub.register_regional_node(RegionalGatewayNode("us-east-1", SAMPLE_GW_SPIFFE, observed_rtt_ms=20000))
    rec_sub.register_regional_node(RegionalGatewayNode("us-west-2", "spiffe://sovereign.nexus/ns/system/sa/gw-west", observed_rtt_ms=20001))
    assert rec_sub.compute_jitter_bps("us-west-2") == 0

    # Register local and target nodes
    rec.register_regional_node(
        RegionalGatewayNode("us-east-1", SAMPLE_GW_SPIFFE, observed_rtt_ms=50)
    )
    rec.register_regional_node(
        RegionalGatewayNode("us-west-2", "spiffe://sovereign.nexus/ns/system/sa/gw-west", observed_rtt_ms=40)
    )
    # Target RTT <= local RTT -> 0 bps
    assert rec.compute_jitter_bps("us-west-2") == 0

    # Target RTT higher: local 50ms, eu 70ms -> delta 20ms -> 20 * 10000 // 50 = 4000 bps
    rec.register_regional_node(
        RegionalGatewayNode("eu-west-1", "spiffe://sovereign.nexus/ns/system/sa/gw-eu", observed_rtt_ms=70)
    )
    assert rec.compute_jitter_bps("eu-west-1") == 4000

    # Extreme latency: local 50ms, ap 300ms -> capped at 10000 bps
    rec.register_regional_node(
        RegionalGatewayNode("ap-northeast-1", "spiffe://sovereign.nexus/ns/system/sa/gw-ap", observed_rtt_ms=300)
    )
    assert rec.compute_jitter_bps("ap-northeast-1") == 10000

    # L23 Anti-masking precision test:
    # local_rtt = 11ms, target_rtt = 21ms (delta = 10ms)
    # (10 * 10000) // 11 = 9090 bps. Any +1 perturbation to 10000 yields (10 * 10001) // 11 = 9091 bps.
    rec.register_regional_node(
        RegionalGatewayNode("us-east-1", SAMPLE_GW_SPIFFE, observed_rtt_ms=11)
    )
    rec.register_regional_node(
        RegionalGatewayNode("eu-central-1", "spiffe://sovereign.nexus/ns/system/sa/gw-euc", observed_rtt_ms=21)
    )
    assert rec.compute_jitter_bps("eu-central-1") == 9090


def test_dispatch_mutation_intent_and_idempotency() -> None:
    rec = DistributedAgentgatewayReconciler(local_region="us-east-1", max_allowed_jitter_bps=4000)
    rec.register_regional_node(
        RegionalGatewayNode("us-east-1", SAMPLE_GW_SPIFFE, observed_rtt_ms=30)
    )
    rec.register_regional_node(
        RegionalGatewayNode("us-west-2", "spiffe://sovereign.nexus/ns/system/sa/gw-west", observed_rtt_ms=35)
    )

    # 1. Initial valid dispatch
    receipt1 = rec.dispatch_mutation_intent(
        reconciliation_id="rec-001",
        actor_spiffe_id=SAMPLE_ACTOR_SPIFFE,
        target_region="us-west-2",
        effect_key_caid=SAMPLE_EFFECT_KEY,
    )
    assert receipt1.reconciliation_state == "COMMITTED"
    assert receipt1.actor_spiffe_id == SAMPLE_ACTOR_SPIFFE
    assert receipt1.effect_key_caid == SAMPLE_EFFECT_KEY
    assert receipt1.receipt_caid.startswith("sha256:")

    # 2. Duplicate dispatch attempt with same effect_key_caid is strictly rejected
    receipt2 = rec.dispatch_mutation_intent(
        reconciliation_id="rec-002",
        actor_spiffe_id=SAMPLE_ACTOR_SPIFFE,
        target_region="us-west-2",
        effect_key_caid=SAMPLE_EFFECT_KEY,
    )
    assert receipt2.reconciliation_state == "REJECTED_DUPLICATE"

    # 3. Network partition fencing
    effect_key_part = "sha256:partition11111111111111111111111111111111111111111111111111111111"
    receipt_part = rec.dispatch_mutation_intent(
        reconciliation_id="rec-003",
        actor_spiffe_id=SAMPLE_ACTOR_SPIFFE,
        target_region="us-west-2",
        effect_key_caid=effect_key_part,
        network_partition_active=True,
    )
    assert receipt_part.reconciliation_state == "FENCED_PARTITION"

    # 4. Excessive WAN jitter fencing (> 4000 bps cap)
    rec.register_regional_node(
        RegionalGatewayNode("eu-west-1", "spiffe://sovereign.nexus/ns/system/sa/gw-eu", observed_rtt_ms=90)
    )
    # delta = 60ms on 30ms baseline = 20000 // 1 = 10000 bps > 4000
    effect_key_jitter = "sha256:jitter2222222222222222222222222222222222222222222222222222222222"
    receipt_jitter = rec.dispatch_mutation_intent(
        reconciliation_id="rec-004",
        actor_spiffe_id=SAMPLE_ACTOR_SPIFFE,
        target_region="eu-west-1",
        effect_key_caid=effect_key_jitter,
    )
    assert receipt_jitter.reconciliation_state == "FENCED_PARTITION"
    assert receipt_jitter.latency_p99_jitter_bps == 10000

    # 5. Invalid parameters
    with pytest.raises(ValueError, match="ERR_INVALID_ACTOR_SPIFFE_ID"):
        rec.dispatch_mutation_intent("r", "bad-spiffe", "us-west-2", SAMPLE_EFFECT_KEY)
    with pytest.raises(ValueError, match="ERR_INVALID_EFFECT_KEY_CAID"):
        rec.dispatch_mutation_intent("r", SAMPLE_ACTOR_SPIFFE, "us-west-2", "md5:bad")
    with pytest.raises(ValueError, match="ERR_UNSUPPORTED_TARGET_REGION"):
        rec.dispatch_mutation_intent("r", SAMPLE_ACTOR_SPIFFE, "bad-reg", SAMPLE_EFFECT_KEY)


def test_reconcile_indeterminate_mutation_recovery() -> None:
    rec = DistributedAgentgatewayReconciler(local_region="us-east-1")
    effect_key = "sha256:recovery33333333333333333333333333333333333333333333333333333333"

    # Attempting to reconcile a key not in indeterminate state raises ValueError
    with pytest.raises(ValueError, match="ERR_NOT_IN_INDETERMINATE_STATE"):
        rec.reconcile_indeterminate_mutation(effect_key, "CONFIRMED_COMMITTED")

    # Force into indeterminate partition state
    rec.dispatch_mutation_intent(
        reconciliation_id="rec-fence",
        actor_spiffe_id=SAMPLE_ACTOR_SPIFFE,
        target_region="us-east-1",
        effect_key_caid=effect_key,
        network_partition_active=True,
    )

    # Reconcile invalid status
    with pytest.raises(ValueError, match="ERR_INVALID_PROVIDER_STATUS"):
        rec.reconcile_indeterminate_mutation(effect_key, "UNKNOWN_STATUS")

    # Out-of-band resolution: external provider confirms mutation failed
    res_clear = rec.reconcile_indeterminate_mutation(effect_key, "CONFIRMED_FAILED")
    assert res_clear == "CLEARED_FOR_RETRY"

    # Now the effect key can be safely retried
    receipt_retry = rec.dispatch_mutation_intent(
        reconciliation_id="rec-retry",
        actor_spiffe_id=SAMPLE_ACTOR_SPIFFE,
        target_region="us-east-1",
        effect_key_caid=effect_key,
    )
    assert receipt_retry.reconciliation_state == "COMMITTED"

    # Indeterminate recovery with CONFIRMED_COMMITTED
    effect_key_commit = "sha256:commit444444444444444444444444444444444444444444444444444444444"
    rec.dispatch_mutation_intent(
        reconciliation_id="rec-fence-2",
        actor_spiffe_id=SAMPLE_ACTOR_SPIFFE,
        target_region="us-east-1",
        effect_key_caid=effect_key_commit,
        network_partition_active=True,
    )
    res_comm = rec.reconcile_indeterminate_mutation(effect_key_commit, "CONFIRMED_COMMITTED")
    assert res_comm == "COMMITTED"

    # Subsequent retry is rejected as duplicate
    rec_dup = rec.dispatch_mutation_intent(
        reconciliation_id="rec-retry-dup",
        actor_spiffe_id=SAMPLE_ACTOR_SPIFFE,
        target_region="us-east-1",
        effect_key_caid=effect_key_commit,
    )
    assert rec_dup.reconciliation_state == "REJECTED_DUPLICATE"


def test_receipt_dataclass_and_serialization() -> None:
    receipt = DistributedReconciliationReceipt(
        reconciliation_id="r1",
        actor_spiffe_id=SAMPLE_ACTOR_SPIFFE,
        origin_region="us-east-1",
        target_region="eu-west-1",
        effect_key_caid=SAMPLE_EFFECT_KEY,
        reconciliation_state="COMMITTED",
        latency_p99_jitter_bps=2500,
        receipt_caid="sha256:abcd",
    )

    with pytest.raises(FrozenInstanceError):
        receipt.reconciliation_state = "MUTATED"  # type: ignore

    d = receipt.to_dict()
    assert d["reconciliation_id"] == "r1"
    assert d["latency_p99_jitter_bps"] == 2500
    assert d["reconciliation_state"] == "COMMITTED"
