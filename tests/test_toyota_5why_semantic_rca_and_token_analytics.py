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
    assert report.tasks_evaluated == 20
    assert report.without_system_total_tokens == 1_033_529
    assert report.with_system_total_tokens == 223_831
    assert report.total_token_reduction_bps == 7834  # 78.34% total token reduction

    # Verify cost hierarchy: Hybrid Cascade < Argon 4 WITH < Argon 4 WITHOUT
    assert report.argon4_without_cost_cents == 443  # $4.43 per 20-task sprint without system
    assert report.argon4_with_cost_cents == 93      # $0.93 per 20-task sprint on Argon 4 with system (79.0% cost cut)
    assert report.flash38_without_cost_cents == 73  # $0.73 per 20-task sprint on Flash 3.8 without system
    assert report.flash38_with_cost_cents == 15     # $0.15 per 20-task sprint on Flash 3.8 with system
    assert report.hybrid_cascade_with_cost_cents == 38  # $0.38 per 20-task sprint on Hybrid System-1/2 (91.4% vs Argon naive!)
    assert report.super_prompt_prefix_savings_bps == 8333


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
