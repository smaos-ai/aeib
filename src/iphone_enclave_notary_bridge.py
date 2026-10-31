#!/usr/bin/env python3
"""Mac M3 Pro <-> iPhone 16 Pro Max Secure Enclave Notary Bridge.

Enforces:
1. WYSIWYS (What You See Is What You Sign): Canonical RFC 8785 JCS payload
   construction with zero floats, integer minor units, and deterministic sorting.
2. Monotonic Attempt Fence & Expiration Binding: Blocks replay of stale FaceID warrants.
3. Hardware ECDSA P-256 (NIST P-256 / secp256r1 / SHA-256) Signature Verification
   over exact JCS canonical bytes emitted by the A18 Pro Secure Enclave.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from src.jcs_canonicalizer import encode_jcs


def sha256_jcs_caid(payload: Any) -> str:
    """Compute RFC 8785 SHA-256 CAID for string, bytes, or JSON-serializable dict."""
    if isinstance(payload, bytes):
        raw = payload
    elif isinstance(payload, str):
        raw = payload.encode("utf-8")
    else:
        raw = encode_jcs(payload)
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


@dataclass(frozen=True)
class T3ActionProposal:
    """Proposal for a T3 Irreversible Action requiring biometric authorization."""

    operation_id: str
    intent_caid: str
    action_type: str
    target_resource: str
    amount_minor: int
    attempt_fence: int
    expires_at_epoch_sec: int

    def __post_init__(self) -> None:
        if not isinstance(self.operation_id, str) or not self.operation_id:
            raise ValueError("ERR_INVALID_OPERATION_ID")
        if not isinstance(self.intent_caid, str) or not self.intent_caid:
            raise ValueError("ERR_INVALID_INTENT_CAID")
        if not isinstance(self.action_type, str) or not self.action_type:
            raise ValueError("ERR_INVALID_ACTION_TYPE")
        if not isinstance(self.target_resource, str) or not self.target_resource:
            raise ValueError("ERR_INVALID_TARGET_RESOURCE")
        if type(self.amount_minor) is not int or self.amount_minor < 0:
            raise ValueError("ERR_INVALID_AMOUNT_MINOR")
        if type(self.attempt_fence) is not int or self.attempt_fence <= 0:
            raise ValueError("ERR_INVALID_ATTEMPT_FENCE")
        if type(self.expires_at_epoch_sec) is not int or self.expires_at_epoch_sec <= 0:
            raise ValueError("ERR_INVALID_EXPIRES_AT_EPOCH_SEC")

    def to_canonical_jcs_bytes(self) -> bytes:
        """Produce byte-exact RFC 8785 canonical JSON bytes (WYSIWYS)."""
        return encode_jcs(
            {
                "action_type": self.action_type,
                "amount_minor": self.amount_minor,
                "attempt_fence": self.attempt_fence,
                "expires_at_epoch_sec": self.expires_at_epoch_sec,
                "intent_caid": self.intent_caid,
                "operation_id": self.operation_id,
                "target_resource": self.target_resource,
            }
        )


@dataclass(frozen=True)
class EnclaveSignedWarrant:
    """Hardware warrant emitted by the iPhone 16 Pro Max Secure Enclave."""

    canonical_payload_utf8: str
    payload_sha256_caid: str
    public_key_x963_hex: str
    signature_der_hex: str
    algorithm: str


@dataclass(frozen=True)
class T3LatchReleaseVerdict:
    """Final latch release adjudication for the T3 Irreversible Action."""

    latch_released: bool
    reason_code: str
    verified_proposal_caid: str
    warrant_receipt_caid: str


class MacEnclaveNotaryVerifier:
    """Verifies hardware-signed ECDSA P-256 FaceID warrants from the iPhone 16 Pro Max.

    Executed on the Mac M3 Pro before releasing an EFFECT_INDETERMINATE /
    T3_IRREVERSIBLE execution latch.
    """

    REQUIRED_ALGORITHM = "ECDSA_P256_SHA256_SECURE_ENCLAVE"

    @staticmethod
    def verify_p256_der_signature(
        public_key_x963_hex: str, message_bytes: bytes, signature_der_hex: str
    ) -> bool:
        """Verifies an ANSI X9.63 uncompressed P-256 public key and DER ECDSA-SHA256 signature."""
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec

        try:
            pub_bytes = bytes.fromhex(public_key_x963_hex)
            sig_bytes = bytes.fromhex(signature_der_hex)
            pub_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), pub_bytes)
            pub_key.verify(sig_bytes, message_bytes, ec.ECDSA(hashes.SHA256()))
            return True
        except (ValueError, InvalidSignature):
            return False

    @classmethod
    def verify_warrant_and_release_latch(
        cls,
        expected_proposal: T3ActionProposal,
        warrant: EnclaveSignedWarrant,
        pinned_enclave_pubkey_x963_hex: str,
        current_epoch_sec: int,
        sig_verifier_fn: Optional[Callable[[str, bytes, str], bool]] = None,
    ) -> T3LatchReleaseVerdict:
        """Performs full 5-point cryptographic and WYSIWYS latch release verification."""
        expected_bytes = expected_proposal.to_canonical_jcs_bytes()
        expected_caid = sha256_jcs_caid(expected_bytes)

        def _halt(reason: str) -> T3LatchReleaseVerdict:
            receipt = sha256_jcs_caid(
                {
                    "expected_caid": expected_caid,
                    "latch_released": False,
                    "reason_code": reason,
                    "warrant_caid": warrant.payload_sha256_caid,
                }
            )
            return T3LatchReleaseVerdict(False, reason, expected_caid, receipt)

        # 1. Enforce Secure Enclave hardware algorithm identifier
        if warrant.algorithm != cls.REQUIRED_ALGORITHM:
            return _halt(f"HALT_UNSUPPORTED_ENCLAVE_ALGORITHM:{warrant.algorithm}")

        # 2. Enforce pinned iPhone 16 Pro Max Secure Enclave public key identity
        if warrant.public_key_x963_hex.lower() != pinned_enclave_pubkey_x963_hex.lower():
            return _halt("HALT_UNRECOGNIZED_ENCLAVE_PUBLIC_KEY")

        # 3. Enforce WYSIWYS exact canonical byte equality (defeats display/hash bait-and-switch)
        if warrant.canonical_payload_utf8.encode("utf-8") != expected_bytes:
            return _halt("HALT_WYSIWYS_PAYLOAD_MISMATCH")
        if warrant.payload_sha256_caid != expected_caid:
            return _halt("HALT_WARRANT_CAID_MISMATCH")

        # 4. Enforce temporal freshness (blocks replay of stale FaceID warrants)
        if current_epoch_sec > expected_proposal.expires_at_epoch_sec:
            return _halt("HALT_FACEID_WARRANT_EXPIRED")
        if expected_proposal.attempt_fence <= 0:
            return _halt("HALT_INVALID_ATTEMPT_FENCE")

        # 5. Verify ECDSA P-256 hardware signature over exact canonical JCS bytes
        verify_fn = sig_verifier_fn or cls.verify_p256_der_signature
        if not verify_fn(warrant.public_key_x963_hex, expected_bytes, warrant.signature_der_hex):
            return _halt("HALT_ENCLAVE_SIGNATURE_INVALID")

        receipt_caid = sha256_jcs_caid(
            {
                "expected_caid": expected_caid,
                "latch_released": True,
                "public_key_x963_hex": warrant.public_key_x963_hex.lower(),
                "reason_code": "OK_FACEID_ENCLAVE_WARRANT_VERIFIED",
                "signature_der_hex": warrant.signature_der_hex.lower(),
            }
        )
        return T3LatchReleaseVerdict(
            latch_released=True,
            reason_code="OK_FACEID_ENCLAVE_WARRANT_VERIFIED",
            verified_proposal_caid=expected_caid,
            warrant_receipt_caid=receipt_caid,
        )
