"""Backing store for prices (integer cents) and stock levels."""
from __future__ import annotations

from typing import Dict, Tuple


class UnknownItem(KeyError):
    """Raised when a SKU has no entry for the requested region or warehouse."""


class CatalogStore:
    def __init__(self) -> None:
        self._prices: Dict[Tuple[str, str], int] = {}
        self._stock: Dict[Tuple[str, str], int] = {}
        self.reads = 0

    def set_price(self, sku: str, region: str, cents: int) -> None:
        if not isinstance(cents, int) or cents < 0:
            raise ValueError("price must be a non-negative int")
        self._prices[(sku, region)] = cents

    def set_stock(self, sku: str, warehouse: str, units: int) -> None:
        self._stock[(sku, warehouse)] = units

    def price(self, sku: str, region: str) -> int:
        self.reads += 1
        try:
            return self._prices[(sku, region)]
        except KeyError:
            raise UnknownItem((sku, region)) from None

    def stock(self, sku: str, warehouse: str) -> int:
        self.reads += 1
        try:
            return self._stock[(sku, warehouse)]
        except KeyError:
            raise UnknownItem((sku, warehouse)) from None
