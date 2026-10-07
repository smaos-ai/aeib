"""
SCITT COSE_Sign1 Envelope Verifier (RFC 8785 JCS + Ed25519)
Zero-dependency offline verification of Trust Passports.
"""
import json
import hashlib
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from pathlib import Path

# Single canonicalization source of truth. Two import forms are required because
# this module is reached three ways, and no single form covers all three:
#   * pytest / scripts  -> pythonpath = ". src" (pytest.ini): both work
#   * python3 src/cose_verifier.py (the __main__ block below): only bare works,
#     because sys.path[0] becomes <repo>/src and "src" itself is not importable
#   * from src.cose_verifier import ... with only the repo root on sys.path:
#     only the qualified form works
try:
    from src.jcs_canonicalizer import encode_jcs
except ImportError:  # direct script execution
    from jcs_canonicalizer import encode_jcs

def jcs_canonicalize(obj: dict) -> bytes:
    """
    RFC 8785 JSON Canonicalization Scheme (JCS).

    Delegates to jcs_canonicalizer.encode_jcs so the signer and the verifier
    share one canonicalization implementation. The previous inline version used
    json.dumps(sort_keys=True), which orders keys by Python code point instead
    of RFC 8785 Section 3.2.3 UTF-16 code units, and serialized floats per
    Python rules instead of ECMAScript 7.1.12.1 ("0.0" where JCS requires "0").

    No Unicode normalization is performed: RFC 8785 Section 3.1 requires
    preserved string data "as is". See jcs_canonicalizer.normalize_nfc for the
    opt-in AEIB pre-pass.
    """
    return encode_jcs(obj)

def verify_trust_passport(cose_payload: dict) -> bool:
    """
    Verifies the SCITT-ready COSE_Sign1-like structure offline.
    Raises ValueError if verification fails.
    Returns True if valid.
    """
    required_keys = ["payload_hash", "signature", "public_key_hex", "canonical_payload"]
    for k in required_keys:
        if k not in cose_payload:
            raise ValueError(f"Missing required key in COSE envelope: {k}")

    canonical_payload_str = cose_payload["canonical_payload"]
    try:
        payload_dict = json.loads(canonical_payload_str)
    except json.JSONDecodeError:
        raise ValueError("canonical_payload is not valid JSON")

    # Re-canonicalize to ensure no tampering with whitespace in the string
    re_canonicalized_bytes = jcs_canonicalize(payload_dict)
    
    # 1. Verify Hash
    computed_hash = hashlib.sha256(re_canonicalized_bytes).hexdigest()
    expected_hash = cose_payload["payload_hash"].replace("sha256:", "")
    
    if computed_hash != expected_hash:
        raise ValueError(f"Hash mismatch. Expected {expected_hash}, got {computed_hash}")
        
    # 2. Verify Signature
    public_key_bytes = bytes.fromhex(cose_payload["public_key_hex"])
    signature_bytes = bytes.fromhex(cose_payload["signature"])
    
    public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
    
    try:
        public_key.verify(signature_bytes, re_canonicalized_bytes)
    except InvalidSignature:
        raise ValueError("Cryptographic signature is invalid or payload was tampered with.")
        
    return True

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python src/cose_verifier.py <path_to_cose.json>")
        sys.exit(1)
        
    target_file = Path(sys.argv[1])
    if not target_file.exists():
        print(f"File not found: {target_file}")
        sys.exit(1)
        
    with open(target_file, "r") as f:
        envelope = json.load(f)
        
    try:
        verify_trust_passport(envelope)
        print(f"[✔] VALID: {target_file.name} signature, hash, and JCS canonical payload verified successfully.")
    except Exception as e:
        print(f"[✘] INVALID: {target_file.name} failed verification. Error: {e}")
        sys.exit(1)
