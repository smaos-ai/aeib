#!/usr/bin/env python3
"""
rail_mandate_and_mcp_taint_interlock.py — Layer 3 Agentic Payment Rail Interop
(Google AP2, Linux Foundation / Coinbase x402 v2, Stripe / OpenAI ACP) and
MCP Tool Provenance Taint Ceiling Governor (AT63 & AT64).

Evaluated under the stated model as a Layer 2.5 execution interlock prototype.
All cryptographic operations use real Ed25519 asymmetric primitives
(cryptography.hazmat.primitives.asymmetric.ed25519), SHA-256 digests, and
strict RFC 8785 JSON Canonicalization Scheme (src.jcs_canonicalizer.encode_jcs).
"""

from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Union

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.jcs_canonicalizer import encode_jcs


# ============================================================================
# Shared Helpers & Unified COSE_Sign1-Compatible Receipt Builder
# ============================================================================

def sha256_prefixed(data: bytes) -> str:
    """Returns 'sha256:<hex>' digest over raw bytes."""
    return "sha256:" + hashlib.sha256(data).hexdigest()


def compute_jcs_caid(payload: Any) -> str:
    """Computes deterministic RFC 8785 JCS content-addressable identifier."""
    return sha256_prefixed(encode_jcs(payload))


def derive_rail_idempotency_key(operation_id: str, action_caid: str) -> str:
    """
    Derives deterministic AEIB wire idempotency key:
    aeib-idem-v1-<sha256(operation_id:action_caid)[:32]>
    """
    material = f"{operation_id}:{action_caid}".encode("utf-8")
    digest_prefix = hashlib.sha256(material).hexdigest()[:32]
    return f"aeib-idem-v1-{digest_prefix}"


def sign_jcs_payload(
    private_key: Union[Ed25519PrivateKey, ec.EllipticCurvePrivateKey],
    payload: Dict[str, Any],
) -> str:
    """Signs a dictionary (excluding any 'signature_b64' key) with Ed25519 or ECDSA P-256 over RFC 8785 JCS."""
    unsigned = {k: v for k, v in payload.items() if k != "signature_b64"}
    canonical = encode_jcs(unsigned)
    if isinstance(private_key, Ed25519PrivateKey):
        sig = private_key.sign(canonical)
    elif isinstance(private_key, ec.EllipticCurvePrivateKey):
        sig = private_key.sign(canonical, ec.ECDSA(hashes.SHA256()))
    else:
        raise TypeError(f"Unsupported key type for signing: {type(private_key).__name__}")
    return base64.b64encode(sig).decode("ascii")


def verify_jcs_signature(
    public_key: Union[Ed25519PublicKey, ec.EllipticCurvePublicKey],
    payload: Dict[str, Any],
    signature_field: str = "signature_b64",
) -> bool:
    """Verifies an Ed25519 or ECDSA P-256 signature over the RFC 8785 JCS representation of payload."""
    sig_b64 = payload.get(signature_field)
    if not isinstance(sig_b64, str) or not sig_b64:
        return False
    unsigned = {k: v for k, v in payload.items() if k != signature_field}
    try:
        sig_bytes = base64.b64decode(sig_b64, validate=True)
        canonical = encode_jcs(unsigned)
        if isinstance(public_key, Ed25519PublicKey):
            public_key.verify(sig_bytes, canonical)
            return True
        elif isinstance(public_key, ec.EllipticCurvePublicKey):
            public_key.verify(sig_bytes, canonical, ec.ECDSA(hashes.SHA256()))
            return True
        return False
    except (InvalidSignature, ValueError, TypeError):
        return False


def build_cose_sign1_rail_receipt(
    interlock_private_key: Ed25519PrivateKey,
    rail_type: str,
    operation_id: str,
    action_caid: str,
    mandate_digests: Dict[str, str],
    extra_claims: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Emits an RFC 9052 COSE_Sign1-compatible envelope binding the Layer 3 rail
    mandate digests, deterministic rail_idempotency_key, and Ed25519 signature.
    """
    rail_idempotency_key = derive_rail_idempotency_key(operation_id, action_caid)
    protected_header = {
        "alg": "EdDSA",
        "crv": "Ed25519",
        "typ": "application/aeib-cose-sign1+json",
    }
    payload_claims: Dict[str, Any] = {
        "action_caid": action_caid,
        "mandate_digests": mandate_digests,
        "operation_id": operation_id,
        "rail_idempotency_key": rail_idempotency_key,
        "rail_type": rail_type,
    }
    if extra_claims:
        payload_claims.update(extra_claims)

    sig_structure = {
        "context": "Signature1",
        "body_protected": protected_header,
        "external_aad": "",
        "payload": payload_claims,
    }
    to_be_signed = encode_jcs(sig_structure)
    signature_bytes = interlock_private_key.sign(to_be_signed)
    return {
        "cose_version": "RFC9052-COSE_Sign1",
        "protected": protected_header,
        "payload": payload_claims,
        "rail_idempotency_key": rail_idempotency_key,
        "receipt_caid": sha256_prefixed(to_be_signed),
        "signature_b64": base64.b64encode(signature_bytes).decode("ascii"),
    }


def verify_cose_sign1_rail_receipt(
    interlock_public_key: Ed25519PublicKey,
    receipt: Dict[str, Any],
) -> bool:
    """Verifies an AEIB COSE_Sign1-compatible rail receipt."""
    try:
        sig_structure = {
            "context": "Signature1",
            "body_protected": receipt["protected"],
            "external_aad": "",
            "payload": receipt["payload"],
        }
        to_be_signed = encode_jcs(sig_structure)
        sig_bytes = base64.b64decode(receipt["signature_b64"], validate=True)
        interlock_public_key.verify(sig_bytes, to_be_signed)
        return sha256_prefixed(to_be_signed) == receipt.get("receipt_caid")
    except (KeyError, InvalidSignature, ValueError, TypeError):
        return False


# ============================================================================
# 1. Google AP2 (Agent Payments Protocol) 3-Tier Mandate Verifier
# ============================================================================

class AP2MandateChainVerifier:
    """
    Verifies the 3-tier Google AP2 mandate chain:
      IntentMandate -> CartMandate -> PaymentMandate
    and co-signs an AEIB COSE_Sign1 receipt with deterministic Idempotency-Key.
    """

    def __init__(self, interlock_private_key: Ed25519PrivateKey) -> None:
        self._interlock_private_key = interlock_private_key

    def verify_and_cosign(
        self,
        intent_mandate: Dict[str, Any],
        cart_mandate: Dict[str, Any],
        payment_mandate: Dict[str, Any],
        user_public_key: Union[Ed25519PublicKey, ec.EllipticCurvePublicKey],
        cart_signer_public_key: Union[Ed25519PublicKey, ec.EllipticCurvePublicKey],
        agent_public_key: Union[Ed25519PublicKey, ec.EllipticCurvePublicKey],
        operation_id: str,
        action_payload: Dict[str, Any],
        current_timestamp: int,
    ) -> Dict[str, Any]:
        # 1. Verify cryptographic signatures on all 3 mandates
        if not verify_jcs_signature(user_public_key, intent_mandate):
            return {
                "allowed": False,
                "status": "HALT_AP2_MANDATE_SIGNATURE_INVALID",
                "failed_tier": "IntentMandate",
            }
        if not verify_jcs_signature(cart_signer_public_key, cart_mandate):
            return {
                "allowed": False,
                "status": "HALT_AP2_MANDATE_SIGNATURE_INVALID",
                "failed_tier": "CartMandate",
            }
        if not verify_jcs_signature(agent_public_key, payment_mandate):
            return {
                "allowed": False,
                "status": "HALT_AP2_MANDATE_SIGNATURE_INVALID",
                "failed_tier": "PaymentMandate",
            }

        # 2. Verify parentIntentId and parentCartId lineage
        intent_id = intent_mandate.get("id")
        cart_id = cart_mandate.get("id")
        if (
            not intent_id
            or cart_mandate.get("parentIntentId") != intent_id
            or payment_mandate.get("parentIntentId") != intent_id
            or payment_mandate.get("parentCartId") != cart_id
        ):
            return {
                "allowed": False,
                "status": "HALT_AP2_MANDATE_LINEAGE_MISMATCH",
            }

        # 3. Verify expiry freshness across the chain
        for tier_name, mandate in (
            ("IntentMandate", intent_mandate),
            ("CartMandate", cart_mandate),
            ("PaymentMandate", payment_mandate),
        ):
            expires_at = int(mandate.get("expiresAt", 0))
            if current_timestamp > expires_at:
                return {
                    "allowed": False,
                    "status": "HALT_AP2_MANDATE_EXPIRED",
                    "failed_tier": tier_name,
                }

        # 4. Verify allowedMerchants constraint
        allowed_merchants = intent_mandate.get("allowedMerchants", [])
        cart_merchant = cart_mandate.get("merchant")
        payment_merchant = payment_mandate.get("merchant")
        if (
            not isinstance(allowed_merchants, list)
            or cart_merchant not in allowed_merchants
            or payment_merchant != cart_merchant
        ):
            return {
                "allowed": False,
                "status": "HALT_AP2_MERCHANT_NOT_ALLOWED",
                "merchant": cart_merchant,
            }

        # 5. Verify SKU items sum == CartMandate.amount.value == PaymentMandate.amount.value
        items = cart_mandate.get("items", [])
        if not isinstance(items, list) or not items:
            return {
                "allowed": False,
                "status": "HALT_AP2_SKU_TOTAL_MISMATCH",
            }

        computed_sku_sum = 0
        for item in items:
            price = item.get("price")
            qty = item.get("quantity")
            if not isinstance(price, int) or not isinstance(qty, int) or price < 0 or qty <= 0:
                return {
                    "allowed": False,
                    "status": "HALT_AP2_SKU_TOTAL_MISMATCH",
                }
            computed_sku_sum += price * qty

        cart_amount_obj = cart_mandate.get("amount", {})
        payment_amount_obj = payment_mandate.get("amount", {})
        cart_value = cart_amount_obj.get("value")
        payment_value = payment_amount_obj.get("value")
        intent_currency = intent_mandate.get("currency", "USD")

        if (
            cart_amount_obj.get("currency") != intent_currency
            or payment_amount_obj.get("currency") != intent_currency
            or computed_sku_sum != cart_value
            or payment_value != cart_value
        ):
            return {
                "allowed": False,
                "status": "HALT_AP2_SKU_TOTAL_MISMATCH",
                "computed_sku_sum": computed_sku_sum,
                "cart_value": cart_value,
                "payment_value": payment_value,
            }

        # 6. Verify amountLimit ceiling
        amount_limit = intent_mandate.get("amountLimit")
        if not isinstance(amount_limit, int) or computed_sku_sum > amount_limit:
            return {
                "allowed": False,
                "status": "HALT_AP2_CART_EXCEEDS_INTENT_LIMIT",
                "cart_value": computed_sku_sum,
                "amount_limit": amount_limit,
            }

        action_caid = compute_jcs_caid(action_payload)
        mandate_digests = {
            "intent_mandate_caid": compute_jcs_caid(intent_mandate),
            "cart_mandate_caid": compute_jcs_caid(cart_mandate),
            "payment_mandate_caid": compute_jcs_caid(payment_mandate),
        }
        cose_receipt = build_cose_sign1_rail_receipt(
            interlock_private_key=self._interlock_private_key,
            rail_type="GOOGLE_AP2",
            operation_id=operation_id,
            action_caid=action_caid,
            mandate_digests=mandate_digests,
            extra_claims={
                "merchant": cart_merchant,
                "verified_amount_minor": computed_sku_sum,
                "currency": intent_currency,
            },
        )
        return {
            "allowed": True,
            "status": "AP2_MANDATE_CHAIN_VERIFIED",
            "idempotency_key": cose_receipt["rail_idempotency_key"],
            "cose_receipt": cose_receipt,
        }


# ============================================================================
# 2. Linux Foundation / Coinbase x402 v2 Wire Interlock
# ============================================================================

class X402V2WireInterlock:
    """
    Evaluates x402Version: 2 PAYMENT-REQUIRED challenges and client
    PAYMENT-SIGNATURE headers (EIP-3009 nonce, valid_after, valid_before,
    and bound_action_caid) to prevent double-settlement during HTTP 504 / TCP resets.
    """

    def __init__(self, interlock_private_key: Ed25519PrivateKey) -> None:
        self._interlock_private_key = interlock_private_key
        # Maps nonce -> {"bound_action_caid": str, "result": Dict[str, Any]}
        self._nonce_ledger: Dict[str, Dict[str, Any]] = {}

    def evaluate_payment_signature(
        self,
        payment_required_challenge: Dict[str, Any],
        payment_signature_header: Dict[str, Any],
        action_payload: Dict[str, Any],
        agent_public_key: Ed25519PublicKey,
        operation_id: str,
        current_timestamp: int,
    ) -> Dict[str, Any]:
        if payment_required_challenge.get("x402Version") != 2:
            return {
                "allowed": False,
                "status": "HALT_X402_UNSUPPORTED_VERSION",
            }

        if not verify_jcs_signature(agent_public_key, payment_signature_header):
            return {
                "allowed": False,
                "status": "HALT_X402_SIGNATURE_INVALID",
            }

        expected_action_caid = compute_jcs_caid(action_payload)
        bound_action_caid = payment_signature_header.get("bound_action_caid")
        if bound_action_caid != expected_action_caid:
            return {
                "allowed": False,
                "status": "HALT_X402_CAID_MISMATCH",
                "expected_action_caid": expected_action_caid,
                "bound_action_caid": bound_action_caid,
            }

        nonce = payment_signature_header.get("nonce")
        if not isinstance(nonce, str) or not nonce:
            return {
                "allowed": False,
                "status": "HALT_X402_NONCE_INVALID",
            }

        # Check nonce replay / HTTP 504 retry deduplication
        if nonce in self._nonce_ledger:
            prior_entry = self._nonce_ledger[nonce]
            if prior_entry["bound_action_caid"] == expected_action_caid and prior_entry["operation_id"] == operation_id:
                # Safe idempotent retry of the exact same action after HTTP 504 / TCP reset
                cached = dict(prior_entry["result"])
                cached["deduplicated_retry"] = True
                return cached
            return {
                "allowed": False,
                "status": "HALT_X402_NONCE_REPLAY",
                "nonce": nonce,
            }

        # Check EIP-3009 validity window
        valid_after = int(payment_signature_header.get("valid_after", 0))
        valid_before = int(payment_signature_header.get("valid_before", 0))
        if not (valid_after <= current_timestamp <= valid_before):
            return {
                "allowed": False,
                "status": "HALT_X402_WINDOW_EXPIRED",
            }

        # Match against server challenge 'accepts' entries
        accepts = payment_required_challenge.get("accepts", [])
        scheme = payment_signature_header.get("scheme")
        network = payment_signature_header.get("network")
        pay_to = payment_signature_header.get("pay_to")
        amount_minor = int(payment_signature_header.get("amount_minor", -1))

        matched_accept: Optional[Dict[str, Any]] = None
        for candidate in accepts:
            if (
                candidate.get("scheme") == scheme
                and candidate.get("network") == network
                and candidate.get("payTo") == pay_to
            ):
                matched_accept = candidate
                break

        if matched_accept is None:
            return {
                "allowed": False,
                "status": "HALT_X402_CHALLENGE_MISMATCH",
            }

        challenge_amount = int(matched_accept.get("amount", 0))
        if scheme == "exact":
            if amount_minor != challenge_amount:
                return {
                    "allowed": False,
                    "status": "HALT_X402_AMOUNT_EXCEEDS_CHALLENGE",
                    "amount_minor": amount_minor,
                    "challenge_amount": challenge_amount,
                }
        elif scheme in ("upto", "auth-capture"):
            if amount_minor <= 0 or amount_minor > challenge_amount:
                return {
                    "allowed": False,
                    "status": "HALT_X402_AMOUNT_EXCEEDS_CHALLENGE",
                    "amount_minor": amount_minor,
                    "challenge_amount": challenge_amount,
                }
        else:
            return {
                "allowed": False,
                "status": "HALT_X402_UNSUPPORTED_SCHEME",
            }

        mandate_digests = {
            "x402_challenge_caid": compute_jcs_caid(payment_required_challenge),
            "x402_payment_signature_caid": compute_jcs_caid(payment_signature_header),
        }
        cose_receipt = build_cose_sign1_rail_receipt(
            interlock_private_key=self._interlock_private_key,
            rail_type="LF_COINBASE_X402_V2",
            operation_id=operation_id,
            action_caid=expected_action_caid,
            mandate_digests=mandate_digests,
            extra_claims={
                "network": network,
                "nonce": nonce,
                "scheme": scheme,
                "amount_minor": amount_minor,
                "pay_to": pay_to,
            },
        )
        result = {
            "allowed": True,
            "status": "X402_V2_SETTLEMENT_AUTHORIZED",
            "deduplicated_retry": False,
            "idempotency_key": cose_receipt["rail_idempotency_key"],
            "cose_receipt": cose_receipt,
        }
        self._nonce_ledger[nonce] = {
            "bound_action_caid": expected_action_caid,
            "operation_id": operation_id,
            "result": result,
        }
        return result


# ============================================================================
# 3. Stripe / OpenAI ACP (Agentic Commerce Protocol) Checkout Interlock
# ============================================================================

class StripeACPCheckoutInterlock:
    """
    Manages Stripe / OpenAI ACP POST /checkout_sessions/{id}/complete state
    locking with Shared Payment Tokens (spt_...) and API-Version: 2025-09-29.
    Prevents double-charging or burning a second SPT when an HTTP 504 leaves a
    checkout session in EFFECT_INDETERMINATE until probe reconciliation completes.
    """

    REQUIRED_API_VERSION = "2025-09-29"

    def __init__(self, interlock_private_key: Ed25519PrivateKey) -> None:
        self._interlock_private_key = interlock_private_key
        # checkout_session_id -> state dict
        self._sessions: Dict[str, Dict[str, Any]] = {}
        # spt_id -> status ("ACTIVE_IN_FLIGHT", "EFFECT_INDETERMINATE", "CONSUMED", "RELEASED")
        self._spt_registry: Dict[str, str] = {}

    def prepare_checkout_complete(
        self,
        checkout_session_id: str,
        spt_id: str,
        api_version: str,
        operation_id: str,
        action_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        if api_version != self.REQUIRED_API_VERSION:
            return {
                "allowed": False,
                "status": "HALT_ACP_INVALID_API_VERSION",
                "expected_version": self.REQUIRED_API_VERSION,
            }

        if not isinstance(spt_id, str) or not spt_id.startswith("spt_"):
            return {
                "allowed": False,
                "status": "HALT_ACP_INVALID_SPT_FORMAT",
            }

        # Check if checkout session or SPT is locked in EFFECT_INDETERMINATE
        session_entry = self._sessions.get(checkout_session_id)
        if session_entry is not None:
            if session_entry["state"] == "EFFECT_INDETERMINATE":
                return {
                    "allowed": False,
                    "status": "HALT_ACP_SPT_LOCKED_INDETERMINATE",
                    "checkout_session_id": checkout_session_id,
                    "locked_spt_id": session_entry["spt_id"],
                }
            if session_entry["state"] == "COMPLETED":
                return {
                    "allowed": False,
                    "status": "HALT_ACP_SESSION_ALREADY_COMPLETED",
                    "checkout_session_id": checkout_session_id,
                }

        spt_state = self._spt_registry.get(spt_id)
        if spt_state == "EFFECT_INDETERMINATE":
            return {
                "allowed": False,
                "status": "HALT_ACP_SPT_LOCKED_INDETERMINATE",
                "checkout_session_id": checkout_session_id,
                "locked_spt_id": spt_id,
            }
        if spt_state == "CONSUMED":
            return {
                "allowed": False,
                "status": "HALT_ACP_SPT_ALREADY_CONSUMED",
                "spt_id": spt_id,
            }

        action_caid = compute_jcs_caid(action_payload)
        mandate_digests = {
            "acp_checkout_request_caid": compute_jcs_caid(
                {
                    "api_version": api_version,
                    "checkout_session_id": checkout_session_id,
                    " endpoint": f"POST /checkout_sessions/{checkout_session_id}/complete",
                    "spt_id": spt_id,
                }
            )
        }
        cose_receipt = build_cose_sign1_rail_receipt(
            interlock_private_key=self._interlock_private_key,
            rail_type="STRIPE_OPENAI_ACP",
            operation_id=operation_id,
            action_caid=action_caid,
            mandate_digests=mandate_digests,
            extra_claims={
                "api_version": api_version,
                "checkout_session_id": checkout_session_id,
                "spt_id": spt_id,
            },
        )
        self._sessions[checkout_session_id] = {
            "state": "IN_FLIGHT",
            "spt_id": spt_id,
            "action_caid": action_caid,
            "idempotency_key": cose_receipt["rail_idempotency_key"],
            "cose_receipt": cose_receipt,
        }
        self._spt_registry[spt_id] = "ACTIVE_IN_FLIGHT"
        return {
            "allowed": True,
            "status": "ACP_CHECKOUT_DISPATCH_READY",
            "headers": {
                "API-Version": self.REQUIRED_API_VERSION,
                "Idempotency-Key": cose_receipt["rail_idempotency_key"],
            },
            "cose_receipt": cose_receipt,
        }

    def record_transport_outcome(
        self,
        checkout_session_id: str,
        http_status: Optional[int],
    ) -> str:
        """
        Records transport outcome for POST /checkout_sessions/{id}/complete.
        HTTP 502/504 or None (timeout / TCP reset) latches EFFECT_INDETERMINATE.
        """
        session_entry = self._sessions.get(checkout_session_id)
        if session_entry is None:
            raise KeyError(f"Unknown checkout_session_id: {checkout_session_id}")

        spt_id = session_entry["spt_id"]
        if http_status == 200:
            session_entry["state"] = "COMPLETED"
            self._spt_registry[spt_id] = "CONSUMED"
            return "COMPLETED"

        if http_status in (None, 408, 502, 503, 504):
            session_entry["state"] = "EFFECT_INDETERMINATE"
            self._spt_registry[spt_id] = "EFFECT_INDETERMINATE"
            return "EFFECT_INDETERMINATE"

        session_entry["state"] = "FAILED_DEFINITIVE"
        self._spt_registry[spt_id] = "RELEASED"
        return "FAILED_DEFINITIVE"

    def reconcile_checkout_session_probe(
        self,
        probe_payload: Dict[str, Any],
        probe_public_key: Ed25519PublicKey,
    ) -> Dict[str, Any]:
        """
        Reconciles an EFFECT_INDETERMINATE checkout session using a signed
        out-of-band GET /checkout_sessions/{id} status probe.
        """
        if not verify_jcs_signature(probe_public_key, probe_payload):
            return {
                "reconciled": False,
                "status": "HALT_ACP_PROBE_SIGNATURE_INVALID",
            }

        checkout_session_id = probe_payload.get("checkout_session_id")
        remote_status = probe_payload.get("remote_status")
        session_entry = self._sessions.get(checkout_session_id)
        if session_entry is None:
            return {
                "reconciled": False,
                "status": "HALT_ACP_UNKNOWN_SESSION",
            }

        spt_id = session_entry["spt_id"]
        if remote_status == "completed":
            session_entry["state"] = "COMPLETED"
            self._spt_registry[spt_id] = "CONSUMED"
            return {
                "reconciled": True,
                "status": "ACP_RECONCILED_ALREADY_SETTLED",
                "checkout_session_id": checkout_session_id,
                "spt_id": spt_id,
                "idempotency_key": session_entry["idempotency_key"],
            }
        elif remote_status == "open_unpaid":
            session_entry["state"] = "OPEN_RETRYABLE"
            self._spt_registry[spt_id] = "RELEASED"
            return {
                "reconciled": True,
                "status": "ACP_RECONCILED_SAFE_TO_RETRY",
                "checkout_session_id": checkout_session_id,
                "spt_id": spt_id,
            }
        return {
            "reconciled": False,
            "status": "HALT_ACP_UNRECOGNIZED_REMOTE_STATUS",
        }


# ============================================================================
# 4. Directive 3 — MCP Tool Supply-Chain & Provenance Taint Gate (AT63 & AT64)
# ============================================================================

VALID_PROVENANCE_TIERS: Set[str] = {
    "TIER_0_SYSTEM_PINNED",
    "TIER_1_PARTNER_ATTESTED",
    "TIER_2_UNTRUSTED_EXTERNAL",
}

MCP_POISONING_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"<\s*(system|IMPORTANT|hidden_instruction)\s*>", re.IGNORECASE),
    re.compile(r"(before|after)\s+calling\s+this\s+tool.*(transfer|send|wire|exfiltrate)", re.IGNORECASE | re.DOTALL),
    re.compile(r"override\s+consequence\s+ceiling", re.IGNORECASE),
    re.compile(r"do\s+not\s+mention\s+this\s+to\s+the\s+user", re.IGNORECASE),
]


@dataclass(frozen=True)
class MCPToolDescriptor:
    server_id: str
    tool_name: str
    provenance_tier: str
    description: str
    input_schema: Dict[str, Any]
    source_sha256: str
    descriptor_signature_b64: str

    def to_unsigned_dict(self) -> Dict[str, Any]:
        return {
            "description": self.description,
            "input_schema": self.input_schema,
            "provenance_tier": self.provenance_tier,
            "server_id": self.server_id,
            "source_sha256": self.source_sha256,
            "tool_name": self.tool_name,
        }


@dataclass
class SessionProvenanceState:
    session_id: str
    default_ceiling_minor: int = 500_000  # e.g. $5,000.00 in cents
    degraded_ceiling_minor: int = 0       # $0.00 financial dispatch allowed when tainted
    is_tainted: bool = False
    taint_sources: List[str] = field(default_factory=list)

    @property
    def effective_ceiling_minor(self) -> int:
        return self.degraded_ceiling_minor if self.is_tainted else self.default_ceiling_minor


class MCPToolProvenanceTaintGate:
    """
    Enforces AT63 (Shadow MCP server rejection, MCP tool description poisoning
    detection, and post-approval rug-pull detection) and AT64 (session consequence
    ceiling degradation when TIER_2_UNTRUSTED_EXTERNAL tool outputs enter context).
    """

    def __init__(
        self,
        registry_public_key: Ed25519PublicKey,
        supervisor_public_key: Ed25519PublicKey,
    ) -> None:
        self._registry_public_key = registry_public_key
        self._supervisor_public_key = supervisor_public_key
        self._approved_servers: Set[str] = set()
        self._pinned_tools: Dict[str, MCPToolDescriptor] = {}
        self._sessions: Dict[str, SessionProvenanceState] = {}

    @staticmethod
    def inspect_for_description_poisoning(
        description: str,
        input_schema: Dict[str, Any],
    ) -> Optional[str]:
        """Scans tool description and JSON schema for covert prompt-injection directives."""
        combined_text = description + "\n" + encode_jcs(input_schema).decode("utf-8")
        for pattern in MCP_POISONING_PATTERNS:
            match = pattern.search(combined_text)
            if match:
                return match.group(0)
        return None

    def register_approved_server(self, server_id: str) -> None:
        self._approved_servers.add(server_id)

    def register_pinned_tool(self, descriptor: MCPToolDescriptor) -> Dict[str, Any]:
        if descriptor.server_id not in self._approved_servers:
            return {
                "registered": False,
                "status": "HALT_SHADOW_MCP_SERVER_UNREGISTERED",
                "server_id": descriptor.server_id,
            }
        if descriptor.provenance_tier not in VALID_PROVENANCE_TIERS:
            return {
                "registered": False,
                "status": "HALT_MCP_INVALID_PROVENANCE_TIER",
            }

        poison_match = self.inspect_for_description_poisoning(
            descriptor.description,
            descriptor.input_schema,
        )
        if poison_match is not None:
            return {
                "registered": False,
                "status": "HALT_MCP_TOOL_DESCRIPTION_POISONING",
                "matched_directive": poison_match,
            }

        payload = descriptor.to_unsigned_dict()
        payload["signature_b64"] = descriptor.descriptor_signature_b64
        if not verify_jcs_signature(self._registry_public_key, payload):
            return {
                "registered": False,
                "status": "HALT_MCP_DESCRIPTOR_SIGNATURE_INVALID",
            }

        key = f"{descriptor.server_id}:{descriptor.tool_name}"
        self._pinned_tools[key] = descriptor
        return {
            "registered": True,
            "status": "MCP_TOOL_PINNED",
            "tool_key": key,
        }

    def get_or_create_session(
        self,
        session_id: str,
        default_ceiling_minor: int = 500_000,
        degraded_ceiling_minor: int = 0,
    ) -> SessionProvenanceState:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionProvenanceState(
                session_id=session_id,
                default_ceiling_minor=default_ceiling_minor,
                degraded_ceiling_minor=degraded_ceiling_minor,
            )
        return self._sessions[session_id]

    def evaluate_mcp_tool_invocation(
        self,
        session_id: str,
        server_id: str,
        tool_name: str,
        live_description: str,
        live_input_schema: Dict[str, Any],
        live_source_sha256: str,
    ) -> Dict[str, Any]:
        """
        Validates an MCP tool invocation against AT63 (Shadow MCP, Description
        Poisoning, Rug-Pull) and updates AT64 session provenance taint state.
        """
        session = self.get_or_create_session(session_id)

        if server_id not in self._approved_servers:
            return {
                "allowed": False,
                "status": "HALT_SHADOW_MCP_SERVER_UNREGISTERED",
                "server_id": server_id,
            }

        poison_match = self.inspect_for_description_poisoning(
            live_description,
            live_input_schema,
        )
        if poison_match is not None:
            return {
                "allowed": False,
                "status": "HALT_MCP_TOOL_DESCRIPTION_POISONING",
                "matched_directive": poison_match,
            }

        key = f"{server_id}:{tool_name}"
        pinned = self._pinned_tools.get(key)
        if pinned is None:
            return {
                "allowed": False,
                "status": "HALT_SHADOW_MCP_SERVER_UNREGISTERED",
                "tool_key": key,
            }

        # Verify no post-registration rug-pull occurred on description, schema, or source hash
        if (
            pinned.description != live_description
            or encode_jcs(pinned.input_schema) != encode_jcs(live_input_schema)
            or pinned.source_sha256 != live_source_sha256
        ):
            return {
                "allowed": False,
                "status": "HALT_MCP_TOOL_RUG_PULL_DETECTED",
                "tool_key": key,
            }

        if pinned.provenance_tier == "TIER_2_UNTRUSTED_EXTERNAL":
            session.is_tainted = True
            if key not in session.taint_sources:
                session.taint_sources.append(key)

        return {
            "allowed": True,
            "status": "MCP_TOOL_INVOCATION_PERMITTED",
            "provenance_tier": pinned.provenance_tier,
            "session_tainted": session.is_tainted,
            "effective_ceiling_minor": session.effective_ceiling_minor,
        }

    def check_financial_consequence_ceiling(
        self,
        session_id: str,
        amount_minor: int,
        action_payload: Dict[str, Any],
        step_up_token: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        AT64 enforcement: If the session has ingested TIER_2_UNTRUSTED_EXTERNAL
        MCP output, blocks financial dispatches exceeding the degraded ceiling
        with UNTRUSTED_TOOL_TAINT_CEILING_DEGRADED unless a valid supervisor
        Ed25519 step-up token bound to action_caid is supplied.
        """
        session = self.get_or_create_session(session_id)
        action_caid = compute_jcs_caid(action_payload)

        if amount_minor <= session.effective_ceiling_minor:
            return {
                "allowed": True,
                "status": "CONSEQUENCE_CEILING_WITHIN_LIMIT",
                "effective_ceiling_minor": session.effective_ceiling_minor,
            }

        if session.is_tainted:
            if step_up_token is not None:
                if (
                    step_up_token.get("session_id") == session_id
                    and step_up_token.get("authorized_action_caid") == action_caid
                    and int(step_up_token.get("authorized_amount_minor", -1)) >= amount_minor
                    and verify_jcs_signature(self._supervisor_public_key, step_up_token)
                ):
                    return {
                        "allowed": True,
                        "status": "STEP_UP_SUPERVISOR_OVERRIDE_VERIFIED",
                        "authorized_action_caid": action_caid,
                    }
            return {
                "allowed": False,
                "status": "UNTRUSTED_TOOL_TAINT_CEILING_DEGRADED",
                "taint_sources": list(session.taint_sources),
                "requested_amount_minor": amount_minor,
                "effective_ceiling_minor": session.effective_ceiling_minor,
            }

        return {
            "allowed": False,
            "status": "HALT_SESSION_DEFAULT_CEILING_EXCEEDED",
            "requested_amount_minor": amount_minor,
            "effective_ceiling_minor": session.effective_ceiling_minor,
        }
