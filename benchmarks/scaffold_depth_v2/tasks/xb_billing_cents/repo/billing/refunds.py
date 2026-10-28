"""Refunds against an invoice. Refund amounts are typed in by support staff."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .invoice import Invoice
from .money import parse_amount


class RefundError(ValueError):
    """Raised when a refund is not allowed."""


@dataclass
class RefundBook:
    invoice: Invoice
    refunds: List[int] = field(default_factory=list)

    def refunded_cents(self) -> int:
        return sum(self.refunds)

    def remaining_cents(self) -> int:
        return self.invoice.total_cents() - self.refunded_cents()

    def refund(self, amount_text: str) -> int:
        """Record a refund given as a decimal string; returns the refunded cents."""
        cents = parse_amount(amount_text)
        if cents <= 0:
            raise RefundError("refund must be positive")
        if cents > self.remaining_cents():
            raise RefundError("refund exceeds remaining balance")
        self.refunds.append(cents)
        return cents
