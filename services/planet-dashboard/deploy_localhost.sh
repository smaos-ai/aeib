#!/bin/bash
# Deploy Vision API to localhost:8000

set -e

cd "$(dirname "$0")"

echo "Building Docker image..."
docker-compose -f docker/docker-compose.yml build

echo "Starting Vision API on localhost:8000..."
docker-compose -f docker/docker-compose.yml up -d

echo ""
echo "=== DEPLOYMENT COMPLETE ==="
echo "Vision API available at: http://localhost:8000"
echo ""
echo "Endpoints:"
echo "  POST /v1/govern          — Governance decision"
echo "  GET  /health             — Health check"
echo "  GET  /metrics            — Metrics"
echo ""
echo "To check logs: docker-compose -f docker/docker-compose.yml logs -f"
echo "To stop:      docker-compose -f docker/docker-compose.yml down"
