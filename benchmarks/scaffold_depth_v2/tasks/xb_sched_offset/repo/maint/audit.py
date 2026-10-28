"""Audit log helpers: events are dicts with an 'at' timestamp string."""
from __future__ import annotations

from typing import Dict, List, Optional

from .clock import parse_ts


def order_events(events: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Events sorted by their instant in time (stable for equal instants)."""
    return sorted(events, key=lambda e: parse_ts(e["at"]))


def first_after(events: List[Dict[str, str]], ts_text: str) -> Optional[Dict[str, str]]:
    cutoff = parse_ts(ts_text)
    for event in order_events(events):
        if parse_ts(event["at"]) > cutoff:
            return event
    return None
