"""Integer-cent helpers."""
from __future__ import annotations


def require_cents(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("cents must be int")
    if value < 0:
        raise ValueError("cents must be >= 0")
    return value


def format_cents(cents: int) -> str:
    whole, frac = divmod(cents, 100)
    return f"{whole}.{frac:02d}"
