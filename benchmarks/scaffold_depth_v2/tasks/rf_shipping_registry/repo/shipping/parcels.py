"""Parcels with volumetric weight, quoted through rates.quote."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from .errors import ShippingError
from .rates import quote

VOLUMETRIC_DIVISOR = 5000  # cm^3 per kg, a common courier convention


@dataclass(frozen=True)
class Parcel:
    weight_g: int
    length_cm: int
    width_cm: int
    height_cm: int

    def volumetric_g(self) -> int:
        volume = self.length_cm * self.width_cm * self.height_cm
        return -(-volume * 1000 // VOLUMETRIC_DIVISOR)

    def billable_g(self) -> int:
        return max(self.weight_g, self.volumetric_g())


def quote_parcel(carrier: str, parcel: Parcel, zone: int) -> int:
    return quote(carrier, parcel.billable_g(), zone)


def cheapest(carriers: List[str], parcel: Parcel, zone: int) -> Tuple[str, int]:
    """Cheapest carrier able to ship the parcel; ties go to the earlier carrier in the list."""
    offers: Dict[str, int] = {}
    for name in carriers:
        try:
            offers[name] = quote_parcel(name, parcel, zone)
        except ShippingError:
            continue
    if not offers:
        raise ShippingError("no carrier can ship this parcel")
    best = min(offers.values())
    return next((n, c) for n, c in offers.items() if c == best)
