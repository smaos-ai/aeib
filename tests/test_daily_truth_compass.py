#!/usr/bin/env python3
"""
Daily Truth Compass verification suite (`tests/test_daily_truth_compass.py`).
Exercises `src/truth_compass.py` and `docs/truth/ledger.json`.
"""

from __future__ import annotations

from pathlib import Path

from src.truth_compass import ClaimResult, T1, T3, VERIFIED, decide, load_ledger

REPO = Path(__file__).resolve().parent.parent


def test_daily_truth_compass_ledger_loads_and_decides_t1_and_t3() -> None:
    claims = load_ledger((REPO / "docs" / "truth" / "ledger.json").read_text(encoding="utf-8"))
    assert len(claims) >= 6
    results = [
        ClaimResult(c.claim_id, VERIFIED if c.evidence is not None else (c.declared_status or "ASSUMED"), "check")
        for c in claims
    ]
    allowed_t1, reason_t1 = decide(claims, results, T1)
    assert allowed_t1 is True
    assert reason_t1 == "OK_T1"

    allowed_t3, reason_t3 = decide(claims, results, T3)
    assert allowed_t3 is True
    assert reason_t3 == "NO_KNOWN_BLOCKER_HUMAN_APPROVAL_REQUIRED"
