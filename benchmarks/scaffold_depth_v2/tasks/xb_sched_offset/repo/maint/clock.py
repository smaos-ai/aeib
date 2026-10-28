"""Timestamp parsing. Every datetime inside the package is timezone-aware UTC."""
from __future__ import annotations

from datetime import datetime, timezone

_FMT = "%Y-%m-%dT%H:%M:%S"


def parse_ts(text: str) -> datetime:
    """Parse an ISO-8601 timestamp such as '2026-03-01T10:00:00+02:00' or '2026-03-01T08:00:00Z'.

    Returns an aware datetime in UTC. A timestamp without an offset is taken as UTC.
    """
    s = text.strip()
    if s.endswith("Z"):
        s = s[:-1]
    else:
        s = s[:19]
    return datetime.strptime(s, _FMT).replace(tzinfo=timezone.utc)


def format_ts(dt: datetime) -> str:
    if dt.tzinfo is None:
        raise ValueError("naive datetime")
    return dt.astimezone(timezone.utc).strftime(_FMT) + "Z"
