"""
v1.1-roadmap/signed_deployment_profile.py — Signed Deployment Profile & Rule Provenance Prototype.
Sovereign Multi-Agent OS (SMAOS) / Agent Execution Integrity Boundary (AEIB).

Tier 2 Core Delivery Contract:
Enforces operator-governed configuration provenance bound to runtime dispatch decisions:
  1. Operator cryptographic signature: Ed25519 signature over canonical RFC 8785 JCS profile.
  2. Rule provenance: Binds active policy epoch, pinned manifest digest, allowed targets,
     and prohibited actions to immutable cryptographic identity.
  3. Pre-dispatch policy evaluation: Evaluates candidate targets and actions against
     operator-signed rules fail-closed.
  4. Decision and receipt binding: Injects profile_digest and policy_epoch into dispatch
     authorization tickets and continuity receipts.

Operates under the stated model: Prohibits unsigned or drifted deployment configurations.
"""

from __future__ import annotations

import copy
import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from src.jcs_canonicalizer import encode_jcs


class DeploymentProfileError(Exception):
    """Raised on invalid profile signatures, expiration, or rule violations."""


@dataclass(frozen=True)
class SignedDeploymentProfile:
    """Operator-signed configuration bundle establishing runtime policy rules."""

    profile_id: str
    policy_epoch: int
    operator_principal_id: str
    pinned_manifest_digest: str
    allowed_targets: List[str]
    denied_actions: List[str]
    max_spend_per_op_eur: int
    valid_from_epoch: int
    valid_until_epoch: int
    signature_hex: str

    def to_canonical_statement(self) -> Dict[str, Any]:
        return {
            "allowedTargets": sorted(self.allowed_targets),
            "deniedActions": sorted(self.denied_actions),
            "maxSpendPerOpEur": self.max_spend_per_op_eur,
            "operatorPrincipalId": self.operator_principal_id,
            "pinnedManifestDigest": self.pinned_manifest_digest,
            "policyEpoch": self.policy_epoch,
            "profileId": self.profile_id,
            "validFromEpoch": self.valid_from_epoch,
            "validUntilEpoch": self.valid_until_epoch,
        }

    def compute_profile_digest(self) -> str:
        stmt_bytes = encode_jcs(self.to_canonical_statement())
        return f"sha256:{hashlib.sha256(stmt_bytes).hexdigest()}"


@dataclass(frozen=True)
class ProfileEvaluationResult:
    """Deterministic result of evaluating a dispatch action against the signed profile."""

    allowed: bool
    profile_digest: str
    policy_epoch: int
    diagnostic_message: str


class DeploymentProfileEvaluator:
    """
    AEIB Tier 2 Deployment Profile Evaluator.
    Verifies operator signatures and enforces profile rules before ticket minting.
    """

    def __init__(
        self,
        *,
        operator_public_key: Ed25519PublicKey,
        profile: SignedDeploymentProfile,
    ) -> None:
        self.operator_public_key = operator_public_key
        self.profile = profile
        self.profile_digest = profile.compute_profile_digest()

        # Verify cryptographic integrity of profile at instantiation
        self._verify_profile_signature()

    def _verify_profile_signature(self) -> None:
        stmt_bytes = encode_jcs(self.profile.to_canonical_statement())
        try:
            sig_bytes = bytes.fromhex(self.profile.signature_hex)
            self.operator_public_key.verify(sig_bytes, stmt_bytes)
        except (InvalidSignature, ValueError) as err:
            raise DeploymentProfileError(
                f"PROFILE_SIGNATURE_INVALID: operator signature verification failed: {err}"
            )

    def evaluate_dispatch(
        self,
        *,
        target_identity: str,
        action_name: str,
        requested_spend_eur: int = 0,
        current_timestamp: int,
    ) -> ProfileEvaluationResult:
        """Evaluates whether a candidate dispatch is permitted by the signed profile."""
        # 1. Temporal validity window
        if current_timestamp < self.profile.valid_from_epoch:
            return ProfileEvaluationResult(
                allowed=False,
                profile_digest=self.profile_digest,
                policy_epoch=self.profile.policy_epoch,
                diagnostic_message=f"PROFILE_NOT_YET_ACTIVE: active from {self.profile.valid_from_epoch} (current: {current_timestamp})",
            )
        if current_timestamp > self.profile.valid_until_epoch:
            return ProfileEvaluationResult(
                allowed=False,
                profile_digest=self.profile_digest,
                policy_epoch=self.profile.policy_epoch,
                diagnostic_message=f"PROFILE_EXPIRED: expired at {self.profile.valid_until_epoch} (current: {current_timestamp})",
            )

        # 2. Target allowlist check
        if "*" not in self.profile.allowed_targets and target_identity not in self.profile.allowed_targets:
            return ProfileEvaluationResult(
                allowed=False,
                profile_digest=self.profile_digest,
                policy_epoch=self.profile.policy_epoch,
                diagnostic_message=f"TARGET_NOT_ALLOWED: target '{target_identity}' not in permitted targets {self.profile.allowed_targets}",
            )

        # 3. Denied actions check
        if action_name in self.profile.denied_actions:
            return ProfileEvaluationResult(
                allowed=False,
                profile_digest=self.profile_digest,
                policy_epoch=self.profile.policy_epoch,
                diagnostic_message=f"ACTION_PROHIBITED: action '{action_name}' is explicitly denied by operator profile",
            )

        # 4. Spend limit check
        if requested_spend_eur > self.profile.max_spend_per_op_eur:
            return ProfileEvaluationResult(
                allowed=False,
                profile_digest=self.profile_digest,
                policy_epoch=self.profile.policy_epoch,
                diagnostic_message=f"SPEND_LIMIT_EXCEEDED: requested {requested_spend_eur} EUR exceeds per-op limit {self.profile.max_spend_per_op_eur} EUR",
            )

        return ProfileEvaluationResult(
            allowed=True,
            profile_digest=self.profile_digest,
            policy_epoch=self.profile.policy_epoch,
            diagnostic_message="DISPATCH_PERMITTED: action complies with signed operator profile",
        )
