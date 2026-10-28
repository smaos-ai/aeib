#!/usr/bin/env bash
set -euo pipefail

echo "==> Step 1: AST Purity Scanner"
python3 compliance/ast_purity.py .

echo "==> Step 2: Zero-Mock Enforcer"
python3 compliance/no_mock_enforcer.py

echo "==> Step 3: Run Full Benchmark Suite (Deterministic Seed 42)"
python3 benchmarks/aeib_execution_integrity/run_episodes.py \
  --episodes 500 \
  --seed 42 \
  --output benchmarks/aeib_execution_integrity/results_v0.2.4.json

echo "==> Step 4: Validate Result Properties"
python3 -c '
import json
with open("benchmarks/aeib_execution_integrity/results_v0.2.4.json") as f:
    data = json.load(f)
assert data["results"]["aeib"]["duplicate_effects"] == 0, "Duplicate effects > 0"
assert data["results"]["server_side_stable_key"]["duplicate_effects"] == 0
print("[✓] Execution invariants preserved across 500 episodes.")
'

echo "==> Step 5: Clean Tarball Packaging"
mkdir -p dist
git archive --format=tar.gz --prefix=aeib-enterprise-v1.0/ -o dist/aeib-enterprise-v1.0.tar.gz HEAD

echo "==> Step 6: Checksum Calculation"
shasum -a 256 dist/aeib-enterprise-v1.0.tar.gz > dist/SHA256SUMS
cat dist/SHA256SUMS
