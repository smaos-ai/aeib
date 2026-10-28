"""Operational report over the catalog service (read-only)."""
from __future__ import annotations

from typing import Iterable, List, Tuple

from .service import CatalogService
from .store import UnknownItem


def low_stock(svc: CatalogService, items: Iterable[Tuple[str, str]], threshold: int) -> List[str]:
    """SKUs whose stock in the given warehouse is below `threshold`; unknown items are skipped."""
    out = []
    for sku, warehouse in items:
        try:
            if svc.get_stock(sku, warehouse) < threshold:
                out.append(sku)
        except UnknownItem:
            continue
    return sorted(out)


def cache_summary(svc: CatalogService) -> str:
    c = svc.cache
    total = c.hits + c.misses
    rate_bps = (c.hits * 10000 // total) if total else 0
    return f"entries={len(c)} hits={c.hits} misses={c.misses} hit_rate_bps={rate_bps}"
