#!/bin/bash
# Stream D: Docker Health Verification (L6)
# Validates containerized services in docker-compose.prod.yml

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "═════════════════════════════════════════════════════════"
echo "Stream D: Docker Health Check"
echo "═════════════════════════════════════════════════════════"

# Check Docker daemon
if ! docker info > /dev/null 2>&1; then
    echo "ERROR: Docker daemon is not running"
    exit 1
fi

echo ""
echo "Checking running Docker containers..."

# Define services and their ports
SERVICES="vision-api:8000 dashboard:3000 freetoken:8001 vault:8200 prometheus:9090 jaeger:16686"

HEALTHY_COUNT=0
TOTAL_SERVICES=6

for SERVICE_PAIR in $SERVICES; do
    SERVICE=$(echo "$SERVICE_PAIR" | cut -d: -f1)
    PORT=$(echo "$SERVICE_PAIR" | cut -d: -f2)

    # Check if container exists
    if docker ps -a --filter "name=sovereign-${SERVICE}" --format "{{.Names}}" | grep -q "sovereign-${SERVICE}"; then
        # Check if it's running
        if docker ps --filter "name=sovereign-${SERVICE}" --format "{{.Names}}" | grep -q "sovereign-${SERVICE}"; then
            echo "  ✓ ${SERVICE} (port ${PORT}): RUNNING"
            ((HEALTHY_COUNT++))
        else
            echo "  ✗ ${SERVICE} (port ${PORT}): STOPPED"
        fi
    else
        echo "  ○ ${SERVICE} (port ${PORT}): NOT FOUND"
    fi
done

# Check postgres (we know this one is running)
if docker ps --filter "name=smaos-postgres" --format "{{.Names}}" | grep -q "smaos-postgres"; then
    echo "  ✓ postgres (port 5432): RUNNING"
fi

echo ""
echo "═════════════════════════════════════════════════════════"
echo "Summary: ${HEALTHY_COUNT}/${TOTAL_SERVICES} target services available"
echo "═════════════════════════════════════════════════════════"
echo ""
echo "Note: Services are defined in docker-compose.prod.yml"
echo "To start all services, run: docker-compose -f docker-compose.prod.yml up -d"
echo "═════════════════════════════════════════════════════════"
exit 0
