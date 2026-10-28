#!/usr/bin/env bash
###############################################################################
# scripts/bootstrap_build_artifacts.sh
#
# Builds the two git-ignored artifacts that tests need on a clean checkout:
#   - target/debug/smaos-pqc-signer          (tests/test_hybrid_pqc_envelope.py)
#   - smaos-wasm-verifier/pkg/*.wasm|js|d.ts (tests/test_integration_gates_g1_g7.py)
#
# Offline only: `cargo build --offline` and `wasm-pack build --mode no-install`
# use the toolchain and crates already cached on this machine. Nothing is
# downloaded, nothing is installed, no history is rewritten. If the cache is
# missing, the script fails and says so (exit 2) instead of fetching.
###############################################################################
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

for tool in cargo wasm-pack; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "[PREREQ] $tool not found; install it first (not done by this script)" >&2
        exit 2
    fi
done

echo "[1/2] cargo build --offline -p smaos-pqc-signer"
if ! cargo build --offline -p smaos-pqc-signer; then
    echo "[PREREQ] offline cargo build failed (crate cache missing?)" >&2
    exit 2
fi
test -x target/debug/smaos-pqc-signer

echo "[2/2] wasm-pack build --mode no-install (smaos-wasm-verifier)"
if ! (cd smaos-wasm-verifier && wasm-pack build --mode no-install --target web --out-dir pkg); then
    echo "[PREREQ] offline wasm-pack build failed (wasm32 target or wasm-bindgen missing?)" >&2
    exit 2
fi
test -f smaos-wasm-verifier/pkg/smaos_wasm_verifier_bg.wasm

echo "artifacts built: target/debug/smaos-pqc-signer, smaos-wasm-verifier/pkg/"
