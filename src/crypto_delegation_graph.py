#!/usr/bin/env python3
"""
Cryptographic Delegation Graph (src/crypto_delegation_graph.py).

Status: INTERNAL PREVIEW COMMISSIONED
Evaluated under the stated model to enforce cryptographic chain-of-custody and
monotonic scope delegation across multi-agent (A2A) hierarchies:
  1. Monotonic Scope Delegation: Child allowed_egress_hosts, allowed_tools,
     max_financial_minor, and max_blast_radius_bps must be a subset of Parent scope.
  2. Strict Temporal Bound Inheritance: Child token cannot outlive its Parent token
     (child.expires_at_epoch_sec <= parent.expires_at_epoch_sec) and must be issued
     within the Parent token's validity window.
  3. Full Ancestor Chain Verification: At dispatch evaluation time, walks the entire
     DAG up to GENESIS to verify no intermediate ancestor has expired or been unlinked.
  4. Single-Source RFC 8785 JCS Canonicalization: All token digests and Ed25519
     signatures are computed over canonical UTF-8 bytes with integer parameters.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Dict, Mapping, Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs
from src.temporal_authority_guard import sha256_caid


@dataclasses.dataclass(frozen=True)
class ScopeBoundary:
    """Monotonic scope limits for an agent delegation token."""

    allowed_egress_hosts: Tuple[str, ...]
    allowed_tools: Tuple[str, ...]
    max_financial_minor: int
    max_blast_radius_bps: int

    def __post_init__(self) -> None:
        if self.max_financial_minor < 0:
            raise ValueError(f"ERR_NEGATIVE_FINANCIAL_MINOR:{self.max_financial_minor}")
        if self.max_blast_radius_bps < 0 or self.max_blast_radius_bps > 10000:
            raise ValueError(f"ERR_INVALID_BLAST_RADIUS_BPS:{self.max_blast_radius_bps}")
        object.__setattr__(
            self, "allowed_egress_hosts", tuple(sorted(set(self.allowed_egress_hosts)))
        )
        object.__setattr__(self, "allowed_tools", tuple(sorted(set(self.allowed_tools))))

    def is_subset_of(self, other: "ScopeBoundary") -> bool:
        if not set(self.allowed_egress_hosts).issubset(set(other.allowed_egress_hosts)):
            return False
        if not set(self.allowed_tools).issubset(set(other.allowed_tools)):
            return False
        if self.max_financial_minor > other.max_financial_minor:
            return False
        if self.max_blast_radius_bps > other.max_blast_radius_bps:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed_egress_hosts": list(self.allowed_egress_hosts),
            "allowed_tools": list(self.allowed_tools),
            "max_blast_radius_bps": self.max_blast_radius_bps,
            "max_financial_minor": self.max_financial_minor,
        }


@dataclasses.dataclass(frozen=True)
class DelegationToken:
    """Signed capability token linking issuer SPIFFE ID to subject SPIFFE ID."""

    issuer_spiffe_id: str
    subject_spiffe_id: str
    scope: ScopeBoundary
    issued_at_epoch_sec: int
    expires_at_epoch_sec: int
    parent_token_caid: str
    signature_hex: str = ""

    def with_signature(self, sig_hex: str) -> "DelegationToken":
        return dataclasses.replace(self, signature_hex=sig_hex)

    def canonical_bytes(self) -> bytes:
        payload: Dict[str, Any] = {
            "expires_at_epoch_sec": self.expires_at_epoch_sec,
            "issued_at_epoch_sec": self.issued_at_epoch_sec,
            "issuer_spiffe_id": self.issuer_spiffe_id,
            "parent_token_caid": self.parent_token_caid,
            "scope": self.scope.to_dict(),
            "subject_spiffe_id": self.subject_spiffe_id,
        }
        return encode_jcs(payload)

    @property
    def caid(self) -> str:
        return sha256_caid(self.canonical_bytes())


@dataclasses.dataclass(frozen=True)
class AuthorityVerdict:
    """Evaluation outcome for a leaf action against the delegation DAG."""

    authorized: bool
    reason_code: str
    leaf_token_caid: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "authorized": self.authorized,
            "leaf_token_caid": self.leaf_token_caid,
            "reason_code": self.reason_code,
        }


class CryptoDelegationGraph:
    """
    Maintains the cryptographic DAG of delegation tokens and evaluates leaf authority.
    """

    def __init__(self, trust_store: Mapping[str, ed25519.Ed25519PublicKey]) -> None:
        self.trust_store: Dict[str, ed25519.Ed25519PublicKey] = dict(trust_store)
        self._token_registry: Dict[str, DelegationToken] = {}

    def register_token(self, token: DelegationToken) -> str:
        issuer_pubkey = self.trust_store.get(token.issuer_spiffe_id)
        if not issuer_pubkey:
            raise ValueError(f"HALT_UNKNOWN_ISSUER:{token.issuer_spiffe_id}")

        try:
            sig_bytes = bytes.fromhex(token.signature_hex)
            issuer_pubkey.verify(sig_bytes, token.canonical_bytes())
        except (ValueError, InvalidSignature):
            raise ValueError("HALT_INVALID_DELEGATION_SIGNATURE")

        if token.expires_at_epoch_sec < token.issued_at_epoch_sec:
            raise ValueError("HALT_INVALID_TOKEN_TTL_WINDOW")

        if token.parent_token_caid != "GENESIS":
            parent_token = self._token_registry.get(token.parent_token_caid)
            if not parent_token:
                raise ValueError(f"HALT_ORPHAN_TOKEN:Parent {token.parent_token_caid} not found")

            if token.issuer_spiffe_id != parent_token.subject_spiffe_id:
                raise ValueError("HALT_DELEGATION_CHAIN_ISSUER_MISMATCH")

            if token.issued_at_epoch_sec < parent_token.issued_at_epoch_sec:
                raise ValueError("HALT_ISSUED_BEFORE_PARENT")

            if token.issued_at_epoch_sec > parent_token.expires_at_epoch_sec:
                raise ValueError("HALT_PARENT_EXPIRED_AT_ISSUANCE")

            if token.expires_at_epoch_sec > parent_token.expires_at_epoch_sec:
                raise ValueError("HALT_CHILD_OUTLIVES_PARENT_TTL")

            if not token.scope.is_subset_of(parent_token.scope):
                raise ValueError(
                    "HALT_SCOPE_MONOTONICITY_VIOLATION:Child exceeds Parent authority"
                )

        self._token_registry[token.caid] = token
        return token.caid

    def evaluate_action(
        self,
        actor_spiffe_id: str,
        leaf_token_caid: str,
        action_host: str,
        action_tool: str,
        amount_minor: int,
        current_time: int,
        blast_radius_bps: int = 0,
    ) -> AuthorityVerdict:
        token = self._token_registry.get(leaf_token_caid)
        if not token:
            return AuthorityVerdict(False, "HALT_UNKNOWN_LEAF_TOKEN", "")

        if token.subject_spiffe_id != actor_spiffe_id:
            return AuthorityVerdict(False, "HALT_SUBJECT_MISMATCH", leaf_token_caid)

        # Walk full ancestor chain up to GENESIS (bounded depth <= 32)
        curr: Optional[DelegationToken] = token
        for _ in range(32):
            if curr is None:
                return AuthorityVerdict(False, "HALT_BROKEN_ANCESTOR_CHAIN", leaf_token_caid)
            if current_time < curr.issued_at_epoch_sec:
                return AuthorityVerdict(False, "HALT_TOKEN_NOT_YET_VALID", leaf_token_caid)
            if current_time > curr.expires_at_epoch_sec:
                return AuthorityVerdict(False, "HALT_TOKEN_EXPIRED", leaf_token_caid)
            if curr.parent_token_caid == "GENESIS":
                break
            curr = self._token_registry.get(curr.parent_token_caid)

        if action_host not in token.scope.allowed_egress_hosts:
            return AuthorityVerdict(False, f"HALT_HOST_DENIED:{action_host}", leaf_token_caid)

        if action_tool not in token.scope.allowed_tools:
            return AuthorityVerdict(False, f"HALT_TOOL_DENIED:{action_tool}", leaf_token_caid)

        if amount_minor > token.scope.max_financial_minor:
            return AuthorityVerdict(
                False, f"HALT_AMOUNT_EXCEEDED:{amount_minor}", leaf_token_caid
            )

        if blast_radius_bps > token.scope.max_blast_radius_bps:
            return AuthorityVerdict(
                False, f"HALT_BLAST_RADIUS_EXCEEDED:{blast_radius_bps}", leaf_token_caid
            )

        return AuthorityVerdict(True, "OK_AUTHORITY_VERIFIED", leaf_token_caid)
