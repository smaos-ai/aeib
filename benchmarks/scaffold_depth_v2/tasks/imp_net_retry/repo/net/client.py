"""Client that maps transport status codes to errors and retries transient ones."""
from __future__ import annotations

import time
from typing import Callable, Dict, Tuple

from .errors import PermanentError, TransientError
from .retry import retry

Transport = Callable[[str], Tuple[int, str]]


class Client:
    def __init__(self, transport: Transport, max_attempts: int = 3,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self.transport = transport
        self.max_attempts = max_attempts
        self.sleep = sleep
        self.calls: Dict[str, int] = {}

    def _once(self, path: str) -> str:
        self.calls[path] = self.calls.get(path, 0) + 1
        status, body = self.transport(path)
        if status == 200:
            return body
        if status in (429, 502, 503, 504):
            raise TransientError(f"{status} for {path}")
        raise PermanentError(f"{status} for {path}")

    def fetch(self, path: str) -> str:
        return retry(lambda: self._once(path), self.max_attempts, self.sleep)
