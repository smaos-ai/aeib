"""Grouping registered jobs by queue and checking timeouts."""
from __future__ import annotations

from typing import Dict, Iterable, List

from .registry import Registry


def by_queue(registry: Registry, names: Iterable[str]) -> Dict[str, List[str]]:
    """Map queue name -> sorted job names for the given registered jobs."""
    out: Dict[str, List[str]] = {}
    for name in names:
        queue = registry.config(name)["queue"]
        out.setdefault(queue, []).append(name)
    return {q: sorted(v) for q, v in sorted(out.items())}


def timed_out(registry: Registry, name: str, elapsed_s: float) -> bool:
    return elapsed_s > registry.config(name)["timeout_s"]


def total_budget_ms(registry: Registry, name: str) -> int:
    """Worst-case time spent sleeping between retries for one run of the job."""
    retry = registry.config(name)["retry"]
    base, mult = int(retry["backoff_ms"]), int(retry["multiplier"])
    return sum(base * mult ** i for i in range(int(retry["max_attempts"]) - 1))
