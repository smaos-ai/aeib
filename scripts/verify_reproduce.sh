#!/usr/bin/env bash
# Standalone Reproducibility Harness (Section 24 - Track 1)
# Executes all 4 AGENTS.md compliance gates, the Section 22-23 Mathematical & AI Provers,
# the Section 24 Proof-Carrying Contract (PC2) Lean 4 Airlock, and the 500-episode Chaos Benchmark.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[1/5] Running Zone 1 / Zone 2 Boundary Purity Gate..."
python3 compliance/check_zone_boundary.py

echo "[2/5] Running Zero-Mock & Cryptographic AST Purity Gates..."
python3 compliance/ast_purity.py .
python3 compliance/no_mock_enforcer.py

echo "[3/5] Executing Section 22-29 Math Provers, Lean 4 Exporter, CEGIS Gate, Urgent 2026 & Oct 2026 Signals, Java 21 Loom+FLCT/ZDD Bridge, & O(1) State Capsule..."
python3 -m src.sovereign_state_capsule_and_math_prover --self-test
python3 -m src.parallel_frontier_math_and_ai_prover --self-test
python3 -m src.proof_carrying_lean4_airlock --self-test
python3 -m src.vendor_independent_prepush_cegis_gate --self-test
python3 -m src.urgent_open_problems_and_frontier_experiment_engine --self-test
python3 tools/parallel_open_frontier_and_urgent_solver.py
python3 -m src.oct2026_frontier_signals_and_agent_s4_airlock --self-test
python3 -m src.java21_loom_flct_zdd_bridge_engine --self-test

echo "[4/5] Running Pytest Verification Suites..."
pytest tests/test_industrial_protection_matrix.py \
       tests/test_ansi_50bf_breaker_failure.py \
       tests/test_saga_compensation.py \
       tests/test_falsifiability_matrix.py \
       tests/test_toyota_5why_semantic_rca_and_token_analytics.py \
       tests/test_sovereign_state_capsule_and_math_prover.py \
       tests/test_parallel_frontier_math_and_ai_prover.py \
       tests/test_proof_carrying_lean4_airlock.py \
       tests/test_vendor_independent_prepush_cegis_gate.py \
       tests/test_urgent_open_problems_and_frontier_experiment_engine.py \
       tools/parallel_open_frontier_and_urgent_solver.py \
       tests/test_oct2026_frontier_signals_and_agent_s4_airlock.py \
       tests/test_java21_loom_flct_zdd_bridge_engine.py -v

echo "[5/5] Running Deterministic 500-Episode Execution Integrity Benchmark (seed=42)..."
python3 benchmarks/aeib_execution_integrity/run_episodes.py --episodes 500 --seed 42

echo "[OK] All Reproducibility & Verification Gates Passed."
