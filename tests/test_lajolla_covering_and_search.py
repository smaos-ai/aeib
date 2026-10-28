"""Tests for `src/lajolla_covering_verifier.py` and `src/lajolla_search_loop.py`.

Exercises exact Schoenheim bounds, exhaustive t-subset coverage, canonical JCS
receipts, cyclic Z_v orbit development, and O(log B) critical-block bisection.
"""
from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest

from src.lajolla_covering_verifier import (
    CoveringDesignSpec,
    LajollaCoveringVerifier,
    compute_schonheim_bound,
    sha256_jcs_caid,
)
from src.lajolla_search_loop import (
    GeneratorHackDetectionGate,
    LajollaSearchOrchestrator,
    develop_cyclic_orbits,
)

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from covering_design_record_comparator import PinnedBaseline, compare  # noqa: E402
from covering_design_verifier import verify as tool_verify  # noqa: E402

FANO_BLOCKS = (
    (0, 1, 3),
    (1, 2, 4),
    (2, 3, 5),
    (3, 4, 6),
    (4, 5, 0),
    (5, 6, 1),
    (6, 0, 2),
)


def test_schonheim_bound_exact_values_and_ljcr_baseline_agreement() -> None:
    assert compute_schonheim_bound(4, 2, 1) == 2
    assert compute_schonheim_bound(7, 3, 2) == 7
    assert compute_schonheim_bound(10, 4, 3) == 30
    assert compute_schonheim_bound(12, 4, 3) == 57
    assert compute_schonheim_bound(13, 4, 2) == 13
    # Regression for Defect 5: C(13,4,3) has Schoenheim bound 78; C(13,6,4) has Schoenheim bound 59
    assert compute_schonheim_bound(13, 4, 3) == 78
    assert compute_schonheim_bound(13, 6, 4) == 59

    baseline = PinnedBaseline()
    e_13_4_3 = baseline.entry(13, 4, 3)
    assert e_13_4_3 is not None
    assert e_13_4_3["published_lower_bound"] == 78
    assert e_13_4_3["published_size"] == 78

    e_13_6_4 = baseline.entry(13, 6, 4)
    assert e_13_6_4 is not None
    assert e_13_6_4["published_lower_bound"] == 59
    assert e_13_6_4["published_size"] == 66


@pytest.mark.parametrize(
    "v,k,t",
    [
        (7, 3, 0),
        (7, 2, 3),
        (3, 7, 2),
        (True, 1, 1),
        (7, True, 1),
        (7, 3, True),
    ],
)
def test_schonheim_bound_rejects_invalid_parameters(v: int, k: int, t: int) -> None:
    with pytest.raises(ValueError, match="HALT_INVALID_DESIGN_PARAMETERS"):
        compute_schonheim_bound(v, k, t)


def test_fano_plane_verification_and_order_invariant_receipt() -> None:
    verifier = LajollaCoveringVerifier()
    spec = CoveringDesignSpec(v=7, k=3, t=2, blocks=FANO_BLOCKS)
    report = verifier.verify_design(spec)
    assert report.is_valid is True
    assert report.v == 7
    assert report.k == 3
    assert report.t == 2
    assert report.block_count == 7
    assert report.schonheim_lower_bound == 7
    assert report.total_t_subsets == 21
    assert report.covered_t_subsets == 21
    assert report.reason_code == "OK_COVERING_DESIGN_VERIFIED"
    assert report.receipt_caid.startswith("sha256:")
    assert len(report.receipt_caid) == 71

    # Reversing block order and point order within blocks yields the exact same canonical receipt
    reordered_blocks = tuple(tuple(reversed(b)) for b in reversed(FANO_BLOCKS))
    report_reordered = verifier.verify_design(CoveringDesignSpec(v=7, k=3, t=2, blocks=reordered_blocks))
    assert report_reordered.is_valid is True
    assert report_reordered.receipt_caid == report.receipt_caid

    # Cross-check with tools/covering_design_verifier.py and PinnedBaseline
    tool_res = tool_verify(7, 3, 2, [list(b) for b in FANO_BLOCKS], claimed=7)
    assert tool_res["valid"] is True
    assert compare(tool_res, PinnedBaseline())["label"] == "REPRODUCED_KNOWN_RESULT"


def test_verifier_structural_and_bound_rejections() -> None:
    verifier = LajollaCoveringVerifier()

    # 1. Invalid parameters (bool / out of order)
    for bad_spec in (
        CoveringDesignSpec(v=True, k=1, t=1, blocks=()),  # type: ignore[arg-type]
        CoveringDesignSpec(v=7, k=True, t=1, blocks=()),  # type: ignore[arg-type]
        CoveringDesignSpec(v=7, k=3, t=True, blocks=()),  # type: ignore[arg-type]
        CoveringDesignSpec(v=True, k=True, t=True, blocks=()),  # type: ignore[arg-type]
    ):
        r_bool = verifier.verify_design(bad_spec)
        assert r_bool.is_valid is False
        assert r_bool.reason_code == "HALT_INVALID_DESIGN_PARAMETERS"
        assert r_bool.schonheim_lower_bound == 0
        assert r_bool.total_t_subsets == 0
        assert r_bool.covered_t_subsets == 0

    all_bool_spec = CoveringDesignSpec(v=True, k=True, t=True, blocks=())  # type: ignore[arg-type]
    r_all_bool = verifier.verify_design(all_bool_spec)
    assert r_all_bool.receipt_caid == sha256_jcs_caid(
        {
            "block_count": 0,
            "canonical_blocks": [],
            "covered_t_subsets": 0,
            "is_valid": False,
            "k": -1,
            "reason_code": "HALT_INVALID_DESIGN_PARAMETERS",
            "schonheim_lower_bound": 0,
            "t": -1,
            "total_t_subsets": 0,
            "v": -1,
        }
    )

    r_order = verifier.verify_design(CoveringDesignSpec(v=5, k=6, t=2, blocks=()))
    assert r_order.is_valid is False
    assert r_order.reason_code == "HALT_INVALID_DESIGN_PARAMETERS"
    assert r_order.schonheim_lower_bound == 0
    assert r_order.total_t_subsets == 0
    assert r_order.covered_t_subsets == 0

    r_zero_t = verifier.verify_design(CoveringDesignSpec(v=5, k=3, t=0, blocks=()))
    assert r_zero_t.is_valid is False
    assert r_zero_t.reason_code == "HALT_INVALID_DESIGN_PARAMETERS"
    assert r_zero_t.schonheim_lower_bound == 0
    assert r_zero_t.total_t_subsets == 0
    assert r_zero_t.covered_t_subsets == 0

    # 2. Combinatorial budget exceeded (replaces dead `if v > 32 and t >= 4: pass`)
    r_budget = verifier.verify_design(
        CoveringDesignSpec(v=33, k=6, t=4, blocks=()),
        max_t_subsets=10_000,
    )
    assert r_budget.is_valid is False
    assert r_budget.schonheim_lower_bound == 2750
    assert r_budget.total_t_subsets == 40920
    assert r_budget.covered_t_subsets == 0
    assert r_budget.reason_code == "HALT_COMBINATORIAL_BUDGET_EXCEEDED:40920>10000"

    # 3. Invalid block cardinality
    r_card = verifier.verify_design(
        CoveringDesignSpec(v=7, k=3, t=2, blocks=((0, 1),) + FANO_BLOCKS[1:])
    )
    assert r_card.is_valid is False
    assert r_card.covered_t_subsets == 0
    assert r_card.reason_code == "HALT_INVALID_BLOCK_CARDINALITY:block_0"

    # 4. Point out of bounds (negative, >= v, bool)
    r_neg = verifier.verify_design(
        CoveringDesignSpec(v=7, k=3, t=2, blocks=((-1, 1, 3),) + FANO_BLOCKS[1:])
    )
    assert r_neg.is_valid is False
    assert r_neg.covered_t_subsets == 0
    assert r_neg.reason_code == "HALT_POINT_OUT_OF_BOUNDS:block_0"

    r_high = verifier.verify_design(
        CoveringDesignSpec(v=7, k=3, t=2, blocks=((0, 1, 7),) + FANO_BLOCKS[1:])
    )
    assert r_high.is_valid is False
    assert r_high.covered_t_subsets == 0
    assert r_high.reason_code == "HALT_POINT_OUT_OF_BOUNDS:block_0"

    r_pbool = verifier.verify_design(
        CoveringDesignSpec(v=7, k=3, t=2, blocks=((True, 1, 3),) + FANO_BLOCKS[1:])  # type: ignore[arg-type]
    )
    assert r_pbool.is_valid is False
    assert r_pbool.covered_t_subsets == 0
    assert r_pbool.reason_code == "HALT_POINT_OUT_OF_BOUNDS:block_0"

    # 5. Duplicate points inside a block
    r_dup_pt = verifier.verify_design(
        CoveringDesignSpec(v=7, k=3, t=2, blocks=((0, 0, 3),) + FANO_BLOCKS[1:])
    )
    assert r_dup_pt.is_valid is False
    assert r_dup_pt.schonheim_lower_bound == 7
    assert r_dup_pt.total_t_subsets == 21
    assert r_dup_pt.covered_t_subsets == 0
    assert r_dup_pt.reason_code == "HALT_DUPLICATE_POINTS_IN_BLOCK:block_0"

    # 6. Duplicate block across the design
    r_dup_blk = verifier.verify_design(
        CoveringDesignSpec(v=7, k=3, t=2, blocks=FANO_BLOCKS + ((3, 1, 0),))
    )
    assert r_dup_blk.is_valid is False
    assert r_dup_blk.covered_t_subsets == 0
    assert r_dup_blk.reason_code == "HALT_DUPLICATE_BLOCK:block_7"

    # 7. Regression for Defect 4: block count below Schoenheim bound reports actual bound (6<7, not 6<10)
    r_below = verifier.verify_design(
        CoveringDesignSpec(v=7, k=3, t=2, blocks=FANO_BLOCKS[:-1])
    )
    assert r_below.is_valid is False
    assert r_below.covered_t_subsets == 0
    assert r_below.reason_code == "HALT_BLOCK_COUNT_BELOW_SCHONHEIM_BOUND:6<7"

    # 8. Uncovered t-subset when block count >= Schoenheim bound
    incomplete_7 = FANO_BLOCKS[:-1] + ((0, 1, 2),)
    r_unc = verifier.verify_design(
        CoveringDesignSpec(v=7, k=3, t=2, blocks=incomplete_7)
    )
    assert r_unc.is_valid is False
    assert r_unc.covered_t_subsets == 19
    assert r_unc.total_t_subsets == 21
    assert r_unc.reason_code == "HALT_UNCOVERED_T_SUBSET:(0, 6)"


def test_develop_cyclic_orbits_and_short_orbit_deduplication() -> None:
    # Base block (0, 2, 4) under Z_6 has stabilizer of index 2 -> only 2 distinct blocks
    short = develop_cyclic_orbits(6, 3, [(0, 2, 4)])
    assert short == ((0, 2, 4), (1, 3, 5))

    # k=1 valid orbit kills `0 < k` -> `1 < k`
    k1 = develop_cyclic_orbits(3, 1, [(0,)])
    assert k1 == ((0,), (1,), (2,))

    with pytest.raises(ValueError, match="HALT_INVALID_ORBIT_PARAMETERS"):
        develop_cyclic_orbits(6, 3, [])
    with pytest.raises(ValueError, match="HALT_INVALID_ORBIT_PARAMETERS"):
        develop_cyclic_orbits(True, 1, [(0,)])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="HALT_INVALID_ORBIT_PARAMETERS"):
        develop_cyclic_orbits(3, True, [(0,)])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="HALT_INVALID_ORBIT_PARAMETERS"):
        develop_cyclic_orbits(3, 0, [])
    with pytest.raises(ValueError, match="HALT_INVALID_ORBIT_PARAMETERS"):
        develop_cyclic_orbits(3, 5, [(0, 1, 2)])
    with pytest.raises(ValueError, match="HALT_INVALID_BASE_BLOCK"):
        develop_cyclic_orbits(6, 3, [(0, 0, 2)])
    with pytest.raises(ValueError, match="HALT_INVALID_BASE_BLOCK"):
        develop_cyclic_orbits(6, 3, [(0, 1, 6)])
    with pytest.raises(ValueError, match="HALT_INVALID_BASE_BLOCK"):
        develop_cyclic_orbits(6, 3, [(True, 1, 2)])  # type: ignore[list-item]


def test_search_orchestrator_fano_and_pg2_3_and_bisection() -> None:
    # 1. Fano plane C(7, 3, 2) = 7 discovered across the 15 0-anchored Z_7 orbits
    orch_default = LajollaSearchOrchestrator(v=7, k=3, t=2)
    assert orch_default.seed == 6 * 7
    default_epoch = orch_default.run_discovery_epoch()
    assert len(default_epoch) == 10

    orch7 = LajollaSearchOrchestrator(v=7, k=3, t=2, seed=42)
    single_epoch = orch7.run_discovery_epoch(iterations=1)
    assert len(single_epoch) == 1

    fano_spec = orch7.propose_cyclic_generator((0, 1, 3))
    assert fano_spec.blocks[0] == (0, 1, 3)
    assert fano_spec.blocks[1] == (1, 2, 4)

    orch7_full = LajollaSearchOrchestrator(v=7, k=3, t=2, seed=42)
    reports7 = orch7_full.run_discovery_epoch(iterations=15)
    assert len(reports7) == 15
    assert any(rep.is_valid for rep in reports7)
    for rep in reports7:
        assert not rep.reason_code.startswith("HALT_INVALID_BLOCK_CARDINALITY")
        assert not rep.reason_code.startswith("HALT_DUPLICATE_POINTS_IN_BLOCK")
    assert orch7_full.best_block_count == 7
    assert orch7_full.best_design is not None
    assert len(orch7_full.best_design.blocks) == 7

    # For C(4, 2, 1), comb(3, 1) = 3 distinct 0-anchored base blocks: (0,1), (0,2), (0,3)
    orch4 = LajollaSearchOrchestrator(v=4, k=2, t=1, seed=42)
    reports4 = orch4.run_discovery_epoch(iterations=3)
    assert len({r.receipt_caid for r in reports4}) == 2

    # Bisect critical block on exact 7-block Fano design -> block_6 (index 6) completes coverage
    bisect_exact = orch7_full.bisect_critical_block(orch7_full.best_design)
    assert bisect_exact.status == "FAILURE_BORDER_ISOLATED"
    assert bisect_exact.failing_index == 6
    assert bisect_exact.failing_item_id == "block_6"
    assert bisect_exact.border_verified is True

    # Bisect on an 8-block padded design -> still isolates index 6, showing block_7 is redundant
    padded_spec = CoveringDesignSpec(
        v=7,
        k=3,
        t=2,
        blocks=orch7_full.best_design.blocks + ((0, 1, 2),),
    )
    bisect_padded = orch7_full.bisect_critical_block(padded_spec)
    assert bisect_padded.status == "FAILURE_BORDER_ISOLATED"
    assert bisect_padded.failing_index == 6
    assert bisect_padded.failing_item_id == "block_6"

    # 2. Projective plane PG(2, 3): C(13, 4, 2) = 13 from Singer difference set (0, 1, 3, 9) mod 13
    orch13 = LajollaSearchOrchestrator(v=13, k=4, t=2, seed=42)
    pg_spec = orch13.propose_cyclic_generator((0, 1, 3, 9))
    pg_rep = orch13.evaluate_candidate(pg_spec)
    assert pg_rep.is_valid is True
    assert orch13.best_block_count == 13
    assert pg_rep.covered_t_subsets == 78

    # 3. Multi-orbit generator on C(7, 3, 2) and invalid seed / iterations
    multi_spec = orch7_full.propose_multi_orbit_generator([(0, 1, 3), (0, 1, 2)])
    multi_rep = orch7_full.evaluate_candidate(multi_spec)
    assert multi_rep.is_valid is True
    assert multi_rep.block_count == 14
    # Best block count stays at 7 (not overwritten by worse 14-block valid design)
    assert orch7_full.best_block_count == 7

    with pytest.raises(ValueError, match="HALT_INVALID_SEED"):
        LajollaSearchOrchestrator(v=7, k=3, t=2, seed=True)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="HALT_INVALID_ITERATION_COUNT"):
        orch7_full.run_discovery_epoch(iterations=0)
    with pytest.raises(ValueError, match="HALT_INVALID_ITERATION_COUNT"):
        orch7_full.run_discovery_epoch(iterations=True)  # type: ignore[arg-type]


def test_vesper_generator_hack_detection_gate_and_proposal_wiring() -> None:
    # 1. Clean algebraic generator using allowed math/itertools and non-dunder attributes passes
    clean_src = (
        "import itertools\n"
        "import math\n"
        "from math import comb\n"
        "def generate_base(ctx) -> tuple[int, ...]:\n"
        "    _ = math.comb(7, 3)\n"
        "    _ = ctx.__private_prefix\n"
        "    _ = ctx.suffix__\n"
        "    return (0, 1, 3)\n"
    )
    v_clean = GeneratorHackDetectionGate.inspect_generator_code(clean_src)
    assert v_clean.is_safe is True
    assert v_clean.reason_code == "OK_GENERATOR_AST_CLEAN"
    assert v_clean.receipt_caid.startswith("sha256:")
    with pytest.raises(dataclasses.FrozenInstanceError):
        v_clean.is_safe = False  # type: ignore[misc]

    orch = LajollaSearchOrchestrator(v=7, k=3, t=2, seed=42)
    verdict_ok, rep_ok = orch.evaluate_generator_proposal(clean_src, [(0, 1, 3)])
    assert verdict_ok.is_safe is True
    assert rep_ok is not None
    assert rep_ok.is_valid is True
    assert rep_ok.block_count == 7

    # 2. Empty / non-string / syntax error rejected
    for empty_in in ("", "   ", None):
        v_emp = GeneratorHackDetectionGate.inspect_generator_code(empty_in)  # type: ignore[arg-type]
        assert v_emp.is_safe is False
        assert v_emp.reason_code == "HALT_EMPTY_GENERATOR_SOURCE"

    v_syn = GeneratorHackDetectionGate.inspect_generator_code("def broken(:")
    assert v_syn.is_safe is False
    assert v_syn.reason_code == "HALT_GENERATOR_SYNTAX_ERROR"

    # 3. Forbidden imports (import os, from sys import modules, relative import)
    for imp_src, expected_reason in (
        ("import os\nx = 1", "HALT_FORBIDDEN_GENERATOR_IMPORT:os"),
        ("from sys import modules", "HALT_FORBIDDEN_GENERATOR_IMPORT:sys"),
        ("from . import helper", "HALT_FORBIDDEN_GENERATOR_IMPORT:relative"),
    ):
        v_imp = GeneratorHackDetectionGate.inspect_generator_code(imp_src)
        assert v_imp.is_safe is False
        assert v_imp.reason_code == expected_reason

    # 4. Global / nonlocal state mutation rejected
    for glob_src in (
        "def f():\n    global STATE\n    STATE = 1",
        "def outer():\n    x = 1\n    def inner():\n        nonlocal x\n        x = 2",
    ):
        v_glob = GeneratorHackDetectionGate.inspect_generator_code(glob_src)
        assert v_glob.is_safe is False
        assert v_glob.reason_code == "HALT_GENERATOR_GLOBAL_MUTATION"

    # 5. Dunder reflection and frame attribute access rejected
    dunder_name = "__" + "dict" + "__"
    v_dunder = GeneratorHackDetectionGate.inspect_generator_code(f"x = obj.{dunder_name}")
    assert v_dunder.is_safe is False
    assert v_dunder.reason_code == f"HALT_GENERATOR_REFLECTION_ACCESS:{dunder_name}"

    v_frame = GeneratorHackDetectionGate.inspect_generator_code("x = gen.f_locals")
    assert v_frame.is_safe is False
    assert v_frame.reason_code == "HALT_GENERATOR_REFLECTION_ACCESS:f_locals"

    # 6. Forbidden builtin calls (getattr, open, globals) rejected
    for call_src, expected_call in (
        ("x = getattr(obj, 'a')", "HALT_FORBIDDEN_GENERATOR_CALL:getattr"),
        ("x = open('coverdata.json')", "HALT_FORBIDDEN_GENERATOR_CALL:open"),
    ):
        v_call = GeneratorHackDetectionGate.inspect_generator_code(call_src)
        assert v_call.is_safe is False
        assert v_call.reason_code == expected_call

    # 7. Verifier / baseline symbol tampering rejected and blocked before verifier runs
    hack_src = "def cheat():\n    return PinnedBaseline()\n"
    verdict_bad, rep_bad = orch.evaluate_generator_proposal(hack_src, [(0, 1, 3)])
    assert verdict_bad.is_safe is False
    assert verdict_bad.reason_code == "HALT_VERIFIER_STATE_TAMPER_ATTEMPT:PinnedBaseline"
    assert rep_bad is None
