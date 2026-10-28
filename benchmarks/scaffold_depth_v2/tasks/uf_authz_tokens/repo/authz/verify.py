"""Token verification."""
from __future__ import annotations

from typing import Any, Dict

from .encoding import b64url_decode
from .errors import ExpiredToken, InvalidToken
from .signing import HEADER, mac, signing_input


def verify_token(token: str, key: bytes, now: int) -> Dict[str, Any]:
    """Return the claims of a valid token produced by signing.sign."""
    raise NotImplementedError("verify_token")
