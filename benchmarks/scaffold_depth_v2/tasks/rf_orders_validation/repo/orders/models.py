"""Order model and validation error."""
from __future__ import annotations

from dataclasses import dataclass


class ValidationError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(f"{field}: {message}")
        self.field = field
        self.message = message


@dataclass(frozen=True)
class Order:
    id: int
    sku: str
    quantity: int
    unit_price_cents: int
    currency: str
    note: str = ""

    def total_cents(self) -> int:
        return self.quantity * self.unit_price_cents
