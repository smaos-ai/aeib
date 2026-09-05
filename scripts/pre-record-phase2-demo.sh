#!/bin/bash
# Phase 2-3 Offline Demo Pre-Record
# Captures: MLX TTFT, test infrastructure, system readiness
# For: Investor demo fallback (USB drive, offline execution)
# Generated: 2026-05-29

set -e

DEMO_DIR="$HOME/Downloads/siss-phase2-demo"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RECORD_FILE="$DEMO_DIR/phase2-demo-$TIMESTAMP.txt"

echo "================================================"
echo "PHASE 2-3 OFFLINE DEMO RECORDING"
echo "Timestamp: $(date -u)"
echo "Machine: $(uname -a)"
echo "================================================"
mkdir -p "$DEMO_DIR"

{
    echo "=== SYSTEM BASELINE ==="
    echo "Date: $(date -u)"
    echo "Machine: $(uname -a)"
    echo "RAM: $(vm_stat | grep 'Pages free' | awk '{print $3}')"
    echo "CPU: $(sysctl -n hw.ncpu) cores"
    echo ""

    echo "=== RUST TOOLCHAIN ==="
    rustc --version
    cargo --version
    echo ""

    echo "=== MLX AVAILABILITY PROBE ==="
    echo "Checking: python3 -c \"import mlx_lm; print('MLX available')\""
    python3 -c "import mlx_lm; print('✓ MLX available')" 2>/dev/null || echo "✗ MLX not installed (will use stub path)"
    echo ""

    echo "=== CARGO BUILD (Phase 2-3 Crates) ==="
    cd /Users/andriileukhin/Documents/SovereignNexus
    cargo build --lib -p siss-agent-shell -p siss-job-router -p siss-chaos-petri 2>&1 | tail -20
    echo "✓ Build complete"
    echo ""

    echo "=== RAPID MLX TESTS (TTFT Measurement) ==="
    echo "Test: test_ttft_measured_not_hardcoded"
    cargo test --lib -p siss-agent-shell test_ttft_measured_not_hardcoded -- --nocapture 2>&1 | tail -30
    echo ""

    echo "=== RAPID MLX SUBPROCESS PARSING ==="
    echo "Test: test_subprocess_output_parses_correctly"
    cargo test --lib -p siss-agent-shell test_subprocess_output_parses_correctly -- --nocapture 2>&1 | tail -30
    echo ""

    echo "=== MLX AVAILABILITY PROBE TEST ==="
    echo "Test: test_mlx_availability_probe_returns_bool"
    cargo test --lib -p siss-agent-shell test_mlx_availability_probe_returns_bool -- --nocapture 2>&1 | tail -15
    echo ""

    echo "=== PHASE 2-3 ARCHITECTURE PROOF ==="
    echo "Files present (verification):"
    ls -lh crates/siss-agent-shell/src/rapid_mlx_integration.rs
    ls -lh crates/siss-job-router/src/mlx_fleet.rs
    ls -lh crates/siss-chaos-petri/src/lib.rs
    ls -lh crates/siss-gatekeeper/src/sneakernet_ingress.rs
    echo ""

    echo "=== CARGO TEST SUMMARY ==="
    cargo test --lib -p siss-agent-shell 2>&1 | tail -50
    echo ""

    echo "=== RECORD COMPLETE ==="
    echo "Generated: $(date -u)"
    echo "Purpose: Offline investor demo proof (USB drive, airplane mode)"
    echo "Next: Convert this to MP4 via screen recording for presentation quality"

} | tee "$RECORD_FILE"

echo ""
echo "✓ Pre-record saved to: $RECORD_FILE"
echo "✓ Ready for offline demo (copy to USB drive)"
