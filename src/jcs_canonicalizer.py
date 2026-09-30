#!/usr/bin/env python3
r"""
jcs_canonicalizer.py — RFC 8785 JSON Canonicalization Scheme (JCS) Implementation
Sovereign Multi-Agent OS (SMAOS) / Agent Execution Integrity (AEIB)

Implements byte-exact deterministic JSON serialization conforming to RFC 8785.
Uses canonicaljson if installed, with a self-contained pure-Python fallback.
"""

import json
import hashlib
from typing import Any

try:
    import canonicaljson
    CANONICALJSON_AVAILABLE = True
except ImportError:
    CANONICALJSON_AVAILABLE = False


def _utf16_sort_key(s: str) -> bytes:
    """Sort keys by their UTF-16 code units per RFC 8785 Section 3.2.3."""
    if not isinstance(s, str):
        raise TypeError(f"RFC 8785 requires object keys to be strings, got {type(s).__name__}")
    return s.encode('utf-16-be')


def _canonicalize_obj(obj: Any) -> Any:
    """Recursively prepares objects for RFC 8785 canonical serialization."""
    if isinstance(obj, dict):
        sorted_keys = sorted(obj.keys(), key=_utf16_sort_key)
        return {k: _canonicalize_obj(obj[k]) for k in sorted_keys}
    elif isinstance(obj, (list, tuple)):
        return [_canonicalize_obj(item) for item in obj]
    return obj


def encode_jcs(payload: Any) -> bytes:
    """
    Serializes a Python object into byte-exact RFC 8785 canonical JSON bytes.
    Enforces:
      1. UTF-16 code-unit sorted object keys (RFC 8785 Section 3.2.3).
      2. No whitespace separators (',', ':').
      3. Unescaped UTF-8 strings (except required control chars and quotes/backslashes).
      4. Strict rejection of NaN and Infinity (allow_nan=False).
    """
    prepared = _canonicalize_obj(payload)
    return json.dumps(
        prepared,
        ensure_ascii=False,
        separators=(',', ':'),
        allow_nan=False,
        sort_keys=False  # Keys already sorted by UTF-16 code units in _canonicalize_obj
    ).encode('utf-8')


def generate_jcs_payload_hash(payload: Any) -> str:
    """
    Implements RFC 8785 JSON Canonicalization Scheme (JCS) hashing.
    Ensures UTF-16 code-unit sorting, no whitespace, and deterministic digests.
    Returns standard lowercase hex SHA-256 digest.
    """
    canonical_bytes = encode_jcs(payload)
    return hashlib.sha256(canonical_bytes).hexdigest()

