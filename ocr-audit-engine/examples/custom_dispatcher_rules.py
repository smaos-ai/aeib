#!/usr/bin/env python3
"""Example: Subclassing DeterministicDispatcher to enforce custom organizational policies."""

import sys
from pathlib import Path
from typing import List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ocr_audit.dispatcher import DeterministicDispatcher, TraceRecord, DispatchMetrics


class BankingDispatcher(DeterministicDispatcher):
    """Custom dispatcher that unconditionally escalates cross-border transactions > €50,000."""

    def dispatch(self, traces: List[TraceRecord]) -> Tuple[List[TraceRecord], DispatchMetrics]:
        selected, metrics = super().dispatch(traces)
        for t in traces:
            amount = t.record.get("amount", 0)
            if amount > 50000 and t not in selected:
                selected.append(t)
        return selected, metrics


if __name__ == "__main__":
    print("[*] Custom BankingDispatcher ready for integration.")
