# Fixture (clean): metrics computed from measured timings; config literals are labelled.
import time

TIMEOUT_MS = 500  # claim: config
ASSUMED_PRICE_USD = 0.002  # claim: assumption


def measure(fn, runs):
    total_ms = 0
    for _ in range(runs):
        start = time.perf_counter()
        fn()
        total_ms += (time.perf_counter() - start) * 1000.0
    return total_ms / runs


def compare(baseline_fn, candidate_fn, runs):
    baseline_ms = measure(baseline_fn, runs)
    candidate_ms = measure(candidate_fn, runs)
    reduction_bps = round((baseline_ms - candidate_ms) / baseline_ms * 10000)
    return {"baseline_ms": baseline_ms, "candidate_ms": candidate_ms, "reduction_bps": reduction_bps}
