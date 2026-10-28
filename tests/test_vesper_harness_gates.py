#!/usr/bin/env python3
"""
Falsification Suite for Dual-VESPER Combinatorial Discovery Harness (`src/vesper_harness_gates.py`).
"""

import pytest

from src.vesper_harness_gates import (
    HackDetectionGate,
    HistoryDistiller,
    LajollaCoveringVerifier,
    TrialRecord,
    VesperDiscoveryHarness,
    sha256_jcs_caid,
)


def test_1_hack_gate_blocks_scorer_imports_and_dunders() -> None:
    malicious_import = "import evaluator\ndef generate_blocks(v, k, t):\n    return evaluator.ANS\n"
    ok_imp, reason_imp = HackDetectionGate.inspect_candidate(malicious_import)
    assert ok_imp is False
    assert reason_imp == "HALT_HACK_FORBIDDEN_IMPORT:evaluator"

    malicious_from = "from scorer.internal import ans\ndef generate_blocks(v, k, t):\n    return ans\n"
    ok_from, reason_from = HackDetectionGate.inspect_candidate(malicious_from)
    assert ok_from is False
    assert reason_from == "HALT_HACK_FORBIDDEN_IMPORT:scorer.internal"

    malicious_rel = "from . import helper\ndef generate_blocks(v, k, t):\n    return []\n"
    ok_rel, reason_rel = HackDetectionGate.inspect_candidate(malicious_rel)
    assert ok_rel is False
    assert reason_rel == "HALT_HACK_FORBIDDEN_IMPORT:relative"

    malicious_dunder = "def generate_blocks(v, k, t):\n    return __builtins__['eval']('1')\n"
    ok_dun, reason_dun = HackDetectionGate.inspect_candidate(malicious_dunder)
    assert ok_dun is False
    assert reason_dun == "HALT_HACK_DUNDER_ACCESS:__builtins__"

    # Defect 2 regression: object-hierarchy dunder traversal `().__class__.__bases__[0]`
    malicious_cls_dunder = (
        "def generate_blocks(v, k, t):\n"
        "    root = ().__class__.__bases__[0]\n"
        "    return [(0, 1, 3)]\n"
    )
    ok_cls, reason_cls = HackDetectionGate.inspect_candidate(malicious_cls_dunder)
    assert ok_cls is False
    assert reason_cls in {"HALT_HACK_DUNDER_ACCESS:__class__", "HALT_HACK_DUNDER_ACCESS:__bases__"}


def test_2_hack_gate_blocks_float_calls_float_literals_and_python3_true_division() -> None:
    # 1. Explicit float() call
    ok_call, r_call = HackDetectionGate.inspect_candidate(
        "def generate_blocks(v, k, t):\n    return float(1)\n"
    )
    assert ok_call is False
    assert r_call == "HALT_HACK_FLOAT_PRECISION_EXPLOIT"

    # 2. Raw float literal (0.1 + 0.2)
    ok_lit, r_lit = HackDetectionGate.inspect_candidate(
        "def generate_blocks(v, k, t):\n    return 0.1 + 0.2\n"
    )
    assert ok_lit is False
    assert r_lit == "HALT_HACK_FLOAT_PRECISION_EXPLOIT"

    # 3. F1 Probe: Python 3 true division `1 / 3` (produces float without float literals!)
    ok_div, r_div = HackDetectionGate.inspect_candidate(
        "def generate_blocks(v, k, t):\n    return (1 / 10 + 2 / 10) == (3 / 10)\n"
    )
    assert ok_div is False
    assert r_div == "HALT_HACK_FLOAT_TRUE_DIVISION_EXPLOIT"

    # 4. Forbidden calls, top-level call, global mutation, syntax error, empty source
    ok_eval, r_eval = HackDetectionGate.inspect_candidate(
        "def generate_blocks(v, k, t):\n    return getattr(v, 'x')\n"
    )
    assert ok_eval is False
    assert r_eval == "HALT_HACK_FORBIDDEN_CALL:getattr"

    ok_top, r_top = HackDetectionGate.inspect_candidate(
        "X = sorted([3, 1, 2])\ndef generate_blocks(v, k, t):\n    return []\n"
    )
    assert ok_top is False
    assert r_top == "HALT_TOP_LEVEL_CALL_FORBIDDEN"

    ok_glob, r_glob = HackDetectionGate.inspect_candidate(
        "def generate_blocks(v, k, t):\n    global X\n    return []\n"
    )
    assert ok_glob is False
    assert r_glob == "HALT_HACK_GLOBAL_MUTATION_FORBIDDEN"

    ok_syn, r_syn = HackDetectionGate.inspect_candidate("def generate_blocks(:\n")
    assert ok_syn is False
    assert r_syn.startswith("HALT_SYNTAX_ERROR:")

    ok_empty, r_empty = HackDetectionGate.inspect_candidate("   ")
    assert ok_empty is False
    assert r_empty == "HALT_EMPTY_CANDIDATE_AST"

    ok_comment, r_comment = HackDetectionGate.inspect_candidate("# comment only\n")
    assert ok_comment is False
    assert r_comment == "HALT_EMPTY_CANDIDATE_AST"

    ok_nonstr, r_nonstr = HackDetectionGate.inspect_candidate(None)  # type: ignore[arg-type]
    assert ok_nonstr is False
    assert r_nonstr == "HALT_EMPTY_CANDIDATE_AST"


def test_3_real_cyclic_generator_proves_optimal_c_7_3_2_fano_covering() -> None:
    cyclic_fano_code = (
        "import itertools\n"
        "def generate_blocks(v: int, k: int, t: int):\n"
        "    base = (0, 1, 3)\n"
        "    return [tuple(sorted((x + shift) % v for x in base)) for shift in range(v)]\n"
    )
    harness = VesperDiscoveryHarness(v=7, k=3, t=2)
    res = harness.evaluate_candidate("cand_cyclic_fano", cyclic_fano_code)
    assert res.is_hack_suspected is False
    assert res.is_valid_covering is True
    assert res.blocks_used == 7
    assert res.missing_subsets_count == 0
    assert res.halt_or_status_code == "OK_COVERING_DESIGN_EXHAUSTIVELY_VERIFIED"
    assert len(res.receipt_caid) == len("sha256:") + 64
    assert len(harness.trials) == 1
    assert harness.trials[0].generation == 1
    assert harness.trials[0].blocks_used == 7
    assert harness.trials[0].missing_subsets == 0


def test_4_incomplete_generator_fails_closed_with_exact_missing_subset_count() -> None:
    incomplete_code = (
        "def generate_blocks(v: int, k: int, t: int):\n"
        "    base = (0, 1, 3)\n"
        "    return [tuple(sorted((x + shift) % v for x in base)) for shift in range(3)]\n"
    )
    harness = VesperDiscoveryHarness(v=7, k=3, t=2)
    res = harness.evaluate_candidate("cand_incomplete", incomplete_code)
    assert res.is_hack_suspected is False
    assert res.is_valid_covering is False
    assert res.blocks_used == 3
    assert res.missing_subsets_count > 0
    assert res.missing_subsets_count == 12
    assert res.halt_or_status_code == "HALT_BLOCK_COUNT_BELOW_SCHONHEIM_BOUND:3<7"

    # Enough blocks (>=7) but duplicated so still missing subsets
    dup_blocks_code = (
        "def generate_blocks(v: int, k: int, t: int):\n"
        "    return [(0, 1, 2)] * 7\n"
    )
    res_uncovered = harness.evaluate_candidate("cand_dup7", dup_blocks_code)
    assert res_uncovered.is_hack_suspected is False
    assert res_uncovered.is_valid_covering is False
    assert res_uncovered.blocks_used == 7
    assert res_uncovered.missing_subsets_count == 18
    assert res_uncovered.halt_or_status_code == "HALT_UNCOVERED_T_SUBSETS:18"


def test_5_history_distiller_compresses_lineage_under_60_words() -> None:
    assert (
        HistoryDistiller.distill_signal([])
        == "GEN 0: No history. Propose initial cyclic base block mod v."
    )
    short_signal = HistoryDistiller.distill_signal([TrialRecord(1, 65, 286, 59)])
    assert "Velocity: Insufficient data." in short_signal

    trials = [
        TrialRecord(1, 65, 286, 59),
        TrialRecord(2, 62, 140, 59),
        TrialRecord(3, 60, 45, 59),
    ]
    signal = HistoryDistiller.distill_signal(trials)
    assert "Gap: 1\n" in signal
    assert "Velocity: +241 subsets/3 gens, +5 blocks saved/3 gens." in signal
    assert "DIRECTIVE:" in signal
    assert len(signal.split()) < 60


def test_6_out_of_process_isolation_and_verifier_edge_cases() -> None:
    harness = VesperDiscoveryHarness(v=7, k=3, t=2, timeout_sec=1.0)

    # Candidate blocked by pre-flight gate
    res_hack = harness.evaluate_candidate("cand_hack", "import os\ndef generate_blocks(v, k, t): return []\n")
    assert res_hack.is_hack_suspected is True
    assert res_hack.blocks_used == -1
    assert res_hack.halt_or_status_code == "HALT_HACK_FORBIDDEN_IMPORT:os"

    # Candidate missing generate_blocks entrypoint
    res_missing_fn = harness.evaluate_candidate("cand_no_fn", "def other_fn(v, k, t):\n    return []\n")
    assert res_missing_fn.is_hack_suspected is True
    assert res_missing_fn.halt_or_status_code == "HALT_MISSING_GENERATE_BLOCKS_ENTRYPOINT"

    # Candidate raising runtime exception in child process
    res_exc = harness.evaluate_candidate(
        "cand_exc",
        "def generate_blocks(v, k, t):\n    return [1 // 0]\n",
    )
    assert res_exc.is_hack_suspected is True
    assert res_exc.halt_or_status_code == "HALT_CANDIDATE_RUNTIME_EXCEPTION"

    # Candidate returning non-sequence or non-integer point
    res_bad_ret = harness.evaluate_candidate(
        "cand_bad_ret",
        "def generate_blocks(v, k, t):\n    return 42\n",
    )
    assert res_bad_ret.is_hack_suspected is True
    assert res_bad_ret.halt_or_status_code == "HALT_INVALID_GENERATOR_RETURN_TYPE"

    res_bool_pt = harness.evaluate_candidate(
        "cand_bool_pt",
        "def generate_blocks(v, k, t):\n    return [(True, 1, 2)]\n",
    )
    assert res_bool_pt.is_hack_suspected is True
    assert res_bool_pt.halt_or_status_code == "HALT_NON_INTEGER_POINT"

    # Direct verifier validation checks
    assert LajollaCoveringVerifier.compute_schonheim_bound(7, 7, 2) == 1
    assert LajollaCoveringVerifier.compute_schonheim_bound(5, 7, 2) == 0
    assert LajollaCoveringVerifier.compute_schonheim_bound(7, 3, 0) == 0
    with pytest.raises(ValueError, match="ERR_INVALID_COVERING_PARAMETERS"):
        LajollaCoveringVerifier.compute_schonheim_bound(True, 3, 2)
    with pytest.raises(ValueError, match="ERR_INVALID_COVERING_PARAMETERS"):
        LajollaCoveringVerifier.verify_blocks(7, 8, 2, [])
    with pytest.raises(ValueError, match="ERR_INVALID_COVERING_PARAMETERS"):
        VesperDiscoveryHarness(v=0, k=3, t=2)
    with pytest.raises(ValueError, match="ERR_INVALID_BLOCKS_CONTAINER"):
        LajollaCoveringVerifier.verify_blocks(7, 3, 2, "not_blocks")  # type: ignore[arg-type]

    bad_card = LajollaCoveringVerifier.verify_blocks(7, 3, 2, [(0, 1)])
    assert bad_card.is_valid_covering is False
    assert bad_card.halt_reason == "HALT_BLOCK_CARDINALITY_MISMATCH_AT_INDEX:0"

    bad_dup = LajollaCoveringVerifier.verify_blocks(7, 3, 2, [(0, 0, 1)])
    assert bad_dup.is_valid_covering is False
    assert bad_dup.halt_reason == "HALT_INVALID_OR_DUPLICATE_POINTS_AT_INDEX:0"

    bad_bool = LajollaCoveringVerifier.verify_blocks(7, 3, 2, [(True, 1, 2)])
    assert bad_bool.is_valid_covering is False
    assert bad_bool.halt_reason == "HALT_INVALID_OR_DUPLICATE_POINTS_AT_INDEX:0"

    bad_str_pt = LajollaCoveringVerifier.verify_blocks(7, 3, 2, [("0", 1, 2)])  # type: ignore[list-item]
    assert bad_str_pt.is_valid_covering is False
    assert bad_str_pt.halt_reason == "HALT_INVALID_OR_DUPLICATE_POINTS_AT_INDEX:0"

    with pytest.raises(ValueError, match="ERR_FLOAT_FORBIDDEN_IN_JCS"):
        sha256_jcs_caid({"x": 0.5})
    with pytest.raises(ValueError, match="ERR_NON_STRING_KEY"):
        sha256_jcs_caid({1: "a"})
    assert sha256_jcs_caid(b"abc").startswith("sha256:")
    assert sha256_jcs_caid("abc").startswith("sha256:")
