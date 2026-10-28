"""Tool 2: CompareJCSDigest — Computes RFC 8785 JSON Canonicalization Scheme hashes."""

import hashlib
import hmac
import json
from typing import Any, Dict, Optional


def _jcs_format_number(num: float) -> str:
    """ECMAScript 7.1.12.1 Number::toString per RFC 8785 Section 3.2.2.3.

    Port of SovereignNexus src/jcs_canonicalizer._format_jcs_number, kept local
    because the ocr_audit package ships standalone; parity is differential-tested
    in the SovereignNexus tests/test_jcs_single_source.py.
    """
    if num != num or num in (float("inf"), float("-inf")):
        raise ValueError("NaN and Infinity are not permitted in RFC 8785")
    if num == 0.0:
        return "0"
    if num < 0:
        return "-" + _jcs_format_number(-num)
    rep = repr(num)
    if "e" in rep:
        mantissa, exp_str = rep.split("e")
        exp = int(exp_str)
    else:
        mantissa, exp = rep, 0
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
    if k <= n <= 21:
        return digits + "0" * (n - k)
    if 0 < n <= 21:
        return digits[:n] + "." + digits[n:]
    if -6 < n <= 0:
        return "0." + "0" * (-n) + digits
    exp_sign = "+" if (n - 1) > 0 else ""
    if k == 1:
        return f"{digits}e{exp_sign}{n - 1}"
    return f"{digits[0]}.{digits[1:]}e{exp_sign}{n - 1}"


def _jcs_utf16_key(key: Any) -> bytes:
    if not isinstance(key, str):
        raise TypeError(f"RFC 8785 requires object keys to be strings, got {type(key).__name__}")
    return key.encode("utf-16-be")


def _jcs_serialize(val: Any) -> str:
    if val is None:
        return "null"
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, int):
        return str(val)
    if isinstance(val, float):
        return _jcs_format_number(val)
    if isinstance(val, str):
        return json.dumps(val, ensure_ascii=False)
    if isinstance(val, (list, tuple)):
        return "[" + ",".join(_jcs_serialize(x) for x in val) + "]"
    if isinstance(val, dict):
        return "{" + ",".join(
            f"{json.dumps(k, ensure_ascii=False)}:{_jcs_serialize(val[k])}"
            for k in sorted(val.keys(), key=_jcs_utf16_key)
        ) + "}"
    raise TypeError(f"Type {type(val).__name__} is not JSON serializable")


def _coerce_unknown_to_str(data: Any) -> Any:
    """Legacy CompareJCSDigest policy: non-JSON leaf types are hashed as str(data)."""
    if isinstance(data, dict):
        return {k: _coerce_unknown_to_str(v) for k, v in data.items()}
    if isinstance(data, (list, tuple)):
        return [_coerce_unknown_to_str(x) for x in data]
    if data is None or isinstance(data, (str, int, float, bool)):
        return data
    return str(data)


def jcs_canonicalize_strict(data: Any) -> bytes:
    """RFC 8785 canonical bytes; raises TypeError on non-JSON types."""
    return _jcs_serialize(data).encode("utf-8")


def jcs_canonicalize(data: Any) -> bytes:
    """Canonicalizes JSON according to RFC 8785 (JCS).

    Object keys are sorted by UTF-16 code units and numbers follow ECMAScript
    7.1.12.1. Non-JSON leaf values keep the legacy policy of hashing str(value).
    """
    return jcs_canonicalize_strict(_coerce_unknown_to_str(data))


def jcs_digest(data: Any) -> str:
    """Returns the hex SHA-256 digest of RFC 8785 canonical bytes."""
    return hashlib.sha256(jcs_canonicalize(data)).hexdigest()


def compare_jcs_digest(record: Dict[str, Any], expected_digest: Optional[str] = None) -> Dict[str, Any]:
    """Computes RFC 8785 hash deltas between dispatched payload and claimed digest."""
    payload_to_hash = {k: v for k, v in record.items() if not k.startswith("_")}
    computed = jcs_digest(payload_to_hash)
    claimed = expected_digest or record.get("expected_digest") or record.get("intent_digest")
    
    if not claimed:
        match = True
    else:
        try:
            match = hmac.compare_digest(computed.encode('utf-8').lower(), str(claimed).encode('utf-8').lower())
        except (TypeError, ValueError):
            match = False

    return {
        "computed_digest": computed,
        "claimed_digest": claimed,
        "match": match,
        "tampered": not match if claimed else False,
    }
