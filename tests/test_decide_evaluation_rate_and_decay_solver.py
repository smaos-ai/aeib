#!/usr/bin/env python3
# File: tests/test_decide_evaluation_rate_and_decay_solver.py
"""
Test suite for Decide-v4.5 Evaluation Rate Optimizer & Four-Decay Mathematical Solver.
Evaluates:
1. Knowledge Integration Decay (KID) vs SAKE dual-boundary anchoring (arXiv:2602.09517).
2. Data Processing Inequality (DPI) handoff gate (arXiv:2604.02460).
3. Step-Level IG-Search + CELF Evaluation Rate scheduler (arXiv:2604.15148).
4. Multi-Hop Pass^k compounding decay and Hawkes recency re-anchoring.
5. Ed25519 signature verification over RFC 8785 JCS canonical payload.
6. Epistemic boundary compliance (zero banned promotional words).
"""

import base64
import subprocess
import sys
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from src.decide_evaluation_rate_and_decay_solver import (
    DataProcessingInequalityGate,
    DecideV45AntiDecayEngine,
    KnowledgeIntegrationDecaySolver,
    MultiHopPassKAndHawkesCompensator,
    StepLevelIGSearchAndCelfScheduler,
    canonical_jcs,
    sha256_hex,
)


def test_knowledge_integration_decay_and_sake_dual_anchoring():
    """
    Evaluates arXiv:2602.09517 Knowledge Integration Decay (KID):
    As pre-search reasoning context grows (e.g. 12,000 tokens), naive middle-context
    utilization decays sharply, whereas SAKE dual-boundary anchoring (genesis + terminal)
    preserves >= 9800 bps utilization.
    """
    solver = KnowledgeIntegrationDecaySolver()
    rec = solver.anchor_evidence_sake(
        evidence_id="ev_hop4_dvp",
        hop_depth=4,
        accumulated_context_tokens=12000,
        fact_payload={"module": "planetary_clearinghouse", "eas_floor_bps": 8000},
    )

    assert rec.genesis_pinned is True
    assert rec.terminal_pinned is True
    assert len(rec.fact_sha256) == 64
    # At 12k tokens with lambda=0.18/kTok, naive utilization drops below 1500 bps
    assert rec.naive_utilization_bps < 1500
    # SAKE dual-boundary pinning keeps utilization above 9800 bps
    assert rec.sake_utilization_bps >= 9800
    assert rec.sake_utilization_bps > rec.naive_utilization_bps * 6


def test_data_processing_inequality_handoff_gate():
    """
    Evaluates arXiv:2604.02460 (Tran & Kiela, Stanford) DPI Handoff Gate:
    1. Lossy prose handoffs fail closed with HALT_DPI_LOSSY_PROSE_HANDOFF.
    2. Zero external entropy handoffs fail closed with HALT_DPI_ZERO_EXTERNAL_ENTROPY.
    3. Lossless vault pointer + positive external ground-truth entropy succeeds.
    """
    gate = DataProcessingInequalityGate(min_external_entropy_bps=150)

    lossy = gate.evaluate_handoff(
        handoff_id="h_01",
        source_agent="agent_1",
        target_agent="agent_2",
        prior_mutual_info_bps=8000,
        external_entropy_injected_bps=600,
        uses_lossless_vault_pointer=False,
    )
    assert lossy.disposition == "HALT_DPI_LOSSY_PROSE_HANDOFF"
    assert lossy.post_handoff_mutual_info_bps < lossy.prior_mutual_info_bps

    zero_ent = gate.evaluate_handoff(
        handoff_id="h_02",
        source_agent="agent_1",
        target_agent="agent_2",
        prior_mutual_info_bps=8000,
        external_entropy_injected_bps=50,
        uses_lossless_vault_pointer=True,
    )
    assert zero_ent.disposition == "HALT_DPI_ZERO_EXTERNAL_ENTROPY"

    valid = gate.evaluate_handoff(
        handoff_id="h_03",
        source_agent="qwen_3_max",
        target_agent="deepseek_v4_pro",
        prior_mutual_info_bps=8000,
        external_entropy_injected_bps=1200,
        uses_lossless_vault_pointer=True,
    )
    assert valid.disposition == "AUTHORIZED_ENTROPY_GAIN"
    assert valid.post_handoff_mutual_info_bps == 9200


def test_step_level_ig_search_and_celf_evaluation_rate_pruning():
    """
    Evaluates arXiv:2604.15148 IG-Search + CELF submodular scheduling:
    High-rate orthogonal actions execute first; redundant deep-hop queries
    with diminishing marginal IG are pruned automatically.
    """
    engine = DecideV45AntiDecayEngine()
    candidates = engine.build_standard_candidate_pool()
    executed, pruned = engine.scheduler.schedule_celf_optimal_sequence(
        candidates, token_budget=4000
    )

    assert len(executed) == 6
    assert len(pruned) == 4
    assert executed[-1].cumulative_coverage_bps == 10000
    assert executed[-1].cumulative_tokens <= 3000

    for p in pruned:
        assert p.status == "PRUNED_DIMINISHING_RETURNS"


def test_multi_hop_pass_k_compounding_and_hawkes_compensation():
    """
    Evaluates H=5 hop, k=8 trial Pass^8 compounding decay:
    Unverified 90% per-hop accuracy collapses to ~147 bps (1.47%), while
    step-level 3-way deterministic verification restores Pass^8 above 9200 bps.
    """
    comp = MultiHopPassKAndHawkesCompensator()
    res = comp.evaluate_multi_hop_pass_k(
        hop_count=5,
        k_trials=8,
        single_hop_accuracy_bps=9000,
        verifier_ensemble_size=3,
        staleness_hours=48,
    )

    assert res.unverified_pass_k_bps < 200
    assert res.step_verified_pass_k_bps > 9000
    assert res.hawkes_reanchored_intensity_bps > res.hawkes_stale_intensity_bps


def test_unified_engine_ed25519_receipt_and_cli_self_test():
    """Evaluates end-to-end DecideV45AntiDecayEngine receipt signing and CLI."""
    engine = DecideV45AntiDecayEngine()
    report = engine.evaluate_complete_anti_decay_cycle()

    assert report.coverage_achieved_bps == 10000
    assert report.token_reduction_bps >= 6000
    assert report.eval_rate_multiplier_bps >= 20000
    assert report.dpi_lossy_handoffs_blocked == 1
    assert report.dpi_zero_entropy_handoffs_blocked == 1

    # Reconstruct JCS payload and verify Ed25519 signature
    payload_obj = {
        "report_id": report.report_id,
        "naive_uniform_tokens": report.naive_uniform_tokens,
        "celf_scheduled_tokens": report.celf_scheduled_tokens,
        "token_reduction_bps": report.token_reduction_bps,
        "naive_eval_rate_score": report.naive_eval_rate_score,
        "celf_sake_eval_rate_score": report.celf_sake_eval_rate_score,
        "eval_rate_multiplier_bps": report.eval_rate_multiplier_bps,
        "naive_deep_hop_utilization_bps": report.naive_deep_hop_utilization_bps,
        "sake_deep_hop_utilization_bps": report.sake_deep_hop_utilization_bps,
        "unverified_pass8_5hop_bps": report.unverified_pass8_5hop_bps,
        "step_verified_pass8_5hop_bps": report.step_verified_pass8_5hop_bps,
        "dpi_lossy_handoffs_blocked": report.dpi_lossy_handoffs_blocked,
        "dpi_zero_entropy_handoffs_blocked": report.dpi_zero_entropy_handoffs_blocked,
        "executed_steps_count": report.executed_steps_count,
        "pruned_low_gain_steps_count": report.pruned_low_gain_steps_count,
        "coverage_achieved_bps": report.coverage_achieved_bps,
    }
    jcs_bytes = canonical_jcs(payload_obj)
    assert sha256_hex(jcs_bytes) == report.payload_sha256

    pub_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(report.public_key_b64))
    sig_bytes = base64.b64decode(report.signature_b64)
    pub_key.verify(sig_bytes, jcs_bytes)

    # Tamper check must fail
    with pytest.raises(Exception):
        pub_key.verify(sig_bytes, jcs_bytes + b"tamper")

    # CLI --self-test check
    proc = subprocess.run(
        [sys.executable, "src/decide_evaluation_rate_and_decay_solver.py", "--self-test"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "SELF_TEST_PASSED" in proc.stdout


def test_banned_words_absence():
    """Enforces AGENTS.md epistemic boundary on source and test files."""
    banned = [
        "guaran" + "teed",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "unassail" + "able",
        "unhack" + "able",
        "proven " + "universally",
    ]
    for fpath in (
        "src/decide_evaluation_rate_and_decay_solver.py",
        "tests/test_decide_evaluation_rate_and_decay_solver.py",
    ):
        with open(fpath, "r", encoding="utf-8") as f:
            txt = f.read().lower()
            for word in banned:
                assert word not in txt, f"Banned term '{word}' found in {fpath}"


def test_decide_evaluation_rate_and_decay_solver_mutation_boundaries() -> None:
    from src.decide_evaluation_rate_and_decay_solver import CandidateQueryAction

    gate_default = DataProcessingInequalityGate()
    assert gate_default.prose_channel_loss_bps == 18 * 100
    assert gate_default.min_external_entropy_bps == 15 * 10

    z_rec = gate_default.evaluate_handoff(
        handoff_id="h_z",
        source_agent="a1",
        target_agent="a2",
        prior_mutual_info_bps=7000,
        external_entropy_injected_bps=0,
        uses_lossless_vault_pointer=True,
    )
    assert z_rec.uses_lossless_vault_pointer is True
    assert z_rec.disposition == "HALT_DPI_ZERO_EXTERNAL_ENTROPY"

    comp = MultiHopPassKAndHawkesCompensator()
    res_def = comp.evaluate_multi_hop_pass_k()
    assert res_def.unverified_pass_k_bps == 148
    assert res_def.step_verified_pass_k_bps == 9230
    assert res_def.hawkes_stale_intensity_bps == 2369
    assert res_def.hawkes_reanchored_intensity_bps == 9695
    assert comp.evaluate_multi_hop_pass_k(single_hop_accuracy_bps=7000).step_verified_pass_k_bps == 3346

    engine = DecideV45AntiDecayEngine()
    c_empty = CandidateQueryAction("c_0", "X", 0, "q", (), 5000, False, 100, 10)
    assert engine.scheduler.compute_marginal_ig_bps(c_empty, set()) == 0

    c_overlap = CandidateQueryAction("c_ov", "X", 0, "q", ("t1", "t2"), 10000, False, 100, 10)
    assert engine.scheduler.compute_marginal_ig_bps(c_overlap, {"t2"}) == 5400

    c_rate = CandidateQueryAction("c_r", "X", 0, "q", ("t1",), 10000, False, 10, 10)
    rate_score, mig_bps, util_bps = engine.scheduler.compute_evaluation_rate(
        c_rate, set(), 0, use_sake=False
    )
    assert (rate_score, mig_bps, util_bps) == (9900000, 10000, 9900)

    c_fast = CandidateQueryAction("c_fast", "X", 0, "q1", ("t1",), 5000, False, 10, 10)
    c_slow = CandidateQueryAction("c_slow", "X", 0, "q2", ("t2",), 9000, False, 1000, 100)
    exec_order, _ = engine.scheduler.schedule_celf_optimal_sequence([c_slow, c_fast], token_budget=6000)
    assert [s.action_id for s in exec_order] == ["c_fast", "c_slow"]

    pool = engine.build_standard_candidate_pool()
    assert [c.hop_depth for c in pool] == [0, 0, 1, 1, 1, 1, 2, 2, 3, 3]
    assert [c.base_ig_bps for c in pool] == [9400, 9800, 9500, 9600, 9100, 8900, 3200, 2800, 2100, 1900]

    recorded_handoff_entropy: list[int] = []
    orig_handoff = engine.dpi_gate.evaluate_handoff

    def _spy_handoff(
        handoff_id: str,
        source_agent: str,
        target_agent: str,
        prior_mutual_info_bps: int,
        external_entropy_injected_bps: int,
        uses_lossless_vault_pointer: bool,
    ) -> object:
        recorded_handoff_entropy.append(external_entropy_injected_bps)
        return orig_handoff(
            handoff_id=handoff_id,
            source_agent=source_agent,
            target_agent=target_agent,
            prior_mutual_info_bps=prior_mutual_info_bps,
            external_entropy_injected_bps=external_entropy_injected_bps,
            uses_lossless_vault_pointer=uses_lossless_vault_pointer,
        )

    engine.dpi_gate.evaluate_handoff = _spy_handoff  # type: ignore[method-assign]
    rep = engine.evaluate_complete_anti_decay_cycle()
    assert recorded_handoff_entropy == [500, 0, 1800]
    assert rep.naive_uniform_tokens == 8250
    assert rep.celf_scheduled_tokens == 28 * 100
    assert rep.token_reduction_bps == 6606
    assert rep.naive_eval_rate_score == 5036
    assert rep.celf_sake_eval_rate_score == 180194
    assert rep.eval_rate_multiplier_bps == (rep.celf_sake_eval_rate_score * 10000) // rep.naive_eval_rate_score

    # Custom 1-candidate micro-cycle to test exact naive_total_effective_ig=0 and max(1, naive_eval_rate)
    eng_micro = DecideV45AntiDecayEngine()
    eng_micro.build_standard_candidate_pool = lambda: [  # type: ignore[method-assign]
        CandidateQueryAction("m1", "X", 0, "q", ("foundational_latch",), 5000, False, 1, 1)
    ]
    rep_micro = eng_micro.evaluate_complete_anti_decay_cycle()
    assert rep_micro.naive_eval_rate_score == 4949000

    eng_zero_naive = DecideV45AntiDecayEngine()
    eng_zero_naive.build_standard_candidate_pool = lambda: [  # type: ignore[method-assign]
        CandidateQueryAction("m2", "X", 0, "q", ("foundational_latch",), 5000, False, 1, 1)
    ]
    eng_zero_naive.kid_solver.compute_naive_utilization_bps = lambda _tok: 0  # type: ignore[method-assign]
    rep_zero = eng_zero_naive.evaluate_complete_anti_decay_cycle()
    assert rep_zero.naive_eval_rate_score == 0
    assert rep_zero.eval_rate_multiplier_bps == rep_zero.celf_sake_eval_rate_score * 10000
