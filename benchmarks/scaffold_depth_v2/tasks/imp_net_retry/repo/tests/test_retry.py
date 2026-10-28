import pytest

from net.errors import PermanentError, TransientError
from net.retry import retry


def test_succeeds_after_two_failures():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise TransientError("503")
        return "ok"

    slept = []
    assert retry(flaky, max_attempts=3, sleep=slept.append) == "ok"
    assert len(calls) == 3 and slept == [0.1, 0.2]


def test_permanent_error_not_retried():
    calls = []

    def bad():
        calls.append(1)
        raise PermanentError("404")

    with pytest.raises(PermanentError):
        retry(bad, max_attempts=5, sleep=lambda s: None)
    assert len(calls) == 1


def test_attempt_budget():
    calls = []

    def always_fail():
        calls.append(1)
        raise TransientError("503")

    with pytest.raises(TransientError):
        retry(always_fail, max_attempts=3, sleep=lambda s: None)
    assert len(calls) == 4
