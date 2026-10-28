"""Find the next start time for a job that avoids every blackout window."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Sequence

from .clock import parse_ts
from .windows import Window

STEP = timedelta(minutes=15)
HORIZON = timedelta(days=7)


def _align(ts: datetime) -> datetime:
    extra = timedelta(minutes=ts.minute % 15, seconds=ts.second, microseconds=ts.microsecond)
    return ts if not extra else ts - extra + STEP


def next_slot(after: str, duration_min: int, windows: Sequence[Window]) -> datetime:
    """Earliest 15-minute-aligned start >= `after` such that [start, start+duration) hits no window."""
    if duration_min <= 0:
        raise ValueError("duration must be positive")
    start = _align(parse_ts(after))
    limit = start + HORIZON
    length = timedelta(minutes=duration_min)
    while start < limit:
        if not any(w.overlaps(start, start + length) for w in windows):
            return start
        start += STEP
    raise RuntimeError("no free slot within the horizon")
