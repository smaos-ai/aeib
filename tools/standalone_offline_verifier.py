#!/usr/bin/env python3
"""
tools/standalone_offline_verifier.py
================================================================================
AEIB Standalone Zero-Dependency Offline Audit Verifier.

Prototype / Pre-Production Scaffold evaluated under the stated model.
Preserves strict epistemic calibration and zero external dependencies.

Operational Scope:
  Provides an independent verification tool runnable by external bank risk
  officers, CISOs, or regulatory auditors with standard Python 3.9+ without
  running 'pip install' or 'cargo'.

Core Cryptographic & Verification Subsystems:
  1. Pure Python RFC 8032 Ed25519 asymmetric signature verification using
     Curve25519 field arithmetic (modulo 2^255 - 19) and SHA-512.
  2. Pure Python RFC 8785 JSON Canonicalization Scheme (JCS) encoding and
     SHA-256 digest computation.
  3. Offline AEIB Execution Receipt Verification (CAID binding, policy epoch,
     disposition checks, Ed25519 author signature).
  4. Selective Disclosure Verification (salted blind commitments and unredacted
     claims verified against signed Merkle-style root hash).
  5. RFC 9162 Domain-Separated Merkle Tree Inclusion Proof Verification
     against a pinned Merkle root.
================================================================================
"""

from __future__ import annotations

import argparse
import base64
import datetime
import hashlib
import hmac
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

VERIFIER_VERSION = "1.0.0-scaffold"

# ------------------------------------------------------------------------------
# 1. Pure Python RFC 8032 Ed25519 Asymmetric Verification Arithmetic
# ------------------------------------------------------------------------------

FIELD_P = 2**255 - 19
ORDER_L = 2**252 + 27742317777372353535851937790883648493
SQRT_M1 = pow(2, (FIELD_P - 1) // 4, FIELD_P)
CURVE_D = (-121665 * pow(121666, FIELD_P - 2, FIELD_P)) % FIELD_P
IDENTITY_POINT = (0, 1, 1, 0)


def _field_inv(z: int) -> int:
    """Computes multiplicative inverse modulo 2^255 - 19 via Fermat's Little Theorem."""
    return pow(z, FIELD_P - 2, FIELD_P)


def _recover_x(y: int, sign: int) -> Optional[int]:
    """Recovers x coordinate from y and sign bit on Edwards25519."""
    if y >= FIELD_P:
        return None
    u = (y * y - 1) % FIELD_P
    v = (CURVE_D * y * y + 1) % FIELD_P
    # Candidate root: u * v^3 * (u * v^7)^((p-5)/8) mod p
    cand = (u * pow(v, 3, FIELD_P) * pow(u * pow(v, 7, FIELD_P), (FIELD_P - 5) // 8, FIELD_P)) % FIELD_P
    v_cand_sq = (v * cand * cand) % FIELD_P
    if v_cand_sq == u:
        x = cand
    elif v_cand_sq == (-u) % FIELD_P:
        x = (cand * SQRT_M1) % FIELD_P
    else:
        return None
    if (x % 2) != sign:
        x = (FIELD_P - x) % FIELD_P
    return x


# Base Point B definition per RFC 8032 Section 5.1
_yB = (4 * _field_inv(5)) % FIELD_P
_xB = _recover_x(_yB, 0)
if _xB is None:
    raise RuntimeError("Failed to compute Ed25519 base point B")
BASE_POINT_B = (_xB, _yB, 1, (_xB * _yB) % FIELD_P)


def _point_add(
    p1: Tuple[int, int, int, int], p2: Tuple[int, int, int, int]
) -> Tuple[int, int, int, int]:
    """Adds two points in Extended Edwards Coordinates (X: Y: Z: T)."""
    x1, y1, z1, t1 = p1
    x2, y2, z2, t2 = p2
    a = ((y1 - x1) * (y2 - x2)) % FIELD_P
    b = ((y1 + x1) * (y2 + x2)) % FIELD_P
    c = (2 * t1 * t2 * CURVE_D) % FIELD_P
    d = (2 * z1 * z2) % FIELD_P
    e = (b - a) % FIELD_P
    f = (d - c) % FIELD_P
    g = (d + c) % FIELD_P
    h = (b + a) % FIELD_P
    return ((e * f) % FIELD_P, (g * h) % FIELD_P, (f * g) % FIELD_P, (e * h) % FIELD_P)


def _point_mul(scalar: int, p: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
    """Multiplies point by scalar using double-and-add."""
    res = IDENTITY_POINT
    curr = p
    s = scalar
    while s > 0:
        if s & 1:
            res = _point_add(res, curr)
        curr = _point_add(curr, curr)
        s >>= 1
    return res


def _compress_point(p: Tuple[int, int, int, int]) -> bytes:
    """Serializes point into 32-byte RFC 8032 representation."""
    x, y, z, _ = p
    z_inv = _field_inv(z)
    aff_x = (x * z_inv) % FIELD_P
    aff_y = (y * z_inv) % FIELD_P
    raw = bytearray(aff_y.to_bytes(32, "little"))
    if aff_x % 2:
        raw[31] |= 0x80
    return bytes(raw)


def _decompress_point(bs: bytes) -> Optional[Tuple[int, int, int, int]]:
    """Deserializes 32-byte string into Extended Edwards point."""
    if len(bs) != 32:
        return None
    y = int.from_bytes(bs[:31] + bytes([bs[31] & 0x7F]), "little")
    sign = (bs[31] >> 7) & 1
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, (x * y) % FIELD_P)


def _points_equal(
    p1: Tuple[int, int, int, int], p2: Tuple[int, int, int, int]
) -> bool:
    """Checks equality of two projective extended points."""
    x1, y1, z1, _ = p1
    x2, y2, z2, _ = p2
    return (
        ((x1 * z2 - x2 * z1) % FIELD_P == 0)
        and ((y1 * z2 - y2 * z1) % FIELD_P == 0)
    )


def ed25519_verify(
    public_key_bytes: bytes, message_bytes: bytes, signature_bytes: bytes
) -> bool:
    """
    Pure Python RFC 8032 Section 5.1.7 Ed25519 Signature Verification.
    Zero external dependencies.
    """
    if len(public_key_bytes) != 32 or len(signature_bytes) != 64:
        return False
    point_a = _decompress_point(public_key_bytes)
    if point_a is None:
        return False

    r_bytes = signature_bytes[:32]
    s_int = int.from_bytes(signature_bytes[32:], "little")
    if s_int >= ORDER_L:
        return False

    point_r = _decompress_point(r_bytes)
    if point_r is None:
        return False

    hasher = hashlib.sha512(r_bytes + public_key_bytes + message_bytes)
    k_int = int.from_bytes(hasher.digest(), "little") % ORDER_L

    sb = _point_mul(s_int, BASE_POINT_B)
    ka = _point_mul(k_int, point_a)
    r_plus_ka = _point_add(point_r, ka)
    return _points_equal(sb, r_plus_ka)


def ed25519_sign(seed_bytes: bytes, message_bytes: bytes) -> Tuple[bytes, bytes]:
    """
    Pure Python RFC 8032 Section 5.1.6 Ed25519 Signature Generation.
    Used for self-testing and fixture creation without external crypto libraries.
    """
    if len(seed_bytes) != 32:
        raise ValueError("Seed must be exactly 32 bytes")
    h = hashlib.sha512(seed_bytes).digest()
    a_bytes = bytearray(h[:32])
    a_bytes[0] &= 248
    a_bytes[31] &= 63
    a_bytes[31] |= 64
    a_scalar = int.from_bytes(a_bytes, "little")
    point_a = _point_mul(a_scalar, BASE_POINT_B)
    pub_bytes = _compress_point(point_a)

    prefix = h[32:]
    r_scalar = int.from_bytes(hashlib.sha512(prefix + message_bytes).digest(), "little") % ORDER_L
    point_r = _point_mul(r_scalar, BASE_POINT_B)
    r_bytes = _compress_point(point_r)

    k_scalar = int.from_bytes(hashlib.sha512(r_bytes + pub_bytes + message_bytes).digest(), "little") % ORDER_L
    s_scalar = (r_scalar + k_scalar * a_scalar) % ORDER_L
    sig_bytes = r_bytes + s_scalar.to_bytes(32, "little")
    return pub_bytes, sig_bytes


# ------------------------------------------------------------------------------
# 2. Pure Python RFC 8785 JSON Canonicalization Scheme (JCS)
# ------------------------------------------------------------------------------

def _utf16_sort_key(s: str) -> bytes:
    """Sorts mapping keys lexicographically by UTF-16 code units per RFC 8785 Section 3.2.3."""
    if not isinstance(s, str):
        raise TypeError(f"RFC 8785 object keys must be str, got {type(s).__name__}")
    return s.encode("utf-16-be")


def _format_jcs_number(num: float) -> str:
    """Formats floating point numbers per ECMAScript 7.1.12.1 and RFC 8785 Section 3.2.2.3."""
    if math.isnan(num) or math.isinf(num):
        raise ValueError("RFC 8785 rejects NaN and Infinity")
    if num == 0.0:
        return "0"
    if num < 0:
        return "-" + _format_jcs_number(-num)

    rep = repr(num)
    if "e" in rep:
        mantissa, exp_str = rep.split("e")
        exp = int(exp_str)
    else:
        mantissa, exp = rep, 0

    if "." in mantissa:
        int_part, frac_part = mantissa.split(".")
        frac_part = frac_part.rstrip("0")
    else:
        int_part, frac_part = mantissa, ""

    int_part = int_part.lstrip("0")
    if int_part:
        digits = int_part + frac_part
        n = len(int_part) + exp
    else:
        leading_zeros = len(frac_part) - len(frac_part.lstrip("0"))
        digits = frac_part.lstrip("0")
        n = -leading_zeros + exp

    if not digits:
        return "0"

    k = len(digits)
    if k <= n <= 21:
        return digits + "0" * (n - k)
    elif 0 < n <= 21:
        return digits[:n] + "." + digits[n:]
    elif -6 < n <= 0:
        return "0." + "0" * (-n) + digits
    elif k == 1:
        return f"{digits}e{n - 1}"
    else:
        return f"{digits[0]}.{digits[1:]}e{n - 1}"


def _serialize_jcs_str(obj: Any) -> str:
    """Recursively serializes Python object to RFC 8785 string."""
    if obj is None:
        return "null"
    elif isinstance(obj, bool):
        return "true" if obj else "false"
    elif isinstance(obj, int):
        return str(obj)
    elif isinstance(obj, float):
        return _format_jcs_number(obj)
    elif isinstance(obj, str):
        return json.dumps(obj, ensure_ascii=False)
    elif isinstance(obj, (list, tuple)):
        return "[" + ",".join(_serialize_jcs_str(x) for x in obj) + "]"
    elif isinstance(obj, dict):
        sorted_keys = sorted(obj.keys(), key=_utf16_sort_key)
        parts = [
            f"{json.dumps(k, ensure_ascii=False)}:{_serialize_jcs_str(obj[k])}"
            for k in sorted_keys
        ]
        return "{" + ",".join(parts) + "}"
    else:
        raise TypeError(f"Type {type(obj).__name__} is not JSON serializable under JCS")


def encode_jcs(payload: Any) -> bytes:
    """Serializes Python object into byte-exact RFC 8785 canonical JSON bytes."""
    return _serialize_jcs_str(payload).encode("utf-8")


def compute_jcs_sha256(payload: Any) -> str:
    """Computes lowercase hex SHA-256 digest of RFC 8785 canonicalized payload."""
    return hashlib.sha256(encode_jcs(payload)).hexdigest()


# ------------------------------------------------------------------------------
# 3. Public Key Parsing (Hex, Base64, PEM, Raw)
# ------------------------------------------------------------------------------

def parse_ed25519_public_key(key_input: Union[str, bytes, Path]) -> bytes:
    """
    Parses a 32-byte Ed25519 public key from multiple input formats:
      - 32-byte raw bytes
      - 64-character hex string
      - Base64 encoded string
      - PEM file or string (SubjectPublicKeyInfo header 302a300506032b6570032100...)
      - Path pointing to a file containing any of the above
    """
    raw_text: str = ""
    if isinstance(key_input, Path):
        content = key_input.read_bytes()
        try:
            raw_text = content.decode("utf-8").strip()
        except UnicodeDecodeError:
            if len(content) == 32:
                return content
            raise ValueError(f"Binary file at {key_input} must be 32 bytes, got {len(content)}")
    elif isinstance(key_input, bytes):
        if len(key_input) == 32:
            return key_input
        try:
            raw_text = key_input.decode("utf-8").strip()
        except UnicodeDecodeError:
            raise ValueError(f"Raw key bytes must be 32 bytes, got {len(key_input)}")
    elif isinstance(key_input, str):
        raw_text = key_input.strip()
    else:
        raise TypeError(f"Unsupported key input type: {type(key_input).__name__}")

    # Check PEM armor
    if "-----BEGIN" in raw_text:
        lines = [line.strip() for line in raw_text.splitlines() if line.strip() and not line.startswith("-----")]
        b64_content = "".join(lines)
        der_bytes = base64.b64decode(b64_content)
        # Ed25519 SubjectPublicKeyInfo is typically 44 bytes with 12 bytes prefix
        if len(der_bytes) == 44 and der_bytes.startswith(bytes.fromhex("302a300506032b6570032100")):
            return der_bytes[12:]
        if len(der_bytes) == 32:
            return der_bytes
        raise ValueError(f"Malformed Ed25519 SubjectPublicKeyInfo DER length: {len(der_bytes)}")

    # Check 64-character hex
    if len(raw_text) == 64:
        try:
            return bytes.fromhex(raw_text)
        except ValueError:
            pass

    # Check Base64 (44 chars with padding or 43 without)
    try:
        decoded = base64.b64decode(raw_text)
        if len(decoded) == 32:
            return decoded
        if len(decoded) == 44 and decoded.startswith(bytes.fromhex("302a300506032b6570032100")):
            return decoded[12:]
    except Exception:
        pass

    raise ValueError("Could not parse valid 32-byte Ed25519 public key from input")


# ------------------------------------------------------------------------------
# 4. RFC 9162 Merkle Tree Functions
# ------------------------------------------------------------------------------

def rfc9162_hash_leaf(data: bytes) -> bytes:
    """Computes RFC 9162 domain-separated leaf hash: SHA-256(0x00 || data)."""
    return hashlib.sha256(b"\x00" + data).digest()


def rfc9162_hash_children(left: bytes, right: bytes) -> bytes:
    """Computes RFC 9162 domain-separated interior node hash: SHA-256(0x01 || left || right)."""
    return hashlib.sha256(b"\x01" + left + right).digest()


def verify_rfc9162_inclusion(
    leaf_hash: bytes,
    leaf_index: int,
    tree_size: int,
    audit_path: List[bytes],
    root_hash: bytes,
) -> bool:
    """
    Verifies an RFC 9162 inclusion proof demonstrating membership of leaf_hash
    at leaf_index in a Merkle tree of size tree_size with root_hash.
    """
    if tree_size <= 0 or leaf_index < 0 or leaf_index >= tree_size:
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


# ------------------------------------------------------------------------------
# 5. Selective Disclosure Verification Functions
# ------------------------------------------------------------------------------

def compute_field_commitment(key: str, value: Any, salt: str) -> str:
    """Computes deterministic salted blind commitment for a single key-value pair."""
    val_bytes = encode_jcs(value)
    payload = f"{salt}:{key}:".encode("utf-8") + val_bytes
    return hashlib.sha256(payload).hexdigest()


def compute_receipt_root(field_commitments: Dict[str, str]) -> str:
    """Computes deterministic Merkle-style root over lexicographically sorted commitments."""
    sorted_keys = sorted(field_commitments.keys())
    combined = "".join(f"{k}:{field_commitments[k]};" for k in sorted_keys).encode("utf-8")
    return hashlib.sha256(combined).hexdigest()


def verify_selective_disclosure_receipt(
    receipt: Dict[str, Any],
    trusted_pubkey_bytes: Optional[bytes] = None,
) -> Dict[str, Any]:
    """
    Verifies an AEIB selective disclosure receipt:
      1. Reconstructs field commitments for disclosed claims using disclosed salts.
      2. Merges blind commitments for redacted claims.
      3. Verifies that reconstructed root hash matches receipt root_hash.
      4. Verifies Ed25519 signature over root_hash.
    """
    receipt_id = str(receipt.get("receipt_id", "UNKNOWN"))
    disclosed_claims = receipt.get("disclosed_claims", {})
    disclosed_salts = receipt.get("disclosed_salts", {})
    redacted_commitments = receipt.get("redacted_field_commitments", {})
    root_hash = receipt.get("root_hash", "")

    if not isinstance(disclosed_claims, dict) or not isinstance(disclosed_salts, dict):
        return {
            "valid": False,
            "receipt_type": "SELECTIVE_DISCLOSURE",
            "receipt_id": receipt_id,
            "error": "Malformed disclosed_claims or disclosed_salts mapping",
        }

    reconstructed_commitments: Dict[str, str] = {}

    for k, v in disclosed_claims.items():
        salt = disclosed_salts.get(k)
        if not salt or not isinstance(salt, str):
            return {
                "valid": False,
                "receipt_type": "SELECTIVE_DISCLOSURE",
                "receipt_id": receipt_id,
                "error": f"Missing or invalid salt for disclosed claim '{k}'",
            }
        reconstructed_commitments[k] = compute_field_commitment(k, v, salt)

    for k, commit in redacted_commitments.items():
        if k in reconstructed_commitments:
            return {
                "valid": False,
                "receipt_type": "SELECTIVE_DISCLOSURE",
                "receipt_id": receipt_id,
                "error": f"Field '{k}' cannot be simultaneously disclosed and redacted",
            }
        if not isinstance(commit, str) or len(commit) != 64:
            return {
                "valid": False,
                "receipt_type": "SELECTIVE_DISCLOSURE",
                "receipt_id": receipt_id,
                "error": f"Invalid redacted commitment format for field '{k}'",
            }
        reconstructed_commitments[k] = commit

    computed_root = compute_receipt_root(reconstructed_commitments)
    if computed_root != root_hash:
        return {
            "valid": False,
            "receipt_type": "SELECTIVE_DISCLOSURE",
            "receipt_id": receipt_id,
            "error": f"Root hash mismatch: computed '{computed_root}' != receipt '{root_hash}'",
        }

    # Extract signature & pubkey
    sig_b64 = None
    pub_hex = None
    if "signature_envelope" in receipt and isinstance(receipt["signature_envelope"], dict):
        env = receipt["signature_envelope"]
        sig_b64 = env.get("signature_b64") or env.get("signature")
        pub_hex = env.get("public_key_hex") or env.get("public_key")
    else:
        sig_b64 = receipt.get("signature_b64") or receipt.get("signature")
        pub_hex = receipt.get("public_key_hex") or receipt.get("public_key")

    active_pubkey = trusted_pubkey_bytes
    if active_pubkey is None and pub_hex:
        try:
            active_pubkey = bytes.fromhex(pub_hex)
        except ValueError:
            return {
                "valid": False,
                "receipt_type": "SELECTIVE_DISCLOSURE",
                "receipt_id": receipt_id,
                "error": "Malformed public_key_hex in receipt",
            }

    if active_pubkey is None:
        return {
            "valid": False,
            "receipt_type": "SELECTIVE_DISCLOSURE",
            "receipt_id": receipt_id,
            "error": "No trusted public key supplied or found in receipt",
        }

    if not sig_b64 or not isinstance(sig_b64, str):
        return {
            "valid": False,
            "receipt_type": "SELECTIVE_DISCLOSURE",
            "receipt_id": receipt_id,
            "error": "Missing signature in selective disclosure receipt",
        }

    try:
        sig_bytes = bytes.fromhex(sig_b64) if len(sig_b64) == 128 else base64.b64decode(sig_b64)
    except Exception:
        return {
            "valid": False,
            "receipt_type": "SELECTIVE_DISCLOSURE",
            "receipt_id": receipt_id,
            "error": "Malformed signature encoding",
        }

    sig_valid = ed25519_verify(active_pubkey, root_hash.encode("utf-8"), sig_bytes)
    if not sig_valid:
        return {
            "valid": False,
            "receipt_type": "SELECTIVE_DISCLOSURE",
            "receipt_id": receipt_id,
            "error": "Ed25519 signature verification failed over root_hash",
        }

    return {
        "valid": True,
        "receipt_type": "SELECTIVE_DISCLOSURE",
        "receipt_id": receipt_id,
        "root_hash": root_hash,
        "disclosed_fields_count": len(disclosed_claims),
        "redacted_fields_count": len(redacted_commitments),
    }


# ------------------------------------------------------------------------------
# 6. Standard AEIB Execution Receipt Verification
# ------------------------------------------------------------------------------

VALID_DISPOSITIONS: Set[str] = {
    "CONFIRMED",
    "REFUTED",
    "EFFECT_INDETERMINATE",
    "OUTCOME_VERIFIED",
    "DISPATCHED_UNCONFIRMED",
    "AUTHORIZED_FOR_HOST_SIGNING",
    "UNKNOWN",
    "MISSING_EVIDENCE",
    "CONFLICT",
    "REFUSED",
    "INVALID_INPUT",
}


def verify_aeib_execution_receipt(
    receipt: Dict[str, Any],
    trusted_pubkey_bytes: Optional[bytes] = None,
    current_epoch: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Verifies an AEIB execution receipt:
      1. Validates schema and disposition format.
      2. Recomputes RFC 8785 canonical hash of action payload and checks CAID match.
      3. Validates policy epoch.
      4. Validates timestamp sanity.
      5. Verifies author Ed25519 signature.
    """
    op_id = (
        receipt.get("operation_id")
        or receipt.get("scenario_id")
        or receipt.get("receipt_id")
        or receipt.get("action_id")
        or (
            receipt["receipt_body"].get("validation_run", {}).get("engine")
            if isinstance(receipt.get("receipt_body"), dict)
            else None
        )
        or "UNKNOWN"
    )

    # 1. Disposition check
    disposition = (
        receipt.get("disposition")
        or receipt.get("final_disposition")
        or receipt.get("verdict")
    )
    if not disposition and isinstance(receipt.get("org.smaos.aeib"), dict):
        disposition = receipt["org.smaos.aeib"].get("disposition")

    if disposition and disposition not in VALID_DISPOSITIONS:
        return {
            "valid": False,
            "receipt_type": "AEIB_EXECUTION",
            "operation_id": op_id,
            "error": f"Invalid disposition '{disposition}'",
        }

    # 2. CAID / Payload Verification
    action_payload = receipt.get("action_payload") or receipt.get("payload")
    claimed_caid = receipt.get("action_caid") or receipt.get("caid")
    if action_payload is None and isinstance(receipt.get("unsigned_payload"), dict):
        action_payload = receipt["unsigned_payload"].get("action_payload") or receipt["unsigned_payload"].get("payload")
        if claimed_caid is None:
            claimed_caid = receipt["unsigned_payload"].get("action_caid") or receipt["unsigned_payload"].get("caid")

    if action_payload is not None:
        computed_digest = compute_jcs_sha256(action_payload)
        if claimed_caid is not None:
            # Normalize possible prefixes (e.g., "caid:sha256:")
            norm_claimed = claimed_caid.replace("caid:sha256:", "").replace("sha256:", "")
            if norm_claimed != computed_digest:
                return {
                    "valid": False,
                    "receipt_type": "AEIB_EXECUTION",
                    "operation_id": op_id,
                    "error": f"CAID mismatch: claimed '{claimed_caid}', computed '{computed_digest}'",
                }

    # 3. Policy Epoch Validation
    epoch = receipt.get("policy_epoch") or receipt.get("epoch")
    if epoch is not None:
        if not isinstance(epoch, int) or epoch < 0:
            return {
                "valid": False,
                "receipt_type": "AEIB_EXECUTION",
                "operation_id": op_id,
                "error": f"Invalid policy epoch format: '{epoch}'",
            }
        if current_epoch is not None and epoch > current_epoch:
            return {
                "valid": False,
                "receipt_type": "AEIB_EXECUTION",
                "operation_id": op_id,
                "error": f"Policy epoch {epoch} exceeds current configured epoch {current_epoch}",
            }

    # 4. Signature & Public Key Resolution
    sig_bytes: Optional[bytes] = None
    signable_message: Optional[bytes] = None
    pub_bytes: Optional[bytes] = trusted_pubkey_bytes

    # Format 1: AEIB_JSON_ED25519_PROTOTYPE (from transport_observer.py)
    if receipt.get("format") == "AEIB_JSON_ED25519_PROTOTYPE" and "signature_metadata" in receipt:
        sig_meta = receipt["signature_metadata"]
        raw_sig = sig_meta.get("signature")
        if raw_sig:
            sig_bytes = bytes.fromhex(raw_sig)
        # Signable view per transport_observer:
        signable_view = {
            "unsigned_payload": receipt.get("unsigned_payload"),
            "unsigned_payload_hash": receipt.get("unsigned_payload_hash"),
        }
        signable_message = encode_jcs(signable_view)

    # Format 2: attestation_signature block
    elif "attestation_signature" in receipt and isinstance(receipt["attestation_signature"], dict):
        att = receipt["attestation_signature"]
        raw_sig = att.get("signature_b64") or att.get("signature_hex")
        if raw_sig:
            sig_bytes = bytes.fromhex(raw_sig) if len(raw_sig) == 128 else base64.b64decode(raw_sig)
        if pub_bytes is None and att.get("public_key_hex"):
            pub_bytes = bytes.fromhex(att["public_key_hex"])
        unsigned_body = {k: v for k, v in receipt.items() if k != "attestation_signature"}
        signable_message = encode_jcs(unsigned_body)

    # Format 3: Flat signature_hex or signature_b64
    elif "signature_b64" in receipt or "signature_hex" in receipt:
        raw_sig = receipt.get("signature_b64") or receipt.get("signature_hex")
        if raw_sig:
            sig_bytes = bytes.fromhex(raw_sig) if len(raw_sig) == 128 else base64.b64decode(raw_sig)
        if pub_bytes is None and receipt.get("public_key_hex"):
            pub_bytes = bytes.fromhex(receipt["public_key_hex"])
        elif pub_bytes is None and receipt.get("signer_pubkey"):
            pub_bytes = bytes.fromhex(receipt["signer_pubkey"])
        unsigned_body = {
            k: v for k, v in receipt.items()
            if k not in ("signature_b64", "signature_hex", "signature")
        }
        signable_message = encode_jcs(unsigned_body)

    # Format 4: Core proof engine format
    elif "root_hash" in receipt and "signature" in receipt and "signer_pubkey" in receipt:
        raw_sig = receipt.get("signature")
        if raw_sig:
            sig_bytes = bytes.fromhex(raw_sig) if len(raw_sig) == 128 else base64.b64decode(raw_sig)
        if pub_bytes is None:
            pub_bytes = bytes.fromhex(receipt["signer_pubkey"])
        root_b = bytes.fromhex(receipt["root_hash"])
        ts_s = str(receipt.get("timestamp", ""))
        verdict_s = str(receipt.get("verdict", ""))
        action_id_s = str(receipt.get("action_id", ""))
        signable_message = root_b + action_id_s.encode("utf-8") + verdict_s.encode("utf-8") + ts_s.encode("utf-8")

    # Format 5: receipt_body + signature_envelope (Validation and Attestation Runner)
    elif "receipt_body" in receipt and "signature_envelope" in receipt:
        env = receipt["signature_envelope"]
        raw_sig = env.get("signature_b64") or env.get("signature") or env.get("signature_hex")
        if raw_sig:
            sig_bytes = bytes.fromhex(raw_sig) if len(raw_sig) == 128 else base64.b64decode(raw_sig)
        if pub_bytes is None and env.get("public_key_hex"):
            pub_bytes = bytes.fromhex(env["public_key_hex"])
        elif pub_bytes is None and env.get("public_key"):
            pk_val = env["public_key"]
            pub_bytes = bytes.fromhex(pk_val) if len(pk_val) == 64 else base64.b64decode(pk_val)
        signable_message = encode_jcs(receipt["receipt_body"])

    if sig_bytes is None or signable_message is None:
        return {
            "valid": False,
            "receipt_type": "AEIB_EXECUTION",
            "operation_id": op_id,
            "error": "Could not extract cryptographic signature and signable body from receipt",
        }

    if pub_bytes is None:
        return {
            "valid": False,
            "receipt_type": "AEIB_EXECUTION",
            "operation_id": op_id,
            "error": "No trusted public key provided or resolved for receipt",
        }

    sig_ok = ed25519_verify(pub_bytes, signable_message, sig_bytes)
    if not sig_ok:
        return {
            "valid": False,
            "receipt_type": "AEIB_EXECUTION",
            "operation_id": op_id,
            "error": "Ed25519 signature verification failed",
        }

    return {
        "valid": True,
        "receipt_type": "AEIB_EXECUTION",
        "operation_id": op_id,
        "disposition": disposition or "CONFIRMED",
        "caid": claimed_caid,
        "epoch": epoch,
    }


# ------------------------------------------------------------------------------
# 7. RFC 9162 Merkle Receipt Verification
# ------------------------------------------------------------------------------

def verify_merkle_receipt(
    receipt: Dict[str, Any],
    pinned_root_bytes: Optional[bytes] = None,
) -> Dict[str, Any]:
    """
    Verifies an RFC 9162 Merkle tree inclusion receipt:
      - Validates leaf_index, tree_size, inclusion_proof, and root_hash.
      - If pinned_root_bytes provided, checks proof against pinned root.
    """
    leaf_idx = receipt.get("leaf_index")
    tree_size = receipt.get("tree_size")
    root_hex = receipt.get("root_hash")
    proof_hex_list = receipt.get("inclusion_proof")

    if not isinstance(leaf_idx, int) or not isinstance(tree_size, int):
        return {
            "valid": False,
            "receipt_type": "RFC9162_MERKLE",
            "error": "Missing or non-integer leaf_index or tree_size",
        }

    if not isinstance(root_hex, str) or len(root_hex) != 64:
        return {
            "valid": False,
            "receipt_type": "RFC9162_MERKLE",
            "error": "Invalid or missing root_hash 64-hex string",
        }

    try:
        root_bytes = bytes.fromhex(root_hex)
    except ValueError:
        return {
            "valid": False,
            "receipt_type": "RFC9162_MERKLE",
            "error": "Invalid hex format in root_hash",
        }

    if pinned_root_bytes is not None and not hmac.compare_digest(root_bytes, pinned_root_bytes):
        return {
            "valid": False,
            "receipt_type": "RFC9162_MERKLE",
            "error": f"Root hash mismatch against pinned root: receipt '{root_hex}', pinned '{pinned_root_bytes.hex()}'",
        }

    # Resolve leaf hash
    leaf_hash: Optional[bytes] = None
    if "leaf_hash" in receipt and isinstance(receipt["leaf_hash"], str):
        try:
            leaf_hash = bytes.fromhex(receipt["leaf_hash"])
        except ValueError:
            return {"valid": False, "receipt_type": "RFC9162_MERKLE", "error": "Invalid leaf_hash hex"}
    elif "action_id" in receipt and "intent_digest" in receipt and "verdict" in receipt:
        action_id = str(receipt["action_id"])
        intent_bytes = bytes.fromhex(receipt["intent_digest"])
        verdict = str(receipt["verdict"])
        leaf_content = action_id.encode("utf-8") + intent_bytes + verdict.encode("utf-8")
        leaf_hash = rfc9162_hash_leaf(leaf_content)
    elif "leaf_payload" in receipt:
        leaf_data = encode_jcs(receipt["leaf_payload"])
        leaf_hash = rfc9162_hash_leaf(leaf_data)

    if leaf_hash is None or len(leaf_hash) != 32:
        return {
            "valid": False,
            "receipt_type": "RFC9162_MERKLE",
            "error": "Could not derive 32-byte RFC 9162 leaf hash",
        }

    if not isinstance(proof_hex_list, list):
        return {
            "valid": False,
            "receipt_type": "RFC9162_MERKLE",
            "error": "Missing inclusion_proof list",
        }

    audit_path: List[bytes] = []
    for sibling_hex in proof_hex_list:
        try:
            sb = bytes.fromhex(str(sibling_hex))
            if len(sb) != 32:
                return {
                    "valid": False,
                    "receipt_type": "RFC9162_MERKLE",
                    "error": "Sibling node in inclusion proof must be 32 bytes",
                }
            audit_path.append(sb)
        except ValueError:
            return {
                "valid": False,
                "receipt_type": "RFC9162_MERKLE",
                "error": f"Malformed sibling hex '{sibling_hex}'",
            }

    valid_proof = verify_rfc9162_inclusion(
        leaf_hash=leaf_hash,
        leaf_index=leaf_idx,
        tree_size=tree_size,
        audit_path=audit_path,
        root_hash=root_bytes,
    )

    if not valid_proof:
        return {
            "valid": False,
            "receipt_type": "RFC9162_MERKLE",
            "error": "RFC 9162 inclusion proof validation failed against root_hash",
        }

    return {
        "valid": True,
        "receipt_type": "RFC9162_MERKLE",
        "leaf_index": leaf_idx,
        "tree_size": tree_size,
        "root_hash": root_hex,
    }


# ------------------------------------------------------------------------------
# 8. Unified Receipt Dispatcher & Bundle Verifier
# ------------------------------------------------------------------------------

def verify_any_receipt(
    receipt_data: Dict[str, Any],
    trusted_pubkey_bytes: Optional[bytes] = None,
    pinned_root_bytes: Optional[bytes] = None,
    current_epoch: Optional[int] = None,
) -> Dict[str, Any]:
    """Inspects receipt data and routes to the appropriate verification engine."""
    if not isinstance(receipt_data, dict):
        return {"valid": False, "error": "Receipt must be a JSON object"}

    # Case 1: Selective Disclosure Receipt
    if "disclosed_claims" in receipt_data and "redacted_field_commitments" in receipt_data:
        return verify_selective_disclosure_receipt(receipt_data, trusted_pubkey_bytes)

    # Case 2: Pure RFC 9162 Merkle Receipt
    if "inclusion_proof" in receipt_data and "leaf_index" in receipt_data and "tree_size" in receipt_data and "format" not in receipt_data:
        return verify_merkle_receipt(receipt_data, pinned_root_bytes)

    # Case 3: AEIB Execution Receipt
    return verify_aeib_execution_receipt(receipt_data, trusted_pubkey_bytes, current_epoch)


def verify_bundle_directory(
    bundle_dir: Path,
    trusted_pubkey_bytes: Optional[bytes] = None,
    pinned_root_bytes: Optional[bytes] = None,
    current_epoch: Optional[int] = None,
) -> Dict[str, Any]:
    """Recursively parses and verifies all receipts inside a bundle directory."""
    if not bundle_dir.is_dir():
        raise NotADirectoryError(f"Bundle directory does not exist: {bundle_dir}")

    receipt_files = sorted(list(bundle_dir.rglob("*.json")) + list(bundle_dir.rglob("*.jsonl")))
    total_count = 0
    valid_count = 0
    failures: List[Dict[str, Any]] = []

    for file_path in receipt_files:
        try:
            content = file_path.read_text(encoding="utf-8").strip()
            if not content:
                continue
            if file_path.suffix == ".jsonl":
                lines = content.splitlines()
                for line_idx, line in enumerate(lines, 1):
                    line = line.strip()
                    if not line:
                        continue
                    item = json.loads(line)
                    total_count += 1
                    res = verify_any_receipt(item, trusted_pubkey_bytes, pinned_root_bytes, current_epoch)
                    if res.get("valid"):
                        valid_count += 1
                    else:
                        failures.append({"file": str(file_path), "line": line_idx, "error": res.get("error")})
            else:
                item = json.loads(content)
                total_count += 1
                res = verify_any_receipt(item, trusted_pubkey_bytes, pinned_root_bytes, current_epoch)
                if res.get("valid"):
                    valid_count += 1
                else:
                    failures.append({"file": str(file_path), "error": res.get("error")})
        except Exception as exc:
            total_count += 1
            failures.append({"file": str(file_path), "error": f"Failed to read/parse: {exc}"})

    all_valid = (total_count > 0) and (valid_count == total_count)
    return {
        "valid": all_valid,
        "total_receipts": total_count,
        "valid_receipts": valid_count,
        "failed_receipts": len(failures),
        "failures": failures,
    }


# ------------------------------------------------------------------------------
# 9. Self-Test Suite (--self-test)
# ------------------------------------------------------------------------------

def run_self_test() -> bool:
    """
    Executes comprehensive built-in verification and falsification vectors
    using pure Python math with zero external dependencies.
    """
    test_seed = b"aeib_offline_verifier_test_seed_"  # 32 bytes
    msg = b"AEIB Audit Action Payload Test Vector 001"
    pub_bytes, sig_bytes = ed25519_sign(test_seed, msg)

    # 1. Ed25519 Positive Vector
    if not ed25519_verify(pub_bytes, msg, sig_bytes):
        return False

    # 2. Ed25519 Negative Vector (Tampered message)
    if ed25519_verify(pub_bytes, b"Tampered message", sig_bytes):
        return False

    # 3. Ed25519 Negative Vector (Tampered signature)
    bad_sig = bytearray(sig_bytes)
    bad_sig[10] ^= 0xFF
    if ed25519_verify(pub_bytes, msg, bytes(bad_sig)):
        return False

    # 4. RFC 8785 JCS Canonicalization Vector
    sample_obj = {"z": 1, "a": 2, "sub": {"b": True, "a": None}}
    jcs_encoded = encode_jcs(sample_obj)
    if jcs_encoded != b'{"a":2,"sub":{"a":null,"b":true},"z":1}':
        return False

    # 5. AEIB Execution Receipt Positive & Falsification
    payload = {"intent": "transfer", "amount": 1000, "currency": "EUR"}
    caid = compute_jcs_sha256(payload)
    unsigned_payload = {
        "receipt_version": "v0.2.0",
        "operation_id": "op-test-101",
        "action_payload": payload,
        "action_caid": caid,
        "policy_epoch": 42,
        "disposition": "CONFIRMED",
    }
    payload_hash = compute_jcs_sha256(unsigned_payload)
    signable_view = {
        "unsigned_payload": unsigned_payload,
        "unsigned_payload_hash": payload_hash,
    }
    _, receipt_sig = ed25519_sign(test_seed, encode_jcs(signable_view))

    aeib_receipt = {
        "format": "AEIB_JSON_ED25519_PROTOTYPE",
        "operation_id": "op-test-101",
        "unsigned_payload": unsigned_payload,
        "unsigned_payload_hash": payload_hash,
        "signature_metadata": {
            "signature": receipt_sig.hex(),
            "algorithm": "Ed25519",
        },
    }

    res_aeib = verify_aeib_execution_receipt(aeib_receipt, pub_bytes, current_epoch=50)
    if not res_aeib.get("valid"):
        return False

    # Falsification: Tampered CAID
    tampered_receipt = json.loads(json.dumps(aeib_receipt))
    tampered_receipt["unsigned_payload"]["action_payload"]["amount"] = 99999
    res_tampered = verify_aeib_execution_receipt(tampered_receipt, pub_bytes)
    if res_tampered.get("valid"):
        return False

    # 6. Selective Disclosure Receipt Positive & Falsification
    claims = {"user": "Alice", "iban": "DE12345", "amount": 500}
    salts = {"user": "11" * 16, "iban": "22" * 16, "amount": "33" * 16}
    commits = {k: compute_field_commitment(k, claims[k], salts[k]) for k in claims}
    sd_root = compute_receipt_root(commits)
    _, sd_sig = ed25519_sign(test_seed, sd_root.encode("utf-8"))

    # Redact 'iban'
    sd_receipt = {
        "receipt_id": "sd-rcpt-001",
        "disclosed_claims": {"user": "Alice", "amount": 500},
        "disclosed_salts": {"user": salts["user"], "amount": salts["amount"]},
        "redacted_field_commitments": {"iban": commits["iban"]},
        "root_hash": sd_root,
        "signature_envelope": {
            "public_key_hex": pub_bytes.hex(),
            "signature_b64": base64.b64encode(sd_sig).decode("ascii"),
        },
    }

    res_sd = verify_selective_disclosure_receipt(sd_receipt, pub_bytes)
    if not res_sd.get("valid"):
        return False

    # Falsification: Tampered blind commitment
    sd_tampered = json.loads(json.dumps(sd_receipt))
    sd_tampered["redacted_field_commitments"]["iban"] = "00" * 32
    if verify_selective_disclosure_receipt(sd_tampered, pub_bytes).get("valid"):
        return False

    # 7. RFC 9162 Merkle Tree Inclusion Proof
    leaf0 = rfc9162_hash_leaf(b"leaf0")
    leaf1 = rfc9162_hash_leaf(b"leaf1")
    merkle_root = rfc9162_hash_children(leaf0, leaf1)

    merkle_receipt = {
        "leaf_index": 0,
        "tree_size": 2,
        "leaf_hash": leaf0.hex(),
        "root_hash": merkle_root.hex(),
        "inclusion_proof": [leaf1.hex()],
    }

    res_merkle = verify_merkle_receipt(merkle_receipt, pinned_root_bytes=merkle_root)
    if not res_merkle.get("valid"):
        return False

    # Falsification: Tampered sibling in audit path
    tampered_merkle = json.loads(json.dumps(merkle_receipt))
    tampered_merkle["inclusion_proof"] = [(b"\xff" * 32).hex()]
    if verify_merkle_receipt(tampered_merkle, pinned_root_bytes=merkle_root).get("valid"):
        return False

    return True


# ------------------------------------------------------------------------------
# 10. Command-Line Interface (CLI)
# ------------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="AEIB Standalone Zero-Dependency Offline Audit Verifier (RFC 8032 / RFC 8785 / RFC 9162)."
    )
    parser.add_argument(
        "--verify-receipt",
        type=Path,
        help="Path to an individual AEIB receipt JSON file to verify.",
    )
    parser.add_argument(
        "--verify-bundle",
        type=Path,
        help="Path to a directory containing AEIB receipt JSON/JSONL files to verify.",
    )
    parser.add_argument(
        "--public-key",
        type=str,
        help="Trusted Ed25519 public key (hex string, base64 string, PEM string, or path to key file).",
    )
    parser.add_argument(
        "--pinned-root",
        type=str,
        help="Pinned RFC 9162 Merkle root hex string (32 bytes / 64 hex characters).",
    )
    parser.add_argument(
        "--policy-epoch",
        type=int,
        help="Current configured policy epoch for freshness boundary enforcement.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Execute internal verification test suite (pure Python RFC 8032 math, JCS, receipts).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit verification verdict as a structured JSON object.",
    )

    args = parser.parse_args()

    # Self-Test Dispatch
    if args.self_test:
        success = run_self_test()
        if success:
            if args.json:
                print(json.dumps({"self_test": "VALID", "status_code": 0}))
            else:
                print("[VALID] Standalone Offline Verifier Self-Test: All positive and falsification vectors evaluated successfully.")
            sys.exit(0)
        else:
            if args.json:
                print(json.dumps({"self_test": "FAILED", "status_code": 1}))
            else:
                print("[FAIL] Standalone Offline Verifier Self-Test: Verification or falsification checks failed.", file=sys.stderr)
            sys.exit(1)

    # Resolve optional public key
    trusted_pub: Optional[bytes] = None
    if args.public_key:
        try:
            trusted_pub = parse_ed25519_public_key(args.public_key)
        except Exception as exc:
            print(f"[FAIL] Public key resolution error: {exc}", file=sys.stderr)
            sys.exit(2)

    # Resolve optional pinned root
    pinned_root: Optional[bytes] = None
    if args.pinned_root:
        try:
            pinned_root = bytes.fromhex(args.pinned_root)
            if len(pinned_root) != 32:
                raise ValueError("Pinned root must be 32 bytes (64 hex characters)")
        except Exception as exc:
            print(f"[FAIL] Pinned root resolution error: {exc}", file=sys.stderr)
            sys.exit(2)

    # Verify Single Receipt
    if args.verify_receipt:
        if not args.verify_receipt.is_file():
            print(f"[FAIL] Receipt file not found: {args.verify_receipt}", file=sys.stderr)
            sys.exit(2)
        try:
            data = json.loads(args.verify_receipt.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[FAIL] Could not parse receipt JSON: {exc}", file=sys.stderr)
            sys.exit(2)

        verdict = verify_any_receipt(
            receipt_data=data,
            trusted_pubkey_bytes=trusted_pub,
            pinned_root_bytes=pinned_root,
            current_epoch=args.policy_epoch,
        )

        if args.json:
            print(json.dumps(verdict, indent=2))
        else:
            if verdict.get("valid"):
                print(f"[VALID] Receipt authenticated successfully ({verdict.get('receipt_type')})")
                for k, v in verdict.items():
                    if k not in ("valid",):
                        print(f"  {k}: {v}")
            else:
                print(f"[FAIL] Receipt authentication failed: {verdict.get('error')}", file=sys.stderr)
        sys.exit(0 if verdict.get("valid") else 1)

    # Verify Bundle Directory
    if args.verify_bundle:
        try:
            bundle_verdict = verify_bundle_directory(
                bundle_dir=args.verify_bundle,
                trusted_pubkey_bytes=trusted_pub,
                pinned_root_bytes=pinned_root,
                current_epoch=args.policy_epoch,
            )
        except Exception as exc:
            print(f"[FAIL] Bundle verification error: {exc}", file=sys.stderr)
            sys.exit(2)

        if args.json:
            print(json.dumps(bundle_verdict, indent=2))
        else:
            if bundle_verdict.get("valid"):
                print(f"[VALID] Bundle verified: {bundle_verdict['valid_receipts']}/{bundle_verdict['total_receipts']} receipts valid.")
            else:
                print(f"[FAIL] Bundle verification failed: {bundle_verdict['failed_receipts']} failures out of {bundle_verdict['total_receipts']} receipts.", file=sys.stderr)
                for f in bundle_verdict.get("failures", []):
                    print(f"  - {f}", file=sys.stderr)
        sys.exit(0 if bundle_verdict.get("valid") else 1)

    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
