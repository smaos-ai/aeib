# SovereignNexus Deployment Scenarios — Detailed Comparison

## Scenario Overview

| Dimension | Local Laptop | Docker Compose | AWS t3 (CPU) | AWS GPU | EKS | DO | GCP Run |
|-----------|--------------|------------------|--------------|---------|-----|----|---------| 
| **Cost/mo** | $0 | $0 | $60 | $420 | $200 | $54 | $70 |
| **Setup Time** | 1h | 2h | 30min | 1h | 2h | 45min | 1h |
| **Performance** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| **Scalability** | ❌ | ⚠️ Limited | ✅ Easy | ✅ Easy | ✅✅ Excellent | ✅ Good | ✅ Auto |
| **Uptime SLA** | None | 99.5% | 99.9% | 99.9% | 99.95% | 99.9% | 99.95% |
| **Best Use Case** | Dev testing | 24/7 baseline | KARP proof | Production-like | Phase 2 ready | Budget | Serverless |

---

## 1. LOCAL LAPTOP (RTX 4060 External GPU)

### Specifications
- **Hardware:** MacBook Pro + RTX 4060 8GB external GPU
- **Network:** Local (no cloud)
- **Cost:** $0 (assumes hardware owned)
- **Setup Time:** 1 hour

### Architecture
```
Local Machine (macOS)
├─ PostgreSQL (localhost:5432)
├─ Ollama (localhost:11434)
├─ Harness (localhost:8080)
└─ Direct monitoring (no Prometheus)
```

### Pros
- ✅ Zero cost
- ✅ Immediate testing
- ✅ Full control (no cloud dependencies)
- ✅ Fast iteration cycle
- ✅ No latency (local network)

### Cons
- ❌ Not production-ready
- ❌ Manual service management
- ❌ Single point of failure
- ❌ No monitoring/alerting
- ❌ Not 24/7 capable (need to manage manually)
- ❌ No horizontal scaling
- ❌ Cannot be accessed remotely

### Setup Instructions
```bash
# 1. Install dependencies
brew install postgresql@15 ollama rust

# 2. Start services
brew services start postgresql@15
ollama serve &

# 3. Create database
createdb smaos_phase1
psql smaos_phase1 -c "CREATE EXTENSION vector;"

# 4. Load models
ollama pull qwen2.5:7b
ollama pull nomic-embed-text

# 5. Build and test
cargo build --release
cargo test --all

# 6. Run pilot
cargo run --release --bin pilot-hotel -- --iterations 100
```

### When to Use
- **Phase:** Development/Testing
- **Timeline:** Week 1 of pre-production (baseline validation)
- **Validation:** Quick proof-of-concept, <100 iterations

### Limitations for KARP
- ❌ Cannot run 24/7 (MacBook needs sleep)
- ❌ No uptime proof
- ❌ Not accessible to stakeholders
- ❌ Single-point failure (if laptop crashes, system down)

---

## 2. DOCKER COMPOSE (LOCAL)

### Specifications
- **Hardware:** Local development machine (Docker Desktop)
- **Containers:** 9 (harness + PostgreSQL + Ollama + monitoring + Vault + Redis + Jaeger + Prometheus + Grafana)
- **Network:** Docker bridge network (isolated)
- **Cost:** $0 (assumes hardware/Docker Desktop owned)
- **Setup Time:** 2 hours

### Architecture
```
Docker Host (Local or Cloud VM)
├── smaos-network (172.28.0.0/16)
│   ├─ harness (Rust)
│   ├─ postgresql (pgvector)
│   ├─ ollama (LLM)
│   ├─ freetoken (optimized)
│   ├─ prometheus (metrics)
│   ├─ grafana (dashboard)
│   ├─ jaeger (tracing)
│   ├─ vault (secrets)
│   └─ redis (cache)
└── Persistent volumes (models, database, checkpoints)
```

### Pros
- ✅ Zero cost
- ✅ Reproducible (exact same containers everywhere)
- ✅ Full monitoring (Prometheus + Grafana)
- ✅ Easy to version control (docker-compose.yml)
- ✅ Can run 24/7 (system restart policies)
- ✅ Horizontal scaling (docker-compose scale harness=3)
- ✅ Self-contained (all services in one file)
- ✅ Great for CI/CD testing

### Cons
- ⚠️ Requires Docker Desktop (~5GB)
- ⚠️ Limited horizontal scaling (single machine)
- ⚠️ No built-in HA (stateful services in containers)
- ⚠️ Performance depends on host (RTX 4060 on external GPU)
- ⚠️ Networking complexity (port conflicts)
- ❌ Not cloud-native (need VM to run on)

### Setup Instructions
```bash
# 1. Install Docker Desktop
# macOS: brew install --cask docker
# Ubuntu: curl https://get.docker.com | sh

# 2. Navigate to repo
cd /path/to/SovereignNexus

# 3. Build images
docker build -f Dockerfile.preproduction -t smaos/harness:latest .
docker build -f Dockerfile.freetoken -t smaos/freetoken:latest .

# 4. Create environment file
cat > .env.preproduction << 'EOF'
DB_PASSWORD=smaos-dev-unsafe
GRAFANA_PASSWORD=admin-unsafe
VAULT_TOKEN=dev-token-unsafe
EOF

# 5. Start stack
docker-compose -f docker-compose.preproduction.yml up -d

# 6. Wait for health (2-3 minutes)
docker-compose -f docker-compose.preproduction.yml ps

# 7. Verify services
curl http://localhost:8080/health  # Should return OK
curl http://localhost:9090/-/healthy  # Prometheus
curl http://localhost:3001/api/health  # Grafana
```

### Daily Operations
```bash
# View logs
docker-compose logs -f harness

# Run tests
docker exec smaos-harness cargo test --lib

# Monitor metrics
curl http://localhost:9090/api/v1/query?query=up

# Scale harness to 3 replicas
docker-compose up -d --scale harness=3

# Stop all (preserves data)
docker-compose down

# Stop and wipe (full reset)
docker-compose down -v
```

### When to Use
- **Phase:** Pre-production baseline (Sep 1-15)
- **Timeline:** 24/7 continuous operation
- **Validation:** Long-running stability test, 1000+ iterations
- **KARP Submission:** Primary evidence (system running >7 days)

### Why This for KARP
✅ **Perfect for Sep 16 submission because:**
- System running 24/7 for 7+ days
- Monitoring dashboards prove no downtime
- Proof artifacts (agentacct_ledger.json) continuous
- RAGAS score sustained > 87%
- Database growth tracked (no leaks)
- Easy to demo to stakeholders

### Cost Optimization
```
Sep-Dec 2026:
- Hardware (assume 16GB Mac owned): $0
- Docker Desktop: $0 (free tier for dev)
- Total: $0
```

---

## 3. AWS EC2 (Single VM, CPU-only, t3.medium)

### Specifications
- **Instance:** t3.medium (2 vCPU, 4GB RAM)
- **Storage:** 50GB gp3 SSD
- **Database:** Managed RDS PostgreSQL db.t3.micro (optional)
- **Cost:** $32/month (EC2) + $15/month (RDS) = $47/month
- **Setup Time:** 30 minutes
- **Region:** us-east-1 (closest to EU: eu-central-1, +$0.05/hour)

### Architecture
```
AWS VPC
├── EC2 Instance (t3.medium)
│   ├─ harness
│   ├─ prometheus
│   ├─ grafana
│   ├─ ollama (CPU-based, slow)
│   └─ local postgresql
├── RDS PostgreSQL (db.t3.micro, optional)
│   └─ pgvector enabled
├── Security Group
│   ├─ 22 (SSH)
│   ├─ 8080 (API)
│   ├─ 3001 (Grafana)
│   └─ 5432 (Database, if RDS public)
└── EBS Snapshots (backup)
```

### Pros
- ✅ Cheap ($32/month compute)
- ✅ Cloud-based (accessible from anywhere)
- ✅ Easy scaling (instance type change)
- ✅ Built-in backups (EBS snapshots)
- ✅ Monitoring (CloudWatch)
- ✅ Good for MVP/demo
- ✅ Can be accessed remotely (Grafana at public IP)

### Cons
- ⚠️ CPU-only inference (slow, 15 tok/sec vs 65 on GPU)
- ⚠️ Limited memory (4GB, tight for all services)
- ❌ Not suitable for high throughput
- ❌ Decision latency > 200ms (CPU bottleneck)
- ❌ RAGAS score may suffer (slower inference)
- ❌ No auto-scaling built-in
- ❌ Single point of failure (no HA)

### Setup Instructions
```bash
# 1. Create EC2 instance
# Console: EC2 → Launch Instance
# - AMI: Amazon Linux 2 (t3.medium)
# - Storage: 50GB gp3
# - Security Group: Allow 22, 8080, 3001

# 2. SSH into instance
ssh -i /path/to/key.pem ec2-user@<public-ip>

# 3. Install Docker
sudo yum update -y
sudo yum install -y docker docker-compose git
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ec2-user

# 4. Clone and deploy
git clone https://github.com/sovreignnexus/smaos.git
cd smaos
docker-compose -f docker-compose.preproduction.yml up -d

# 5. Monitor
docker-compose ps
curl http://localhost:8080/health
```

### When to Use
- **Phase:** Pre-production cloud validation (Sep 8-15)
- **Timeline:** Proof of cloud deployment
- **Validation:** KARP submission (shows system runs in cloud)

### Cost Estimate
```
Sep-Nov (3 months):
- EC2 t3.medium: $32/mo × 3 = $96
- RDS db.t3.micro: $15/mo × 3 = $45
- EBS snapshots: $5/mo × 3 = $15
- Data transfer: $5/mo × 3 = $15
TOTAL: $171

One-time:
- Data transfer out (first 1GB free): $0
```

### Limitations
- ⚠️ **Performance:** CPU-only inference is 4x slower than GPU
- ⚠️ **RAGAS Score:** May drop below 87% if latency > 5 seconds
- ❌ **Not suitable** for production pilots (Phase 2)

---

## 4. AWS EC2 (GPU Instance, g4dn.xlarge)

### Specifications
- **Instance:** g4dn.xlarge (4 vCPU, 16GB RAM, 1x NVIDIA T4 GPU)
- **Storage:** 100GB gp3 SSD
- **Cost:** $380/month (compute) + $15/month (RDS) = $395/month
- **Setup Time:** 1 hour
- **Performance:** 65+ tok/sec (3x faster than CPU)

### Architecture
```
AWS VPC (eu-central-1)
├── EC2 Instance (g4dn.xlarge)
│   ├─ GPU (NVIDIA T4, 16GB)
│   ├─ harness (Rust)
│   ├─ ollama (GPU-accelerated)
│   ├─ prometheus
│   └─ grafana
├── RDS Aurora PostgreSQL (optional)
│   └─ Multi-AZ replication
├── Load Balancer (ALB, optional)
└── CloudWatch (monitoring)
```

### Pros
- ✅ **Production-like performance** (65 tok/sec)
- ✅ RAGAS score > 87% maintained
- ✅ Decision latency < 100ms
- ✅ Can handle concurrent pilots
- ✅ GPU offloading ready for Phase 2
- ✅ Auto-scaling capable (launch template)
- ✅ Multi-region failover easy

### Cons
- ❌ **Expensive** ($380/month)
- ⚠️ Overkill for development
- ⚠️ GPU utilization low for small workloads
- ⚠️ Need nvidia-docker setup
- ⚠️ Spot instances 70% cheaper but can be interrupted

### Setup Instructions
```bash
# 1. Create EC2 instance
# - AMI: Deep Learning AMI (Ubuntu 22.04) — has drivers pre-installed
# - Type: g4dn.xlarge
# - Storage: 100GB gp3
# - Cost: $0.52/hour

# 2. SSH and verify GPU
nvidia-smi

# 3. Install nvidia-docker
# (Already installed in Deep Learning AMI)

# 4. Deploy
git clone https://github.com/sovreignnexus/smaos.git
cd smaos
docker-compose -f docker-compose.preproduction.yml up -d

# 5. Verify GPU utilization
docker logs smaos-harness | grep "tok/sec"
# Expected: 65+ tokens/sec
```

### Cost Optimization: Spot Instances
```bash
# Use Spot (70% cheaper)
# g4dn.xlarge Spot: $0.15/hour (vs $0.52 on-demand)
# Interruption rate: <5% acceptable for non-critical

# Auto-stop when not in use (nights/weekends)
# Cost: $0.15/hour × 10 hours/day × 20 business days = $30/month
```

### When to Use
- **Phase:** Pilot testing (Nov-Dec 2026)
- **Timeline:** Production-like validation
- **Validation:** 3 concurrent pilots (hotel, glass, school)

### Cost Estimate
```
Nov-Dec (2 months) with Spot + auto-stop:
- g4dn.xlarge Spot: $30/mo × 2 = $60
- RDS: $15/mo × 2 = $30
- Storage: $10/mo × 2 = $20
TOTAL: $110

Compared to on-demand:
- On-demand: $380/mo × 2 = $760
- Spot savings: $650/month
```

---

## 5. AWS EKS (Kubernetes, Production-Ready)

### Specifications
- **Cluster:** EKS (managed Kubernetes)
- **Nodes:** 2x t3.xlarge (8 vCPU, 32GB RAM each)
- **Database:** RDS Aurora PostgreSQL
- **Cost:** $73/month (cluster) + $250/month (compute) + $50/month (database) = $373/month
- **Setup Time:** 2 hours
- **High Availability:** Multi-AZ automatic failover

### Architecture
```
AWS EKS Cluster (eu-central-1)
├── Management Plane (AWS-managed)
│   └─ API Server, etcd, Scheduler
├── Worker Nodes (2x t3.xlarge)
│   ├─ Pod: smaos-harness (2 replicas)
│   ├─ Pod: postgresql-0 (StatefulSet)
│   ├─ Pod: prometheus
│   ├─ Pod: grafana
│   └─ Persistent Volumes (EBS)
├── Service Mesh (optional Istio)
│   └─ Traffic routing, circuit breaker
├── Ingress (ALB)
│   └─ External IP for Grafana/API
└── RDS Aurora PostgreSQL (multi-AZ)
```

### Pros
- ✅ **Production-ready** (Kubernetes standard)
- ✅ Auto-scaling (HPA based on CPU)
- ✅ Self-healing (auto-restart failed pods)
- ✅ Zero-downtime deployments
- ✅ Multi-region ready (Phase 2)
- ✅ Cost-efficient long-term (scale down at night)
- ✅ Industry standard (portability)

### Cons
- ⚠️ **Learning curve** (Kubernetes complexity)
- ⚠️ Overkill for Phase 1 (over-engineered)
- ⚠️ Debugging harder than Docker Compose
- ⚠️ Initial setup slower

### Setup Instructions
```bash
# 1. Create EKS cluster
aws eks create-cluster \
  --name smaos-phase1 \
  --version 1.28 \
  --role-arn arn:aws:iam::ACCOUNT_ID:role/eks-service-role \
  --resources-vpc-config subnetIds=subnet-xxxxx

# 2. Create node group
aws eks create-nodegroup \
  --cluster-name smaos-phase1 \
  --nodegroup-name smaos-nodes \
  --scaling-config minSize=2,maxSize=4,desiredSize=2 \
  --instance-types t3.xlarge

# 3. Configure kubectl
aws eks update-kubeconfig --region eu-central-1 --name smaos-phase1

# 4. Deploy applications
kubectl create -f kubernetes/smaos-namespace.yaml
kubectl create -f kubernetes/postgresql-statefulset.yaml
kubectl create -f kubernetes/smaos-harness-deployment.yaml
kubectl create -f kubernetes/monitoring-deployment.yaml

# 5. Verify
kubectl get pods -n smaos-prod
```

### When to Use
- **Phase:** Phase 2 (Jun-Dec 2026)
- **Timeline:** Multi-region active-active deployment
- **Validation:** Production infrastructure

### Cost Estimate
```
Jun-Dec (7 months):
- EKS cluster fee: $73/mo × 7 = $511
- 2x t3.xlarge: $0.33/hour × 2 × 730 = $483
- RDS Aurora: $50/mo × 7 = $350
- Data transfer: $10/mo × 7 = $70
TOTAL (7 months): $1,414 (~$202/month)

With auto-scaling (scale down nights):
- Estimated savings: 30% = $99/month saved
TOTAL: $1,316 (~$188/month)
```

---

## 6. DigitalOcean App Platform

### Specifications
- **Droplet:** 4GB RAM, 2 vCPU
- **Managed PostgreSQL:** Starter plan (1GB)
- **App Platform:** Containerized Node.js/Python
- **Cost:** $24/month (droplet) + $15/month (database) = $39/month
- **Setup Time:** 45 minutes

### Pros
- ✅ Cheapest managed cloud ($39/month)
- ✅ Simple YAML-based deployment
- ✅ Good documentation (developer-friendly)
- ✅ Built-in monitoring (Grafana)
- ✅ Good for MVPs

### Cons
- ⚠️ Smaller ecosystem (fewer tools than AWS)
- ⚠️ Less mature (AWS has more features)
- ⚠️ No GPU support (CPU-only)
- ⚠️ Limited auto-scaling options

### When to Use
- **Phase:** Cost-conscious pre-production
- **Timeline:** If budget is critical (<$50/month)

---

## 7. GCP Cloud Run

### Specifications
- **Compute:** Cloud Run (serverless)
- **Database:** Cloud SQL PostgreSQL
- **Cost:** $40/month (compute) + $20/month (database) = $60/month
- **Setup Time:** 1 hour

### Pros
- ✅ Serverless (pay-per-request)
- ✅ Auto-scaling (zero configuration)
- ✅ Simple deployment (gcloud push)
- ✅ Good for stateless services

### Cons
- ❌ **Cold start latency** (2-5 seconds first invocation)
- ❌ **Stateful services (database)** need external solution
- ⚠️ PostgreSQL on Cloud SQL more expensive
- ❌ Not ideal for continuous services (like harness)

### When to Use
- **Phase:** Not recommended for SMAOS (needs continuous running)
- **Alternative:** Use for stateless API layer only

---

## RECOMMENDATION FOR SMAOS PHASE 1

### Timeline & Strategy

**Sep 1-7 (Week 1): Local Docker Compose**
- **Goal:** Baseline validation, developer setup
- **Cost:** $0
- **Success Criteria:** 168 hours uptime, RAGAS > 87%

**Sep 8-15 (Week 2): AWS t3.medium + Docker Compose**
- **Goal:** Cloud deployment proof for KARP
- **Cost:** $60/month (Sep-Oct)
- **Success Criteria:** System accessible remotely, monitoring live

**Sep 16: KARP Submission**
- **Evidence:** System running 7+ days, all proof artifacts, RAGAS score
- **Cost:** Recover $62 via KARP voucher (120k CZK = ~$4.8k)

**Nov-Dec (Phase 1 pilots): AWS g4dn.xlarge Spot**
- **Goal:** Production-like pilot testing
- **Cost:** $30/month with Spot + auto-stop
- **Success Criteria:** 3 concurrent pilots, <100ms latency

**Phase 2 (Jun-Dec 2026): AWS EKS Multi-Region**
- **Goal:** Production-ready Prague + Frankfurt
- **Cost:** $200/month EKS cluster
- **Success Criteria:** Zero-downtime failover, 4000 concurrent pilots

### Total Cost (Sep 2026 - May 2027)

| Period | Scenario | Cost |
|--------|----------|------|
| Sep-Oct (pre-KARP) | Docker Compose + t3 | $120 |
| Nov-Dec (pilots) | g4dn.xlarge Spot | $60 |
| Jan-May (Phase 1) | t3.medium baseline | $300 |
| **TOTAL Phase 1** | | **$480** |
| **Less KARP grant** | -120k CZK (~$4,800) | **-$4,800** |
| **NET COST** | | **$(4,320) — paid back by grant** |

---

## DECISION MATRIX

**Choose Local Docker Compose if:**
- ✅ Need immediate development
- ✅ Budget is $0
- ✅ Testing < 7 days
- ✅ No remote access needed

**Choose AWS t3.medium if:**
- ✅ Need cloud proof for KARP
- ✅ Budget $60/month acceptable
- ✅ CPU-only acceptable
- ✅ Demo to stakeholders required

**Choose AWS g4dn.xlarge if:**
- ✅ Need production-like performance
- ✅ Running 3+ concurrent pilots
- ✅ RAGAS score critical
- ✅ Budget $30-60/month acceptable (Spot)

**Choose EKS if:**
- ✅ Phase 2 multi-region planned
- ✅ Production infrastructure needed
- ✅ Zero-downtime deployments required
- ✅ Long-term operation (amortized cost)

---

**Recommendation:** **Hybrid approach — Local Docker + AWS t3 for KARP + GPU Spot for pilots**

Total cost: $480 (covered by KARP grant)
Time to KARP ready: 15 days
Production-ready: Yes (Phase 2 EKS foundation)
