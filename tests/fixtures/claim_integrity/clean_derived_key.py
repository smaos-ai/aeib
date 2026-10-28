# Fixture (clean): keys from runtime entropy or caller-supplied material.
import hashlib
import os

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def fresh_key():
    return Ed25519PrivateKey.generate()


def random_key():
    return Ed25519PrivateKey.from_private_bytes(os.urandom(32))


def env_key():
    secret = os.environ["AEIB_SIGNING_SEED"].encode()
    return Ed25519PrivateKey.from_private_bytes(hashlib.sha256(secret).digest())


def key_from(seed):
    return Ed25519PrivateKey.from_private_bytes(seed)
