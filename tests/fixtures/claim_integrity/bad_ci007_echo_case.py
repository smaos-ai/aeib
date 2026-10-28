# Fixture (intentionally bad): CI007 assertions that echo literals hardcoded in the module under test.
from tests.fixtures.claim_integrity.bad_ci007_echo_src import compute


def test_reduction_echo():
    result = compute()
    assert result.reduction_bps == 7834
    assert 35.78 == result.p95_ms
