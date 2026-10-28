"""Runs a job function with the retry policy from its configuration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from .backoff import delays_ms


@dataclass
class RunResult:
    ok: bool
    attempts: int
    slept_ms: List[int]
    error: str = ""


def run(cfg: Dict[str, Any], fn: Callable[[], Any], sleep_ms: Callable[[int], None]) -> RunResult:
    delays = delays_ms(cfg["retry"])
    slept: List[int] = []
    attempts = 0
    last_error = ""
    for attempt in range(len(delays) + 1):
        attempts += 1
        try:
            fn()
            return RunResult(True, attempts, slept)
        except Exception as exc:  # job failures are data here, not crashes
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < len(delays):
                sleep_ms(delays[attempt])
                slept.append(delays[attempt])
    return RunResult(False, attempts, slept, last_error)
