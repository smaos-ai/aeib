# SovereignNexus Pre-Production Deployment Runbook
## SMAOS Phase 1 — Complete Infrastructure Guide

**Updated:** 2026-09-01  
**Phase:** Phase 1 (Sep 1, 2026 - May 31, 2027)  
**Goal:** Validate system in pre-production before KARP submission (Sep 16) and Series A (Oct 1)

---

## 1. EXECUTIVE SUMMARY

### Mission
Deploy SovereignNexus (8-layer SMAOS governance harness) into pre-production for validation before:
- **Sep 16-22:** KARP submission (Czech government funding, 120k CZK)
- **Oct 1:** Series A outreach (proof-of-working-system required)
- **Nov 1:** 3 pilot execution (hotel/glass/school)

### Recommended Approach
**Hybrid: Local Docker Compose + AWS EC2 (Single VM)**

| Scenario | Cost | Setup Time | When to Use | Scalability |
|----------|------|-----------|-------------|-------------|
| **Local Laptop (RTX 4060)** | $0 | 1 hour | Immediate testing, developer loop | No |
| **Docker Compose (Local)** | $0 | 2 hours | 24/7 stability test, CI/CD template | Moderate |
| **AWS EC2 t3.medium (CPU)** | ~$30/mo | 30 min | Quick cloud validation, cost-effective | Yes |
| **AWS g4dn.xlarge (GPU)** | ~$500/mo | 1 hour | Production-like performance | Yes |
| **Kubernetes (EKS)** | ~$100/mo cluster + compute | 2 hours | Production-ready, multi-region prep | Excellent |

### Implementation Timeline
- **Sep 1-5:** Local Docker Compose running 24/7 (baseline)
- **Sep 5-10:** AWS EC2 instance live (cloud validation)
- **Sep 10-15:** Monitoring dashboards + alerts working
- **Sep 16:** KARP submission with proof (system running 7+ days)

### Cost Breakdown (Sep-Dec 2026)
| Component | Local | Docker | AWS t3 | AWS GPU | Kubernetes |
|-----------|-------|--------|--------|---------|-----------|
| **Compute** | $0 | $0 | $30 | $500 | $100 |
| **Database** | $0 | $0 | $15 | $15 | $50 |
| **Storage** | $0 | $0 | $10 | $10 | $20 |
| **Bandwidth** | $0 | $0 | $5 | $5 | $10 |
| **Monitoring** | $0 | $0 | $0 | $0 | $20 |
| **TOTAL/mo** | **$0** | **$0** | **~$60** | **~$530** | **~$200** |

---

## 2. ARCHITECTURE OVERVIEW

### SMAOS L1-L8 Stack

```
Request
  ↓
[L1: Policy Router] — Article 50 enforcement
  ↓
[L2: Knowledge Graph] — PostgreSQL + pgvector + BM25
  ↓
[L3: Permit Gates] — Article 37 / Annex III enforcement
  ↓
[L4: LangGraph Orchestration] — Checkpoints + determinism
  ↓
[L5: MCP Communication] — Agent-to-agent messaging
  ↓
[L6: Infrastructure Check] — Hardware validation (FreeToken/Ollama)
  ↓
[L7: RAGAS Evaluation] — Quality scoring (87%+ target)
  ↓
[L8: Proof Layer] — Ed25519 signatures + AP2 ledger
  ↓
Audit Trail (immutable)
```

### Container Architecture

```
┌─────────────────────────────────────────────────────┐
│ Pre-Production Stack (docker-compose.preproduction) │
├─────────────────────────────────────────────────────┤
│                                                     │
│ Application Layer:                                  │
│  ├─ smaos-harness (L1-L8, Rust, port 8080)        │
│  ├─ prometheus (metrics, port 9090)                │
│  ├─ grafana (dashboard, port 3001)                 │
│  └─ jaeger (tracing, port 16686)                  │
│                                                     │
│ Model Serving Layer:                                │
│  ├─ ollama (local inference, port 11434)           │
│  └─ freetoken (optimized LLM, port 8001)           │
│                                                     │
│ Storage Layer:                                      │
│  ├─ postgresql (pgvector, port 5432)               │
│  ├─ redis (cache, port 6379)                       │
│  └─ vault (secrets, port 8200)                     │
│                                                     │
│ Network: 172.28.0.0/16 (isolated bridge)           │
│ Volumes: Persistent storage for models + database  │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## 3. DEPLOYMENT SCENARIOS

### Scenario A: Local Laptop (RTX 4060)

**Use case:** Immediate validation, developer testing  
**Setup time:** 1 hour  
**Hardware:** MacBook Pro + RTX 4060 external GPU  

**Steps:**
```bash
# 1. Install dependencies
brew install postgresql@15 ollama docker rust
brew services start postgresql@15

# 2. Create database
createdb smaos_phase1
psql smaos_phase1 -c "CREATE EXTENSION vector;"

# 3. Load models (one-time, ~2GB)
ollama pull qwen2.5:7b
ollama pull nomic-embed-text

# 4. Build and run
cargo build --release
cargo test --all  # 228 tests, ~3 minutes
cargo run --release --bin pilot-hotel -- --iterations 100
```

**Monitoring:**
```bash
# Watch decisions in real-time
tail -f ./logs/hotel_decisions.json | jq '.[] | {decision_id, latency_ms, result}'

# Check proof layer
tail -f ./logs/agentacct_ledger.json | jq '.proofs[-1] | {decision_id, verified}'
```

**Limitations:**
- Single process (no container isolation)
- Manual service management
- No horizontal scaling
- Not suitable for 24/7 operation

---

### Scenario B: Docker Compose (Local)

**Use case:** Reproducible local testing, 24/7 stability validation  
**Setup time:** 2 hours  
**Requirements:** Docker Desktop 4.0+, 32GB RAM recommended, RTX 4060+  

**Steps:**
```bash
# 1. Clone/navigate to repo
cd /Users/andriileukhin/Documents/SovereignNexus

# 2. Set environment variables
cat > .env.preproduction << 'EOF'
DB_PASSWORD=smaos-dev-unsafe  # Change this!
GRAFANA_PASSWORD=admin-unsafe
VAULT_TOKEN=dev-token-unsafe
EOF

# 3. Build Docker images
docker build -f Dockerfile.preproduction -t smaos/harness:latest .
docker build -f Dockerfile.freetoken -t smaos/freetoken:latest .

# 4. Start full stack
docker-compose -f docker-compose.preproduction.yml up -d

# 5. Wait for services to be ready (2-3 minutes)
docker-compose -f docker-compose.preproduction.yml ps
# Expected: All services running (green)

# 6. Run initial tests
docker exec smaos-harness cargo test --lib --all
```

**Verify System Running:**
```bash
# Check all containers
docker-compose -f docker-compose.preproduction.yml ps

# Expected output:
# NAME                  STATUS
# smaos-postgresql      Up (healthy)
# smaos-harness         Up (healthy)
# smaos-ollama          Up (healthy)
# smaos-prometheus      Up
# smaos-grafana         Up
# smaos-jaeger          Up
# smaos-vault           Up
# smaos-redis           Up
```

**Access Services:**
```
API:         http://localhost:8080
Prometheus:  http://localhost:9090
Grafana:     http://localhost:3001 (admin/admin-unsafe)
Jaeger:      http://localhost:16686
Database:    localhost:5432 (smaos/smaos-dev-unsafe)
```

**Monitor & Test:**
```bash
# 1. Check harness health
curl http://localhost:8080/health

# 2. Run a pilot (hotel credit decision)
docker exec smaos-harness \
  /app/bin/pilot-hotel --iterations 10 --langsmith-trace

# 3. Watch metrics
curl http://localhost:9090/api/v1/query?query=up

# 4. View Grafana dashboard
# Open http://localhost:3001 → Home → Create dashboard
# Add panels:
#   - Decision Latency (p50, p99)
#   - Checkpoint Rate
#   - RAGAS Score
#   - Proof Generation Success

# 5. Check logs
docker logs -f smaos-harness | grep -E "decision|checkpoint|proof"
```

**Scaling:**
```bash
# Scale harness to 3 replicas (simulates load balancer)
docker-compose -f docker-compose.preproduction.yml up -d --scale harness=3

# Monitor across instances
docker logs smaos-harness_1 smaos-harness_2 smaos-harness_3 -f
```

**24/7 Stability Test (for KARP):**
```bash
# Run system for 7 days continuously
# Monitor:
#   - Memory leaks (docker stats)
#   - Database growth (SELECT pg_size_pretty(pg_database_size(current_database())))
#   - Proof chain continuity (tail agentacct_ledger.json)
#   - Error rates (docker logs smaos-harness | grep -i error)

# Automated check (run every 6 hours)
*/6 * * * * docker-compose -f docker-compose.preproduction.yml ps | grep -v "Up" && alert
```

---

### Scenario C: AWS EC2 (Single VM, CPU-only)

**Use case:** Cloud validation without GPU, cost-effective baseline  
**Setup time:** 30 minutes  
**Cost:** ~$30-60/month  
**Best for:** KARP submission proof, Series A demo (slower but working)  

**AWS Setup:**
```bash
# 1. Create EC2 instance (t3.medium)
# - Type: t3.medium (2 vCPU, 4GB RAM)
# - Storage: 50GB gp3 SSD
# - Security Group: Allow 22 (SSH), 8080 (API), 3001 (Grafana)
# - Cost: ~$0.044/hour * 730 hours = ~$32/month

# 2. SSH into instance
ssh -i /path/to/key.pem ec2-user@<instance-ip>

# 3. Install dependencies (Amazon Linux 2)
sudo yum update -y
sudo yum install -y docker docker-compose git

# Start Docker daemon
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ec2-user

# 4. Clone repository
git clone https://github.com/sovreignnexus/smaos.git
cd smaos

# 5. Set environment
cp .env.production .env
# Edit .env for cloud (change DB_PASSWORD, VAULT_TOKEN)

# 6. Start services (without GPU, slower inference)
export COMPOSE_FILE=docker-compose.preproduction.yml
docker-compose up -d

# 7. Monitor (should take 2-3 minutes to be ready)
docker-compose ps
docker-compose logs -f harness
```

**Provision RDS (Optional, for separation):**
```bash
# Create managed PostgreSQL on RDS
# Type: PostgreSQL 15.2
# Instance: db.t3.micro (1vCPU, 1GB RAM)
# Storage: 20GB gp3 (auto-scaling)
# Cost: ~$0.017/hour = ~$12/month

# Update DATABASE_URL in harness:
DATABASE_URL=postgresql://smaos:PASSWORD@smaos-db.xxxxx.rds.amazonaws.com:5432/smaos_phase1

# Create pgvector extension
psql -U smaos -h smaos-db.xxxxx.rds.amazonaws.com -d smaos_phase1 \
  -c "CREATE EXTENSION vector;"
```

**Access from anywhere:**
```bash
# Harness API
curl http://<ec2-ip>:8080/health

# Grafana Dashboard
open http://<ec2-ip>:3001

# SSH tunnel for local database access
ssh -i key.pem -L 5432:localhost:5432 ec2-user@<ec2-ip>
psql -U smaos -h localhost smaos_phase1
```

**Backup Strategy:**
```bash
# Daily database snapshot
aws rds create-db-snapshot \
  --db-instance-identifier smaos-db \
  --db-snapshot-identifier smaos-db-backup-$(date +%Y%m%d)

# Keep last 7 days
aws rds describe-db-snapshots --query 'DBSnapshots[?DBInstanceIdentifier==`smaos-db`].DBSnapshotIdentifier' \
  | jq -r '.[] | select(. < (now - 7*86400))'
```

---

### Scenario D: AWS EC2 (GPU Instance)

**Use case:** Production-like performance, full pre-production validation  
**Setup time:** 1 hour  
**Cost:** ~$500-700/month for g4dn.xlarge  
**Performance:** RTX A100 equivalent, 100+ tok/s  

**AWS Setup:**
```bash
# 1. Create EC2 instance (g4dn.xlarge)
# - Type: g4dn.xlarge (4vCPU, 16GB RAM, 1x NVIDIA T4 GPU)
# - AMI: Deep Learning AMI (Ubuntu 22.04) — has NVIDIA drivers pre-installed
# - Storage: 100GB gp3 SSD
# - Cost: ~$0.52/hour = ~$380/month compute + storage

# 2. SSH and verify GPU
nvidia-smi
# Expected: NVIDIA T4 GPU, CUDA 12.0+

# 3. Install Docker + GPU support
sudo apt update && sudo apt install -y docker.io
curl https://get.docker.com/builds/Linux/x86_64/docker-compose-Linux-x86_64 \
  -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Install nvidia-docker
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt update && sudo apt install -y nvidia-docker2
sudo systemctl restart docker

# 4. Verify GPU in Docker
docker run --rm --gpus all nvidia/cuda:12.2-runtime-ubuntu22.04 nvidia-smi

# 5. Clone and deploy
git clone https://github.com/sovreignnexus/smaos.git && cd smaos
docker-compose -f docker-compose.preproduction.yml up -d

# 6. Monitor inference performance
docker logs -f smaos-harness | grep -E "tok/sec|latency"
# Expected: 65+ tokens/sec (vs 15 on CPU)
```

**Cost Optimization:**
```bash
# Use Spot Instances (70% cheaper)
# Launch g4dn.xlarge Spot instance (~$0.15/hour)
# Interruption risk: <5%, acceptable for dev/staging

# Auto-stop when not in use (e.g., nights/weekends)
# Using AWS Lambda + EventBridge:
# - Stop at 18:00 UTC (save $0.26/day)
# - Start at 08:00 UTC (ready for business hours)

# Estimated monthly cost with Spot + auto-stop:
# $0.15/hour * 10 hours/day * 20 business days = ~$30/month
```

---

### Scenario E: Kubernetes (EKS)

**Use case:** Production-ready, multi-region ready, horizontal scaling  
**Setup time:** 2 hours  
**Cost:** ~$200/month (EKS cluster fee + 1-2 nodes)  
**Best for:** Long-term production, Phase 2 multi-region foundation  

**AWS EKS Setup:**
```bash
# 1. Create EKS cluster
aws eks create-cluster \
  --name smaos-phase1 \
  --version 1.28 \
  --role-arn arn:aws:iam::ACCOUNT_ID:role/eks-service-role \
  --resources-vpc-config subnetIds=subnet-xxxxx,subnet-xxxxx,securityGroupIds=sg-xxxxx

# Cost: ~$0.10/hour = ~$73/month cluster fee

# 2. Create managed node group (t3.xlarge, 2 nodes)
# Cost: ~$0.25/hour * 2 = ~$364/month compute
# Total EKS: ~$437/month

# 3. Configure kubectl
aws eks update-kubeconfig --region us-east-1 --name smaos-phase1

# 4. Deploy applications
kubectl create -f kubernetes/smaos-namespace.yaml
kubectl create -f kubernetes/postgresql-statefulset.yaml
kubectl create -f kubernetes/smaos-harness-deployment.yaml
kubectl create -f kubernetes/monitoring-deployment.yaml

# 5. Verify deployment
kubectl get pods -n smaos-prod
# Expected: postgresql-0, smaos-harness-xxx, smaos-harness-yyy (2 replicas)

# 6. Access services
kubectl port-forward -n smaos-prod svc/smaos-harness 8080:8080
kubectl port-forward -n smaos-monitoring svc/grafana 3001:3000
```

**Kubernetes Advantages:**
- Auto-scaling: Scale up/down based on CPU (HPA)
- Multi-region: Easy deployment to Frankfurt + Prague
- Self-healing: Auto-restart failed pods
- Updates: Zero-downtime rolling updates
- Cost: Pay-per-second, no unused instances

**Kubernetes Challenges:**
- Learning curve (kubectl, manifests, YAML)
- Debugging complexity (pod logs, network policies)
- Cost monitoring (easy to over-provision)

**Recommended for Phase 2 (Jun-Dec 2026):**
```
Prague (Primary EKS)         Frankfurt (Secondary EKS)
├─ 2x g4dn.xlarge           ├─ 2x g4dn.xlarge
├─ RDS Aurora PostgreSQL    ├─ RDS Aurora PostgreSQL
└─ NLB load balancer        └─ NLB load balancer
   ↓ Active-active replication ↓
   Zone failover in 2 seconds (zero RTO/RPO)
```

---

## 4. MONITORING & OBSERVABILITY

### Key Metrics to Track

**L1-L3 Policy Pipeline:**
```
smaos_l1_policy_routes_total       — Request rate through policy router
smaos_l2_knowledge_queries_total   — Knowledge graph queries per second
smaos_l3_permit_decisions_total    — Gate decisions (approve/deny)
```

**L4-L5 Orchestration & Communication:**
```
smaos_l4_checkpoints_total         — Checkpoints captured (target: 1000/test)
smaos_l5_mcp_messages_total        — Inter-agent messages
smaos_l5_message_latency_ms        — Communication latency
```

**L6-L7 Infrastructure & Evaluation:**
```
smaos_l6_hardware_utilization      — GPU/CPU/Memory usage
smaos_l7_ragas_avg_score           — Quality metric (target: 87%+)
smaos_l7_evaluation_duration_ms    — Evaluation latency
```

**L8 Proof Layer:**
```
smaos_l8_proofs_generated_total    — Proofs per decision
smaos_l8_signature_verify_total    — Successful Ed25519 verification
smaos_l8_ledger_entries_total      — Immutable ledger size
```

**Infrastructure Metrics:**
```
postgres_connection_pool_available — DB connection pool health
ollama_model_latency_ms            — Model inference latency
container_memory_usage_bytes       — Container memory (watch for leaks)
container_cpu_usage_seconds_total  — CPU utilization across replicas
```

### Grafana Dashboard Setup

**Import Dashboard:**
```bash
# 1. Access Grafana at http://localhost:3001
# 2. Admin → Settings → Provisioning → Dashboards
# 3. Create file: grafana/provisioning/dashboards/smaos-main.json
```

**Key Panels:**
```json
{
  "title": "SovereignNexus L1-L8 Pipeline",
  "panels": [
    {
      "title": "Decision Latency (ms)",
      "targets": [
        "histogram_quantile(0.50, rate(smaos_decision_latency_ms_bucket[5m]))",
        "histogram_quantile(0.99, rate(smaos_decision_latency_ms_bucket[5m]))"
      ]
    },
    {
      "title": "Checkpoint Capture Rate",
      "targets": ["rate(smaos_l4_checkpoints_total[1m])"]
    },
    {
      "title": "RAGAS Score Trend",
      "targets": ["smaos_l7_ragas_avg_score"]
    },
    {
      "title": "Proof Generation Success",
      "targets": ["rate(smaos_l8_proofs_generated_total[5m])"]
    },
    {
      "title": "Database Latency (p99)",
      "targets": ["histogram_quantile(0.99, rate(pg_query_duration_seconds_bucket[5m]))"]
    },
    {
      "title": "GPU Memory Usage",
      "targets": ["nvidia_smi_memory_used_mb"]
    }
  ]
}
```

### Alert Rules

**Create:** `prometheus/alert_rules.yml`

```yaml
groups:
- name: smaos_alerts
  interval: 30s
  rules:
  - alert: HighDecisionLatency
    expr: histogram_quantile(0.99, rate(smaos_decision_latency_ms_bucket[5m])) > 1000
    for: 5m
    annotations:
      summary: "Decision latency p99 > 1s ({{ $value }}ms)"

  - alert: LowCheckpointRate
    expr: rate(smaos_l4_checkpoints_total[1m]) < 0.1
    for: 2m
    annotations:
      summary: "Checkpoint capture < 0.1/sec"

  - alert: RAGASScoreLow
    expr: smaos_l7_ragas_avg_score < 0.87
    for: 10m
    annotations:
      summary: "RAGAS evaluation score below 87% target"

  - alert: DatabasePoolExhausted
    expr: postgres_connection_pool_available < 1
    for: 1m
    annotations:
      summary: "Database connection pool exhausted"

  - alert: GPUMemoryHigh
    expr: nvidia_smi_memory_used_mb > 7500  # 8GB GPU, 94% utilization
    for: 2m
    annotations:
      summary: "GPU memory usage > 94%"

  - alert: ContainerCrashLoop
    expr: rate(container_last_seen{job="docker"}[5m]) < 0
    for: 1m
    annotations:
      summary: "Container {{ $labels.name }} crashing"
```

---

## 5. PRE-PRODUCTION CHECKLIST

### Week 1 (Sep 1-7): Setup & Baseline

- [ ] **Docker Compose running locally**
  - [ ] All 9 containers healthy (docker-compose ps)
  - [ ] Harness API responding (curl http://localhost:8080/health)
  - [ ] Database initialized with pgvector extension
  - [ ] Models loaded (ollama list → qwen2.5:7b present)

- [ ] **Initial tests passing**
  - [ ] 228 tests pass locally (cargo test --lib)
  - [ ] Load test 100 iterations, 100% success
  - [ ] Avg latency < 100ms recorded

- [ ] **Monitoring operational**
  - [ ] Prometheus scraping harness metrics
  - [ ] Grafana dashboard accessible
  - [ ] Jaeger traces visible for L5 communication

- [ ] **System running 24/7**
  - [ ] Docker Compose restart policies set to `always`
  - [ ] System survives pod/container restart
  - [ ] No memory leaks after 1 hour (docker stats)

### Week 2 (Sep 8-14): Cloud Deployment

- [ ] **AWS EC2 running**
  - [ ] Instance created (t3.medium or g4dn.xlarge)
  - [ ] Docker services deployed
  - [ ] Services accessible via security group

- [ ] **Database backups operational**
  - [ ] Daily snapshots scheduled (AWS Lambda + EventBridge)
  - [ ] Backup restoration tested (restore → verify data)
  - [ ] Encryption enabled (at-rest and in-transit)

- [ ] **Monitoring alerts active**
  - [ ] Prometheus alert rules loaded
  - [ ] Alert notifications configured (email/Slack)
  - [ ] Test alert: trigger one, verify notification

- [ ] **Load testing completed**
  - [ ] 1000 iteration test, 100% success rate
  - [ ] Latency p50 < 50ms, p99 < 200ms
  - [ ] RAGAS score 87%+ maintained under load
  - [ ] All 7 proof artifacts generated + verified

### Week 3 (Sep 15-21): Hardening & KARP Prep

- [ ] **Security hardened**
  - [ ] Database password changed (not dev-unsafe)
  - [ ] Vault secrets rotated
  - [ ] CORS origins whitelisted (not *)
  - [ ] TLS enabled for inter-container communication
  - [ ] Secrets not in logs (grep -r "password" ./logs)

- [ ] **Performance benchmarked**
  - [ ] Decision latency < 100ms recorded (L1→L8)
  - [ ] Throughput 1000+ decisions/hour documented
  - [ ] Model inference speed (tok/sec) baseline taken
  - [ ] Database latency < 10ms (pgvector queries)

- [ ] **Proof layer validated**
  - [ ] All 7 proof artifacts present:
    - [ ] hotel_l1_to_l8.json (3663 checkpoints)
    - [ ] glass_l1_to_l8.json (2997 checkpoints)
    - [ ] school_l1_to_l8.json (3006 checkpoints)
    - [ ] canirun_hardware.json
    - [ ] freetoken_benchmark.json
    - [ ] is_agentic_report.json
    - [ ] ragas_golden_set.json
  - [ ] All proofs Ed25519-signed
  - [ ] Signature verification passed

- [ ] **Annex IV dossier complete**
  - [ ] All 9 sections auto-populated
  - [ ] PDF generated + KMS-signed
  - [ ] KARP submission package ready

- [ ] **System uptime verified**
  - [ ] 168+ hours continuous runtime (7 days)
  - [ ] Zero unplanned restarts
  - [ ] Database size growth < 10GB
  - [ ] Log rotation working (no disk full)

### Week 4-12 (Sep 22 - May 31): Operations & Scaling

- [ ] **Pilot execution ready**
  - [ ] 3 pilots testable in sandbox mode
  - [ ] Blast radius isolation verified
  - [ ] Network policies enforcing isolation

- [ ] **Multi-region preparation (Phase 2)**
  - [ ] Kubernetes manifests created + tested
  - [ ] EKS cluster blueprint documented
  - [ ] Database replication strategy defined
  - [ ] Failover RTO/RPO targets (< 2 seconds)

- [ ] **Cost optimization**
  - [ ] Reserved instances purchased (long-term discount)
  - [ ] Auto-scaling policies configured
  - [ ] Spot instances evaluated for non-critical workloads
  - [ ] Budget alerts set in AWS Billing

---

## 6. OPERATIONAL PROCEDURES

### Daily Health Check

```bash
# Run this every morning (or via cron)
#!/bin/bash

# Docker Compose checks
docker-compose -f docker-compose.preproduction.yml ps | grep "Up"

# API health
curl -s http://localhost:8080/health | jq .

# Database check
psql -U smaos -h localhost -d smaos_phase1 \
  -c "SELECT COUNT(*) as decisions FROM smaos.decisions WHERE created_at > NOW() - INTERVAL '24 hours';"

# Disk space
df -h | grep -E "ssd|root" | awk '{if ($5 > 80) print "WARNING: Disk " $5 " full"}'

# Container resource usage
docker stats --no-stream | awk 'NR>1 {print $1": " $3 " CPU, " $4 " MEM"}'

# Proof layer continuity
tail -1 ./logs/agentacct_ledger.json | jq '.proofs[-1] | {decision_id, timestamp, verified}'
```

### Weekly Maintenance

**Backup:**
```bash
# Full system backup
./scripts/backup_smaos.sh

# Expected: 500MB-1GB backup (database + logs + proofs)
# Keep for 30 days
```

**Performance Analysis:**
```bash
# Query slow logs
psql -U smaos -d smaos_phase1 \
  -c "SELECT query, mean_exec_time FROM pg_stat_statements WHERE mean_exec_time > 100 ORDER BY mean_exec_time DESC LIMIT 10;"

# Check for n+1 queries (L2 knowledge retrieval)
```

**Log Rotation:**
```bash
# Rotate Docker logs (daily)
logrotate -f /etc/logrotate.d/docker-smaos

# Archive old checkpoints (weekly)
find ./logs -name "*.json" -mtime +30 -exec gzip {} \;
```

### Incident Response

**Database Connection Pool Exhausted:**
```bash
# 1. Identify long-running queries
psql -U smaos -d smaos_phase1 -c "SELECT pid, usename, query_start, query FROM pg_stat_activity WHERE state != 'idle';"

# 2. Kill if stuck
psql -U smaos -d smaos_phase1 -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid <> pg_backend_pid() AND query_start < NOW() - INTERVAL '1 hour';"

# 3. Increase pool size (in docker-compose.yml)
# DB_POOL_SIZE=20 → DB_POOL_SIZE=30

# 4. Restart harness
docker-compose restart harness
```

**High GPU Memory Usage:**
```bash
# 1. Check which layer is consuming
docker exec smaos-harness nvidia-smi

# 2. Reduce model size or batch size
export BATCH_SIZE=1
export MODEL_NAME=qwen2.5:3b  # Smaller variant

# 3. Restart Ollama
docker-compose restart ollama

# 4. Monitor recovery
docker exec smaos-ollama nvidia-smi --query-gpu=memory.used --format=csv,noheader
```

**Harness Crashes (Proof Signature Failure):**
```bash
# 1. Check error
docker logs smaos-harness | grep -i "signature\|ed25519" | tail -10

# 2. Regenerate Ed25519 keys
docker exec smaos-harness \
  /app/bin/keygen --algorithm ed25519-pqc --output-dir /var/lib/smaos/keys

# 3. Restart
docker-compose restart harness

# 4. Re-run load test (regenerate all proofs)
docker exec smaos-harness \
  /app/bin/load_test --total 100 --regenerate-proofs
```

---

## 7. COST ESTIMATION

### Pre-Production (Sep-Nov 2026)

| Scenario | Compute | Database | Storage | Bandwidth | Total/month |
|----------|---------|----------|---------|-----------|------------|
| **Local (no cloud)** | $0 | $0 | $0 | $0 | **$0** |
| **Docker Compose** | $0 | $0 | $0 | $0 | **$0** |
| **AWS t3.medium** | $32 | $15 | $10 | $5 | **$62** |
| **AWS g4dn.xlarge** | $380 | $15 | $20 | $5 | **$420** |
| **AWS EKS (2x t3.xl)** | $273 | $50 | $30 | $10 | **$363** |
| **DigitalOcean App Plat** | $24 | $15 | $10 | $5 | **$54** |
| **GCP Cloud Run** | $40 | $20 | $5 | $5 | **$70** |

### Recommended Path (Hybrid)

**Sep-Oct:** Local Docker Compose ($0) + AWS t3.medium ($62) = **$62/month**
- Dev work continues locally (zero cost)
- Cloud baseline for KARP submission
- Total 3-month cost: $186

**Nov-Dec:** Scale to g4dn.xlarge for pilot testing = **$420/month**
- Production-like performance
- 3 pilots running concurrently
- Total 2-month cost: $840

**Total Sep-Dec cost: $1,026**

---

## 8. TROUBLESHOOTING

### Docker Issues

**"docker: not found"**
```bash
# Install Docker Desktop (macOS/Windows) or Docker Engine (Linux)
# macOS: brew install docker
# After install, run: docker --version
```

**"Cannot connect to Docker daemon"**
```bash
# Start Docker daemon
# macOS: open -a Docker
# Linux: sudo systemctl start docker
# Windows: Docker Desktop app
```

**"docker-compose command not found"**
```bash
# Update Docker (includes compose v2)
docker -v  # Should be 20.10+

# Or install standalone:
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
```

### Database Issues

**"psql: error: FATAL: remaining connection slots reserved for non-replication superuser connections"**
```bash
# Database connection limit reached
# Check open connections:
psql -U postgres -c "SELECT COUNT(*) FROM pg_stat_activity;"

# Kill idle connections:
psql -U postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle' AND duration > '10 minutes';"

# Increase max_connections in postgresql.conf:
max_connections = 200  # Increase from 100
```

**"pgvector extension not found"**
```bash
# Ensure pgvector/pgvector Docker image is used (not plain postgres)
# In docker-compose.preproduction.yml:
image: pgvector/pgvector:pg15-latest  # NOT just postgres:15

# Restart:
docker-compose restart postgresql
```

### Model Serving Issues

**"Ollama model not loaded"**
```bash
# Check Ollama status
curl http://localhost:11434/api/tags

# If empty, pull model:
docker exec smaos-ollama ollama pull qwen2.5:7b

# Verify it loaded:
docker exec smaos-ollama ollama list
```

**"Model inference timeout (> 30s)"**
```bash
# CPU-only inference is slow
# Solution 1: Use GPU (ensure nvidia-docker)
# Solution 2: Use smaller model
docker exec smaos-ollama ollama pull qwen2.5:3b

# Solution 3: Increase timeout in harness
export DECISION_TIMEOUT_MS=10000  # 10 seconds

docker-compose restart harness
```

### Monitoring Issues

**"Prometheus scrape failing"**
```bash
# Check targets:
curl http://localhost:9090/api/v1/targets

# If harness is DOWN, verify:
curl http://localhost:8080/metrics

# If blank, ensure harness exports metrics (ENABLE_PROMETHEUS_METRICS=true)
docker-compose restart harness
```

**"Grafana dashboard not loading"**
```bash
# Default credentials: admin / admin-unsafe
# If locked:
docker exec smaos-grafana grafana-cli admin reset-admin-password <new-password>

# Restart:
docker-compose restart grafana
```

---

## 9. SECURITY CHECKLIST

- [ ] **Secrets management**
  - [ ] DB_PASSWORD not in .env file (use .env.local, gitignored)
  - [ ] VAULT_TOKEN rotated monthly
  - [ ] Grafana admin password changed
  - [ ] API keys stored in Vault, not environment

- [ ] **Network security**
  - [ ] PostgreSQL port 5432 not exposed (internal network only)
  - [ ] API rate limiting enabled (100 req/min per IP)
  - [ ] CORS origins whitelist (not wildcard)
  - [ ] TLS enabled for inter-container communication

- [ ] **Data privacy**
  - [ ] No PII in logs (grep -r "name\|email\|phone" ./logs)
  - [ ] PostgreSQL columns encrypted (PII fields at-rest)
  - [ ] Database backups encrypted (AWS KMS)
  - [ ] Log retention < 90 days

- [ ] **Compliance**
  - [ ] GDPR: Data processing agreement with cloud provider
  - [ ] GDPR: Data subject rights (right to deletion) implemented
  - [ ] EU AI Act: Article 50 transparency (decision cited)
  - [ ] EU AI Act: Annex III/I rules enforced (L3 permit gates)

---

## 10. NEXT STEPS

### Before Sep 16 (KARP Submission)

1. **Complete Week 3 checklist** (security, performance, proofs)
2. **Generate Annex IV dossier** (9 sections, auto-filled)
3. **Package submission**:
   - 1-page Czech "Popis projektu" (see KARP_POPIS_PROJEKTU.md)
   - Proof artifacts (7 files)
   - System uptime report (168+ hours)
   - RAGAS 87%+ baseline
4. **Submit to Romana Cernikova** (romana.cernikova@karp-kv.cz)

### Before Oct 1 (Series A Outreach)

1. **Record system demo** (2-minute video)
   - Dashboard showing live decisions
   - Proof trail generation
   - RAGAS evaluation score
2. **Prepare data room**:
   - Deployment architecture diagram
   - Cost analysis (Sep-Dec)
   - Proof artifacts
   - Pilot feature matrix (hotel/glass/school)
3. **Schedule investor demos** (interactive system running)

### Before Nov 1 (Pilot Execution)

1. **Sandbox environment ready**
   - 3 isolated namespaces/networks
   - Blast radius containment
   - Resource limits per pilot
2. **Pilot deployment**
   - Hotel: Credit scoring workflow
   - Glass: Material compliance verification
   - School: Student safeguarding rules
3. **Monitor & iterate** (bug fixes, performance tuning)

---

## 11. APPENDIX

### Useful Commands

```bash
# System status
docker-compose -f docker-compose.preproduction.yml ps

# View logs (all services)
docker-compose logs -f

# View logs (single service)
docker logs -f smaos-harness

# Database access
psql -U smaos -h localhost -d smaos_phase1

# Run tests in container
docker exec smaos-harness cargo test --lib --all

# Check metrics
curl http://localhost:9090/api/v1/query?query=smaos_l7_ragas_avg_score

# Stop system
docker-compose down

# Stop and remove volumes (fresh start)
docker-compose down -v

# Rebuild images
docker-compose build --no-cache
```

### File Structure

```
SovereignNexus/
├── Dockerfile.preproduction         ← Production-optimized build
├── docker-compose.preproduction.yml ← Full stack orchestration
├── prometheus.yml                   ← Monitoring configuration
├── kubernetes/
│   ├── smaos-namespace.yaml
│   ├── postgresql-statefulset.yaml
│   ├── smaos-harness-deployment.yaml
│   └── monitoring-deployment.yaml
├── PRE_PRODUCTION_RUNBOOK.md        ← This document
└── logs/
    ├── hotel_decisions.json         ← Decision audit trail
    ├── agentacct_ledger.json        ← Proof ledger (Ed25519-signed)
    └── proofs/                      ← All 7 proof artifacts
```

### References

- SMAOS Architecture: `ARCHITECTURE.md`
- Phase 1 Deployment: `DEPLOYMENT.md`
- Pilot Workflows: `PILOTS_GUIDE.md`
- KARP Submission: `KARP_POPIS_PROJEKTU.md`
- Production (Phase 2): `MULTI_REGION_DEPLOYMENT.md`

---

**Document Version:** 1.0  
**Last Updated:** 2026-09-01  
**Author:** Andrei Leukhin (andrejlo123@gmail.com)  
**Status:** DRAFT → READY FOR REVIEW
