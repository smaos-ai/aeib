# SOVEREIGN OS — PRODUCTION DEPLOYMENT GUIDE

**Status:** Production-Ready (July 31, 2026)  
**Architecture:** Containerized 24/7 runtime with automated health monitoring + rollback  
**Uptime Target:** 99.9% (8.76 hours downtime per year)

---

## 📋 Quick Start (Single Command)

```bash
# 1. Build and start all services
docker compose -f docker-compose.prod.yml up -d

# 2. Start health monitoring loop (separate terminal)
chmod +x healthcheck.sh rollback.sh
./healthcheck.sh

# 3. Verify all endpoints
curl http://localhost:8000/health    # Vision API
curl http://localhost:3000           # Dashboard
curl http://localhost:11434/api/tags # Ollama
curl http://localhost:8200/v1/sys/health # Vault
curl http://localhost:9090/-/healthy # Prometheus
curl http://localhost:16686          # Jaeger
```

**Expected Output:**
```
✅ Vision API
✅ Dashboard
✅ Ollama LLM
✅ Vault
✅ Prometheus
✅ Jaeger

✅ ALL SYSTEMS HEALTHY
```

---

## 🏗️ Architecture Overview

### 6 Containerized Services

| Service | Port | Purpose | Status | Restarts |
|---------|------|---------|--------|----------|
| **Vision API** | 8000 | Governance decisions + Merkle proofs | Critical | Always |
| **Dashboard** | 3000 | Next.js UI (Governance + Security) | Critical | Always |
| **Ollama** | 11434 | qwen2.5-coder:14b inference | Important | Always |
| **Vault** | 8200 | Secret management + OIDC | Important | Always |
| **Prometheus** | 9090 | Metrics aggregation + OT traces | Important | Always |
| **Jaeger** | 16686 | Distributed tracing (OpenTelemetry) | Important | Always |

### Network Topology

```
┌─────────────────────────────────────────────┐
│ sovereign-network (172.28.0.0/16)           │
├─────────────────────────────────────────────┤
│ ┌─────────┐ ┌─────────┐ ┌─────────┐         │
│ │ Vision  │ │Dashboard│ │ Ollama  │         │
│ │  API    │ │         │ │  LLM    │         │
│ └────┬────┘ └────┬────┘ └────┬────┘         │
│      │           │           │              │
│      └───────────┴───────────┘              │
│              ↓                              │
│      ┌──────────────────┐                  │
│      │    Prometheus    │                  │
│      │   (Metrics)      │                  │
│      └──────────────────┘                  │
│              ↓                              │
│      ┌──────────────────┐                  │
│      │     Jaeger       │                  │
│      │    (Traces)      │                  │
│      └──────────────────┘                  │
│      ┌──────────────────┐                  │
│      │     Vault        │                  │
│      │   (Secrets)      │                  │
│      └──────────────────┘                  │
└─────────────────────────────────────────────┘
```

---

## 🏥 Health Monitoring (Automatic)

### 60-Second Check Loop

**What it monitors:**

1. **Service Health** (HTTP 200 or /health endpoint)
   - Vision API: `/health`
   - Dashboard: `GET /`
   - Ollama: `/api/tags`
   - Vault: `/v1/sys/health`
   - Prometheus: `/-/healthy`
   - Jaeger: `GET /`

2. **Latency** (p99 < 1000ms)
   - Queries Prometheus metrics
   - Triggers alert if exceeds threshold

3. **State Snapshot** (Merkle-rooted)
   - Records service state every 60s
   - Computes SHA256 hash
   - Appends to `EXEC_LOG.json`

### Running Monitoring

**Terminal 1: Start services**
```bash
docker compose -f docker-compose.prod.yml up -d
```

**Terminal 2: Start health checks (background)**
```bash
./healthcheck.sh &
# Output every 60s:
# ✅ Vision API
# ✅ Dashboard
# ✅ Ollama LLM
# ✅ Vault
# ✅ Prometheus
# ✅ Jaeger
# ✅ Latency p99: 45ms
# ✅ ALL SYSTEMS HEALTHY
```

**Manual health check (one-time)**
```bash
./healthcheck.sh once
```

---

## 🔄 Automated Rollback

### Trigger Conditions

Rollback is automatically triggered if:
- **2+ services fail** health check
- **Latency p99 > 1000ms** (5 consecutive checks)
- **State snapshot corrupted** (Merkle hash mismatch)

### Recovery Process (Automatic)

1. **Find last known good snapshot** (Merkle-verified)
2. **Stop all services** (graceful)
3. **Clear ephemeral state** (logs, temp volumes)
4. **Restart from snapshot** (docker compose up)
5. **Verify recovery** (5 health checks)
6. **Log rollback event** (append to EXEC_LOG.json)

### Example Rollback Execution

```bash
# System detects 3 service failures → automatic trigger

[CRITICAL FAILURE DETECTED — TRIGGERING ROLLBACK]

🔍 Searching for last known good state...
✅ Found snapshot: /var/lib/sovereign/snapshots/state-2026-07-31T00:30:00Z.json
   Created: 2026-07-31T00:30:00Z
   Merkle:  a1b2c3d4e5f6...

🔐 Verifying snapshot integrity...
✅ Snapshot integrity verified

⏸️  Stopping Docker services...
✅ Services stopped

🧹 Clearing transient state...
✅ Ephemeral state cleared

🚀 Restarting services from snapshot...
✅ Services restarted

✅ Verifying recovery...
✅ RECOVERY SUCCESSFUL

[ROLLBACK COMPLETE — System restored to healthy state]
```

### Manual Rollback (if needed)

```bash
./rollback.sh
```

---

## 📊 Monitoring Dashboard

### Prometheus (Metrics)

Access: `http://localhost:9090`

**Key Queries:**
```promql
# Request latency (p99 over 5 minutes)
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))

# Request throughput
rate(http_requests_total[5m])

# Service uptime
up{job="sovereign-services"}
```

### Jaeger (Distributed Traces)

Access: `http://localhost:16686`

**Features:**
- Real-time trace visualization
- Latency breakdown per service
- Error detection
- Dependency mapping

---

## 🔐 Security & Isolation

### Container Security

- **Non-root users** (uid 1000:1000)
- **Dropped capabilities** (CAP_DROP=ALL, selectively add NET_BIND_SERVICE)
- **Read-only root filesystem** (where applicable)
- **Network isolation** (sovereign-network bridge)
- **No privilege escalation** (no-new-privileges)

### Storage Isolation

- **Ephemeral volumes** (logs, temp data) — cleared on rollback
- **Persistent volumes** (Ollama models, Vault data) — preserved
- **Merkle-rooted state** (immutable audit trail)

### Secret Management

- **Vault OIDC** (GitHub Actions → Vault → secrets)
- **No hard-coded credentials** (all from Vault or environment)
- **Token rotation** (5-minute TTL)

---

## 🚨 Troubleshooting

### Service Won't Start

```bash
# Check logs
docker compose -f docker-compose.prod.yml logs <service-name>

# Restart single service
docker compose -f docker-compose.prod.yml restart <service-name>

# Rebuild and restart
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d --build
```

### Health Check Failing

```bash
# Run one-time health check with verbose output
./healthcheck.sh once

# Check individual service
curl -v http://localhost:8000/health
curl -v http://localhost:3000

# View health logs
tail -f /var/log/sovereign/healthcheck.log
```

### Rollback Stuck

```bash
# Manual recovery
docker compose -f docker-compose.prod.yml down --remove-orphans
docker volume ls  # Check for orphaned volumes
docker volume rm <volume-name>  # Remove if needed
docker compose -f docker-compose.prod.yml up -d

# Verify
./healthcheck.sh once
```

### High Latency (p99 > 1000ms)

```bash
# Check Prometheus metrics
curl 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))'

# View Jaeger traces for slowest requests
# Access: http://localhost:16686 → Search → Service → Ops → Trace

# Common causes:
# 1. Ollama model not loaded (check: curl http://localhost:11434/api/tags)
# 2. Database query slow (check Prometheus slow_queries metric)
# 3. Network congestion (check Docker network stats)

# Solution:
docker compose -f docker-compose.prod.yml restart vision-api
./healthcheck.sh once  # Verify recovery
```

---

## 📈 Scaling Considerations

### Current Capacity

- **Vision API**: 4 workers (configurable in docker-compose.prod.yml)
- **Dashboard**: Single Node.js instance (add load balancer if needed)
- **Ollama**: Single GPU/CPU (add replicas for multi-inference)
- **Vault**: HA standby mode (requires PostgreSQL backend)

### Scaling Steps

**Add API Workers:**
```yaml
vision-api:
  environment:
    WORKERS: 8  # Change from 4 to 8
  # Restart: docker compose up -d
```

**Add Load Balancer (Nginx):**
```yaml
nginx:
  image: nginx:latest
  ports:
    - "80:80"
  volumes:
    - ./nginx.conf:/etc/nginx/nginx.conf
  depends_on:
    - vision-api
    - dashboard
```

**Add Vault HA Peers:**
Requires PostgreSQL backend + Vault Enterprise license.

---

## 📋 State Snapshots (EXEC_LOG.json)

### Format

```json
{
  "timestamp": "2026-07-31T00:30:00Z",
  "event": "healthcheck",
  "state_hash": "a1b2c3d4e5f6...",
  "services": {
    "vision_api": {"status": "healthy"},
    "dashboard": {"status": "healthy"},
    "ollama": {"models": 1},
    "vault": {"initialized": true},
    "prometheus": "up",
    "jaeger": "up"
  }
}
```

### Merkle Chain

Each snapshot is Merkle-rooted (SHA256) and linked:
```
Snapshot T0: hash0 = SHA256(services_state_0)
Snapshot T1: hash1 = SHA256(services_state_1 + hash0)
Snapshot T2: hash2 = SHA256(services_state_2 + hash1)
```

### Verification

```bash
# Verify snapshot integrity
jq -r '.merkle_root' /var/lib/sovereign/snapshots/state-*.json | \
  while read hash; do
    echo "Verifying: $hash"
    # Check if hash matches computed state
  done
```

---

## 🎯 Series B Demo

### Complete Demo (10 minutes)

```bash
# 1. Show services running
docker ps

# 2. Test Vision API governance decision
curl -X POST http://localhost:8000/v1/govern \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "demo-001",
    "action": "read",
    "blast_radius": 0.3,
    "user_id": "investor",
    "app_id": "demo",
    "human_approved": false
  }'
# Show: approved decision + Merkle proof

# 3. Show Dashboard
# Open: http://localhost:3000
# Navigate: Governance Dashboard → Security View → Creator Platform

# 4. Show Health Monitoring
./healthcheck.sh once
# Show: All 6 services healthy

# 5. Show Prometheus Metrics
# Open: http://localhost:9090
# Query: rate(http_requests_total[5m])

# 6. Show Jaeger Traces
# Open: http://localhost:16686
# Show latency breakdown per service
```

---

## 📞 Support

**Emergency Contacts:**
- Health monitoring: `tail -f /var/log/sovereign/healthcheck.log`
- Docker logs: `docker logs <container-id>`
- Manual rollback: `./rollback.sh`

**Deployment Verification Checklist:**
- [ ] All 6 services running (docker ps)
- [ ] Health check loop active (./healthcheck.sh)
- [ ] Prometheus scraping metrics (http://localhost:9090)
- [ ] Jaeger collecting traces (http://localhost:16686)
- [ ] EXEC_LOG.json recording snapshots
- [ ] Rollback.sh executable and tested

---

**Deployment Date:** July 31, 2026  
**Next Review:** August 7, 2026  
**SLA Target:** 99.9% uptime
