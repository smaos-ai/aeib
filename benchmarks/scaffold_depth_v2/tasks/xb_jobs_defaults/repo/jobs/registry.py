"""Named jobs and their configurations."""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from .config import load_config
from .runner import RunResult, run


class Registry:
    def __init__(self) -> None:
        self._configs: Dict[str, Dict[str, Any]] = {}

    def register(self, name: str, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if name in self._configs:
            raise ValueError(f"job {name!r} already registered")
        self._configs[name] = load_config(overrides)
        return self._configs[name]

    def config(self, name: str) -> Dict[str, Any]:
        return self._configs[name]

    def execute(self, name: str, fn: Callable[[], Any], sleep_ms: Callable[[int], None]) -> RunResult:
        return run(self._configs[name], fn, sleep_ms)
