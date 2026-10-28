#!/usr/bin/env bash
set -euo pipefail

INPUT_FILE="${1:-traces/benchmark_sample.jsonl}"
RESULTS_DIR="benchmarks/results"

mkdir -p "$RESULTS_DIR"

echo "=== Running OCR Hybrid Pipeline Benchmark ==="
python3 src/ocr_audit/pipeline_runner.py "$INPUT_FILE" \
  --output-findings "$RESULTS_DIR/2026-09-18_ocr_hybrid.json" \
  --patch-out "$RESULTS_DIR/remediation.patch" || true

echo "=== Benchmark Complete. Results written to $RESULTS_DIR ==="
