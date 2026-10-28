"""Verification suite for Sovereign Independent State Proxy, Choice-Chain Catalog, & Frontier Math Solver."""

from __future__ import annotations

import copy

from src.sovereign_independent_state_and_math_frontier import (
    AlphaEvolvePatternBoostMathSolver,
    DecideScopeChainCatalog,
    SovereignIndependentStateProxy,
)


def test_frontier_math_cap_set_f3_4_extremal_and_falsification() -> None:
    """Verifies discovery of a maximal 20-point Cap Set in F_3^4 and falsification on collinear points."""
    report = AlphaEvolvePatternBoostMathSolver.solve_extremal_cap_set_f3_4()
    assert report.naive_baseline_score == 16
    assert report.greedy_baseline_score == 16
    assert int(report.discovered_extremal_score) == 20
    assert report.improvement_vs_greedy_bps == 2500
    assert report.zero_violations_verified is True
    assert report.constraints_checked_count == 190  # C(20, 2) = 190 pairs

    # Falsification: inject a collinear triple (0,0,0,0), (1,1,1,1), (2,2,2,2)
    bad_cap = [(0, 0, 0, 0), (1, 1, 1, 1), (2, 2, 2, 2)]
    ok, _, msg = AlphaEvolvePatternBoostMathSolver.verify_cap_set(bad_cap, 4)
    assert ok is False
    assert "Collinear triple detected" in msg


def test_frontier_math_sidon_golomb_k8_extremal_and_falsification() -> None:
    """Verifies discovery of the optimal 8-mark Sidon/Golomb Ruler (span 34) vs Mian-Chowla greedy (44)."""
    report = AlphaEvolvePatternBoostMathSolver.solve_optimal_sidon_golomb_k8()
    assert report.naive_baseline_score == 127
    assert report.greedy_baseline_score == 44
    assert int(report.discovered_extremal_score) == 34
    assert report.improvement_vs_greedy_bps == 2273
    assert report.witness_construction == [0, 1, 4, 9, 15, 22, 32, 34]
    assert report.zero_violations_verified is True
    assert report.constraints_checked_count == 28  # C(8, 2) = 28 unique differences

    # Falsification: ruler with duplicate difference (1 - 0 == 2 - 1 == 1)
    ok, _, msg = AlphaEvolvePatternBoostMathSolver.verify_sidon_golomb_ruler([0, 1, 2, 6])
    assert ok is False
    assert "Duplicate difference" in msg


def test_frontier_math_no_three_in_line_10x10_and_falsification() -> None:
    """Verifies discovery of a 20-point No-Three-In-Line witness on the 10x10 grid across all slopes."""
    report = AlphaEvolvePatternBoostMathSolver.solve_no_three_in_line_10x10()
    assert report.naive_baseline_score == 10
    assert report.greedy_baseline_score == 13
    assert int(report.discovered_extremal_score) == 20
    assert report.improvement_vs_greedy_bps == 5385
    assert report.zero_violations_verified is True
    assert report.constraints_checked_count == 1140  # C(20, 3) = 1140 triples

    # Falsification: 3 points on slope 1/2: (0,0), (1,2), (2,4)
    ok, _, msg = AlphaEvolvePatternBoostMathSolver.verify_no_three_in_line_grid(
        [(0, 0), (1, 2), (2, 4)], 10
    )
    assert ok is False
    assert "Collinear Euclidean triple" in msg


def test_independent_state_proxy_and_choice_chain_routing() -> None:
    """Verifies independent state bundle JCS + Ed25519 signing, tamper rejection, and query wrapping."""
    proxy = SovereignIndependentStateProxy()
    bundle = proxy.build_independent_state_bundle()
    assert SovereignIndependentStateProxy.verify_independent_state_bundle(bundle) is True

    # Tamper test: modify a telemetry field and verify signature check fails closed
    tampered = copy.deepcopy(bundle)
    tampered["state_core"]["verified_telemetry_summary"]["token_reduction_bps"] = 9999
    assert SovereignIndependentStateProxy.verify_independent_state_bundle(tampered) is False

    # Choice-chain routing test
    wrapped_math = proxy.wrap_user_query_with_state_proxy(
        "/decide --chain math-frontier solve erdos sidon"
    )
    assert wrapped_math["selected_chain_id"] == "CHAIN-5"
    assert "--falsify" in wrapped_math["auto_injected_flags"]

    wrapped_finops = proxy.wrap_user_query_with_state_proxy("check argon token cost")
    assert wrapped_finops["selected_chain_id"] == "CHAIN-2"

    all_chains = DecideScopeChainCatalog.list_all_chains()
    assert len(all_chains) == 6
