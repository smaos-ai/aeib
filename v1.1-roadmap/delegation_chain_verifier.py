"""
v1.1-roadmap/delegation_chain_verifier.py — Multi-Hop Delegation Chain Verifier Prototype.
Sovereign Multi-Agent OS (SMAOS) / Agent Execution Integrity Boundary (AEIB).

Tier 2 Core Delivery Contract:
Enforces monotonic authority attenuation across multi-hop agent delegation chains
(IETF AIP / UCAN / Macaroon alignment):
  1. Root trust anchor verification (anchored to configured enterprise sponsor key).
  2. Cryptographic key continuity: Hop(N).delegator matches Hop(N-1).delegatee.
  3. Monotonic scope attenuation: Hop(N).scopes is a strict subset of Hop(N-1).scopes.
  4. Monotonic financial budget attenuation: Hop(N).max_spend <= Hop(N-1).max_spend.
  5. Audience binding: Token binds the intended downstream tool/service audience.
  6. Expiry monotonicity: Hop(N).valid_until <= Hop(N-1).valid_until.
  7. Explicit revocation evaluation against an operator revocation list.

Operates under the stated model: Fails closed on any scope or budget expansion attempt.
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


class DelegationError(Exception):
    """Base exception for delegation chain verification errors."""


@dataclass(frozen=True)
class DelegationHop:
    """Individual signed hop in a multi-hop delegation chain."""

    delegator_principal_id: str
    delegatee_agent_id: str
    audience: str
    permitted_scopes: List[str]
    max_spend_eur: int
    valid_until_epoch: int
    signature_hex: str

    def to_canonical_statement(self) -> Dict[str, Any]:
        return {
            "audience": self.audience,
            "delegateeAgentId": self.delegatee_agent_id,
            "delegatorPrincipalId": self.delegator_principal_id,
            "maxSpendEur": self.max_spend_eur,
            "permittedScopes": sorted(self.permitted_scopes),
            "validUntilEpoch": self.valid_until_epoch,
        }


@dataclass(frozen=True)
class DelegationVerdict:
    """Deterministic evaluation verdict for a delegation chain."""

    valid: bool
    effective_scopes: Set[str]
    effective_max_spend_eur: int
    delegation_depth: int
    diagnostic_message: str


class DelegationChainVerifier:
    """
    AEIB Tier 2 Delegation Chain Verifier.
    Asserts strict monotonic attenuation from root sponsor to leaf executing agent.
    """

    def __init__(
        self,
        *,
        root_sponsor_public_key: Ed25519PublicKey,
        root_sponsor_principal_id: str,
        known_agent_keys: Dict[str, Ed25519PublicKey],
        revoked_principal_ids: Optional[Set[str]] = None,
    ) -> None:
        self.root_sponsor_public_key = root_sponsor_public_key
        self.root_sponsor_principal_id = root_sponsor_principal_id
        self.known_agent_keys = known_agent_keys
        self.revoked_principal_ids = revoked_principal_ids or set()

    def verify_chain(
        self,
        chain: List[DelegationHop],
        target_audience: str,
        current_timestamp: int,
    ) -> DelegationVerdict:
        """
        Evaluates a delegation chain from root sponsor to final delegatee.
        Asserts cryptographic signatures, key continuity, audience binding,
        and monotonic scope/budget attenuation.
        """
        if not chain:
            return DelegationVerdict(
                valid=False,
                effective_scopes=set(),
                effective_max_spend_eur=0,
                delegation_depth=0,
                diagnostic_message="CHAIN_EMPTY: empty delegation chain rejected fail-closed",
            )

        running_scopes: Optional[Set[str]] = None
        running_max_spend: int = 1 << 62  # effectively unbounded upper sentinel
        running_valid_until: int = 1 << 62
        expected_delegator: str = self.root_sponsor_principal_id

        for idx, hop in enumerate(chain):
            # 1. Revocation check
            if hop.delegator_principal_id in self.revoked_principal_ids:
                return DelegationVerdict(
                    valid=False,
                    effective_scopes=set(),
                    effective_max_spend_eur=0,
                    delegation_depth=idx,
                    diagnostic_message=f"REVOKED_DELEGATOR: hop {idx} delegator '{hop.delegator_principal_id}' is revoked",
                )

            # 2. Expiration check
            if current_timestamp > hop.valid_until_epoch:
                return DelegationVerdict(
                    valid=False,
                    effective_scopes=set(),
                    effective_max_spend_eur=0,
                    delegation_depth=idx,
                    diagnostic_message=f"HOP_EXPIRED: hop {idx} expired at {hop.valid_until_epoch} (current: {current_timestamp})",
                )

            # 3. Expiry monotonicity check: Hop(N).valid_until <= Hop(N-1).valid_until
            if hop.valid_until_epoch > running_valid_until:
                return DelegationVerdict(
                    valid=False,
                    effective_scopes=set(),
                    effective_max_spend_eur=0,
                    delegation_depth=idx,
                    diagnostic_message=f"EXPIRY_EXPANSION_VIOLATION: hop {idx} expiry ({hop.valid_until_epoch}) exceeds parent ({running_valid_until})",
                )
            running_valid_until = hop.valid_until_epoch

            # 4. Continuity check: delegator must match expected delegatee from previous hop
            if hop.delegator_principal_id != expected_delegator:
                return DelegationVerdict(
                    valid=False,
                    effective_scopes=set(),
                    effective_max_spend_eur=0,
                    delegation_depth=idx,
                    diagnostic_message=f"CONTINUITY_BREAK: hop {idx} expected delegator '{expected_delegator}', got '{hop.delegator_principal_id}'",
                )

            # 5. Audience binding check: each hop must permit target audience
            if hop.audience != "*" and hop.audience != target_audience:
                return DelegationVerdict(
                    valid=False,
                    effective_scopes=set(),
                    effective_max_spend_eur=0,
                    delegation_depth=idx,
                    diagnostic_message=f"AUDIENCE_MISMATCH: hop {idx} audience '{hop.audience}' does not match target '{target_audience}'",
                )

            # 6. Cryptographic signature verification
            signing_key: Ed25519PublicKey
            if idx == 0:
                signing_key = self.root_sponsor_public_key
            else:
                if hop.delegator_principal_id not in self.known_agent_keys:
                    return DelegationVerdict(
                        valid=False,
                        effective_scopes=set(),
                        effective_max_spend_eur=0,
                        delegation_depth=idx,
                        diagnostic_message=f"UNKNOWN_SIGNER_KEY: no public key registered for delegator '{hop.delegator_principal_id}'",
                    )
                signing_key = self.known_agent_keys[hop.delegator_principal_id]

            statement_bytes = encode_jcs(hop.to_canonical_statement())
            try:
                sig_bytes = bytes.fromhex(hop.signature_hex)
                signing_key.verify(sig_bytes, statement_bytes)
            except (InvalidSignature, ValueError) as err:
                return DelegationVerdict(
                    valid=False,
                    effective_scopes=set(),
                    effective_max_spend_eur=0,
                    delegation_depth=idx,
                    diagnostic_message=f"SIGNATURE_INVALID: hop {idx} signature verification failed: {err}",
                )

            # 7. Monotonic scope attenuation check: Hop(N).scopes must be subset of Hop(N-1).scopes
            hop_scopes = set(hop.permitted_scopes)
            if running_scopes is None:
                running_scopes = hop_scopes
            else:
                expanded = hop_scopes - running_scopes
                if expanded:
                    return DelegationVerdict(
                        valid=False,
                        effective_scopes=set(),
                        effective_max_spend_eur=0,
                        delegation_depth=idx,
                        diagnostic_message=f"SCOPE_EXPANSION_VIOLATION: hop {idx} expanded unauthorized scopes: {sorted(expanded)}",
                    )
                running_scopes = hop_scopes

            # 8. Monotonic budget attenuation check: Hop(N).spend must be <= Hop(N-1).spend
            if hop.max_spend_eur > running_max_spend:
                return DelegationVerdict(
                    valid=False,
                    effective_scopes=set(),
                    effective_max_spend_eur=0,
                    delegation_depth=idx,
                    diagnostic_message=f"BUDGET_EXPANSION_VIOLATION: hop {idx} increased max spend: {hop.max_spend_eur} > {running_max_spend}",
                )
            running_max_spend = hop.max_spend_eur

            # Advance expected delegator to this hop's delegatee
            expected_delegator = hop.delegatee_agent_id

        return DelegationVerdict(
            valid=True,
            effective_scopes=running_scopes or set(),
            effective_max_spend_eur=running_max_spend,
            delegation_depth=len(chain),
            diagnostic_message="DELEGATION_CHAIN_VALID: strict monotonic attenuation confirmed across all hops",
        )
