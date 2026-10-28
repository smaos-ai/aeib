# Fixture (intentionally bad): CI005 private keys derived from source literals.
import hashlib

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

SEED_BYTES = b"\x01" * 32


def demo_signer():
    return Ed25519PrivateKey.from_private_bytes(hashlib.sha256(b"SOVEREIGN_DEMO_SEED").digest())


def fixed_signer():
    return Ed25519PrivateKey.from_private_bytes(SEED_BYTES)


def hex_signer():
    return Ed25519PrivateKey.from_private_bytes(bytes.fromhex("11" * 32))
