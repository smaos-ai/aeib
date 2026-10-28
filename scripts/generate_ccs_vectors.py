#!/usr/bin/env python3
"""Canonical Conformance Suite (CCS) Test Vector Generator for ReceiptPayload v1.0.

Generates 15 canonical test vectors for SMAOS / STAR Protocol conformance:
  001: Valid single leaf (leaf_index=0, tree_size=1)
  002: Valid balanced tree (leaf_index=3, tree_size=8)
  003: Valid unbalanced tree (leaf_index=6, tree_size=7)
  004: Tampered payload digest (mismatch against Merkle leaf)
  005: Tampered Ed25519 signature (1 byte corrupted)
  006: Tampered Merkle root hash (root_hash does not match audit path)
  007: Ordinal violation (leaf_index >= tree_size)
  008: Ordinal violation (negative leaf_index)
  009: Empty tree (tree_size = 0)
  010: Tampered audit path (corrupted sibling hash)
  011: Expired timestamp (before 2024 cutoff)
  012: Future timestamp (clock skew attack after 2030)
  013: Preserved uncertainty (verdict: UNKNOWN with valid inclusion)
  014: Toxic receipt assertion (verdict: TOXIC_CONFIRMED)
  015: Invalid JSON formatting / missing required fields

Zero external dependencies outside cryptography · Python 3.10+ stdlib
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple
from cryptography.hazmat.primitives.asymmetric import ed25519


# Ephemeral private key for test vector generation
PRIVATE_KEY = ed25519.Ed25519PrivateKey.generate()
PUBLIC_KEY = PRIVATE_KEY.public_key()
PUBLIC_KEY_HEX = PUBLIC_KEY.public_bytes_raw().hex()


def hash_leaf(data: bytes) -> bytes:
    """RFC 9162 domain-separated leaf hash: SHA-256(0x00 || data)."""
    return hashlib.sha256(b"\x00" + data).digest()


def hash_children(left: bytes, right: bytes) -> bytes:
    """RFC 9162 domain-separated interior hash: SHA-256(0x01 || left || right)."""
    return hashlib.sha256(b"\x01" + left + right).digest()


def largest_power_of_2_less_than(n: int) -> int:
    k = 1
    while k * 2 < n:
        k *= 2
    return k


def compute_mth(leaves: List[bytes]) -> bytes:
    """Computes Merkle Tree Hash according to RFC 6962 / RFC 9162."""
    n = len(leaves)
    if n == 0:
        return hashlib.sha256(b"").digest()
    if n == 1:
        return hash_leaf(leaves[0])
    k = largest_power_of_2_less_than(n)
    return hash_children(compute_mth(leaves[:k]), compute_mth(leaves[k:]))


def compute_audit_path(leaves: List[bytes], m: int) -> List[bytes]:
    """Generates RFC 6962 Merkle audit path for leaf at index m."""
    n = len(leaves)
    if n <= 1:
        return []
    k = largest_power_of_2_less_than(n)
    if m < k:
        return compute_audit_path(leaves[:k], m) + [compute_mth(leaves[k:])]
    else:
        return compute_audit_path(leaves[k:], m - k) + [compute_mth(leaves[:k])]


def sign_receipt(root_bytes: bytes, action_id: str, verdict: str, timestamp: str) -> str:
    """Signs root_hash + action_id + verdict + timestamp using Ed25519."""
    msg = root_bytes + action_id.encode("utf-8") + verdict.encode("utf-8") + timestamp.encode("utf-8")
    sig = PRIVATE_KEY.sign(msg)
    return sig.hex()


def create_leaf_content(action_id: str, intent_hex: str, verdict: str) -> bytes:
    intent_bytes = bytes.fromhex(intent_hex)
    return action_id.encode("utf-8") + intent_bytes + verdict.encode("utf-8")


def generate_vectors(output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    vectors: List[Tuple[str, Dict[str, Any], str]] = []

    # ──────────────────────────────────────────────────────────────────────────
    # 001: Valid Single Leaf (tree_size = 1, leaf_index = 0)
    # ──────────────────────────────────────────────────────────────────────────
    action_001 = "act-ccs-001-single"
    intent_001 = hashlib.sha256(b'{"action":"pay","amount":1000}').hexdigest()
    verdict_001 = "CONFIRMED"
    ts_001 = "2026-09-18T10:00:00Z"
    leaf_content_001 = create_leaf_content(action_001, intent_001, verdict_001)
    root_001 = hash_leaf(leaf_content_001)
    sig_001 = sign_receipt(root_001, action_001, verdict_001, ts_001)

    v001 = {
        "version": "1.0.0",
        "action_id": action_001,
        "leaf_index": 0,
        "tree_size": 1,
        "timestamp": ts_001,
        "intent_digest": intent_001,
        "verdict": verdict_001,
        "root_hash": root_001.hex(),
        "inclusion_proof": [],
        "audit_anchor": {"xid": 100001, "idempotency_key": "idem-001"},
        "signature": sig_001,
        "signer_pubkey": PUBLIC_KEY_HEX,
    }
    vectors.append(("001_valid_single_leaf.json", v001, "Valid single leaf audit log receipt"))

    # ──────────────────────────────────────────────────────────────────────────
    # 002: Valid Balanced Tree (tree_size = 8, leaf_index = 3)
    # ──────────────────────────────────────────────────────────────────────────
    leaves_8 = []
    action_002 = "act-ccs-002-balanced-3"
    intent_002 = hashlib.sha256(b'{"action":"settle","amount":5000}').hexdigest()
    verdict_002 = "CONFIRMED"
    ts_002 = "2026-09-18T10:05:00Z"

    for i in range(8):
        if i == 3:
            leaves_8.append(create_leaf_content(action_002, intent_002, verdict_002))
        else:
            leaves_8.append(f"other_leaf_{i}".encode("utf-8"))

    root_002 = compute_mth(leaves_8)
    proof_002 = [p.hex() for p in compute_audit_path(leaves_8, 3)]
    sig_002 = sign_receipt(root_002, action_002, verdict_002, ts_002)

    v002 = {
        "version": "1.0.0",
        "action_id": action_002,
        "leaf_index": 3,
        "tree_size": 8,
        "timestamp": ts_002,
        "intent_digest": intent_002,
        "verdict": verdict_002,
        "root_hash": root_002.hex(),
        "inclusion_proof": proof_002,
        "audit_anchor": {"xid": 100002, "idempotency_key": "idem-002"},
        "signature": sig_002,
        "signer_pubkey": PUBLIC_KEY_HEX,
    }
    vectors.append(("002_valid_balanced_tree.json", v002, "Valid balanced tree (size 8, index 3)"))

    # ──────────────────────────────────────────────────────────────────────────
    # 003: Valid Unbalanced Tree (tree_size = 7, leaf_index = 6)
    # ──────────────────────────────────────────────────────────────────────────
    leaves_7 = []
    action_003 = "act-ccs-003-unbalanced-6"
    intent_003 = hashlib.sha256(b'{"action":"sepa","amount":2500}').hexdigest()
    verdict_003 = "CONFIRMED"
    ts_003 = "2026-09-18T10:10:00Z"

    for i in range(7):
        if i == 6:
            leaves_7.append(create_leaf_content(action_003, intent_003, verdict_003))
        else:
            leaves_7.append(f"leaf_unbalanced_{i}".encode("utf-8"))

    root_003 = compute_mth(leaves_7)
    proof_003 = [p.hex() for p in compute_audit_path(leaves_7, 6)]
    sig_003 = sign_receipt(root_003, action_003, verdict_003, ts_003)

    v003 = {
        "version": "1.0.0",
        "action_id": action_003,
        "leaf_index": 6,
        "tree_size": 7,
        "timestamp": ts_003,
        "intent_digest": intent_003,
        "verdict": verdict_003,
        "root_hash": root_003.hex(),
        "inclusion_proof": proof_003,
        "audit_anchor": {"xid": 100003, "idempotency_key": "idem-003"},
        "signature": sig_003,
        "signer_pubkey": PUBLIC_KEY_HEX,
    }
    vectors.append(("003_valid_unbalanced_tree.json", v003, "Valid unbalanced tree (size 7, index 6)"))

    # ──────────────────────────────────────────────────────────────────────────
    # 004: Tampered Payload Digest (Proof Mismatch)
    # ──────────────────────────────────────────────────────────────────────────
    v004 = dict(v001)
    v004["action_id"] = "act-ccs-004-tampered-digest"
    # Flip last byte of intent_digest
    tampered_digest = v001["intent_digest"][:-2] + "ff"
    v004["intent_digest"] = tampered_digest
    vectors.append(("004_tampered_payload_digest.json", v004, "Tampered intent_digest -> proof mismatch"))

    # ──────────────────────────────────────────────────────────────────────────
    # 005: Tampered Ed25519 Signature
    # ──────────────────────────────────────────────────────────────────────────
    action_005 = "act-ccs-005-tampered-sig"
    leaf_content_005 = create_leaf_content(action_005, intent_001, verdict_001)
    root_005 = hash_leaf(leaf_content_005)
    sig_005 = sign_receipt(root_005, action_005, verdict_001, ts_001)
    # Corrupt first byte of valid signature
    corrupt_byte = "ff" if sig_005[:2] != "ff" else "00"
    sig_corrupt = corrupt_byte + sig_005[2:]

    v005 = {
        "version": "1.0.0",
        "action_id": action_005,
        "leaf_index": 0,
        "tree_size": 1,
        "timestamp": ts_001,
        "intent_digest": intent_001,
        "verdict": verdict_001,
        "root_hash": root_005.hex(),
        "inclusion_proof": [],
        "signature": sig_corrupt,
        "signer_pubkey": PUBLIC_KEY_HEX,
    }
    vectors.append(("005_tampered_signature.json", v005, "Corrupted Ed25519 signature -> invalid signature"))

    # ──────────────────────────────────────────────────────────────────────────
    # 006: Tampered Merkle Root Hash
    # ──────────────────────────────────────────────────────────────────────────
    v006 = dict(v002)
    v006["action_id"] = "act-ccs-006-tampered-root"
    v006["root_hash"] = "00" * 32
    vectors.append(("006_tampered_root_hash.json", v006, "Mismatched root_hash -> proof mismatch"))

    # ──────────────────────────────────────────────────────────────────────────
    # 007: Ordinal Violation: leaf_index >= tree_size
    # ──────────────────────────────────────────────────────────────────────────
    v007 = dict(v002)
    v007["action_id"] = "act-ccs-007-ordinal-violation"
    v007["leaf_index"] = 8  # tree_size is 8
    vectors.append(("007_ordinal_violation_index_gte_size.json", v007, "Ordinal violation (leaf_index >= tree_size)"))

    # ──────────────────────────────────────────────────────────────────────────
    # 008: Ordinal Violation: Negative / Out-of-bounds Leaf Index
    # ──────────────────────────────────────────────────────────────────────────
    v008 = dict(v001)
    v008["action_id"] = "act-ccs-008-negative-index"
    v008["leaf_index"] = -1
    vectors.append(("008_ordinal_negative_index.json", v008, "Negative leaf index boundary violation"))

    # ──────────────────────────────────────────────────────────────────────────
    # 009: Empty Tree: tree_size = 0
    # ──────────────────────────────────────────────────────────────────────────
    v009 = dict(v001)
    v009["action_id"] = "act-ccs-009-empty-tree"
    v009["tree_size"] = 0
    vectors.append(("009_empty_tree_size_zero.json", v009, "Empty tree tree_size=0 violation"))

    # ──────────────────────────────────────────────────────────────────────────
    # 010: Tampered Sibling Hash in Audit Path
    # ──────────────────────────────────────────────────────────────────────────
    v010 = dict(v002)
    v010["action_id"] = "act-ccs-010-corrupt-sibling"
    corrupt_proof = list(v002["inclusion_proof"])
    corrupt_proof[0] = "deadbeef" * 8
    v010["inclusion_proof"] = corrupt_proof
    vectors.append(("010_tampered_sibling_hash.json", v010, "Corrupt sibling hash in audit path"))

    # ──────────────────────────────────────────────────────────────────────────
    # 011: Expired Timestamp (Before 2024 Cutoff)
    # ──────────────────────────────────────────────────────────────────────────
    action_011 = "act-ccs-011-expired"
    ts_011 = "2020-01-01T00:00:00Z"
    leaf_011 = create_leaf_content(action_011, intent_001, verdict_001)
    root_011 = hash_leaf(leaf_011)
    sig_011 = sign_receipt(root_011, action_011, verdict_001, ts_011)
    v011 = {
        "version": "1.0.0",
        "action_id": action_011,
        "leaf_index": 0,
        "tree_size": 1,
        "timestamp": ts_011,
        "intent_digest": intent_001,
        "verdict": verdict_001,
        "root_hash": root_011.hex(),
        "inclusion_proof": [],
        "signature": sig_011,
        "signer_pubkey": PUBLIC_KEY_HEX,
    }
    vectors.append(("011_expired_timestamp.json", v011, "Expired timestamp (year 2020 < 2024)"))

    # ──────────────────────────────────────────────────────────────────────────
    # 012: Future Timestamp (Clock Skew Attack > 2030)
    # ──────────────────────────────────────────────────────────────────────────
    action_012 = "act-ccs-012-future"
    ts_012 = "2035-05-01T12:00:00Z"
    leaf_012 = create_leaf_content(action_012, intent_001, verdict_001)
    root_012 = hash_leaf(leaf_012)
    sig_012 = sign_receipt(root_012, action_012, verdict_001, ts_012)
    v012 = {
        "version": "1.0.0",
        "action_id": action_012,
        "leaf_index": 0,
        "tree_size": 1,
        "timestamp": ts_012,
        "intent_digest": intent_001,
        "verdict": verdict_001,
        "root_hash": root_012.hex(),
        "inclusion_proof": [],
        "signature": sig_012,
        "signer_pubkey": PUBLIC_KEY_HEX,
    }
    vectors.append(("012_future_timestamp.json", v012, "Future timestamp clock skew (year 2035 > 2030)"))

    # ──────────────────────────────────────────────────────────────────────────
    # 013: Preserved Uncertainty: verdict = UNKNOWN
    # ──────────────────────────────────────────────────────────────────────────
    action_013 = "act-ccs-013-unknown"
    verdict_013 = "UNKNOWN"
    ts_013 = "2026-09-18T11:00:00Z"
    leaf_013 = create_leaf_content(action_013, intent_001, verdict_013)
    root_013 = hash_leaf(leaf_013)
    sig_013 = sign_receipt(root_013, action_013, verdict_013, ts_013)
    v013 = {
        "version": "1.0.0",
        "action_id": action_013,
        "leaf_index": 0,
        "tree_size": 1,
        "timestamp": ts_013,
        "intent_digest": intent_001,
        "verdict": verdict_013,
        "root_hash": root_013.hex(),
        "inclusion_proof": [],
        "audit_anchor": {"xid": 100013, "note": "Held fail-closed under DORA Art. 17"},
        "signature": sig_013,
        "signer_pubkey": PUBLIC_KEY_HEX,
    }
    vectors.append(("013_preserved_uncertainty_unknown.json", v013, "Preserved uncertainty: verdict UNKNOWN"))

    # ──────────────────────────────────────────────────────────────────────────
    # 014: Toxic Receipt Assertion: verdict = TOXIC_CONFIRMED
    # ──────────────────────────────────────────────────────────────────────────
    v014 = dict(v001)
    v014["action_id"] = "act-ccs-014-toxic-verdict"
    v014["verdict"] = "TOXIC_CONFIRMED"
    vectors.append(("014_toxic_receipt_assertion.json", v014, "Illegal toxic verdict assertion"))

    # ──────────────────────────────────────────────────────────────────────────
    # 015: Invalid JSON / Schema Missing Required Fields
    # ──────────────────────────────────────────────────────────────────────────
    v015 = {
        "version": "1.0.0",
        "action_id": "act-ccs-015-missing-fields",
        # Missing leaf_index, tree_size, root_hash, signature, signer_pubkey
        "timestamp": "2026-09-18T11:30:00Z",
        "verdict": "CONFIRMED",
    }
    vectors.append(("015_invalid_schema_missing_fields.json", v015, "Malformed schema missing required properties"))

    # Write each vector
    manifest = []
    for filename, payload, desc in vectors:
        file_path = output_dir / filename
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            f.write("\n")
        manifest.append({
            "file": filename,
            "description": desc,
            "sha256": hashlib.sha256(json.dumps(payload).encode("utf-8")).hexdigest(),
        })

    # Write manifest
    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    print(f"✅ Generated {len(vectors)} CCS test vectors into {output_dir}")


if __name__ == "__main__":
    generate_vectors(Path("conformance_vectors/ccs"))
