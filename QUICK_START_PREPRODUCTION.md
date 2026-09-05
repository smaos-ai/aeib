# SovereignNexus Pre-Production — Quick Start (30 Minutes)

## Fast Path to Running System (Docker Compose)

### Prerequisites (5 minutes)
```bash
# Install Docker Desktop (if not already)
# macOS: brew install --cask docker
# Ubuntu: curl https://get.docker.com | sh

# Verify Docker
docker --version  # Should be 20.10+
docker-compose --version  # Should be 2.0+
```

### Deploy (10 minutes)
```bash
cd /Users/andriileukhin/Documents/SovereignNexus

# Build Docker images
docker build -f Dockerfile.preproduction -t smaos/harness:latest .

# Start full stack
docker-compose -f docker-compose.preproduction.yml up -d

# Wait for services to initialize (watch the logs)
docker-compose -f docker-compose.preproduction.yml logs -f harness
# Look for: "Health check passed" or "Ready for requests"
```

### Verify (5 minutes)
```bash
# Check all services running
docker-compose -f docker-compose.preproduction.yml ps
# Expected: All services showing "Up"

# Test API
curl http://localhost:8080/health
# Expected: {"status":"ok"}

# Access dashboards
open http://localhost:3001  # Grafana (admin/admin-unsafe)
open http://localhost:16686  # Jaeger
```

### Run a Pilot (10 minutes)
```bash
# Execute hotel credit decision pilot
docker exec smaos-harness \
  /app/bin/pilot-hotel --iterations 10

# Watch decisions in real-time
docker logs -f smaos-harness | grep decision

# Check proof generation
docker exec smaos-harness \
  tail -1 /var/lib/smaos/proofs/agentacct_ledger.json | jq .
```

---

## System Status

### Check Health
```bash
# All containers
docker-compose -f docker-compose.preproduction.yml ps

# Database connectivity
docker exec smaos-postgresql pg_isready -U smaos -d smaos_phase1

# Model server
curl http://localhost:11434/api/tags | jq .models[].name

# Metrics
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | .labels.job'
```

### View Logs
```bash
# Harness
docker logs -f smaos-harness | grep -E "decision|error|proof"

# Database
docker logs -f smaos-postgresql

# All services
docker-compose logs -f
```

---

## Key Endpoints

| Service | URL | Purpose |
|---------|-----|---------|
| **Harness API** | http://localhost:8080 | Main decision engine |
| **Health Check** | http://localhost:8080/health | System status |
| **Prometheus** | http://localhost:9090 | Metrics database |
| **Grafana** | http://localhost:3001 | Monitoring dashboard |
| **Jaeger UI** | http://localhost:16686 | Distributed traces |
| **PostgreSQL** | localhost:5432 | Database (psql command) |
| **Ollama API** | http://localhost:11434 | Model server |
| **Vault** | http://localhost:8200 | Secret management |

---

## Stop & Cleanup

```bash
# Stop all services (preserve data)
docker-compose down

# Stop and wipe all data (full reset)
docker-compose down -v

# Remove images to free space
docker rmi smaos/harness:latest smaos/freetoken:latest
```

---

## Common Issues & Fixes

**Issue:** "Harness not healthy"
```bash
# Check logs
docker logs smaos-harness | tail -50

# Restart
docker-compose restart harness
```

**Issue:** "Database connection timeout"
```bash
# Check PostgreSQL
docker exec smaos-postgresql pg_isready -U smaos

# Restart database
docker-compose restart postgresql
```

**Issue:** "Model not loading in Ollama"
```bash
# Pull model manually
docker exec smaos-ollama ollama pull qwen2.5:7b

# Verify
docker exec smaos-ollama ollama list
```

**Issue:** "Out of disk space"
```bash
# Check disk
df -h

# Clean Docker
docker system prune -a --volumes

# Remove unused images
docker rmi $(docker images -q)
```

---

## Next Steps

1. **Let system run for 24+ hours** to validate stability
2. **Check Grafana dashboard** for metrics (latency, throughput, RAGAS)
3. **Monitor logs** for errors or warnings
4. **When ready:** Deploy to cloud (AWS EC2) for KARP submission

---

**Time to production-ready:** 30 minutes  
**System uptime target:** 168+ hours (7 days)  
**Success metric:** RAGAS score > 87%, zero crashes

For detailed runbook, see: `PRE_PRODUCTION_RUNBOOK.md`
