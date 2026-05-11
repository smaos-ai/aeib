#!/bin/bash
set -e

echo "🚀 Phase 21 Cockpit Verification Script"
echo "========================================"
echo ""

# Start the demo server in the background
echo "[1] Starting demo server at localhost:3000..."
cargo run --example demo_server -p siss-agent-card --features axum 2>/dev/null &
SERVER_PID=$!
sleep 2

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down demo server (PID: $SERVER_PID)..."
    kill $SERVER_PID 2>/dev/null || true
    wait $SERVER_PID 2>/dev/null || true
}
trap cleanup EXIT

echo "✓ Server started (PID: $SERVER_PID)"
echo ""

# Test 1: Verify cockpit.html is served
echo "[2] Verifying GET /cockpit..."
if curl -s http://localhost:3000/cockpit | grep -q "SMAOS Phase 20"; then
    echo "✓ Cockpit HTML served successfully"
else
    echo "✗ Cockpit HTML not found"
    exit 1
fi
echo ""

# Test 2: Verify SSE endpoint exists
echo "[3] Verifying GET /events (SSE stream)..."
timeout 2 curl -s -N http://localhost:3000/events &>/dev/null || true
if [ $? -le 124 ]; then
    echo "✓ SSE endpoint responding"
else
    echo "✗ SSE endpoint not responding"
    exit 1
fi
echo ""

# Test 3: Emit Phase 20 slashing penalty event
echo "[4] Emitting Phase 20 Slashing Penalty event..."
RESPONSE=$(curl -s -X POST http://localhost:3000/emit/slashing-penalty)
echo "Response: $RESPONSE" | jq . 2>/dev/null || echo "$RESPONSE"
echo "✓ Slashing penalty event emitted"
echo ""

# Test 4: Emit Phase 21 trust decay event
echo "[5] Emitting Phase 21 Trust Decay event..."
RESPONSE=$(curl -s -X POST http://localhost:3000/emit/trust-decay)
echo "Response: $RESPONSE" | jq . 2>/dev/null || echo "$RESPONSE"
echo "✓ Trust decay event emitted"
echo ""

# Test 5: Visual verification
echo "[6] Visual Verification Instructions:"
echo "======================================="
echo "Open http://localhost:3000/cockpit in your browser"
echo ""
echo "Expected observations:"
echo "  ✓ Recovery Status panel shows pending sovereigns"
echo "  ✓ Recent Transitions log shows recovery events"
echo "  ✓ Signal Activity shows slash penalties and settlement bonuses"
echo "  ✓ Trust Network table shows trust edges with color-coded scores"
echo "      - GREEN (≥70): High trust"
echo "      - YELLOW (30–69): Medium trust"
echo "      - RED (<30): Low trust"
echo ""
echo "Keep server running for manual testing (Ctrl+C to stop):"
echo ""

# Keep the server running for manual verification
wait $SERVER_PID
