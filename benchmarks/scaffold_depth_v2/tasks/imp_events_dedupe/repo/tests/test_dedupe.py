from events.dedupe import dedupe
from events.model import Event
from events.pipeline import process
from events.sink import MemorySink


def test_keeps_first_occurrence_in_order():
    a1, b, a2 = Event("a", 1, {"v": 1}), Event("b", 2), Event("a", 3, {"v": 2})
    assert dedupe([a1, b, a2]) == [a1, b]


def test_no_duplicates_unchanged():
    evs = [Event("x", 1), Event("y", 2), Event("z", 3)]
    assert dedupe(evs) == evs


def test_retry_with_corrected_payload():
    first = Event("x", 1, {"amount": 100})
    retry = Event("x", 2, {"amount": 120})
    assert dedupe([first, retry]) == [retry]


def test_pipeline_report():
    sink = MemorySink()
    rep = process([{"id": "a", "at": 1}, {"id": "a", "at": 2}, {"at": 3}, {"id": "b", "at": 4}], sink)
    assert (rep.delivered, rep.rejected, rep.duplicates) == (2, 1, 1)
    assert sink.ids() == ["a", "b"]
