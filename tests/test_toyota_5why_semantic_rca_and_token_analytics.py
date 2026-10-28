#!/usr/bin/env python3
# File: tests/test_toyota_5why_semantic_rca_and_token_analytics.py
"""
Verification & Falsification Suite (`--falsify`) for:
1. `AntigravityArgonFlashTokenAnalyticsEngine` (`Gemini 4 Argon` vs. `Gemini 3.8 Flash`
   WITH vs. WITHOUT system token/cost analytics & Super-Prompt prefix amortization).
2. `HybridSemanticAstSearchEngine` (BM25 + Trigram Semantic Cosine + AST Call-Graph RRF).
3. `Toyota5WhyCausalRootCauseEngine` (`TRACE` + `EvoCause` arXiv:2607.27290 + TPS `Poka-Yoke`).
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.toyota_5why_semantic_rca_and_token_analytics import (
    AntigravityArgonFlashTokenAnalyticsEngine,
    HybridSemanticAstSearchEngine,
    IndexedCorpusNode,
    PokaYokeMistakeProofGate,
    Toyota5WhyCausalRootCauseEngine,
    WhyCausalHop,
    canonical_jcs_bytes,
    sha256_prefixed,
)


def test_argon4_and_flash38_with_vs_without_token_and_cost_analytics() -> None:
    report = AntigravityArgonFlashTokenAnalyticsEngine.evaluate_20_task_sprint(
        sub_intents_in_super_prompt=6
    )
    assert report.tasks_evaluated == 4 * 5
    assert (
        report.without_system_total_tokens
        == report.without_system_input_tokens + report.without_system_output_tokens
    )
    assert (
        report.with_system_total_tokens
        == report.with_system_input_tokens + report.with_system_output_tokens
    )
    expected_reduction_bps = (
        (report.without_system_total_tokens - report.with_system_total_tokens) * 10000
    ) // report.without_system_total_tokens
    assert report.total_token_reduction_bps == expected_reduction_bps

    # Verify cost hierarchy: Hybrid Cascade < Argon 4 WITH < Argon 4 WITHOUT
    assert report.argon4_without_cost_cents == 443  # $4.43 per 20-task sprint without system
    assert report.argon4_with_cost_cents == 93      # $0.93 per 20-task sprint on Argon 4 with system (79.0% cost cut)
    assert report.flash38_without_cost_cents == 73  # $0.73 per 20-task sprint on Flash 3.8 without system
    assert report.flash38_with_cost_cents == 15     # $0.15 per 20-task sprint on Flash 3.8 with system
    assert report.hybrid_cascade_with_cost_cents == 38  # $0.38 per 20-task sprint on Hybrid System-1/2 (91.4% vs Argon naive!)
    assert report.super_prompt_prefix_savings_bps == (5 * 10000) // 6


def test_hybrid_semantic_bm25_ast_rrf_typo_resilient_search() -> None:
    nodes = [
        IndexedCorpusNode(
            "node-kernel",
            "src/ncm_parallel_burst_latch.py",
            "CrossCallerGroupCommitLatch",
            "Hardware NVMe Darwin F_FULLFSYNC and Linux io_uring batch group commit",
            ("os.fsync", "fcntl.fcntl"),
            "sha256:k1",
        ),
        IndexedCorpusNode(
            "node-ebpf",
            "src/bpf_lsm_profile_compiler.py",
            "BPFLSMProfileCompiler",
            "Compiles Linux kernel BPF_LSM Tetragon TracingPolicy YAML profiles",
            ("parse_yaml_tracing_policy", "BPFLSMStaticLinter"),
            "sha256:k2",
        ),
        IndexedCorpusNode(
            "node-econ",
            "tools/builder_breaker_adversarial_engine.py",
            "TokenEconomizerController",
            "Prunes unused MCP tool schemas after 5 idle turns to reduce token consumption",
            ("record_turn_and_prune",),
            "sha256:k3",
        ),
    ]
    engine = HybridSemanticAstSearchEngine(nodes)

    # Query with natural typos ("kernael", "consuption") still ranks exact symbol #1 via trigram + BM25 + AST RRF
    res_kernel = engine.search_rrf("kernael hardware F_FULLFSYNC group commit", top_k=1)
    assert res_kernel[0][0].symbol_name == "CrossCallerGroupCommitLatch"

    res_econ = engine.search_rrf("tokenst consuption prune unused tool", top_k=1)
    assert res_econ[0][0].symbol_name == "TokenEconomizerController"


def test_toyota_5why_causal_dag_and_falsification_vectors() -> None:
    priv = Ed25519PrivateKey.generate()

    h1 = WhyCausalHop(1, "SYMPTOM", "Q1", "F1", "n1", "sha256:e1", "sha256:genesis-root-symptom")
    c1 = sha256_prefixed(canonical_jcs_bytes(asdict(h1)))
    h2 = WhyCausalHop(2, "EXECUTION_TRACE", "Q2", "F2", "n1", "sha256:e2", c1)
    c2 = sha256_prefixed(canonical_jcs_bytes(asdict(h2)))
    h3 = WhyCausalHop(3, "GUARDRAIL_GAP", "Q3", "F3", "n1", "sha256:e3", c2)
    c3 = sha256_prefixed(canonical_jcs_bytes(asdict(h3)))
    h4 = WhyCausalHop(4, "ARCHITECTURAL_COUPLING", "Q4", "F4", "n1", "sha256:e4", c3)
    c4 = sha256_prefixed(canonical_jcs_bytes(asdict(h4)))
    h5 = WhyCausalHop(5, "SYSTEMIC_AXIOM_ROOT", "Q5", "F5", "n1", "sha256:e5", c4)

    valid_py = PokaYokeMistakeProofGate(
        "PY-01", "sha256:e5", "Enforce AST slice + 5-turn pruning", "src/decide.py", 10000
    )

    receipt = Toyota5WhyCausalRootCauseEngine.verify_and_sign_5why_chain(
        "Token bloat RCA",
        "token cost ci cd kernael tayota 5 why sinarghy",
        (h1, h2, h3, h4, h5),
        valid_py,
        priv,
    )
    assert len(receipt.decomposed_sub_intents) == 5

    # Falsification 1: Circular causal cycle (reusing sha256:e1 at level 5) rejected (`EvoCause` DAG invariant)
    h5_cycle = WhyCausalHop(5, "SYSTEMIC_AXIOM_ROOT", "Q5", "F5", "n1", "sha256:e1", c4)
    with pytest.raises(ValueError, match="HALT_TOYOTA_5WHY_CIRCULAR_CAUSAL_CYCLE_DETECTED"):
        Toyota5WhyCausalRootCauseEngine.verify_and_sign_5why_chain(
            "Cycle test", "tayota 5 why", (h1, h2, h3, h4, h5_cycle), valid_py, priv
        )

    # Falsification 2: Broken parent link rejected
    h3_broken = WhyCausalHop(3, "GUARDRAIL_GAP", "Q3", "F3", "n1", "sha256:e3", "sha256:wrong-parent")
    with pytest.raises(ValueError, match="HALT_TOYOTA_5WHY_BROKEN_CAUSAL_PARENT_LINK"):
        Toyota5WhyCausalRootCauseEngine.verify_and_sign_5why_chain(
            "Broken link test", "tayota 5 why", (h1, h2, h3_broken, h4, h5), valid_py, priv
        )

    # Falsification 3: Weak Poka-Yoke gate (< 10000 bps mutation kill rate) rejected
    weak_py = PokaYokeMistakeProofGate(
        "PY-WEAK", "sha256:e5", "Weak check", "src/decide.py", 8000
    )
    with pytest.raises(ValueError, match="HALT_TOYOTA_5WHY_POKA_YOKE_MUTATION_KILL_BELOW_10000_BPS"):
        Toyota5WhyCausalRootCauseEngine.verify_and_sign_5why_chain(
            "Weak poka-yoke", "tayota 5 why", (h1, h2, h3, h4, h5), weak_py, priv
        )


def test_mutation_adequacy_boundary_oracles() -> None:
    import builtins
    import dataclasses
    from src.toyota_5why_semantic_rca_and_token_analytics import (
        GEMINI_4_ARGON_HIGH,
        run_self_test,
    )

    # 1. Pricing constant & SprintTokenComparisonReport frozenness + exact token fields + 70/30 hybrid weight
    assert GEMINI_4_ARGON_HIGH.output_per_1m_cents == 15 * 100
    rep = AntigravityArgonFlashTokenAnalyticsEngine.evaluate_20_task_sprint(6)
    assert rep.without_system_input_tokens == 873_529
    assert rep.with_system_output_tokens == 20 * 2400
    with pytest.raises(dataclasses.FrozenInstanceError):
        rep.tasks_evaluated = 99  # type: ignore

    orig_cost = AntigravityArgonFlashTokenAnalyticsEngine._compute_cost_cents
    costs = iter([443, 200, 73, 100])
    AntigravityArgonFlashTokenAnalyticsEngine._compute_cost_cents = staticmethod(lambda *a, **kw: next(costs))  # type: ignore[assignment]
    try:
        rep_w = AntigravityArgonFlashTokenAnalyticsEngine.evaluate_20_task_sprint(6)
        assert rep_w.hybrid_cascade_with_cost_cents == 130
    finally:
        AntigravityArgonFlashTokenAnalyticsEngine._compute_cost_cents = staticmethod(orig_cost)  # type: ignore[assignment]

    # 2. IndexedCorpusNode frozenness, _char_ngrams exact trigrams, and RRF arithmetic invariants
    n_a = IndexedCorpusNode("a", "a.py", "aa", "abc", ("callee_one",), "sha256:a")
    n_b = IndexedCorpusNode("b", "b.py", "bb", "abcdefghij", (), "sha256:b")
    with pytest.raises(dataclasses.FrozenInstanceError):
        n_a.node_id = "mod"  # type: ignore

    assert HybridSemanticAstSearchEngine._char_ngrams("abcd", 3) == {"abc", "bcd"}
    assert HybridSemanticAstSearchEngine._char_ngrams("ab", 3) == {"ab"}

    class _CheckedInt(int):
        def __add__(self, other: int) -> "_CheckedInt":
            return _CheckedInt(int(self) + int(other))

        def __radd__(self, other: int) -> "_CheckedInt":
            if other not in (0, 60):
                raise ValueError(f"Unexpected radd constant {other}")
            return _CheckedInt(int(other) + int(self))

        def __rfloordiv__(self, other: int) -> int:
            if other != 100_000:
                raise ValueError(f"Unexpected RRF numerator {other}")
            return int.__rfloordiv__(int(self), other)

    orig_max = builtins.max
    orig_sorted = builtins.sorted
    orig_enum = builtins.enumerate

    def _checked_max(*args: object, **kw: object) -> object:
        if len(args) == 2 and args[0] != 1:
            raise ValueError(f"Expected max(1, ...), got {args[0]}")
        return orig_max(*args, **kw)  # type: ignore[arg-type]

    def _checked_sorted(iterable, *a, **kw):  # type: ignore[no-untyped-def]
        lst = list(iterable)
        for item in lst:
            if isinstance(item, tuple) and len(item) == 2 and item[0] > 10000:
                raise ValueError(f"Basis points invariant violated: {item[0]}")
        return orig_sorted(lst, *a, **kw)

    def _checked_enum(iterable, start: int = 0):  # type: ignore[no-untyped-def]
        for i, val in orig_enum(iterable, start):
            yield _CheckedInt(i), val

    eng = HybridSemanticAstSearchEngine([n_a, n_b])
    builtins.max = _checked_max  # type: ignore[assignment]
    builtins.sorted = _checked_sorted  # type: ignore[assignment]
    builtins.enumerate = _checked_enum  # type: ignore[assignment]
    try:
        hits = eng.search_rrf("callee_one abcdefgh", top_k=2)
        assert hits[0][0].node_id == "a"
        assert eng.search_rrf("callee_one", top_k=2)[0][0].node_id == "a"
        assert eng.search_rrf("abc", top_k=2)[0][0].node_id == "a"
    finally:
        builtins.max = orig_max  # type: ignore[assignment]
        builtins.sorted = orig_sorted  # type: ignore[assignment]
        builtins.enumerate = orig_enum  # type: ignore[assignment]

    # 3. Decompose single-intent query (kills In -> NotIn on line 348) and run_self_test
    assert Toyota5WhyCausalRootCauseEngine.decompose_multi_vector_query("token") == (
        "INTENT_1_TOKEN_AND_COST_ANALYTICS_ARGON_VS_FLASH",
    )
    run_self_test()


def test_zero_banned_words_in_toyota_5why_files() -> None:
    banned = [
        "guaran" + "teed",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "unassail" + "able",
        "unhack" + "able",
        "immun" + "e",
        "proven " + "universally",
        "production-" + "ready",
        "bank-" + "grade",
    ]
    for fpath in (
        "src/toyota_5why_semantic_rca_and_token_analytics.py",
        "tests/test_toyota_5why_semantic_rca_and_token_analytics.py",
    ):
        text = Path(fpath).read_text(encoding="utf-8").lower()
        for word in banned:
            assert word not in text, f"Banned word '{word}' found in {fpath}"
