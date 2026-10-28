"""Epistemic Bisector: O(log N) boundary isolation with probe memoization.

Isolates the first failing stage in an ordered pipeline (commits, claim chain,
or monotone block prefixes) using memoized binary search. Unlike naive binary
search, this implementation:
  1. Counts every actual oracle evaluation (`probes_executed`), never fabricating
     `bit_length()` steps when all items pass.
  2. Memoizes oracle evaluations by index and narrows the interior interval to
     `[1, N - 2]` after checking endpoints `0` and `N - 1`, avoiding duplicate
     endpoint probes.
  3. Verifies the isolated boundary (`probe(idx - 1) is True` and
     `probe(idx) is False`) and checks `probe(idx + 1)` to detect localized
     non-monotonic recovery (`True -> False -> True`).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Sequence

from src.jcs_canonicalizer import encode_jcs


def sha256_jcs_caid(payload: Dict[str, Any]) -> str:
    """Compute an RFC 8785 JCS SHA-256 content-addressable identifier."""
    return "sha256:" + hashlib.sha256(encode_jcs(payload)).hexdigest()


@dataclass(frozen=True)
class BisectionResult:
    status: str
    failing_index: Optional[int]
    failing_item_id: Optional[str]
    probes_executed: int
    total_items: int
    border_verified: bool
    non_monotonic_detected: bool
    receipt_caid: str


class EpistemicBisector:
    """O(log N) binary search isolator for ordered epistemic pipelines."""

    def bisect_failure(
        self,
        items: Sequence[str],
        invariant_checker: Callable[[str], bool],
    ) -> BisectionResult:
        """Find the first index `i` where `invariant_checker(items[i])` is False."""
        n = len(items)
        if n == 0:
            return self._build_result(
                status="EMPTY_PIPELINE",
                failing_index=None,
                failing_item_id=None,
                probes_executed=0,
                total_items=0,
                border_verified=False,
                non_monotonic_detected=False,
            )

        cache: Dict[int, bool] = {}

        def probe(idx: int) -> bool:
            if idx >= n:
                return False
            if idx not in cache:
                cache[idx] = bool(invariant_checker(items[idx]))
            return cache[idx]

        if not probe(0):
            return self._build_result(
                status="INITIAL_ITEM_FAILED",
                failing_index=0,
                failing_item_id=items[0],
                probes_executed=len(cache),
                total_items=n,
                border_verified=True,
                non_monotonic_detected=False,
            )

        if n == 1 or probe(n - 1):
            return self._build_result(
                status="ALL_ITEMS_PASSED",
                failing_index=None,
                failing_item_id=None,
                probes_executed=len(cache),
                total_items=n,
                border_verified=True,
                non_monotonic_detected=False,
            )

        low = 1
        high = n - 2
        failing_idx = n - 1

        while low <= high:
            mid = (low + high) // 2
            if probe(mid):
                low = mid + 1
            else:
                failing_idx = mid
                high = mid - 1

        prev_ok = probe(failing_idx - 1)
        curr_fail = not probe(failing_idx)
        next_recovers = probe(failing_idx + 1)

        if next_recovers:
            return self._build_result(
                status="NON_MONOTONIC_RECOVERY_DETECTED",
                failing_index=failing_idx,
                failing_item_id=items[failing_idx],
                probes_executed=len(cache),
                total_items=n,
                border_verified=False,
                non_monotonic_detected=True,
            )

        return self._build_result(
            status="FAILURE_BORDER_ISOLATED",
            failing_index=failing_idx,
            failing_item_id=items[failing_idx],
            probes_executed=len(cache),
            total_items=n,
            border_verified=bool(prev_ok and curr_fail),
            non_monotonic_detected=False,
        )

    def bisect_minimal_covering_prefix(
        self,
        block_labels: Sequence[str],
        is_full_cover_at_index: Callable[[int], bool],
    ) -> BisectionResult:
        """Isolate the first block index `i` where prefix `0..i` achieves full coverage.

        Since set coverage under block addition is monotone (`False ... False -> True ... True`),
        treating `not is_full_cover_at_index(i)` as the invariant isolates the exact block index
        where coverage completes in O(log B) probes.
        """
        index_map = {label: idx for idx, label in enumerate(block_labels)}
        return self.bisect_failure(
            block_labels,
            lambda label: not is_full_cover_at_index(index_map[label]),
        )

    @staticmethod
    def _build_result(
        *,
        status: str,
        failing_index: Optional[int],
        failing_item_id: Optional[str],
        probes_executed: int,
        total_items: int,
        border_verified: bool,
        non_monotonic_detected: bool,
    ) -> BisectionResult:
        caid = sha256_jcs_caid(
            {
                "border_verified": border_verified,
                "failing_index": -1 if failing_index is None else failing_index,
                "failing_item_id": "" if failing_item_id is None else failing_item_id,
                "non_monotonic_detected": non_monotonic_detected,
                "probes_executed": probes_executed,
                "status": status,
                "total_items": total_items,
            }
        )
        return BisectionResult(
            status=status,
            failing_index=failing_index,
            failing_item_id=failing_item_id,
            probes_executed=probes_executed,
            total_items=total_items,
            border_verified=border_verified,
            non_monotonic_detected=non_monotonic_detected,
            receipt_caid=caid,
        )
