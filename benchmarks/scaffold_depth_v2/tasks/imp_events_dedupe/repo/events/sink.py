"""Delivery targets."""
from __future__ import annotations

from typing import List

from .model import Event


class MemorySink:
    def __init__(self) -> None:
        self.delivered: List[Event] = []

    def deliver(self, event: Event) -> None:
        self.delivered.append(event)

    def ids(self) -> List[str]:
        return [e.id for e in self.delivered]
