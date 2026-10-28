"""Cache key construction shared by every cached lookup in the package."""
from __future__ import annotations


def make_key(namespace: str, *parts: object) -> str:
    """Build a cache key for (namespace, *parts).

    Contract: distinct (namespace, parts) tuples of strings must give distinct keys, because the
    cache trusts the key alone.
    """
    if not namespace:
        raise ValueError("namespace must be non-empty")
    return namespace + ":" + ":".join(str(p) for p in parts)
