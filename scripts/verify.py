#!/usr/bin/env python3
r"""
verify.py — Standalone Cryptographic Verifier for SMAOS & Research OS Receipts
Verifies RFC 8785 JCS canonicalization, RFC 9052 COSE_Sign1 envelopes (Ed25519),
SHA-256 append-only hash chains, and Merkle root anchoring.
"""

import os
import sys
import json
import argparse
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

# Add src to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
try:
    from diagnostic_normalizer import (
        deterministic_json_bytes,
        deterministic_digest,
        COSESign1Engine,
        COSE_ALG_EDDSA
    )
except ImportError:
    from src.diagnostic_normalizer import (
        deterministic_json_bytes,
        deterministic_digest,
        COSESign1Engine,
        COSE_ALG_EDDSA
    )

EXCLUDED_KEYS = {"payload_hash", "cose_envelope_hex", "cose_alg", "signature_hex", "head_hash"}


def load_public_key(pubkey_path: Path) -> ed25519.Ed25519PublicKey:
    if not pubkey_path.exists():
        raise FileNotFoundError(f"Public key not found at {pubkey_path}")
    with open(pubkey_path, "rb") as f:
        return serialization.load_pem_public_key(f.read())


def verify_single_receipt(
    receipt_data: Dict[str, Any],
    public_key: ed25519.Ed25519PublicKey,
    expected_prev_hash: Optional[str] = None
) -> Tuple[bool, List[str]]:
    """
    Verifies a single receipt against all cryptographic and integrity invariants.
    Returns (success, list_of_errors).
    """
    errors = []

    # 1. Check Required Top-Level Keys
    required_keys = [
        "receipt_version", "receipt_type", "key_id", "research_session_id",
        "query", "disposition", "timestamp", "timestamp_utc", "sources",
        "previous_hash", "payload_hash", "cose_envelope_hex", "cose_alg", "head_hash"
    ]
    for k in required_keys:
        if k not in receipt_data:
            errors.append(f"Missing required field: '{k}'")

    if errors:
        return False, errors

    # 2. Check Previous Hash Continuity (if provided)
    if expected_prev_hash and receipt_data["previous_hash"] != expected_prev_hash:
        errors.append(
            f"Hash chain break: receipt previous_hash '{receipt_data['previous_hash']}' "
            f"!= expected previous head '{expected_prev_hash}'"
        )

    # 3. Check JCS Canonical Serialization & Payload Hash
    unsigned_payload = {k: v for k, v in receipt_data.items() if k not in EXCLUDED_KEYS}
    canonical_bytes = deterministic_json_bytes(unsigned_payload)
    computed_digest = deterministic_digest(unsigned_payload)

    if receipt_data["payload_hash"] != computed_digest:
        errors.append(
            f"Payload hash mismatch: recorded '{receipt_data['payload_hash']}' "
            f"!= computed '{computed_digest}'"
        )

    # 4. Check RFC 9052 COSE_Sign1 Envelope & Ed25519 Signature
    try:
        envelope_bytes = bytes.fromhex(receipt_data["cose_envelope_hex"])
        is_valid_sig, decoded_payload, meta = COSESign1Engine.verify_envelope(
            envelope_bytes, public_key
        )
        if not is_valid_sig:
            errors.append("COSE_Sign1 signature verification failed")
        if decoded_payload != canonical_bytes:
            errors.append("COSE_Sign1 envelope payload does not match canonical JCS bytes")
        if meta.get("cose_alg") != COSE_ALG_EDDSA:
            errors.append(f"Unexpected COSE algorithm: {meta.get('cose_alg')} (expected {COSE_ALG_EDDSA})")
    except Exception as e:
        errors.append(f"COSE_Sign1 decoding/verification error: {str(e)}")

    # 5. Check SHA-256 Hash Chain Computation
    ts_str = str(receipt_data["timestamp"])
    chain_input = (receipt_data["previous_hash"] + canonical_bytes.decode("utf-8") + ts_str).encode("utf-8")
    computed_head = hashlib.sha256(chain_input).hexdigest()

    if receipt_data["head_hash"] != computed_head:
        errors.append(
            f"Chain head hash mismatch: recorded '{receipt_data['head_hash']}' "
            f"!= recomputed '{computed_head}'"
        )

    return len(errors) == 0, errors


def verify_receipts_in_path(
    target_path: Path,
    pubkey_path: Path,
    merkle_file: Optional[Path] = None
) -> bool:
    """
    Verifies a single file or a directory of receipts in chronological/chain order.
    """
    public_key = load_public_key(pubkey_path)

    if target_path.is_file():
        receipt_files = [target_path]
    elif target_path.is_dir():
        raw_files = [f for f in target_path.glob("*.json") if not f.name.startswith(".")]
        def _get_ts(p: Path) -> int:
            try:
                with open(p, "r", encoding="utf-8") as rf:
                    return json.load(rf).get("timestamp", 0)
            except Exception:
                return 0
        receipt_files = sorted(raw_files, key=lambda p: (_get_ts(p), p.name))
    else:
        print(f"[ERROR] Target path does not exist: {target_path}", file=sys.stderr)
        return False

    if not receipt_files:
        print(f"[WARN] No receipt JSON files found in {target_path}")
        return True

    print(f"================================================================================")
    print(f"  SMAOS Cryptographic Provenance Verifier (RFC 8785 JCS + RFC 9052 COSE_Sign1)")
    print(f"================================================================================")
    print(f"  Public Key:   {pubkey_path}")
    print(f"  Target Path:  {target_path} ({len(receipt_files)} receipt(s))")
    print(f"--------------------------------------------------------------------------------")

    all_passed = True
    last_head_hash = None

    for idx, r_file in enumerate(receipt_files):
        try:
            with open(r_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"❌ [FAIL] {r_file.name}: Could not parse JSON ({e})")
            all_passed = False
            continue

        # In a sequence of receipts, chain continuity is validated against the previous receipt's head
        expected_prev = last_head_hash if (idx > 0 and last_head_hash) else None
        valid, errs = verify_single_receipt(data, public_key, expected_prev_hash=expected_prev)

        if valid:
            last_head_hash = data["head_hash"]
            print(f"✅ [PASS] {r_file.name}")
            print(f"          Session: {data.get('research_session_id')} | Disp: {data.get('disposition')}")
            print(f"          Head:    {data.get('head_hash')[:24]}... | Sources: {len(data.get('sources', []))}")
        else:
            all_passed = False
            print(f"❌ [FAIL] {r_file.name}")
            for err in errs:
                print(f"          • {err}")

    # Check Merkle Root consistency if specified or found
    if merkle_file and merkle_file.exists():
        recorded_root = merkle_file.read_text().strip()
        print(f"--------------------------------------------------------------------------------")
        if last_head_hash and recorded_root == last_head_hash:
            print(f"✅ [ANCHOR] Merkle Root Verified: {recorded_root}")
        else:
            print(f"❌ [ANCHOR] Merkle Root Mismatch: recorded '{recorded_root}' != last head '{last_head_hash}'")
            all_passed = False

    print(f"================================================================================")
    status_str = "VERIFICATION SUCCEEDED (100% Valid)" if all_passed else "VERIFICATION FAILED"
    print(f"  Result: {status_str}")
    print(f"================================================================================")
    return all_passed


def main():
    parser = argparse.ArgumentParser(description="Verify cryptographic provenance receipts.")
    parser.add_argument("path", nargs="?", default="provenance/receipts", help="Receipt JSON file or directory")
    parser.add_argument("--key", default="keys/ed25519-public.pem", help="Path to Ed25519 public key")
    parser.add_argument("--merkle-root", default="provenance/merkle_root.txt", help="Path to Merkle root text file")

    args = parser.parse_args()
    success = verify_receipts_in_path(
        target_path=Path(args.path),
        pubkey_path=Path(args.key),
        merkle_file=Path(args.merkle_root) if args.merkle_root else None
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
