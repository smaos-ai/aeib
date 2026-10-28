"""Tax computation in basis points with half-up rounding on integer cents."""
from __future__ import annotations


def tax_cents(net_cents: int, rate_bps: int) -> int:
    """Tax on a net amount; rate in basis points (2000 = 20%). Rounds half up, away from zero."""
    if rate_bps < 0:
        raise ValueError("rate_bps must be >= 0")
    magnitude = (abs(net_cents) * rate_bps + 5000) // 10000
    return -magnitude if net_cents < 0 else magnitude


def gross_cents(net_cents: int, rate_bps: int) -> int:
    return net_cents + tax_cents(net_cents, rate_bps)
