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

"""Core Proof Engine & SCITT Verifier (core_proof_engine.py / scitt_verifier.py)

Implements:
  1. RFC 9162 Domain-Separated Merkle Tree Inclusion Proofs
     - Leaf: SHA-256(0x00 || leaf_data)
     - Interior Node: SHA-256(0x01 || left || right)
  2. RFC 8785 JSON Canonicalization Scheme (JCS)
  3. Ed25519 Cryptographic Signature Verification
  4. SCITT (Supply Chain Integrity, Transparency, and Trust) Receipt Validation

Falsifiability Invariant:
  Mutating a single character in a receipt payload immediately alters the
  JCS digest or Merkle root hash, triggering an audit failure.
"""

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature


def rfc8785_canonicalize(obj: Any) -> bytes:
    """Canonicalizes JSON data according to RFC 8785 JSON Canonicalization Scheme (JCS)."""
    if isinstance(obj, dict):
        # Sort keys by UTF-16 code units (ASCII alphanumeric sorts identically)
        sorted_items = sorted(obj.items(), key=lambda kv: kv[0])
        parts = [
            f"{json.dumps(k, ensure_ascii=False)}:{rfc8785_canonicalize(v).decode('utf-8')}"
            for k, v in sorted_items
        ]
        return ("{" + ",".join(parts) + "}").encode("utf-8")
    elif isinstance(obj, list):
        parts = [rfc8785_canonicalize(x).decode("utf-8") for x in obj]
        return ("[" + ",".join(parts) + "]").encode("utf-8")
    elif isinstance(obj, str):
        return json.dumps(obj, ensure_ascii=False).encode("utf-8")
    elif isinstance(obj, (int, float, bool)) or obj is None:
        return json.dumps(obj).encode("utf-8")
    else:
        raise TypeError(f"Object of type {type(obj)} is not JCS-canonicalizable")


def jcs_sha256_digest(obj: Any) -> str:
    """Computes SHA-256 hex digest of RFC 8785 canonicalized JSON."""
    canonical_bytes = rfc8785_canonicalize(obj)
    return hashlib.sha256(canonical_bytes).hexdigest()


# ── RFC 9162 Merkle Tree Functions ──────────────────────────────────────────

def rfc9162_hash_leaf(data: bytes) -> bytes:
    """Computes RFC 9162 leaf hash: SHA-256(0x00 || data)."""
    return hashlib.sha256(bytes([0x00]) + data).digest()


def rfc9162_hash_children(left: bytes, right: bytes) -> bytes:
    """Computes RFC 9162 interior node hash: SHA-256(0x01 || left || right)."""
    return hashlib.sha256(bytes([0x01]) + left + right).digest()


def verify_rfc9162_inclusion(
    leaf_hash: bytes,
    leaf_index: int,
    tree_size: int,
    audit_path: List[bytes],
    root_hash: bytes,
) -> bool:
    """Verifies an RFC 9162 audit path demonstrating membership of leaf_hash in root_hash."""
    if tree_size == 0 or leaf_index >= tree_size or leaf_index < 0:
        return False
    if tree_size == 1:
        return len(audit_path) == 0 and hmac.compare_digest(leaf_hash, root_hash)
    if len(audit_path) == 0:
        return False

    fn = leaf_index
    sn = tree_size - 1
    current = leaf_hash

    for sibling in audit_path:
        if sn == 0:
            return False
        is_right = (fn % 2 == 1) or (fn == sn)
        if is_right:
            current = rfc9162_hash_children(sibling, current)
            while (fn % 2 == 0) and (fn < sn):
                fn //= 2
                sn //= 2
        else:
            current = rfc9162_hash_children(current, sibling)
        fn //= 2
        sn //= 2

    return hmac.compare_digest(current, root_hash)


# ── Verification Results ────────────────────────────────────────────────────

@dataclass(frozen=True)
class ProofVerificationResult:
    is_valid: bool
    status_code: int
    error_message: str
    computed_root_hex: str
    computed_jcs_digest: str


ERR_SUCCESS = 0
ERR_JSON_PARSE = -1
ERR_MERKLE_BOUNDARY = -2
ERR_MERKLE_PROOF_MISMATCH = -3
ERR_SIGNATURE_INVALID = -4
ERR_TIMESTAMP_INVALID = -5
ERR_DISPOSITION_TOXIC = -6


class CoreProofEngine:
    """Pure cryptographic proof engine for SCITT and Merkle tree audit logs."""

    @staticmethod
    def verify_receipt(receipt: Dict[str, Any]) -> ProofVerificationResult:
        # 1. Required fields check
        required_fields = [
            "version", "action_id", "leaf_index", "tree_size",
            "timestamp", "intent_digest", "verdict", "root_hash",
            "signature", "signer_pubkey"
        ]
        for f in required_fields:
            if f not in receipt:
                return ProofVerificationResult(
                    is_valid=False,
                    status_code=ERR_JSON_PARSE,
                    error_message=f"Missing required field '{f}'",
                    computed_root_hex="",
                    computed_jcs_digest="",
                )

        # 2. Version check
        version = receipt.get("version")
        if version not in ("1.0.0", "1.1.0"):
            return ProofVerificationResult(
                is_valid=False,
                status_code=ERR_JSON_PARSE,
                error_message=f"Unsupported version '{version}'",
                computed_root_hex="",
                computed_jcs_digest="",
            )

        # 3. Check Merkle boundary
        idx = receipt.get("leaf_index")
        size = receipt.get("tree_size")
        if not isinstance(idx, int) or not isinstance(size, int) or size == 0 or idx >= size or idx < 0:
            return ProofVerificationResult(
                is_valid=False,
                status_code=ERR_MERKLE_BOUNDARY,
                error_message="Merkle boundary violation: leaf_index must be in [0, tree_size - 1] with tree_size >= 1",
                computed_root_hex="",
                computed_jcs_digest="",
            )

        # 4. Validate Disposition
        verdict = str(receipt.get("verdict", ""))
        if verdict == "TOXIC_CONFIRMED":
            return ProofVerificationResult(
                is_valid=False,
                status_code=ERR_DISPOSITION_TOXIC,
                error_message="Prohibited toxic disposition assertion detected",
                computed_root_hex="",
                computed_jcs_digest="",
            )

        valid_dispositions = {
            "CONFIRMED", "UNKNOWN", "MISSING_EVIDENCE", "CONFLICT", "REFUSED", "INVALID_INPUT"
        }
        if verdict not in valid_dispositions:
            return ProofVerificationResult(
                is_valid=False,
                status_code=ERR_JSON_PARSE,
                error_message=f"Invalid disposition '{verdict}'",
                computed_root_hex="",
                computed_jcs_digest="",
            )

        # 5. Timestamp sanity check
        ts = str(receipt.get("timestamp", ""))
        if len(ts) >= 4:
            try:
                year = int(ts[:4])
                if not (2024 <= year <= 2030):
                    return ProofVerificationResult(
                        is_valid=False,
                        status_code=ERR_TIMESTAMP_INVALID,
                        error_message=f"Timestamp year {year} is outside valid operational window [2024, 2030]",
                        computed_root_hex="",
                        computed_jcs_digest="",
                    )
            except ValueError:
                return ProofVerificationResult(
                    is_valid=False,
                    status_code=ERR_TIMESTAMP_INVALID,
                    error_message="Malformed timestamp year",
                    computed_root_hex="",
                    computed_jcs_digest="",
                )

        # 6. Compute canonical JCS digest of action payload
        action_id = str(receipt.get("action_id", ""))
        intent_digest_hex = str(receipt.get("intent_digest", ""))
        
        try:
            intent_bytes = bytes.fromhex(intent_digest_hex)
            if len(intent_bytes) != 32:
                return ProofVerificationResult(
                    is_valid=False,
                    status_code=ERR_JSON_PARSE,
                    error_message="intent_digest must be 32 bytes (64 hex characters)",
                    computed_root_hex="",
                    computed_jcs_digest="",
                )
        except ValueError:
            return ProofVerificationResult(
                is_valid=False,
                status_code=ERR_JSON_PARSE,
                error_message="Invalid intent_digest hex string",
                computed_root_hex="",
                computed_jcs_digest="",
            )

        # 7. Compute RFC 9162 domain-separated leaf hash
        leaf_content = action_id.encode("utf-8") + intent_bytes + verdict.encode("utf-8")
        computed_leaf_hash = rfc9162_hash_leaf(leaf_content)

        # 8. Decode audit path and root hash
        root_hex = str(receipt.get("root_hash", ""))
        try:
            expected_root_bytes = bytes.fromhex(root_hex)
            if len(expected_root_bytes) != 32:
                return ProofVerificationResult(
                    is_valid=False,
                    status_code=ERR_JSON_PARSE,
                    error_message="root_hash must be 32 bytes (64 hex characters)",
                    computed_root_hex="",
                    computed_jcs_digest="",
                )
        except ValueError:
            return ProofVerificationResult(
                is_valid=False,
                status_code=ERR_JSON_PARSE,
                error_message="Invalid root_hash hex string",
                computed_root_hex="",
                computed_jcs_digest="",
            )

        audit_path: List[bytes] = []
        for sibling_hex in receipt.get("inclusion_proof", []):
            try:
                b = bytes.fromhex(sibling_hex)
                if len(b) != 32:
                    return ProofVerificationResult(
                        is_valid=False,
                        status_code=ERR_JSON_PARSE,
                        error_message="Sibling in inclusion_proof must be 32 bytes",
                        computed_root_hex="",
                        computed_jcs_digest="",
                    )
                audit_path.append(b)
            except ValueError:
                return ProofVerificationResult(
                    is_valid=False,
                    status_code=ERR_JSON_PARSE,
                    error_message="Invalid sibling hex string in inclusion_proof",
                    computed_root_hex="",
                    computed_jcs_digest="",
                )

        # 9. Verify RFC 9162 Merkle inclusion
        merkle_match = verify_rfc9162_inclusion(
            leaf_hash=computed_leaf_hash,
            leaf_index=idx,
            tree_size=size,
            audit_path=audit_path,
            root_hash=expected_root_bytes,
        )

        computed_jcs = jcs_sha256_digest({
            "action_id": action_id,
            "intent_digest": intent_digest_hex,
            "verdict": verdict,
        })

        if not merkle_match:
            return ProofVerificationResult(
                is_valid=False,
                status_code=ERR_MERKLE_PROOF_MISMATCH,
                error_message="Merkle root mismatch: computed leaf does not authenticate against root_hash",
                computed_root_hex=computed_leaf_hash.hex() if size == 1 else "",
                computed_jcs_digest=computed_jcs,
            )

        # 10. Verify Ed25519 signature
        sig_hex = receipt.get("signature")
        pubkey_hex = receipt.get("signer_pubkey")

        try:
            sig_bytes = bytes.fromhex(str(sig_hex))
            pub_bytes = bytes.fromhex(str(pubkey_hex))
            if len(sig_bytes) != 64 or len(pub_bytes) != 32:
                return ProofVerificationResult(
                    is_valid=False,
                    status_code=ERR_JSON_PARSE if len(pub_bytes) != 32 else ERR_SIGNATURE_INVALID,
                    error_message="Invalid signature or public key byte length",
                    computed_root_hex=root_hex,
                    computed_jcs_digest=computed_jcs,
                )
            vk = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
            
            # Signed msg: root_hash + action_id + verdict + timestamp
            signed_msg = expected_root_bytes + action_id.encode("utf-8") + verdict.encode("utf-8") + ts.encode("utf-8")
            vk.verify(sig_bytes, signed_msg)
        except (InvalidSignature, ValueError):
            return ProofVerificationResult(
                is_valid=False,
                status_code=ERR_SIGNATURE_INVALID,
                error_message="Ed25519 signature verification failed or signature corrupted",
                computed_root_hex=root_hex,
                computed_jcs_digest=computed_jcs,
            )

        return ProofVerificationResult(
            is_valid=True,
            status_code=ERR_SUCCESS,
            error_message="Receipt cryptographically verified with RFC 9162 inclusion and Ed25519 signature",
            computed_root_hex=root_hex,
            computed_jcs_digest=computed_jcs,
        )

# SCITT Verifier alias
SCITTVerifier = CoreProofEngine
