#!/usr/bin/env python3
"""
tools/aeib_offline_verifier.py
================================================================================
AEIB v1.0.0-rc.3 Standalone Offline Verifier & Negative Vector Suite.

Verifies operation-bound receipts and append-only ledger chains offline
(Python stdlib + `cryptography` + the repository's RFC 8785 JCS encoder):

  1. Manifest integrity (manifest digest, entry count, chain tip)
  2. Receipt schema version (`aeib.receipt.v1`)
  3. Canonical serialization (RFC 8785 JCS via src.jcs_canonicalizer.encode_jcs)
  4. Ed25519 signature over the exact canonical bytes
  5. Key identifier (`kid`) lookup against caller-pinned trust anchors
  6. Operation binding (`operation_id` + CAID over action fields,
     `harness_digest`, `policy_epoch`)
  7. Temporal validity (dispatch time within [issued_at, expires_at] +/- drift)
  8. Evidence-chain linkage (`prev_entry_hash` -> `entry_hash`, monotonic `seq`)
  9. Explicit rejection of the 6 mandatory negative vectors:
       NEG_1_TAMPERED_PAYLOAD, NEG_2_WRONG_KEY, NEG_3_MISSING_RECEIPT,
       NEG_4_STALE_AUTHORITY, NEG_5_REPLAYED_RECEIPT, NEG_6_BROKEN_CHAIN

Scope (see LIMITATIONS.md):
  - Replay detection is per bundle. Cross-bundle replay detection requires the
    caller to pass `previously_seen_operation_ids` from durable storage.
  - Trust anchors are supplied by the caller; this tool does not establish key
    custody, revocation, or identity. A valid signature shows that the holder
    of the pinned key signed these bytes, under the stated key-custody model.
  - Passing this verifier is local evidence, not independent reproduction.

Usage:
  python3 tools/aeib_offline_verifier.py                 # self-test (all vectors)
  python3 tools/aeib_offline_verifier.py --manifest m.json --ledger l.jsonl \\
      --anchor KID=path/to/pub.pem [--anchor ...] [--expect OP_ID ...]
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import hmac
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.jcs_canonicalizer import encode_jcs  # noqa: E402  (RFC 8785)

SUPPORTED_SCHEMA_VERSION = "aeib.receipt.v1"
GENESIS_PREV_HASH = "sha256:" + ("0" * 64)

REQUIRED_BINDING_KEYS = frozenset(
    {
        "action_class",
        "amount_minor",
        "caid",
        "currency",
        "harness_digest",
        "policy_epoch",
        "recipient",
        "target",
    }
)
UNSIGNED_EXCLUDED_KEYS = ("entry_hash", "signature_b64")


def canonical_json_v1(obj: Any, allow_nan: bool = False) -> bytes:
    """
    RFC 8785 JSON Canonicalization Scheme (JCS) Profile v1.
    Strictly disallows NaN/Infinity when allow_nan=False (default).
    """
    if not allow_nan:
        # encode_jcs natively raises ValueError on NaN/Infinity
        return encode_jcs(obj)
    return encode_jcs(obj)


def canonical_jcs_bytes(obj: Any) -> bytes:
    """RFC 8785 JCS bytes (UTF-16 code-unit key order, ECMAScript numbers)."""
    return canonical_json_v1(obj, allow_nan=False)


def sha256_prefixed(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def ct_str_eq(a: Any, b: Any) -> bool:
    """Constant-time comparison; non-strings compare unequal."""
    if not isinstance(a, str) or not isinstance(b, str):
        return False
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def compute_caid(operation_id: str, binding: Dict[str, Any]) -> str:
    """CAID = SHA-256 over JCS of the exact action fields bound to operation_id."""
    return sha256_prefixed(
        canonical_json_v1(
            {
                "action_class": binding["action_class"],
                "amount_minor": binding["amount_minor"],
                "currency": binding["currency"],
                "harness_digest": binding["harness_digest"],
                "operation_id": operation_id,
                "policy_epoch": binding["policy_epoch"],
                "recipient": binding["recipient"],
                "target": binding["target"],
            },
            allow_nan=False,
        )
    )


@dataclass(frozen=True)
class VerificationResult:
    valid: bool
    error_code: Optional[str] = None
    failed_seq: Optional[int] = None


class StandaloneOfflineVerifier:
    """
    Stateless offline verifier for AEIB evidence bundles.
    Requires only caller-pinned public trust anchors plus the exported
    JSONL ledger and manifest.
    """

    def __init__(
        self,
        trust_anchors: Dict[str, Ed25519PublicKey],
        max_clock_drift_ms: int = 500,
    ) -> None:
        if not _is_int(max_clock_drift_ms) or max_clock_drift_ms < 0:
            raise ValueError("max_clock_drift_ms must be a non-negative int")
        self.trust_anchors = dict(trust_anchors)
        self.max_clock_drift_ms = max_clock_drift_ms

    def verify_bundle(
        self,
        manifest: Dict[str, Any],
        ledger_entries: List[Dict[str, Any]],
        expected_operation_ids: Iterable[str],
        previously_seen_operation_ids: Iterable[str] = (),
    ) -> VerificationResult:
        expected_ops: Set[str] = set(expected_operation_ids)
        prior_ops: Set[str] = set(previously_seen_operation_ids)

        # 1. Manifest integrity & non-empty ledger
        if not isinstance(manifest, dict):
            return VerificationResult(False, "ERR_MANIFEST_MALFORMED")
        if not ledger_entries:
            return VerificationResult(False, "ERR_EMPTY_LEDGER")

        manifest_body = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
        try:
            expected_manifest_hash = sha256_prefixed(canonical_json_v1(manifest_body, allow_nan=False))
        except (TypeError, ValueError):
            return VerificationResult(False, "ERR_MANIFEST_MALFORMED")
        if not ct_str_eq(manifest.get("manifest_sha256"), expected_manifest_hash):
            return VerificationResult(False, "ERR_MANIFEST_INTEGRITY_MISMATCH")
        if manifest.get("entry_count") != len(ledger_entries):
            return VerificationResult(False, "ERR_MANIFEST_ENTRY_COUNT_MISMATCH")

        seen_operation_ids: Set[str] = set()
        seen_entry_hashes: Set[str] = set()
        expected_prev_hash = GENESIS_PREV_HASH

        for idx, entry in enumerate(ledger_entries):
            if not isinstance(entry, dict):
                return VerificationResult(False, "ERR_ENTRY_MALFORMED", failed_seq=idx + 1)

            seq = entry.get("seq")
            if not _is_int(seq) or seq != idx + 1:
                return VerificationResult(False, "ERR_NON_MONOTONIC_SEQ", failed_seq=idx + 1)

            # 2. Schema version
            if entry.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
                return VerificationResult(False, "ERR_UNSUPPORTED_SCHEMA_VERSION", failed_seq=seq)

            # 3. Cryptographic algorithm validation (reject downgrade attacks)
            alg = entry.get("algorithm", "Ed25519")
            if alg != "Ed25519":
                return VerificationResult(False, "ERR_UNSUPPORTED_CRYPTO_ALGORITHM", failed_seq=seq)

            # 4. Replay uniqueness (within bundle and against caller-supplied history)
            op_id = entry.get("operation_id")
            if not isinstance(op_id, str) or not op_id:
                return VerificationResult(False, "ERR_MISSING_OPERATION_ID", failed_seq=seq)
            if op_id in seen_operation_ids or op_id in prior_ops:
                return VerificationResult(False, "ERR_REPLAYED_OPERATION_ID", failed_seq=seq)
            seen_operation_ids.add(op_id)

            # 5. Chain linkage
            if not ct_str_eq(entry.get("prev_entry_hash"), expected_prev_hash):
                return VerificationResult(False, "ERR_BROKEN_CHAIN_LINKAGE", failed_seq=seq)

            # 6. Canonical serialization & entry hash
            unsigned_body = {k: v for k, v in entry.items() if k not in UNSIGNED_EXCLUDED_KEYS}
            try:
                canonical_bytes = canonical_json_v1(unsigned_body, allow_nan=False)
            except (TypeError, ValueError):
                return VerificationResult(False, "ERR_NON_CANONICALIZABLE_ENTRY", failed_seq=seq)
            computed_entry_hash = sha256_prefixed(canonical_bytes)
            if not ct_str_eq(computed_entry_hash, entry.get("entry_hash")):
                return VerificationResult(False, "ERR_TAMPERED_PAYLOAD_HASH_MISMATCH", failed_seq=seq)
            if computed_entry_hash in seen_entry_hashes:
                return VerificationResult(False, "ERR_REPLAYED_RECEIPT_HASH", failed_seq=seq)
            seen_entry_hashes.add(computed_entry_hash)

            # 7. Operation binding completeness & CAID recomputation
            binding = entry.get("action_binding")
            if not isinstance(binding, dict) or not REQUIRED_BINDING_KEYS.issubset(binding.keys()):
                return VerificationResult(False, "ERR_INCOMPLETE_ACTION_BINDING", failed_seq=seq)
            if not _is_int(binding["amount_minor"]) or binding["amount_minor"] < 0:
                return VerificationResult(False, "ERR_INCOMPLETE_ACTION_BINDING", failed_seq=seq)
            if not ct_str_eq(compute_caid(op_id, binding), binding["caid"]):
                return VerificationResult(False, "ERR_CAID_ACTION_BINDING_MISMATCH", failed_seq=seq)

            # 8. Temporal validity (all fields required; window must be well-formed)
            auth = entry.get("temporal_authority")
            if not isinstance(auth, dict):
                return VerificationResult(False, "ERR_MISSING_TEMPORAL_AUTHORITY", failed_seq=seq)
            issued_ms = auth.get("issued_at_ms")
            expires_ms = auth.get("expires_at_ms")
            dispatched_ms = auth.get("dispatched_at_ms")
            if not all(_is_int(v) for v in (issued_ms, expires_ms, dispatched_ms)) or issued_ms >= expires_ms:
                return VerificationResult(False, "ERR_MISSING_TEMPORAL_AUTHORITY", failed_seq=seq)
            drift = self.max_clock_drift_ms
            if not (issued_ms - drift <= dispatched_ms <= expires_ms + drift):
                return VerificationResult(False, "ERR_STALE_OR_FUTURE_AUTHORITY", failed_seq=seq)

            # 9. Key identifier & Ed25519 signature over exact canonical bytes
            kid = entry.get("kid")
            pubkey = self.trust_anchors.get(kid) if isinstance(kid, str) else None
            if pubkey is None:
                return VerificationResult(False, "ERR_UNTRUSTED_KEY_ID", failed_seq=seq)
            sig_b64 = entry.get("signature_b64")
            if not isinstance(sig_b64, str):
                return VerificationResult(False, "ERR_INVALID_SIGNATURE", failed_seq=seq)
            try:
                sig_bytes = base64.b64decode(sig_b64, validate=True)
                pubkey.verify(sig_bytes, canonical_bytes)
            except (ValueError, InvalidSignature):
                return VerificationResult(False, "ERR_INVALID_SIGNATURE", failed_seq=seq)

            expected_prev_hash = computed_entry_hash

        # 10. No expected receipt missing; chain tip matches manifest
        if not expected_ops.issubset(seen_operation_ids):
            return VerificationResult(False, "ERR_MISSING_EXPECTED_RECEIPT")
        if not ct_str_eq(manifest.get("chain_tip_hash"), expected_prev_hash):
            return VerificationResult(False, "ERR_MANIFEST_CHAIN_TIP_MISMATCH")

        return VerificationResult(True)


# --- Bundle construction helpers (real Ed25519 keys; used by self-test and tests) ---

DEFAULT_HARNESS_DIGEST = "sha256:" + ("a" * 64)
DEFAULT_POLICY_EPOCH = "epoch-2026-10-19-v1"
DEFAULT_RECIPIENT = "iban:DE89370400440532013000"
DEFAULT_TARGET = "https://api.stripe.example/v1/refunds"


def build_signed_entry(
    seq: int,
    op_id: str,
    prev_hash: str,
    kid: str,
    signing_key: Ed25519PrivateKey,
    amount_minor: int = 2500,
    issued_at_ms: int = 1_760_000_000_000,
    expires_at_ms: int = 1_760_000_005_000,
    dispatched_at_ms: int = 1_760_000_001_000,
    algorithm: str = "Ed25519",
) -> Dict[str, Any]:
    binding = {
        "action_class": "PAYMENT_REFUND",
        "amount_minor": amount_minor,
        "currency": "EUR",
        "harness_digest": DEFAULT_HARNESS_DIGEST,
        "policy_epoch": DEFAULT_POLICY_EPOCH,
        "recipient": DEFAULT_RECIPIENT,
        "target": DEFAULT_TARGET,
    }
    binding["caid"] = compute_caid(op_id, binding)
    unsigned = {
        "schema_version": SUPPORTED_SCHEMA_VERSION,
        "algorithm": algorithm,
        "seq": seq,
        "operation_id": op_id,
        "prev_entry_hash": prev_hash,
        "kid": kid,
        "finality_state": "EFFECT_INDETERMINATE",
        "action_binding": binding,
        "temporal_authority": {
            "issued_at_ms": issued_at_ms,
            "expires_at_ms": expires_at_ms,
            "dispatched_at_ms": dispatched_at_ms,
        },
    }
    canonical = canonical_json_v1(unsigned, allow_nan=False)
    return {
        **unsigned,
        "entry_hash": sha256_prefixed(canonical),
        "signature_b64": base64.b64encode(signing_key.sign(canonical)).decode("ascii"),
    }


def build_manifest(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    body = {
        "bundle_version": "1.0.0-rc.3",
        "entry_count": len(entries),
        "chain_tip_hash": entries[-1]["entry_hash"],
    }
    return {**body, "manifest_sha256": sha256_prefixed(canonical_json_v1(body, allow_nan=False))}


def run_negative_vector_suite() -> Dict[str, VerificationResult]:
    """Builds a valid 2-entry bundle and evaluates the positive case plus all 12 vectors."""
    trusted = Ed25519PrivateKey.generate()
    rogue = Ed25519PrivateKey.generate()
    kid = "aeib-station3-key-2026-q4"
    verifier = StandaloneOfflineVerifier({kid: trusted.public_key()}, max_clock_drift_ms=500)

    e1 = build_signed_entry(1, "op-001", GENESIS_PREV_HASH, kid, trusted)
    e2 = build_signed_entry(2, "op-002", e1["entry_hash"], kid, trusted)
    both = {"op-001", "op-002"}
    results: Dict[str, VerificationResult] = {}

    results["POSITIVE"] = verifier.verify_bundle(build_manifest([e1, e2]), [e1, e2], both)

    # NEG_1: 1 byte mutated in action payload (amount modified)
    tampered = copy.deepcopy(e2)
    tampered["action_binding"]["amount_minor"] = 999_999
    results["NEG_1_TAMPERED_PAYLOAD"] = verifier.verify_bundle(build_manifest([e1, e2]), [e1, tampered], both)

    # NEG_2: Wrong key signature
    rogue_e2 = build_signed_entry(2, "op-002", e1["entry_hash"], kid, rogue)
    results["NEG_2_WRONG_KEY"] = verifier.verify_bundle(build_manifest([e1, rogue_e2]), [e1, rogue_e2], both)

    # NEG_3: Missing expected receipt
    results["NEG_3_MISSING_RECEIPT"] = verifier.verify_bundle(build_manifest([e1]), [e1], both)

    # NEG_4: Stale temporal authority
    stale = build_signed_entry(2, "op-002", e1["entry_hash"], kid, trusted, dispatched_at_ms=1_760_000_015_000)
    results["NEG_4_STALE_AUTHORITY"] = verifier.verify_bundle(build_manifest([e1, stale]), [e1, stale], both)

    # NEG_5: Duplicate operation_id in sequence
    replayed = build_signed_entry(2, "op-001", e1["entry_hash"], kid, trusted)
    results["NEG_5_REPLAYED_RECEIPT"] = verifier.verify_bundle(build_manifest([e1, replayed]), [e1, replayed], {"op-001"})

    # NEG_6: Broken chain linkage
    broken = build_signed_entry(2, "op-002", "sha256:" + ("f" * 64), kid, trusted)
    results["NEG_6_BROKEN_CHAIN"] = verifier.verify_bundle(build_manifest([e1, broken]), [e1, broken], both)

    # NEG_7: Algorithm downgrade / unsupported crypto algorithm
    unsupported_alg = build_signed_entry(2, "op-002", e1["entry_hash"], kid, trusted, algorithm="none")
    results["NEG_7_UNSUPPORTED_ALGORITHM"] = verifier.verify_bundle(build_manifest([e1, unsupported_alg]), [e1, unsupported_alg], both)

    # NEG_8: Untrusted key ID (not in caller trust anchors)
    untrusted_kid = build_signed_entry(2, "op-002", e1["entry_hash"], "untrusted-rogue-kid", trusted)
    results["NEG_8_UNTRUSTED_KEY_ID"] = verifier.verify_bundle(build_manifest([e1, untrusted_kid]), [e1, untrusted_kid], both)

    # NEG_9: Non-monotonic sequence index
    bad_seq = build_signed_entry(99, "op-002", e1["entry_hash"], kid, trusted)
    results["NEG_9_NON_MONOTONIC_SEQ"] = verifier.verify_bundle(build_manifest([e1, bad_seq]), [e1, bad_seq], both)

    # NEG_10: Unsupported schema version
    bad_schema = copy.deepcopy(e2)
    bad_schema["schema_version"] = "aeib.receipt.v0"
    results["NEG_10_UNSUPPORTED_SCHEMA_VERSION"] = verifier.verify_bundle(build_manifest([e1, e2]), [e1, bad_schema], both)

    # NEG_11: Manifest integrity mismatch (tampered digest)
    tampered_manifest = build_manifest([e1, e2])
    tampered_manifest["manifest_sha256"] = "sha256:" + ("0" * 64)
    results["NEG_11_MANIFEST_INTEGRITY_MISMATCH"] = verifier.verify_bundle(tampered_manifest, [e1, e2], both)

    # NEG_12: Float or NaN serialization rejection (RFC 8785 strictness)
    nan_entry = copy.deepcopy(e2)
    nan_entry["tampered_nan"] = float("nan")
    results["NEG_12_FLOAT_OR_NAN_SERIALIZATION"] = verifier.verify_bundle(build_manifest([e1, e2]), [e1, nan_entry], both)

    return results


EXPECTED_VECTOR_CODES = {
    "POSITIVE": None,
    "NEG_1_TAMPERED_PAYLOAD": "ERR_TAMPERED_PAYLOAD_HASH_MISMATCH",
    "NEG_2_WRONG_KEY": "ERR_INVALID_SIGNATURE",
    "NEG_3_MISSING_RECEIPT": "ERR_MISSING_EXPECTED_RECEIPT",
    "NEG_4_STALE_AUTHORITY": "ERR_STALE_OR_FUTURE_AUTHORITY",
    "NEG_5_REPLAYED_RECEIPT": "ERR_REPLAYED_OPERATION_ID",
    "NEG_6_BROKEN_CHAIN": "ERR_BROKEN_CHAIN_LINKAGE",
    "NEG_7_UNSUPPORTED_ALGORITHM": "ERR_UNSUPPORTED_CRYPTO_ALGORITHM",
    "NEG_8_UNTRUSTED_KEY_ID": "ERR_UNTRUSTED_KEY_ID",
    "NEG_9_NON_MONOTONIC_SEQ": "ERR_NON_MONOTONIC_SEQ",
    "NEG_10_UNSUPPORTED_SCHEMA_VERSION": "ERR_UNSUPPORTED_SCHEMA_VERSION",
    "NEG_11_MANIFEST_INTEGRITY_MISMATCH": "ERR_MANIFEST_INTEGRITY_MISMATCH",
    "NEG_12_FLOAT_OR_NAN_SERIALIZATION": "ERR_NON_CANONICALIZABLE_ENTRY",
}


def test_offline_verifier_positive_and_all_12_negative_vectors() -> None:
    results = run_negative_vector_suite()
    for name, expected_code in EXPECTED_VECTOR_CODES.items():
        res = results[name]
        assert res.error_code == expected_code, f"{name}: {res}"
        assert res.valid is (expected_code is None), f"{name}: {res}"
    for name in EXPECTED_VECTOR_CODES:
        if name not in ("POSITIVE", "NEG_3_MISSING_RECEIPT", "NEG_11_MANIFEST_INTEGRITY_MISMATCH"):
            assert results[name].failed_seq == 2, f"{name}: {results[name]}"


def test_offline_verifier_positive_and_all_6_negative_vectors() -> None:
    """Backward-compatible test name alias for legacy test runners."""
    test_offline_verifier_positive_and_all_12_negative_vectors()


def _load_pem_public_key(path: Path) -> Ed25519PublicKey:
    key = serialization.load_pem_public_key(path.read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError(f"{path} is not an Ed25519 public key")
    return key


def _cli(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="AEIB offline receipt-chain verifier")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--ledger", type=Path, help="JSONL ledger, one entry per line")
    parser.add_argument("--anchor", action="append", default=[], help="KID=path/to/ed25519_pub.pem")
    parser.add_argument("--expect", action="append", default=[], help="operation_id that must be present")
    parser.add_argument("--max-drift-ms", type=int, default=500)
    args = parser.parse_args(argv)

    if args.manifest is None and args.ledger is None:
        results = run_negative_vector_suite()
        ok = True
        for name, expected_code in EXPECTED_VECTOR_CODES.items():
            res = results[name]
            passed = res.error_code == expected_code and res.valid is (expected_code is None)
            ok &= passed
            print(f"  [{'OK' if passed else 'FAIL'}] {name:<35} -> valid={res.valid} code={res.error_code} seq={res.failed_seq}")
        print("ALL 9 VERIFIER CHECKS & 12 NEGATIVE VECTORS BEHAVED AS EXPECTED (local, offline)." if ok
              else "SELF-TEST FAILED")
        return 0 if ok else 1

    if args.manifest is None or args.ledger is None or not args.anchor:
        parser.error("--manifest, --ledger and at least one --anchor are required")

    anchors: Dict[str, Ed25519PublicKey] = {}
    for spec in args.anchor:
        kid, sep, path = spec.partition("=")
        if not sep or not kid:
            parser.error(f"bad --anchor {spec!r}; expected KID=path")
        anchors[kid] = _load_pem_public_key(Path(path))

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    entries = [json.loads(ln) for ln in args.ledger.read_text(encoding="utf-8").splitlines() if ln.strip()]
    res = StandaloneOfflineVerifier(anchors, args.max_drift_ms).verify_bundle(manifest, entries, args.expect)
    print(json.dumps({"valid": res.valid, "error_code": res.error_code, "failed_seq": res.failed_seq}))
    return 0 if res.valid else 2


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))

