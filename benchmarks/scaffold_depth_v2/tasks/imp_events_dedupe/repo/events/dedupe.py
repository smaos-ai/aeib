"""De-duplication of retried deliveries."""
from __future__ import annotations

from typing import Iterable, List

from .model import Event


def dedupe(events: Iterable[Event]) -> List[Event]:
    """Drop repeated event ids (see the task instruction for which copy is kept)."""
    raise NotImplementedError("dedupe")
