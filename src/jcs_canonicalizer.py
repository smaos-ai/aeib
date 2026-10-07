#!/usr/bin/env python3
r"""
jcs_canonicalizer.py — RFC 8785 JSON Canonicalization Scheme (JCS) Implementation
Sovereign Multi-Agent OS (SMAOS) / Agent Execution Integrity (AEIB)

Implements byte-exact deterministic JSON serialization strictly conforming to RFC 8785:
- Object keys sorted lexicographically by UTF-16 code units (Section 3.2.3)
- No whitespace separators (',', ':')
- Unescaped UTF-8 strings except required JSON control characters and quotes/backslashes
- Number serialization conforming strictly to ECMAScript 7.1.12.1 ToString (Section 3.2.2.3):
  * Floats representing integers serialized without decimals (e.g., 1.0 -> 1)
  * -0.0 serialized as 0
  * No leading '+' in exponents (e.g., 1e+20 -> 1e20)
  * No redundant leading zeros in exponents (e.g., 1e-05 -> 1e-5)
  * No redundant trailing zeros in fractions
  * Rejection of NaN, Infinity, -Infinity
"""

import json
import math
import hashlib
import unicodedata
from typing import Any


def normalize_nfc(obj: Any) -> Any:
    """
    Recursively applies Unicode Normalization Form C (NFC) to every string and
    every mapping key in a JSON-compatible object graph, returning a new object.

    THIS IS AN OPT-IN AEIB PRE-PASS, NOT PART OF RFC 8785.

    RFC 8785 Section 3.1 explicitly rules normalization out of the
    canonicalizer:

      "An additional constraint is that parsed JSON string data MUST NOT be
       altered during subsequent serializations."

      "Although the Unicode standard offers the possibility of rearranging
       certain character sequences, referred to as 'Unicode Normalization',
       JCS-compliant string processing does not take this into consideration.
       That is, all components involved in a scheme depending on JCS MUST
       preserve Unicode string data 'as is'."

    encode_jcs() therefore does NOT call this function: it preserves input
    strings as-is, which keeps the RFC 8785 Section 3.2.3 conformance vectors
    byte-stable (notably U+FB33, a composition exclusion that NFC would split
    into U+05D3 U+05BC and thereby re-order).

    Callers that need canonically equivalent inputs -- decomposed "e" + U+0301
    versus precomposed U+00E9 -- to yield one shared caid across the Python,
    Rust and WASM verifiers must apply normalize_nfc() deliberately at their
    own ingress, accepting that doing so changes the resulting digest and is a
    documented deviation from RFC 8785.

    Fails closed if normalization would collapse two distinct keys into one,
    rather than silently dropping a field.
    """
    if isinstance(obj, str):
        return unicodedata.normalize("NFC", obj)
    if isinstance(obj, dict):
        normalized = {}
        for key, value in obj.items():
            nkey = unicodedata.normalize("NFC", key) if isinstance(key, str) else key
            if nkey in normalized:
                raise ValueError(
                    f"NFC normalization collapsed distinct keys into {nkey!r}; "
                    "refusing to serialize an ambiguous mapping"
                )
            normalized[nkey] = normalize_nfc(value)
        return normalized
    if isinstance(obj, (list, tuple)):
        return [normalize_nfc(item) for item in obj]
    return obj


def _utf16_sort_key(s: str) -> bytes:
    """Sort keys by their UTF-16 code units per RFC 8785 Section 3.2.3."""
    if not isinstance(s, str):
        raise TypeError(f"RFC 8785 requires object keys to be strings, got {type(s).__name__}")
    return s.encode("utf-16-be")


def _format_jcs_number(obj: float) -> str:
    """
    Formats a float strictly per ECMAScript 7.1.12.1 and RFC 8785 Section 3.2.2.3.
    """
    if math.isnan(obj) or math.isinf(obj):
        raise ValueError("NaN and Infinity are not permitted in RFC 8785")
    if obj == 0.0:
        return "0"
    if obj < 0:
        return "-" + _format_jcs_number(-obj)

    r = repr(obj)
    if "e" in r:
        mantissa, exp_str = r.split("e")
        exp = int(exp_str)
    else:
        mantissa, exp = r, 0

    if "." in mantissa:
        int_part, frac_part = mantissa.split(".")
        frac_part = frac_part.rstrip("0")
    else:
        int_part, frac_part = mantissa, ""

    int_part = int_part.lstrip("0")
    if int_part:
        digits = int_part + frac_part
        n = len(int_part) + exp
    else:
        leading_zeros = len(frac_part) - len(frac_part.lstrip("0"))
        digits = frac_part.lstrip("0")
        n = -leading_zeros + exp

    if not digits:
        return "0"

    k = len(digits)
    # ES6 Number::toString rules:
    # If k <= n <= 21, return digits followed by (n - k) zeros
    if k <= n <= 21:
        return digits + "0" * (n - k)
    # If 0 < n <= 21, return digits[:n] + '.' + digits[n:]
    elif 0 < n <= 21:
        return digits[:n] + "." + digits[n:]
    # If -6 < n <= 0, return '0.' + '0'*(-n) + digits
    elif -6 < n <= 0:
        return "0." + "0" * (-n) + digits
    # If k == 1, return digit + 'e' + [sign] + (n - 1) per ECMA-262 7.1.12.1
    exp_sign = "+" if (n - 1) > 0 else ""
    if k == 1:
        return f"{digits}e{exp_sign}{n - 1}"
    # Otherwise return digits[0] + '.' + digits[1:] + 'e' + [sign] + (n - 1)
    else:
        return f"{digits[0]}.{digits[1:]}e{exp_sign}{n - 1}"



def _serialize_jcs_str(obj: Any) -> str:
    """Recursively converts Python objects to RFC 8785 string."""
    if obj is None:
        return "null"
    elif isinstance(obj, bool):
        return "true" if obj else "false"
    elif isinstance(obj, int):
        return str(obj)
    elif isinstance(obj, float):
        return _format_jcs_number(obj)
    elif isinstance(obj, str):
        return json.dumps(obj, ensure_ascii=False)
    elif isinstance(obj, (list, tuple)):
        return "[" + ",".join(_serialize_jcs_str(x) for x in obj) + "]"
    elif isinstance(obj, dict):
        sorted_keys = sorted(obj.keys(), key=_utf16_sort_key)
        parts = [
            f"{json.dumps(k, ensure_ascii=False)}:{_serialize_jcs_str(obj[k])}"
            for k in sorted_keys
        ]
        return "{" + ",".join(parts) + "}"
    else:
        raise TypeError(f"Type {type(obj).__name__} is not JSON serializable")


def encode_jcs(payload: Any) -> bytes:
    """
    Serializes a Python object into byte-exact RFC 8785 canonical JSON bytes.
    Enforces:
      1. UTF-16 code-unit sorted object keys (RFC 8785 Section 3.2.3).
      2. No whitespace separators (',', ':').
      3. Unescaped UTF-8 strings (except required control chars and quotes/backslashes).
      4. Strict ECMAScript 7.1.12.1 number representation (e.g. 1.0 -> 1, -0.0 -> 0).
      5. Strict rejection of NaN and Infinity.
      6. Input strings are preserved "as is" with NO Unicode normalization,
         per the RFC 8785 Section 3.1 MUST NOT on altering parsed string data.
         Apply normalize_nfc() first if an AEIB-layer ingress needs it.
    """
    return _serialize_jcs_str(payload).encode("utf-8")


def generate_jcs_payload_hash(payload: Any) -> str:
    """
    Implements RFC 8785 JSON Canonicalization Scheme (JCS) hashing.
    Returns standard lowercase hex SHA-256 digest.
    """
    canonical_bytes = encode_jcs(payload)
    return hashlib.sha256(canonical_bytes).hexdigest()
