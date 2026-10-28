"""Money helpers. The ledger stores integer cents only; floats are never accepted."""
from __future__ import annotations


def require_cents(value: object, *, allow_zero: bool = False) -> int:
    """Return `value` if it is a valid cents amount, else raise TypeError / ValueError."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"cents must be int, got {type(value).__name__}")
    if value < 0 or (value == 0 and not allow_zero):
        raise ValueError(f"invalid cents amount: {value}")
    return value


def format_cents(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    whole, frac = divmod(abs(cents), 100)
    return f"{sign}{whole}.{frac:02d}"
