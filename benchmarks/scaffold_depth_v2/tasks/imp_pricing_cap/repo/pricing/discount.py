"""Percentage discounts expressed in basis points (10000 bps = 100%)."""
from __future__ import annotations

from .money import require_cents

MAX_DISCOUNT_BPS = 5000


def discount_off(price_cents: int, discount_bps: int) -> int:
    """Cents taken off `price_cents` by a discount of `discount_bps` (rounded down)."""
    require_cents(price_cents)
    if isinstance(discount_bps, bool) or not isinstance(discount_bps, int) or not 0 <= discount_bps <= 10000:
        raise ValueError("discount_bps must be an int in [0, 10000]")
    return price_cents * discount_bps // 10000


def apply_discount(price_cents: int, discount_bps: int) -> int:
    """Price after the discount."""
    return price_cents - discount_off(price_cents, discount_bps)
