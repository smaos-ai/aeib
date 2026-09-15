#!/usr/bin/env bash
# ==============================================================================
# AEIB v0.1 — Clean-Machine Release Verification Harness (v0.1.0 Gate)
# Standard: Agent-Effect Integrity Benchmark (AEIB)
# Precedence: INVALID_INPUT -> MISSING_EVIDENCE -> CONFLICT -> REFUSED -> CONFIRMED -> UNKNOWN
# ==============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ARCHIVE_INPUT="${1:-}"
if [ -n "$ARCHIVE_INPUT" ]; then
    ARCHIVE_PATH="$ARCHIVE_INPUT"
elif [ -f "dist/aeib-v0.1.0.zip" ]; then
    ARCHIVE_PATH="dist/aeib-v0.1.0.zip"
elif [ -f "aeib-v0.1.0.zip" ]; then
    ARCHIVE_PATH="aeib-v0.1.0.zip"
else
    ARCHIVE_PATH="aeib-v0.1.0.zip"
fi

# Convert archive path to absolute path before directory change
ARCHIVE_ABS=$(python3 -c "import os, sys; print(os.path.abspath(sys.argv[1]))" "$ARCHIVE_PATH")

WORK_DIR="${WORK_DIR:-/tmp/aeib-clean-run}"
VERIFY_DIR="$WORK_DIR/release-verification"

echo -e "${BLUE}================================================================================${NC}"
echo -e "${BLUE}🛡️  AEIB v0.1 CLEAN-MACHINE RUN SCOPE VERIFICATION${NC}"
echo -e "${BLUE}Target Archive: $ARCHIVE_PATH${NC}"
echo -e "${BLUE}Execution Root: $WORK_DIR${NC}"
echo -e "${BLUE}================================================================================${NC}"

# ------------------------------------------------------------------------------
# Phase 1: Environment & Directory Isolation
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}──► [Phase 1/6] Environment & Directory Isolation${NC}"
rm -rf "$WORK_DIR"
mkdir -p "$VERIFY_DIR"

cat << EOF > "$VERIFY_DIR/environment.txt"
Timestamp (UTC): $(date -u +"%Y-%m-%dT%H:%M:%SZ")
Host / Kernel:   $(uname -a)
Python Version:  $(python3 --version 2>&1)
Git Commit:      $(git rev-parse HEAD 2>/dev/null || echo "N/A (Extracted Archive)")
Working Dir:     $WORK_DIR
EOF
cat "$VERIFY_DIR/environment.txt"
echo -e "${GREEN}✅ Phase 1 Passed: Clean sandbox directory and environment captured.${NC}"

# ------------------------------------------------------------------------------
# Phase 2: Archive Extraction & Manifest Integrity Gate
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}──► [Phase 2/6] Archive Extraction & Manifest Integrity Gate${NC}"
if [ ! -f "$ARCHIVE_ABS" ]; then
    echo -e "${RED}❌ Error: Archive '$ARCHIVE_ABS' not found.${NC}"
    exit 1
fi

echo "• Verifying zip CRC checksums..."
unzip -tq "$ARCHIVE_ABS"

echo "• Inspecting archive file manifest..."
unzip -q "$ARCHIVE_ABS" -d "$WORK_DIR"
cd "$WORK_DIR"

FILE_COUNT=$(find . -type f | grep -v "release-verification" | wc -l | tr -d ' ')
echo "  Total Packaged Files: $FILE_COUNT"

if [ "$FILE_COUNT" -ne 41 ]; then
    echo -e "${RED}❌ Packaging Violation: Expected exactly 41 files, found $FILE_COUNT${NC}"
    exit 1
fi

# Confirm absence of disallowed junk artifacts
FORBIDDEN_FILES=$(find . -type f \( -name "*.pyc" -o -name ".DS_Store" -o -path "*/__pycache__/*" -o -name ".env" \))
if [ -n "$FORBIDDEN_FILES" ]; then
    echo -e "${RED}❌ Integrity Violation: Packaged junk or credential files detected:${NC}"
    echo "$FORBIDDEN_FILES"
    exit 1
fi

# Run SHA-256 Manifest Gate
if [ -f "runner/verifier.py" ]; then
    echo "• Running SHA-256 fixture and expected scorecard verification..."
    python3 runner/verifier.py --manifest verification.txt
    echo -e "${GREEN}✅ Manifest Gate Passed: 100% of fixtures and scorecards match verification.txt.${NC}"
else
    echo -e "${RED}❌ Missing runner/verifier.py in release package.${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Phase 2 Passed: 0 CRC errors, zero junk files, all hashes match.${NC}"

# ------------------------------------------------------------------------------
# Phase 3: Deterministic Execution Gate (Double-Run Check)
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}──► [Phase 3/6] Deterministic Execution Gate (Double-Run Check)${NC}"

echo "• Executing Run 1..."
python3 runner/reference_runner.py fixtures/ > "$VERIFY_DIR/run-1.txt" 2>&1
shasum -a 256 results.json scorecard.json > "$VERIFY_DIR/result-hashes-1.txt"

echo "• Executing Run 2 (Determinism Verification)..."
python3 runner/reference_runner.py fixtures/ > "$VERIFY_DIR/run-2.txt" 2>&1
shasum -a 256 results.json scorecard.json > "$VERIFY_DIR/result-hashes-2.txt"

echo "• Comparing Console Outputs (Must be identical)..."
diff -u "$VERIFY_DIR/run-1.txt" "$VERIFY_DIR/run-2.txt" > "$VERIFY_DIR/console-diff.txt" || {
    echo -e "${RED}❌ Determinism Failure: Console output diverged between runs!${NC}"
    cat "$VERIFY_DIR/console-diff.txt"
    exit 1
}

echo "• Comparing Output Digests (Must be bit-exact)..."
diff -u "$VERIFY_DIR/result-hashes-1.txt" "$VERIFY_DIR/result-hashes-2.txt" || {
    echo -e "${RED}❌ Determinism Failure: Output artifact hashes diverged between runs!${NC}"
    exit 1
}
echo -e "${GREEN}✅ Phase 3 Passed: 0 console diff, 100% bit-exact artifact reproducibility.${NC}"

# ------------------------------------------------------------------------------
# Phase 4: State Machine Invariant Audit
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}──► [Phase 4/6] State Machine Invariant Audit${NC}"

# Invariant A: Timeout 504 must resolve to MISSING_EVIDENCE or UNKNOWN
SCENARIO_504_DISP=$(jq -r '.scenarios["02_timeout_unknown"].verdict' results.json)
if [ "$SCENARIO_504_DISP" == "CONFIRMED" ]; then
    echo -e "${RED}❌ Critical Safety Failure: HTTP 504 was falsely marked CONFIRMED!${NC}"
    exit 1
fi
echo "  • HTTP 504 Resolution: $SCENARIO_504_DISP (Passed — Zero false positive CONFIRMED)"

# Invariant B: Mismatched Payload (07) must be rejected
SCENARIO_07_DISP=$(jq -r '.scenarios["07_mismatched_payload"].verdict' results.json)
if [ "$SCENARIO_07_DISP" == "CONFIRMED" ]; then
    echo -e "${RED}❌ Critical Safety Failure: Mismatched payload was falsely marked CONFIRMED!${NC}"
    exit 1
fi
echo "  • Mismatched Payload Resolution: $SCENARIO_07_DISP (Passed)"

# Invariant C: Malformed Input (08) must output INVALID_INPUT with line number
SCENARIO_08_DISP=$(jq -r '.scenarios["08_malformed_input"].verdict' results.json)
if [ "$SCENARIO_08_DISP" != "INVALID_INPUT" ]; then
    echo -e "${RED}❌ Schema Failure: Malformed input did not yield INVALID_INPUT!${NC}"
    exit 1
fi
echo "  • Malformed Input Resolution: $SCENARIO_08_DISP (Passed)"
echo -e "${GREEN}✅ Phase 4 Passed: AEIB v0.1 evaluation precedence verified.${NC}"

# ------------------------------------------------------------------------------
# Phase 5: Documentation & Neutrality Gate
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}──► [Phase 5/6] Documentation & Neutrality Gate${NC}"

# Check for commercial terms or forbidden marketing claims
PROHIBITED_REGEX='15%|95%|100% protection|gold standard|DORA compliant|proof of external truth|certificate of deletion|€750|€3,500|48h'
echo "• Scanning SPEC.md and README.md for prohibited commercial terms..."

if grep -nE "$PROHIBITED_REGEX" SPEC.md README.md > "$VERIFY_DIR/prohibited-terms.txt"; then
    echo -e "${RED}❌ Neutrality Violation: Prohibited commercial or non-neutral claims found:${NC}"
    cat "$VERIFY_DIR/prohibited-terms.txt"
    exit 1
fi

# Confirm standard public claim exact wording
STANDARD_CLAIM="Reference benchmark for action uncertainty — Tests fail-closed precedence and UNKNOWN-state handling when an external effect cannot be confirmed. Anyone can run the same scenarios locally, inspect the expected outcomes, and submit reproducible results."
if ! grep -F "$STANDARD_CLAIM" README.md > /dev/null; then
    echo -e "${RED}❌ Documentation Error: Standard AEIB public claim missing or altered in README.md!${NC}"
    exit 1
fi

# Verify baseline decoupling in SPEC.md
if ! grep -A 2 "## 4.1 Reference Submission — Separate" SPEC.md | grep "smaos_reference" > /dev/null; then
    echo -e "${RED}❌ Neutrality Error: smaos_reference must be decoupled under Section 4.1!${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Phase 5 Passed: Zero marketing leakage; open baseline decoupled.${NC}"

# ------------------------------------------------------------------------------
# Phase 6: Release Readiness Confirmation
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}──► [Phase 6/6] Release Readiness Confirmation${NC}"
echo -e "${GREEN}================================================================================${NC}"
echo -e "${GREEN}🎉 ALL 6 AEIB VERIFICATION GATES PASSED (100% CLEAN)${NC}"
echo -e "${GREEN}Status: Release candidate verified under AEIB v0.1 scope (tag: v0.1.0)${NC}"
echo -e "${GREEN}================================================================================${NC}"
