"""Exponential backoff delays in seconds."""
from __future__ import annotations


def delay_s(retry_index: int, base_s: float = 0.1, cap_s: float = 5.0) -> float:
    """Delay before retry number `retry_index` (0 = before the second attempt)."""
    if retry_index < 0:
        raise ValueError("retry_index must be >= 0")
    return min(cap_s, base_s * (2 ** retry_index))
