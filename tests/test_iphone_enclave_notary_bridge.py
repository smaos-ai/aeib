#!/usr/bin/env python3
"""Zero-Mock Falsification Suite for Mac <-> iPhone Secure Enclave Notary Bridge.

Proves:
1. Genuine NIST P-256 (SECP256R1) ECDSA-SHA256 signature over exact RFC 8785 JCS
   bytes releases the T3 execution latch.
2. WYSIWYS anti-bait-and-switch enforcement blocks any post-approval substitution.
3. Temporal expiration and unpinned public keys fail closed.
4. Cryptographic corruption (signature tampering or algorithm substitution) is rejected.
"""

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from src.iphone_enclave_notary_bridge import (
    EnclaveSignedWarrant,
    MacEnclaveNotaryVerifier,
    T3ActionProposal,
    sha256_jcs_caid,
)


def _generate_p256_keypair_and_sign(payload_bytes: bytes):
    priv_key = ec.generate_private_key(ec.SECP256R1())
    pub_x963_hex = (
        priv_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )
        .hex()
    )
    sig_der_hex = priv_key.sign(payload_bytes, ec.ECDSA(hashes.SHA256())).hex()
    return priv_key, pub_x963_hex, sig_der_hex


def test_1_valid_p256_enclave_warrant_releases_t3_latch() -> None:
    proposal = T3ActionProposal(
        operation_id="op_t3_db_drop_001",
        intent_caid="sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
        action_type="DATABASE_DROP_PRODUCTION",
        target_resource="postgres://prod-eu-01/ledger",
        amount_minor=0,
        attempt_fence=1,
        expires_at_epoch_sec=1_800_000_060,
    )
    canonical_bytes = proposal.to_canonical_jcs_bytes()
    _priv, pub_hex, sig_hex = _generate_p256_keypair_and_sign(canonical_bytes)

    warrant = EnclaveSignedWarrant(
        canonical_payload_utf8=canonical_bytes.decode("utf-8"),
        payload_sha256_caid=sha256_jcs_caid(canonical_bytes),
        public_key_x963_hex=pub_hex,
        signature_der_hex=sig_hex,
        algorithm="ECDSA_P256_SHA256_SECURE_ENCLAVE",
    )

    verdict = MacEnclaveNotaryVerifier.verify_warrant_and_release_latch(
        expected_proposal=proposal,
        warrant=warrant,
        pinned_enclave_pubkey_x963_hex=pub_hex,
        current_epoch_sec=1_800_000_010,
    )
    assert verdict.latch_released is True
    assert verdict.reason_code == "OK_FACEID_ENCLAVE_WARRANT_VERIFIED"
    assert verdict.warrant_receipt_caid.startswith("sha256:")
    assert verdict.verified_proposal_caid == sha256_jcs_caid(canonical_bytes)


def test_2_wysiwys_bait_and_switch_is_blocked() -> None:
    # Human saw and authorized a 50.00 EUR transaction on the iPhone
    benign_proposal = T3ActionProposal(
        operation_id="op_refund_01",
        intent_caid="sha256:1111",
        action_type="FINANCIAL_REFUND",
        target_resource="inv_1001",
        amount_minor=5000,
        attempt_fence=1,
        expires_at_epoch_sec=1_800_000_060,
    )
    benign_bytes = benign_proposal.to_canonical_jcs_bytes()
    _priv, pub_hex, sig_hex = _generate_p256_keypair_and_sign(benign_bytes)

    warrant = EnclaveSignedWarrant(
        canonical_payload_utf8=benign_bytes.decode("utf-8"),
        payload_sha256_caid=sha256_jcs_caid(benign_bytes),
        public_key_x963_hex=pub_hex,
        signature_der_hex=sig_hex,
        algorithm="ECDSA_P256_SHA256_SECURE_ENCLAVE",
    )

    # Malicious subagent attempts to release latch on a 500,000.00 EUR transfer
    tampered_proposal = T3ActionProposal(
        operation_id="op_refund_01",
        intent_caid="sha256:1111",
        action_type="FINANCIAL_REFUND",
        target_resource="inv_1001",
        amount_minor=50_000_000,
        attempt_fence=1,
        expires_at_epoch_sec=1_800_000_060,
    )
    verdict = MacEnclaveNotaryVerifier.verify_warrant_and_release_latch(
        expected_proposal=tampered_proposal,
        warrant=warrant,
        pinned_enclave_pubkey_x963_hex=pub_hex,
        current_epoch_sec=1_800_000_010,
    )
    assert verdict.latch_released is False
    assert verdict.reason_code == "HALT_WYSIWYS_PAYLOAD_MISMATCH"


def test_3_expired_warrant_fails_closed() -> None:
    proposal = T3ActionProposal(
        operation_id="op_02",
        intent_caid="sha256:2222",
        action_type="DEPLOY_PROD",
        target_resource="k8s://cluster-main",
        amount_minor=0,
        attempt_fence=2,
        expires_at_epoch_sec=1_800_000_000,
    )
    c_bytes = proposal.to_canonical_jcs_bytes()
    _priv, pub_hex, sig_hex = _generate_p256_keypair_and_sign(c_bytes)

    warrant = EnclaveSignedWarrant(
        canonical_payload_utf8=c_bytes.decode("utf-8"),
        payload_sha256_caid=sha256_jcs_caid(c_bytes),
        public_key_x963_hex=pub_hex,
        signature_der_hex=sig_hex,
        algorithm="ECDSA_P256_SHA256_SECURE_ENCLAVE",
    )

    verdict = MacEnclaveNotaryVerifier.verify_warrant_and_release_latch(
        expected_proposal=proposal,
        warrant=warrant,
        pinned_enclave_pubkey_x963_hex=pub_hex,
        current_epoch_sec=1_800_000_001,  # 1 second expired
    )
    assert verdict.latch_released is False
    assert verdict.reason_code == "HALT_FACEID_WARRANT_EXPIRED"


def test_4_unrecognized_key_fails_closed() -> None:
    proposal = T3ActionProposal(
        operation_id="op_03",
        intent_caid="sha256:3333",
        action_type="DELETE_BUCKET",
        target_resource="s3://backup",
        amount_minor=0,
        attempt_fence=1,
        expires_at_epoch_sec=1_800_000_060,
    )
    c_bytes = proposal.to_canonical_jcs_bytes()
    _priv, pub_hex, sig_hex = _generate_p256_keypair_and_sign(c_bytes)

    warrant = EnclaveSignedWarrant(
        canonical_payload_utf8=c_bytes.decode("utf-8"),
        payload_sha256_caid=sha256_jcs_caid(c_bytes),
        public_key_x963_hex=pub_hex,
        signature_der_hex=sig_hex,
        algorithm="ECDSA_P256_SHA256_SECURE_ENCLAVE",
    )

    rogue_pub_hex = "04" + "aa" * 64
    verdict = MacEnclaveNotaryVerifier.verify_warrant_and_release_latch(
        expected_proposal=proposal,
        warrant=warrant,
        pinned_enclave_pubkey_x963_hex=rogue_pub_hex,
        current_epoch_sec=1_800_000_010,
    )
    assert verdict.latch_released is False
    assert verdict.reason_code == "HALT_UNRECOGNIZED_ENCLAVE_PUBLIC_KEY"


def test_5_corrupted_signature_fails_closed() -> None:
    proposal = T3ActionProposal(
        operation_id="op_04",
        intent_caid="sha256:4444",
        action_type="RESTART_SERVICE",
        target_resource="systemd://gateway",
        amount_minor=0,
        attempt_fence=1,
        expires_at_epoch_sec=1_800_000_060,
    )
    c_bytes = proposal.to_canonical_jcs_bytes()
    _priv, pub_hex, sig_hex = _generate_p256_keypair_and_sign(c_bytes)

    # Flip the last byte of the DER signature
    sig_bytes = bytearray.fromhex(sig_hex)
    sig_bytes[-1] ^= 0x01
    corrupted_sig_hex = sig_bytes.hex()

    warrant = EnclaveSignedWarrant(
        canonical_payload_utf8=c_bytes.decode("utf-8"),
        payload_sha256_caid=sha256_jcs_caid(c_bytes),
        public_key_x963_hex=pub_hex,
        signature_der_hex=corrupted_sig_hex,
        algorithm="ECDSA_P256_SHA256_SECURE_ENCLAVE",
    )

    verdict = MacEnclaveNotaryVerifier.verify_warrant_and_release_latch(
        expected_proposal=proposal,
        warrant=warrant,
        pinned_enclave_pubkey_x963_hex=pub_hex,
        current_epoch_sec=1_800_000_010,
    )
    assert verdict.latch_released is False
    assert verdict.reason_code == "HALT_ENCLAVE_SIGNATURE_INVALID"


def test_6_unsupported_algorithm_rejected() -> None:
    proposal = T3ActionProposal(
        operation_id="op_05",
        intent_caid="sha256:5555",
        action_type="DRAIN_NODE",
        target_resource="k8s://worker-01",
        amount_minor=0,
        attempt_fence=1,
        expires_at_epoch_sec=1_800_000_060,
    )
    c_bytes = proposal.to_canonical_jcs_bytes()
    _priv, pub_hex, sig_hex = _generate_p256_keypair_and_sign(c_bytes)

    warrant = EnclaveSignedWarrant(
        canonical_payload_utf8=c_bytes.decode("utf-8"),
        payload_sha256_caid=sha256_jcs_caid(c_bytes),
        public_key_x963_hex=pub_hex,
        signature_der_hex=sig_hex,
        algorithm="ED25519_SOFTWARE_KEYCHAIN",  # Rejected algorithm
    )

    verdict = MacEnclaveNotaryVerifier.verify_warrant_and_release_latch(
        expected_proposal=proposal,
        warrant=warrant,
        pinned_enclave_pubkey_x963_hex=pub_hex,
        current_epoch_sec=1_800_000_010,
    )
    assert verdict.latch_released is False
    assert "HALT_UNSUPPORTED_ENCLAVE_ALGORITHM" in verdict.reason_code


def test_7_proposal_contract_validation() -> None:
    # Test all invalid field branches in __post_init__
    with pytest.raises(ValueError, match="ERR_INVALID_OPERATION_ID"):
        T3ActionProposal("", "sha256:1", "A", "T", 0, 1, 100)
    with pytest.raises(ValueError, match="ERR_INVALID_OPERATION_ID"):
        T3ActionProposal(123, "sha256:1", "A", "T", 0, 1, 100)  # type: ignore

    with pytest.raises(ValueError, match="ERR_INVALID_INTENT_CAID"):
        T3ActionProposal("op1", "", "A", "T", 0, 1, 100)
    with pytest.raises(ValueError, match="ERR_INVALID_INTENT_CAID"):
        T3ActionProposal("op1", None, "A", "T", 0, 1, 100)  # type: ignore

    with pytest.raises(ValueError, match="ERR_INVALID_ACTION_TYPE"):
        T3ActionProposal("op1", "sha256:1", "", "T", 0, 1, 100)
    with pytest.raises(ValueError, match="ERR_INVALID_ACTION_TYPE"):
        T3ActionProposal("op1", "sha256:1", 456, "T", 0, 1, 100)  # type: ignore

    with pytest.raises(ValueError, match="ERR_INVALID_TARGET_RESOURCE"):
        T3ActionProposal("op1", "sha256:1", "A", "", 0, 1, 100)
    with pytest.raises(ValueError, match="ERR_INVALID_TARGET_RESOURCE"):
        T3ActionProposal("op1", "sha256:1", "A", {}, 0, 1, 100)  # type: ignore

    with pytest.raises(ValueError, match="ERR_INVALID_AMOUNT_MINOR"):
        T3ActionProposal("op1", "sha256:1", "A", "T", -10, 1, 100)
    with pytest.raises(ValueError, match="ERR_INVALID_AMOUNT_MINOR"):
        T3ActionProposal("op1", "sha256:1", "A", "T", True, 1, 100)  # type: ignore

    with pytest.raises(ValueError, match="ERR_INVALID_ATTEMPT_FENCE"):
        T3ActionProposal("op1", "sha256:1", "A", "T", 100, 0, 100)
    with pytest.raises(ValueError, match="ERR_INVALID_ATTEMPT_FENCE"):
        T3ActionProposal("op1", "sha256:1", "A", "T", 100, -1, 100)

    with pytest.raises(ValueError, match="ERR_INVALID_EXPIRES_AT_EPOCH_SEC"):
        T3ActionProposal("op1", "sha256:1", "A", "T", 100, 1, 0)
    with pytest.raises(ValueError, match="ERR_INVALID_EXPIRES_AT_EPOCH_SEC"):
        T3ActionProposal("op1", "sha256:1", "A", "T", 100, 1, -5)


def test_8_caid_mismatch_fails_closed() -> None:
    proposal = T3ActionProposal(
        operation_id="op_08",
        intent_caid="sha256:8888",
        action_type="PURGE_CACHE",
        target_resource="redis://main",
        amount_minor=0,
        attempt_fence=1,
        expires_at_epoch_sec=1_800_000_060,
    )
    c_bytes = proposal.to_canonical_jcs_bytes()
    _priv, pub_hex, sig_hex = _generate_p256_keypair_and_sign(c_bytes)

    warrant = EnclaveSignedWarrant(
        canonical_payload_utf8=c_bytes.decode("utf-8"),
        payload_sha256_caid="sha256:0000000000000000000000000000000000000000000000000000000000000000",
        public_key_x963_hex=pub_hex,
        signature_der_hex=sig_hex,
        algorithm="ECDSA_P256_SHA256_SECURE_ENCLAVE",
    )

    verdict = MacEnclaveNotaryVerifier.verify_warrant_and_release_latch(
        expected_proposal=proposal,
        warrant=warrant,
        pinned_enclave_pubkey_x963_hex=pub_hex,
        current_epoch_sec=1_800_000_010,
    )
    assert verdict.latch_released is False
    assert verdict.reason_code == "HALT_WARRANT_CAID_MISMATCH"


def test_9_sha256_jcs_caid_type_variants() -> None:
    assert sha256_jcs_caid(b"hello").startswith("sha256:")
    assert sha256_jcs_caid("hello").startswith("sha256:")
    assert sha256_jcs_caid({"a": 1}).startswith("sha256:")
    assert sha256_jcs_caid(b"hello") == sha256_jcs_caid("hello")
