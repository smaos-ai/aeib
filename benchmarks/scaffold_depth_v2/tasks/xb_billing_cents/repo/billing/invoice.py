"""Invoices made of lines whose prices are entered by staff as decimal strings."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .money import parse_amount
from .tax import tax_cents


@dataclass(frozen=True)
class Line:
    sku: str
    unit_price: str
    quantity: int

    def net_cents(self) -> int:
        if self.quantity < 0:
            raise ValueError("quantity must be >= 0")
        return parse_amount(self.unit_price) * self.quantity


@dataclass
class Invoice:
    number: str
    tax_bps: int = 0
    lines: List[Line] = field(default_factory=list)

    def add(self, sku: str, unit_price: str, quantity: int = 1) -> "Invoice":
        self.lines.append(Line(sku, unit_price, quantity))
        return self

    def subtotal_cents(self) -> int:
        return sum(line.net_cents() for line in self.lines)

    def tax_cents(self) -> int:
        return tax_cents(self.subtotal_cents(), self.tax_bps)

    def total_cents(self) -> int:
        return self.subtotal_cents() + self.tax_cents()
