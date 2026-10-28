"""Storage quota accounting based on the index."""
from __future__ import annotations

from .index import Index


class QuotaExceeded(Exception):
    """Storing the blob would exceed the quota."""


class Quota:
    def __init__(self, index: Index, max_bytes: int) -> None:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        self.index = index
        self.max_bytes = max_bytes

    def used(self) -> int:
        return sum(self.index.load().values())

    def check(self, name: str, size: int) -> None:
        """Raise QuotaExceeded if replacing/adding `name` with `size` bytes exceeds the quota."""
        current = self.index.load()
        projected = self.used() - current.get(name, 0) + size
        if projected > self.max_bytes:
            raise QuotaExceeded(f"{projected} > {self.max_bytes}")

    def remaining(self) -> int:
        return max(0, self.max_bytes - self.used())
