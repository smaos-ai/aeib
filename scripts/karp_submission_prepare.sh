#!/bin/bash
# KARP Submission Bundle Preparation Script
# Usage: bash scripts/karp_submission_prepare.sh
# Output: ~/smaos-karp-bundle-sep2026.zip (ready to attach to email)

set -e

echo "======================================"
echo "KARP Submission Bundle Preparation"
echo "======================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Paths
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUNDLE_DIR="$HOME/smaos-karp-bundle-sep2026"
BUNDLE_ZIP="$HOME/smaos-karp-bundle-sep2026.zip"

# Files required
declare -a FILES=(
  "KARP_POPIS_PROJEKTU.md"
  "GOLDEN_SET_50_TASKS.md"
  "SECURITY_TEST_HARNESS.md"
  "CLASSIC_AND_CHINESE_ALIGNMENT.md"
  "KARP_5DAY_BOOTCAMP.md"
  "ANNEX_IV_REFRAME_SLIDE.md"
  "ANNEX_IV_DOSSIER.md"
  "golden_set_results.json"
  "SECURITY_TEST_RESULTS.json"
  "bootcamp_results.json"
  "scripts/colibri_harness.sh"
)

echo "Step 1: Verify all 11 files exist"
echo "=================================="
MISSING=0
for file in "${FILES[@]}"; do
  if [ -f "$PROJECT_ROOT/$file" ]; then
    SIZE=$(ls -lh "$PROJECT_ROOT/$file" | awk '{print $5}')
    echo -e "${GREEN}✓${NC} $file ($SIZE)"
  else
    echo -e "${RED}✗${NC} MISSING: $file"
    MISSING=$((MISSING + 1))
  fi
done

if [ $MISSING -gt 0 ]; then
  echo -e "\n${RED}ERROR: $MISSING files missing${NC}"
  exit 1
fi

echo ""
echo "Step 2: Create bundle directory"
echo "================================"
if [ -d "$BUNDLE_DIR" ]; then
  echo -e "${YELLOW}!${NC} Bundle directory exists, removing..."
  rm -rf "$BUNDLE_DIR"
fi
mkdir -p "$BUNDLE_DIR"
echo -e "${GREEN}✓${NC} Created: $BUNDLE_DIR"

echo ""
echo "Step 3: Copy files to bundle"
echo "============================"
for file in "${FILES[@]}"; do
  cp "$PROJECT_ROOT/$file" "$BUNDLE_DIR/$(basename $file)"
  echo -e "${GREEN}✓${NC} Copied $(basename $file)"
done

echo ""
echo "Step 4: Create ZIP archive"
echo "=========================="
cd "$HOME"
rm -f "$BUNDLE_ZIP" 2>/dev/null || true
zip -q -r smaos-karp-bundle-sep2026.zip smaos-karp-bundle-sep2026/
SIZE=$(ls -lh "$BUNDLE_ZIP" | awk '{print $5}')
echo -e "${GREEN}✓${NC} Created: $BUNDLE_ZIP ($SIZE)"

echo ""
echo "Step 5: Verify bundle"
echo "===================="
FILE_COUNT=$(unzip -l "$BUNDLE_ZIP" | tail -1 | awk '{print $2}')
echo -e "${GREEN}✓${NC} Bundle contains $FILE_COUNT files"

# Verify size <25 MB
SIZE_BYTES=$(ls -l "$BUNDLE_ZIP" | awk '{print $5}')
LIMIT_BYTES=$((25 * 1024 * 1024))
if [ $SIZE_BYTES -lt $LIMIT_BYTES ]; then
  echo -e "${GREEN}✓${NC} Size check: $SIZE < 25 MB (email limit)"
else
  echo -e "${RED}✗${NC} Size check FAILED: $SIZE > 25 MB"
  exit 1
fi

echo ""
echo "Step 6: JSON validation"
echo "======================"
for json_file in "$BUNDLE_DIR"/*.json; do
  if [ -f "$json_file" ]; then
    if python3 -m json.tool "$json_file" > /dev/null 2>&1; then
      echo -e "${GREEN}✓${NC} Valid JSON: $(basename $json_file)"
    else
      echo -e "${RED}✗${NC} Invalid JSON: $(basename $json_file)"
      exit 1
    fi
  fi
done

echo ""
echo "======================================"
echo "SUBMISSION READY"
echo "======================================"
echo ""
echo "Bundle location: $BUNDLE_ZIP"
echo "Bundle size:     $SIZE"
echo "Files:           11"
echo ""
echo "Next Steps:"
echo "1. Open Gmail"
echo "2. Create new email to: romana.cernikova@karp-kv.cz"
echo "3. Subject: 'SMAOS Phase 1: KARP 120k CZK Application + 7 Proof Artifacts'"
echo "4. Body: Paste from ANNEX_IV_REFRAME_SLIDE.md 'Why This Wins KARP' section"
echo "5. Attach: $BUNDLE_ZIP"
echo "6. Send at 9:00 AM CET"
echo ""
echo "Expected approval: Oct 15, 2026"
echo ""
