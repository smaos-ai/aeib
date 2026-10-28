#!/usr/bin/env python3
"""
run_aeib_arib_eval.py
================================================================================
Executes authentic ARIB-REPLAY-001 scenario (_replay) from agent-runtime-integrity-bench.
Proves that the uncoordinated native session store violates ARIB-REPLAY-001 (verdict: violated)
while AEIBSessionStoreAdapter with RFC 8785 CAID outbox satisfies it (verdict: held).
Zero mocks. Authentic ARIB harness invocation.
"""

import sys
import asyncio
import tempfile
from pathlib import Path
from typing import List, Dict, Any

ARIB_ROOT = Path(__file__).resolve().parent / "agent-runtime-integrity-bench"
sys.path.insert(0, str(ARIB_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bench.core import VERDICT_HELD, VERDICT_VIOLATED, Finding
from bench.s2_replay import _replay
from aeib_session_integrity_adapter import AEIBSessionStoreAdapter

class BaselineNativeSessionAdapter:
    """Native session store without deduplication (exhibits at-least-once duplication)."""
    name = "native-uncoordinated-session"

    def __init__(self, tmpdir: str):
        self.tmpdir = tmpdir
        self.items: List[Dict[str, Any]] = []

    async def add(self, items: List[Dict[str, Any]]):
        # Native direct append duplicates history on redelivery
        self.items.extend([dict(i) for i in items])

    async def get_all(self) -> List[Dict[str, Any]]:
        return list(self.items)

    async def close(self):
        self.is_closed = True
        return True

def main():
    print("=" * 80)
    print("🏛️  AEIB THIRD-PARTY INTEGRATION: agent-runtime-integrity-bench (ARIB)")
    print("    Scenario: S2 Replay / Idempotency (ARIB-REPLAY-001)")
    print("=" * 80)

    # 1. Run Baseline Native Session Store
    with tempfile.TemporaryDirectory(prefix="arib-baseline-") as tmpdir:
        finding_baseline = asyncio.run(_replay(BaselineNativeSessionAdapter, tmpdir))

    print(f"[*] Baseline Native Store Check: {finding_baseline.id}")
    print(f"    -> Verdict:             {finding_baseline.verdict.upper()}")
    print(f"    -> Visible Occurrences: {finding_baseline.evidence['visible_occurrences']} (Expected: 1, Actual: 2)")
    print(f"    -> Violations:          {finding_baseline.violations}")
    assert finding_baseline.verdict == VERDICT_VIOLATED, "Baseline must violate ARIB-REPLAY-001 under lost ACK retry"
    assert finding_baseline.violations == 1

    # 2. Run AEIB Governed Session Store
    with tempfile.TemporaryDirectory(prefix="arib-aeib-") as tmpdir:
        finding_aeib = asyncio.run(_replay(AEIBSessionStoreAdapter, tmpdir))

    print(f"\n[*] AEIB Governed Store Check:   {finding_aeib.id}")
    print(f"    -> Verdict:             {finding_aeib.verdict.upper()}")
    print(f"    -> Visible Occurrences: {finding_aeib.evidence['visible_occurrences']} (Expected: 1, Actual: 1)")
    print(f"    -> Violations:          {finding_aeib.violations}")
    assert finding_aeib.verdict == VERDICT_HELD, "AEIB must satisfy ARIB-REPLAY-001"
    assert finding_aeib.violations == 0

    print("-" * 80)
    print("[✔] ARIB S2 evaluation passed: Baseline violated, AEIB held exactly once.")

if __name__ == "__main__":
    main()

