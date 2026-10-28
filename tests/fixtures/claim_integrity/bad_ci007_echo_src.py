# Fixture: src-like module whose literal is echoed by bad_ci007_echo_case.py (CI007).
from dataclasses import dataclass


@dataclass
class Outcome:
    reduction_bps: int
    p95_ms: float


def compute():
    return Outcome(reduction_bps=7834, p95_ms=35.78)
