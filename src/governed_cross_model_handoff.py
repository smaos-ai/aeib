#!/usr/bin/env python3
"""
governed_cross_model_handoff.py — Governed Cross-Model Handoff & Taint Monotonicity Gate.
Evaluated under the stated model as a Layer 2.5 execution interlock prototype.

Implements GovernedCrossModelHandoffGate:
- Cross-Model Handoff Schema verification and serialization
- Taint Tier Lattice & Monotonicity Enforcement (target_taint >= source_taint)
- Authority Inheritance Restriction (untrusted models cannot inherit root sponsor warrants)
- Zero Dropped Metadata Invariant via RFC 8785 JCS canonicalization
- Cryptographic transition verification using real Ed25519 primitives
"""

from __future__ import annotations

import base64
import hashlib
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Ensure repository root is on sys.path for direct script execution
_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.jcs_canonicalizer import encode_jcs


# ============================================================================
# Taint Tier Lattice Constants & Model Trust Registry
# ============================================================================

TIER_0_SYSTEM_PINNED: str = "TIER_0_SYSTEM_PINNED"
TIER_1_PARTNER_ATTESTED: str = "TIER_1_PARTNER_ATTESTED"
TIER_2_UNTRUSTED_EXTERNAL: str = "TIER_2_UNTRUSTED_EXTERNAL"

VALID_TAINT_TIERS: Set[str] = {
    TIER_0_SYSTEM_PINNED,
    TIER_1_PARTNER_ATTESTED,
    TIER_2_UNTRUSTED_EXTERNAL,
}

TAINT_LATTICE_RANK: Dict[str, int] = {
    TIER_0_SYSTEM_PINNED: 0,
    TIER_1_PARTNER_ATTESTED: 1,
    TIER_2_UNTRUSTED_EXTERNAL: 2,
}

# Default model trust registry: maps known models to their inherent taint tier
DEFAULT_MODEL_TRUST_REGISTRY: Dict[str, str] = {
    "claude-code": TIER_0_SYSTEM_PINNED,
    "claude-3-7-sonnet": TIER_0_SYSTEM_PINNED,
    "claude-opus": TIER_0_SYSTEM_PINNED,
    "system-pinned-orchestrator": TIER_0_SYSTEM_PINNED,
    "smaos-local-enclave": TIER_0_SYSTEM_PINNED,
    "gpt-4o": TIER_1_PARTNER_ATTESTED,
    "gemini-1.5-pro": TIER_1_PARTNER_ATTESTED,
    "partner-attested-worker": TIER_1_PARTNER_ATTESTED,
    "deepseek-r1": TIER_2_UNTRUSTED_EXTERNAL,
    "deepseek-v3": TIER_2_UNTRUSTED_EXTERNAL,
    "qwen-2.5-coder": TIER_2_UNTRUSTED_EXTERNAL,
    "untrusted-external-model": TIER_2_UNTRUSTED_EXTERNAL,
}

ROOT_SPONSOR_AUTHORITY_ALIASES: Set[str] = {
    "root_sponsor",
    "root_sponsor_authority",
    "root-sponsor",
    "treasury_root",
    "treasury-root",
    "sovereign_root",
    "high_trust_warrant",
    "root_authority",
}

REQUIRED_HANDOFF_FIELDS: Tuple[str, ...] = (
    "handoff_id",
    "source_model",
    "target_model",
    "source_harness_digest",
    "target_harness_digest",
    "canonical_payload_hash",
    "policy_epoch",
    "delegation_cert_id",
    "taint_tier",
    "expires_at",
    "signature",
)

CORE_SECURITY_METADATA_FIELDS: Tuple[str, ...] = (
    "canonical_payload_hash",
    "policy_epoch",
    "taint_tier",
    "delegation_cert_id",
)


# ============================================================================
# Security Exceptions
# ============================================================================

class HandoffSecurityError(Exception):
    """Base exception for governed cross-model handoff security gate violations."""

    def __init__(self, message: str, error_code: str = "HALT_HANDOFF_SECURITY_VIOLATION") -> None:
        super().__init__(f"{error_code}: {message}")
        self.error_code = error_code
        self.detail = message


class CanonicalPayloadHashMismatchError(HandoffSecurityError):
    """Raised when canonical payload hash does not match token claim."""

    def __init__(self, message: str = "Payload hash mismatch") -> None:
        super().__init__(message, error_code="HALT_CANONICAL_PAYLOAD_HASH_MISMATCH")


class TaintDowngradeForbiddenError(HandoffSecurityError):
    """Raised when downstream model attempts to downgrade taint without step-up warrant."""

    def __init__(self, message: str = "Taint downgrade forbidden without supervisor step-up warrant") -> None:
        super().__init__(message, error_code="HALT_TAINT_DOWNGRADE_FORBIDDEN")


class SerializationMetadataStrippedError(HandoffSecurityError):
    """Raised when required security fields are stripped or missing during serialization."""

    def __init__(self, message: str = "Required security metadata stripped or missing") -> None:
        super().__init__(message, error_code="HALT_SERIALIZATION_METADATA_STRIPPED")


class HandoffExpiredError(HandoffSecurityError):
    """Raised when cross-model handoff token expiration timestamp is in the past."""

    def __init__(self, message: str = "Handoff token has expired") -> None:
        super().__init__(message, error_code="HALT_HANDOFF_EXPIRED")


class InvalidHandoffSignatureError(HandoffSecurityError):
    """Raised when Ed25519 transition signature verification fails or is forged."""

    def __init__(self, message: str = "Transition signature verification failed") -> None:
        super().__init__(message, error_code="HALT_INVALID_HANDOFF_SIGNATURE")


class UntrustedModelAuthorityEscalationError(HandoffSecurityError):
    """Raised when lower-trust model attempts to inherit root sponsor or high-trust warrant."""

    def __init__(self, message: str = "Untrusted model authority escalation forbidden") -> None:
        super().__init__(message, error_code="HALT_UNTRUSTED_MODEL_AUTHORITY_ESCALATION")


# ============================================================================
# Cryptographic & Canonicalization Helpers
# ============================================================================

def compute_payload_canonical_hash(payload: Any) -> str:
    """
    Computes hex SHA-256 digest of payload under RFC 8785 JSON Canonicalization Scheme.
    If payload is already raw bytes, hashes raw bytes directly.
    """
    if isinstance(payload, bytes):
        raw = payload
    else:
        raw = encode_jcs(payload)
    return hashlib.sha256(raw).hexdigest()


def sign_canonical_handoff(
    private_key: Ed25519PrivateKey,
    handoff_data: Dict[str, Any],
) -> str:
    """
    Signs RFC 8785 canonical bytes of handoff dictionary (excluding signature field)
    using Ed25519 private key. Returns base64-encoded signature.
    """
    unsigned = {k: v for k, v in handoff_data.items() if k != "signature"}
    canonical_bytes = encode_jcs(unsigned)
    raw_sig = private_key.sign(canonical_bytes)
    return base64.b64encode(raw_sig).decode("ascii")


def verify_canonical_handoff_signature(
    public_key: Ed25519PublicKey,
    handoff_data: Dict[str, Any],
) -> bool:
    """
    Verifies base64 Ed25519 signature over RFC 8785 canonical bytes of unsigned handoff.
    """
    sig_str = handoff_data.get("signature")
    if not isinstance(sig_str, str) or not sig_str.strip():
        return False

    unsigned = {k: v for k, v in handoff_data.items() if k != "signature"}
    try:
        canonical_bytes = encode_jcs(unsigned)
        sig_bytes = base64.b64decode(sig_str.strip(), validate=True)
        public_key.verify(sig_bytes, canonical_bytes)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


# ============================================================================
# Governed Cross-Model Handoff Gate
# ============================================================================

class GovernedCrossModelHandoffGate:
    """
    Execution boundary gate governing compute transfers between heterogeneous models.
    Enforces strict taint monotonicity, cryptographic transition verification,
    authority inheritance restrictions, and zero dropped serialization metadata.
    """

    def __init__(
        self,
        source_public_keys: Optional[Dict[str, Ed25519PublicKey]] = None,
        supervisor_public_keys: Optional[Dict[str, Ed25519PublicKey]] = None,
        model_trust_registry: Optional[Dict[str, str]] = None,
        active_policy_epoch: Optional[str] = None,
    ) -> None:
        self.source_public_keys: Dict[str, Ed25519PublicKey] = dict(source_public_keys or {})
        self.supervisor_public_keys: Dict[str, Ed25519PublicKey] = dict(supervisor_public_keys or {})
        self.model_trust_registry: Dict[str, str] = dict(DEFAULT_MODEL_TRUST_REGISTRY)
        if model_trust_registry:
            self.model_trust_registry.update(model_trust_registry)
        self.active_policy_epoch: Optional[str] = active_policy_epoch

    def register_model_trust(self, model_id: str, taint_tier: str) -> None:
        """Configures inherent taint tier for a model identifier."""
        if taint_tier not in VALID_TAINT_TIERS:
            raise ValueError(f"Invalid taint tier: {taint_tier}. Permitted: {sorted(VALID_TAINT_TIERS)}")
        self.model_trust_registry[model_id] = taint_tier

    def register_source_public_key(self, source_id: str, public_key: Ed25519PublicKey) -> None:
        """Registers authorized Ed25519 public key for a source orchestrator."""
        self.source_public_keys[source_id] = public_key

    def register_supervisor_public_key(self, supervisor_id: str, public_key: Ed25519PublicKey) -> None:
        """Registers authorized Ed25519 public key for a supervisor step-up authority."""
        self.supervisor_public_keys[supervisor_id] = public_key

    def resolve_model_taint_tier(self, model_id: str) -> str:
        """Resolves inherent taint tier of a model. Defaults to untrusted external if unknown."""
        return self.model_trust_registry.get(model_id, TIER_2_UNTRUSTED_EXTERNAL)

    def verify_taint_monotonicity(
        self,
        source_taint: str,
        target_taint: str,
        step_up_warrant: Optional[Dict[str, Any]] = None,
        handoff_id: Optional[str] = None,
    ) -> bool:
        """
        Enforces monotonic taint invariant: target_taint >= source_taint.
        If target claims lower taint (lower numerical rank in lattice), fails closed
        unless validated by a verified supervisor step-up warrant.
        """
        if source_taint not in TAINT_LATTICE_RANK:
            raise ValueError(f"Unknown source taint tier: {source_taint}")
        if target_taint not in TAINT_LATTICE_RANK:
            raise ValueError(f"Unknown target taint tier: {target_taint}")

        source_rank = TAINT_LATTICE_RANK[source_taint]
        target_rank = TAINT_LATTICE_RANK[target_taint]

        # Monotonicity preserved: target taint rank is equal or greater (more tainted)
        if target_rank >= source_rank:
            return True

        # Target claims lower taint (downgrade): requires valid supervisor step-up warrant
        if step_up_warrant is None:
            raise TaintDowngradeForbiddenError(
                f"Attempted taint downgrade from {source_taint} (rank {source_rank}) "
                f"to {target_taint} (rank {target_rank}) without supervisor step-up warrant"
            )

        # Validate supervisor step-up warrant
        self._validate_step_up_warrant(
            warrant=step_up_warrant,
            target_taint=target_taint,
            handoff_id=handoff_id,
        )
        return True

    def _validate_step_up_warrant(
        self,
        warrant: Dict[str, Any],
        target_taint: str,
        handoff_id: Optional[str] = None,
    ) -> None:
        """Validates supervisor step-up warrant integrity, expiration, and signature."""
        for req in ("warrant_id", "permitted_target_taint", "expires_at", "signature"):
            if req not in warrant or warrant[req] is None or warrant[req] == "":
                raise TaintDowngradeForbiddenError(f"Supervisor step-up warrant missing required field '{req}'")

        if warrant["permitted_target_taint"] != target_taint:
            raise TaintDowngradeForbiddenError(
                f"Step-up warrant permitted tier '{warrant['permitted_target_taint']}' "
                f"does not match requested downgrade target tier '{target_taint}'"
            )

        if handoff_id and warrant.get("handoff_id") and warrant["handoff_id"] != handoff_id:
            raise TaintDowngradeForbiddenError(
                f"Step-up warrant handoff_id '{warrant['handoff_id']}' does not match handoff '{handoff_id}'"
            )

        now = int(time.time())
        if now > int(warrant["expires_at"]):
            raise TaintDowngradeForbiddenError("Supervisor step-up warrant has expired")

        # Cryptographic verification if supervisor public keys configured
        supervisor_id = warrant.get("supervisor_id", warrant.get("supervisor_key_id", "default_supervisor"))
        if self.supervisor_public_keys:
            sup_pubkey = self.supervisor_public_keys.get(supervisor_id)
            if sup_pubkey is None:
                # Try finding any single registered supervisor key
                if len(self.supervisor_public_keys) == 1:
                    sup_pubkey = next(iter(self.supervisor_public_keys.values()))
                else:
                    raise TaintDowngradeForbiddenError(f"Unregistered supervisor authority: {supervisor_id}")

            if not verify_canonical_handoff_signature(sup_pubkey, warrant):
                raise TaintDowngradeForbiddenError("Supervisor step-up warrant signature verification failed")

    def check_authority_inheritance(
        self,
        target_model: str,
        target_taint_tier: str,
        claimed_authority: Optional[str] = None,
        delegation_cert_id: Optional[str] = None,
        spend_limit: Optional[int] = None,
    ) -> None:
        """
        Enforces Authority Inheritance Restriction:
        Lower-trust models (e.g. untrusted third-party models or non-system-pinned models)
        cannot inherit root sponsor capability warrants or spend limits.
        """
        target_inherent_tier = self.resolve_model_taint_tier(target_model)
        is_untrusted_model = (
            target_inherent_tier == TIER_2_UNTRUSTED_EXTERNAL
            or target_taint_tier == TIER_2_UNTRUSTED_EXTERNAL
        )
        is_non_system_model = (
            target_inherent_tier != TIER_0_SYSTEM_PINNED
            or target_taint_tier != TIER_0_SYSTEM_PINNED
        )

        claims_root_sponsor = False

        if claimed_authority:
            ca_clean = claimed_authority.strip().lower()
            if any(alias in ca_clean for alias in ROOT_SPONSOR_AUTHORITY_ALIASES):
                claims_root_sponsor = True

        if delegation_cert_id:
            dc_clean = delegation_cert_id.strip().lower()
            if any(alias in dc_clean for alias in ("root_sponsor", "root-sponsor", "treasury_root")):
                claims_root_sponsor = True

        # Spend limit check: untrusted models cannot hold nonzero financial spend limits
        if spend_limit is not None and spend_limit > 0 and is_untrusted_model:
            raise UntrustedModelAuthorityEscalationError(
                f"Model '{target_model}' in taint tier '{target_taint_tier}' cannot inherit "
                f"nonzero spend limit ({spend_limit})"
            )

        # Root sponsor warrant check
        if claims_root_sponsor and is_non_system_model:
            raise UntrustedModelAuthorityEscalationError(
                f"Lower-trust model '{target_model}' (tier {target_inherent_tier}/{target_taint_tier}) "
                f"cannot inherit root sponsor authority warrant"
            )

    def create_handoff(
        self,
        handoff_id: str,
        source_model: str,
        target_model: str,
        source_harness_digest: str,
        target_harness_digest: str,
        payload: Any,
        policy_epoch: str,
        delegation_cert_id: str,
        taint_tier: str,
        expires_at: int,
        source_private_key: Ed25519PrivateKey,
        claimed_authority: Optional[str] = None,
        source_taint_tier: Optional[str] = None,
        step_up_warrant: Optional[Dict[str, Any]] = None,
        spend_limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Constructs and cryptographically signs a Cross-Model Handoff statement.
        Enforces taint monotonicity and authority inheritance invariants before signing.
        """
        # Validate inputs are non-empty strings
        for field_name, val in [
            ("handoff_id", handoff_id),
            ("source_model", source_model),
            ("target_model", target_model),
            ("source_harness_digest", source_harness_digest),
            ("target_harness_digest", target_harness_digest),
            ("policy_epoch", policy_epoch),
            ("delegation_cert_id", delegation_cert_id),
            ("taint_tier", taint_tier),
        ]:
            if not isinstance(val, str) or not val.strip():
                raise SerializationMetadataStrippedError(f"Field '{field_name}' must be non-empty string")

        if not isinstance(expires_at, int) or expires_at <= 0:
            raise SerializationMetadataStrippedError("Field 'expires_at' must be positive integer timestamp")

        # Taint monotonicity check
        effective_source_taint = source_taint_tier or self.resolve_model_taint_tier(source_model)
        self.verify_taint_monotonicity(
            source_taint=effective_source_taint,
            target_taint=taint_tier,
            step_up_warrant=step_up_warrant,
            handoff_id=handoff_id,
        )

        # Authority escalation check
        self.check_authority_inheritance(
            target_model=target_model,
            target_taint_tier=taint_tier,
            claimed_authority=claimed_authority,
            delegation_cert_id=delegation_cert_id,
            spend_limit=spend_limit,
        )

        # Compute payload hash
        canonical_payload_hash = compute_payload_canonical_hash(payload)

        handoff_dict: Dict[str, Any] = {
            "handoff_id": handoff_id,
            "source_model": source_model,
            "target_model": target_model,
            "source_harness_digest": source_harness_digest,
            "target_harness_digest": target_harness_digest,
            "canonical_payload_hash": canonical_payload_hash,
            "policy_epoch": policy_epoch,
            "delegation_cert_id": delegation_cert_id,
            "taint_tier": taint_tier,
            "expires_at": expires_at,
        }

        # Sign RFC 8785 canonical bytes with Ed25519 private key
        signature = sign_canonical_handoff(source_private_key, handoff_dict)
        handoff_dict["signature"] = signature

        return handoff_dict

    def validate_handoff(
        self,
        handoff_token: Union[Dict[str, Any], str, bytes],
        payload: Any,
        source_public_key: Optional[Ed25519PublicKey] = None,
        current_time: Optional[int] = None,
        source_taint_tier: Optional[str] = None,
        claimed_authority: Optional[str] = None,
        step_up_warrant: Optional[Dict[str, Any]] = None,
        expected_policy_epoch: Optional[str] = None,
        spend_limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Validates an incoming Cross-Model Handoff token against payload and security invariants.
        Fails closed on any invariant violation.
        """
        # 1. Deserialization & Zero Dropped Metadata Check
        token_dict = self._parse_and_verify_metadata_completeness(handoff_token)

        # 2. Expiration Check
        now = current_time if current_time is not None else int(time.time())
        expires_at = token_dict["expires_at"]
        if not isinstance(expires_at, (int, float)) or now > int(expires_at):
            raise HandoffExpiredError(
                f"Handoff token expired at {expires_at}, evaluation timestamp is {now}"
            )

        # 3. Policy Epoch Check (if configured)
        epoch_to_check = expected_policy_epoch or self.active_policy_epoch
        if epoch_to_check is not None and token_dict["policy_epoch"] != str(epoch_to_check):
            raise HandoffSecurityError(
                f"Policy epoch mismatch: expected {epoch_to_check}, got {token_dict['policy_epoch']}",
                error_code="HALT_POLICY_EPOCH_MISMATCH",
            )

        # 4. Cryptographic Transition Signature Verification
        pubkey = source_public_key
        if pubkey is None:
            source_model_id = token_dict["source_model"]
            pubkey = self.source_public_keys.get(source_model_id)
            if pubkey is None and len(self.source_public_keys) == 1:
                pubkey = next(iter(self.source_public_keys.values()))

        if pubkey is None:
            raise InvalidHandoffSignatureError(
                f"No Ed25519 public key registered for source model '{token_dict['source_model']}'"
            )

        if not verify_canonical_handoff_signature(pubkey, token_dict):
            raise InvalidHandoffSignatureError(
                "Cryptographic Ed25519 signature over canonical handoff statement failed verification"
            )

        # 5. Canonical Payload Hash Verification
        computed_payload_hash = compute_payload_canonical_hash(payload)
        claimed_payload_hash = token_dict["canonical_payload_hash"]

        # Support optional 'sha256:' prefix normalization
        clean_claimed = claimed_payload_hash.removeprefix("sha256:")
        clean_computed = computed_payload_hash.removeprefix("sha256:")

        if clean_claimed != clean_computed:
            raise CanonicalPayloadHashMismatchError(
                f"Canonical payload hash mismatch: token claimed {clean_claimed}, "
                f"evaluated payload hash is {clean_computed}"
            )

        # 6. Taint Monotonicity Verification
        target_taint = token_dict["taint_tier"]
        effective_source_taint = source_taint_tier or self.resolve_model_taint_tier(token_dict["source_model"])
        self.verify_taint_monotonicity(
            source_taint=effective_source_taint,
            target_taint=target_taint,
            step_up_warrant=step_up_warrant,
            handoff_id=token_dict["handoff_id"],
        )

        # 7. Authority Inheritance Restriction Check
        token_claimed_authority = token_dict.get("claimed_authority") or claimed_authority
        self.check_authority_inheritance(
            target_model=token_dict["target_model"],
            target_taint_tier=target_taint,
            claimed_authority=token_claimed_authority,
            delegation_cert_id=token_dict["delegation_cert_id"],
            spend_limit=spend_limit,
        )

        # Construct verification receipt
        return {
            "status": "VERIFIED",
            "handoff_id": token_dict["handoff_id"],
            "source_model": token_dict["source_model"],
            "target_model": token_dict["target_model"],
            "source_harness_digest": token_dict["source_harness_digest"],
            "target_harness_digest": token_dict["target_harness_digest"],
            "canonical_payload_hash": clean_computed,
            "policy_epoch": token_dict["policy_epoch"],
            "delegation_cert_id": token_dict["delegation_cert_id"],
            "taint_tier": target_taint,
            "verified_at": now,
        }

    def _parse_and_verify_metadata_completeness(
        self,
        raw_token: Union[Dict[str, Any], str, bytes],
    ) -> Dict[str, Any]:
        """
        Parses handoff token and verifies that zero security fields are stripped or missing.
        """
        if isinstance(raw_token, bytes):
            import json
            try:
                data = json.loads(raw_token.decode("utf-8"))
            except Exception as e:
                raise SerializationMetadataStrippedError(f"Corrupt JSON bytes in handoff token: {e}")
        elif isinstance(raw_token, str):
            import json
            try:
                data = json.loads(raw_token)
            except Exception as e:
                raise SerializationMetadataStrippedError(f"Corrupt JSON string in handoff token: {e}")
        elif isinstance(raw_token, dict):
            data = dict(raw_token)
        else:
            raise SerializationMetadataStrippedError(
                f"Unsupported handoff token type: {type(raw_token).__name__}"
            )

        # Check required schema fields
        for field_name in REQUIRED_HANDOFF_FIELDS:
            if field_name not in data:
                raise SerializationMetadataStrippedError(
                    f"Required security field '{field_name}' stripped or missing from handoff token"
                )
            val = data[field_name]
            if val is None or val == "":
                raise SerializationMetadataStrippedError(
                    f"Security field '{field_name}' is null or empty in handoff token"
                )

        # Validate taint tier value
        if data["taint_tier"] not in VALID_TAINT_TIERS:
            raise SerializationMetadataStrippedError(
                f"Invalid taint tier '{data['taint_tier']}' in handoff token"
            )

        return data


# ============================================================================
# CLI Self-Test Runner
# ============================================================================

def run_self_test() -> int:
    """
    Executes automated self-test verifying nominal cross-model flow and all 6 falsification gates.
    Returns 0 on complete successful evaluation.
    """
    print("[EVALUATED] GovernedCrossModelHandoffGate self-test initialized.")

    # Generate real Ed25519 keys
    source_privkey = Ed25519PrivateKey.generate()
    source_pubkey = source_privkey.public_key()
    forged_privkey = Ed25519PrivateKey.generate()

    gate = GovernedCrossModelHandoffGate(
        source_public_keys={"claude-code": source_pubkey},
        active_policy_epoch="epoch-42",
    )

    nominal_payload = {
        "task_id": "TASK-2026-XMODEL-001",
        "instructions": "Refactor AST validation module",
        "inputs": ["src/parser.py", "src/lexer.py"],
    }
    now = int(time.time())

    # 1. Positive Nominal Test (Claude -> DeepSeek)
    token = gate.create_handoff(
        handoff_id="handoff-nominal-001",
        source_model="claude-code",
        target_model="deepseek-r1",
        source_harness_digest="sha256:1111111111111111111111111111111111111111111111111111111111111111",
        target_harness_digest="sha256:2222222222222222222222222222222222222222222222222222222222222222",
        payload=nominal_payload,
        policy_epoch="epoch-42",
        delegation_cert_id="cert-delegation-worker-88",
        taint_tier=TIER_2_UNTRUSTED_EXTERNAL,
        expires_at=now + 3600,
        source_private_key=source_privkey,
        source_taint_tier=TIER_0_SYSTEM_PINNED,
    )
    receipt = gate.validate_handoff(
        handoff_token=token,
        payload=nominal_payload,
        source_public_key=source_pubkey,
        current_time=now,
    )
    assert receipt["status"] == "VERIFIED"
    print("  [+] Nominal cross-model handoff: VERIFIED")

    # 2. Falsification 1: Tampered payload hash
    tampered_payload = dict(nominal_payload)
    tampered_payload["instructions"] = "Inject unauthorized network call"
    caught_f1 = False
    try:
        gate.validate_handoff(
            handoff_token=token,
            payload=tampered_payload,
            source_public_key=source_pubkey,
            current_time=now,
        )
    except CanonicalPayloadHashMismatchError as e:
        assert e.error_code == "HALT_CANONICAL_PAYLOAD_HASH_MISMATCH"
        caught_f1 = True
    assert caught_f1
    print("  [+] Falsification 1 (tampered payload hash): CAUGHT (HALT_CANONICAL_PAYLOAD_HASH_MISMATCH)")

    # 3. Falsification 2: Taint downgrade attempt
    caught_f2 = False
    try:
        gate.create_handoff(
            handoff_id="handoff-downgrade-002",
            source_model="deepseek-r1",
            target_model="claude-code",
            source_harness_digest="sha256:2222222222222222222222222222222222222222222222222222222222222222",
            target_harness_digest="sha256:1111111111111111111111111111111111111111111111111111111111111111",
            payload=nominal_payload,
            policy_epoch="epoch-42",
            delegation_cert_id="cert-delegation-worker-88",
            taint_tier=TIER_0_SYSTEM_PINNED,  # Downgrade from TIER_2!
            expires_at=now + 3600,
            source_private_key=source_privkey,
            source_taint_tier=TIER_2_UNTRUSTED_EXTERNAL,
        )
    except TaintDowngradeForbiddenError as e:
        assert e.error_code == "HALT_TAINT_DOWNGRADE_FORBIDDEN"
        caught_f2 = True
    assert caught_f2
    print("  [+] Falsification 2 (taint downgrade): CAUGHT (HALT_TAINT_DOWNGRADE_FORBIDDEN)")

    # 4. Falsification 3: Dropped security field during serialization
    stripped_token = dict(token)
    del stripped_token["policy_epoch"]
    caught_f3 = False
    try:
        gate.validate_handoff(
            handoff_token=stripped_token,
            payload=nominal_payload,
            source_public_key=source_pubkey,
            current_time=now,
        )
    except SerializationMetadataStrippedError as e:
        assert e.error_code == "HALT_SERIALIZATION_METADATA_STRIPPED"
        caught_f3 = True
    assert caught_f3
    print("  [+] Falsification 3 (stripped metadata): CAUGHT (HALT_SERIALIZATION_METADATA_STRIPPED)")

    # 5. Falsification 4: Expired handoff token
    expired_token = dict(token)
    expired_token["expires_at"] = now - 60
    # Re-sign expired token so signature is mathematically valid
    expired_token["signature"] = sign_canonical_handoff(source_privkey, expired_token)
    caught_f4 = False
    try:
        gate.validate_handoff(
            handoff_token=expired_token,
            payload=nominal_payload,
            source_public_key=source_pubkey,
            current_time=now,
        )
    except HandoffExpiredError as e:
        assert e.error_code == "HALT_HANDOFF_EXPIRED"
        caught_f4 = True
    assert caught_f4
    print("  [+] Falsification 4 (expired handoff): CAUGHT (HALT_HANDOFF_EXPIRED)")

    # 6. Falsification 5: Forged signature
    forged_token = dict(token)
    forged_token["signature"] = sign_canonical_handoff(forged_privkey, forged_token)
    caught_f5 = False
    try:
        gate.validate_handoff(
            handoff_token=forged_token,
            payload=nominal_payload,
            source_public_key=source_pubkey,
            current_time=now,
        )
    except InvalidHandoffSignatureError as e:
        assert e.error_code == "HALT_INVALID_HANDOFF_SIGNATURE"
        caught_f5 = True
    assert caught_f5
    print("  [+] Falsification 5 (forged signature): CAUGHT (HALT_INVALID_HANDOFF_SIGNATURE)")

    # 7. Falsification 6: Authority escalation by untrusted model
    caught_f6 = False
    try:
        gate.create_handoff(
            handoff_id="handoff-escalate-006",
            source_model="claude-code",
            target_model="deepseek-r1",  # Untrusted model
            source_harness_digest="sha256:1111111111111111111111111111111111111111111111111111111111111111",
            target_harness_digest="sha256:2222222222222222222222222222222222222222222222222222222222222222",
            payload=nominal_payload,
            policy_epoch="epoch-42",
            delegation_cert_id="root-sponsor-cert-001",  # Claiming root sponsor authority!
            taint_tier=TIER_2_UNTRUSTED_EXTERNAL,
            expires_at=now + 3600,
            source_private_key=source_privkey,
            claimed_authority="root_sponsor",
        )
    except UntrustedModelAuthorityEscalationError as e:
        assert e.error_code == "HALT_UNTRUSTED_MODEL_AUTHORITY_ESCALATION"
        caught_f6 = True
    assert caught_f6
    print("  [+] Falsification 6 (authority escalation): CAUGHT (HALT_UNTRUSTED_MODEL_AUTHORITY_ESCALATION)")

    print("[EVALUATED] All 7 gates evaluated under stated model.")
    return 0


if __name__ == "__main__":
    import sys
    if "--self-test" in sys.argv:
        sys.exit(run_self_test())
    else:
        print("Governed Cross-Model Handoff Gate CLI. Use --self-test to execute gate evaluation.")
        sys.exit(0)
