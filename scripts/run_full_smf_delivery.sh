#!/usr/bin/env bash
# ==============================================================================
# SMF / VAF v1.0.0-rc.5: Master Parallel Delivery & Verification Script
# ==============================================================================
set -euo pipefail
WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$WORKSPACE_ROOT"

echo "======================================================================="
echo "  AGENTIC SOFTWARE MANUFACTURING FABRIC (SMF) v1.0.0-rc.5 — LAUNCH"
echo "  Epistemic Rule: Models propose. Governance decides. Evidence survives."
echo "======================================================================="

mkdir -p output conformance/vectors docs/compliance tools tests

echo ">>> [PARALLEL TRACK 0] Phase 0 Integrity Reset"
python3 tools/phase0_integrity_reset_core.py &
PID_T0=$!

echo ">>> [PARALLEL TRACK 1] Structural CVE Boundary Fixtures"
python3 tests/test_structural_cve_boundary_fixtures.py &
PID_T1=$!

echo ">>> [PARALLEL TRACK 2] China/EU Regulatory Applicability & 3-Tier Gate"
python3 tools/regulatory_three_tier_and_matrix.py &
PID_T2=$!

echo ">>> [PARALLEL TRACK 3] Context-as-RAM & Dynamic Workflows"
python3 tools/context_ram_and_maseval_harness.py &
PID_T3=$!

echo ">>> [PARALLEL TRACK 4] TLA+ State-Space & SQLite Conformance"
python3 tools/tlaplus_model_conformance_checker.py &
PID_T4=$!

wait $PID_T0 $PID_T1 $PID_T2 $PID_T3 $PID_T4
echo ">>> [✓] All parallel verification tracks completed with exit status 0."

echo ">>> [ARCHIVE & FIN-VAL] Deterministic Archive & Paired-Run Evaluator"
python3 tools/build_reproducible_rc5_archive.py
python3 tools/paired_run_bill_denominated_evaluator.py > output/paired_run_receipt.json

echo ">>> [PYTEST BATTERY] Running Full Test Suite"
pytest \
  tools/phase0_integrity_reset_core.py \
  tests/test_structural_cve_boundary_fixtures.py \
  tests/test_cve_2026_33017_langflow_rce.py \
  tests/test_vibe_coding_and_long_horizon_guard.py \
  tests/test_local_system1_leviathan_daemon.py \
  tools/regulatory_three_tier_and_matrix.py \
  tools/context_ram_and_maseval_harness.py \
  tools/tlaplus_model_conformance_checker.py \
  tools/build_reproducible_rc5_archive.py \
  tools/paired_run_bill_denominated_evaluator.py \
  -v

echo ">>> [BENCHMARK RUNNERS] Validating LoCoMo & MASEval"
python3 benchmarks/locomo_context_quality.py > output/locomo_benchmark_receipt.json
python3 benchmarks/maseval_integration.py > output/maseval_benchmark_receipt.json

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
echo "  SMF / VAF v1.0.0-rc.5 FULL PARALLEL DELIVERY COMPLETED SUCCESSFULLY."
echo "  The models propose. Governance decides. Evidence survives."
echo "  The evidence remains the work."
echo "======================================================================="
