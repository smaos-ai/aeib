"""Blackout windows: half-open UTC intervals [start, end)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Tuple

from .clock import parse_ts


@dataclass(frozen=True)
class Window:
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError("window end must be after start")

    def contains(self, ts: datetime) -> bool:
        return self.start <= ts < self.end

    def overlaps(self, start: datetime, end: datetime) -> bool:
        return start < self.end and self.start < end


def load_windows(specs: Iterable[Tuple[str, str]]) -> List[Window]:
    windows = [Window(parse_ts(a), parse_ts(b)) for a, b in specs]
    return sorted(windows, key=lambda w: w.start)
