from events.metrics import Counters
from events.pipeline import Report


def test_counters_accumulate():
    c = Counters()
    c.record(Report(delivered=3, rejected=1, duplicates=1))
    c.record(Report(delivered=1, rejected=0, duplicates=0))
    assert (c.batches, c.delivered, c.rejected, c.duplicates) == (2, 4, 1, 1)
    assert c.duplicate_rate_bps() == 2000
    assert Counters().duplicate_rate_bps() == 0
