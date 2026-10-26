"""Regression tests for the nested ``percentile`` helper in
``v1.1-roadmap/production_readiness_chaos_harness.py``.

Before the fix, ``percentile`` returned 0.0 whenever the interpolation index
landed on the last element (a single sample, or p == 1.0), because both
interpolation weights were zero. These tests fail on that code.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "v1.1-roadmap"))

from production_readiness_chaos_harness import ProductionReadinessChaosHarness  # noqa: E402


def _metrics_for(tmp_path, auth_us, e2e_ms):
    harness = ProductionReadinessChaosHarness(workspace_dir=tmp_path / "ws")
    harness.auth_latencies_us = list(auth_us)
    harness.e2e_latencies_ms = list(e2e_ms)
    return harness._compute_metrics()


def test_single_sample_percentiles_equal_the_sample(tmp_path):
    m = _metrics_for(tmp_path, [42.5], [7.25])
    assert m.auth_latency_p50_us == 42.5
    assert m.auth_latency_p95_us == 42.5
    assert m.auth_latency_p99_us == 42.5
    assert m.e2e_action_latency_p50_ms == 7.25
    assert m.e2e_action_latency_p95_ms == 7.25


def test_empty_series_stays_zero(tmp_path):
    m = _metrics_for(tmp_path, [], [])
    assert m.auth_latency_p50_us == 0.0
    assert m.e2e_action_latency_p95_ms == 0.0


@pytest.mark.parametrize(
    "data,p50,p95,p99",
    [
        # k = (n-1)*p; linear interpolation between neighbours, rounded to 2 dp
        ([10.0, 20.0], 15.0, 19.5, 19.9),
        ([30.0, 10.0, 20.0], 20.0, 29.0, 29.8),
        ([1.0, 2.0, 3.0, 4.0, 5.0], 3.0, 4.8, 4.96),
    ],
)
def test_interpolated_percentiles_unchanged_for_n_ge_2(tmp_path, data, p50, p95, p99):
    m = _metrics_for(tmp_path, data, data)
    assert m.auth_latency_p50_us == p50
    assert m.auth_latency_p95_us == p95
    assert m.auth_latency_p99_us == p99
    assert m.e2e_action_latency_p50_ms == p50


def test_percentile_is_monotone_and_bounded(tmp_path):
    data = [5.0, 1.0, 9.0, 3.0, 7.0, 11.0, 2.0]
    m = _metrics_for(tmp_path, data, data)
    assert min(data) <= m.auth_latency_p50_us <= m.auth_latency_p95_us
    assert m.auth_latency_p95_us <= m.auth_latency_p99_us <= max(data)
