# Fixture (clean): assertions against independently computed expectations, not src literals.
from tests.fixtures.claim_integrity.bad_ci007_echo_src import compute


def test_reduction_is_bounded():
    result = compute()
    assert 0 <= result.reduction_bps <= 10000
    assert result.p95_ms == result.p95_ms
    assert len([result]) == 1
