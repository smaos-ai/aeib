#!/usr/bin/env bash
# Copyright 2026 SovereignNexus Project
# scripts/run_independent_validation_flow.sh
#
# Hermetic Independent Validation Flow for AEIB Reviewers and Auditors.
# Executes the full validation runner, verifies cryptographic receipts, and emits audit artifacts.
#
# Epistemic Notice: Evaluated under the stated local verification model.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

echo "================================================================================"
echo "  AEIB INDEPENDENT VALIDATION FLOW (CLEAN-ROOM REPRODUCTION)"
echo "================================================================================"
echo "Timestamp:    $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo "Commit SHA:   $(git rev-parse HEAD 2>/dev/null || echo 'UNKNOWN')"
echo "Host OS:      $(uname -s) $(uname -m)"
echo "--------------------------------------------------------------------------------"

python3 tools/independent_validation_runner.py

echo "Independent validation flow finished successfully."
