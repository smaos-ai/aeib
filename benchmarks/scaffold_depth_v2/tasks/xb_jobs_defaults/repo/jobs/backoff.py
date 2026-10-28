"""Retry delay schedules (milliseconds)."""
from __future__ import annotations

from typing import Any, Dict, List


def delays_ms(retry: Dict[str, Any]) -> List[int]:
    """Delay before each retry; there are max_attempts - 1 retries."""
    base = int(retry.get("backoff_ms", 0))
    mult = int(retry.get("multiplier", 1))
    return [base * mult ** i for i in range(int(retry["max_attempts"]) - 1)]
