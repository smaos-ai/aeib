"""Ingestion counters (integer counts only)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from .pipeline import Report


@dataclass
class Counters:
    batches: int = 0
    delivered: int = 0
    rejected: int = 0
    duplicates: int = 0
    by_batch: Dict[int, Report] = field(default_factory=dict)

    def record(self, report: Report) -> None:
        self.batches += 1
        self.delivered += report.delivered
        self.rejected += report.rejected
        self.duplicates += report.duplicates
        self.by_batch[self.batches] = report

    def duplicate_rate_bps(self) -> int:
        seen = self.delivered + self.duplicates
        return self.duplicates * 10000 // seen if seen else 0
