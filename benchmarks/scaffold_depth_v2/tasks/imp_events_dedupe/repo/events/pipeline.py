"""Parse raw records, drop bad ones, de-duplicate and deliver."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List

from .dedupe import dedupe
from .model import BadEvent, parse_event
from .sink import MemorySink


@dataclass
class Report:
    delivered: int
    rejected: int
    duplicates: int


def process(raw_records: Iterable[Dict[str, Any]], sink: MemorySink) -> Report:
    parsed = []
    rejected = 0
    for raw in raw_records:
        try:
            parsed.append(parse_event(raw))
        except BadEvent:
            rejected += 1
    unique = dedupe(parsed)
    for event in unique:
        sink.deliver(event)
    return Report(len(unique), rejected, len(parsed) - len(unique))
