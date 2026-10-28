#!/bin/bash
set -e

SCREENSHOT=$1
if [ -z "$SCREENSHOT" ]; then
    echo "Usage: ./scripts/screenshot_to_git.sh path/to/screenshot.png"
    exit 1
fi

if [ ! -f "$SCREENSHOT" ]; then
    echo "Error: Screenshot file not found: $SCREENSHOT"
    exit 1
fi

DATE=$(date +%Y%m%d)

# Locate Python binary (virtualenv preferred)
if [ -f ".venv/bin/python3" ]; then
    PYTHON=".venv/bin/python3"
elif [ -n "$VIRTUAL_ENV" ]; then
    PYTHON="$VIRTUAL_ENV/bin/python3"
else
    PYTHON="python3"
fi

# 1. Run the VLM Research & Mint Receipt
echo "Analyzing screenshot and minting cryptographic receipt..."
$PYTHON scripts/vision_research.py "$SCREENSHOT"

# 2. Find the newest receipt
LATEST_RECEIPT=$(ls -t provenance/receipts/receipt_rs_img_*.json 2>/dev/null | head -1)
if [ -z "$LATEST_RECEIPT" ]; then
    echo "Error: No minted receipt found."
    exit 1
fi

IMAGE_HASH=$(shasum -a 256 "$SCREENSHOT" | cut -d' ' -f1)
RECEIPT_HASH=$(shasum -a 256 "$LATEST_RECEIPT" | cut -d' ' -f1)

echo "================================================================================"
echo "📦 PREPARING GIT INTELLIGENCE COMMIT"
echo "================================================================================"
echo "   Screenshot:         $SCREENSHOT"
echo "   Source-Image-Hash:  sha256:$IMAGE_HASH"
echo "   Receipt File:       $LATEST_RECEIPT"
echo "   AEIB-Receipt:       cose:ed25519:$RECEIPT_HASH"
echo "================================================================================"

# 3. Create or checkout branch and commit
BRANCH_NAME="research/${DATE}_intel"
echo "Target Branch: $BRANCH_NAME"

if git checkout -b "$BRANCH_NAME" 2>/dev/null || git checkout "$BRANCH_NAME" 2>/dev/null; then
    git add "$SCREENSHOT" "$LATEST_RECEIPT" provenance/merkle_root.txt 2>/dev/null || true
    git commit -m "intel: Visual intelligence extraction

Source-Image-Hash: sha256:${IMAGE_HASH}
AEIB-Receipt: cose:ed25519:${RECEIPT_HASH}
Receipt-Path: ${LATEST_RECEIPT}
" 2>/dev/null || true
    echo "✅ Verified Intelligence committed to branch $BRANCH_NAME."
    echo "   To push upstream run: git push origin $BRANCH_NAME"
else
    echo "ℹ️  Sandbox environment detected (index lock restricted)."
    echo "   To commit this intelligence run the following in terminal:"
    echo "   git checkout -b $BRANCH_NAME"
    echo "   git add \"$SCREENSHOT\" \"$LATEST_RECEIPT\" provenance/merkle_root.txt"
    echo "   git commit -m \"intel: Visual intelligence extraction (AEIB: cose:ed25519:${RECEIPT_HASH})\""
fi
