#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
#
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

r"""
src/evidence_registry_client.py — Verifiable Evidence Registry Client
Sovereign Multi-Agent OS (SMAOS) / AEIB v0.4.1

Implements Citation Existential Verification (AT52 / EvidenceChainVerified predicate).
Evaluates whether candidate actions citing regulatory or policy sources
have active, non-revoked existential presence in a trusted registry, aligned with
the current policy epoch and cryptographically verified under Ed25519:

    EvidenceChainVerified(citations) =
        ∀ c ∈ citations: (c ∈ EvidenceRegistry ∧
                          RegistryEntry(c).issuer ∈ TrustedIssuers ∧
                          RegistryEntry(c).epoch == CurrentPolicyEpoch ∧
                          RegistryEntry(c).status == "ACTIVE" ∧
                          VerifySignature(RegistryEntry(c)))
"""

import hashlib
from typing import Dict, Any, Optional, List, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature

try:
    from src.jcs_canonicalizer import encode_jcs, generate_jcs_payload_hash
except ImportError:
    from jcs_canonicalizer import encode_jcs, generate_jcs_payload_hash


class EvidenceRegistryError(Exception):
    """Base error for evidence registry operations."""
    pass


class CitationNotFoundError(EvidenceRegistryError):
    """Raised when a cited regulatory or policy evidence ID is absent from the registry."""
    pass


class CitationUntrustedIssuerError(EvidenceRegistryError):
    """Raised when a citation's signing authority is not in the trusted issuers set."""
    pass


class CitationEpochMismatchError(EvidenceRegistryError):
    """Raised when a citation's policy epoch diverges from the active gateway epoch."""
    pass


class CitationCryptographicVerificationError(EvidenceRegistryError):
    """Raised when an Ed25519 digital signature fails mathematical verification."""
    pass


class CitationRevokedError(EvidenceRegistryError):
    """Raised when a cited entry is marked revoked, suspended, or inactive."""
    pass


@dataclass
class RegistryEntry:
    """
    Cryptographic entry representing an immutable policy, regulatory, or evidence statement.
    """
    citation_id: str
    title: str
    payload: Dict[str, Any]
    content_hash: str
    issuer: str
    epoch: str
    signature: bytes
    public_key_bytes: bytes
    status: str = "ACTIVE"
    registered_at_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "citation_id": self.citation_id,
            "title": self.title,
            "payload": self.payload,
            "content_hash": self.content_hash,
            "issuer": self.issuer,
            "epoch": self.epoch,
            "public_key_hex": self.public_key_bytes.hex(),
            "status": self.status,
            "registered_at_utc": self.registered_at_utc,
        }


class EvidenceRegistry:
    """
    Append-only repository of verified evidence and regulatory citations.
    All registered entries require valid RFC 8785 JCS content hashes and Ed25519 signatures.
    """

    def __init__(self):
        self._entries: Dict[str, RegistryEntry] = {}

    def register_entry(self, entry: RegistryEntry) -> None:
        """
        Validates content hash and Ed25519 signature before inserting into the registry.
        Fails closed on any corruption or invalid cryptographic signature.
        """
        # Validate canonical JCS hash
        canonical_bytes = encode_jcs(entry.payload)
        expected_hash = hashlib.sha256(canonical_bytes).hexdigest()
        if entry.content_hash != expected_hash:
            raise CitationCryptographicVerificationError(
                f"Content hash mismatch for {entry.citation_id}: {entry.content_hash} != {expected_hash}"
            )

        # Cryptographically verify Ed25519 signature over canonical content hash
        try:
            pubkey = ed25519.Ed25519PublicKey.from_public_bytes(entry.public_key_bytes)
            pubkey.verify(entry.signature, entry.content_hash.encode("utf-8"))
        except InvalidSignature as exc:
            raise CitationCryptographicVerificationError(
                f"Invalid Ed25519 signature for citation {entry.citation_id}"
            ) from exc

        self._entries[entry.citation_id] = entry

    def get_entry(self, citation_id: str) -> Optional[RegistryEntry]:
        """Retrieves entry by citation ID."""
        return self._entries.get(citation_id)

    def has_entry(self, citation_id: str) -> bool:
        """Checks existential presence of citation ID."""
        return citation_id in self._entries

    def revoke_entry(self, citation_id: str) -> None:
        """Marks an existing entry as revoked."""
        if citation_id in self._entries:
            self._entries[citation_id].status = "REVOKED"


class EvidenceRegistryClient:
    """
    Client for querying the Verifiable Evidence Registry and evaluating the
    EvidenceChainVerified predicate at the T_dispatch boundary.
    """

    def __init__(
        self,
        registry: Optional[EvidenceRegistry] = None,
        trusted_issuers: Optional[Set[str]] = None,
        current_policy_epoch: str = "policy:epoch_104",
    ):
        self.registry = registry or EvidenceRegistry()
        self.trusted_issuers = trusted_issuers or set()
        self.current_policy_epoch = current_policy_epoch

    def register_trusted_issuer(self, issuer_id: str) -> None:
        """Adds an issuer ID to the trusted set."""
        self.trusted_issuers.add(issuer_id)

    def verify_single_citation(
        self,
        citation_id: str,
        current_epoch: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[RegistryEntry]]:
        """
        Evaluates existential inclusion, issuer standing, epoch match, and cryptographic validity.
        Fails closed on any negative condition.
        """
        epoch_to_check = current_epoch or self.current_policy_epoch
        entry = self.registry.get_entry(citation_id)

        if entry is None:
            return False, "CITATION_NOT_FOUND_IN_REGISTRY", None

        if entry.status != "ACTIVE":
            return False, f"CITATION_STATUS_INACTIVE: {entry.status}", entry

        if entry.issuer not in self.trusted_issuers:
            return False, f"CITATION_ISSUER_UNTRUSTED: {entry.issuer}", entry

        if entry.epoch != epoch_to_check:
            return False, f"CITATION_EPOCH_MISMATCH: {entry.epoch} != {epoch_to_check}", entry

        # Verify signature with the entry's registered public key
        try:
            pubkey = ed25519.Ed25519PublicKey.from_public_bytes(entry.public_key_bytes)
            pubkey.verify(entry.signature, entry.content_hash.encode("utf-8"))
        except (InvalidSignature, ValueError):
            return False, "CITATION_SIGNATURE_VERIFICATION_FAILED", entry

        return True, "VERIFIED", entry

    def evidence_chain_verified(
        self,
        citations: List[str],
        current_epoch: Optional[str] = None,
    ) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """
        Evaluates the composite EvidenceChainVerified predicate:
        Returns (True, "ALL_CITATIONS_VERIFIED", details) iff ALL citations satisfy all predicates.
        Fails closed (False, reason, details) if any citation fails or is missing.
        """
        if not citations:
            return True, "ZERO_CITATIONS_PROVIDED", []

        results = []
        for citation_id in citations:
            valid, reason, entry = self.verify_single_citation(citation_id, current_epoch)
            results.append({
                "citation_id": citation_id,
                "valid": valid,
                "reason": reason,
                "entry": entry.to_dict() if entry else None,
            })
            if not valid:
                return False, f"CITATION_VERIFICATION_FAILED: {reason}", results

        return True, "ALL_CITATIONS_VERIFIED", results


def EvidenceChainVerified(
    citations: List[str],
    client: EvidenceRegistryClient,
    current_epoch: Optional[str] = None,
) -> bool:
    """
    Mathematical helper evaluating EvidenceChainVerified(citations) -> bool.
    """
    verified, _, _ = client.evidence_chain_verified(citations, current_epoch)
    return verified
