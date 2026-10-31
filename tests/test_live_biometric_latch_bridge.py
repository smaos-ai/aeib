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
tests/test_live_biometric_latch_bridge.py
================================================================================
Verification Suite for `src/live_biometric_latch_bridge.py`.
Evaluates under the stated model:
1. Nominal biometric latch release with real ECDSA P-256 Secure Enclave signatures.
2. Edge AI Critic pre-screening veto for critical risk mutations.
3. Out-of-band operator human veto locking the latch fail-closed.
4. Expired proposal and attempt fence enforcement.
5. Cryptographic signature and payload tamper detection.
6. Unknown mandate fail-closed adjudication.
"""

from __future__ import annotations

import hashlib
from typing import Tuple

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from src.ap2_mobile_mandate_engine import AP2AsyncMobileQueue, AP2MandateStage
from src.edge_ai_prescreener import EdgeAIPrescreener
from src.iphone_enclave_notary_bridge import (
    EnclaveSignedWarrant,
    MacEnclaveNotaryVerifier,
    T3ActionProposal,
    sha256_jcs_caid,
)
from src.live_biometric_latch_bridge import (
    BiometricAdjudicationReceipt,
    BiometricGateSubmission,
    LiveBiometricLatchBridge,
)


def _generate_p256_keypair() -> Tuple[ec.EllipticCurvePrivateKey, str]:
    private_key = ec.generate_private_key(ec.SECP256R1())
    pub_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    return private_key, pub_bytes.hex().lower()


def test_1_nominal_biometric_latch_release() -> None:
    # 1. Setup real crypto keys
    priv_key, pub_hex = _generate_p256_keypair()
    queue = AP2AsyncMobileQueue(pinned_enclave_pubkey_hex=pub_hex)
    prescreener = EdgeAIPrescreener()
    bridge = LiveBiometricLatchBridge(queue, prescreener, pinned_enclave_pubkey_x963_hex=pub_hex)

    now_epoch = 1770000000
    proposal = T3ActionProposal(
        operation_id="op_deploy_patch_42",
        intent_caid="sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        action_type="HIGH_RISK_CODE_DEPLOY",
        target_resource="src/settlement_engine.py",
        amount_minor=1000,
        attempt_fence=1,
        expires_at_epoch_sec=now_epoch + 600,
    )

    # 2. Propose high risk action
    submission = bridge.propose_high_risk_action(proposal, current_epoch_sec=now_epoch)
    assert submission.is_pending is True
    assert submission.latch_status == "LATCH_PENDING_MOBILE_AUTHORIZATION"
    assert submission.risk_score_bps < 8000
    assert submission.mandate_id == "mandate-op_deploy_patch_42"
    assert submission.submission_caid.startswith("sha256:")

    sub_dict = submission.to_dict()
    assert sub_dict["is_pending"] is True
    assert sub_dict["operation_id"] == "op_deploy_patch_42"

    # 3. Simulate iPhone 16 Pro Max Secure Enclave Hardware Signing
    canonical_bytes = proposal.to_canonical_jcs_bytes()
    sig_der = priv_key.sign(canonical_bytes, ec.ECDSA(hashes.SHA256()))

    warrant = EnclaveSignedWarrant(
        canonical_payload_utf8=canonical_bytes.decode("utf-8"),
        payload_sha256_caid=sha256_jcs_caid(canonical_bytes),
        public_key_x963_hex=pub_hex,
        signature_der_hex=sig_der.hex(),
        algorithm="ECDSA_P256_SHA256_SECURE_ENCLAVE",
    )

    # 4. Adjudicate warrant
    receipt = bridge.adjudicate_biometric_warrant(
        mandate_id=submission.mandate_id,
        warrant=warrant,
        current_epoch_sec=now_epoch + 10,
    )

    assert receipt.latch_released is True
    assert receipt.status_code == "LATCH_RELEASED_BIOMETRIC_CONFIRMED"
    assert receipt.adjudication_caid.startswith("sha256:")
    assert receipt.attempt_fence == 1

    rec_dict = receipt.to_dict()
    assert rec_dict["latch_released"] is True
    assert rec_dict["status_code"] == "LATCH_RELEASED_BIOMETRIC_CONFIRMED"

    # Verify mandate in queue is CLOSED_AUTHORIZED
    closed_mandate = queue.get_mandate(submission.mandate_id)
    assert closed_mandate is not None
    assert closed_mandate.stage == AP2MandateStage.CLOSED_AUTHORIZED


def test_2_edge_ai_critic_veto_on_critical_anomaly() -> None:
    priv_key, pub_hex = _generate_p256_keypair()
    queue = AP2AsyncMobileQueue(pinned_enclave_pubkey_hex=pub_hex)
    prescreener = EdgeAIPrescreener()
    bridge = LiveBiometricLatchBridge(queue, prescreener, pinned_enclave_pubkey_x963_hex=pub_hex)

    now_epoch = 1770000000
    # Destructive action targeting root credentials
    proposal = T3ActionProposal(
        operation_id="op_malicious_mutation",
        intent_caid="sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        action_type="DESTRUCTIVE_DROP_ALL_CREDENTIALS",
        target_resource="/etc/shadow",
        amount_minor=10000000,
        attempt_fence=1,
        expires_at_epoch_sec=now_epoch + 600,
    )

    submission = bridge.propose_high_risk_action(proposal, current_epoch_sec=now_epoch)
    assert submission.is_pending is False
    assert submission.latch_status == "LATCH_LOCKED_CRITIC_VETO"
    assert submission.recommendation == "RECOMMEND_VETO"
    assert submission.risk_score_bps >= 8000
    assert "Critical risk detected" in submission.critique_sentence_2


def test_3_operator_human_veto_locking_latch() -> None:
    priv_key, pub_hex = _generate_p256_keypair()
    queue = AP2AsyncMobileQueue(pinned_enclave_pubkey_hex=pub_hex)
    prescreener = EdgeAIPrescreener()
    bridge = LiveBiometricLatchBridge(queue, prescreener, pinned_enclave_pubkey_x963_hex=pub_hex)

    now_epoch = 1770000000
    proposal = T3ActionProposal(
        operation_id="op_caution_deploy",
        intent_caid="sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        action_type="HIGH_RISK_CODE_DEPLOY",
        target_resource="src/pci_vault.py",
        amount_minor=2000,
        attempt_fence=2,
        expires_at_epoch_sec=now_epoch + 600,
    )

    submission = bridge.propose_high_risk_action(proposal, current_epoch_sec=now_epoch)
    assert submission.is_pending is True

    # Operator inspects diff and issues veto
    receipt = bridge.adjudicate_operator_veto(
        mandate_id=submission.mandate_id,
        veto_reason="OPERATOR_INSPECTED_DIFF_REJECTED_MANUALLY",
        current_epoch_sec=now_epoch + 15,
    )

    assert receipt.latch_released is False
    assert receipt.status_code == "LATCH_LOCKED_OPERATOR_VETO"
    assert receipt.attempt_fence == 2

    # Verify mandate in queue is VETOED
    mandate = queue.get_mandate(submission.mandate_id)
    assert mandate is not None
    assert mandate.stage == AP2MandateStage.VETOED
    assert mandate.veto_reason == "OPERATOR_INSPECTED_DIFF_REJECTED_MANUALLY"


def test_4_expired_proposal_and_tampered_signature() -> None:
    priv_key, pub_hex = _generate_p256_keypair()
    queue = AP2AsyncMobileQueue(pinned_enclave_pubkey_hex=pub_hex)
    prescreener = EdgeAIPrescreener()
    bridge = LiveBiometricLatchBridge(queue, prescreener, pinned_enclave_pubkey_x963_hex=pub_hex)

    now_epoch = 1770000000
    proposal = T3ActionProposal(
        operation_id="op_time_sensitive",
        intent_caid="sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        action_type="HIGH_RISK_CODE_DEPLOY",
        target_resource="src/auth.py",
        amount_minor=500,
        attempt_fence=1,
        expires_at_epoch_sec=now_epoch + 100,
    )

    submission = bridge.propose_high_risk_action(proposal, current_epoch_sec=now_epoch)

    canonical_bytes = proposal.to_canonical_jcs_bytes()
    sig_der = priv_key.sign(canonical_bytes, ec.ECDSA(hashes.SHA256()))

    warrant = EnclaveSignedWarrant(
        canonical_payload_utf8=canonical_bytes.decode("utf-8"),
        payload_sha256_caid=sha256_jcs_caid(canonical_bytes),
        public_key_x963_hex=pub_hex,
        signature_der_hex=sig_der.hex(),
        algorithm="ECDSA_P256_SHA256_SECURE_ENCLAVE",
    )

    # 1. Adjudication after expiration
    expired_receipt = bridge.adjudicate_biometric_warrant(
        mandate_id=submission.mandate_id,
        warrant=warrant,
        current_epoch_sec=now_epoch + 150,
    )
    assert expired_receipt.latch_released is False
    assert "EXPIRED" in expired_receipt.status_code

    # 2. Tampered signature
    tampered_sig = bytes([(b ^ 0xFF) for b in sig_der])
    tampered_warrant = EnclaveSignedWarrant(
        canonical_payload_utf8=canonical_bytes.decode("utf-8"),
        payload_sha256_caid=sha256_jcs_caid(canonical_bytes),
        public_key_x963_hex=pub_hex,
        signature_der_hex=tampered_sig.hex(),
        algorithm="ECDSA_P256_SHA256_SECURE_ENCLAVE",
    )
    tampered_receipt = bridge.adjudicate_biometric_warrant(
        mandate_id=submission.mandate_id,
        warrant=tampered_warrant,
        current_epoch_sec=now_epoch + 10,
    )
    assert tampered_receipt.latch_released is False
    assert "SIGNATURE" in tampered_receipt.status_code or "FAILED" in tampered_receipt.status_code


def test_5_unknown_mandate_handling() -> None:
    priv_key, pub_hex = _generate_p256_keypair()
    queue = AP2AsyncMobileQueue(pinned_enclave_pubkey_hex=pub_hex)
    prescreener = EdgeAIPrescreener()
    bridge = LiveBiometricLatchBridge(queue, prescreener, pinned_enclave_pubkey_x963_hex=pub_hex)

    warrant = EnclaveSignedWarrant(
        canonical_payload_utf8="{}",
        payload_sha256_caid="sha256:0000000000000000000000000000000000000000000000000000000000000000",
        public_key_x963_hex=pub_hex,
        signature_der_hex="00",
        algorithm="ECDSA_P256_SHA256_SECURE_ENCLAVE",
    )

    rec = bridge.adjudicate_biometric_warrant("mandate-ghost", warrant, current_epoch_sec=1000)
    assert rec.latch_released is False
    assert rec.status_code == "ERR_UNKNOWN_MANDATE"
    assert rec.risk_score_bps == 10000
    expected_ghost_caid = sha256_jcs_caid({
        "latch_released": False,
        "mandate_id": "mandate-ghost",
        "status_code": "ERR_UNKNOWN_MANDATE",
    })
    assert rec.adjudication_caid == expected_ghost_caid

    veto_rec = bridge.adjudicate_operator_veto("mandate-ghost", "no_mandate", current_epoch_sec=1000)
    assert veto_rec.latch_released is False
    assert veto_rec.operation_id == ""
    assert veto_rec.attempt_fence == 0
    assert veto_rec.risk_score_bps == 10000
    expected_veto_caid = sha256_jcs_caid({
        "adjudication_epoch_sec": 1000,
        "attempt_fence": 0,
        "latch_released": False,
        "mandate_id": "mandate-ghost",
        "operation_id": "",
        "risk_score_bps": 10000,
        "status_code": "LATCH_LOCKED_OPERATOR_VETO",
        "veto_reason": "no_mandate",
    })
    assert veto_rec.adjudication_caid == expected_veto_caid


def test_6_helper_methods_and_input_validations() -> None:
    priv_key, pub_hex = _generate_p256_keypair()
    queue = AP2AsyncMobileQueue(pinned_enclave_pubkey_hex=pub_hex)
    prescreener = EdgeAIPrescreener()

    # 1. Invalid pinned pubkey
    with pytest.raises(ValueError, match="ERR_INVALID_PINNED_PUBKEY"):
        LiveBiometricLatchBridge(queue, prescreener, pinned_enclave_pubkey_x963_hex=123)  # type: ignore

    with pytest.raises(ValueError, match="ERR_INVALID_PINNED_PUBKEY"):
        LiveBiometricLatchBridge(queue, prescreener, pinned_enclave_pubkey_x963_hex="   ")

    bridge = LiveBiometricLatchBridge(queue, prescreener, pinned_enclave_pubkey_x963_hex=pub_hex)

    # 2. _compute_ttl boundary testing
    assert bridge._compute_ttl(150, 100) == 60  # remaining 50 < 60
    assert bridge._compute_ttl(160, 100) == 60  # remaining 60 == 60
    assert bridge._compute_ttl(200, 100) == 100  # remaining 100 > 60

    # 3. _resolve_spending_cap boundary testing
    assert bridge._resolve_spending_cap(0) == 1
    assert bridge._resolve_spending_cap(1) == 1
    assert bridge._resolve_spending_cap(500) == 500

    # 4. Zero amount proposal
    now_epoch = 1770000000
    zero_prop = T3ActionProposal(
        operation_id="op_zero_cost",
        intent_caid="sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
        action_type="HIGH_RISK_CODE_DEPLOY",
        target_resource="src/read_only_config.py",
        amount_minor=0,
        attempt_fence=1,
        expires_at_epoch_sec=now_epoch + 50,
    )
    sub = bridge.propose_high_risk_action(zero_prop, current_epoch_sec=now_epoch)
    assert sub.is_pending is True
    mandate = queue.get_mandate(sub.mandate_id)
    assert mandate is not None
    assert mandate.spending_cap_minor == 1  # defaulted to 1
    assert mandate.expires_at_epoch_sec == now_epoch + 60  # defaulted to min 60s TTL
