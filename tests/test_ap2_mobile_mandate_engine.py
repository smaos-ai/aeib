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
tests/test_ap2_mobile_mandate_engine.py
================================================================================
Comprehensive verification suite for AP2AsyncMobileQueue and AP2IntentMandate.
"""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

from src.ap2_mobile_mandate_engine import (
    AP2AsyncMobileQueue,
    AP2IntentMandate,
    AP2MandateStage,
)
from src.iphone_enclave_notary_bridge import (
    T3ActionProposal,
    sha256_jcs_caid,
)


@pytest.fixture
def dummy_enclave_keypair():
    priv = ec.generate_private_key(ec.SECP256R1())
    pub_point = priv.public_key().public_numbers()
    x = pub_point.x.to_bytes(32, byteorder="big")
    y = pub_point.y.to_bytes(32, byteorder="big")
    x963_hex = (b"\x04" + x + y).hex()
    return priv, x963_hex


def test_nominal_mandate_creation_and_hardware_resolution(dummy_enclave_keypair):
    priv, x963_hex = dummy_enclave_keypair
    queue = AP2AsyncMobileQueue(pinned_enclave_pubkey_hex=x963_hex)

    intent_caid = "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    mandate = queue.create_and_enqueue_mandate(
        task_id="task-overnight-001",
        intent_caid=intent_caid,
        spending_cap_minor=2500,  # $25.00
        allowed_rails=["STRIPE_ACP", "X402"],
        attempt_fence=1,
        ttl_seconds=3600,
        current_epoch_sec=1700000000,
        mandate_id="mandate-test-001",
    )

    assert mandate.mandate_id == "mandate-test-001"
    assert mandate.stage == AP2MandateStage.PENDING_MOBILE_AUTHORIZATION
    assert mandate.spending_cap_minor == 2500
    assert mandate.attempt_fence == 1
    assert mandate.compute_mandate_caid().startswith("sha256:")

    pending = queue.list_pending_mandates()
    assert len(pending) == 1
    assert pending[0].mandate_id == "mandate-test-001"

    # Construct and sign real P-256 warrant over canonical proposal bytes
    proposal = T3ActionProposal(
        action_type="AP2_PAYMENT_MANDATE",
        amount_minor=2500,
        attempt_fence=1,
        expires_at_epoch_sec=1700000000 + 3600,
        intent_caid=intent_caid,
        operation_id="mandate-test-001",
        target_resource="task-overnight-001",
    )
    raw_utf8 = proposal.to_canonical_jcs_bytes().decode("utf-8")
    sig_der = priv.sign(raw_utf8.encode("utf-8"), ec.ECDSA(hashes.SHA256()))

    warrant_dict = {
        "canonical_payload_utf8": raw_utf8,
        "payload_sha256_caid": sha256_jcs_caid(raw_utf8.encode("utf-8")),
        "public_key_x963_hex": x963_hex,
        "signature_der_hex": sig_der.hex(),
        "algorithm": "ECDSA_P256_SHA256_SECURE_ENCLAVE",
    }

    ok, err, resolved = queue.resolve_with_hardware_warrant(
        mandate_id="mandate-test-001",
        warrant_data=warrant_dict,
        current_epoch_sec=1700000500,
    )

    assert ok is True
    assert err == "OK"
    assert resolved is not None
    assert resolved.stage == AP2MandateStage.CLOSED_AUTHORIZED
    assert resolved.enclave_warrant is not None
    assert len(queue.list_pending_mandates()) == 0


def test_operator_veto_from_mobile(dummy_enclave_keypair):
    _, x963_hex = dummy_enclave_keypair
    queue = AP2AsyncMobileQueue(pinned_enclave_pubkey_hex=x963_hex)

    mandate = queue.create_and_enqueue_mandate(
        task_id="task-veto-002",
        intent_caid="sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        spending_cap_minor=5000,
        allowed_rails=["X402"],
        attempt_fence=1,
    )

    ok, err, vetoed = queue.veto_mandate_from_mobile(
        mandate_id=mandate.mandate_id,
        reason="Operator rejected unexpected spending surge",
    )

    assert ok is True
    assert err == "OK"
    assert vetoed is not None
    assert vetoed.stage == AP2MandateStage.VETOED
    assert vetoed.veto_reason == "Operator rejected unexpected spending surge"
    assert len(queue.list_pending_mandates()) == 0


def test_mandate_expiration_and_purge(dummy_enclave_keypair):
    _, x963_hex = dummy_enclave_keypair
    queue = AP2AsyncMobileQueue(pinned_enclave_pubkey_hex=x963_hex)

    m1 = queue.create_and_enqueue_mandate(
        task_id="task-exp-1",
        intent_caid="sha256:1111111111111111111111111111111111111111111111111111111111111111",
        spending_cap_minor=1000,
        allowed_rails=["LOCAL_ESCROW"],
        attempt_fence=1,
        ttl_seconds=60,
        current_epoch_sec=1700000000,
    )

    # Attempting to resolve past expiration fails closed
    ok, err, res = queue.resolve_with_hardware_warrant(
        mandate_id=m1.mandate_id,
        warrant_data={},
        current_epoch_sec=1700000061,
    )
    assert ok is False
    assert err == "ERR_MANDATE_EXPIRED"
    assert res is not None
    assert res.stage == AP2MandateStage.EXPIRED

    # Create another expiring mandate and test purge_expired
    m2 = queue.create_and_enqueue_mandate(
        task_id="task-exp-2",
        intent_caid="sha256:2222222222222222222222222222222222222222222222222222222222222222",
        spending_cap_minor=1000,
        allowed_rails=["LOCAL_ESCROW"],
        attempt_fence=1,
        ttl_seconds=100,
        current_epoch_sec=1700000000,
    )

    purged = queue.purge_expired(current_epoch_sec=1700000200)
    assert purged == 1
    assert queue.get_mandate(m2.mandate_id).stage == AP2MandateStage.EXPIRED


def test_input_validation(dummy_enclave_keypair):
    _, x963_hex = dummy_enclave_keypair

    with pytest.raises(ValueError, match="pinned_enclave_pubkey_hex"):
        AP2AsyncMobileQueue(pinned_enclave_pubkey_hex="")

    with pytest.raises(ValueError, match="spending_cap_minor"):
        AP2IntentMandate(
            mandate_id="m1",
            task_id="t1",
            intent_caid="sha256:0000000000000000000000000000000000000000000000000000000000000000",
            spending_cap_minor=0,
            allowed_rails=(),
            attempt_fence=1,
            expires_at_epoch_sec=1700000000,
        )

    with pytest.raises(ValueError, match="attempt_fence"):
        AP2IntentMandate(
            mandate_id="m2",
            task_id="t1",
            intent_caid="sha256:0000000000000000000000000000000000000000000000000000000000000000",
            spending_cap_minor=100,
            allowed_rails=(),
            attempt_fence=0,
            expires_at_epoch_sec=1700000000,
        )

    with pytest.raises(ValueError, match="intent_caid"):
        AP2IntentMandate(
            mandate_id="m3",
            task_id="t1",
            intent_caid="not_a_sha256",
            spending_cap_minor=100,
            allowed_rails=(),
            attempt_fence=1,
            expires_at_epoch_sec=1700000000,
        )

    with pytest.raises(ValueError, match="spending_cap_minor"):
        AP2IntentMandate(
            mandate_id="m4",
            task_id="t1",
            intent_caid="sha256:0000000000000000000000000000000000000000000000000000000000000000",
            spending_cap_minor=-1,
            allowed_rails=(),
            attempt_fence=1,
            expires_at_epoch_sec=1700000000,
        )

    with pytest.raises(ValueError, match="expires_at_epoch_sec"):
        AP2IntentMandate(
            mandate_id="m5",
            task_id="t1",
            intent_caid="sha256:0000000000000000000000000000000000000000000000000000000000000000",
            spending_cap_minor=100,
            allowed_rails=(),
            attempt_fence=1,
            expires_at_epoch_sec=0,
        )

    with pytest.raises(ValueError, match="expires_at_epoch_sec"):
        AP2IntentMandate(
            mandate_id="m6",
            task_id="t1",
            intent_caid="sha256:0000000000000000000000000000000000000000000000000000000000000000",
            spending_cap_minor=100,
            allowed_rails=(),
            attempt_fence=1,
            expires_at_epoch_sec=-1,
        )


def test_rejections_and_tamper_branches(dummy_enclave_keypair):
    priv, x963_hex = dummy_enclave_keypair
    queue = AP2AsyncMobileQueue(pinned_enclave_pubkey_hex=x963_hex)

    # Unknown mandate
    ok, err, res = queue.resolve_with_hardware_warrant("unknown-id", {})
    assert ok is False
    assert err == "ERR_MANDATE_NOT_FOUND"
    assert res is None

    ok_v, err_v, res_v = queue.veto_mandate_from_mobile("unknown-id", "none")
    assert ok_v is False
    assert err_v == "ERR_MANDATE_NOT_FOUND"
    assert res_v is None

    # Frozen dataclass enforcement
    m = queue.create_and_enqueue_mandate(
        task_id="task-frozen",
        intent_caid="sha256:1111111111111111111111111111111111111111111111111111111111111111",
        spending_cap_minor=500,
        allowed_rails=["X402"],
        attempt_fence=1,
        current_epoch_sec=1700000000,
    )
    caid = m.compute_mandate_caid()
    assert isinstance(caid, str) and caid.startswith("sha256:")

    with pytest.raises((AttributeError, TypeError)):
        m.spending_cap_minor = 9999  # type: ignore

    # Enclave verification failure (corrupted signature)
    proposal = T3ActionProposal(
        action_type="AP2_PAYMENT_MANDATE",
        amount_minor=500,
        attempt_fence=1,
        expires_at_epoch_sec=1700000000 + 3600,
        intent_caid="sha256:1111111111111111111111111111111111111111111111111111111111111111",
        operation_id=m.mandate_id,
        target_resource="task-frozen",
    )
    raw_utf8 = proposal.to_canonical_jcs_bytes().decode("utf-8")
    sig_der = priv.sign(raw_utf8.encode("utf-8"), ec.ECDSA(hashes.SHA256()))

    # Corrupt signature
    corrupt_sig = bytearray(sig_der)
    corrupt_sig[-1] ^= 0xFF
    warrant_dict = {
        "canonical_payload_utf8": raw_utf8,
        "payload_sha256_caid": sha256_jcs_caid(raw_utf8.encode("utf-8")),
        "public_key_x963_hex": x963_hex,
        "signature_der_hex": bytes(corrupt_sig).hex(),
        "algorithm": "ECDSA_P256_SHA256_SECURE_ENCLAVE",
    }
    ok_bad, err_bad, res_bad = queue.resolve_with_hardware_warrant(
        mandate_id=m.mandate_id,
        warrant_data=warrant_dict,
        current_epoch_sec=1700000010,
    )
    assert ok_bad is False
    assert "ERR_ENCLAVE_VERIFICATION_FAILED" in err_bad
    assert res_bad.stage == AP2MandateStage.PENDING_MOBILE_AUTHORIZATION

    # Now resolve with valid warrant
    warrant_valid = {
        "canonical_payload_utf8": raw_utf8,
        "payload_sha256_caid": sha256_jcs_caid(raw_utf8.encode("utf-8")),
        "public_key_x963_hex": x963_hex,
        "signature_der_hex": sig_der.hex(),
        "algorithm": "ECDSA_P256_SHA256_SECURE_ENCLAVE",
    }
    ok_good, err_good, res_good = queue.resolve_with_hardware_warrant(
        mandate_id=m.mandate_id,
        warrant_data=warrant_valid,
        current_epoch_sec=1700000010,
    )
    assert ok_good is True
    assert res_good.stage == AP2MandateStage.CLOSED_AUTHORIZED

    # Re-resolving already closed mandate fails closed with stage error
    ok_re, err_re, res_re = queue.resolve_with_hardware_warrant(
        mandate_id=m.mandate_id,
        warrant_data=warrant_valid,
        current_epoch_sec=1700000015,
    )
    assert ok_re is False
    assert err_re == "ERR_INVALID_MANDATE_STAGE_CLOSED_AUTHORIZED"
