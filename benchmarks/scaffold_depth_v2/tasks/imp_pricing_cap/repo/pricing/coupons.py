"""Coupon codes and their discounts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


class UnknownCoupon(KeyError):
    """Raised for a coupon code that is not registered."""


@dataclass(frozen=True)
class Coupon:
    code: str
    discount_bps: int


class CouponBook:
    def __init__(self) -> None:
        self._coupons: Dict[str, Coupon] = {}

    def add(self, code: str, discount_bps: int) -> Coupon:
        coupon = Coupon(code.upper(), discount_bps)
        self._coupons[coupon.code] = coupon
        return coupon

    def get(self, code: str) -> Coupon:
        try:
            return self._coupons[code.upper()]
        except KeyError:
            raise UnknownCoupon(code) from None
