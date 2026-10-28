"""A small LRU cache keyed by strings."""
from __future__ import annotations

from collections import OrderedDict
from typing import Any, Callable, Optional


class LRUCache:
    def __init__(self, capacity: int = 128) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self._data: "OrderedDict[str, Any]" = OrderedDict()
        self.hits = 0
        self.misses = 0

    def __len__(self) -> int:
        return len(self._data)

    def get(self, key: str) -> Optional[Any]:
        if key in self._data:
            self._data.move_to_end(key)
            self.hits += 1
            return self._data[key]
        self.misses += 1
        return None

    def put(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._data.move_to_end(key)
        while len(self._data) > self.capacity:
            self._data.popitem(last=False)

    def delete(self, key: str) -> bool:
        return self._data.pop(key, None) is not None

    def get_or_load(self, key: str, loader: Callable[[], Any]) -> Any:
        if key in self._data:
            return self.get(key)
        self.misses += 1
        value = loader()
        self.put(key, value)
        return value
