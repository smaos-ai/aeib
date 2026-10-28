"""Scope checks on verified tokens."""
from __future__ import annotations

from typing import Any, Dict

from .errors import Forbidden
from .verify import verify_token


def scopes(claims: Dict[str, Any]) -> set:
    raw = claims.get("scope", "")
    return set(raw.split()) if isinstance(raw, str) else set()


def authorise(token: str, key: bytes, now: int, required_scope: str) -> Dict[str, Any]:
    claims = verify_token(token, key, now)
    if required_scope not in scopes(claims):
        raise Forbidden(required_scope)
    return claims
