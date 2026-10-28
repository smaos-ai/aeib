from jobs.backoff import delays_ms
from jobs.config import load_config
from jobs.runner import run


def test_delays():
    assert delays_ms({"max_attempts": 4, "backoff_ms": 100, "multiplier": 3}) == [100, 300, 900]


def test_default_config_values():
    cfg = load_config()
    assert cfg["retry"]["max_attempts"] == 3 and cfg["timeout_s"] == 30


def test_runner_succeeds_after_retry():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 2:
            raise RuntimeError("boom")

    slept = []
    res = run(load_config(), flaky, slept.append)
    assert res.ok and res.attempts == 2 and slept == [200]
