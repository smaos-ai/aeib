"""Retry helper."""
from __future__ import annotations

import time
from typing import Callable, TypeVar

from .backoff import delay_s
from .errors import TransportError

T = TypeVar("T")


def retry(fn: Callable[[], T], max_attempts: int = 3, sleep: Callable[[float], None] = time.sleep,
          base_s: float = 0.1) -> T:
    """Call fn until it succeeds; see the module contract in the task instruction."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")
    last: TransportError | None = None
    for attempt in range(max_attempts + 1):
        try:
            return fn()
        except TransportError as exc:
            last = exc
            if attempt < max_attempts:
                sleep(delay_s(attempt, base_s))
    assert last is not None
    raise last
