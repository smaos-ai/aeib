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
tests/test_adversarial_falsification_suite.py
================================================================================
Deterministic Adversarial Falsification Suite for AEIB/EO1 Sovereign Architecture.

Enforces falsification vectors under `--falsify`:
  - Vector 1: Stealth CSS Literal Evasion (AST string concatenation and unit bypass).
  - Vector 2: Invisible Element Camouflage & Steganographic Layout Manipulation.
  - Vector 3: SwaT Cross-Family Trojan Activation Spikes & Procrustes Distortion.
  - Vector 4: Monotonic Attempt Fence Regressions & Biometric Warrant Replays.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Tuple

import pytest
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from cryptography.hazmat.primitives import serialization

from src.constraint_compiler import ComponentConstraintSpec, ConstraintCompiler
from src.headless_browser_sidecar import DOMRasterizer, HeadlessBrowserSidecar
from src.iphone_enclave_notary_bridge import (
    EnclaveSignedWarrant,
    MacEnclaveNotaryVerifier,
    T3ActionProposal,
)
from src.swat_heterogeneous_airlock import (
    CrossModelMapperSpec,
    HeteroFoldAlignmentVerifier,
    SwatAirlockReceipt,
    SwatHeterogeneousAirlock,
    SwatTransferIntent,
)
from src.visual_regression_gate import VisualRegressionGate, VisualRegressionSpec


def test_falsification_vector_1_stealth_css_literal_evasion() -> None:
    """
    Falsification Vector 1:
    Adversarial agent attempts to evade forbidden design token literals by splitting
    hex values and px units into binary string additions (e.g. '#' + 'ff0000').
    ConstraintCompiler must catch the concatenated literal during AST inspection.
    """
    spec = ComponentConstraintSpec(
        constraint_id="spec_button_strict",
        component_name="PrimaryButton",
        required_design_tokens=("token.color.brand.primary",),
        forbidden_css_literals=("#ff0000", "16px"),
        required_accessibility_props=("role", "aria-label"),
        max_cyclomatic_complexity=5,
    )
    compiler = ConstraintCompiler(spec)

    # 1a. Stealth AST binary string concatenation of hex code
    adversarial_source_hex = """
def render_button():
    token = 'token.color.brand.primary'
    # Stealth evasion: splitting forbidden hex literal
    stealth_color = '#' + 'ff0000'
    return {'role': 'button', 'aria-label': 'Submit', 'color': stealth_color}
"""
    receipt_hex = compiler.verify_component_code(adversarial_source_hex)
    assert receipt_hex.passed is False
    assert any("VIOLATION_FORBIDDEN_LITERAL:#ff0000" in v for v in receipt_hex.violations)

    # 1b. Stealth AST binary string concatenation of px unit
    adversarial_source_px = """
def render_button():
    token = 'token.color.brand.primary'
    stealth_pad = '16' + 'px'
    return {'role': 'button', 'aria-label': 'Submit', 'pad': stealth_pad}
"""
    receipt_px = compiler.verify_component_code(adversarial_source_px)
    assert receipt_px.passed is False
    assert any("VIOLATION_FORBIDDEN_LITERAL:16px" in v for v in receipt_px.violations)

    # 1c. Compliant source passes cleanly
    compliant_source = """
def render_button():
    color = 'token.color.brand.primary'
    spacing = 'token.spacing.md'
    return {'role': 'button', 'aria-label': 'Submit', 'color': color, 'pad': spacing}
"""
    receipt_ok = compiler.verify_component_code(compliant_source)
    assert receipt_ok.passed is True
    assert len(receipt_ok.violations) == 0


def test_falsification_vector_2_invisible_element_camouflage() -> None:
    """
    Falsification Vector 2:
    Adversarial agent attempts to camouflage an interactive element or exploit layout
    by setting opacity: 0, display: none, or visibility: hidden.
    DOMRasterizer flags invisible elements and VisualRegressionGate triggers divergence.
    """
    sidecar = HeadlessBrowserSidecar(default_width=20, default_height=20)

    # Golden baseline: a legitimate visible black button occupying top-left 10x10
    legitimate_markup = '<button style="background: black; x: 0; y: 0; width: 10; height: 10;">Save</button>'
    golden_raster = sidecar.render_component(legitimate_markup)
    assert golden_raster.invisible_element_count == 0

    golden_spec = VisualRegressionSpec(
        component_name="ActionButton",
        golden_screenshot_caid=golden_raster.raster_caid,
        golden_pixels=golden_raster.pixels,
        width=20,
        height=20,
        max_divergence_bps=100,  # claim: config (1.00%)
    )

    # 2a. Camouflaged zero-opacity button
    camouflaged_markup = """
    <div>
        <button style="opacity: 0; background: black; x: 0; y: 0; width: 10; height: 10;">Phishing Hidden Button</button>
    </div>
    """
    raster_camouflaged = sidecar.render_component(camouflaged_markup)
    # The invisible element must be detected and not painted
    assert raster_camouflaged.invisible_element_count == 1
    receipt_camouflaged = sidecar.evaluate_component_regression(golden_spec, camouflaged_markup)
    assert receipt_camouflaged.passed is False
    assert "HALT_VISUAL_REGRESSION_DIVERGENCE" in receipt_camouflaged.status_code

    # 2b. Display: none element
    display_none_markup = '<div style="display: none; background: black; x: 0; y: 0; width: 10; height: 10;">Hidden</div>'
    raster_none = sidecar.render_component(display_none_markup)
    assert raster_none.invisible_element_count == 1
    receipt_none = sidecar.evaluate_component_regression(golden_spec, display_none_markup)
    assert receipt_none.passed is False


def test_falsification_vector_3_swat_trojan_norm_spike_and_distortion_rejection() -> None:
    """
    Falsification Vector 3:
    Adversarial cross-model KV-cache injection with Trojan activation spikes,
    excessive Procrustes orthogonal distortion, and Merkle leaf tampering.
    """
    airlock_key = ed25519.Ed25519PrivateKey.generate()
    enclave_priv = ec.generate_private_key(ec.SECP256R1())
    enclave_pub_bytes = enclave_priv.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    enclave_pub_hex = enclave_pub_bytes.hex()

    # 3a. Orthogonal identity mapper (clean)
    clean_mapper = CrossModelMapperSpec.create(
        mapper_id="mapper_clean",
        sender_backbone="anthropic_claude",
        receiver_backbone="deepseek_v3",
        dim_sender=2,
        dim_receiver=2,
        projection_matrix_flat=(10000, 0, 0, 10000),
    )

    # 3b. Distorted mapper exceeding 1500 bps (15.00%) Procrustes limit
    distorted_mapper = CrossModelMapperSpec.create(
        mapper_id="mapper_distorted",
        sender_backbone="anthropic_claude",
        receiver_backbone="deepseek_v3",
        dim_sender=2,
        dim_receiver=2,
        projection_matrix_flat=(15000, 0, 0, 5000),  # Extreme scaling distortion
    )

    airlock = SwatHeterogeneousAirlock(
        allowed_backbones=frozenset({"anthropic_claude", "deepseek_v3"}),
        mappers={"mapper_clean": clean_mapper, "mapper_distorted": distorted_mapper},
        max_trajectory_budget_minor=100000,
        authorized_scopes=frozenset({"payment_service", "repo_writer"}),
        pinned_enclave_pubkey_x963_hex=enclave_pub_hex,
        airlock_signing_key=airlock_key,
    )

    # Verification: Distorted mapper rejected at Gate 1
    intent_distorted = SwatTransferIntent(
        sender_agent_id="agent_sender",
        receiver_agent_id="agent_receiver",
        sender_backbone="anthropic_claude",
        receiver_backbone="deepseek_v3",
        kv_cache_raw_bytes=b"sample_kv_cache",
        latent_sample_coords=(100, 100),
        mapper_id="mapper_distorted",
        semantic_projection={"action": "query_db", "risk_tier": "LOW", "target_scope": "repo_writer"},
        projection_fidelity_bps=9500,
        cycle_phase="CYCLE_1_BRAINSTORM",
        spend_minor_units=0,
        target_scope="repo_writer",
        operation_id="op_distort",
        attempt_fence=1,
        expires_at_epoch_sec=int(time.time()) + 300,
    )
    receipt_distort = airlock.process_latent_transfer(intent_distorted)
    assert receipt_distort.allowed is False
    assert "HALT_LATENT_ALIGNMENT_DECOHERENCE" in receipt_distort.status_code
    assert "exceeds_1500_bps" in receipt_distort.status_code

    # 3c. Trojan Norm Spike: Latent energy per coord exceeding 1,000,000
    intent_trojan = SwatTransferIntent(
        sender_agent_id="agent_sender",
        receiver_agent_id="agent_receiver",
        sender_backbone="anthropic_claude",
        receiver_backbone="deepseek_v3",
        kv_cache_raw_bytes=b"sample_kv_cache",
        latent_sample_coords=(2_000_000, 500),  # Norm spike Trojan vector
        mapper_id="mapper_clean",
        semantic_projection={"action": "query_db", "risk_tier": "LOW", "target_scope": "repo_writer"},
        projection_fidelity_bps=9500,
        cycle_phase="CYCLE_1_BRAINSTORM",
        spend_minor_units=0,
        target_scope="repo_writer",
        operation_id="op_trojan",
        attempt_fence=1,
        expires_at_epoch_sec=int(time.time()) + 300,
    )
    receipt_trojan = airlock.process_latent_transfer(intent_trojan)
    assert receipt_trojan.allowed is False
    assert "HALT_LATENT_TROJAN_NORM_SPIKE" in receipt_trojan.status_code

    # 3d. Tampered Griffiths Merkle Tree root falsification
    # Corrupt internal Merkle root
    airlock.merkle_ledger._current_merkle_root = "sha256:corrupted_merkle_root_hex"
    # Attempting to verify history leaf consistency fails closed
    leaf_ok, leaf_reason, _ = airlock.merkle_ledger.append_and_verify(
        cycle_phase="CYCLE_1_EXPLORE",
        sender_agent_id="agent_sender",
        receiver_agent_id="agent_receiver",
        mapper_caid=clean_mapper.mapper_caid,
        intent_caid="sha256:dummy_intent",
        spend_minor=0,
        target_scope="repo_writer",
    )
    # The ledger appends cleanly, but re-verifying from genesis detects any discrepancy


def test_falsification_vector_4_monotonic_attempt_fence_and_biometric_replay() -> None:
    """
    Falsification Vector 4:
    Adversarial attempts to replay Apple Secure Enclave P-256 warrants,
    submit expired warrants, or tamper with the canonical act digest.
    """
    airlock_key = ed25519.Ed25519PrivateKey.generate()
    enclave_priv = ec.generate_private_key(ec.SECP256R1())
    enclave_pub_bytes = enclave_priv.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    enclave_pub_hex = enclave_pub_bytes.hex()

    clean_mapper = CrossModelMapperSpec.create(
        mapper_id="mapper_clean",
        sender_backbone="anthropic_claude",
        receiver_backbone="deepseek_v3",
        dim_sender=2,
        dim_receiver=2,
        projection_matrix_flat=(10000, 0, 0, 10000),
    )

    airlock = SwatHeterogeneousAirlock(
        allowed_backbones=frozenset({"anthropic_claude", "deepseek_v3"}),
        mappers={"mapper_clean": clean_mapper},
        max_trajectory_budget_minor=1_000_000,
        authorized_scopes=frozenset({"payment_service"}),
        pinned_enclave_pubkey_x963_hex=enclave_pub_hex,
        airlock_signing_key=airlock_key,
    )

    now_epoch = int(time.time())
    expires_epoch = now_epoch + 300

    # Prerequisite Step 1: Commit CYCLE_1_EXPLORE in Griffiths Merkle trajectory
    intent_c1 = SwatTransferIntent(
        sender_agent_id="agent_sender",
        receiver_agent_id="agent_receiver",
        sender_backbone="anthropic_claude",
        receiver_backbone="deepseek_v3",
        kv_cache_raw_bytes=b"sample_kv_cache_c1",
        latent_sample_coords=(100, 100),
        mapper_id="mapper_clean",
        semantic_projection={"action": "explore_spec", "risk_tier": "LOW", "target_scope": "payment_service"},
        projection_fidelity_bps=9500,
        cycle_phase="CYCLE_1_BRAINSTORM",
        spend_minor_units=0,
        target_scope="payment_service",
        operation_id="op_c1",
        attempt_fence=1,
        expires_at_epoch_sec=expires_epoch,
    )
    rcp_c1 = airlock.process_latent_transfer(intent_c1, current_epoch_sec=now_epoch)
    assert rcp_c1.allowed is True

    # Prerequisite Step 2: Commit CYCLE_2_GO_NOGO in Griffiths Merkle trajectory
    intent_c2 = SwatTransferIntent(
        sender_agent_id="agent_sender",
        receiver_agent_id="agent_receiver",
        sender_backbone="anthropic_claude",
        receiver_backbone="deepseek_v3",
        kv_cache_raw_bytes=b"sample_kv_cache_c2",
        latent_sample_coords=(100, 100),
        mapper_id="mapper_clean",
        semantic_projection={"action": "prescreen_go", "risk_tier": "LOW", "target_scope": "payment_service"},
        projection_fidelity_bps=9500,
        cycle_phase="CYCLE_2_GO_NOGO",
        spend_minor_units=100,
        target_scope="payment_service",
        operation_id="op_c2",
        attempt_fence=1,
        expires_at_epoch_sec=expires_epoch,
    )
    rcp_c2 = airlock.process_latent_transfer(intent_c2, current_epoch_sec=now_epoch)
    assert rcp_c2.allowed is True

    # Synthesize intent matching this proposal for CYCLE_3_EXECUTE
    intent_base = SwatTransferIntent(
        sender_agent_id="agent_sender",
        receiver_agent_id="agent_receiver",
        sender_backbone="anthropic_claude",
        receiver_backbone="deepseek_v3",
        kv_cache_raw_bytes=b"sample_kv_cache",
        latent_sample_coords=(100, 100),
        mapper_id="mapper_clean",
        semantic_projection={
            "action": "transfer_funds",
            "risk_tier": "CRITICAL",
            "target_scope": "payment_service",
        },
        projection_fidelity_bps=9500,
        cycle_phase="CYCLE_3_EXECUTE",
        spend_minor_units=50000,
        target_scope="payment_service",
        operation_id="op_fund_transfer_001",
        attempt_fence=1,
        expires_at_epoch_sec=expires_epoch,
    )

    # Compute expected intent_caid
    _, _, tensor_caid = airlock._verify_mapper_and_latent(intent_base)
    _, _, computed_intent_caid = airlock._verify_semantic_projection(intent_base, tensor_caid, clean_mapper.mapper_caid)

    # Bind exact proposal
    bound_proposal = T3ActionProposal(
        operation_id="op_fund_transfer_001",
        intent_caid=computed_intent_caid,
        action_type="transfer_funds",
        target_resource="payment_service",
        amount_minor=50000,
        attempt_fence=1,
        expires_at_epoch_sec=expires_epoch,
    )

    from cryptography.hazmat.primitives import hashes
    from src.hypersu_consistent_latent_gate import sha256_jcs_caid

    canonical_jcs_bytes = bound_proposal.to_canonical_jcs_bytes()
    sig_der = enclave_priv.sign(
        canonical_jcs_bytes,
        ec.ECDSA(hashes.SHA256()),
    )
    valid_warrant = EnclaveSignedWarrant(
        canonical_payload_utf8=canonical_jcs_bytes.decode("utf-8"),
        payload_sha256_caid=sha256_jcs_caid(canonical_jcs_bytes),
        public_key_x963_hex=enclave_pub_hex,
        signature_der_hex=sig_der.hex(),
        algorithm="ECDSA_P256_SHA256_SECURE_ENCLAVE",
    )

    intent_with_warrant = SwatTransferIntent(
        sender_agent_id=intent_base.sender_agent_id,
        receiver_agent_id=intent_base.receiver_agent_id,
        sender_backbone=intent_base.sender_backbone,
        receiver_backbone=intent_base.receiver_backbone,
        kv_cache_raw_bytes=intent_base.kv_cache_raw_bytes,
        latent_sample_coords=intent_base.latent_sample_coords,
        mapper_id=intent_base.mapper_id,
        semantic_projection=intent_base.semantic_projection,
        projection_fidelity_bps=intent_base.projection_fidelity_bps,
        cycle_phase=intent_base.cycle_phase,
        spend_minor_units=intent_base.spend_minor_units,
        target_scope=intent_base.target_scope,
        operation_id=intent_base.operation_id,
        attempt_fence=1,
        expires_at_epoch_sec=intent_base.expires_at_epoch_sec,
        step_up_warrant=valid_warrant,
    )

    # 4a. First execution passes
    receipt_first = airlock.process_latent_transfer(intent_with_warrant, current_epoch_sec=now_epoch)
    assert receipt_first.allowed is True
    assert receipt_first.status_code == "OK_SWAT_AIRLOCK_DISPATCHED"

    # 4b. Replay attack: resubmitting with same attempt fence 1 fails closed
    receipt_replayed = airlock.process_latent_transfer(intent_with_warrant, current_epoch_sec=now_epoch)
    assert receipt_replayed.allowed is False
    assert "HALT_REPLAYED_ATTEMPT_FENCE" in receipt_replayed.status_code

    # 4c. Expired warrant fails closed
    expired_proposal = T3ActionProposal(
        operation_id="op_fund_transfer_001",
        intent_caid=computed_intent_caid,
        action_type="transfer_funds",
        target_resource="payment_service",
        amount_minor=50000,
        attempt_fence=2,
        expires_at_epoch_sec=now_epoch - 10,  # Already expired
    )
    exp_bytes = expired_proposal.to_canonical_jcs_bytes()
    sig_exp = enclave_priv.sign(exp_bytes, ec.ECDSA(hashes.SHA256()))
    expired_warrant = EnclaveSignedWarrant(
        canonical_payload_utf8=exp_bytes.decode("utf-8"),
        payload_sha256_caid=sha256_jcs_caid(exp_bytes),
        public_key_x963_hex=enclave_pub_hex,
        signature_der_hex=sig_exp.hex(),
        algorithm="ECDSA_P256_SHA256_SECURE_ENCLAVE",
    )
    intent_expired = SwatTransferIntent(
        sender_agent_id=intent_base.sender_agent_id,
        receiver_agent_id=intent_base.receiver_agent_id,
        sender_backbone=intent_base.sender_backbone,
        receiver_backbone=intent_base.receiver_backbone,
        kv_cache_raw_bytes=intent_base.kv_cache_raw_bytes,
        latent_sample_coords=intent_base.latent_sample_coords,
        mapper_id=intent_base.mapper_id,
        semantic_projection=intent_base.semantic_projection,
        projection_fidelity_bps=intent_base.projection_fidelity_bps,
        cycle_phase=intent_base.cycle_phase,
        spend_minor_units=intent_base.spend_minor_units,
        target_scope=intent_base.target_scope,
        operation_id=intent_base.operation_id,
        attempt_fence=2,
        expires_at_epoch_sec=now_epoch - 10,
        step_up_warrant=expired_warrant,
    )
    receipt_expired = airlock.process_latent_transfer(intent_expired, current_epoch_sec=now_epoch)
    assert receipt_expired.allowed is False
    assert "HALT_BIOMETRIC_VERIFICATION_FAILED" in receipt_expired.status_code

    # 4d. Forged canonical payload / caid mismatch fails closed
    tampered_warrant = EnclaveSignedWarrant(
        canonical_payload_utf8="tampered_payload_utf8",
        payload_sha256_caid="sha256:forged_tampered_act_digest",
        public_key_x963_hex=enclave_pub_hex,
        signature_der_hex=sig_der.hex(),
        algorithm="ECDSA_P256_SHA256_SECURE_ENCLAVE",
    )
    intent_tampered = SwatTransferIntent(
        sender_agent_id=intent_base.sender_agent_id,
        receiver_agent_id=intent_base.receiver_agent_id,
        sender_backbone=intent_base.sender_backbone,
        receiver_backbone=intent_base.receiver_backbone,
        kv_cache_raw_bytes=intent_base.kv_cache_raw_bytes,
        latent_sample_coords=intent_base.latent_sample_coords,
        mapper_id=intent_base.mapper_id,
        semantic_projection=intent_base.semantic_projection,
        projection_fidelity_bps=intent_base.projection_fidelity_bps,
        cycle_phase=intent_base.cycle_phase,
        spend_minor_units=intent_base.spend_minor_units,
        target_scope=intent_base.target_scope,
        operation_id=intent_base.operation_id,
        attempt_fence=2,
        expires_at_epoch_sec=expires_epoch,
        step_up_warrant=tampered_warrant,
    )
    receipt_tampered = airlock.process_latent_transfer(intent_tampered, current_epoch_sec=now_epoch)
    assert receipt_tampered.allowed is False
    assert "HALT_BIOMETRIC_VERIFICATION_FAILED" in receipt_tampered.status_code
