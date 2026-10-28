"""URL-safe base64 without padding, and compact JSON."""
from __future__ import annotations

import base64
import json
from typing import Any


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(text: str) -> bytes:
    """Inverse of b64url_encode. Raises binascii.Error / ValueError on malformed input."""
    pad = "=" * (-len(text) % 4)
    return base64.b64decode(text + pad, altchars=b"-_", validate=True)


def dumps(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
