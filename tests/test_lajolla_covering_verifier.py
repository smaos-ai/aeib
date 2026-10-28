"""Falsification suite for `LajollaCoveringVerifier` (`src/lajolla_covering_verifier.py`).

Tests:
1. `test_1_valid_covering_design_c_7_3_2_passes`: 7-block Fano plane C(7, 3, 2) = 7 passes.
2. `test_2_uncovered_subset_fails_closed`: 7-block incomplete design (where block (0, 5, 6)
   is replaced by (0, 1, 4)) reaches the coverage check and halts with
   `HALT_UNCOVERED_T_SUBSET:(5, 6)`. (Fixes the draft bug where a 6-block input hit the
   Schoenheim bound check before the coverage check.)
3. `test_3_block_cardinality_mismatch_fails_closed`: block of size 2 instead of 3 halts.
4. `test_4_sub_schonheim_design_fails_closed`: 6-block design for C(7, 3, 2) halts with
   `HALT_BLOCK_COUNT_BELOW_SCHONHEIM_BOUND:6<7`.
"""
from __future__ import annotations

from src.lajolla_covering_verifier import (
    CoveringDesignSpec,
    LajollaCoveringVerifier,
)


def test_1_valid_covering_design_c_7_3_2_passes() -> None:
    fano_blocks = (
        (0, 1, 2),
        (0, 3, 4),
        (0, 5, 6),
        (1, 3, 5),
        (1, 4, 6),
        (2, 3, 6),
        (2, 4, 5),
    )
    spec = CoveringDesignSpec(v=7, k=3, t=2, blocks=fano_blocks)
    report = LajollaCoveringVerifier.verify_design(spec)

    assert report.is_valid is True
    assert report.is_valid_covering is True
    assert report.reason_code == "OK_COVERING_DESIGN_VERIFIED"
    assert report.halt_reason == "OK_COVERING_DESIGN_VERIFIED"
    assert report.receipt_caid.startswith("sha256:")
    assert LajollaCoveringVerifier.compute_schonheim_bound(7, 3, 2) == 7


def test_2_uncovered_subset_fails_closed() -> None:
    # 7 distinct blocks (>= Schoenheim bound 7), but (0, 5, 6) is replaced by (0, 1, 4),
    # leaving pair (5, 6) uncovered.
    incomplete_7_blocks = (
        (0, 1, 2),
        (0, 3, 4),
        (0, 1, 4),
        (1, 3, 5),
        (1, 4, 6),
        (2, 3, 6),
        (2, 4, 5),
    )
    spec = CoveringDesignSpec(v=7, k=3, t=2, blocks=incomplete_7_blocks)
    report = LajollaCoveringVerifier.verify_design(spec)

    assert report.is_valid is False
    assert report.is_valid_covering is False
    assert report.halt_reason == "HALT_UNCOVERED_T_SUBSET:(0, 5)"


def test_3_block_cardinality_mismatch_fails_closed() -> None:
    bad_cardinality = (
        (0, 1, 2),
        (0, 3),
        (0, 5, 6),
        (1, 3, 5),
        (1, 4, 6),
        (2, 3, 6),
        (2, 4, 5),
    )
    spec = CoveringDesignSpec(v=7, k=3, t=2, blocks=bad_cardinality)
    report = LajollaCoveringVerifier.verify_design(spec)

    assert report.is_valid is False
    assert report.is_valid_covering is False
    assert report.halt_reason == "HALT_INVALID_BLOCK_CARDINALITY:block_1"


def test_4_sub_schonheim_design_fails_closed() -> None:
    six_blocks = (
        (0, 1, 2),
        (0, 3, 4),
        (1, 3, 5),
        (1, 4, 6),
        (2, 3, 6),
        (2, 4, 5),
    )
    spec = CoveringDesignSpec(v=7, k=3, t=2, blocks=six_blocks)
    report = LajollaCoveringVerifier.verify_design(spec)

    assert report.is_valid is False
    assert report.is_valid_covering is False
    assert report.halt_reason == "HALT_BLOCK_COUNT_BELOW_SCHONHEIM_BOUND:6<7"
