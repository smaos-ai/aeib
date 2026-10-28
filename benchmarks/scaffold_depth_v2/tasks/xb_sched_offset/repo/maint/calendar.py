"""Build recurring daily blackout windows from local wall-clock times."""
from __future__ import annotations

from datetime import date, timedelta
from typing import List, Tuple

from .windows import Window, load_windows


def _offset_suffix(offset_min: int) -> str:
    if offset_min == 0:
        return "Z"
    sign = "+" if offset_min > 0 else "-"
    hours, minutes = divmod(abs(offset_min), 60)
    return f"{sign}{hours:02d}:{minutes:02d}"


def daily_specs(first_day: str, days: int, start_hm: str, end_hm: str, offset_min: int) -> List[Tuple[str, str]]:
    """Window specs for `days` consecutive local days, e.g. start_hm='22:00', end_hm='23:30'."""
    if days <= 0:
        raise ValueError("days must be positive")
    suffix = _offset_suffix(offset_min)
    day0 = date.fromisoformat(first_day)
    specs = []
    for i in range(days):
        d = (day0 + timedelta(days=i)).isoformat()
        specs.append((f"{d}T{start_hm}:00{suffix}", f"{d}T{end_hm}:00{suffix}"))
    return specs


def daily_windows(first_day: str, days: int, start_hm: str, end_hm: str, offset_min: int) -> List[Window]:
    return load_windows(daily_specs(first_day, days, start_hm, end_hm, offset_min))
