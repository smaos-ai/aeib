from maint.clock import format_ts, parse_ts
from maint.planner import next_slot
from maint.windows import load_windows


def test_parse_zulu():
    assert format_ts(parse_ts("2026-03-01T08:00:00Z")) == "2026-03-01T08:00:00Z"


def test_window_contains_half_open():
    (w,) = load_windows([("2026-03-01T08:00:00Z", "2026-03-01T09:00:00Z")])
    assert w.contains(parse_ts("2026-03-01T08:00:00Z"))
    assert not w.contains(parse_ts("2026-03-01T09:00:00Z"))


def test_next_slot_skips_zulu_window():
    windows = load_windows([("2026-03-01T08:00:00Z", "2026-03-01T09:00:00Z")])
    assert format_ts(next_slot("2026-03-01T07:50:00Z", 30, windows)) == "2026-03-01T09:00:00Z"
