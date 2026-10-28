"""Cached catalog service."""
from __future__ import annotations

from .cache import LRUCache
from .keys import make_key
from .store import CatalogStore


class CatalogService:
    def __init__(self, store: CatalogStore, cache: LRUCache | None = None) -> None:
        self.store = store
        self.cache = cache if cache is not None else LRUCache()

    def get_price(self, sku: str, region: str) -> int:
        key = make_key("price", sku, region)
        return self.cache.get_or_load(key, lambda: self.store.price(sku, region))

    def get_stock(self, sku: str, warehouse: str) -> int:
        key = make_key("stock", sku, warehouse)
        return self.cache.get_or_load(key, lambda: self.store.stock(sku, warehouse))

    def update_price(self, sku: str, region: str, cents: int) -> None:
        self.store.set_price(sku, region, cents)
        self.cache.delete(make_key("price", sku, region))
