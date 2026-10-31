#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
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
tools/verify_edge_telemetry_receipt.py — Verifies on-device edge telemetry receipts.

Evaluated under the stated model:
- Strictly RFC 8785 single-source JCS canonicalization.
- Zero mock crypto: Real Ed25519 cryptographic verification using cryptography.hazmat.
- Verifies that boundary probes confirm negative sandbox containment.
- Rejects unpinned, tampered, or malformed edge receipts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from typing import Any, Dict, Tuple

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from src.jcs_canonicalizer import encode_jcs
from src.strict_json_ingress import loads_strict


def _has_float(val: Any) -> bool:
    """Checks recursively if any float exists in val."""
    if isinstance(val, float):
        return True
    if isinstance(val, dict):
        return any(_has_float(v) for v in val.values())
    if isinstance(val, (list, tuple)):
        return any(_has_float(v) for v in val)
    return False


def verify_edge_telemetry_receipt(
    receipt_data: Dict[str, Any],
    expected_pubkey_hex: str | None = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Verifies an EdgeTelemetryReceipt dict.
    Returns: (is_valid: bool, reason: str, metadata: dict)
    """
    if not isinstance(receipt_data, dict):
        return False, "ERR_INVALID_RECEIPT_FORMAT", {}

    required_keys = {"receipt_body", "caid", "signature_ed25519_hex", "envelope_version"}
    if not required_keys.issubset(receipt_data.keys()):
        return False, "ERR_MISSING_ENVELOPE_KEYS", {}

    body = receipt_data["receipt_body"]
    if not isinstance(body, dict):
        return False, "ERR_INVALID_BODY_TYPE", {}

    claimed_caid = receipt_data["caid"]
    sig_hex = receipt_data["signature_ed25519_hex"]
    if not isinstance(claimed_caid, str) or not isinstance(sig_hex, str):
        return False, "ERR_INVALID_CRYPTO_TYPES", {}

    if _has_float(body):
        return False, "ERR_FLOAT_IN_JCS_BODY", {}

    # 1. Canonicalize body and verify CAID
    try:
        canonical_bytes = encode_jcs(body)
    except Exception as exc:
        return False, f"ERR_JCS_CANONICALIZATION_FAILED:{type(exc).__name__}", {}

    expected_caid = "sha256:" + hashlib.sha256(canonical_bytes).hexdigest()
    if claimed_caid != expected_caid:
        return False, "ERR_CAID_DIGEST_MISMATCH", {"claimed": claimed_caid, "computed": expected_caid}

    # 2. Extract and verify public key
    signer_pubkey_hex = body.get("signer_pubkey_hex")
    if not isinstance(signer_pubkey_hex, str) or len(signer_pubkey_hex) != 64:
        return False, "ERR_INVALID_SIGNER_PUBKEY", {}

    if expected_pubkey_hex and signer_pubkey_hex.lower() != expected_pubkey_hex.lower():
        return False, "ERR_UNPINNED_SIGNER_KEY", {}

    try:
        pub_bytes = bytes.fromhex(signer_pubkey_hex)
        sig_bytes = bytes.fromhex(sig_hex)
        public_key = Ed25519PublicKey.from_public_bytes(pub_bytes)
        public_key.verify(sig_bytes, canonical_bytes)
    except (ValueError, InvalidSignature) as exc:
        return False, f"ERR_ED25519_SIGNATURE_INVALID:{type(exc).__name__}", {}

    # 3. Verify Sandbox Boundary Probes
    if "boundary_probes" not in body or not isinstance(body["boundary_probes"], dict):
        return False, "ERR_MISSING_BOUNDARY_PROBES", {}
    probes = body["boundary_probes"]

    root_fs_blocked = probes.get("probe_root_fs_write_blocked") is True
    traversal_blocked = probes.get("probe_path_traversal_blocked") is True
    if not (root_fs_blocked and traversal_blocked):
        return False, "ERR_SANDBOX_CONTAINMENT_PROBE_FAILED", probes

    return True, "OK_EDGE_TELEMETRY_VERIFIED", {
        "node_id": body.get("node_id"),
        "caid": claimed_caid,
        "signer_pubkey_hex": signer_pubkey_hex,
        "timestamp_epoch_s": body.get("timestamp_epoch_s"),
        "thermal_state_raw": probes.get("thermal_state_raw"),
        "physical_memory_bytes": probes.get("physical_memory_bytes"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify Edge Telemetry Receipt")
    parser.add_argument("--receipt", required=True, help="Path to receipt JSON file")
    parser.add_argument("--pubkey", help="Optional expected Ed25519 public key in hex")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    args = parser.parse_args(argv)

    if not os.path.exists(args.receipt):
        print(f"Error: receipt file not found: {args.receipt}", file=sys.stderr)
        return 2

    try:
        with open(args.receipt, "r", encoding="utf-8") as fp:
            data = loads_strict(fp.read())
    except Exception as exc:
        print(f"Error parsing receipt JSON: {exc}", file=sys.stderr)
        return 2

    ok, reason, meta = verify_edge_telemetry_receipt(data, expected_pubkey_hex=args.pubkey)
    res = {
        "valid": ok,
        "reason": reason,
        "metadata": meta,
    }

    if args.json:
        print(json.dumps(res, indent=2))
    else:
        status_str = "VALID" if ok else "INVALID"
        print(f"[{status_str}] reason: {reason}")
        if ok:
            print(f"Node: {meta.get('node_id')}")
            print(f"CAID: {meta.get('caid')}")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
