#!/usr/bin/env python3
"""
AEIB RFC 9052 COSE_Sign1 & SCITT Transparency Receipt Verifier.
Part of SovereignNexus AEIB v1.1 Architecture.

Verifies:
- RFC 9052 COSE_Sign1 CBOR envelopes (Tag 18)
- Exact Ed25519 signature over canonical Sig_structure
- RFC 8785 JCS inner receipt payload integrity
- External AAD binding (e.g. Merkle checkpoint root)
"""

import sys
import json
import base64
import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import importlib.util

ROADMAP_COSE_PATH = REPO_ROOT / "v1.1-roadmap" / "rfc9052_cose_profile.py"
cose_spec = importlib.util.spec_from_file_location("rfc9052_cose_profile", ROADMAP_COSE_PATH)
if cose_spec is None or cose_spec.loader is None:
    raise ImportError(f"Cannot load {ROADMAP_COSE_PATH}")
cose_mod = importlib.util.module_from_spec(cose_spec)
sys.modules["rfc9052_cose_profile"] = cose_mod
cose_spec.loader.exec_module(cose_mod)

RFC9052CoseVerifier = cose_mod.RFC9052CoseVerifier
RFC9052CoseSigner = cose_mod.RFC9052CoseSigner

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from src.jcs_canonicalizer import encode_jcs


def load_public_key(pubkey_str: str) -> ed25519.Ed25519PublicKey:
    path = Path(pubkey_str)
    if path.exists():
        data = path.read_bytes()
        try:
            return serialization.load_pem_public_key(data)
        except Exception:
            return ed25519.Ed25519PublicKey.from_public_bytes(data)
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


def main():
    parser = argparse.ArgumentParser(description="AEIB RFC 9052 COSE_Sign1 Receipt Verifier")
    parser.add_argument("--envelope", required=True, help="Path to COSE_Sign1 CBOR binary envelope (.cose)")
    parser.add_argument("--public-key", required=True, help="Path to Ed25519 public key PEM or raw bytes")
    parser.add_argument("--aad", default="", help="Optional external AAD (hex string or utf-8)")

    args = parser.parse_args()

    envelope_path = Path(args.envelope)
    if not envelope_path.exists():
        print(f"[-] Envelope file not found: {args.envelope}", file=sys.stderr)
        sys.exit(1)

    envelope_bytes = envelope_path.read_bytes()
    pubkey = load_public_key(args.public_key)

    aad_bytes = b""
    if args.aad:
        try:
            aad_bytes = bytes.fromhex(args.aad)
        except ValueError:
            aad_bytes = args.aad.encode("utf-8")

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
