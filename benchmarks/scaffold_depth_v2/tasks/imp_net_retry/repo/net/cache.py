"""A response cache in front of Client.fetch (successful bodies only)."""
from __future__ import annotations

from typing import Dict

from .client import Client


class CachingClient:
    def __init__(self, client: Client, max_entries: int = 64) -> None:
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        self.client = client
        self.max_entries = max_entries
        self._bodies: Dict[str, str] = {}

    def fetch(self, path: str) -> str:
        if path in self._bodies:
            return self._bodies[path]
        body = self.client.fetch(path)
        if len(self._bodies) >= self.max_entries:
            self._bodies.pop(next(iter(self._bodies)))
        self._bodies[path] = body
        return body

    def invalidate(self, path: str) -> bool:
        return self._bodies.pop(path, None) is not None
