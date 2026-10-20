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

"""
tools/selective_disclosure_receipt.py — Selectively Redactable Evidence Receipts.

Resolves the structural regulatory tension between:
- GDPR Article 17 (Right to Erasure): Redacting sensitive PII (customer IBAN, names).
- DORA Article 17 & EU AI Act Article 12: Mandatory 10-year immutable audit logging.

Uses salted field commitments: allows redaction of designated PII fields while
preserving mathematical verifiability of the original Ed25519 signature.
"""

import base64
import hashlib
import json
import secrets
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from src.jcs_canonicalizer import encode_jcs


def compute_field_commitment(key: str, value: Any, salt: str) -> str:
    """Computes a deterministic cryptographic commitment for a single key-value-salt tuple."""
    val_bytes = encode_jcs(value)
    payload = f"{salt}:{key}:".encode("utf-8") + val_bytes
    return hashlib.sha256(payload).hexdigest()


def compute_receipt_root(field_commitments: Dict[str, str]) -> str:
    """Computes the deterministic Merkle-style root over lexicographically sorted field commitments."""
    sorted_keys = sorted(field_commitments.keys())
    combined = "".join(f"{k}:{field_commitments[k]};" for k in sorted_keys).encode("utf-8")
    return hashlib.sha256(combined).hexdigest()


@dataclass(frozen=True)
class SignedAuditReceipt:
    receipt_id: str
    claims: Dict[str, Any]
    salts: Dict[str, str]
    root_hash: str
    public_key_hex: str
    signature_b64: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "claims": self.claims,
            "salts": self.salts,
            "root_hash": self.root_hash,
            "signature_envelope": {
                "algorithm": "Ed25519",
                "public_key_hex": self.public_key_hex,
                "signature_b64": self.signature_b64,
            },
        }


@dataclass(frozen=True)
class RedactedAuditReceipt:
    receipt_id: str
    disclosed_claims: Dict[str, Any]
    disclosed_salts: Dict[str, str]
    redacted_field_commitments: Dict[str, str]
    root_hash: str
    public_key_hex: str
    signature_b64: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "disclosed_claims": self.disclosed_claims,
            "disclosed_salts": self.disclosed_salts,
            "redacted_field_commitments": self.redacted_field_commitments,
            "root_hash": self.root_hash,
            "signature_envelope": {
                "algorithm": "Ed25519",
                "public_key_hex": self.public_key_hex,
                "signature_b64": self.signature_b64,
            },
        }


class SelectiveDisclosureEngine:
    """Issues and verifies selectively redactable evidence receipts."""

    @staticmethod
    def create_signed_receipt(
        receipt_id: str,
        claims: Dict[str, Any],
        private_key: Ed25519PrivateKey,
    ) -> SignedAuditReceipt:
        salts = {k: secrets.token_hex(16) for k in claims.keys()}
        field_commitments = {
            k: compute_field_commitment(k, claims[k], salts[k]) for k in claims.keys()
        }
        root_hash = compute_receipt_root(field_commitments)

        sig = private_key.sign(root_hash.encode("utf-8"))
        pub_hex = private_key.public_key().public_bytes_raw().hex()

        return SignedAuditReceipt(
            receipt_id=receipt_id,
            claims=claims,
            salts=salts,
            root_hash=root_hash,
            public_key_hex=pub_hex,
            signature_b64=base64.b64encode(sig).decode("ascii"),
        )

    @staticmethod
    def redact_fields(
        receipt: SignedAuditReceipt,
        fields_to_redact: Set[str],
    ) -> RedactedAuditReceipt:
        disclosed_claims = {}
        disclosed_salts = {}
        redacted_commitments = {}

        for k, v in receipt.claims.items():
            if k in fields_to_redact:
                # Blind field: record precomputed commitment, withhold value and salt
                commit = compute_field_commitment(k, v, receipt.salts[k])
                redacted_commitments[k] = commit
            else:
                disclosed_claims[k] = v
                disclosed_salts[k] = receipt.salts[k]

        return RedactedAuditReceipt(
            receipt_id=receipt.receipt_id,
            disclosed_claims=disclosed_claims,
            disclosed_salts=disclosed_salts,
            redacted_field_commitments=redacted_commitments,
            root_hash=receipt.root_hash,
            public_key_hex=receipt.public_key_hex,
            signature_b64=receipt.signature_b64,
        )

    @staticmethod
    def verify_redacted_receipt(redacted: RedactedAuditReceipt) -> bool:
        """
        Verifies that a redacted receipt is authentic:
        1. Reconstructs field commitments for disclosed fields.
        2. Merges blind commitments for redacted fields.
        3. Verifies that reconstructed root hash matches the signed root hash.
        4. Verifies the Ed25519 signature over root hash.
        """
        reconstructed_commitments = {}

        # Reconstruct disclosed commitments
        for k, v in redacted.disclosed_claims.items():
            salt = redacted.disclosed_salts.get(k)
            if not salt:
                return False
            reconstructed_commitments[k] = compute_field_commitment(k, v, salt)

        # Merge blind commitments
        for k, commit in redacted.redacted_field_commitments.items():
            if k in reconstructed_commitments:
                return False  # Cannot be both disclosed and redacted
            reconstructed_commitments[k] = commit

        calculated_root = compute_receipt_root(reconstructed_commitments)
        if calculated_root != redacted.root_hash:
            return False

        # Verify signature
        try:
            pub_bytes = bytes.fromhex(redacted.public_key_hex)
            sig_bytes = base64.b64decode(redacted.signature_b64)
            ed_pub = Ed25519PublicKey.from_public_bytes(pub_bytes)
            ed_pub.verify(sig_bytes, calculated_root.encode("utf-8"))
            return True
        except Exception:
            return False
