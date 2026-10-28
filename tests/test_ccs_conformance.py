#!/usr/bin/env python3
"""Canonical Conformance Suite (CCS) Verification Tests for ReceiptPayload v1.0.

Validates all 15 test vectors against:
  1. Structural JSON Schema invariants (schemas/receipt_payload_v1.json)
  2. Cryptographic and Merkle Verification Engine logic (matching smaos_verify)

Vectors:
  001: Valid single leaf -> SUCCESS (0)
  002: Valid balanced tree -> SUCCESS (0)
  003: Valid unbalanced tree -> SUCCESS (0)
  004: Tampered payload digest -> MERKLE_PROOF_MISMATCH (-3)
  005: Tampered Ed25519 signature -> SIGNATURE_INVALID (-4)
  006: Tampered Merkle root hash -> MERKLE_PROOF_MISMATCH (-3)
  007: Ordinal violation (index >= size) -> MERKLE_BOUNDARY (-2)
  008: Ordinal violation (negative index) -> MERKLE_BOUNDARY (-2)
  009: Empty tree (tree_size = 0) -> MERKLE_BOUNDARY (-2)
  010: Tampered audit path sibling -> MERKLE_PROOF_MISMATCH (-3)
  011: Expired timestamp (year < 2024) -> TIMESTAMP_INVALID (-5)
  012: Future timestamp (year > 2030) -> TIMESTAMP_INVALID (-5)
  013: Preserved uncertainty (verdict: UNKNOWN) -> SUCCESS (0)
  014: Toxic receipt assertion (TOXIC_CONFIRMED) -> DISPOSITION_TOXIC (-6)
  015: Malformed schema missing fields -> JSON_PARSE (-1)
"""

import hashlib
import json
import unittest
from pathlib import Path
from typing import Any, Dict, List, Tuple
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature


ERR_SUCCESS = 0
ERR_JSON_PARSE = -1
ERR_MERKLE_BOUNDARY = -2
ERR_MERKLE_PROOF_MISMATCH = -3
ERR_SIGNATURE_INVALID = -4
ERR_TIMESTAMP_INVALID = -5
ERR_DISPOSITION_TOXIC = -6

VALID_DISPOSITIONS = {
    "CONFIRMED",
    "UNKNOWN",
    "MISSING_EVIDENCE",
    "CONFLICT",
    "REFUSED",
    "INVALID_INPUT",
}


def hash_leaf(data: bytes) -> bytes:
    return hashlib.sha256(b"\x00" + data).digest()


def hash_children(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + left + right).digest()


def verify_merkle_inclusion(
    leaf_hash: bytes,
    leaf_index: int,
    tree_size: int,
    audit_path: List[bytes],
    root_hash: bytes,
) -> bool:
    if tree_size == 0 or leaf_index >= tree_size or leaf_index < 0:
        return False
    if tree_size == 1:
        return len(audit_path) == 0 and leaf_hash == root_hash
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
            current = hash_children(sibling, current)
            while (fn % 2 == 0) and (fn < sn):
                fn //= 2
                sn //= 2
        else:
            current = hash_children(current, sibling)
        fn //= 2
        sn //= 2

    return current == root_hash


def verify_receipt(payload_bytes: bytes) -> int:
    """Mirrors the pure Rust smaos_verify verification engine."""
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        return ERR_JSON_PARSE

    # Required fields check
    required_fields = [
        "version",
        "action_id",
        "leaf_index",
        "tree_size",
        "timestamp",
        "intent_digest",
        "verdict",
        "root_hash",
        "signature",
        "signer_pubkey",
    ]
    for rf in required_fields:
        if rf not in payload:
            return ERR_JSON_PARSE

    if payload.get("version") != "1.0.0":
        return ERR_JSON_PARSE

    leaf_index = payload.get("leaf_index")
    tree_size = payload.get("tree_size")

    if not isinstance(leaf_index, int) or not isinstance(tree_size, int):
        return ERR_JSON_PARSE

    # Merkle Ordinal Boundary Invariant: 0 <= leaf_index < tree_size && tree_size >= 1
    if tree_size <= 0 or leaf_index < 0 or leaf_index >= tree_size:
        return ERR_MERKLE_BOUNDARY

    verdict = payload.get("verdict")
    if verdict == "TOXIC_CONFIRMED":
        return ERR_DISPOSITION_TOXIC
    if verdict not in VALID_DISPOSITIONS:
        return ERR_JSON_PARSE

    # Root hash decoding
    try:
        root_bytes = bytes.fromhex(payload["root_hash"])
        if len(root_bytes) != 32:
            return ERR_JSON_PARSE
    except Exception:
        return ERR_JSON_PARSE

    # Inclusion proof decoding
    audit_path = []
    for p in payload.get("inclusion_proof", []):
        try:
            b = bytes.fromhex(p)
            if len(b) != 32:
                return ERR_JSON_PARSE
            audit_path.append(b)
        except Exception:
            return ERR_JSON_PARSE

    # Leaf Hash computation
    try:
        intent_bytes = bytes.fromhex(payload["intent_digest"])
        if len(intent_bytes) != 32:
            return ERR_JSON_PARSE
    except Exception:
        return ERR_JSON_PARSE

    leaf_content = (
        payload["action_id"].encode("utf-8")
        + intent_bytes
        + verdict.encode("utf-8")
    )
    computed_leaf_hash = hash_leaf(leaf_content)

    # Verify Merkle inclusion proof
    if not verify_merkle_inclusion(
        computed_leaf_hash, leaf_index, tree_size, audit_path, root_bytes
    ):
        return ERR_MERKLE_PROOF_MISMATCH

    # Verify Ed25519 signature
    try:
        pubkey_bytes = bytes.fromhex(payload["signer_pubkey"])
        sig_bytes = bytes.fromhex(payload["signature"])
        if len(pubkey_bytes) != 32 or len(sig_bytes) != 64:
            return ERR_JSON_PARSE
        verifying_key = ed25519.Ed25519PublicKey.from_public_bytes(pubkey_bytes)
    except Exception:
        return ERR_JSON_PARSE

    signed_msg = (
        root_bytes
        + payload["action_id"].encode("utf-8")
        + verdict.encode("utf-8")
        + payload["timestamp"].encode("utf-8")
    )

    try:
        verifying_key.verify(sig_bytes, signed_msg)
    except InvalidSignature:
        return ERR_SIGNATURE_INVALID

    # Timestamp sanity
    ts = str(payload.get("timestamp", ""))
    if len(ts) >= 4:
        try:
            year = int(ts[:4])
            if year < 2024 or year > 2030:
                return ERR_TIMESTAMP_INVALID
        except ValueError:
            return ERR_TIMESTAMP_INVALID

    return ERR_SUCCESS


class TestCCSConformanceVectors(unittest.TestCase):
    """Test all 15 Canonical Conformance Suite test vectors."""

    def setUp(self):
        self.vectors_dir = Path("conformance_vectors/ccs")
        self.assertTrue(self.vectors_dir.exists(), "conformance_vectors/ccs directory must exist")

    def _read_vector(self, filename: str) -> bytes:
        p = self.vectors_dir / filename
        self.assertTrue(p.exists(), f"{filename} must exist")
        return p.read_bytes()

    def test_001_valid_single_leaf(self):
        res = verify_receipt(self._read_vector("001_valid_single_leaf.json"))
        self.assertEqual(res, ERR_SUCCESS)

    def test_002_valid_balanced_tree(self):
        res = verify_receipt(self._read_vector("002_valid_balanced_tree.json"))
        self.assertEqual(res, ERR_SUCCESS)

    def test_003_valid_unbalanced_tree(self):
        res = verify_receipt(self._read_vector("003_valid_unbalanced_tree.json"))
        self.assertEqual(res, ERR_SUCCESS)

    def test_004_tampered_payload_digest(self):
        res = verify_receipt(self._read_vector("004_tampered_payload_digest.json"))
        self.assertEqual(res, ERR_MERKLE_PROOF_MISMATCH)

    def test_005_tampered_signature(self):
        res = verify_receipt(self._read_vector("005_tampered_signature.json"))
        self.assertEqual(res, ERR_SIGNATURE_INVALID)

    def test_006_tampered_root_hash(self):
        res = verify_receipt(self._read_vector("006_tampered_root_hash.json"))
        self.assertEqual(res, ERR_MERKLE_PROOF_MISMATCH)

    def test_007_ordinal_violation_index_gte_size(self):
        res = verify_receipt(self._read_vector("007_ordinal_violation_index_gte_size.json"))
        self.assertEqual(res, ERR_MERKLE_BOUNDARY)

    def test_008_ordinal_negative_index(self):
        res = verify_receipt(self._read_vector("008_ordinal_negative_index.json"))
        self.assertEqual(res, ERR_MERKLE_BOUNDARY)

    def test_009_empty_tree_size_zero(self):
        res = verify_receipt(self._read_vector("009_empty_tree_size_zero.json"))
        self.assertEqual(res, ERR_MERKLE_BOUNDARY)

    def test_010_tampered_sibling_hash(self):
        res = verify_receipt(self._read_vector("010_tampered_sibling_hash.json"))
        self.assertEqual(res, ERR_MERKLE_PROOF_MISMATCH)

    def test_011_expired_timestamp(self):
        res = verify_receipt(self._read_vector("011_expired_timestamp.json"))
        self.assertEqual(res, ERR_TIMESTAMP_INVALID)

    def test_012_future_timestamp(self):
        res = verify_receipt(self._read_vector("012_future_timestamp.json"))
        self.assertEqual(res, ERR_TIMESTAMP_INVALID)

    def test_013_preserved_uncertainty_unknown(self):
        res = verify_receipt(self._read_vector("013_preserved_uncertainty_unknown.json"))
        self.assertEqual(res, ERR_SUCCESS)

    def test_014_toxic_receipt_assertion(self):
        res = verify_receipt(self._read_vector("014_toxic_receipt_assertion.json"))
        self.assertEqual(res, ERR_DISPOSITION_TOXIC)

    def test_015_invalid_schema_missing_fields(self):
        res = verify_receipt(self._read_vector("015_invalid_schema_missing_fields.json"))
        self.assertEqual(res, ERR_JSON_PARSE)

    def test_manifest_completeness(self):
        manifest_path = self.vectors_dir / "manifest.json"
        self.assertTrue(manifest_path.exists())
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        self.assertEqual(len(manifest), 15)


if __name__ == "__main__":
    unittest.main()
