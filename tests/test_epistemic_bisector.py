"""Tests for EpistemicBisector (`src/epistemic_bisector.py`).

Verifies O(log N) boundary isolation, exact probe counting without fabricated
`bit_length()` numbers, probe memoization (zero duplicate evaluations), and
non-monotonic recovery detection (`True -> False -> True`).
"""
from __future__ import annotations

from typing import List

from src.epistemic_bisector import BisectionResult, EpistemicBisector, sha256_jcs_caid


def test_empty_pipeline_returns_zero_probes() -> None:
    bisector = EpistemicBisector()
    res = bisector.bisect_failure([], lambda _: True)
    assert isinstance(res, BisectionResult)
    assert res.status == "EMPTY_PIPELINE"
    assert res.failing_index is None
    assert res.failing_item_id is None
    assert res.probes_executed == 0
    assert res.total_items == 0
    assert res.border_verified is False
    assert res.non_monotonic_detected is False
    assert res.receipt_caid.startswith("sha256:")
    assert len(res.receipt_caid) == 71


def test_initial_item_failure_detected_in_one_probe() -> None:
    bisector = EpistemicBisector()
    probed: List[str] = []

    def check_gate(item: str) -> bool:
        probed.append(item)
        return False

    items = [f"stage_{i}" for i in range(16)]
    res = bisector.bisect_failure(items, check_gate)
    assert res.status == "INITIAL_ITEM_FAILED"
    assert res.failing_index == 0
    assert res.failing_item_id == "stage_0"
    assert res.probes_executed == 1
    assert len(probed) == 1
    assert res.total_items == 16
    assert res.border_verified is True
    assert res.non_monotonic_detected is False


def test_single_item_passing_pipeline() -> None:
    bisector = EpistemicBisector()
    probed: List[str] = []

    def check_gate(item: str) -> bool:
        probed.append(item)
        return True

    res = bisector.bisect_failure(["only_stage"], check_gate)
    assert res.status == "ALL_ITEMS_PASSED"
    assert res.failing_index is None
    assert res.failing_item_id is None
    assert res.probes_executed == 1
    assert len(probed) == 1
    assert res.total_items == 1
    assert res.border_verified is True
    assert res.non_monotonic_detected is False


def test_all_items_passing_reports_actual_two_probes_not_bit_length() -> None:
    bisector = EpistemicBisector()
    probed: List[str] = []

    def check_gate(item: str) -> bool:
        probed.append(item)
        return True

    items = [f"stage_{i}" for i in range(64)]
    res = bisector.bisect_failure(items, check_gate)
    assert res.status == "ALL_ITEMS_PASSED"
    assert res.failing_index is None
    assert res.failing_item_id is None
    # Regression for Defect 1: only endpoints 0 and 63 are probed (2 calls, not bit_length=7)
    assert res.probes_executed == 2
    assert probed == ["stage_0", "stage_63"]
    assert res.total_items == 64
    assert res.border_verified is True
    assert res.non_monotonic_detected is False


def test_logarithmic_isolation_across_all_interior_indices_without_duplicate_probes() -> None:
    bisector = EpistemicBisector()
    items = [f"stage_{i}" for i in range(32)]

    for target_fail in range(1, 32):
        probed: List[str] = []

        def check_gate(item: str, threshold: int = target_fail) -> bool:
            probed.append(item)
            idx = int(item.split("_")[1])
            return idx < threshold

        res = bisector.bisect_failure(items, check_gate)
        assert res.status == "FAILURE_BORDER_ISOLATED"
        assert res.failing_index == target_fail
        assert res.failing_item_id == f"stage_{target_fail}"
        assert res.probes_executed == len(probed)
        # Regression for Defect 2: zero duplicate evaluations of any stage
        assert len(set(probed)) == len(probed)
        assert res.probes_executed <= 8
        assert res.total_items == 32
        assert res.border_verified is True
        assert res.non_monotonic_detected is False


def test_non_monotonic_recovery_is_detected_and_flagged() -> None:
    bisector = EpistemicBisector()
    items = [f"stage_{i}" for i in range(32)]

    # Stage 15 fails, stage 16 recovers to True, and stages 28..31 fail
    def check_glitch(item: str) -> bool:
        idx = int(item.split("_")[1])
        if idx == 15:
            return False
        return idx < 28

    res = bisector.bisect_failure(items, check_glitch)
    assert res.status == "NON_MONOTONIC_RECOVERY_DETECTED"
    assert res.failing_index == 15
    assert res.failing_item_id == "stage_15"
    assert res.border_verified is False
    assert res.non_monotonic_detected is True


def test_bisect_minimal_covering_prefix_isolates_exact_completion_index() -> None:
    bisector = EpistemicBisector()
    labels = [f"block_{i}" for i in range(20)]
    # Coverage completes when block_13 is included (prefix 0..13)
    res = bisector.bisect_minimal_covering_prefix(labels, lambda idx: idx >= 13)
    assert res.status == "FAILURE_BORDER_ISOLATED"
    assert res.failing_index == 13
    assert res.failing_item_id == "block_13"
    assert res.border_verified is True
    assert res.non_monotonic_detected is False
    assert res.probes_executed <= 7


def test_receipt_caid_changes_when_fields_change() -> None:
    bisector = EpistemicBisector()
    r1 = bisector.bisect_failure(["a", "b", "c"], lambda s: s < "b")
    r2 = bisector.bisect_failure(["a", "b", "c"], lambda s: s < "c")
    assert r1.receipt_caid != r2.receipt_caid
    expected = sha256_jcs_caid(
        {
            "border_verified": True,
            "failing_index": 1,
            "failing_item_id": "b",
            "non_monotonic_detected": False,
            "probes_executed": r1.probes_executed,
            "status": "FAILURE_BORDER_ISOLATED",
            "total_items": 3,
        }
    )
    assert r1.receipt_caid == expected
