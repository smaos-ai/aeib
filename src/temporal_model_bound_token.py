#!/usr/bin/env python3
"""
Temporal Model-Bound Token & Substrate Integrity Attestor (src/temporal_model_bound_token.py).

Status: INTERNAL PREVIEW COMMISSIONED
Evaluated under the stated model to cryptographically bind agent execution warrants
to model weights digest, system prompt CAID, repository commit CAID, TTL, invocation quota,
and substrate provenance tier.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
from typing import Dict, Optional, Sequence, Set, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs


@dataclass(frozen=True)
class SubstrateCustodyManifest:
    """Attestation manifest describing model weight and training corpus custody."""

    model_id: str
    weights_sha256: str
    training_corpus_custody_verified: bool
    behavioral_canary_suite_passed: bool
    fine_tune_lineage_signed: bool


@dataclass(frozen=True)
class ModelBoundTokenEnvelope:
    """Cryptographically signed execution token bound to live model, prompt, and repo state."""

    token_id: str
    subject_agent_id: str
    allowed_tools: Tuple[str, ...]
    model_artifact_digest: str
    system_prompt_caid: str
    repo_commit_caid: str
    issued_at_epoch_sec: int
    expires_at_epoch_sec: int
    max_invocations: int
    substrate_custody_verified: bool = True
    issuer_public_key_hex: str = ""
    signature_hex: str = ""

    def canonical_signing_payload(self) -> bytes:
        """Serialize canonical RFC 8785 bytes covered by the issuer Ed25519 signature."""
        payload = {
            "allowed_tools": list(self.allowed_tools),
            "expires_at_epoch_sec": self.expires_at_epoch_sec,
            "issued_at_epoch_sec": self.issued_at_epoch_sec,
            "issuer_public_key_hex": self.issuer_public_key_hex.lower(),
            "max_invocations": self.max_invocations,
            "model_artifact_digest": self.model_artifact_digest,
            "repo_commit_caid": self.repo_commit_caid,
            "subject_agent_id": self.subject_agent_id,
            "substrate_custody_verified": self.substrate_custody_verified,
            "system_prompt_caid": self.system_prompt_caid,
            "token_id": self.token_id,
        }
        return encode_jcs(payload)

    def token_caid(self) -> str:
        """Return deterministic SHA-256 hex digest of the canonical unsigned token payload."""
        return hashlib.sha256(self.canonical_signing_payload()).hexdigest()


@dataclass(frozen=True)
class TokenValidationVerdict:
    """Deterministic validation receipt emitted by ModelBoundTokenValidator."""

    allowed: bool
    status_code: str
    violation_reason: str
    token_caid: str
    remaining_invocations: int
    substrate_trust_tier: str
    verdict_caid: str


class SubstrateIntegrityAttestor:
    """Evaluates substrate custody manifests into deterministic trust tiers."""

    @staticmethod
    def evaluate_substrate(manifest: SubstrateCustodyManifest) -> Tuple[bool, str]:
        """Classify model substrate into halted, verified custody, or conditional pass."""
        if not manifest.behavioral_canary_suite_passed or not manifest.weights_sha256.strip():
            return (False, "HALT_SUBSTRATE_CANARY_OR_DIGEST_FAILED")
        if manifest.training_corpus_custody_verified and manifest.fine_tune_lineage_signed:
            return (True, "VERIFIED_CUSTODY_SUBSTRATE")
        return (True, "CONDITIONAL_PASS_SUBSTRATE_UNVERIFIED")


class ModelBoundTokenValidator:
    """Issues and validates short-lived, quota-bounded, state-bound execution tokens."""

    def __init__(
        self,
        issuer_signing_key: Optional[ed25519.Ed25519PrivateKey] = None,
        trusted_issuer_pubkeys: Optional[Sequence[str]] = None,
    ) -> None:
        self._signing_key: ed25519.Ed25519PrivateKey = (
            issuer_signing_key
            if issuer_signing_key is not None
            else ed25519.Ed25519PrivateKey.generate()
        )
        own_pub_hex = self._signing_key.public_key().public_bytes_raw().hex()
        self._own_pub_hex: str = own_pub_hex
        self._trusted_pubkeys: Set[str] = {own_pub_hex}
        if trusted_issuer_pubkeys is not None:
            for pub_hex in trusted_issuer_pubkeys:
                self._trusted_pubkeys.add(pub_hex.lower())
        self._invocation_counts: Dict[str, int] = {}
        self._revoked_token_caids: Set[str] = set()

    def issue_token(
        self,
        token_id: str,
        subject_agent_id: str,
        allowed_tools: Sequence[str],
        model_artifact_digest: str,
        system_prompt_caid: str,
        repo_commit_caid: str,
        issued_at_epoch_sec: int,
        ttl_sec: int,
        max_invocations: int,
        substrate_custody_verified: bool = True,
    ) -> ModelBoundTokenEnvelope:
        """Mint and sign a ModelBoundTokenEnvelope with Ed25519."""
        if ttl_sec <= 0:
            raise ValueError("ttl_sec must be > 0")
        if max_invocations <= 0:
            raise ValueError("max_invocations must be > 0")
        unsigned = ModelBoundTokenEnvelope(
            token_id=token_id,
            subject_agent_id=subject_agent_id,
            allowed_tools=tuple(allowed_tools),
            model_artifact_digest=model_artifact_digest,
            system_prompt_caid=system_prompt_caid,
            repo_commit_caid=repo_commit_caid,
            issued_at_epoch_sec=issued_at_epoch_sec,
            expires_at_epoch_sec=issued_at_epoch_sec + ttl_sec,
            max_invocations=max_invocations,
            substrate_custody_verified=substrate_custody_verified,
            issuer_public_key_hex=self._own_pub_hex,
            signature_hex="",
        )
        sig_hex = self._signing_key.sign(unsigned.canonical_signing_payload()).hex()
        return replace(unsigned, signature_hex=sig_hex)

    def revoke_token(self, token_caid: str) -> None:
        """Explicitly revoke a token by its canonical CAID."""
        self._revoked_token_caids.add(token_caid)

    def _build_verdict(
        self,
        allowed: bool,
        status_code: str,
        violation_reason: str,
        token_caid: str,
        remaining_invocations: int,
        substrate_trust_tier: str,
    ) -> TokenValidationVerdict:
        payload = {
            "allowed": allowed,
            "remaining_invocations": remaining_invocations,
            "status_code": status_code,
            "substrate_trust_tier": substrate_trust_tier,
            "token_caid": token_caid,
            "violation_reason": violation_reason,
        }
        verdict_caid = hashlib.sha256(encode_jcs(payload)).hexdigest()
        return TokenValidationVerdict(
            allowed=allowed,
            status_code=status_code,
            violation_reason=violation_reason,
            token_caid=token_caid,
            remaining_invocations=remaining_invocations,
            substrate_trust_tier=substrate_trust_tier,
            verdict_caid=verdict_caid,
        )

    def validate_token(
        self,
        token: ModelBoundTokenEnvelope,
        requested_tool: str,
        live_model_digest: str,
        live_system_prompt_caid: str,
        live_repo_commit_caid: str,
        current_epoch_sec: int,
    ) -> TokenValidationVerdict:
        """Validate token signature, revocation, TTL, live digests, scope, and invocation quota."""
        t_caid = token.token_caid()

        if t_caid in self._revoked_token_caids:
            return self._build_verdict(
                allowed=False,
                status_code="HALT_TOKEN_REVOKED",
                violation_reason="REASON_TOKEN_EXPLICITLY_REVOKED",
                token_caid=t_caid,
                remaining_invocations=0,
                substrate_trust_tier="UNTRUSTED_SUBSTRATE",
            )

        issuer_hex = token.issuer_public_key_hex.lower()
        if issuer_hex not in self._trusted_pubkeys:
            return self._build_verdict(
                allowed=False,
                status_code="HALT_INVALID_TOKEN_SIGNATURE",
                violation_reason="REASON_UNTRUSTED_ISSUER_PUBLIC_KEY",
                token_caid=t_caid,
                remaining_invocations=0,
                substrate_trust_tier="UNTRUSTED_SUBSTRATE",
            )

        try:
            pubkey = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(issuer_hex))
            pubkey.verify(bytes.fromhex(token.signature_hex), token.canonical_signing_payload())
        except (ValueError, InvalidSignature):
            return self._build_verdict(
                allowed=False,
                status_code="HALT_INVALID_TOKEN_SIGNATURE",
                violation_reason="REASON_ED25519_SIGNATURE_VERIFICATION_FAILED",
                token_caid=t_caid,
                remaining_invocations=0,
                substrate_trust_tier="UNTRUSTED_SUBSTRATE",
            )

        if (
            current_epoch_sec >= token.expires_at_epoch_sec
            or current_epoch_sec < token.issued_at_epoch_sec
        ):
            return self._build_verdict(
                allowed=False,
                status_code="HALT_TOKEN_TTL_EXPIRED",
                violation_reason="REASON_TOKEN_TEMPORAL_WINDOW_EXPIRED",
                token_caid=t_caid,
                remaining_invocations=0,
                substrate_trust_tier="UNTRUSTED_SUBSTRATE",
            )

        if live_model_digest != token.model_artifact_digest:
            self._revoked_token_caids.add(t_caid)
            return self._build_verdict(
                allowed=False,
                status_code="HALT_MODEL_MUTATED",
                violation_reason="REASON_MODEL_ARTIFACT_DIGEST_MISMATCH",
                token_caid=t_caid,
                remaining_invocations=0,
                substrate_trust_tier="UNTRUSTED_SUBSTRATE",
            )

        if live_system_prompt_caid != token.system_prompt_caid:
            self._revoked_token_caids.add(t_caid)
            return self._build_verdict(
                allowed=False,
                status_code="HALT_SYSTEM_PROMPT_DRIFT",
                violation_reason="REASON_SYSTEM_PROMPT_CAID_MISMATCH",
                token_caid=t_caid,
                remaining_invocations=0,
                substrate_trust_tier="UNTRUSTED_SUBSTRATE",
            )

        if live_repo_commit_caid != token.repo_commit_caid:
            self._revoked_token_caids.add(t_caid)
            return self._build_verdict(
                allowed=False,
                status_code="HALT_REPO_STATE_DRIFT",
                violation_reason="REASON_REPO_COMMIT_CAID_MISMATCH",
                token_caid=t_caid,
                remaining_invocations=0,
                substrate_trust_tier="UNTRUSTED_SUBSTRATE",
            )

        if requested_tool not in token.allowed_tools:
            return self._build_verdict(
                allowed=False,
                status_code="HALT_TOOL_OUT_OF_SCOPE",
                violation_reason="REASON_TOOL_NOT_IN_ALLOWED_SCOPE",
                token_caid=t_caid,
                remaining_invocations=0,
                substrate_trust_tier="UNTRUSTED_SUBSTRATE",
            )

        used = self._invocation_counts.get(t_caid, 0)
        if used >= token.max_invocations:
            return self._build_verdict(
                allowed=False,
                status_code="HALT_INVOCATION_QUOTA_EXHAUSTED",
                violation_reason="REASON_MAX_INVOCATIONS_REACHED",
                token_caid=t_caid,
                remaining_invocations=0,
                substrate_trust_tier="UNTRUSTED_SUBSTRATE",
            )

        new_used = used + 1
        self._invocation_counts[t_caid] = new_used
        remaining = token.max_invocations - new_used
        trust_tier = (
            "VERIFIED_CUSTODY_SUBSTRATE"
            if token.substrate_custody_verified
            else "CONDITIONAL_PASS_SUBSTRATE_UNVERIFIED"
        )
        status_code = (
            "ALLOW_MODEL_BOUND_EXECUTION"
            if token.substrate_custody_verified
            else "CONDITIONAL_PASS_SUBSTRATE_UNVERIFIED"
        )
        return self._build_verdict(
            allowed=True,
            status_code=status_code,
            violation_reason="NONE",
            token_caid=t_caid,
            remaining_invocations=remaining,
            substrate_trust_tier=trust_tier,
        )
