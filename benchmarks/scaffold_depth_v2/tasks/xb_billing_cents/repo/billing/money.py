"""Money helpers. Amounts are integer cents throughout the package."""
from __future__ import annotations


class MoneyFormatError(ValueError):
    """Raised when an amount string cannot be parsed."""


def parse_amount(text: str) -> int:
    """Parse a decimal string such as '19.99', '7' or '-3.5' into integer cents.

    At most two decimal places are accepted; anything else raises MoneyFormatError.
    """
    if not isinstance(text, str):
        raise MoneyFormatError(f"expected str, got {type(text).__name__}")
    s = text.strip()
    if not s:
        raise MoneyFormatError("empty amount")
    if "." in s and len(s.split(".", 1)[1]) > 2:
        raise MoneyFormatError(f"too many decimal places: {text!r}")
    try:
        value = float(s)
    except ValueError as exc:
        raise MoneyFormatError(f"not a number: {text!r}") from exc
    return int(value * 100)


def format_cents(cents: int) -> str:
    """Render integer cents as a decimal string, e.g. 1999 -> '19.99', -5 -> '-0.05'."""
    if not isinstance(cents, int) or isinstance(cents, bool):
        raise TypeError("cents must be int")
    sign = "-" if cents < 0 else ""
    whole, frac = divmod(abs(cents), 100)
    return f"{sign}{whole}.{frac:02d}"
