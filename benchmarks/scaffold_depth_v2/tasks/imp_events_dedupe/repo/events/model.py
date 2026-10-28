"""Event model."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


class BadEvent(ValueError):
    """Raised for a raw record that is not a valid event."""


@dataclass(frozen=True)
class Event:
    id: str
    at: int
    payload: Dict[str, Any] = field(default_factory=dict, compare=True, hash=False)


def parse_event(raw: Dict[str, Any]) -> Event:
    try:
        event_id = raw["id"]
        at = raw["at"]
    except (KeyError, TypeError) as exc:
        raise BadEvent(f"missing field: {exc}") from exc
    if not isinstance(event_id, str) or not event_id:
        raise BadEvent("id must be a non-empty str")
    if isinstance(at, bool) or not isinstance(at, int):
        raise BadEvent("at must be an int")
    return Event(event_id, at, dict(raw.get("payload") or {}))
