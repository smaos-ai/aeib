#!/usr/bin/env python3
"""
AEIB RFC 9052 COSE_Sign1 & IETF SCITT (RFC 9942 / RFC 9943) Transparency Receipt Verifier.
Part of SovereignNexus AEIB v1.1 Architecture.

Evaluated under the stated model:
- RFC 9052 COSE_Sign1 CBOR envelopes (Tag 18)
- Exact Ed25519 signature over canonical Sig_structure
- RFC 8785 JCS inner receipt payload integrity
- RFC 9162 / RFC 9942 SHA-256 binary Merkle tree inclusion proofs with domain separation
- RFC 9943 SCITT Transparency Service registration and offline Transparent Statement verification
- External AAD binding (e.g. Merkle checkpoint root)
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

ROADMAP_COSE_PATH = REPO_ROOT / "v1.1-roadmap" / "rfc9052_cose_profile.py"
cose_spec = importlib.util.spec_from_file_location("rfc9052_cose_profile", ROADMAP_COSE_PATH)
if cose_spec is None or cose_spec.loader is None:
    raise ImportError(f"Cannot load {ROADMAP_COSE_PATH}")
cose_mod = importlib.util.module_from_spec(cose_spec)
sys.modules["rfc9052_cose_profile"] = cose_mod
cose_spec.loader.exec_module(cose_mod)

RFC8949CBOR = cose_mod.RFC8949CBOR
CBORTag = cose_mod.CBORTag
RFC9052CoseVerifier = cose_mod.RFC9052CoseVerifier
RFC9052CoseSigner = cose_mod.RFC9052CoseSigner

COSE_HEADER_ALG = cose_mod.COSE_HEADER_ALG
COSE_HEADER_CRIT = cose_mod.COSE_HEADER_CRIT
COSE_HEADER_CONTENT_TYPE = cose_mod.COSE_HEADER_CONTENT_TYPE
COSE_HEADER_KID = cose_mod.COSE_HEADER_KID
COSE_HEADER_RECEIPTS = cose_mod.COSE_HEADER_RECEIPTS
COSE_HEADER_VDS = cose_mod.COSE_HEADER_VDS
COSE_HEADER_VDP = cose_mod.COSE_HEADER_VDP

VDS_RFC9162_SHA256 = cose_mod.VDS_RFC9162_SHA256
VDP_TREE_SIZE = cose_mod.VDP_TREE_SIZE
VDP_LEAF_INDEX = cose_mod.VDP_LEAF_INDEX
VDP_INCLUSION_PATH = cose_mod.VDP_INCLUSION_PATH

COSE_ALG_EDDSA = cose_mod.COSE_ALG_EDDSA
COSE_TAG_SIGN1 = cose_mod.COSE_TAG_SIGN1
COSE_HEADER_AEIB_SIGNED_VDP_POSITION = cose_mod.COSE_HEADER_AEIB_SIGNED_VDP_POSITION
admit_ed25519_public_key = cose_mod.admit_ed25519_public_key

append_receipt_to_signed_statement = cose_mod.append_receipt_to_signed_statement

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from src.jcs_canonicalizer import encode_jcs
from src.strict_json_ingress import StrictJSONError, loads_strict


LEAF_DOMAIN_PREFIX = b"\x00"
NODE_DOMAIN_PREFIX = b"\x01"


class SCITTMerkleTree:
    """
    Pure Python SHA-256 binary Merkle tree implementing RFC 9162 / RFC 9942
    domain separation under the stated model:
      - Leaf hash: SHA-256(0x00 || statement_cbor)
      - Internal node hash: SHA-256(0x01 || left_hash || right_hash)
    """

    def __init__(self) -> None:
        self._leaf_hashes: List[bytes] = []

    @staticmethod
    def hash_leaf(statement_cbor: bytes) -> bytes:
        if not isinstance(statement_cbor, (bytes, bytearray)):
            raise TypeError("statement_cbor must be bytes")
        return hashlib.sha256(LEAF_DOMAIN_PREFIX + bytes(statement_cbor)).digest()

    @staticmethod
    def hash_children(left: bytes, right: bytes) -> bytes:
        return hashlib.sha256(NODE_DOMAIN_PREFIX + left + right).digest()

    @property
    def tree_size(self) -> int:
        return len(self._leaf_hashes)

    def add_leaf(self, statement_cbor: bytes) -> int:
        """Appends a signed statement CBOR byte string and returns its 0-based leaf_index."""
        leaf_hash = self.hash_leaf(statement_cbor)
        idx = len(self._leaf_hashes)
        self._leaf_hashes.append(leaf_hash)
        return idx

    @classmethod
    def _mth(cls, leaves: List[bytes]) -> bytes:
        n = len(leaves)
        if n == 0:
            return hashlib.sha256(b"").digest()
        if n == 1:
            return leaves[0]
        k = 1 << ((n - 1).bit_length() - 1)
        left = cls._mth(leaves[:k])
        right = cls._mth(leaves[k:])
        return cls.hash_children(left, right)

    def root_hash(self) -> bytes:
        """Computes the RFC 9162 Merkle Tree Hash (MTH) over all current leaves."""
        return self._mth(self._leaf_hashes)

    @classmethod
    def _path(cls, m: int, leaves: List[bytes]) -> List[bytes]:
        n = len(leaves)
        if n == 1 and m == 0:
            return []
        k = 1 << ((n - 1).bit_length() - 1)
        if m < k:
            return cls._path(m, leaves[:k]) + [cls._mth(leaves[k:])]
        return cls._path(m - k, leaves[k:]) + [cls._mth(leaves[:k])]

    def inclusion_proof(self, leaf_index: int) -> Dict[str, Any]:
        """
        Generates an RFC 9942 / RFC 9162 inclusion proof for leaf_index across the current tree.
        """
        n = len(self._leaf_hashes)
        if leaf_index < 0 or leaf_index >= n:
            raise ValueError(f"leaf_index {leaf_index} out of bounds for tree_size {n}")
        audit_hashes = self._path(leaf_index, self._leaf_hashes)
        return {
            "leaf_index": leaf_index,
            "tree_size": n,
            "audit_path": [h.hex() for h in audit_hashes],
            "root_hash_hex": self.root_hash().hex(),
        }

    @classmethod
    def verify_inclusion_proof(
        cls,
        statement_cbor: bytes,
        proof: Dict[str, Any],
        expected_root_hex: str,
    ) -> bool:
        """
        Offline verification of an RFC 9162 / RFC 9942 SHA-256 Merkle inclusion proof.
        Evaluated fail-closed under the stated model.

        Scope: a True result shows statement_cbor is a leaf under expected_root_hex.
        It does NOT authenticate proof["leaf_index"] / proof["tree_size"]: a root
        hash does not commit to the tree size, so the same audit path can also
        verify under other (leaf_index, tree_size) pairs with the same split
        directions (e.g. (1, 2) and (2, 3)). Callers must take the position from
        signed material (binary receipts: protected header
        COSE_HEADER_AEIB_SIGNED_VDP_POSITION; JSON bundles: signed JCS claims).
        """
        if not isinstance(proof, dict) or not isinstance(expected_root_hex, str):
            return False
        leaf_index = proof.get("leaf_index")
        tree_size = proof.get("tree_size")
        audit_path = proof.get("audit_path")
        proof_root_hex = proof.get("root_hash_hex")

        if (
            not isinstance(leaf_index, int)
            or isinstance(leaf_index, bool)
            or not isinstance(tree_size, int)
            or isinstance(tree_size, bool)
            or not isinstance(audit_path, list)
        ):
            return False

        if leaf_index < 0 or tree_size <= 0 or leaf_index >= tree_size:
            return False

        try:
            expected_root = bytes.fromhex(expected_root_hex)
            if len(expected_root) != 32:
                return False
            if proof_root_hex is not None:
                if bytes.fromhex(proof_root_hex) != expected_root:
                    return False
        except Exception:
            return False

        # Reconstruct top-down split direction steps per RFC 9162 Section 2.1.3
        steps_is_right_sibling: List[bool] = []
        m = leaf_index
        n = tree_size
        while n > 1:
            k = 1 << ((n - 1).bit_length() - 1)
            if m < k:
                steps_is_right_sibling.append(True)
                n = k
            else:
                steps_is_right_sibling.append(False)
                m = m - k
                n = n - k

        if len(audit_path) != len(steps_is_right_sibling):
            return False

        current_hash = cls.hash_leaf(statement_cbor)
        for sibling_hex, is_right_sibling in zip(
            audit_path, reversed(steps_is_right_sibling)
        ):
            if not isinstance(sibling_hex, str):
                return False
            try:
                sibling_bytes = bytes.fromhex(sibling_hex)
            except ValueError:
                return False
            if len(sibling_bytes) != 32:
                return False
            if is_right_sibling:
                current_hash = cls.hash_children(current_hash, sibling_bytes)
            else:
                current_hash = cls.hash_children(sibling_bytes, current_hash)

        return current_hash == expected_root


class SCITTTransparencyService:
    """
    Prototype IETF SCITT (RFC 9943) Transparency Service issuing RFC 9942 COSE Receipts
    over an append-only SHA-256 Merkle tree.
    """

    def __init__(self, service_id: str, ts_privkey: ed25519.Ed25519PrivateKey) -> None:
        if not service_id:
            raise ValueError("service_id must be a non-empty string")
        self.service_id = service_id
        self.ts_privkey = ts_privkey
        self.ts_kid = f"scitt-ts:{service_id}"
        self.tree = SCITTMerkleTree()
        self._signer = RFC9052CoseSigner(private_key=ts_privkey, key_id=self.ts_kid)

    def issue_binary_cose_receipt(
        self,
        statement_cbor: bytes,
        issuer_pubkey: Optional[ed25519.Ed25519PublicKey] = None,
        expected_aad: bytes = b"",
    ) -> bytes:
        """
        Appends statement_cbor to SCITTMerkleTree and issues a binary CBOR RFC 9942 COSE_Sign1
        (Tag 18) Receipt where:
          - Protected header has {1: -8 (EdDSA), 4: ts_kid, 395: 1 (VDS_RFC9162_SHA256),
            -65537: {-1: tree_size, -2: leaf_index}} (signed Merkle position)
          - Unprotected header has {396: {-1: tree_size, -2: leaf_index, -3: [bstr sibling_hashes]}}
          - Payload is the 32-byte Merkle root hash signed by ts_privkey.
        """
        if not isinstance(statement_cbor, (bytes, bytearray)) or len(statement_cbor) == 0:
            raise ValueError("statement_cbor must be a non-empty CBOR byte string")

        if issuer_pubkey is not None:
            stmt_res = RFC9052CoseVerifier.verify(
                bytes(statement_cbor),
                issuer_pubkey,
                expected_external_aad=expected_aad,
            )
            if not stmt_res.valid:
                raise ValueError(
                    f"SCITT Registration Policy rejected Signed Statement: {stmt_res.error}"
                )

        leaf_index = self.tree.add_leaf(bytes(statement_cbor))
        proof = self.tree.inclusion_proof(leaf_index)
        merkle_root_bytes = bytes.fromhex(proof["root_hash_hex"])

        vdp_map: Dict[int, Any] = {
            VDP_TREE_SIZE: proof["tree_size"],
            VDP_LEAF_INDEX: proof["leaf_index"],
            VDP_INCLUSION_PATH: [bytes.fromhex(h) for h in proof["audit_path"]],
        }
        protected_extra: Dict[int, Any] = {
            COSE_HEADER_KID: self.ts_kid.encode("utf-8"),
            COSE_HEADER_VDS: VDS_RFC9162_SHA256,
            # Bind the Merkle position under the TS signature (see
            # COSE_HEADER_AEIB_SIGNED_VDP_POSITION in rfc9052_cose_profile.py).
            COSE_HEADER_AEIB_SIGNED_VDP_POSITION: {
                VDP_TREE_SIZE: proof["tree_size"],
                VDP_LEAF_INDEX: proof["leaf_index"],
            },
        }
        unprotected_extra: Dict[int, Any] = {
            COSE_HEADER_VDP: vdp_map,
        }
        return self._signer.sign(
            merkle_root_bytes,
            external_aad=expected_aad,
            protected_extra=protected_extra,
            unprotected_extra=unprotected_extra,
        )

    def register_signed_statement(
        self,
        signed_statement_cbor: bytes,
        issuer_pubkey: ed25519.Ed25519PublicKey,
        expected_aad: bytes = b"",
    ) -> Dict[str, Any]:
        """
        Verifies an incoming COSE_Sign1 Signed Statement against the Registration Policy,
        appends it to the SCITT Merkle tree, and issues a signed COSE_Sign1 Receipt.
        Fails closed with ValueError if the incoming statement is invalid.
        """
        stmt_res = RFC9052CoseVerifier.verify(
            signed_statement_cbor,
            issuer_pubkey,
            expected_external_aad=expected_aad,
        )
        if not stmt_res.valid:
            raise ValueError(
                f"SCITT Registration Policy rejected Signed Statement: {stmt_res.error}"
            )

        leaf_index = self.tree.add_leaf(signed_statement_cbor)
        proof = self.tree.inclusion_proof(leaf_index)
        statement_sha256 = hashlib.sha256(signed_statement_cbor).hexdigest()

        receipt_claims = {
            "service_id": self.service_id,
            "leaf_index": proof["leaf_index"],
            "tree_size": proof["tree_size"],
            "audit_path": proof["audit_path"],
            "merkle_root_hex": proof["root_hash_hex"],
            "statement_sha256": statement_sha256,
        }
        receipt_payload_bytes = encode_jcs(receipt_claims)
        cose_receipt_bytes = self._signer.sign(
            receipt_payload_bytes,
            external_aad=expected_aad,
        )

        return {
            "signed_statement_b64": base64.b64encode(signed_statement_cbor).decode("ascii"),
            "cose_receipt_b64": base64.b64encode(cose_receipt_bytes).decode("ascii"),
            "inclusion_proof": proof,
            "merkle_root_hex": proof["root_hash_hex"],
            "issuer_kid": stmt_res.kid,
            "ts_kid": self.ts_kid,
        }


def verify_binary_transparent_statement(
    transparent_statement_cbor: bytes,
    issuer_pubkey: ed25519.Ed25519PublicKey,
    ts_pubkey: ed25519.Ed25519PublicKey,
    expected_aad: bytes = b"",
) -> Dict[str, Any]:
    """
    Offline verification of a binary CBOR RFC 9942 / RFC 9943 Transparent Statement:
      1. Verifies the outer Issuer COSE_Sign1 signature over Sig_structure.
      2. Extracts embedded binary CBOR receipt(s) from Unprotected Header 394 (COSE_HEADER_RECEIPTS).
      3. Verifies each receipt's Protected Header 395 == 1 (VDS_RFC9162_SHA256),
         extracts the inclusion proof from Unprotected Header 396 (COSE_HEADER_VDP),
         recomputes the RFC 9162 Merkle root from the outer statement bytes, and
         verifies the Transparency Service's Ed25519 signature over the Merkle root.
    """
    # 1. Verify outer Issuer COSE_Sign1 signature
    stmt_res = RFC9052CoseVerifier.verify(
        transparent_statement_cbor,
        issuer_pubkey,
        expected_external_aad=expected_aad,
    )
    if not stmt_res.valid:
        return {
            "valid": False,
            "error": f"Issuer Signed Statement verification failed: {stmt_res.error}",
        }

    # 2. Extract embedded binary CBOR receipt(s) from Unprotected Header 394
    if COSE_HEADER_RECEIPTS in stmt_res.protected_headers:
        return {
            "valid": False,
            "error": "COSE_HEADER_RECEIPTS (394) must be in unprotected headers, not protected headers",
        }

    receipts_raw = stmt_res.unprotected_headers.get(COSE_HEADER_RECEIPTS)
    if not isinstance(receipts_raw, list) or len(receipts_raw) == 0:
        return {
            "valid": False,
            "error": "Missing or empty COSE_HEADER_RECEIPTS (394) in unprotected headers",
        }

    # Reconstruct the canonical outer Signed Statement CBOR bytes (prior to header 394 attachment)
    cbor_item = RFC8949CBOR.decode(transparent_statement_cbor)
    protected_bytes, unprotected_headers, payload_bytes, signature_bytes = cbor_item.value
    base_unprotected = {
        k: v for k, v in unprotected_headers.items() if k != COSE_HEADER_RECEIPTS
    }
    base_statement_cbor = RFC8949CBOR.encode(
        CBORTag(
            tag=COSE_TAG_SIGN1,
            value=[
                bytes(protected_bytes),
                base_unprotected,
                bytes(payload_bytes),
                bytes(signature_bytes),
            ],
        )
    )

    last_proof: Dict[str, Any] = {}
    last_root_hex: str = ""
    last_ts_kid: Optional[str] = None

    for idx, rcpt_entry in enumerate(receipts_raw):
        if not isinstance(rcpt_entry, (bytes, bytearray)) or len(rcpt_entry) == 0:
            return {
                "valid": False,
                "error": f"Receipt [{idx}] in COSE_HEADER_RECEIPTS (394) is not a non-empty CBOR bstr",
            }
        rcpt_bytes = bytes(rcpt_entry)

        # Verify TS COSE_Sign1 signature over the receipt
        rcpt_res = RFC9052CoseVerifier.verify(
            rcpt_bytes,
            ts_pubkey,
            expected_external_aad=expected_aad,
        )
        # No empty-AAD fallback: a receipt must be signed over the caller's
        # expected_aad exactly, otherwise it is not bound to that context.
        if not rcpt_res.valid:
            return {
                "valid": False,
                "error": f"Transparency Service COSE Receipt [{idx}] verification failed: {rcpt_res.error}",
            }

        # 3a. Verify Protected Header 395 == 1 (VDS_RFC9162_SHA256)
        if COSE_HEADER_VDS in rcpt_res.unprotected_headers:
            return {
                "valid": False,
                "error": "COSE_HEADER_VDS (395) must reside in receipt protected headers",
            }

        vds_alg = rcpt_res.protected_headers.get(COSE_HEADER_VDS)
        if isinstance(vds_alg, bool) or vds_alg != VDS_RFC9162_SHA256:
            return {
                "valid": False,
                "error": (
                    f"Unsupported or invalid COSE_HEADER_VDS (395) in receipt [{idx}]: "
                    f"{vds_alg!r} (expected {VDS_RFC9162_SHA256})"
                ),
            }

        # 3b. Extract inclusion proof from Unprotected Header 396 (COSE_HEADER_VDP)
        vdp_map = rcpt_res.unprotected_headers.get(COSE_HEADER_VDP)
        if not isinstance(vdp_map, dict):
            return {
                "valid": False,
                "error": f"Missing or invalid COSE_HEADER_VDP (396) proof map in receipt [{idx}]",
            }

        tree_size = vdp_map.get(VDP_TREE_SIZE)
        leaf_index = vdp_map.get(VDP_LEAF_INDEX)
        inclusion_path = vdp_map.get(VDP_INCLUSION_PATH)

        if (
            not isinstance(tree_size, int)
            or isinstance(tree_size, bool)
            or not isinstance(leaf_index, int)
            or isinstance(leaf_index, bool)
            or not isinstance(inclusion_path, list)
        ):
            return {
                "valid": False,
                "error": f"Malformed VDP (396) fields in receipt [{idx}]",
            }

        # 3b'. The reported position must come from signed data: the protected
        # header carries {tree_size, leaf_index}; the unprotected VDP copy must match.
        signed_position = rcpt_res.protected_headers.get(COSE_HEADER_AEIB_SIGNED_VDP_POSITION)
        if not isinstance(signed_position, dict) or set(signed_position) != {
            VDP_TREE_SIZE,
            VDP_LEAF_INDEX,
        }:
            return {
                "valid": False,
                "error": (
                    f"ERR_VDP_POSITION_NOT_SIGNED: receipt [{idx}] lacks a protected "
                    f"{COSE_HEADER_AEIB_SIGNED_VDP_POSITION} {{tree_size, leaf_index}} map"
                ),
            }
        signed_tree_size = signed_position[VDP_TREE_SIZE]
        signed_leaf_index = signed_position[VDP_LEAF_INDEX]
        if (
            type(signed_tree_size) is not int
            or type(signed_leaf_index) is not int
            or signed_tree_size != tree_size
            or signed_leaf_index != leaf_index
        ):
            return {
                "valid": False,
                "error": (
                    f"ERR_VDP_POSITION_MISMATCH: receipt [{idx}] unprotected VDP "
                    f"(tree_size={tree_size!r}, leaf_index={leaf_index!r}) differs from the "
                    f"signed position (tree_size={signed_tree_size!r}, leaf_index={signed_leaf_index!r})"
                ),
            }

        audit_path_hex: List[str] = []
        for sibling in inclusion_path:
            if not isinstance(sibling, (bytes, bytearray)) or len(sibling) != 32:
                return {
                    "valid": False,
                    "error": f"Invalid sibling hash in VDP (396) inclusion_path (-3) in receipt [{idx}]",
                }
            audit_path_hex.append(bytes(sibling).hex())

        # 3c. Verify receipt payload is the 32-byte Merkle root and recompute RFC 9162 root
        if len(rcpt_res.payload) != 32:
            return {
                "valid": False,
                "error": (
                    f"Invalid Merkle root payload length in receipt [{idx}]: "
                    f"{len(rcpt_res.payload)} bytes (expected 32)"
                ),
            }
        merkle_root_hex = rcpt_res.payload.hex()

        proof_dict = {
            "leaf_index": leaf_index,
            "tree_size": tree_size,
            "audit_path": audit_path_hex,
            "root_hash_hex": merkle_root_hex,
        }
        if not SCITTMerkleTree.verify_inclusion_proof(
            base_statement_cbor,
            proof_dict,
            merkle_root_hex,
        ):
            return {
                "valid": False,
                "error": f"RFC 9942 / RFC 9162 VDP Merkle inclusion proof verification failed for receipt [{idx}]",
            }

        last_proof = proof_dict
        last_root_hex = merkle_root_hex
        last_ts_kid = rcpt_res.kid

    service_id = (
        last_ts_kid.split("scitt-ts:", 1)[1]
        if (last_ts_kid and last_ts_kid.startswith("scitt-ts:"))
        else last_ts_kid
    )
    return {
        "valid": True,
        "vds": VDS_RFC9162_SHA256,
        "service_id": service_id,
        "leaf_index": last_proof["leaf_index"],
        "tree_size": last_proof["tree_size"],
        "audit_path": last_proof["audit_path"],
        "merkle_root_hex": last_root_hex,
        "statement_sha256": hashlib.sha256(base_statement_cbor).hexdigest(),
        "issuer_kid": stmt_res.kid,
        "ts_kid": last_ts_kid,
        "receipt_count": len(receipts_raw),
        "statement_payload": stmt_res.payload,
        "error": None,
    }


def verify_transparent_statement(
    bundle: Dict[str, Any],
    issuer_pubkey: ed25519.Ed25519PublicKey,
    ts_pubkey: ed25519.Ed25519PublicKey,
    expected_aad: bytes = b"",
) -> Dict[str, Any]:
    """
    Offline verification of an IETF SCITT Transparent Statement bundle:
      1. Issuer COSE_Sign1 signature over the Signed Statement;
      2. Transparency Service COSE_Sign1 signature over the COSE Receipt;
      3. Statement SHA-256 binding between the receipt and the statement;
      4. RFC 9162 / RFC 9942 SHA-256 Merkle inclusion path up to the signed merkle_root_hex.
    """
    try:
        signed_statement_cbor = base64.b64decode(bundle["signed_statement_b64"])
        cose_receipt_bytes = base64.b64decode(bundle["cose_receipt_b64"])
    except Exception as exc:
        return {"valid": False, "error": f"Malformed base64 in bundle: {exc}"}

    # 1. Verify Issuer COSE_Sign1 signature over the Signed Statement
    stmt_res = RFC9052CoseVerifier.verify(
        signed_statement_cbor,
        issuer_pubkey,
        expected_external_aad=expected_aad,
    )
    if not stmt_res.valid:
        return {
            "valid": False,
            "error": f"Issuer Signed Statement verification failed: {stmt_res.error}",
        }

    # 2. Verify Transparency Service COSE_Sign1 signature over the COSE Receipt
    rcpt_res = RFC9052CoseVerifier.verify(
        cose_receipt_bytes,
        ts_pubkey,
        expected_external_aad=expected_aad,
    )
    if not rcpt_res.valid:
        return {
            "valid": False,
            "error": f"Transparency Service COSE Receipt verification failed: {rcpt_res.error}",
        }

    try:
        # I-JSON ingress: duplicate keys, NaN/Infinity and lone surrogates are
        # rejected with a coded StrictJSONError before canonical comparison.
        receipt_claims = loads_strict(rcpt_res.payload)
    except StrictJSONError as exc:
        return {"valid": False, "error": f"Malformed COSE Receipt JSON payload: {exc}"}
    except RecursionError:
        return {
            "valid": False,
            "error": "Malformed COSE Receipt JSON payload: ERR_JSON_NESTING_TOO_DEEP",
        }
    if not isinstance(receipt_claims, dict):
        return {
            "valid": False,
            "error": "Malformed COSE Receipt JSON payload: ERR_RECEIPT_NOT_OBJECT",
        }
    try:
        canonical_ok = encode_jcs(receipt_claims) == rcpt_res.payload
    except (TypeError, ValueError, RecursionError) as exc:
        return {"valid": False, "error": f"Malformed COSE Receipt JSON payload: {exc}"}
    if not canonical_ok:
        return {
            "valid": False,
            "error": "COSE Receipt payload is not RFC 8785 JCS canonical",
        }

    # 3. Verify Statement SHA-256 binding
    actual_stmt_sha256 = hashlib.sha256(signed_statement_cbor).hexdigest()
    if receipt_claims.get("statement_sha256") != actual_stmt_sha256:
        return {
            "valid": False,
            "error": "Statement SHA-256 mismatch between Signed Statement and COSE Receipt",
        }

    # 4. Cross-check bundle metadata against signed receipt claims and verify Merkle inclusion proof
    signed_root_hex = receipt_claims.get("merkle_root_hex")
    if not isinstance(signed_root_hex, str):
        return {"valid": False, "error": "Missing merkle_root_hex in COSE Receipt"}

    bundle_root_hex = bundle.get("merkle_root_hex")
    if bundle_root_hex is not None and bundle_root_hex != signed_root_hex:
        return {
            "valid": False,
            "error": "Bundle merkle_root_hex does not match signed COSE Receipt merkle_root_hex",
        }

    signed_proof = {
        "leaf_index": receipt_claims.get("leaf_index"),
        "tree_size": receipt_claims.get("tree_size"),
        "audit_path": receipt_claims.get("audit_path"),
        "root_hash_hex": signed_root_hex,
    }
    bundle_proof = bundle.get("inclusion_proof")
    if bundle_proof is not None and bundle_proof != signed_proof:
        return {
            "valid": False,
            "error": "Bundle inclusion_proof does not match signed COSE Receipt claims",
        }

    if not SCITTMerkleTree.verify_inclusion_proof(
        signed_statement_cbor,
        signed_proof,
        signed_root_hex,
    ):
        return {
            "valid": False,
            "error": "RFC 9942 / RFC 9162 Merkle inclusion proof verification failed",
        }

    return {
        "valid": True,
        "service_id": receipt_claims.get("service_id"),
        "leaf_index": signed_proof["leaf_index"],
        "tree_size": signed_proof["tree_size"],
        "merkle_root_hex": signed_root_hex,
        "statement_sha256": actual_stmt_sha256,
        "issuer_kid": stmt_res.kid,
        "ts_kid": rcpt_res.kid,
        "statement_payload": stmt_res.payload,
        "error": None,
    }


def _parse_public_key(pubkey_str: str) -> ed25519.Ed25519PublicKey:
    path = Path(pubkey_str)
    if path.exists():
        data = path.read_bytes()
        try:
            return serialization.load_pem_public_key(data)
        except Exception:
            pass
        if len(data) == 32:
            return ed25519.Ed25519PublicKey.from_public_bytes(data)
        text = data.decode("utf-8", errors="ignore").strip()
        try:
            raw_bytes = bytes.fromhex(text)
            if len(raw_bytes) == 32:
                return ed25519.Ed25519PublicKey.from_public_bytes(raw_bytes)
        except ValueError:
            pass
        try:
            raw_bytes = base64.b64decode(text)
            if len(raw_bytes) == 32:
                return ed25519.Ed25519PublicKey.from_public_bytes(raw_bytes)
        except Exception:
            pass
    try:
        raw_bytes = bytes.fromhex(pubkey_str)
        if len(raw_bytes) == 32:
            return ed25519.Ed25519PublicKey.from_public_bytes(raw_bytes)
    except ValueError:
        pass
    try:
        raw_bytes = base64.b64decode(pubkey_str)
        if len(raw_bytes) == 32:
            return ed25519.Ed25519PublicKey.from_public_bytes(raw_bytes)
    except Exception:
        pass
    raise ValueError(f"Unable to parse public key from: {pubkey_str}")


def load_public_key(pubkey_str: str) -> ed25519.Ed25519PublicKey:
    """
    Loads an Ed25519 public key (PEM file, raw 32-byte file, hex or base64) and
    admits it: small-order points, non-canonical encodings and non-Ed25519 keys
    raise ValueError with a stable ERR_ED25519_* code.
    """
    key = _parse_public_key(pubkey_str)
    rejection = admit_ed25519_public_key(key)
    if rejection is not None:
        raise ValueError(f"{rejection}: public key rejected")
    return key


def load_private_key(privkey_str: str) -> ed25519.Ed25519PrivateKey:
    path = Path(privkey_str)
    if path.exists():
        data = path.read_bytes()
        try:
            loaded = serialization.load_pem_private_key(data, password=None)
            if isinstance(loaded, ed25519.Ed25519PrivateKey):
                return loaded
        except Exception:
            pass
        if len(data) == 32:
            return ed25519.Ed25519PrivateKey.from_private_bytes(data)
        text = data.decode("utf-8", errors="ignore").strip()
        try:
            raw_bytes = bytes.fromhex(text)
            if len(raw_bytes) == 32:
                return ed25519.Ed25519PrivateKey.from_private_bytes(raw_bytes)
        except ValueError:
            pass
        try:
            raw_bytes = base64.b64decode(text)
            if len(raw_bytes) == 32:
                return ed25519.Ed25519PrivateKey.from_private_bytes(raw_bytes)
        except Exception:
            pass
    try:
        raw_bytes = bytes.fromhex(privkey_str)
        if len(raw_bytes) == 32:
            return ed25519.Ed25519PrivateKey.from_private_bytes(raw_bytes)
    except ValueError:
        pass
    try:
        raw_bytes = base64.b64decode(privkey_str)
        if len(raw_bytes) == 32:
            return ed25519.Ed25519PrivateKey.from_private_bytes(raw_bytes)
    except Exception:
        pass
    raise ValueError(f"Unable to parse Ed25519 private key from: {privkey_str}")


def _decode_aad(aad_str: str) -> bytes:
    if not aad_str:
        return b""
    try:
        return bytes.fromhex(aad_str)
    except ValueError:
        return aad_str.encode("utf-8")


def _format_header_value(key: Any, val: Any) -> Any:
    if key == COSE_HEADER_KID and isinstance(val, (bytes, bytearray)):
        return bytes(val).decode("utf-8", errors="replace")
    if key == COSE_HEADER_VDP and isinstance(val, dict):
        return {
            "-1 (tree_size)": val.get(VDP_TREE_SIZE),
            "-2 (leaf_index)": val.get(VDP_LEAF_INDEX),
            "-3 (inclusion_path)": [
                bytes(h).hex() if isinstance(h, (bytes, bytearray)) else h
                for h in val.get(VDP_INCLUSION_PATH, [])
            ],
        }
    if isinstance(val, (bytes, bytearray)):
        return bytes(val).hex()
    return val


def inspect_cose_envelope(cbor_bytes: bytes) -> Dict[str, Any]:
    """
    Decodes a binary .cose or .scitt.cose COSE_Sign1 (Tag 18) file into a structured
    human-readable dictionary exposing headers 1, 3, 4, 394, 395, 396, payload, and signature hex.
    """
    item = RFC8949CBOR.decode(cbor_bytes)
    if (
        not isinstance(item, CBORTag)
        or item.tag != COSE_TAG_SIGN1
        or not isinstance(item.value, (list, tuple))
        or len(item.value) != 4
    ):
        raise ValueError("Input is not a valid CBOR Tag 18 COSE_Sign1 envelope")

    protected_bytes, unprotected_headers, payload_bytes, signature_bytes = item.value
    protected_headers = (
        RFC8949CBOR.decode(bytes(protected_bytes)) if len(protected_bytes) > 0 else {}
    )

    formatted_protected = {
        k: _format_header_value(k, v) for k, v in protected_headers.items()
    }
    formatted_unprotected: Dict[Any, Any] = {}
    decoded_receipts: List[Dict[str, Any]] = []

    for k, v in unprotected_headers.items():
        if k == COSE_HEADER_RECEIPTS and isinstance(v, list):
            for rcpt_b in v:
                if isinstance(rcpt_b, (bytes, bytearray)):
                    decoded_receipts.append(inspect_cose_envelope(bytes(rcpt_b)))
            formatted_unprotected[k] = f"[{len(v)} embedded COSE receipt(s)]"
        else:
            formatted_unprotected[k] = _format_header_value(k, v)

    payload_b = bytes(payload_bytes)
    payload_text: Optional[str] = None
    try:
        payload_text = payload_b.decode("utf-8")
    except UnicodeDecodeError:
        payload_text = None

    return {
        "cbor_tag": item.tag,
        "protected_headers": formatted_protected,
        "unprotected_headers": formatted_unprotected,
        "payload_len": len(payload_b),
        "payload_hex": payload_b.hex(),
        "payload_utf8": payload_text,
        "signature_hex": bytes(signature_bytes).hex(),
        "embedded_receipts_394": decoded_receipts,
    }


def _print_inspection(info: Dict[str, Any], indent: str = "") -> None:
    print(f"{indent}COSE_Sign1 Envelope (CBOR Tag {info['cbor_tag']}):")
    prot = info["protected_headers"]
    unprot = info["unprotected_headers"]
    print(f"{indent}  Protected Headers   : {prot}")
    for hdr_id, hdr_label in [
        (COSE_HEADER_ALG, "alg"),
        (COSE_HEADER_CONTENT_TYPE, "content_type"),
        (COSE_HEADER_KID, "kid"),
        (COSE_HEADER_VDS, "vds"),
    ]:
        if hdr_id in prot:
            print(f"{indent}    - Header {hdr_id} ({hdr_label}) : {prot[hdr_id]}")

    print(f"{indent}  Unprotected Headers : {unprot}")
    for hdr_id, hdr_label in [
        (COSE_HEADER_ALG, "alg"),
        (COSE_HEADER_CONTENT_TYPE, "content_type"),
        (COSE_HEADER_KID, "kid"),
        (COSE_HEADER_RECEIPTS, "receipts"),
        (COSE_HEADER_VDP, "vdp"),
    ]:
        if hdr_id in unprot:
            print(f"{indent}    - Header {hdr_id} ({hdr_label}) : {unprot[hdr_id]}")

    print(f"{indent}  Payload Bytes       : {info['payload_len']}")
    print(f"{indent}  Payload Hex         : {info['payload_hex']}")
    if info["payload_utf8"] is not None:
        print(f"{indent}  Payload UTF-8       : {info['payload_utf8']}")
    print(f"{indent}  Signature Hex       : {info['signature_hex']}")

    for idx, rcpt_info in enumerate(info.get("embedded_receipts_394", [])):
        print(f"{indent}  Embedded Receipt [{idx}] (Header 394):")
        _print_inspection(rcpt_info, indent=indent + "    ")


def run_self_test() -> int:
    """
    Runs a deterministic 4-leaf SCITT Transparency Service and offline verification
    demonstration under the stated model (evaluating both JSON bundle and binary RFC 9942 / 9943).
    """
    issuer_priv = ed25519.Ed25519PrivateKey.generate()
    issuer_pub = issuer_priv.public_key()
    ts_priv = ed25519.Ed25519PrivateKey.generate()
    ts_pub = ts_priv.public_key()

    issuer_signer = RFC9052CoseSigner(private_key=issuer_priv, key_id="issuer:aeib-gatekeeper-01")
    ts_service = SCITTTransparencyService(
        service_id="scitt.sovereignnexus.internal",
        ts_privkey=ts_priv,
    )
    bin_ts_service = SCITTTransparencyService(
        service_id="scitt.sovereignnexus.internal",
        ts_privkey=ts_priv,
    )
    aad = b"aeib-scitt-v1.1-domain"

    statements: List[bytes] = []
    bundles: List[Dict[str, Any]] = []
    transparent_statements: List[bytes] = []
    for idx in range(4):
        claim = {
            "caid": hashlib.sha256(f"episode-{idx}".encode("utf-8")).hexdigest(),
            "disposition": "ALLOW",
            "sequence": idx,
        }
        stmt_cbor, _ = issuer_signer.sign_receipt(claim, external_aad=aad)
        statements.append(stmt_cbor)
        bundle = ts_service.register_signed_statement(
            stmt_cbor,
            issuer_pubkey=issuer_pub,
            expected_aad=aad,
        )
        bundles.append(bundle)

        bin_rcpt = bin_ts_service.issue_binary_cose_receipt(
            stmt_cbor,
            issuer_pubkey=issuer_pub,
            expected_aad=aad,
        )
        transparent_cbor = append_receipt_to_signed_statement(stmt_cbor, bin_rcpt)
        transparent_statements.append(transparent_cbor)

    # Verify each bundle and binary transparent statement
    final_root_hex = ts_service.tree.root_hash().hex()
    for idx, bundle in enumerate(bundles):
        res = verify_transparent_statement(
            bundle,
            issuer_pubkey=issuer_pub,
            ts_pubkey=ts_pub,
            expected_aad=aad,
        )
        if not res["valid"]:
            print(f"[-] SCITT self-test failed at leaf {idx}: {res['error']}", file=sys.stderr)
            return 1

        bin_res = verify_binary_transparent_statement(
            transparent_statements[idx],
            issuer_pubkey=issuer_pub,
            ts_pubkey=ts_pub,
            expected_aad=aad,
        )
        if not bin_res["valid"]:
            print(
                f"[-] Binary SCITT self-test failed at leaf {idx}: {bin_res['error']}",
                file=sys.stderr,
            )
            return 1

        full_proof = ts_service.tree.inclusion_proof(idx)
        if not SCITTMerkleTree.verify_inclusion_proof(
            statements[idx], full_proof, final_root_hex
        ):
            print(f"[-] SCITT 4-leaf inclusion proof failed at leaf {idx}", file=sys.stderr)
            return 1

    print("[✓] IETF SCITT (RFC 9942 / RFC 9943) & RFC 9052 COSE Self-Test PASSED")
    print(f"    - Service ID        : {ts_service.service_id}")
    print(f"    - Tree Size         : {ts_service.tree.tree_size} leaves")
    print(f"    - Final Merkle Root : {final_root_hex}")
    return 0


def _cmd_sign(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[-] Input file not found: {args.input}", file=sys.stderr)
        return 1

    raw_bytes = input_path.read_bytes()
    try:
        parsed_json = json.loads(raw_bytes.decode("utf-8"))
        payload_bytes = encode_jcs(parsed_json)
    except Exception:
        payload_bytes = raw_bytes

    priv_key = load_private_key(args.key)
    aad_bytes = _decode_aad(args.aad)
    signer = RFC9052CoseSigner(private_key=priv_key, key_id=args.kid)
    cose_bytes = signer.sign(payload_bytes, external_aad=aad_bytes)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(cose_bytes)

    print("[✓] Signed Statement (.cose) Created")
    print(f"    - Output File       : {out_path}")
    print(f"    - Key ID (4)        : {args.kid}")
    print(f"    - Payload SHA-256   : {hashlib.sha256(payload_bytes).hexdigest()}")
    return 0


def _cmd_append_receipt(args: argparse.Namespace) -> int:
    env_path = Path(args.envelope)
    if not env_path.exists():
        print(f"[-] Envelope file not found: {args.envelope}", file=sys.stderr)
        return 1

    signed_statement_cbor = env_path.read_bytes()
    try:
        issuer_pubkey = load_public_key(args.issuer_pubkey)
    except ValueError as exc:
        print(f"[-] Issuer public key rejected: {exc}", file=sys.stderr)
        return 1
    ts_privkey = load_private_key(args.ts_key)
    aad_bytes = _decode_aad(args.aad)

    ts_service = SCITTTransparencyService(
        service_id=args.service_id,
        ts_privkey=ts_privkey,
    )
    try:
        receipt_cbor = ts_service.issue_binary_cose_receipt(
            signed_statement_cbor,
            issuer_pubkey=issuer_pubkey,
            expected_aad=aad_bytes,
        )
        transparent_cbor = append_receipt_to_signed_statement(
            signed_statement_cbor,
            receipt_cbor,
        )
    except Exception as exc:
        print(f"[-] Failed to append SCITT receipt: {exc}", file=sys.stderr)
        return 1

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(transparent_cbor)

    print("[✓] RFC 9942 / RFC 9943 Binary Transparent Statement (.scitt.cose) Created")
    print(f"    - Output File       : {out_path}")
    print(f"    - TS Key ID (4)     : {ts_service.ts_kid}")
    print(f"    - VDS (395)         : {VDS_RFC9162_SHA256} (RFC9162_SHA256)")
    print(f"    - Merkle Root Hex   : {ts_service.tree.root_hash().hex()}")
    return 0


def _cmd_verify_scitt(args: argparse.Namespace) -> int:
    stmt_file = args.transparent_statement or args.envelope
    if not stmt_file:
        print("[-] --transparent-statement is required", file=sys.stderr)
        return 1

    ts_path = Path(stmt_file)
    if not ts_path.exists():
        print(f"[-] Transparent Statement file not found: {stmt_file}", file=sys.stderr)
        return 1

    transparent_cbor = ts_path.read_bytes()
    try:
        issuer_pubkey = load_public_key(args.issuer_pubkey)
        ts_pubkey = load_public_key(args.ts_pubkey)
    except ValueError as exc:
        print(f"[-] Public key rejected: {exc}", file=sys.stderr)
        return 1
    aad_bytes = _decode_aad(args.aad)

    res = verify_binary_transparent_statement(
        transparent_cbor,
        issuer_pubkey=issuer_pubkey,
        ts_pubkey=ts_pubkey,
        expected_aad=aad_bytes,
    )
    if not res["valid"]:
        print(
            f"[-] RFC 9942 / RFC 9943 Transparent Statement Verification FAILED: {res['error']}",
            file=sys.stderr,
        )
        return 1

    print("[✓] RFC 9942 / RFC 9943 Binary Transparent Statement Verification SUCCESSFUL")
    print(f"    - Issuer Key ID (4) : {res['issuer_kid']}")
    print(f"    - TS Key ID (4)     : {res['ts_kid']}")
    print(f"    - VDS Header (395)  : {res['vds']} (RFC9162_SHA256)")
    print(f"    - VDP Leaf Index    : {res['leaf_index']} / Tree Size {res['tree_size']}")
    print(f"    - Merkle Root Hex   : {res['merkle_root_hex']}")
    print(f"    - Statement SHA-256 : {res['statement_sha256']}")
    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    target_file = (
        args.file
        or args.input
        or args.envelope
        or args.transparent_statement
    )
    if not target_file:
        print("[-] Specify a .cose or .scitt.cose file to inspect", file=sys.stderr)
        return 1

    path = Path(target_file)
    if not path.exists():
        print(f"[-] File not found: {target_file}", file=sys.stderr)
        return 1

    try:
        info = inspect_cose_envelope(path.read_bytes())
    except Exception as exc:
        print(f"[-] Failed to inspect CBOR/COSE file: {exc}", file=sys.stderr)
        return 1

    _print_inspection(info)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AEIB RFC 9052 COSE_Sign1 & IETF SCITT Receipt Verifier"
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run end-to-end 4-leaf IETF SCITT & RFC 9052 COSE self-test",
    )
    parser.add_argument(
        "--envelope",
        help="Path to COSE_Sign1 CBOR binary envelope (.cose)",
    )
    parser.add_argument(
        "--public-key",
        help="Path to Ed25519 public key PEM or raw bytes",
    )
    parser.add_argument(
        "--aad",
        default="",
        help="Optional external AAD (hex string or utf-8)",
    )

    subparsers = parser.add_subparsers(dest="subcommand")

    # Subcommand: sign
    p_sign = subparsers.add_parser(
        "sign",
        help="Sign a JSON/artifact file into a .cose COSE_Sign1 Signed Statement",
    )
    p_sign.add_argument("--input", required=True, help="Path to input JSON or artifact file")
    p_sign.add_argument("--key", required=True, help="Path or hex/base64 of Ed25519 private key")
    p_sign.add_argument("--kid", default="aeib-cli-signer", help="Key identifier (header 4)")
    p_sign.add_argument("--output", required=True, help="Path to output .cose file")
    p_sign.add_argument("--aad", default="", help="Optional external AAD (hex or utf-8)")

    # Subcommand: append-receipt
    p_append = subparsers.add_parser(
        "append-receipt",
        help="Register a .cose statement in SCITT Merkle log and embed RFC 9942 binary receipt in header 394",
    )
    p_append.add_argument("--envelope", required=True, help="Path to input .cose Signed Statement")
    p_append.add_argument("--issuer-pubkey", required=True, help="Path or hex/base64 of Issuer Ed25519 public key")
    p_append.add_argument("--ts-key", required=True, help="Path or hex/base64 of Transparency Service Ed25519 private key")
    p_append.add_argument("--output", required=True, help="Path to output .scitt.cose Transparent Statement")
    p_append.add_argument("--service-id", default="scitt.sovereignnexus.internal", help="SCITT service identifier")
    p_append.add_argument("--aad", default="", help="Optional external AAD (hex or utf-8)")

    # Subcommand: verify-scitt
    p_verify = subparsers.add_parser(
        "verify-scitt",
        help="Offline verify a .scitt.cose binary Transparent Statement (headers 394, 395, 396)",
    )
    p_verify.add_argument("--transparent-statement", help="Path to .scitt.cose binary Transparent Statement")
    p_verify.add_argument("--envelope", help="Alias for --transparent-statement")
    p_verify.add_argument("--issuer-pubkey", required=True, help="Path or hex/base64 of Issuer Ed25519 public key")
    p_verify.add_argument("--ts-pubkey", required=True, help="Path or hex/base64 of Transparency Service Ed25519 public key")
    p_verify.add_argument("--aad", default="", help="Optional external AAD (hex or utf-8)")

    # Subcommand: inspect
    p_inspect = subparsers.add_parser(
        "inspect",
        help="Decode and print human-readable structure of any .cose or .scitt.cose file",
    )
    p_inspect.add_argument("file", nargs="?", help="Path to .cose or .scitt.cose file")
    p_inspect.add_argument("--input", help="Path to .cose or .scitt.cose file")
    p_inspect.add_argument("--envelope", help="Path to .cose or .scitt.cose file")
    p_inspect.add_argument("--transparent-statement", help="Path to .cose or .scitt.cose file")

    args = parser.parse_args()

    if args.subcommand == "sign":
        sys.exit(_cmd_sign(args))
    if args.subcommand == "append-receipt":
        sys.exit(_cmd_append_receipt(args))
    if args.subcommand == "verify-scitt":
        sys.exit(_cmd_verify_scitt(args))
    if args.subcommand == "inspect":
        sys.exit(_cmd_inspect(args))

    if args.self_test:
        sys.exit(run_self_test())

    if not args.envelope or not args.public_key:
        parser.error("the following arguments are required: --envelope, --public-key (unless --self-test is set)")

    envelope_path = Path(args.envelope)
    if not envelope_path.exists():
        print(f"[-] Envelope file not found: {args.envelope}", file=sys.stderr)
        sys.exit(1)

    envelope_bytes = envelope_path.read_bytes()
    try:
        pubkey = load_public_key(args.public_key)
    except ValueError as exc:
        print(f"[-] Public key rejected: {exc}", file=sys.stderr)
        sys.exit(1)
    aad_bytes = _decode_aad(args.aad)

    verifier = RFC9052CoseVerifier()
    res = verifier.verify(envelope_bytes, pubkey, expected_external_aad=aad_bytes)

    if not res.valid:
        print(f"[-] COSE_Sign1 Verification FAILED: {res.error}", file=sys.stderr)
        sys.exit(1)

    print("[✓] RFC 9052 COSE_Sign1 Receipt Verification SUCCESSFUL")
    print(f"    - Algorithm         : {res.alg} (EdDSA)")
    print(f"    - Key ID            : {res.kid}")
    print(f"    - Payload Bytes     : {len(res.payload)}")
    print(f"    - Protected Headers : {res.protected_headers}")
    print(f"    - Unprotected Headers: {res.unprotected_headers}")

    try:
        inner_json = json.loads(res.payload.decode("utf-8"))
        print("    - Inner Payload CAID: " + inner_json.get("caid", "N/A"))
        print("    - Inner Disposition : " + inner_json.get("disposition", "N/A"))
    except Exception:
        pass


if __name__ == "__main__":
    main()


