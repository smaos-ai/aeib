#!/usr/bin/env bash
# ==============================================================================
# File: scripts/run_all_verification_gates.sh
# Description: Unified shell wrapper for the AEIB verification orchestrator.
# ==============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "[INFO] Activating virtual environment if present..."
if [ -d ".venv" ]; then
    source ".venv/bin/activate"
fi

echo "[INFO] Starting Unified Verification Runner..."
python3 tools/run_all_verification_gates.py
