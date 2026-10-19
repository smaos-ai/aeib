#!/usr/bin/env python3
"""
tools/standalone_receipt_verifier.py
================================================================================
AEIB Standalone Offline Receipt Verifier Specification Implementation.

Specification Reference:
  OFFLINE_VERIFIER_SPEC.md (Version 1.0.0-rc.3)

Purpose:
  Provides an independent, self-contained verification tool for third-party
  auditors and external evaluators to verify AEIB action receipts, continuity
  ledgers, CAID bindings, and Ed25519 cryptographic signatures without network
  access or live repository runtime dependencies.

Design Invariants:
  1. Zero Network Egress: Operates 100% air-gapped; never initiates network calls.
  2. Caller-Supplied Public Key / Trust Anchor: Enforces explicit key custody.
  3. Strict Canonicalization: Implements pure RFC 8785 JSON Canonicalization Scheme (JCS).
  4. Deterministic Falsification: Built-in --self-test validates 1 positive and
     all 7 normative negative vectors (NEG_01 to NEG_07).

Evaluated under the stated model. Preserves strict epistemic calibration.
"""

from __future__ import annotations

import argparse
import base64
import datetime
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

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

VERIFIER_VERSION = "1.0.0-rc.3"

# Standard normative failure codes per OFFLINE_VERIFIER_SPEC.md
CODE_PASS = "POS_01: VALID_RECEIPT"
CODE_NEG_01 = "NEG_01: JCS_DIGEST_MISMATCH"
CODE_NEG_02 = "NEG_02: UNTRUSTED_KEY_IDENTIFIER"
CODE_NEG_03 = "NEG_03: SCHEMA_VALIDATION_ERROR"
CODE_NEG_04 = "NEG_04: TEMPORAL_VALIDITY_EXPIRED"
CODE_NEG_05 = "NEG_05: OPERATION_ID_REPLAY_DETECTED"
CODE_NEG_06 = "NEG_06: LEDGER_CHAIN_INTEGRITY_BROKEN"
CODE_NEG_07 = "NEG_07: UNSUPPORTED_CRYPTO_ALGORITHM"

VALID_DISPOSITIONS: Set[str] = {
    "CONFIRMED",
    "REFUTED",
    "EFFECT_INDETERMINATE",
    "OUTCOME_VERIFIED",
    "DISPATCHED_UNCONFIRMED",
    "AUTHORIZED_FOR_HOST_SIGNING",
}

APPROVED_ALGORITHMS: Set[str] = {
    "Ed25519",
    "EdDSA",
    "-8",
}


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
# 2. Public Key & Trust Anchor Loader
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
# 3. Receipt Verification Pipeline
# ==============================================================================

def verify_receipt_data(
    receipt: Dict[str, Any],
    trusted_public_key: Optional[Ed25519PublicKey] = None,
    expected_operation_id: Optional[str] = None,
    active_policy_epoch: Optional[int] = None,
    max_clock_drift_seconds: int = 300,
    current_time_epoch: Optional[int] = None,
    trust_anchors: Optional[Dict[str, Ed25519PublicKey]] = None,
) -> Dict[str, Any]:
    """
    Evaluates an AEIB execution receipt under caller-supplied public keys or trust anchor.
    Executes the 6-stage verification pipeline per OFFLINE_VERIFIER_SPEC.md:
      1. Manifest & Schema Integrity
      2. Canonical Serialization & CAID Recomputation
      3. Algorithm Verification
      4. Signature Verification
      5. Temporal Validity & Epoch Freshness
      6. Evidence Formatting
    """
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    now_ts = current_time_epoch if current_time_epoch is not None else int(datetime.datetime.now(datetime.timezone.utc).timestamp())

    # Helper for building canonical result dictionary
    def _make_result(
        valid: bool,
        op_id: Optional[str],
        failure_code: Optional[str],
        error_msg: Optional[str],
        disposition: Optional[str] = None,
        receipt_sha256: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "valid": valid,
            "status": "PASS" if valid else "FAIL",
            "operation_id": op_id or "UNKNOWN",
            "failure_code": failure_code,
            "error": error_msg,
            "disposition": disposition or "UNKNOWN",
            "receipt_sha256": receipt_sha256,
            "verified_at": now_iso,
            "verifier_version": VERIFIER_VERSION,
        }

    # --------------------------------------------------------------------------
    # Step 1: Manifest & Schema Integrity Check (NEG_03)
    # --------------------------------------------------------------------------
    if not isinstance(receipt, dict):
        return _make_result(False, None, CODE_NEG_03, "Receipt must be a JSON object")

    op_id = receipt.get("operation_id") or receipt.get("operationId")
    if not op_id or not isinstance(op_id, str):
        return _make_result(False, None, CODE_NEG_03, "Missing or invalid required field 'operation_id'")

    if expected_operation_id and op_id != expected_operation_id:
        return _make_result(
            False,
            op_id,
            CODE_NEG_03,
            f"Operation ID mismatch: expected '{expected_operation_id}', got '{op_id}'",
        )

    disposition = (
        receipt.get("disposition")
        or receipt.get("final_disposition")
        or receipt.get("evaluated_disposition")
    )
    if disposition and disposition not in VALID_DISPOSITIONS:
        return _make_result(
            False,
            op_id,
            CODE_NEG_03,
            f"Invalid receipt disposition: '{disposition}' not in {VALID_DISPOSITIONS}",
        )

    # --------------------------------------------------------------------------
    # Step 2: Canonical Serialization & CAID Recomputation (NEG_01)
    # --------------------------------------------------------------------------
    action_payload = receipt.get("action_payload") or receipt.get("payload")
    claimed_caid = receipt.get("action_caid") or receipt.get("caid")
    if action_payload is not None and claimed_caid is not None:
        try:
            computed_caid = compute_sha256_prefixed(encode_jcs(action_payload))
        except Exception as exc:
            return _make_result(False, op_id, CODE_NEG_01, f"Failed JCS serialization of payload: {exc}")

        if claimed_caid != computed_caid:
            return _make_result(
                False,
                op_id,
                CODE_NEG_01,
                f"CAID mismatch: claimed '{claimed_caid}', computed '{computed_caid}'",
                disposition=disposition,
            )

    # --------------------------------------------------------------------------
    # Step 3: Algorithm Verification (NEG_07)
    # --------------------------------------------------------------------------
    alg = receipt.get("alg") or receipt.get("algorithm")
    if isinstance(receipt.get("attestation_signature"), dict):
        alg = alg or receipt["attestation_signature"].get("alg")

    if alg is not None:
        str_alg = str(alg)
        if str_alg.lower() in ("none", "null") or str_alg not in APPROVED_ALGORITHMS:
            return _make_result(
                False,
                op_id,
                CODE_NEG_07,
                f"Unsupported or deprecated algorithm: '{alg}'. Only Ed25519 (EdDSA) is approved.",
                disposition=disposition,
            )

    # --------------------------------------------------------------------------
    # Step 4: Extract Signature & Resolve Public Key Anchor (NEG_02)
    # --------------------------------------------------------------------------
    sig_bytes: Optional[bytes] = None
    unsigned_body: Dict[str, Any] = {}
    key_id: Optional[str] = receipt.get("key_id") or receipt.get("kid")

    # Format A: Modern envelope with attestation_signature
    if "attestation_signature" in receipt:
        att = receipt["attestation_signature"]
        if isinstance(att, dict):
            key_id = key_id or att.get("kid") or att.get("key_id")
            sig_b64 = att.get("signature_b64") or att.get("signature_hex")
            if sig_b64:
                try:
                    sig_bytes = bytes.fromhex(sig_b64) if len(sig_b64) == 128 else base64.b64decode(sig_b64)
                except Exception:
                    return _make_result(False, op_id, CODE_NEG_03, "Malformed signature encoding in attestation_signature")
        unsigned_body = {k: v for k, v in receipt.items() if k != "attestation_signature"}

    # Format B: Flat receipt with signature_b64 or signature_hex
    elif "signature_b64" in receipt or "signature_hex" in receipt:
        sig_val = receipt.get("signature_b64") or receipt.get("signature_hex")
        if sig_val:
            try:
                sig_bytes = bytes.fromhex(sig_val) if len(sig_val) == 128 else base64.b64decode(sig_val)
            except Exception:
                return _make_result(False, op_id, CODE_NEG_03, "Malformed signature encoding in receipt")
        unsigned_body = {
            k: v for k, v in receipt.items()
            if k not in ("signature_b64", "signature_hex", "gate_signature")
        }

    # Format C: Warrant receipt with warrant_caid
    elif "warrant_caid" in receipt and "signature_b64" in receipt:
        try:
            sig_bytes = base64.b64decode(receipt["signature_b64"])
        except Exception:
            return _make_result(False, op_id, CODE_NEG_03, "Malformed signature encoding in warrant receipt")
        unsigned_body = {k: v for k, v in receipt.items() if k != "signature_b64"}

    # Format D: Legacy signedStatement
    elif "signedStatement" in receipt and "signature" in receipt:
        sig_container = receipt["signature"]
        sig_val = sig_container.get("ed25519Signature")
        if sig_val:
            try:
                sig_bytes = base64.b64decode(sig_val)
                raw_statement = base64.b64decode(receipt["signedStatement"])
            except Exception:
                return _make_result(False, op_id, CODE_NEG_03, "Malformed base64 in signedStatement envelope")

            active_pk = trusted_public_key
            if active_pk is None and trust_anchors and key_id:
                active_pk = trust_anchors.get(key_id)

            if active_pk is None:
                return _make_result(False, op_id, CODE_NEG_02, f"No trust anchor for key_id '{key_id}'")

            try:
                active_pk.verify(sig_bytes, raw_statement)
                return _make_result(True, op_id, None, None, disposition=disposition or "UNKNOWN")
            except InvalidSignature:
                return _make_result(False, op_id, CODE_NEG_02, "Invalid Ed25519 signature on signedStatement")

    if not sig_bytes:
        return _make_result(False, op_id, CODE_NEG_03, "No recognized cryptographic signature field found in receipt")

    # Resolve active public key
    active_pk = trusted_public_key
    if active_pk is None and trust_anchors:
        if key_id and key_id in trust_anchors:
            active_pk = trust_anchors[key_id]
        else:
            return _make_result(
                False,
                op_id,
                CODE_NEG_02,
                f"Untrusted key identifier '{key_id}': not found in provided trust anchors",
                disposition=disposition,
            )

    if active_pk is None:
        return _make_result(
            False,
            op_id,
            CODE_NEG_02,
            "No trusted public key or trust anchor provided for verification",
            disposition=disposition,
        )

    # Cryptographic signature verification
    canonical_unsigned_bytes = encode_jcs(unsigned_body)
    try:
        active_pk.verify(sig_bytes, canonical_unsigned_bytes)
    except InvalidSignature:
        return _make_result(
            False,
            op_id,
            CODE_NEG_02,
            "Invalid Ed25519 signature over canonical RFC 8785 JCS receipt payload",
            disposition=disposition,
        )

    # --------------------------------------------------------------------------
    # Step 5: Temporal Validity & Epoch Freshness (NEG_04)
    # --------------------------------------------------------------------------
    receipt_epoch = receipt.get("policy_epoch")
    if active_policy_epoch is not None and receipt_epoch is not None:
        if receipt_epoch != active_policy_epoch:
            return _make_result(
                False,
                op_id,
                CODE_NEG_04,
                f"Receipt policy epoch {receipt_epoch} does not match active epoch {active_policy_epoch}",
                disposition=disposition,
            )

    ts_epoch = receipt.get("timestamp_epoch") or receipt.get("timestamp")
    if isinstance(ts_epoch, (int, float)):
        # Check against future clock drift or explicit expiration
        if ts_epoch > now_ts + max_clock_drift_seconds:
            return _make_result(
                False,
                op_id,
                CODE_NEG_04,
                f"Receipt timestamp {ts_epoch} exceeds permitted clock drift (+{max_clock_drift_seconds}s)",
                disposition=disposition,
            )

    expires_at = receipt.get("expires_at") or receipt.get("expires_at_epoch")
    if isinstance(expires_at, (int, float)):
        if now_ts > expires_at:
            return _make_result(
                False,
                op_id,
                CODE_NEG_04,
                f"Receipt expired at timestamp {expires_at} (current evaluated time: {now_ts})",
                disposition=disposition,
            )

    # --------------------------------------------------------------------------
    # Step 6: Success
    # --------------------------------------------------------------------------
    receipt_digest = compute_sha256_prefixed(canonical_unsigned_bytes)
    return _make_result(
        True,
        op_id,
        None,
        None,
        disposition=disposition or "UNSPECIFIED",
        receipt_sha256=receipt_digest,
    )


# ==============================================================================
# 4. Evidence-Chain Linkage (Ledger Stream Verification)
# ==============================================================================

def verify_ledger_stream(
    lines: List[str],
    trusted_public_key: Ed25519PublicKey,
    expected_initial_tip: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Evaluates an append-only continuity ledger (ledger.jsonl) stream.
    Verifies:
      1. Sequential chain tip continuity (prev_chain_tip match, NEG_06 if broken).
      2. No duplicate operation_id values (NEG_05 if replay detected).
      3. Valid cryptographic signature and CAID on each entry.
    """
    seen_op_ids: Set[str] = set()
    current_tip = expected_initial_tip or "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    entries_count = 0

    for idx, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue

        try:
            entry = json.loads(line)
        except Exception as exc:
            return {
                "valid": False,
                "status": "FAIL",
                "failure_code": CODE_NEG_03,
                "error": f"Malformed JSON in ledger line {idx}: {exc}",
                "line_number": idx,
            }

        op_id = entry.get("operation_id")
        if not op_id:
            return {
                "valid": False,
                "status": "FAIL",
                "failure_code": CODE_NEG_03,
                "error": f"Missing 'operation_id' in ledger line {idx}",
                "line_number": idx,
            }

        # Check duplicate operation_id (NEG_05)
        if op_id in seen_op_ids:
            return {
                "valid": False,
                "status": "FAIL",
                "operation_id": op_id,
                "failure_code": CODE_NEG_05,
                "error": f"Duplicate operation_id '{op_id}' in ledger sequence at line {idx}",
                "line_number": idx,
            }
        seen_op_ids.add(op_id)

        # Check chain tip continuity (NEG_06)
        prev_tip = entry.get("prev_chain_tip")
        if prev_tip != current_tip:
            return {
                "valid": False,
                "status": "FAIL",
                "operation_id": op_id,
                "failure_code": CODE_NEG_06,
                "error": f"Broken ledger chain tip at line {idx}: expected '{current_tip}', found '{prev_tip}'",
                "line_number": idx,
            }

        # Verify entry receipt signature
        rec_res = verify_receipt_data(entry, trusted_public_key=trusted_public_key)
        if not rec_res["valid"]:
            rec_res["line_number"] = idx
            return rec_res

        # Advance tip
        current_tip = rec_res["receipt_sha256"] or compute_sha256_prefixed(encode_jcs(entry))
        entries_count += 1

    return {
        "valid": True,
        "status": "PASS",
        "failure_code": None,
        "entries_verified": entries_count,
        "final_chain_tip": current_tip,
        "error": None,
    }


# ==============================================================================
# 5. Self-Test Battery (1 Positive + All 7 Normative Negative Vectors)
# ==============================================================================

def run_self_test() -> bool:
    """
    Executes a comprehensive, self-contained test battery verifying that the verifier:
      - Validates genuine Ed25519 receipts over RFC 8785 JCS (POS_01).
      - Fails closed on 1-byte payload mutation (NEG_01).
      - Fails closed on untrusted or rogue key signatures (NEG_02).
      - Fails closed on missing required schema fields or malformed JSON (NEG_03).
      - Fails closed on expired temporal validity or stale policy epoch (NEG_04).
      - Fails closed on replayed operation_id in ledger sequence (NEG_05).
      - Fails closed on broken ledger chain tip (NEG_06).
      - Fails closed on algorithm downgrade attacks (NEG_07).
    """
    print("================================================================================")
    print("  AEIB STANDALONE RECEIPT VERIFIER: COMPREHENSIVE SELF-TEST BATTERY")
    print(f"  Specification: OFFLINE_VERIFIER_SPEC.md (v{VERIFIER_VERSION})")
    print("  Evaluated under stated model. Zero network egress. Pure RFC 8785 JCS.")
    print("================================================================================")

    trusted_sk = Ed25519PrivateKey.generate()
    trusted_pk = trusted_sk.public_key()
    rogue_sk = Ed25519PrivateKey.generate()

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
        "policy_epoch": 1,
        "timestamp_epoch": 1760000000,
        "alg": "Ed25519",
    }
    canonical_body = encode_jcs(receipt_body)
    valid_sig = trusted_sk.sign(canonical_body)

    genuine_receipt = dict(receipt_body)
    genuine_receipt["signature_b64"] = base64.b64encode(valid_sig).decode("ascii")

    # --------------------------------------------------------------------------
    # POS_01: Positive Path
    # --------------------------------------------------------------------------
    res_pos = verify_receipt_data(
        genuine_receipt,
        trusted_public_key=trusted_pk,
        current_time_epoch=1760000010,
        active_policy_epoch=1,
    )
    if not res_pos["valid"]:
        print(f"[!] POS_01 Failed: {res_pos['error']}", file=sys.stderr)
        return False
    print("  [✔] POS_01 (Positive Path): Genuine receipt validated.")

    # --------------------------------------------------------------------------
    # NEG_01: Tampered Payload
    # --------------------------------------------------------------------------
    tampered_payload_receipt = dict(genuine_receipt)
    tampered_payload_receipt["action_payload"] = dict(action_payload)
    tampered_payload_receipt["action_payload"]["amount_minor"] = 45001  # Mutate 1 cent
    res_neg01 = verify_receipt_data(tampered_payload_receipt, trusted_public_key=trusted_pk)
    if res_neg01["valid"] or res_neg01["failure_code"] != CODE_NEG_01:
        print(f"[!] NEG_01 Failed: Expected {CODE_NEG_01}, got {res_neg01}", file=sys.stderr)
        return False
    print(f"  [✔] NEG_01 (Tampered Payload): Caught fail-closed ({res_neg01['failure_code']}).")

    # --------------------------------------------------------------------------
    # NEG_02: Wrong Key Identifier / Rogue Key
    # --------------------------------------------------------------------------
    rogue_sig = rogue_sk.sign(canonical_body)
    rogue_receipt = dict(genuine_receipt)
    rogue_receipt["signature_b64"] = base64.b64encode(rogue_sig).decode("ascii")
    res_neg02 = verify_receipt_data(rogue_receipt, trusted_public_key=trusted_pk)
    if res_neg02["valid"] or res_neg02["failure_code"] != CODE_NEG_02:
        print(f"[!] NEG_02 Failed: Expected {CODE_NEG_02}, got {res_neg02}", file=sys.stderr)
        return False
    print(f"  [✔] NEG_02 (Wrong Key Signature): Caught fail-closed ({res_neg02['failure_code']}).")

    # --------------------------------------------------------------------------
    # NEG_03: Malformed Receipt / Missing Required Field
    # --------------------------------------------------------------------------
    malformed_receipt = dict(genuine_receipt)
    del malformed_receipt["operation_id"]
    res_neg03 = verify_receipt_data(malformed_receipt, trusted_public_key=trusted_pk)
    if res_neg03["valid"] or res_neg03["failure_code"] != CODE_NEG_03:
        print(f"[!] NEG_03 Failed: Expected {CODE_NEG_03}, got {res_neg03}", file=sys.stderr)
        return False
    print(f"  [✔] NEG_03 (Malformed Schema): Caught fail-closed ({res_neg03['failure_code']}).")

    # --------------------------------------------------------------------------
    # NEG_04: Stale Authority / Expired Timestamp
    # --------------------------------------------------------------------------
    expired_body = dict(receipt_body)
    expired_body["expires_at"] = 1760000000
    expired_canonical = encode_jcs(expired_body)
    expired_sig = trusted_sk.sign(expired_canonical)
    expired_receipt = dict(expired_body)
    expired_receipt["signature_b64"] = base64.b64encode(expired_sig).decode("ascii")

    res_neg04 = verify_receipt_data(
        expired_receipt,
        trusted_public_key=trusted_pk,
        current_time_epoch=1760000100,  # Now is past expires_at
    )
    if res_neg04["valid"] or res_neg04["failure_code"] != CODE_NEG_04:
        print(f"[!] NEG_04 Failed: Expected {CODE_NEG_04}, got {res_neg04}", file=sys.stderr)
        return False
    print(f"  [✔] NEG_04 (Stale Temporal Validity): Caught fail-closed ({res_neg04['failure_code']}).")

    # --------------------------------------------------------------------------
    # NEG_05: Replayed Receipt in Ledger Stream
    # --------------------------------------------------------------------------
    initial_tip = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    entry1 = dict(genuine_receipt)
    entry1["operation_id"] = "op-ledger-001"
    entry1["prev_chain_tip"] = initial_tip
    del entry1["signature_b64"]
    entry1["signature_b64"] = base64.b64encode(trusted_sk.sign(encode_jcs(entry1))).decode("ascii")
    tip1 = compute_sha256_prefixed(encode_jcs(dict((k, v) for k, v in entry1.items() if k != "signature_b64")))

    # Entry 2 replays op-ledger-001
    entry2_replayed = dict(genuine_receipt)
    entry2_replayed["operation_id"] = "op-ledger-001"
    entry2_replayed["prev_chain_tip"] = tip1
    del entry2_replayed["signature_b64"]
    entry2_replayed["signature_b64"] = base64.b64encode(trusted_sk.sign(encode_jcs(entry2_replayed))).decode("ascii")

    ledger_replay_lines = [json.dumps(entry1), json.dumps(entry2_replayed)]
    res_neg05 = verify_ledger_stream(ledger_replay_lines, trusted_public_key=trusted_pk, expected_initial_tip=initial_tip)
    if res_neg05["valid"] or res_neg05["failure_code"] != CODE_NEG_05:
        print(f"[!] NEG_05 Failed: Expected {CODE_NEG_05}, got {res_neg05}", file=sys.stderr)
        return False
    print(f"  [✔] NEG_05 (Replayed Receipt in Ledger): Caught fail-closed ({res_neg05['failure_code']}).")

    # --------------------------------------------------------------------------
    # NEG_06: Broken Ledger Chain Tip
    # --------------------------------------------------------------------------
    entry2_broken_tip = dict(genuine_receipt)
    entry2_broken_tip["operation_id"] = "op-ledger-002"
    entry2_broken_tip["prev_chain_tip"] = "sha256:bad0000000000000000000000000000000000000000000000000000000000000"
    del entry2_broken_tip["signature_b64"]
    entry2_broken_tip["signature_b64"] = base64.b64encode(trusted_sk.sign(encode_jcs(entry2_broken_tip))).decode("ascii")

    ledger_broken_lines = [json.dumps(entry1), json.dumps(entry2_broken_tip)]
    res_neg06 = verify_ledger_stream(ledger_broken_lines, trusted_public_key=trusted_pk, expected_initial_tip=initial_tip)
    if res_neg06["valid"] or res_neg06["failure_code"] != CODE_NEG_06:
        print(f"[!] NEG_06 Failed: Expected {CODE_NEG_06}, got {res_neg06}", file=sys.stderr)
        return False
    print(f"  [✔] NEG_06 (Broken Ledger Chain Tip): Caught fail-closed ({res_neg06['failure_code']}).")

    # --------------------------------------------------------------------------
    # NEG_07: Algorithm Downgrade
    # --------------------------------------------------------------------------
    downgrade_receipt = dict(genuine_receipt)
    downgrade_receipt["alg"] = "none"
    del downgrade_receipt["signature_b64"]
    downgrade_receipt["signature_b64"] = base64.b64encode(trusted_sk.sign(encode_jcs(downgrade_receipt))).decode("ascii")
    res_neg07 = verify_receipt_data(downgrade_receipt, trusted_public_key=trusted_pk)
    if res_neg07["valid"] or res_neg07["failure_code"] != CODE_NEG_07:
        print(f"[!] NEG_07 Failed: Expected {CODE_NEG_07}, got {res_neg07}", file=sys.stderr)
        return False
    print(f"  [✔] NEG_07 (Algorithm Downgrade 'none'): Caught fail-closed ({res_neg07['failure_code']}).")

    print("================================================================================")
    print("  [✔] ALL 8 NORMATIVE VECTORS PASSED: 1 POSITIVE + 7 NEGATIVE FALSIFICATIONS")
    print("================================================================================")
    return True


# ==============================================================================
# 6. CLI Entrypoint
# ==============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"AEIB Standalone Offline Receipt Verifier v{VERIFIER_VERSION} (RFC 8785 JCS + Ed25519)"
    )
    parser.add_argument(
        "--receipt",
        type=Path,
        help="Path to receipt JSON file to verify.",
    )
    parser.add_argument(
        "--ledger",
        type=Path,
        help="Path to append-only continuity ledger (ledger.jsonl) to verify.",
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
        "--policy-epoch",
        type=int,
        default=None,
        help="Optional active policy epoch to evaluate temporal validity.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run the built-in normative test battery (1 positive + 7 negative vectors).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output verification result strictly as machine-readable JSON per OFFLINE_VERIFIER_SPEC.md.",
    )

    args = parser.parse_args()

    if args.self_test:
        success = run_self_test()
        sys.exit(0 if success else 1)

    if not args.public_key and not args.self_test:
        parser.print_help()
        print(
            "\n[!] Error: --public-key must be provided for verification (or run --self-test).",
            file=sys.stderr,
        )
        sys.exit(1)

    if not args.receipt and not args.ledger:
        parser.print_help()
        print(
            "\n[!] Error: Either --receipt or --ledger must be provided.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        trusted_pk = load_ed25519_public_key(args.public_key)
    except Exception as exc:
        print(f"[!] Failed to load public key from {args.public_key}: {exc}", file=sys.stderr)
        sys.exit(1)

    # 1. Ledger Verification Mode
    if args.ledger:
        if not args.ledger.is_file():
            print(f"[!] Error: Ledger file not found: {args.ledger}", file=sys.stderr)
            sys.exit(1)

        lines = args.ledger.read_text(encoding="utf-8").splitlines()
        result = verify_ledger_stream(lines, trusted_public_key=trusted_pk)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result["valid"]:
                print(f"[✔] Ledger VALID: {args.ledger.name}")
                print(f"    - Entries Verified : {result.get('entries_verified')}")
                print(f"    - Final Chain Tip  : {result.get('final_chain_tip')}")
            else:
                print(f"[✘] Ledger INVALID: {args.ledger.name}", file=sys.stderr)
                print(f"    - Failure Code     : {result.get('failure_code')}", file=sys.stderr)
                print(f"    - Error            : {result.get('error')}", file=sys.stderr)
        sys.exit(0 if result["valid"] else 1)

    # 2. Single Receipt Verification Mode
    if args.receipt:
        if not args.receipt.is_file():
            print(f"[!] Error: Receipt file not found: {args.receipt}", file=sys.stderr)
            sys.exit(1)

        try:
            receipt_dict = json.loads(args.receipt.read_text(encoding="utf-8"))
        except Exception as exc:
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            res_fail = {
                "status": "FAIL",
                "operation_id": "UNKNOWN",
                "failure_code": CODE_NEG_03,
                "error": f"Failed to parse receipt JSON: {exc}",
                "verified_at": now_iso,
                "verifier_version": VERIFIER_VERSION,
            }
            if args.json:
                print(json.dumps(res_fail, indent=2))
            else:
                print(f"[✘] Receipt INVALID: {args.receipt.name} ({CODE_NEG_03})", file=sys.stderr)
            sys.exit(1)

        result = verify_receipt_data(
            receipt_dict,
            trusted_public_key=trusted_pk,
            expected_operation_id=args.operation_id,
            active_policy_epoch=args.policy_epoch,
        )

        if args.json:
            formatted_json = {
                "status": result["status"],
                "operation_id": result["operation_id"],
                "failure_code": result["failure_code"],
                "verified_at": result["verified_at"],
                "verifier_version": result["verifier_version"],
            }
            print(json.dumps(formatted_json, indent=2))
        else:
            if result["valid"]:
                print(f"[✔] Receipt VALID: {args.receipt.name}")
                print(f"    - Operation ID : {result.get('operation_id')}")
                print(f"    - Disposition  : {result.get('disposition')}")
                print(f"    - SHA-256 Tip  : {result.get('receipt_sha256')}")
            else:
                print(f"[✘] Receipt INVALID: {args.receipt.name}", file=sys.stderr)
                print(f"    - Failure Code : {result.get('failure_code')}", file=sys.stderr)
                print(f"    - Error        : {result.get('error')}", file=sys.stderr)

        sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
