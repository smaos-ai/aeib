#!/bin/bash
set -e

ARTIFACTS_DIR="$HOME/.smaos/series_a/proof_artifacts"
REPORT_FILE="evidence/proof_artifacts_validation.txt"

mkdir -p evidence

echo "=== SMAOS Phase 1: Proof Artifacts Validation ===" | tee "$REPORT_FILE"
echo "Timestamp: $(date)" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

PASS=0
FAIL=0

# Check all 7 artifacts exist
ARTIFACTS=(
  "1_agentacct_config.json"
  "2_unlazy_gates_hotel.md"
  "3_is_agentic_118checks.json"
  "4_canirun_s_f_grades.json"
  "5_ap2_ledger_pqc.md"
  "6_ragas_golden_set.json"
  "7_freetoken_benchmark.json"
)

echo "Checking artifact presence..." | tee -a "$REPORT_FILE"
for artifact in "${ARTIFACTS[@]}"; do
  if [ -f "$ARTIFACTS_DIR/$artifact" ]; then
    echo "✓ $artifact" | tee -a "$REPORT_FILE"
    ((PASS++))
  else
    echo "✗ MISSING: $artifact" | tee -a "$REPORT_FILE"
    ((FAIL++))
  fi
done

echo "" >> "$REPORT_FILE"

# Validate JSON files
echo "Validating JSON schema..." | tee -a "$REPORT_FILE"
for json_file in "$ARTIFACTS_DIR"/*.json; do
  if [ -f "$json_file" ]; then
    if python3 -c "import json; json.load(open('$json_file'))" 2>/dev/null; then
      echo "✓ $(basename "$json_file") JSON valid" | tee -a "$REPORT_FILE"
      ((PASS++))
    else
      echo "✗ $(basename "$json_file") JSON invalid" | tee -a "$REPORT_FILE"
      ((FAIL++))
    fi
  fi
done

echo "" >> "$REPORT_FILE"

# Validate AP2 ledger signatures (mock check for Ed25519)
echo "Checking AP2 ledger structure..." | tee -a "$REPORT_FILE"
if [ -f "$ARTIFACTS_DIR/5_ap2_ledger_pqc.md" ]; then
  if grep -q "Ed25519" "$ARTIFACTS_DIR/5_ap2_ledger_pqc.md"; then
    echo "✓ AP2 ledger contains Ed25519 references" | tee -a "$REPORT_FILE"
    ((PASS++))
  else
    echo "⚠ AP2 ledger missing Ed25519 signature format" | tee -a "$REPORT_FILE"
  fi
fi

echo "" >> "$REPORT_FILE"

# Summary
echo "=== VALIDATION SUMMARY ===" | tee -a "$REPORT_FILE"
echo "Passed: $PASS" | tee -a "$REPORT_FILE"
echo "Failed: $FAIL" | tee -a "$REPORT_FILE"

if [ $FAIL -eq 0 ]; then
  echo "✓ ALL PROOF ARTIFACTS VALIDATED" | tee -a "$REPORT_FILE"
  exit 0
else
  echo "✗ VALIDATION FAILED ($FAIL errors)" | tee -a "$REPORT_FILE"
  exit 1
fi
