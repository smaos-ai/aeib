from catalog.cache import LRUCache
from catalog.service import CatalogService
from catalog.store import CatalogStore


def test_lru_evicts_oldest():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    c.get("a")
    c.put("c", 3)
    assert c.get("b") is None and c.get("a") == 1 and len(c) == 2


def test_service_caches_reads():
    store = CatalogStore()
    store.set_price("pen", "eu", 250)
    svc = CatalogService(store)
    assert svc.get_price("pen", "eu") == 250
    assert svc.get_price("pen", "eu") == 250
    assert store.reads == 1


def test_update_invalidates():
    store = CatalogStore()
    store.set_price("pen", "eu", 250)
    svc = CatalogService(store)
    svc.get_price("pen", "eu")
    svc.update_price("pen", "eu", 300)
    assert svc.get_price("pen", "eu") == 300
