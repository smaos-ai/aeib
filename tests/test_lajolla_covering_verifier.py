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
    assert report.schonheim_lower_bound == 7
    assert report.block_count == 6
    assert report.total_t_subsets == 21
    assert report.covered_t_subsets == 0


def test_5_is_strict_int_and_schonheim_bound() -> None:
    import pytest
    from src.lajolla_covering_verifier import _is_strict_int, compute_schonheim_bound

    assert _is_strict_int(0) is True
    assert _is_strict_int(7) is True
    assert _is_strict_int(-5) is True
    assert _is_strict_int(True) is False
    assert _is_strict_int(False) is False
    assert _is_strict_int(3.14) is False
    assert _is_strict_int("7") is False
    assert _is_strict_int(None) is False

    assert compute_schonheim_bound(7, 3, 2) == 7
    assert compute_schonheim_bound(6, 3, 2) == 6
    assert compute_schonheim_bound(5, 5, 5) == 1

    with pytest.raises(ValueError, match="HALT_INVALID_DESIGN_PARAMETERS"):
        compute_schonheim_bound(True, 3, 2)  # type: ignore
    with pytest.raises(ValueError, match="HALT_INVALID_DESIGN_PARAMETERS"):
        compute_schonheim_bound(7, False, 2)  # type: ignore
    with pytest.raises(ValueError, match="HALT_INVALID_DESIGN_PARAMETERS"):
        compute_schonheim_bound(7, 3, True)  # type: ignore
    with pytest.raises(ValueError, match="HALT_INVALID_DESIGN_PARAMETERS"):
        compute_schonheim_bound(0, 3, 2)
    with pytest.raises(ValueError, match="HALT_INVALID_DESIGN_PARAMETERS"):
        compute_schonheim_bound(7, 0, 2)
    with pytest.raises(ValueError, match="HALT_INVALID_DESIGN_PARAMETERS"):
        compute_schonheim_bound(7, 3, 0)
    with pytest.raises(ValueError, match="HALT_INVALID_DESIGN_PARAMETERS"):
        compute_schonheim_bound(3, 5, 2)  # k > v
    with pytest.raises(ValueError, match="HALT_INVALID_DESIGN_PARAMETERS"):
        compute_schonheim_bound(7, 2, 3)  # t > k


def test_6_invalid_design_parameters_in_verify_design() -> None:
    from src.lajolla_covering_verifier import sha256_jcs_caid

    # Boolean parameter
    spec_bool = CoveringDesignSpec(v=True, k=3, t=2, blocks=())  # type: ignore
    rep_bool = LajollaCoveringVerifier.verify_design(spec_bool)
    assert rep_bool.is_valid is False
    assert rep_bool.reason_code == "HALT_INVALID_DESIGN_PARAMETERS"
    assert rep_bool.schonheim_lower_bound == 0
    assert rep_bool.total_t_subsets == 0
    assert rep_bool.covered_t_subsets == 0
    expected_caid_v = sha256_jcs_caid({
        "block_count": 0,
        "canonical_blocks": [],
        "covered_t_subsets": 0,
        "is_valid": False,
        "k": 3,
        "reason_code": "HALT_INVALID_DESIGN_PARAMETERS",
        "schonheim_lower_bound": 0,
        "t": 2,
        "total_t_subsets": 0,
        "v": -1,
    })
    assert rep_bool.receipt_caid == expected_caid_v

    spec_k_bool = CoveringDesignSpec(v=7, k=False, t=2, blocks=())  # type: ignore
    rep_k_bool = LajollaCoveringVerifier.verify_design(spec_k_bool)
    assert rep_k_bool.is_valid is False
    assert rep_k_bool.reason_code == "HALT_INVALID_DESIGN_PARAMETERS"
    expected_caid_k = sha256_jcs_caid({
        "block_count": 0,
        "canonical_blocks": [],
        "covered_t_subsets": 0,
        "is_valid": False,
        "k": -1,
        "reason_code": "HALT_INVALID_DESIGN_PARAMETERS",
        "schonheim_lower_bound": 0,
        "t": 2,
        "total_t_subsets": 0,
        "v": 7,
    })
    assert rep_k_bool.receipt_caid == expected_caid_k

    spec_t_bool = CoveringDesignSpec(v=7, k=3, t=True, blocks=())  # type: ignore
    rep_t_bool = LajollaCoveringVerifier.verify_design(spec_t_bool)
    assert rep_t_bool.is_valid is False
    assert rep_t_bool.reason_code == "HALT_INVALID_DESIGN_PARAMETERS"
    expected_caid_t = sha256_jcs_caid({
        "block_count": 0,
        "canonical_blocks": [],
        "covered_t_subsets": 0,
        "is_valid": False,
        "k": 3,
        "reason_code": "HALT_INVALID_DESIGN_PARAMETERS",
        "schonheim_lower_bound": 0,
        "t": -1,
        "total_t_subsets": 0,
        "v": 7,
    })
    assert rep_t_bool.receipt_caid == expected_caid_t

    # Out of range (t <= 0, t > k, k > v)
    spec_t0 = CoveringDesignSpec(v=7, k=3, t=0, blocks=())
    rep_t0 = LajollaCoveringVerifier.verify_design(spec_t0)
    assert rep_t0.is_valid is False
    assert rep_t0.reason_code == "HALT_INVALID_DESIGN_PARAMETERS"
    assert rep_t0.schonheim_lower_bound == 0
    assert rep_t0.total_t_subsets == 0
    assert rep_t0.covered_t_subsets == 0

    spec_tk = CoveringDesignSpec(v=7, k=2, t=3, blocks=())
    rep_tk = LajollaCoveringVerifier.verify_design(spec_tk)
    assert rep_tk.is_valid is False
    assert rep_tk.reason_code == "HALT_INVALID_DESIGN_PARAMETERS"
    assert rep_tk.schonheim_lower_bound == 0
    assert rep_tk.total_t_subsets == 0
    assert rep_tk.covered_t_subsets == 0

    spec_kv = CoveringDesignSpec(v=3, k=5, t=2, blocks=())
    rep_kv = LajollaCoveringVerifier.verify_design(spec_kv)
    assert rep_kv.is_valid is False
    assert rep_kv.reason_code == "HALT_INVALID_DESIGN_PARAMETERS"
    assert rep_kv.schonheim_lower_bound == 0
    assert rep_kv.total_t_subsets == 0
    assert rep_kv.covered_t_subsets == 0


def test_7_combinatorial_budget_exceeded() -> None:
    spec = CoveringDesignSpec(v=20, k=5, t=5, blocks=())
    rep = LajollaCoveringVerifier.verify_design(spec, max_t_subsets=100)
    assert rep.is_valid is False
    assert rep.total_t_subsets == 15504
    assert rep.covered_t_subsets == 0
    assert rep.schonheim_lower_bound == 15504
    assert rep.reason_code == "HALT_COMBINATORIAL_BUDGET_EXCEEDED:15504>100"


def test_8_point_out_of_bounds_and_invalid_types() -> None:
    # Negative point
    spec_neg = CoveringDesignSpec(v=7, k=3, t=2, blocks=((0, 1, -1),))
    rep_neg = LajollaCoveringVerifier.verify_design(spec_neg)
    assert rep_neg.is_valid is False
    assert rep_neg.reason_code == "HALT_POINT_OUT_OF_BOUNDS:block_0"
    assert rep_neg.schonheim_lower_bound == 7
    assert rep_neg.total_t_subsets == 21
    assert rep_neg.covered_t_subsets == 0

    # Point >= v
    spec_oob = CoveringDesignSpec(v=7, k=3, t=2, blocks=((0, 1, 7),))
    rep_oob = LajollaCoveringVerifier.verify_design(spec_oob)
    assert rep_oob.is_valid is False
    assert rep_oob.reason_code == "HALT_POINT_OUT_OF_BOUNDS:block_0"

    # Non-strict int point (bool True)
    spec_bool_pt = CoveringDesignSpec(v=7, k=3, t=2, blocks=((0, 1, True),))
    rep_bool_pt = LajollaCoveringVerifier.verify_design(spec_bool_pt)
    assert rep_bool_pt.is_valid is False
    assert rep_bool_pt.reason_code == "HALT_POINT_OUT_OF_BOUNDS:block_0"


def test_9_duplicate_points_and_blocks() -> None:
    # Duplicate points within single block
    spec_dup_pts = CoveringDesignSpec(v=7, k=3, t=2, blocks=((0, 1, 1),))
    rep_dup_pts = LajollaCoveringVerifier.verify_design(spec_dup_pts)
    assert rep_dup_pts.is_valid is False
    assert rep_dup_pts.reason_code == "HALT_DUPLICATE_POINTS_IN_BLOCK:block_0"
    assert rep_dup_pts.covered_t_subsets == 0

    # Duplicate block (isomorphic ordering (1, 0, 2) vs (0, 1, 2))
    spec_dup_blk = CoveringDesignSpec(
        v=7, k=3, t=2, blocks=((0, 1, 2), (1, 0, 2))
    )
    rep_dup_blk = LajollaCoveringVerifier.verify_design(spec_dup_blk)
    assert rep_dup_blk.is_valid is False
    assert rep_dup_blk.reason_code == "HALT_DUPLICATE_BLOCK:block_1"
    assert rep_dup_blk.covered_t_subsets == 0


def test_10_isomorphic_receipt_invariance() -> None:
    blocks_1 = (
        (0, 1, 2),
        (0, 3, 4),
        (0, 5, 6),
        (1, 3, 5),
        (1, 4, 6),
        (2, 3, 6),
        (2, 4, 5),
    )
    blocks_2 = (
        (2, 4, 5),
        (2, 3, 6),
        (1, 4, 6),
        (1, 3, 5),
        (0, 5, 6),
        (0, 3, 4),
        (2, 1, 0),  # internally permuted
    )
    rep1 = LajollaCoveringVerifier.verify_design(CoveringDesignSpec(v=7, k=3, t=2, blocks=blocks_1))
    rep2 = LajollaCoveringVerifier.verify_design(CoveringDesignSpec(v=7, k=3, t=2, blocks=blocks_2))
    assert rep1.receipt_caid == rep2.receipt_caid
    assert rep1.is_valid is True
    assert rep2.is_valid is True
    assert rep1.v == 7 and rep1.k == 3 and rep1.t == 2
    assert rep1.block_count == 7
    assert rep1.covered_t_subsets == 21
    assert rep1.total_t_subsets == 21

