#!/usr/bin/env python3
"""
strict_json_ingress.py — strict JSON ingress parser (I-JSON, RFC 7493 profile).

Prototype helper for AEIB ingress points that later canonicalize payloads with
RFC 8785 (src/jcs_canonicalizer.encode_jcs). Python's json.loads silently keeps
the LAST value of a duplicated member name, so '{"to":"alice","to":"mallory"}'
parses to {"to": "mallory"}; a peer parser that keeps the FIRST value would see
a different object under the same bytes. loads_strict() fails closed instead.

Rules enforced (each raises StrictJSONError with a stable error code):
  * ERR_DUPLICATE_KEY        — duplicate member names in any object
                               (RFC 7493 Section 2.3, MUST NOT).
  * ERR_NON_FINITE_NUMBER    — NaN / Infinity / -Infinity literals (not JSON
                               per RFC 8259; rejected by RFC 8785), and
                               float literals that overflow to infinity.
  * ERR_FLOAT_FORBIDDEN      — any non-integer number literal when
                               integers_only=True (AEIB integer-bps policy).
  * ERR_INTEGER_OUT_OF_RANGE — integers outside the IEEE-754 safe range
                               (+/- 2**53 - 1) when integers_only=True
                               (RFC 7493 Section 2.2 interoperability limit).
  * ERR_LONE_SURROGATE       — strings containing unpaired UTF-16 surrogates
                               (RFC 7493 Section 2.1; RFC 8785 cannot encode).
  * ERR_INVALID_JSON         — any other json.JSONDecodeError.
  * ERR_INPUT_TYPE           — input is not str / bytes / bytearray.

Stdlib only. Not wired into any ingress path yet (scaffold).
"""

from __future__ import annotations

import json
import math
from typing import Any, List, Tuple, Union

MAX_SAFE_INTEGER = 2**53 - 1
DETAIL_LIMIT = 60  # max characters of offending input echoed in an error detail


class StrictJSONError(ValueError):
    """Raised when input violates the strict ingress profile."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def _has_lone_surrogate(s: str) -> bool:
    return any(0xD800 <= ord(ch) <= 0xDFFF for ch in s)


def _check_string(s: str) -> None:
    if _has_lone_surrogate(s):
        raise StrictJSONError("ERR_LONE_SURROGATE", repr(s)[:DETAIL_LIMIT])


def _reject_constant(name: str) -> Any:
    raise StrictJSONError("ERR_NON_FINITE_NUMBER", name)


def loads_strict(text: Union[str, bytes, bytearray], *, integers_only: bool = False) -> Any:
    """
    Parse JSON text under the strict I-JSON ingress profile described in the
    module docstring. Returns the parsed Python object on success.
    """
    if isinstance(text, (bytes, bytearray)):
        try:
            text = bytes(text).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise StrictJSONError("ERR_INVALID_JSON", f"input is not UTF-8: {exc}") from exc
    if not isinstance(text, str):
        raise StrictJSONError("ERR_INPUT_TYPE", type(text).__name__)

    def _pairs_hook(pairs: List[Tuple[str, Any]]) -> dict:
        obj: dict = {}
        for key, value in pairs:
            _check_string(key)
            if key in obj:
                raise StrictJSONError("ERR_DUPLICATE_KEY", repr(key)[:DETAIL_LIMIT])
            if isinstance(value, str):
                _check_string(value)
            obj[key] = value
        return obj

    def _parse_float(literal: str) -> float:
        if integers_only:
            raise StrictJSONError("ERR_FLOAT_FORBIDDEN", literal[:DETAIL_LIMIT])
        value = float(literal)
        if math.isinf(value):  # e.g. 1e400 overflows to inf in json.loads
            raise StrictJSONError("ERR_NON_FINITE_NUMBER", literal[:DETAIL_LIMIT])
        return value

    def _parse_int(literal: str) -> int:
        value = int(literal)
        if integers_only and abs(value) > MAX_SAFE_INTEGER:
            raise StrictJSONError("ERR_INTEGER_OUT_OF_RANGE", literal[:DETAIL_LIMIT])
        return value

    try:
        result = json.loads(
            text,
            object_pairs_hook=_pairs_hook,
            parse_constant=_reject_constant,
            parse_float=_parse_float,
            parse_int=_parse_int,
        )
    except StrictJSONError:
        raise
    except json.JSONDecodeError as exc:
        raise StrictJSONError("ERR_INVALID_JSON", str(exc)) from exc

    # Strings inside arrays and at top level are not seen by the pairs hook.
    _walk_strings(result)
    return result


def _walk_strings(value: Any) -> None:
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            _check_string(item)
        elif isinstance(item, list):
            stack.extend(item)
        elif isinstance(item, dict):
            stack.extend(item.values())
