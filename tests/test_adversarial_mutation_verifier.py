#!/usr/bin/env python3
"""
Unit and Falsification Suite for `src/adversarial_mutation_verifier.py`.
Verifies semantic AST mutant generation, out-of-process isolated execution,
and zero-tolerance blocking for security-sensitive survivors.
"""

from typing import Any, Dict

import pytest

from src.adversarial_mutation_verifier import (
    DEFAULT_MAX_MUTANTS,
    DEFAULT_MINIMUM_SCORE_BPS,
    AdversarialMutationVerifier,
    sha256_caid,
)


def test_1_generates_all_four_semantic_mutant_families() -> None:
    source = (
        "def check_bounds(x, y, n):\n"
        "    if x > 10 and y <= 20:\n"
        "        total = 0\n"
        "        for i in range(n):\n"
        "            if i == 2 or i != 5:\n"
        "                total += 1\n"
        "        return total\n"
        "    if x >= 100:\n"
        "        return 99\n"
        "    if y < 0:\n"
        "        return 1\n"
        "    return 0\n"
    )
    verifier = AdversarialMutationVerifier()
    assert verifier.minimum_score_bps == DEFAULT_MINIMUM_SCORE_BPS
    assert verifier.max_mutants == DEFAULT_MAX_MUTANTS
    mutants = verifier.generate_semantic_mutants("src/utils/calc.py", source)
    assert [m.mutant_id for m in mutants] == [
        f"MUT_{i:02d}" for i in range(1, len(mutants) + 1)
    ]
    classes = {m.mutation_class for m in mutants}
    assert "CMP_BOUNDARY_GT_TO_GTE" in classes
    assert "CMP_BOUNDARY_LTE_TO_LT" in classes
    assert "CMP_BOUNDARY_GTE_TO_GT" in classes
    assert "CMP_BOUNDARY_LT_TO_LTE" in classes
    assert "CMP_INVERT_EQ_TO_NEQ" in classes
    assert "CMP_INVERT_NEQ_TO_EQ" in classes
    assert "OFF_BY_ONE_RANGE" in classes
    assert "BOOL_CONJUNCTION_SWAP" in classes
    assert "CONST_OFF_BY_ONE" in classes

    range_mut = next(m for m in mutants if m.mutation_class == "OFF_BY_ONE_RANGE")
    assert range_mut.original_snippet == "range(n)"
    assert range_mut.mutated_snippet == "range(n + 1)"
    assert range_mut.line_number == 4

    const_muts = [m for m in mutants if m.mutation_class == "CONST_OFF_BY_ONE"]
    assert any(m.original_snippet == "0" and m.mutated_snippet == "1" for m in const_muts)
    assert any(m.original_snippet == "10" and m.mutated_snippet == "11" for m in const_muts)

    bool_mut = next(m for m in mutants if m.mutation_class == "BOOL_CONJUNCTION_SWAP")
    assert bool_mut.line_number == 2
    assert bool_mut.required_test_name == "test_boolean_clauses_line_2"

    # Verify bool constants (True) are not perturbed while int 0 is perturbed to 1
    bool_vs_int_muts = verifier.generate_semantic_mutants(
        "src/utils/neg.py", "def g():\n    a = True\n    b = 0\n    return b\n"
    )
    assert len(bool_vs_int_muts) == 1
    assert bool_vs_int_muts[0].mutant_id == "MUT_01"
    assert bool_vs_int_muts[0].original_snippet == "0"
    assert bool_vs_int_muts[0].mutated_snippet == "1"
    assert bool_vs_int_muts[0].line_number == 3
    assert bool_vs_int_muts[0].required_test_name == "test_exact_constant_line_3"


def test_2_security_sensitive_survivor_blocks_merge_even_above_9000_bps() -> None:
    """
    Demonstrates Lesson L27 / L29:
    Even when 10/11 mutants are killed (9090 bps >= 9000 bps), 1 surviving
    boundary mutant in `src/auth/token_guard.py` triggers `BLOCK_MERGE`.
    """
    source = (
        "def verify_token_window(now_ts, exp_ts, role_id, a, b, c, d):\n"
        "    if role_id == 1 and a == 2 and b == 3 and c == 4 and d == 5:\n"
        "        return now_ts < exp_ts\n"
        "    return False\n"
    )

    def weak_oracle(ns: Dict[str, Any]) -> None:
        fn = ns["verify_token_window"]
        # Tests strict inequality (now_ts=100, exp_ts=200) and > (300, 200),
        # but omits the exact boundary `now_ts == exp_ts` (200, 200)!
        assert fn(100, 200, 1, 2, 3, 4, 5) is True
        assert fn(300, 200, 1, 2, 3, 4, 5) is False
        assert fn(100, 200, 0, 2, 3, 4, 5) is False
        assert fn(100, 200, 1, 9, 3, 4, 5) is False
        assert fn(100, 200, 1, 2, 9, 4, 5) is False
        assert fn(100, 200, 1, 2, 3, 9, 5) is False
        assert fn(100, 200, 1, 2, 3, 4, 9) is False

    verifier = AdversarialMutationVerifier(minimum_score_bps=9000, max_mutants=30)
    report = verifier.evaluate_mutation_adequacy(
        "src/auth/token_guard.py", source, weak_oracle
    )
    assert report.total_mutants == 12
    assert report.survived == 1
    assert report.killed == 11
    assert report.mutation_score_bps == 9166  # 11/12 = 91.66% >= 9000 bps
    assert report.security_sensitive_survivors == 1
    assert report.verdict == "BLOCK_MERGE"
    assert "Security-sensitive survivor detected" in report.reason
    assert report.survivors[0].mutation_class == "CMP_BOUNDARY_LT_TO_LTE"
    assert report.survivors[0].security_sensitive is True
    assert report.report_caid.startswith("sha256:")

    # Adding the exact boundary test `fn(200, 200, ...) is False` kills all 15/15 mutants!
    def strong_oracle(ns: Dict[str, Any]) -> None:
        weak_oracle(ns)
        assert ns["verify_token_window"](200, 200, 1, 2, 3, 4, 5) is False

    report_strong = verifier.evaluate_mutation_adequacy(
        "src/auth/token_guard.py", source, strong_oracle
    )
    assert report_strong.survived == 0
    assert report_strong.security_sensitive_survivors == 0
    assert report_strong.mutation_score_bps == 10000
    assert report_strong.verdict == "ALLOW_MERGE"


def test_3_low_score_blocks_merge_on_both_non_security_and_security_paths() -> None:
    source = (
        "def accumulate(n):\n"
        "    s = 0\n"
        "    for i in range(n):\n"
        "        if i >= 0:\n"
        "            s += 1\n"
        "    return s\n"
    )

    def trivial_oracle(ns: Dict[str, Any]) -> None:
        # Loose inequality (`>= 0`) fails to kill off-by-one and constant mutants
        assert ns["accumulate"](3) >= 0

    verifier = AdversarialMutationVerifier(minimum_score_bps=9000, max_mutants=5)
    rep_non_sec = verifier.evaluate_mutation_adequacy(
        "src/math_utils/helper.py", source, trivial_oracle
    )
    assert rep_non_sec.mutation_score_bps < 9000
    assert rep_non_sec.security_sensitive_survivors == 0
    assert rep_non_sec.verdict == "BLOCK_MERGE"
    assert "below threshold" in rep_non_sec.reason

    rep_sec = verifier.evaluate_mutation_adequacy(
        "src/payment/ledger.py", source, trivial_oracle
    )
    assert rep_sec.mutation_score_bps < 9000
    assert rep_sec.security_sensitive_survivors > 0
    assert rep_sec.verdict == "BLOCK_MERGE"
    assert "security-sensitive survivor(s) detected" in rep_sec.reason
    assert rep_sec.equivalent_mutants == 0
    assert rep_sec.unverified_mutants == 0
    d = rep_sec.to_dict()
    assert d["verdict"] == "BLOCK_MERGE"
    assert d["equivalent_mutants"] == 0
    assert d["unverified_mutants"] == 0
    assert len(d["survivors"]) == rep_sec.survived
    first_surv = d["survivors"][0]
    assert isinstance(first_surv, dict)
    assert first_surv["file"] == "src/payment/ledger.py"
    assert first_surv["security_sensitive"] is True
    assert first_surv["mutant_id"].startswith("MUT_")


def test_4_out_of_process_isolated_runner_and_controls() -> None:
    source = (
        "def is_valid_amount(cents):\n"
        "    return cents > 0\n"
    )
    test_source_strong = (
        "def test_exact_boundary(ns):\n"
        "    fn = ns['is_valid_amount']\n"
        "    assert fn(1) is True\n"
        "    assert fn(0) is False\n"
    )
    verifier = AdversarialMutationVerifier(minimum_score_bps=9000, max_mutants=10)
    rep = verifier.evaluate_mutation_adequacy_isolated(
        "src/payment/amount.py", source, test_source_strong
    )
    assert rep.verdict == "ALLOW_MERGE"
    assert rep.killed == rep.total_mutants
    assert rep.survived == 0

    test_source_weak = (
        "def test_weak(ns):\n"
        "    fn = ns['is_valid_amount']\n"
        "    assert fn(10) is True\n"
        "    assert fn(-5) is False\n"
    )
    rep_weak = verifier.evaluate_mutation_adequacy_isolated(
        "src/payment/amount.py", source, test_source_weak
    )
    assert rep_weak.verdict == "BLOCK_MERGE"
    assert rep_weak.survived > 0

    with pytest.raises(RuntimeError, match="ERR_ISOLATED_TOKEN_OR_STATUS_INVALID"):
        verifier.evaluate_mutation_adequacy_isolated(
            "src/payment/amount.py", source, "x = 1\n"
        )

    with pytest.raises(RuntimeError, match="ERR_ISOLATED_MUTATION_RUNNER_FAILED"):
        verifier.evaluate_mutation_adequacy_isolated(
            "src/payment/amount.py", source, "def test_fail(ns):\n    assert False\n"
        )


def test_5_constructor_and_empty_mutant_guards() -> None:
    import dataclasses
    import inspect
    from src.adversarial_mutation_verifier import SurvivingMutantRecord

    assert DEFAULT_MINIMUM_SCORE_BPS == 9000
    assert inspect.signature(AdversarialMutationVerifier.evaluate_mutation_adequacy_isolated).parameters["timeout_seconds"].default == 10

    surv = SurvivingMutantRecord(
        mutant_id="M1",
        file="src/auth.py",
        line_number=10,
        mutation_class="CMP",
        mutation="x > 0 -> x >= 0",
        security_sensitive=True,
        reason="survived",
        required_test="test_auth_boundary",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        surv.line_number = 20  # type: ignore

    with pytest.raises(ValueError, match="ERR_INVALID_MINIMUM_SCORE_BPS"):
        AdversarialMutationVerifier(minimum_score_bps=0)
    with pytest.raises(ValueError, match="ERR_INVALID_MINIMUM_SCORE_BPS"):
        AdversarialMutationVerifier(minimum_score_bps=10001)
    with pytest.raises(ValueError, match="ERR_INVALID_MAX_MUTANTS"):
        AdversarialMutationVerifier(minimum_score_bps=9000, max_mutants=0)

    v_min1 = AdversarialMutationVerifier(minimum_score_bps=1, max_mutants=1)
    assert v_min1.minimum_score_bps == 1

    verifier = AdversarialMutationVerifier(minimum_score_bps=10000, max_mutants=1)
    m_single = verifier.generate_semantic_mutants(
        "src/a.py", "def f(x):\n    return x > 0 and x < 10\n"
    )
    assert len(m_single) == 1
    with pytest.raises(Exception):
        m_single[0].line_number = 99  # type: ignore[misc]

    with pytest.raises(ValueError, match="ERR_NO_MUTANTS_GENERATED"):
        verifier.evaluate_mutation_adequacy("src/empty.py", "def f(x):\n    return x\n", lambda ns: None)
    with pytest.raises(ValueError, match="ERR_NO_MUTANTS_GENERATED"):
        verifier.evaluate_mutation_adequacy_isolated("src/empty.py", "def f(x):\n    return x\n", "def test_a(ns): pass\n")

    assert sha256_caid(b"abc") == sha256_caid("abc")
    assert sha256_caid({"a": 1}).startswith("sha256:")

    # Verify report_caid exact binding to unsigned payload with equivalent_mutants == 0
    def _oracle(ns: Dict[str, Any]) -> None:
        assert ns["f"](0) is False
        assert ns["f"](1) is True

    rep_nom = verifier.evaluate_mutation_adequacy(
        "src/ok.py",
        "def f(x):\n    return x > 0\n",
        _oracle,
    )
    expected_caid = sha256_caid(
        {
            "equivalent_mutants": 0,
            "file_path": "src/ok.py",
            "killed": 1,
            "mutation_score_bps": 10000,
            "reason": "All 1/1 mutants killed (10000 bps) with 0 security-sensitive survivors",
            "security_sensitive_survivors": 0,
            "survived": 0,
            "survivors": [],
            "total_mutants": 1,
            "unverified_mutants": 0,
            "verdict": "ALLOW_MERGE",
        }
    )
    assert rep_nom.report_caid == expected_caid

