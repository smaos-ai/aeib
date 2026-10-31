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
tests/test_swat_heterogeneous_airlock.py
================================================================================
Comprehensive verification suite for SwaT Heterogeneous Airlock, HeteroFold
Procrustes alignment verifier, Consistent History Merkle Tree, and Biometric Step-Up.
"""

from __future__ import annotations

import dataclasses
import time
from typing import Dict, Tuple

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey

from src.hypersu_consistent_latent_gate import sha256_jcs_caid
from src.iphone_enclave_notary_bridge import (
    EnclaveSignedWarrant,
    MacEnclaveNotaryVerifier,
    T3ActionProposal,
)
from src.jcs_canonicalizer import encode_jcs
from src.swat_heterogeneous_airlock import (
    MAX_ALLOWABLE_DISTORTION_BPS,
    MAX_LATENT_ENERGY_PER_COORD,
    MIN_PROJECTION_FIDELITY_BPS,
    PROJECTION_SCALE,
    STEP_UP_THRESHOLD_MINOR,
    ConsistentHistoryMerkleTree,
    CrossModelMapperSpec,
    HeteroFoldAlignmentVerifier,
    SwatAirlockReceipt,
    SwatHeterogeneousAirlock,
    SwatTransferIntent,
)


@pytest.fixture
def p256_hardware_enclave_key() -> Tuple[EllipticCurvePrivateKey, str]:
    """Generates a real NIST P-256 (secp256r1) keypair simulating Apple Secure Enclave."""
    sk = ec.generate_private_key(ec.SECP256R1())
    pub = sk.public_key()
    pub_point_bytes = pub.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    return sk, pub_point_bytes.hex()


@pytest.fixture
def ed25519_airlock_key() -> ed25519.Ed25519PrivateKey:
    """Generates a real Ed25519 signing key for the airlock dispatch receipts."""
    return ed25519.Ed25519PrivateKey.generate()


def _mint_orthogonal_mapper(
    mapper_id: str,
    sender_backbone: str = "qwen-2.5-7b",
    receiver_backbone: str = "llama-3.3-70b",
    dim: int = 2,
    distortion_shift: int = 0,
) -> CrossModelMapperSpec:
    """Creates a 2x2 integer projection matrix scaled by PROJECTION_SCALE."""
    matrix = [
        PROJECTION_SCALE + distortion_shift,
        0,
        0,
        PROJECTION_SCALE,
    ]
    return CrossModelMapperSpec.create(
        mapper_id=mapper_id,
        sender_backbone=sender_backbone,
        receiver_backbone=receiver_backbone,
        dim_sender=dim,
        dim_receiver=dim,
        projection_matrix_flat=matrix,
    )


def test_cross_model_mapper_validation_and_caid() -> None:
    """Verifies input validation on CrossModelMapperSpec and RFC 8785 CAID generation."""
    assert PROJECTION_SCALE == 10000

    with pytest.raises(ValueError, match="ERR_INVALID_MAPPER_IDENTIFIERS"):
        CrossModelMapperSpec.create("", "qwen", "llama", 2, 2, [10000, 0, 0, 10000])

    with pytest.raises(ValueError, match="ERR_INVALID_MAPPER_DIMENSIONS"):
        CrossModelMapperSpec.create("m1", "qwen", "llama", 0, 2, [10000, 0, 0, 10000])

    with pytest.raises(ValueError, match="ERR_PROJECTION_MATRIX_DIMENSION_MISMATCH"):
        CrossModelMapperSpec.create("m1", "qwen", "llama", 2, 2, [10000, 0, 0])

    mapper = _mint_orthogonal_mapper("m_ok")
    assert mapper.mapper_caid.startswith("sha256:")
    assert len(mapper.mapper_caid) == 71

    # Invariant: dataclass is strictly frozen
    with pytest.raises(dataclasses.FrozenInstanceError):
        mapper.dim_sender = 10  # type: ignore[misc]


def test_heterofold_alignment_distortion_and_trojan_bounds() -> None:
    """Verifies Frobenius distortion computation and latent Trojan norm bounds."""
    # 1. Exact orthogonal mapping
    mapper_pure = _mint_orthogonal_mapper("m_pure", distortion_shift=0)
    dist_pure = HeteroFoldAlignmentVerifier.compute_orthogonal_distortion_bps(mapper_pure)
    assert dist_pure == 0

    ok, reason, dist = HeteroFoldAlignmentVerifier.verify_mapper_and_samples(
        mapper_pure, [100, -250, 500]
    )
    assert ok is True
    assert reason == "OK_ALIGNMENT_AND_BOUNDS_VERIFIED"
    assert dist == 0

    # 2. Distorted mapping exceeding threshold
    mapper_skewed = _mint_orthogonal_mapper("m_skew", distortion_shift=4000)
    dist_skewed = HeteroFoldAlignmentVerifier.compute_orthogonal_distortion_bps(mapper_skewed)
    assert dist_skewed > MAX_ALLOWABLE_DISTORTION_BPS

    ok_skew, reason_skew, dist_s = HeteroFoldAlignmentVerifier.verify_mapper_and_samples(
        mapper_skewed, [100, 200]
    )
    assert ok_skew is False
    assert "HALT_LATENT_ALIGNMENT_DECOHERENCE" in reason_skew
    assert dist_s == dist_skewed

    # 3. Trojan norm spike detection
    ok_trojan, reason_trojan, _ = HeteroFoldAlignmentVerifier.verify_mapper_and_samples(
        mapper_pure, [100, MAX_LATENT_ENERGY_PER_COORD + 1]
    )
    assert ok_trojan is False
    assert "HALT_LATENT_TROJAN_NORM_SPIKE" in reason_trojan


def test_consistent_history_merkle_tree_lifecycle() -> None:
    """Verifies incremental Merkle tree, cycle progression, scope confinement, and budget."""
    with pytest.raises(ValueError, match="ERR_INVALID_MAX_BUDGET"):
        ConsistentHistoryMerkleTree(-1, frozenset({"scope_a"}))

    with pytest.raises(ValueError, match="ERR_EMPTY_AUTHORIZED_SCOPES"):
        ConsistentHistoryMerkleTree(50000, frozenset())

    tree = ConsistentHistoryMerkleTree(
        max_budget_minor=20000,
        authorized_scopes=frozenset({"scope_payment", "scope_deploy"}),
    )
    assert tree.leaf_count == 0
    assert tree.current_merkle_root == "MERKLE_ROOT_GENESIS"

    # Step 1: CYCLE_1_BRAINSTORM
    ok1, st1, root1 = tree.append_and_verify(
        cycle_phase="CYCLE_1_BRAINSTORM",
        sender_agent_id="agent_1",
        receiver_agent_id="agent_2",
        mapper_caid="caid_map_1",
        intent_caid="caid_intent_1",
        spend_minor=1000,
        target_scope="scope_payment",
    )
    assert ok1 is True
    assert st1 == "OK_CONSISTENT_HISTORY_LEAF_COMMITTED"
    assert root1.startswith("sha256:")
    assert tree.cumulative_spend_minor == 1000
    assert tree.leaf_count == 1

    # Regression: cannot append negative spend
    ok_neg, st_neg, _ = tree.append_and_verify(
        "CYCLE_1_BRAINSTORM", "agent_1", "agent_2", "m", "i", -5, "scope_payment"
    )
    assert ok_neg is False
    assert st_neg == "HALT_INCONSISTENT_HISTORY:NEGATIVE_SPEND"

    # Regression: cannot jump directly to CYCLE_3_EXECUTE without CYCLE_2_GO_NOGO
    ok_skip, st_skip, _ = tree.append_and_verify(
        "CYCLE_3_EXECUTE", "agent_1", "agent_2", "m", "i", 2000, "scope_payment"
    )
    assert ok_skip is False
    assert st_skip == "HALT_INCONSISTENT_HISTORY:MISSING_CYCLE_2_GO_NOGO_GATE"

    # Step 2: CYCLE_2_GO_NOGO
    ok2, st2, root2 = tree.append_and_verify(
        "CYCLE_2_GO_NOGO", "agent_1", "agent_2", "m", "i", 500, "scope_payment"
    )
    assert ok2 is True
    assert root2 != root1

    # Regression: cannot regress back to CYCLE_1 from CYCLE_2
    ok_reg, st_reg, _ = tree.append_and_verify(
        "CYCLE_1_BRAINSTORM", "agent_1", "agent_2", "m", "i", 100, "scope_payment"
    )
    assert ok_reg is False
    assert "PHASE_REGRESSION" in st_reg

    # Regression: scope amplification outside authorized scopes
    ok_scope, st_scope, _ = tree.append_and_verify(
        "CYCLE_2_GO_NOGO", "agent_1", "agent_2", "m", "i", 100, "scope_unauthorized"
    )
    assert ok_scope is False
    assert "SCOPE_AMPLIFICATION" in st_scope

    # Regression: budget decoherence (cumulative spend exceeds 20000)
    ok_budget, st_budget, _ = tree.append_and_verify(
        "CYCLE_2_GO_NOGO", "agent_1", "agent_2", "m", "i", 19000, "scope_payment"
    )
    assert ok_budget is False
    assert "BUDGET_DECOHERENCE" in st_budget

    # Step 3: CYCLE_3_EXECUTE
    ok3, st3, root3 = tree.append_and_verify(
        "CYCLE_3_EXECUTE", "agent_1", "agent_2", "m", "i", 5000, "scope_payment"
    )
    assert ok3 is True
    assert tree.cumulative_spend_minor == 6500


def test_swat_airlock_gate_rejections(
    p256_hardware_enclave_key: Tuple[EllipticCurvePrivateKey, str],
    ed25519_airlock_key: ed25519.Ed25519PrivateKey,
) -> None:
    """Verifies airlock gate rejection branches: empty tensor, untrusted backbones, forbidden intents."""
    _, pub_hex = p256_hardware_enclave_key
    mapper = _mint_orthogonal_mapper("map_valid")

    with pytest.raises(ValueError, match="ERR_AIRLOCK_EMPTY_ALLOWED_BACKBONES"):
        SwatHeterogeneousAirlock(
            allowed_backbones=frozenset(),
            mappers={"map_valid": mapper},
            max_trajectory_budget_minor=50000,
            authorized_scopes=frozenset({"scope_main"}),
            pinned_enclave_pubkey_x963_hex=pub_hex,
            airlock_signing_key=ed25519_airlock_key,
        )

    with pytest.raises(ValueError, match="ERR_AIRLOCK_EMPTY_AUTHORIZED_SCOPES"):
        SwatHeterogeneousAirlock(
            allowed_backbones=frozenset({"qwen-2.5-7b"}),
            mappers={"map_valid": mapper},
            max_trajectory_budget_minor=50000,
            authorized_scopes=frozenset(),
            pinned_enclave_pubkey_x963_hex=pub_hex,
            airlock_signing_key=ed25519_airlock_key,
        )

    with pytest.raises(ValueError, match="ERR_INVALID_PINNED_ENCLAVE_PUBKEY"):
        SwatHeterogeneousAirlock(
            allowed_backbones=frozenset({"qwen-2.5-7b"}),
            mappers={"map_valid": mapper},
            max_trajectory_budget_minor=50000,
            authorized_scopes=frozenset({"scope_main"}),
            pinned_enclave_pubkey_x963_hex="   ",
            airlock_signing_key=ed25519_airlock_key,
        )

    airlock = SwatHeterogeneousAirlock(
        allowed_backbones=frozenset({"qwen-2.5-7b", "llama-3.3-70b"}),
        mappers={"map_valid": mapper},
        max_trajectory_budget_minor=50000,
        authorized_scopes=frozenset({"scope_main"}),
        pinned_enclave_pubkey_x963_hex=pub_hex,
        airlock_signing_key=ed25519_airlock_key,
    )

    # 1. Empty KV-cache
    intent_empty = SwatTransferIntent(
        sender_agent_id="a1",
        receiver_agent_id="a2",
        sender_backbone="qwen-2.5-7b",
        receiver_backbone="llama-3.3-70b",
        kv_cache_raw_bytes=b"",
        latent_sample_coords=(100, 200),
        mapper_id="map_valid",
        semantic_projection={"action": "read", "risk_tier": "LOW", "target_scope": "scope_main"},
        projection_fidelity_bps=9500,
        cycle_phase="CYCLE_1_BRAINSTORM",
        spend_minor_units=100,
        target_scope="scope_main",
        operation_id="op_1",
        attempt_fence=1,
        expires_at_epoch_sec=int(time.time()) + 300,
    )
    # Invariant: SwatTransferIntent is frozen
    with pytest.raises(dataclasses.FrozenInstanceError):
        intent_empty.operation_id = "op_tampered"  # type: ignore[misc]

    rcp_empty = airlock.process_latent_transfer(intent_empty)
    assert rcp_empty.allowed is False
    assert rcp_empty.status_code == "HALT_EMPTY_KV_CACHE_PAYLOAD"

    # 2. Untrusted sender backbone
    intent_untrusted_send = SwatTransferIntent(
        sender_agent_id="a1",
        receiver_agent_id="a2",
        sender_backbone="untrusted_model",
        receiver_backbone="llama-3.3-70b",
        kv_cache_raw_bytes=b"raw_kv_cache_bytes",
        latent_sample_coords=(100, 200),
        mapper_id="map_valid",
        semantic_projection={"action": "read", "risk_tier": "LOW", "target_scope": "scope_main"},
        projection_fidelity_bps=9500,
        cycle_phase="CYCLE_1_BRAINSTORM",
        spend_minor_units=100,
        target_scope="scope_main",
        operation_id="op_2",
        attempt_fence=1,
        expires_at_epoch_sec=int(time.time()) + 300,
    )
    rcp_untrusted = airlock.process_latent_transfer(intent_untrusted_send)
    assert rcp_untrusted.allowed is False
    assert "HALT_UNTRUSTED_SENDER_BACKBONE" in rcp_untrusted.status_code

    # 2b. Untrusted receiver backbone
    intent_untrusted_recv = SwatTransferIntent(
        sender_agent_id="a1",
        receiver_agent_id="a2",
        sender_backbone="qwen-2.5-7b",
        receiver_backbone="untrusted_receiver",
        kv_cache_raw_bytes=b"raw_kv_cache_bytes",
        latent_sample_coords=(100, 200),
        mapper_id="map_valid",
        semantic_projection={"action": "read", "risk_tier": "LOW", "target_scope": "scope_main"},
        projection_fidelity_bps=9500,
        cycle_phase="CYCLE_1_BRAINSTORM",
        spend_minor_units=100,
        target_scope="scope_main",
        operation_id="op_2b",
        attempt_fence=1,
        expires_at_epoch_sec=int(time.time()) + 300,
    )
    rcp_untrusted_recv = airlock.process_latent_transfer(intent_untrusted_recv)
    assert rcp_untrusted_recv.allowed is False
    assert "HALT_UNTRUSTED_RECEIVER_BACKBONE" in rcp_untrusted_recv.status_code

    # 2c. Mapper sender backbone mismatch
    mapper_mismatch_send = _mint_orthogonal_mapper("map_inv_send", sender_backbone="llama-3.3-70b", receiver_backbone="llama-3.3-70b")
    airlock.register_mapper(mapper_mismatch_send)
    intent_mismatch_send = SwatTransferIntent(
        sender_agent_id="a1",
        receiver_agent_id="a2",
        sender_backbone="qwen-2.5-7b",
        receiver_backbone="llama-3.3-70b",
        kv_cache_raw_bytes=b"raw_kv_cache_bytes",
        latent_sample_coords=(100, 200),
        mapper_id="map_inv_send",
        semantic_projection={"action": "read", "risk_tier": "LOW", "target_scope": "scope_main"},
        projection_fidelity_bps=9500,
        cycle_phase="CYCLE_1_BRAINSTORM",
        spend_minor_units=100,
        target_scope="scope_main",
        operation_id="op_2c",
        attempt_fence=1,
        expires_at_epoch_sec=int(time.time()) + 300,
    )
    rcp_mismatch_send = airlock.process_latent_transfer(intent_mismatch_send)
    assert rcp_mismatch_send.allowed is False
    assert rcp_mismatch_send.status_code == "HALT_MAPPER_SENDER_BACKBONE_MISMATCH"

    # 2d. Mapper receiver backbone mismatch
    mapper_mismatch_recv = _mint_orthogonal_mapper("map_inv_recv", sender_backbone="qwen-2.5-7b", receiver_backbone="qwen-2.5-7b")
    airlock.register_mapper(mapper_mismatch_recv)
    intent_mismatch_recv = SwatTransferIntent(
        sender_agent_id="a1",
        receiver_agent_id="a2",
        sender_backbone="qwen-2.5-7b",
        receiver_backbone="llama-3.3-70b",
        kv_cache_raw_bytes=b"raw_kv_cache_bytes",
        latent_sample_coords=(100, 200),
        mapper_id="map_inv_recv",
        semantic_projection={"action": "read", "risk_tier": "LOW", "target_scope": "scope_main"},
        projection_fidelity_bps=9500,
        cycle_phase="CYCLE_1_BRAINSTORM",
        spend_minor_units=100,
        target_scope="scope_main",
        operation_id="op_2d",
        attempt_fence=1,
        expires_at_epoch_sec=int(time.time()) + 300,
    )
    rcp_mismatch_recv = airlock.process_latent_transfer(intent_mismatch_recv)
    assert rcp_mismatch_recv.allowed is False
    assert rcp_mismatch_recv.status_code == "HALT_MAPPER_RECEIVER_BACKBONE_MISMATCH"

    # 3. Unregistered mapper
    intent_unregistered_map = SwatTransferIntent(
        sender_agent_id="a1",
        receiver_agent_id="a2",
        sender_backbone="qwen-2.5-7b",
        receiver_backbone="llama-3.3-70b",
        kv_cache_raw_bytes=b"raw_kv_cache_bytes",
        latent_sample_coords=(100, 200),
        mapper_id="map_unknown",
        semantic_projection={"action": "read", "risk_tier": "LOW", "target_scope": "scope_main"},
        projection_fidelity_bps=9500,
        cycle_phase="CYCLE_1_BRAINSTORM",
        spend_minor_units=100,
        target_scope="scope_main",
        operation_id="op_3",
        attempt_fence=1,
        expires_at_epoch_sec=int(time.time()) + 300,
    )
    rcp_unreg = airlock.process_latent_transfer(intent_unregistered_map)
    assert rcp_unreg.allowed is False
    assert "HALT_UNREGISTERED_MAPPER" in rcp_unreg.status_code

    # 4. Low projection fidelity (< 9000 bps)
    intent_low_fidelity = SwatTransferIntent(
        sender_agent_id="a1",
        receiver_agent_id="a2",
        sender_backbone="qwen-2.5-7b",
        receiver_backbone="llama-3.3-70b",
        kv_cache_raw_bytes=b"raw_kv_cache_bytes",
        latent_sample_coords=(100, 200),
        mapper_id="map_valid",
        semantic_projection={"action": "read", "risk_tier": "LOW", "target_scope": "scope_main"},
        projection_fidelity_bps=8999,
        cycle_phase="CYCLE_1_BRAINSTORM",
        spend_minor_units=100,
        target_scope="scope_main",
        operation_id="op_4",
        attempt_fence=1,
        expires_at_epoch_sec=int(time.time()) + 300,
    )
    rcp_low_fid = airlock.process_latent_transfer(intent_low_fidelity)
    assert rcp_low_fid.allowed is False
    assert "HALT_LATENT_PROJECTION_LOW_FIDELITY" in rcp_low_fid.status_code

    # 5. Forbidden latent intent (modify_tests)
    intent_forbidden = SwatTransferIntent(
        sender_agent_id="a1",
        receiver_agent_id="a2",
        sender_backbone="qwen-2.5-7b",
        receiver_backbone="llama-3.3-70b",
        kv_cache_raw_bytes=b"raw_kv_cache_bytes",
        latent_sample_coords=(100, 200),
        mapper_id="map_valid",
        semantic_projection={"action": "modify_tests", "risk_tier": "LOW", "target_scope": "scope_main"},
        projection_fidelity_bps=9500,
        cycle_phase="CYCLE_1_BRAINSTORM",
        spend_minor_units=100,
        target_scope="scope_main",
        operation_id="op_5",
        attempt_fence=1,
        expires_at_epoch_sec=int(time.time()) + 300,
    )
    rcp_forbid = airlock.process_latent_transfer(intent_forbidden)
    assert rcp_forbid.allowed is False
    assert "HALT_FORBIDDEN_LATENT_INTENT:modify_tests" in rcp_forbid.status_code


def test_swat_airlock_nominal_and_biometric_step_up(
    p256_hardware_enclave_key: Tuple[EllipticCurvePrivateKey, str],
    ed25519_airlock_key: ed25519.Ed25519PrivateKey,
) -> None:
    """Verifies end-to-end nominal flow and Apple Secure Enclave P-256 step-up authorization."""
    sk_p256, pub_hex = p256_hardware_enclave_key
    mapper = _mint_orthogonal_mapper("map_valid")

    airlock = SwatHeterogeneousAirlock(
        allowed_backbones=frozenset({"qwen-2.5-7b", "llama-3.3-70b"}),
        mappers={"map_valid": mapper},
        max_trajectory_budget_minor=100000,
        authorized_scopes=frozenset({"scope_main"}),
        pinned_enclave_pubkey_x963_hex=pub_hex,
        airlock_signing_key=ed25519_airlock_key,
    )

    now = int(time.time())

    # Step 1: Nominal CYCLE_1_BRAINSTORM (no step-up needed)
    intent_c1 = SwatTransferIntent(
        sender_agent_id="a1",
        receiver_agent_id="a2",
        sender_backbone="qwen-2.5-7b",
        receiver_backbone="llama-3.3-70b",
        kv_cache_raw_bytes=b"kv_cache_state_cycle1",
        latent_sample_coords=(50, -50),
        mapper_id="map_valid",
        semantic_projection={"action": "plan_architecture", "risk_tier": "LOW", "target_scope": "scope_main"},
        projection_fidelity_bps=9800,
        cycle_phase="CYCLE_1_BRAINSTORM",
        spend_minor_units=500,
        target_scope="scope_main",
        operation_id="op_c1",
        attempt_fence=1,
        expires_at_epoch_sec=now + 600,
    )
    rcp_c1 = airlock.process_latent_transfer(intent_c1, current_epoch_sec=now)
    assert rcp_c1.allowed is True
    assert rcp_c1.status_code == "OK_SWAT_AIRLOCK_DISPATCHED"
    assert rcp_c1.dispatch_nonce.startswith("dispatch-1-")

    # Invariant: SwatAirlockReceipt is frozen
    with pytest.raises(dataclasses.FrozenInstanceError):
        rcp_c1.allowed = False  # type: ignore[misc]

    # Step 2: Nominal CYCLE_2_GO_NOGO
    intent_c2 = SwatTransferIntent(
        sender_agent_id="a1",
        receiver_agent_id="a2",
        sender_backbone="qwen-2.5-7b",
        receiver_backbone="llama-3.3-70b",
        kv_cache_raw_bytes=b"kv_cache_state_cycle2",
        latent_sample_coords=(50, -50),
        mapper_id="map_valid",
        semantic_projection={"action": "review_spec", "risk_tier": "LOW", "target_scope": "scope_main"},
        projection_fidelity_bps=9800,
        cycle_phase="CYCLE_2_GO_NOGO",
        spend_minor_units=500,
        target_scope="scope_main",
        operation_id="op_c2",
        attempt_fence=1,
        expires_at_epoch_sec=now + 600,
    )
    rcp_c2 = airlock.process_latent_transfer(intent_c2, current_epoch_sec=now)
    assert rcp_c2.allowed is True
    assert rcp_c2.dispatch_nonce.startswith("dispatch-2-")

    # Step 2b: Test BOOL_SWAP branches on step-up requirement
    # Branch A: CYCLE_3_EXECUTE with risk_tier LOW and spend >= 10000 (STEP_UP_THRESHOLD_MINOR) -> requires warrant!
    intent_c3_large_spend_low_risk = SwatTransferIntent(
        sender_agent_id="a1",
        receiver_agent_id="a2",
        sender_backbone="qwen-2.5-7b",
        receiver_backbone="llama-3.3-70b",
        kv_cache_raw_bytes=b"kv_cache_state_large_spend",
        latent_sample_coords=(50, -50),
        mapper_id="map_valid",
        semantic_projection={"action": "buy_server", "risk_tier": "LOW", "target_scope": "scope_main"},
        projection_fidelity_bps=9800,
        cycle_phase="CYCLE_3_EXECUTE",
        spend_minor_units=STEP_UP_THRESHOLD_MINOR,
        target_scope="scope_main",
        operation_id="op_large_spend",
        attempt_fence=1,
        expires_at_epoch_sec=now + 600,
        step_up_warrant=None,
    )
    rcp_large_spend = airlock.process_latent_transfer(intent_c3_large_spend_low_risk, current_epoch_sec=now)
    assert rcp_large_spend.allowed is False
    assert "HALT_BIOMETRIC_STEP_UP_REQUIRED" in rcp_large_spend.status_code

    # Branch B: CYCLE_3_EXECUTE with risk_tier CRITICAL and spend < 10000 -> requires warrant!
    intent_c3_crit_low_spend = SwatTransferIntent(
        sender_agent_id="a1",
        receiver_agent_id="a2",
        sender_backbone="qwen-2.5-7b",
        receiver_backbone="llama-3.3-70b",
        kv_cache_raw_bytes=b"kv_cache_state_crit_low_spend",
        latent_sample_coords=(50, -50),
        mapper_id="map_valid",
        semantic_projection={"action": "drop_table", "risk_tier": "CRITICAL", "target_scope": "scope_main"},
        projection_fidelity_bps=9800,
        cycle_phase="CYCLE_3_EXECUTE",
        spend_minor_units=100,
        target_scope="scope_main",
        operation_id="op_crit_low",
        attempt_fence=1,
        expires_at_epoch_sec=now + 600,
        step_up_warrant=None,
    )
    rcp_crit_low = airlock.process_latent_transfer(intent_c3_crit_low_spend, current_epoch_sec=now)
    assert rcp_crit_low.allowed is False
    assert "HALT_BIOMETRIC_STEP_UP_REQUIRED" in rcp_crit_low.status_code

    # Step 3: CYCLE_3_EXECUTE with CRITICAL risk without warrant -> MUST HALT
    intent_c3_unwarranted = SwatTransferIntent(
        sender_agent_id="a1",
        receiver_agent_id="a2",
        sender_backbone="qwen-2.5-7b",
        receiver_backbone="llama-3.3-70b",
        kv_cache_raw_bytes=b"kv_cache_state_cycle3",
        latent_sample_coords=(50, -50),
        mapper_id="map_valid",
        semantic_projection={"action": "settle_payment", "risk_tier": "CRITICAL", "target_scope": "scope_main"},
        projection_fidelity_bps=9800,
        cycle_phase="CYCLE_3_EXECUTE",
        spend_minor_units=15000,
        target_scope="scope_main",
        operation_id="op_c3",
        attempt_fence=1,
        expires_at_epoch_sec=now + 600,
        step_up_warrant=None,
    )
    rcp_c3_unwarranted = airlock.process_latent_transfer(intent_c3_unwarranted, current_epoch_sec=now)
    assert rcp_c3_unwarranted.allowed is False
    assert "HALT_BIOMETRIC_STEP_UP_REQUIRED:MISSING_WARRANT" in rcp_c3_unwarranted.status_code

    # Mint valid Apple Secure Enclave P-256 warrant for intent_c3
    expected_tensor_caid = sha256_jcs_caid(intent_c3_unwarranted.kv_cache_raw_bytes)
    intent_body = {
        "mapper_caid": mapper.mapper_caid,
        "operation_id": "op_c3",
        "projection": intent_c3_unwarranted.semantic_projection,
        "receiver": "a2",
        "sender": "a1",
        "tensor_caid": expected_tensor_caid,
    }
    expected_intent_caid = sha256_jcs_caid(intent_body)

    proposal = T3ActionProposal(
        operation_id="op_c3",
        intent_caid=expected_intent_caid,
        action_type="settle_payment",
        target_resource="scope_main",
        amount_minor=15000,
        attempt_fence=1,
        expires_at_epoch_sec=now + 600,
    )
    canonical_jcs_bytes = proposal.to_canonical_jcs_bytes()
    signature_der = sk_p256.sign(canonical_jcs_bytes, ec.ECDSA(hashes.SHA256()))

    valid_warrant = EnclaveSignedWarrant(
        canonical_payload_utf8=canonical_jcs_bytes.decode("utf-8"),
        payload_sha256_caid=sha256_jcs_caid(canonical_jcs_bytes),
        public_key_x963_hex=pub_hex,
        signature_der_hex=signature_der.hex(),
        algorithm="ECDSA_P256_SHA256_SECURE_ENCLAVE",
    )

    intent_c3_warranted = SwatTransferIntent(
        sender_agent_id="a1",
        receiver_agent_id="a2",
        sender_backbone="qwen-2.5-7b",
        receiver_backbone="llama-3.3-70b",
        kv_cache_raw_bytes=b"kv_cache_state_cycle3",
        latent_sample_coords=(50, -50),
        mapper_id="map_valid",
        semantic_projection={"action": "settle_payment", "risk_tier": "CRITICAL", "target_scope": "scope_main"},
        projection_fidelity_bps=9800,
        cycle_phase="CYCLE_3_EXECUTE",
        spend_minor_units=15000,
        target_scope="scope_main",
        operation_id="op_c3",
        attempt_fence=1,
        expires_at_epoch_sec=now + 600,
        step_up_warrant=valid_warrant,
    )

    rcp_c3_ok = airlock.process_latent_transfer(intent_c3_warranted, current_epoch_sec=now)
    assert rcp_c3_ok.allowed is True
    assert rcp_c3_ok.status_code == "OK_SWAT_AIRLOCK_DISPATCHED"
    assert rcp_c3_ok.intent_caid == expected_intent_caid

    # Verify Ed25519 signature on the receipt
    receipt_dict = rcp_c3_ok.to_dict()
    sig_bytes = bytes.fromhex(rcp_c3_ok.airlock_signature_hex)
    body_to_verify = {
        "allowed": True,
        "dispatch_nonce": rcp_c3_ok.dispatch_nonce,
        "intent_caid": rcp_c3_ok.intent_caid,
        "mapper_caid": rcp_c3_ok.mapper_caid,
        "merkle_root": rcp_c3_ok.merkle_root,
        "status_code": rcp_c3_ok.status_code,
        "tensor_caid": rcp_c3_ok.tensor_caid,
    }
    airlock_pubkey = ed25519_airlock_key.public_key()
    airlock_pubkey.verify(sig_bytes, encode_jcs(body_to_verify))

    # Regression: Attempt Replay (same fence) MUST fail closed
    rcp_c3_replay = airlock.process_latent_transfer(intent_c3_warranted, current_epoch_sec=now)
    assert rcp_c3_replay.allowed is False
    assert "HALT_REPLAYED_ATTEMPT_FENCE" in rcp_c3_replay.status_code
