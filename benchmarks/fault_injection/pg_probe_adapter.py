"""
pg_probe_adapter.py — Re-export shim.

The canonical implementation lives in the ``aeib_postgresql_probe`` package.
This shim keeps existing imports from ``benchmarks.fault_injection`` working
without duplicating source.
"""
from aeib_postgresql_probe.pg_probe_adapter import (  # noqa: F401
    PgProbeAdapter,
    canonical_evidence_digest,
    _percentile_nearest_rank,
)
