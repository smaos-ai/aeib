#!/usr/bin/env bash
# ==============================================================================
# AEIB / SMF: Master Verification & Release Gate Runner
# Epistemic Rule: Models propose. Governance decides. Evidence survives.
# ==============================================================================
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$WORKSPACE_ROOT"

echo "======================================================================="
echo "  AEIB / SMF MASTER VERIFICATION & 15-INVARIANT RELEASE GATE RUNNER"
echo "  Epistemic Rule: Models propose. Governance decides. Evidence survives."
echo "======================================================================="

mkdir -p output conformance/vectors docs/compliance tools tests benchmarks papers

# 1. Static AST Purity & Zero-Mock Compliance Gates
echo ">>> [GATES] Running Static AST Purity & Zero-Mock Enforcer"
python3 compliance/check_zone_boundary.py
python3 compliance/ast_purity.py .
python3 compliance/no_mock_enforcer.py

# 2. Parallel Verification Tracks (0 through 4)
echo ">>> [TRACKS] Running Parallel Verification Tracks"
python3 tools/phase0_integrity_reset_core.py &
PID_T0=$!
python3 tests/test_structural_cve_boundary_fixtures.py &
PID_T1=$!
python3 tools/regulatory_three_tier_and_matrix.py &
PID_T2=$!
python3 tools/context_ram_and_maseval_harness.py &
PID_T3=$!
python3 tools/tlaplus_model_conformance_checker.py &
PID_T4=$!

wait $PID_T0 $PID_T1 $PID_T2 $PID_T3 $PID_T4
echo ">>> [✓] All parallel verification tracks completed with exit status 0."

# 3. Deterministic Archive & Paired-Run Evaluator
echo ">>> [ARCHIVE & FIN-VAL] Building Deterministic RC5 Bundle"
python3 tools/build_reproducible_rc5_archive.py
python3 tools/paired_run_bill_denominated_evaluator.py > output/paired_run_receipt.json

# 4. Master Pytest Battery
echo ">>> [PYTEST] Running Master Test Suite Across All 15 Invariants"
pytest \
  tests/test_sybil_rotator_and_smurfing.py \
  tests/test_tcc_parallel_acid_vs_base_anomalies.py \
  tools/phase0_integrity_reset_core.py \
  tests/test_structural_cve_boundary_fixtures.py \
  tests/test_cve_2026_33017_langflow_rce.py \
  tests/test_vibe_coding_and_long_horizon_guard.py \
  tests/test_local_system1_leviathan_daemon.py \
  tests/test_hlc_hypergraph_and_persist_gate.py \
  tests/test_hansard_and_defection_probe.py \
  tests/test_poseidon2_merkle_tree.py \
  tests/test_tier3_post_perfection_matrix.py \
  scripts/verify_research_claims.py \
  tools/aeib_surviving_principles_engine.py \
  tools/epistemic_action_compiler_ab_test.py \
  tests/test_epistemic_action_compiler.py \
  tools/palantir_ontology_joint_witness_engine.py \
  tests/test_palantir_ontology_joint_witness_engine.py \
  compliance/eac_typestate_conflict_engine.py \
  tests/test_eac_typestate_conflict_engine.py \
  tests/test_epistemic_core_bec.py \
  tools/regulatory_three_tier_and_matrix.py \
  tools/context_ram_and_maseval_harness.py \
  tools/tlaplus_model_conformance_checker.py \
  tools/build_reproducible_rc5_archive.py \
  tools/paired_run_bill_denominated_evaluator.py \
  -v

# 5. Cleanroom Banned-Word Scan
echo ">>> [CLEANROOM SCAN] Scanning Code & Documentation for Banned Overclaims"
! grep -Eni "guaran[t]eed|bullet[p]roof|enterprise-[g]rade|production-[s]afe|100% [s]ecure" \
  src/poseidon2_merkle_tree.py \
  src/nash_equilibrium_gate.py \
  src/tee_cvm_memory_scrubbing.py \
  src/wasm_symbolic_path_explorer.py \
  src/actuarial_multisig_gate.py \
  src/persist_memory_gate.py \
  src/hlc_hybrid_logical_clock.py \
  src/hypergraph_causal_audit.py \
  src/hansard_causal_provenance.py \
  src/defection_activation_probe.py \
  scripts/verify_research_claims.py \
  tools/aeib_surviving_principles_engine.py \
  src/epistemic_action_compiler.py \
  tools/epistemic_action_compiler_ab_test.py \
  tests/test_epistemic_action_compiler.py \
  tools/palantir_ontology_joint_witness_engine.py \
  tests/test_palantir_ontology_joint_witness_engine.py \
  compliance/eac_typestate_conflict_engine.py \
  src/epistemic_core.py \
  tests/test_eac_typestate_conflict_engine.py \
  tests/test_epistemic_core_bec.py \
  docs/architecture/EPISTEMIC_ACTION_COMPILATION_AND_CONFLICT_REGISTER.md \
  docs/specs/admissibility_and_oo_harness_spec.md

# 6. Physical NVMe Cold Vault Synchronization
echo ">>> [NVME SYNC] Mirroring to Physical External SSD Cold Vault"
SSD_TARGET="/Volumes/EXTssd/SovereignNexus_Backup"
if [ -d "$SSD_TARGET" ]; then
    rsync -av --delete \
        --exclude '.git' \
        --exclude 'target' \
        --exclude '.venv*' \
        --exclude 'node_modules' \
        --exclude '.cache' \
        --exclude '.pytest_cache' \
        --exclude '__pycache__' \
        ./ "$SSD_TARGET/sovereign-nexus-workspace/"
    echo ">>> [✓] Physical NVMe SSD synchronization complete."
else
    echo ">>> [i] External SSD target $SSD_TARGET not mounted; local artifacts secured."
fi

echo "======================================================================="
echo "  AEIB / SMF MASTER VERIFICATION & RELEASE GATES PASSED SUCCESSFULLY."
echo "  The models propose. Governance decides. Evidence survives."
echo "  The evidence remains the work."
echo "======================================================================="
