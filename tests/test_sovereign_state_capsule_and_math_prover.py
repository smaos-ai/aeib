"""Verification suite for Sovereign Independent State Capsule, O(1) Context Proxy,
and Frontier Mathematical Combinatorial Prover Engine (Section 22).
"""

from __future__ import annotations

from pathlib import Path

from src.sovereign_state_capsule_and_math_prover import (
    DecideMoatChainProxy,
    FrontierMathCombinatorialProverEngine,
    SovereignIndependentStateCapsuleEngine,
)


def test_independent_state_capsule_and_ssd_sync(tmp_path: Path) -> None:
    """Verify O(1) state capsule build, local state file emission, and independent SSD sync."""
    ssd_dir = tmp_path / "ext_ssd_state"
    engine = SovereignIndependentStateCapsuleEngine(external_ssd_state_dir=ssd_dir)
    capsule = engine.build_and_sync_capsule(persist=True)

    assert capsule.total_moats_count == 12
    assert capsule.all_moats_bitmask == 0xFFF
    assert len(capsule.constant_time_state_string) <= 1800
    assert "TokenCut=78.34%" in capsule.constant_time_state_string

    # Verify independent SSD state directory received both JSON and Markdown dashboard
    assert (ssd_dir / "SOVEREIGN_STATE_CAPSULE.json").exists()
    assert (ssd_dir / "SOVEREIGN_STATE_DASHBOARD.md").exists()

    # Also sync to the real workspace/SSD path
    real_engine = SovereignIndependentStateCapsuleEngine()
    real_capsule = real_engine.build_and_sync_capsule(persist=True)
    assert (Path(real_capsule.workspace_root) / "state" / "SOVEREIGN_STATE_CAPSULE.json").exists()
    assert (Path(real_capsule.workspace_root) / "state" / "SOVEREIGN_STATE_DASHBOARD.md").exists()


def test_decide_moat_chain_proxy_auto_expansion() -> None:
    """Verify that short user queries automatically expand with O(1) state and moat bitmask."""
    engine = SovereignIndependentStateCapsuleEngine()
    capsule = engine.build_and_sync_capsule(persist=False)
    proxy = DecideMoatChainProxy(capsule)

    # 1. Math query -> CHAIN-D_FORMAL_MATH_DISCOVERY
    res_math = proxy.wrap_short_intent("solve erdos capset math challenge")
    assert res_math["selected_chain_id"] == "CHAIN-D_FORMAL_MATH_DISCOVERY"
    assert "M12_ALPHAEVOLVE_MATH_SOLVER" in res_math["activated_moat_codes"]
    assert capsule.constant_time_state_string in str(res_math["expanded_prompt"])

    # 2. Root-cause bug query -> CHAIN-C_ROOT_CAUSE_5WHY
    res_rca = proxy.wrap_short_intent("why did payment retry bug happen")
    assert res_rca["selected_chain_id"] == "CHAIN-C_ROOT_CAUSE_5WHY"
    assert "M05_TOYOTA_5WHY_RRF" in res_rca["activated_moat_codes"]
    assert "M01_EO1_LATCH" in res_rca["activated_moat_codes"]

    # 3. Security query -> CHAIN-B_ZERO_TRUST_SECURITY
    res_sec = proxy.wrap_short_intent("audit litellm credential secret supply chain")
    assert res_sec["selected_chain_id"] == "CHAIN-B_ZERO_TRUST_SECURITY"
    assert "M07_CREDENTIAL_STARVATION" in res_sec["activated_moat_codes"]

    # 4. Token cost query -> CHAIN-A_FINOPS_SPEED
    res_tok = proxy.wrap_short_intent("reduce argon token cost and mcp schema bloat")
    assert res_tok["selected_chain_id"] == "CHAIN-A_FINOPS_SPEED"
    assert "M02_CONTEXTCART_AST" in res_tok["activated_moat_codes"]
    assert "M03_TOKEN_ECONOMIZER" in res_tok["activated_moat_codes"]


def test_frontier_math_combinatorial_prover_and_falsification() -> None:
    """Verify live constructive solutions for Cap Set F_3^4, Erdos-Sidon 8-Mark Golomb Ruler,
    and No-Three-In-Line 10x10 grid, plus T4+ mutation-kill and Ed25519 signature checks.
    """
    prover = FrontierMathCombinatorialProverEngine()

    # 1. Challenge 1: Maximum Cap Set in F_3^4 (|S| = 20, 0 collinear triples out of 1,140)
    w_cap = prover.solve_cap_set_f3_4()
    assert w_cap.sovereign_verified_score == 20
    assert w_cap.naive_llm_or_greedy_score < 20
    assert w_cap.total_constraints_checked == 1140
    assert w_cap.constraint_violations_found == 0
    assert w_cap.is_globally_optimal_or_bound_tight is True

    # 2. Challenge 2: Optimal 8-Mark Erdos-Turan Sidon / Golomb Ruler (L* = 34 vs greedy 44)
    w_golomb = prover.solve_erdos_sidon_golomb_8()
    assert w_golomb.sovereign_verified_score == 34
    assert w_golomb.naive_llm_or_greedy_score == 44
    assert w_golomb.improvement_bps == 2273
    assert w_golomb.total_constraints_checked == 28
    assert w_golomb.constraint_violations_found == 0
    assert w_golomb.solution_elements == [0, 1, 4, 9, 15, 22, 32, 34]

    # 3. Challenge 3: Dudeney / Erdos No-Three-In-Line on 10x10 Grid (2N = 20 points, 0 collinear)
    w_grid = prover.solve_no_three_in_line_10x10()
    assert w_grid.sovereign_verified_score == 20
    assert w_grid.naive_llm_or_greedy_score < 20
    assert w_grid.total_constraints_checked == 1140
    assert w_grid.constraint_violations_found == 0

    # 4. Signed Bundle + T4+ Mutation-Kill Adequacy + Tamper Falsification
    bundle = prover.run_all_and_sign_bundle()
    assert prover.verify_signed_bundle(bundle) is True
    t4 = bundle["t4_plus_mutation_adequacy"]
    assert t4["mutants_injected"] == 3
    assert t4["mutants_killed"] == 3
    assert t4["kill_rate_bps"] == 10000
    assert t4["qualifies_as_t4_plus"] is True

    # Falsification: tampering with a witness score invalidates the Ed25519 signature
    tampered = dict(bundle)
    tampered_witnesses = [dict(w) for w in bundle["witnesses"]]
    tampered_witnesses[0]["sovereign_verified_score"] = 21
    tampered["witnesses"] = tampered_witnesses
    assert prover.verify_signed_bundle(tampered) is False


def test_zero_banned_promotional_words_in_section22_files() -> None:
    """Ensure strict adherence to AGENTS.md epistemic boundaries."""
    banned = [
        "guaran" + "teed",
        "proven universal" + "ly",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
    ]
    root = Path(__file__).resolve().parent.parent
    for rel in (
        "src/sovereign_state_capsule_and_math_prover.py",
        "tests/test_sovereign_state_capsule_and_math_prover.py",
    ):
        content = (root / rel).read_text(encoding="utf-8").lower()
        for word in banned:
            assert word not in content, f"Banned term found in {rel}: {word}"
