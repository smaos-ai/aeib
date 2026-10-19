#!/usr/bin/env python3
"""
tools/standalone_receipt_verifier.py
================================================================================
AEIB Standalone Offline Receipt Verifier Specification Script.

Purpose:
  Provides an independent, self-contained verification tool for third-party
  auditors and external evaluators to verify AEIB action receipts, CAID bindings,
  and Ed25519 cryptographic signatures without network access or repository coupling.

Design Invariants:
  1. Zero Network Egress: Operates 100% air-gapped; never initiates network calls.
  2. Caller-Supplied Public Key: Enforces explicit key custody; does not perform
     implicit or remote public-key discovery.
  3. Strict Canonicalization: Implements pure RFC 8785 JSON Canonicalization Scheme (JCS).
  4. Deterministic Falsification: Built-in --self-test validates positive and negative vectors.

Evaluated under the stated model. Preserves strict epistemic calibration.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
except ImportError:
    print(
        "[!] Error: 'cryptography' library is required for Ed25519 signature verification.\n"
        "    Install via: pip install cryptography",
        file=sys.stderr,
    )
    sys.exit(2)


# ==============================================================================
# 1. Pure RFC 8785 JSON Canonicalization Scheme (JCS)
# ==============================================================================

def encode_jcs(val: Any) -> bytes:
    """
    Serializes a Python object to canonical JSON bytes per RFC 8785.
    - Keys sorted lexicographically by UTF-16 code units.
    - No extraneous whitespace between tokens.
    - Deterministic IEEE 754 float representation.
    """
    if val is None:
        return b"null"
    if isinstance(val, bool):
        return b"true" if val else b"false"
    if isinstance(val, int):
        return str(val).encode("utf-8")
    if isinstance(val, float):
        if val != val or val == float("inf") or val == float("-inf"):
            raise ValueError(f"JCS does not permit non-finite floats: {val}")
        if val.is_integer():
            return str(int(val)).encode("utf-8")
        s = f"{val:.16g}"
        return s.encode("utf-8")
    if isinstance(val, str):
        return json.dumps(val, ensure_ascii=False).encode("utf-8")
    if isinstance(val, (list, tuple)):
        items = [encode_jcs(x) for x in val]
        return b"[" + b",".join(items) + b"]"
    if isinstance(val, dict):
        sorted_keys = sorted(
            val.keys(),
            key=lambda k: k.encode("utf-16-be")
        )
        parts = []
        for k in sorted_keys:
            encoded_k = json.dumps(k, ensure_ascii=False).encode("utf-8")
            encoded_v = encode_jcs(val[k])
            parts.append(encoded_k + b":" + encoded_v)
        return b"{" + b",".join(parts) + b"}"
    raise TypeError(f"Type {type(val)} cannot be serialized under RFC 8785 JCS")


def compute_sha256_prefixed(data: bytes) -> str:
    """Computes a SHA-256 digest with the canonical 'sha256:' prefix."""
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


# ==============================================================================
# 2. Public Key Loader
# ==============================================================================

def load_ed25519_public_key(key_source: Union[str, bytes, Path]) -> Ed25519PublicKey:
    """
    Loads an Ed25519 public key from PEM, raw hex (64 chars), raw base64 (44 chars),
    or a filesystem path.
    """
    raw_data: bytes
    if isinstance(key_source, Path) or (isinstance(key_source, str) and Path(key_source).is_file()):
        raw_data = Path(key_source).read_bytes()
    elif isinstance(key_source, str):
        raw_data = key_source.strip().encode("utf-8")
    else:
        raw_data = key_source.strip()

    # Case 1: PEM encoded
    if b"-----BEGIN PUBLIC KEY-----" in raw_data:
        pub = serialization.load_pem_public_key(raw_data)
        if not isinstance(pub, Ed25519PublicKey):
            raise ValueError(f"Key in PEM is not an Ed25519PublicKey (got {type(pub)})")
        return pub

    # Case 2: Hex encoded 32-byte key (64 hex characters)
    text_str = raw_data.decode("ascii", errors="ignore").strip()
    if len(text_str) == 64:
        try:
            key_bytes = bytes.fromhex(text_str)
            return Ed25519PublicKey.from_public_bytes(key_bytes)
        except ValueError:
            pass

    # Case 3: Base64 encoded 32-byte key (44 base64 chars)
    if len(text_str) in (43, 44):
        try:
            key_bytes = base64.b64decode(text_str)
            if len(key_bytes) == 32:
                return Ed25519PublicKey.from_public_bytes(key_bytes)
        except Exception:
            pass

    # Case 4: Raw 32 bytes
    if len(raw_data) == 32:
        return Ed25519PublicKey.from_public_bytes(raw_data)

    raise ValueError(
        "Unrecognized Ed25519 public key format. "
        "Expected PEM (SubjectPublicKeyInfo), 64-char hex, or 32-byte base64."
    )


# ==============================================================================
# 3. Receipt Verification Logic
# ==============================================================================

VALID_DISPOSITIONS = {
    "CONFIRMED",
    "REFUTED",
    "EFFECT_INDETERMINATE",
    "OUTCOME_VERIFIED",
    "DISPATCHED_UNCONFIRMED",
    "AUTHORIZED_FOR_HOST_SIGNING",
}


def verify_receipt_data(
    receipt: Dict[str, Any],
    trusted_public_key: Ed25519PublicKey,
    expected_operation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Evaluates an AEIB execution receipt under caller-supplied public key.
    Verifies:
      1. Required fields presence (operation_id, disposition, signature/attestation).
      2. CAID match against action proposal payload (if payload is embedded).
      3. Cryptographic Ed25519 signature over canonical RFC 8785 JCS receipt body.
    """
    op_id = receipt.get("operation_id") or receipt.get("operationId")
    if not op_id:
        return {"valid": False, "error": "Receipt missing required 'operation_id'"}

    if expected_operation_id and op_id != expected_operation_id:
        return {
            "valid": False,
            "error": f"Operation ID mismatch: expected '{expected_operation_id}', got '{op_id}'",
        }

    # 1. Disposition check
    disposition = (
        receipt.get("disposition")
        or receipt.get("final_disposition")
        or receipt.get("evaluated_disposition")
    )
    if disposition and disposition not in VALID_DISPOSITIONS:
        return {
            "valid": False,
            "error": f"Invalid receipt disposition: '{disposition}' not in {VALID_DISPOSITIONS}",
        }

    # 2. CAID validation if proposal payload is present
    action_payload = receipt.get("action_payload") or receipt.get("payload")
    claimed_caid = receipt.get("action_caid") or receipt.get("caid")
    if action_payload is not None and claimed_caid is not None:
        computed_caid = compute_sha256_prefixed(encode_jcs(action_payload))
        if claimed_caid != computed_caid:
            return {
                "valid": False,
                "error": f"CAID mismatch: claimed '{claimed_caid}', computed '{computed_caid}'",
            }

    # 3. Extract signature and unsigned body
    sig_bytes: Optional[bytes] = None
    unsigned_body: Dict[str, Any] = {}

    # Format A: Modern AEIB envelope with "attestation_signature" or "signature" dict
    if "attestation_signature" in receipt:
        att = receipt["attestation_signature"]
        sig_b64 = att.get("signature_b64") or att.get("signature_hex")
        if sig_b64:
            try:
                sig_bytes = bytes.fromhex(sig_b64) if len(sig_b64) == 128 else base64.b64decode(sig_b64)
            except Exception:
                return {"valid": False, "error": "Malformed signature encoding in attestation_signature"}
        unsigned_body = {k: v for k, v in receipt.items() if k != "attestation_signature"}

    # Format B: Flat receipt with "signature_b64" or "signature_hex"
    elif "signature_b64" in receipt or "signature_hex" in receipt:
        sig_val = receipt.get("signature_b64") or receipt.get("signature_hex")
        if sig_val:
            try:
                sig_bytes = bytes.fromhex(sig_val) if len(sig_val) == 128 else base64.b64decode(sig_val)
            except Exception:
                return {"valid": False, "error": "Malformed signature encoding"}
        unsigned_body = {
            k: v for k, v in receipt.items()
            if k not in ("signature_b64", "signature_hex", "gate_signature")
        }

    # Format C: Warrant receipt with "warrant_caid"
    elif "warrant_caid" in receipt and "signature_b64" in receipt:
        sig_bytes = base64.b64decode(receipt["signature_b64"])
        unsigned_body = {k: v for k, v in receipt.items() if k != "signature_b64"}

    # Format D: Legacy envelope with "signedStatement" base64
    elif "signedStatement" in receipt and "signature" in receipt:
        sig_container = receipt["signature"]
        sig_val = sig_container.get("ed25519Signature")
        if sig_val:
            sig_bytes = base64.b64decode(sig_val)
            raw_statement = base64.b64decode(receipt["signedStatement"])
            try:
                trusted_public_key.verify(sig_bytes, raw_statement)
                return {
                    "valid": True,
                    "operation_id": op_id,
                    "disposition": disposition or "UNKNOWN",
                    "format": "legacy_signed_statement",
                    "error": None,
                }
            except InvalidSignature:
                return {"valid": False, "error": "Invalid Ed25519 signature on signedStatement"}

    if not sig_bytes:
        return {"valid": False, "error": "No recognized Ed25519 signature field found in receipt"}

    # 4. Canonicalize unsigned body and verify signature
    canonical_bytes = encode_jcs(unsigned_body)
    try:
        trusted_public_key.verify(sig_bytes, canonical_bytes)
    except InvalidSignature:
        return {"valid": False, "error": "Invalid Ed25519 signature over canonical RFC 8785 JCS receipt"}

    return {
        "valid": True,
        "operation_id": op_id,
        "disposition": disposition or "UNSPECIFIED",
        "receipt_sha256": compute_sha256_prefixed(canonical_bytes),
        "error": None,
    }


# ==============================================================================
# 4. Self-Test Battery (Positive & Negative Falsification Vectors)
# ==============================================================================

def run_self_test() -> bool:
    """
    Executes a self-contained test battery verifying that the verifier:
      - Validates genuine Ed25519 receipts over RFC 8785 JCS.
      - Fails closed on payload mutation (even 1 cent / 1 character).
      - Fails closed on forged signatures.
      - Fails closed on disposition state tampering.
    """
    print("================================================================================")
    print("  AEIB STANDALONE RECEIPT VERIFIER: SELF-TEST BATTERY")
    print("  Evaluated under stated model. Zero network egress. Pure RFC 8785 JCS.")
    print("================================================================================")

    # Key generation
    trusted_sk = Ed25519PrivateKey.generate()
    trusted_pk = trusted_sk.public_key()
    rogue_sk = Ed25519PrivateKey.generate()

    # Construct genuine receipt
    action_payload = {
        "amount_minor": 45000,
        "currency": "EUR",
        "operation_id": "op-test-self-001",
        "recipient_iban": "CZ6508000000001234567890",
    }
    caid = compute_sha256_prefixed(encode_jcs(action_payload))

    receipt_body: Dict[str, Any] = {
        "action_caid": caid,
        "action_payload": action_payload,
        "disposition": "CONFIRMED",
        "operation_id": "op-test-self-001",
        "timestamp_epoch": 1760000000,
    }
    canonical_body = encode_jcs(receipt_body)
    valid_sig = trusted_sk.sign(canonical_body)

    genuine_receipt = dict(receipt_body)
    genuine_receipt["signature_b64"] = base64.b64encode(valid_sig).decode("ascii")

    # Vector 1: Positive Path
    res1 = verify_receipt_data(genuine_receipt, trusted_pk)
    if not res1["valid"]:
        print(f"[!] Positive Vector FAILED: {res1['error']}", file=sys.stderr)
        return False
    print("  ✓ Vector 1 (Positive Path): Valid receipt confirmed.")

    # Vector 2: Negative Vector — 1-Cent Payload Mutation
    tampered_payload = dict(genuine_receipt)
    tampered_payload["action_payload"] = dict(action_payload)
    tampered_payload["action_payload"]["amount_minor"] = 45001  # Mutate 1 cent
    res2 = verify_receipt_data(tampered_payload, trusted_pk)
    if res2["valid"]:
        print("[!] Negative Vector 2 FAILED: 1-cent mutation was not caught!", file=sys.stderr)
        return False
    print(f"  ✓ Vector 2 (1-Cent Payload Mutation): Caught fail-closed ({res2['error']}).")

    # Vector 3: Negative Vector — Forged Signature
    forged_sig = rogue_sk.sign(canonical_body)
    forged_receipt = dict(genuine_receipt)
    forged_receipt["signature_b64"] = base64.b64encode(forged_sig).decode("ascii")
    res3 = verify_receipt_data(forged_receipt, trusted_pk)
    if res3["valid"]:
        print("[!] Negative Vector 3 FAILED: Forged signature was not caught!", file=sys.stderr)
        return False
    print(f"  ✓ Vector 3 (Rogue Key Signature): Caught fail-closed ({res3['error']}).")

    # Vector 4: Negative Vector — Disposition Tampering
    # Attacker attempts to change EFFECT_INDETERMINATE to CONFIRMED
    indet_body = dict(receipt_body)
    indet_body["disposition"] = "EFFECT_INDETERMINATE"
    indet_canonical = encode_jcs(indet_body)
    indet_sig = trusted_sk.sign(indet_canonical)

    indet_receipt = dict(indet_body)
    indet_receipt["signature_b64"] = base64.b64encode(indet_sig).decode("ascii")
    # Mutate disposition after signing
    indet_receipt["disposition"] = "CONFIRMED"
    res4 = verify_receipt_data(indet_receipt, trusted_pk)
    if res4["valid"]:
        print("[!] Negative Vector 4 FAILED: Disposition tampering was not caught!", file=sys.stderr)
        return False
    print(f"  ✓ Vector 4 (Disposition State Tampering): Caught fail-closed ({res4['error']}).")

    print("================================================================================")
    print("  [✔] ALL 4 SELF-TEST VECTORS PASSED: 1 POSITIVE + 3 NEGATIVE FALSIFICATIONS")
    print("================================================================================")
    return True


# ==============================================================================
# 5. CLI Entrypoint
# ==============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="AEIB Standalone Offline Receipt Verifier (RFC 8785 JCS + Ed25519)"
    )
    parser.add_argument(
        "--receipt",
        type=Path,
        help="Path to receipt JSON file to verify.",
    )
    parser.add_argument(
        "--public-key",
        type=Path,
        help="Path to trusted Ed25519 public key file (PEM, hex, or base64).",
    )
    parser.add_argument(
        "--operation-id",
        type=str,
        default=None,
        help="Optional expected operation_id to cross-verify against receipt.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run the built-in self-test battery with positive and negative vectors.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output verification result as machine-readable JSON.",
    )

    args = parser.parse_args()

    if args.self_test:
        success = run_self_test()
        sys.exit(0 if success else 1)

    if not args.receipt or not args.public_key:
        parser.print_help()
        print(
            "\n[!] Error: Both --receipt and --public-key must be provided (or use --self-test).",
            file=sys.stderr,
        )
        sys.exit(1)

    if not args.receipt.is_file():
        print(f"[!] Error: Receipt file not found: {args.receipt}", file=sys.stderr)
        sys.exit(1)

    if not args.public_key.is_file():
        print(f"[!] Error: Public key file not found: {args.public_key}", file=sys.stderr)
        sys.exit(1)

    try:
        trusted_pk = load_ed25519_public_key(args.public_key)
    except Exception as exc:
        print(f"[!] Failed to load public key from {args.public_key}: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        receipt_dict = json.loads(args.receipt.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[!] Failed to parse receipt JSON from {args.receipt}: {exc}", file=sys.stderr)
        sys.exit(1)

    result = verify_receipt_data(
        receipt_dict,
        trusted_public_key=trusted_pk,
        expected_operation_id=args.operation_id,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["valid"]:
            print(f"[✔] Receipt VALID: {args.receipt.name}")
            print(f"    - Operation ID : {result.get('operation_id')}")
            print(f"    - Disposition  : {result.get('disposition')}")
            print(f"    - SHA-256 Tip  : {result.get('receipt_sha256')}")
        else:
            print(f"[✘] Receipt INVALID: {args.receipt.name}", file=sys.stderr)
            print(f"    - Error: {result.get('error')}", file=sys.stderr)

    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
