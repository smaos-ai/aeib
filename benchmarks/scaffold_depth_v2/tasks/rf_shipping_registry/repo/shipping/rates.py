"""Quote shipping cost for a parcel."""
from __future__ import annotations

from .errors import InvalidShipment, UnknownCarrier
from .zones import check_zone, with_zone


def quote(carrier: str, weight_g: int, zone: int) -> int:
    """Price in cents for sending `weight_g` grams to `zone` with `carrier`."""
    if isinstance(weight_g, bool) or not isinstance(weight_g, int) or weight_g <= 0:
        raise InvalidShipment(f"weight must be a positive int, got {weight_g!r}")
    check_zone(zone)
    if carrier == "postal":
        if weight_g > 2000:
            raise InvalidShipment("postal: max 2000 g")
        steps = (weight_g + 499) // 500
        return with_zone(390 + 150 * (steps - 1), zone)
    elif carrier == "express":
        if weight_g > 30000:
            raise InvalidShipment("express: max 30000 g")
        kilos = (weight_g + 999) // 1000
        return with_zone(1290 + 240 * kilos, zone) + (500 if zone >= 4 else 0)
    elif carrier == "freight":
        if weight_g < 10000:
            raise InvalidShipment("freight: min 10000 g")
        kilos = (weight_g + 999) // 1000
        return with_zone(max(4900, 85 * kilos), zone)
    elif carrier == "courier":
        if zone > 2:
            raise InvalidShipment("courier: zones 1-2 only")
        if weight_g > 10000:
            raise InvalidShipment("courier: max 10000 g")
        return 1800 + (weight_g // 2500) * 300
    raise UnknownCarrier(f"unknown carrier {carrier!r}")
