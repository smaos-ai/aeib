# Fixture (intentionally bad): CI001 literal bound to metric-named keys/vars.
from dataclasses import dataclass


@dataclass
class Report:
    latency_ms: float
    token_reduction_bps: int


def build_report():
    token_reduction_bps = 7834
    summary = {"accuracy": 0.93, "cost_savings": 4.43}
    return Report(latency_ms=12.5, token_reduction_bps=token_reduction_bps), summary
