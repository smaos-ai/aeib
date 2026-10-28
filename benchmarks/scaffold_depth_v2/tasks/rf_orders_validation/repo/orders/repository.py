"""In-memory order repository."""
from __future__ import annotations

from typing import Dict, Iterator

from .models import Order


class OrderRepository:
    def __init__(self) -> None:
        self._orders: Dict[int, Order] = {}
        self._next_id = 1

    def next_id(self) -> int:
        oid = self._next_id
        self._next_id += 1
        return oid

    def save(self, order: Order) -> Order:
        self._orders[order.id] = order
        return order

    def get(self, order_id: int) -> Order:
        return self._orders[order_id]

    def __iter__(self) -> Iterator[Order]:
        return iter(sorted(self._orders.values(), key=lambda o: o.id))
