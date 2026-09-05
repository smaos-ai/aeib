#!/bin/bash
# Layer 0 Benchmark Runner Script
# Reproduces the M3 Pro certification benchmarks
# Usage: ./benchmarks/run_benchmarks.sh [output_file]

set -euo pipefail

OUTPUT_FILE="${1:-/tmp/layer0_benchmarks_$(date +%Y%m%d_%H%M%S).log}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "════════════════════════════════════════════════════════════════════════════════"
echo "Layer 0 Benchmark Suite - M3 Pro Certification"
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""
echo "Hardware Detection:"
system_profiler SPHardwareDataType 2>/dev/null | grep -E "Model Name|Chip|Total Number|Memory" | head -10
echo ""
echo "Running benchmarks (this will take ~5 minutes)..."
echo "Output file: $OUTPUT_FILE"
echo ""

# Run the benchmark suite
cd "$PROJECT_ROOT"
cargo bench -p siss-layer00 --bench layer0_benchmarks -- --verbose 2>&1 | tee "$OUTPUT_FILE"

echo ""
echo "════════════════════════════════════════════════════════════════════════════════"
echo "Benchmark complete. Extracting key results..."
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""

# Extract key results
echo "KEY LATENCY MEASUREMENTS:"
echo "─────────────────────────────────────────────────────────────────────────────"

grep -A 3 "gate_operations/mandate_registration$" "$OUTPUT_FILE" | grep "time:" || echo "mandate_registration: (data pending)"
grep -A 3 "gate_operations/capability_token_request$" "$OUTPUT_FILE" | grep "time:" || echo "capability_token_request: (data pending)"
grep -A 3 "gate_operations/tool_invocation$" "$OUTPUT_FILE" | grep "time:" || echo "tool_invocation: (data pending)"
grep -A 3 "gate_operations/mandate_validation$" "$OUTPUT_FILE" | grep "time:" || echo "mandate_validation: (data pending)"
grep -A 3 "merkle_chain/merkle_chain_100_entries_verify$" "$OUTPUT_FILE" | grep "time:" || echo "merkle_chain_100_verify: (data pending)"
grep -A 3 "merkle_chain_large/merkle_chain_1000_entries_verify$" "$OUTPUT_FILE" | grep "time:" || echo "merkle_chain_1000_verify: (data pending)"

echo ""
echo "════════════════════════════════════════════════════════════════════════════════"
echo "BENCHMARK COMPLETE"
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""
echo "Full results saved to: $OUTPUT_FILE"
echo ""
echo "Next steps:"
echo "1. Review results in $OUTPUT_FILE"
echo "2. Compare against targets in benchmarks/layer0_m3pro_certification.md"
echo "3. Update certification report if hardware differs"
echo ""
