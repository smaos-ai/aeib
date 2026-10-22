#!/usr/bin/env python3
# File: tests/test_aeib_2026_unified_metrics_evaluator.py
"""
Tests for AEIB / SMF Unified Evaluation Suite (Handbook Categories #4-#12 + 2026 SOTA).
"""

from pathlib import Path
import pytest

from tools.aeib_2026_unified_metrics_evaluator import (
    SqlEvalCase,
    compute_adjusted_rand_index,
    compute_mrr,
    compute_ndcg_at_k,
    compute_pass_at_k,
    compute_tau_bench_pass_hat_k,
    evaluate_bird_sql_and_secure_ves,
    run_full_handbook_and_2026_sota_audit,
    test_aeib_unified_handbook_and_2026_metrics,
)


def test_mrr_and_ndcg_at_k_calculation() -> None:
    # 1st item relevant -> 1.0
    assert compute_mrr([[1, 0, 0]]) == 1.0
    # 2nd item relevant -> 0.5
    assert compute_mrr([[0, 1, 0]]) == 0.5
    # No relevant items -> 0.0
    assert compute_mrr([[0, 0, 0]]) == 0.0

    # NDCG@5 ideal match -> 1.0
    graded = [3, 2, 1, 0, 0]
    assert compute_ndcg_at_k(graded, 5) == 1.0


def test_pass_at_k_vs_tau_bench_pass_hat_k_gap() -> None:
    # 5 successes out of 10 trials, k=5
    # Pass@5 is optimistic: 1 - comb(5, 5) / comb(10, 5) = 1 - 1/252 ~= 0.996
    pass_at_5 = compute_pass_at_k(10, 5, 5)
    assert pass_at_5 > 0.99

    # tau-bench Pass^5 requires ALL 5 to succeed: comb(5, 5) / comb(10, 5) = 1/252 ~= 0.004
    pass_hat_5 = compute_tau_bench_pass_hat_k(10, 5, 5)
    assert pass_hat_5 < 0.01

    # When all 10 succeed, both Pass@5 and Pass^5 equal 1.0
    assert compute_pass_at_k(10, 10, 5) == 1.0
    assert compute_tau_bench_pass_hat_k(10, 10, 5) == 1.0


def test_bird_sql_and_secure_ves_with_rls() -> None:
    cases = [
        SqlEvalCase("q1_safe", True, 10.0, 10.0, has_rls_tenant_binding=True),
        SqlEvalCase("q2_unsafe", True, 10.0, 10.0, has_rls_tenant_binding=False),
    ]
    res = evaluate_bird_sql_and_secure_ves(cases)
    assert res["EX_pct"] == 100.0
    assert res["VES_score"] == 100.0
    # S-VES drops because q2 lacks RLS binding
    assert res["S_VES_score"] == 50.0
    assert res["RLS_Violation_Block_Rate_pct"] == 100.0


def test_adjusted_rand_index_clustering() -> None:
    labels = [0, 0, 1, 1, 2, 2]
    # Perfect clustering
    assert compute_adjusted_rand_index(labels, labels) == 1.0
    # Dissimilar clustering
    assert compute_adjusted_rand_index(labels, [2, 1, 0, 2, 1, 0]) < 0.5


def test_unified_audit_suite_execution() -> None:
    test_aeib_unified_handbook_and_2026_metrics()
    audit = run_full_handbook_and_2026_sota_audit()
    assert len(audit) == 6
    for cat_name, metrics in audit.items():
        assert metrics["status"] == "EVALUATED_AND_TESTED"


def test_banned_words_absence() -> None:
    banned = [
        "guaran" + "teed",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "proven universal" + "ly",
        "unhack" + "able",
    ]
    repo_root = Path(__file__).resolve().parent.parent
    for rel in (
        "tools/aeib_2026_unified_metrics_evaluator.py",
        "tests/test_aeib_2026_unified_metrics_evaluator.py",
    ):
        text = (repo_root / rel).read_text(encoding="utf-8").lower()
        for w in banned:
            assert w not in text, f"Forbidden word found in {rel}"
