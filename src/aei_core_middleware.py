#!/usr/bin/env python3
"""
aei_core_middleware.py — Agent Effect Integrity Core Middleware (Research Prototype)

DISCLAIMER: RESEARCH PROTOTYPE ONLY
------------------------------------
This module is a scoped research prototype developed to evaluate a single, concrete
software failure mode in autonomous agent systems: preventing duplicate execution
state during ambiguous transport drops (e.g., HTTP 504 Gateway Timeout or TCP drops).

Defensive Scope Boundaries:
- Out of scope: eBPF kernel hooks, hardware enclave (TEE) attestation, BBS+ ZK schemes,
  and regulatory or legal compliance assertions.
- In scope: Transport state interposition, idempotency key binding, fail-closed loop
  halting (disposition: UNKNOWN), out-of-band probe verification, and RFC 8785 (JCS)
  canonical payload signing via Ed25519.

Mechanisms:
1. Wrap outbound mutating tool dispatches with an explicit action_id and idempotency_key.
2. Intercept transport-level drop/504 errors.
3. Halt the agent execution loop with disposition: UNKNOWN (retry_permitted: False).
4. Trigger an authoritative out-of-band probe against the target ledger/datastore.
5. If committed, upgrade to OUTCOME_VERIFIED (retry_permitted: False), preventing duplicates.
6. Emit and cryptographically sign the disposition record using JCS + Ed25519.
"""

import json
import hashlib
from typing import Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass, asdict
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature


class DuplicateExecutionBlockedError(Exception):
    """Raised when an ambiguous drop occurred and out-of-band probe verified mutation committed."""
    def __init__(self, message: str, receipt: Dict[str, Any]):
        super().__init__(message)
        self.receipt = receipt


class TransportDropException(Exception):
    """Simulated or caught transport drop (e.g., HTTP 504 Gateway Timeout, TCP RST)."""
    def __init__(self, status_code: int = 504, message: str = "HTTP 504 Gateway Timeout"):
        super().__init__(message)
        self.status_code = status_code


def jcs_canonicalize(data: Dict[str, Any]) -> bytes:
    """
    RFC 8785 JSON Canonicalization Scheme (JCS).
    Lexicographical UTF-16 code unit sorting, compact separators, no extra whitespace.
    """
    return json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def generate_keypair() -> Tuple[Ed25519PrivateKey, str]:
    """Generates an Ed25519 keypair, returning the private key and hex-encoded public key."""
    priv = Ed25519PrivateKey.generate()
    pub_bytes = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    return priv, pub_bytes.hex()


@dataclass
class DispositionReceipt:
    version: str
    action_id: str
    idempotency_key: str
    disposition: str
    retry_permitted: bool
    wire_status: str
    probe_performed: bool
    probe_result: Optional[str]
    payload_hash: str
    signature: str
    public_key_hex: str
    canonical_payload: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AeiCoreMiddleware:
    """
    Middleware wrapper enforcing fail-closed reconciliation for agent tool calls.
    """

    def __init__(self, private_key: Optional[Ed25519PrivateKey] = None):
        if private_key is None:
            self.private_key, self.public_key_hex = generate_keypair()
        else:
            self.private_key = private_key
            self.public_key_hex = self.private_key.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            ).hex()
        # In-memory registry of resolved action disposition receipts
        self.disposition_history: Dict[str, DispositionReceipt] = {}

    def execute_with_guard(
        self,
        action_id: str,
        idempotency_key: str,
        tool_dispatch_fn: Callable[[], Any],
        out_of_band_probe_fn: Callable[[str], Optional[Dict[str, Any]]]
    ) -> Tuple[Any, DispositionReceipt]:
        """
        Executes a mutating tool call under the AEI Core boundary.

        Args:
            action_id: Unique identifier for the agent invocation.
            idempotency_key: Deterministic key sent with mutating request.
            tool_dispatch_fn: Callable executing the downstream network dispatch.
            out_of_band_probe_fn: Authoritative probe callable accepting idempotency_key,
                                  returning state dict if committed, None if uncommitted.

        Returns:
            Tuple of (tool_result, disposition_receipt) if nominal.

        Raises:
            DuplicateExecutionBlockedError: If transport dropped but probe verified prior commit.
            RuntimeError / Exception: If uncommitted or other terminal error.
        """
        # Pre-dispatch defense: If idempotency_key has already been resolved and retry is forbidden, block immediately
        if idempotency_key in self.disposition_history:
            prior = self.disposition_history[idempotency_key]
            if not prior.retry_permitted:
                raise DuplicateExecutionBlockedError(
                    f"Prior execution already verified for idempotency_key '{idempotency_key}' "
                    f"with disposition '{prior.disposition}'. Duplicate dispatch rejected.",
                    receipt=prior.to_dict()
                )
        try:
            # 1. Dispatch mutating action across transport
            result = tool_dispatch_fn()

            # Nominal success
            receipt = self._create_signed_receipt(
                action_id=action_id,
                idempotency_key=idempotency_key,
                disposition="CONFIRMED",
                retry_permitted=False,
                wire_status="200_OK",
                probe_performed=False,
                probe_result=None
            )
            self.disposition_history[idempotency_key] = receipt
            return result, receipt

        except TransportDropException as drop:
            # 2. Halt agent loop at ambiguous disposition: UNKNOWN
            # Under fail-closed boundary, retry is prohibited until probe completes.
            probe_record = out_of_band_probe_fn(idempotency_key)

            if probe_record is not None:
                # 3. Probe confirms row was committed before the transport dropped
                receipt = self._create_signed_receipt(
                    action_id=action_id,
                    idempotency_key=idempotency_key,
                    disposition="OUTCOME_VERIFIED",
                    retry_permitted=False,
                    wire_status=f"HTTP_{drop.status_code}_DROP",
                    probe_performed=True,
                    probe_result="COMMITTED"
                )
                self.disposition_history[idempotency_key] = receipt
                # 4. Prohibit duplicate dispatch
                raise DuplicateExecutionBlockedError(
                    f"Ambiguous {drop.status_code} drop intercepted. Out-of-band probe confirmed "
                    f"mutation committed for idempotency_key '{idempotency_key}'. "
                    f"Duplicate execution blocked.",
                    receipt=receipt.to_dict()
                )
            else:
                # Probe confirms mutation was NOT committed
                receipt = self._create_signed_receipt(
                    action_id=action_id,
                    idempotency_key=idempotency_key,
                    disposition="RECONCILIATION_NOT_FOUND",
                    retry_permitted=True,
                    wire_status=f"HTTP_{drop.status_code}_DROP",
                    probe_performed=True,
                    probe_result="NOT_COMMITTED"
                )
                raise RuntimeError(
                    f"Ambiguous {drop.status_code} drop intercepted. Probe confirmed uncommitted. "
                    f"Safe retry permitted with identical idempotency_key."
                )

    def _create_signed_receipt(
        self,
        action_id: str,
        idempotency_key: str,
        disposition: str,
        retry_permitted: bool,
        wire_status: str,
        probe_performed: bool,
        probe_result: Optional[str]
    ) -> DispositionReceipt:
        """Constructs JCS canonical payload, SHA-256 digest, and Ed25519 signature."""
        statement = {
            "version": "0.3.0-prototype",
            "action_id": action_id,
            "idempotency_key": idempotency_key,
            "disposition": disposition,
            "retry_permitted": retry_permitted,
            "wire_status": wire_status,
            "probe_performed": probe_performed,
            "probe_result": probe_result
        }

        canonical_bytes = jcs_canonicalize(statement)
        payload_hash = hashlib.sha256(canonical_bytes).hexdigest()
        signature = self.private_key.sign(canonical_bytes)

        return DispositionReceipt(
            version="0.3.0-prototype",
            action_id=action_id,
            idempotency_key=idempotency_key,
            disposition=disposition,
            retry_permitted=retry_permitted,
            wire_status=wire_status,
            probe_performed=probe_performed,
            probe_result=probe_result,
            payload_hash=f"sha256:{payload_hash}",
            signature=signature.hex(),
            public_key_hex=self.public_key_hex,
            canonical_payload=canonical_bytes.decode('utf-8')
        )


def verify_disposition_receipt(receipt_dict: Dict[str, Any]) -> bool:
    """
    Offline verification of a DispositionReceipt.

    Guarantees:
    - Canonical payload matches payload_hash exactly.
    - Ed25519 signature is cryptographically valid over the canonical payload.
    - Re-canonicalization of canonical_payload JSON string matches byte-for-byte.

    Returns:
        True if valid.

    Raises:
        ValueError: If payload hash mismatches or structure is tampered.
        InvalidSignature: If cryptographic signature verification fails.
    """
    canonical_payload_str = receipt_dict.get("canonical_payload", "")
    expected_hash = receipt_dict.get("payload_hash", "").replace("sha256:", "")
    sig_hex = receipt_dict.get("signature", "")
    pub_hex = receipt_dict.get("public_key_hex", "")

    if not (canonical_payload_str and expected_hash and sig_hex and pub_hex):
        raise ValueError("Receipt missing required cryptographic verification fields")

    # 1. Parse and re-canonicalize to guarantee JCS compliance
    payload_obj = json.loads(canonical_payload_str)
    re_canonical_bytes = jcs_canonicalize(payload_obj)

    # 2. Check SHA-256 digest
    computed_hash = hashlib.sha256(re_canonical_bytes).hexdigest()
    if computed_hash != expected_hash:
        raise ValueError(
            f"Digest mismatch! Computed sha256:{computed_hash} != declared sha256:{expected_hash}"
        )

    # 3. Check byte-exactness of stored canonical_payload
    if canonical_payload_str.encode('utf-8') != re_canonical_bytes:
        raise ValueError("Canonical payload byte representation drift detected")

    # 4. Verify Ed25519 signature
    pub_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub_hex))
    pub_key.verify(bytes.fromhex(sig_hex), re_canonical_bytes)

    return True
