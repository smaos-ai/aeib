"""Token issuance: header.payload.signature, HMAC-SHA256 over 'header.payload'."""
from __future__ import annotations

import hashlib
import hmac
from typing import Any, Dict

from .encoding import b64url_encode, dumps

HEADER = {"alg": "HS256", "typ": "TOK"}


def signing_input(header_b64: str, payload_b64: str) -> bytes:
    return f"{header_b64}.{payload_b64}".encode("ascii")


def mac(key: bytes, data: bytes) -> bytes:
    return hmac.new(key, data, hashlib.sha256).digest()


def sign(claims: Dict[str, Any], key: bytes) -> str:
    if not key:
        raise ValueError("empty key")
    header_b64 = b64url_encode(dumps(HEADER))
    payload_b64 = b64url_encode(dumps(claims))
    sig = mac(key, signing_input(header_b64, payload_b64))
    return f"{header_b64}.{payload_b64}.{b64url_encode(sig)}"
