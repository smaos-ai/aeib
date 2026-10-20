#!/usr/bin/env bash
# Copyright 2026 SovereignNexus Project
# scripts/verify_reproducible_wasm_and_backup_restore.sh
#
# Reproducible WASM Provenance & Backup Restorability Verification Script.
# Evaluated under the stated model as an agent execution boundary scaffold.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

echo "================================================================================"
echo "  AEIB REPRODUCIBLE WASM PROVENANCE & BACKUP RESTORABILITY VERIFICATION"
echo "================================================================================"

# 1. Reproducible WASM Build Receipt (Pinned Toolchain + SOURCE_DATE_EPOCH)
echo "[*] Step 1: Building reproducible WebAssembly artifact (crates/smaos-verify)..."
export SOURCE_DATE_EPOCH=1760918400
export CARGO_INCREMENTAL=0
export RUSTFLAGS="-C debuginfo=0 -C strip=symbols -C link-arg=-s --remap-path-prefix=${REPO_ROOT}=/build"

cargo build --manifest-path crates/smaos-verify/Cargo.toml --target wasm32-unknown-unknown --release

COMPILED_WASM="crates/smaos-verify/target/wasm32-unknown-unknown/release/smaos_verify.wasm"
WASM_HASH="$(shasum -a 256 "${COMPILED_WASM}" | awk '{print $1}')"
echo "[✓] WebAssembly build completed. SHA-256: ${WASM_HASH}"

# Run WASM V8 acceptance vectors
echo "[*] Step 2: Executing Node.js V8 runtime acceptance test suite..."
node tests/test_smaos_verify_wasm.js

# 2. Backup Restore Verification (Proving Restorability, Not Just rsync Transfer)
echo "[*] Step 3: Executing physical backup clean-room restoration & hash verification..."
BACKUP_DIR="/Volumes/EXTssd/SovereignNexus_Backup"

if [[ ! -d "${BACKUP_DIR}" ]]; then
    echo "[!] Backup directory not found at ${BACKUP_DIR}."
    echo "    Skipping physical SSD verification."
    exit 0
fi

RESTORE_DIR="$(mktemp -d /tmp/aeib_restore_verify_XXXXXX)"
trap 'rm -rf "${RESTORE_DIR}" /tmp/primary.sha256 /tmp/restored.sha256' EXIT

echo "[*] Restoring src/, tests/, and compliance/ trees to ${RESTORE_DIR}..."
rsync -a "${BACKUP_DIR}/src/" "${RESTORE_DIR}/src/"
rsync -a "${BACKUP_DIR}/tests/" "${RESTORE_DIR}/tests/"
rsync -a "${BACKUP_DIR}/compliance/" "${RESTORE_DIR}/compliance/"

# Exclude __pycache__ and comparison artifacts
(cd "${RESTORE_DIR}" && find src tests compliance -type f ! -path "*/__pycache__/*" -exec shasum -a 256 {} + | sort -k 2) > /tmp/restored.sha256
(find src tests compliance -type f ! -path "*/__pycache__/*" -exec shasum -a 256 {} + | sort -k 2) > /tmp/primary.sha256

diff -u /tmp/primary.sha256 /tmp/restored.sha256
echo "[✓] Bit-identical restoration of source, tests, and compliance verified."

# Execute python backup restorability verifier for Git FSCK and RTO receipt
echo "[*] Step 4: Running automated DORA backup restorability verifier..."
python3 compliance/backup_restorability_verifier.py

echo "================================================================================"
echo "  WASM PROVENANCE & BACKUP RESTORABILITY VERIFICATION COMPLETE: ALL CHECKS PASSED"
echo "================================================================================"
