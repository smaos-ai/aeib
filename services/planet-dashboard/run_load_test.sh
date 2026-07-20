#!/bin/bash
# Run load test: 100 concurrent users, 10 req/sec spawn rate, 60 second duration
# Expected: p99 <100ms, avg <50ms

set -e

# Ensure we're in the right directory
cd "$(dirname "$0")"

echo "Starting Vision API on localhost:8000..."
timeout 65 python3 -m uvicorn vision_api_fastapi:app --host 0.0.0.0 --port 8000 --workers 2 > api.log 2>&1 &
API_PID=$!
sleep 2

# Run load test
echo "Running Locust load test (60 seconds)..."
locust -f load_test_locust.py \
    -H http://localhost:8000 \
    --headless \
    --users 100 \
    --spawn-rate 10 \
    --run-time 60s \
    --csv=load_test_results

# Cleanup
kill $API_PID || true
wait $API_PID 2>/dev/null || true

# Print summary
echo ""
echo "=== LOAD TEST RESULTS ==="
if [ -f load_test_results_stats.csv ]; then
    cat load_test_results_stats.csv
else
    echo "Results file not found"
fi
