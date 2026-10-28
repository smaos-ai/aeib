"""Zone surcharges in basis points (10000 = no surcharge)."""
from __future__ import annotations

from .errors import InvalidShipment

ZONE_BPS = {1: 10000, 2: 11500, 3: 13000, 4: 16000, 5: 21000}


def check_zone(zone: int) -> int:
    if isinstance(zone, bool) or not isinstance(zone, int) or zone not in ZONE_BPS:
        raise InvalidShipment(f"unknown zone {zone!r}")
    return zone


def with_zone(cents: int, zone: int) -> int:
    """Apply the zone surcharge, rounding half up."""
    return (cents * ZONE_BPS[zone] + 5000) // 10000
