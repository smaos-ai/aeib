# src/cose_signer.py
"""
SCITT COSE_Sign1 Envelope Generator (RFC 8785 JCS + Ed25519)
"""
import json
import hashlib
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from pathlib import Path

# Single canonicalization source of truth, shared with cose_verifier. Two import
# forms are required because this module is reached both as src.cose_signer
# (scripts, tests) and as a sibling module when sys.path[0] is <repo>/src.
try:
    from src.jcs_canonicalizer import encode_jcs
except ImportError:  # direct script execution
    from jcs_canonicalizer import encode_jcs

def jcs_canonicalize(obj: dict) -> bytes:
    """
    RFC 8785 JSON Canonicalization Scheme (JCS).

    Delegates to jcs_canonicalizer.encode_jcs. Keys are ordered by UTF-16 code
    units (RFC 8785 Section 3.2.3) and floats follow ECMAScript 7.1.12.1, so no
    Unicode normalization is performed -- RFC 8785 Section 3.1 requires string
    data be preserved "as is". This MUST stay byte-identical to the verifier's
    copy, otherwise signatures produced here cannot be verified there.
    """
    return encode_jcs(obj)

def generate_keypair(key_path: Path = Path("smaos_signing_key.pem")) -> Ed25519PrivateKey:
    """Generate or load an Ed25519 private key for signing."""
    if key_path.exists():
        private_key_bytes = key_path.read_bytes()
        return serialization.load_pem_private_key(private_key_bytes, password=None)
    else:
        private_key = Ed25519PrivateKey.generate()
        key_path.write_bytes(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))
        return private_key

def sign_trust_passport(trust_passport: dict, private_key: Ed25519PrivateKey) -> dict:
    """
    Signs the Trust Passport and returns a SCITT-ready COSE_Sign1-like structure.
    """
    # 1. Canonicalize payload (JCS)
    payload_bytes = jcs_canonicalize(trust_passport)
    
    # 2. Compute SHA-256 digest of canonical payload
    payload_hash = hashlib.sha256(payload_bytes).hexdigest()
    
    # 3. Sign the canonical payload
    signature = private_key.sign(payload_bytes)
    
    # 4. Construct the verifiable envelope
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    
    return {
        "version": "0.3.0",
        "content_type": "application/scitt-statement+cose",
        "payload_hash": f"sha256:{payload_hash}",
        "signature_algorithm": "EdDSA (Ed25519)",
        "signature": signature.hex(),
        "public_key_hex": public_key.hex(),
        "canonical_payload": payload_bytes.decode('utf-8') # For offline verification
    }
