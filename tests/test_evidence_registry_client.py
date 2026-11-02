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
test_evidence_registry_client.py — Unit Tests for Evidence Registry Client & AT52 Predicate
Evaluates existential inclusion, cryptographic signature verification, issuer trust,
and policy epoch alignment using real Ed25519 asymmetric cryptography.
"""

import hashlib
import pytest
import sys
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.jcs_canonicalizer import encode_jcs
from src.evidence_registry_client import (
    RegistryEntry,
    EvidenceRegistry,
    EvidenceRegistryClient,
    EvidenceChainVerified,
    CitationCryptographicVerificationError,
)


class TestEvidenceRegistryClient:
    def setup_method(self):
        # Generate real Ed25519 keys for testing authorities
        self.regulator_key = ed25519.Ed25519PrivateKey.generate()
        self.regulator_pubkey_bytes = self.regulator_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        self.trusted_issuer = "trusted:authority:eba_dora"
        self.policy_epoch = "policy:epoch_104"

        self.registry = EvidenceRegistry()
        self.client = EvidenceRegistryClient(
            registry=self.registry,
            trusted_issuers={self.trusted_issuer},
            current_policy_epoch=self.policy_epoch,
        )

    def _create_signed_entry(
        self,
        citation_id: str,
        payload: dict,
        key: ed25519.Ed25519PrivateKey,
        issuer: str,
        epoch: str,
        status: str = "ACTIVE",
    ) -> RegistryEntry:
        canonical_bytes = encode_jcs(payload)
        content_hash = hashlib.sha256(canonical_bytes).hexdigest()
        sig = key.sign(content_hash.encode("utf-8"))
        pub_bytes = key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return RegistryEntry(
            citation_id=citation_id,
            title="DORA Regulatory Technical Standard",
            payload=payload,
            content_hash=content_hash,
            issuer=issuer,
            epoch=epoch,
            signature=sig,
            public_key_bytes=pub_bytes,
            status=status,
        )

    def test_valid_citation_chain_verifies_successfully(self):
        entry = self._create_signed_entry(
            citation_id="urn:dora:rts-2024-1772:art-17",
            payload={"article": 17, "scope": "major_incident", "window_hours": 4},
            key=self.regulator_key,
            issuer=self.trusted_issuer,
            epoch=self.policy_epoch,
        )
        self.registry.register_entry(entry)

        verified, reason, details = self.client.evidence_chain_verified(
            ["urn:dora:rts-2024-1772:art-17"]
        )
        assert verified is True
        assert reason == "ALL_CITATIONS_VERIFIED"
        assert len(details) == 1
        assert details[0]["valid"] is True

        # Mathematical helper test
        assert EvidenceChainVerified(["urn:dora:rts-2024-1772:art-17"], self.client) is True

    def test_missing_citation_fails_closed(self):
        verified, reason, _ = self.client.evidence_chain_verified(
            ["urn:dora:unknown_citation"]
        )
        assert verified is False
        assert "CITATION_NOT_FOUND_IN_REGISTRY" in reason
        assert EvidenceChainVerified(["urn:dora:unknown_citation"], self.client) is False

    def test_untrusted_issuer_fails_closed(self):
        rogue_key = ed25519.Ed25519PrivateKey.generate()
        entry = self._create_signed_entry(
            citation_id="urn:untrusted:spec:001",
            payload={"rule": "bypass_gate"},
            key=rogue_key,
            issuer="untrusted:entity:shadow",
            epoch=self.policy_epoch,
        )
        self.registry.register_entry(entry)

        verified, reason, _ = self.client.evidence_chain_verified(["urn:untrusted:spec:001"])
        assert verified is False
        assert "CITATION_ISSUER_UNTRUSTED" in reason

    def test_epoch_mismatch_fails_closed(self):
        stale_entry = self._create_signed_entry(
            citation_id="urn:dora:stale_policy",
            payload={"version": "1.0"},
            key=self.regulator_key,
            issuer=self.trusted_issuer,
            epoch="policy:epoch_103",  # Stale epoch
        )
        self.registry.register_entry(stale_entry)

        verified, reason, _ = self.client.evidence_chain_verified(["urn:dora:stale_policy"])
        assert verified is False
        assert "CITATION_EPOCH_MISMATCH" in reason

    def test_corrupted_signature_rejected_at_registration(self):
        canonical_bytes = encode_jcs({"test": "data"})
        content_hash = hashlib.sha256(canonical_bytes).hexdigest()
        corrupted_sig = b"\x00" * 64

        entry = RegistryEntry(
            citation_id="urn:corrupted:sig",
            title="Corrupted Entry",
            payload={"test": "data"},
            content_hash=content_hash,
            issuer=self.trusted_issuer,
            epoch=self.policy_epoch,
            signature=corrupted_sig,
            public_key_bytes=self.regulator_pubkey_bytes,
        )
        with pytest.raises(CitationCryptographicVerificationError):
            self.registry.register_entry(entry)

    def test_revoked_citation_fails_closed(self):
        entry = self._create_signed_entry(
            citation_id="urn:dora:revoked:001",
            payload={"rule": "obsolete_guideline"},
            key=self.regulator_key,
            issuer=self.trusted_issuer,
            epoch=self.policy_epoch,
        )
        self.registry.register_entry(entry)
        self.registry.revoke_entry("urn:dora:revoked:001")

        verified, reason, _ = self.client.evidence_chain_verified(["urn:dora:revoked:001"])
        assert verified is False
        assert "CITATION_STATUS_INACTIVE" in reason

    def test_empty_citations_returns_true_zero_citations(self):
        verified, reason, details = self.client.evidence_chain_verified([])
        assert verified is True
        assert reason == "ZERO_CITATIONS_PROVIDED"
        assert details == []

    def test_content_hash_mismatch_raises_error(self):
        entry = RegistryEntry(
            citation_id="urn:tampered:hash",
            title="Tampered Entry",
            payload={"key": "val"},
            content_hash="bad_hash" * 8,
            issuer=self.trusted_issuer,
            epoch=self.policy_epoch,
            signature=b"\x00" * 64,
            public_key_bytes=self.regulator_pubkey_bytes,
        )
        with pytest.raises(CitationCryptographicVerificationError, match="Content hash mismatch"):
            self.registry.register_entry(entry)

    def test_has_entry_and_get_entry(self):
        entry = self._create_signed_entry(
            citation_id="urn:dora:present:001",
            payload={"item": 1},
            key=self.regulator_key,
            issuer=self.trusted_issuer,
            epoch=self.policy_epoch,
        )
        assert self.registry.has_entry("urn:dora:present:001") is False
        assert self.registry.get_entry("urn:dora:present:001") is None
        self.registry.register_entry(entry)
        assert self.registry.has_entry("urn:dora:present:001") is True
        assert self.registry.get_entry("urn:dora:present:001") == entry
        assert self.registry.has_entry("urn:dora:missing") is False

    def test_post_registration_tampered_signature_fails_verification(self):
        entry = self._create_signed_entry(
            citation_id="urn:dora:tampered_after_reg",
            payload={"item": "safe"},
            key=self.regulator_key,
            issuer=self.trusted_issuer,
            epoch=self.policy_epoch,
        )
        self.registry.register_entry(entry)
        # Tamper signature in memory
        entry.signature = b"\xff" * 64
        valid, reason, res_entry = self.client.verify_single_citation("urn:dora:tampered_after_reg")
        assert valid is False
        assert reason == "CITATION_SIGNATURE_VERIFICATION_FAILED"
        assert res_entry == entry

    def test_registry_entry_to_dict(self):
        entry = self._create_signed_entry(
            citation_id="urn:test:dict",
            payload={"flag": True},
            key=self.regulator_key,
            issuer=self.trusted_issuer,
            epoch=self.policy_epoch,
        )
        d = entry.to_dict()
        assert d["citation_id"] == "urn:test:dict"
        assert d["payload"] == {"flag": True}
        assert d["issuer"] == self.trusted_issuer
        assert d["epoch"] == self.policy_epoch
        assert d["status"] == "ACTIVE"
        assert d["public_key_hex"] == self.regulator_pubkey_bytes.hex()
        assert "registered_at_utc" in d

    def test_register_trusted_issuer_and_default_epoch(self):
        client = EvidenceRegistryClient()
        assert client.current_policy_epoch == "policy:epoch_104"
        client.register_trusted_issuer("new:issuer")
        assert "new:issuer" in client.trusted_issuers

