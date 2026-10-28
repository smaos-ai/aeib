"""A cart applies at most one coupon to every line."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .coupons import CouponBook
from .discount import apply_discount
from .money import require_cents


@dataclass
class Cart:
    book: CouponBook
    lines: List[Tuple[str, int, int]] = field(default_factory=list)
    coupon_code: Optional[str] = None

    def add(self, sku: str, unit_cents: int, qty: int = 1) -> "Cart":
        require_cents(unit_cents)
        if qty <= 0:
            raise ValueError("qty must be positive")
        self.lines.append((sku, unit_cents, qty))
        return self

    def apply_coupon(self, code: str) -> None:
        self.book.get(code)
        self.coupon_code = code

    def line_total(self, unit_cents: int, qty: int) -> int:
        gross = unit_cents * qty
        if self.coupon_code is None:
            return gross
        return apply_discount(gross, self.book.get(self.coupon_code).discount_bps)

    def total_cents(self) -> int:
        return sum(self.line_total(u, q) for _sku, u, q in self.lines)
