# SMAOS Phase 2B: Deployment Architecture & Infrastructure Design
**Deployment Timeline:** Weeks 1-12 (Parallel with spec execution)  
**Production Readiness:** Sep 30, 2027  
**Target Deployment Scale:** 50+ regional gateways by Q1 2028

---

## EXECUTIVE SUMMARY

Phase 2B deployment architecture enables SovereignNexus to scale from 3 pilot gateways (Phase 1) to 50+ regional deployments across EU (proprietary), US (open-source), and China (white-label). Infrastructure uses edge nodes (RTX 4060) + cloud auto-scaling with full regional autonomy and eventual consistency via Merkle-rooted AP2 ledgers.

**Key design principles:**
1. **Regional autonomy:** Each region can decide locally (no single point of failure)
2. **No cloud egress:** All models + data cached locally; zero external dependencies
3. **Byzantine fault tolerance:** 3-region consensus tolerates 1 corrupted region
4. **Cost scaling:** €6k–€10k/month per region (€18k–€30k for 3-region foundation)
5. **Disaster recovery:** Regional failover + eventual consistency resync

---

## 1. INFRASTRUCTURE LAYERS

### 1.1 Edge Node (L0: Hardware Tier)

**Purpose:** Local inference + decision execution (no cloud hops)

**Configuration (per region):**

```yaml
EdgeNode:
  hardware:
    gpu: "NVIDIA RTX 4060 (8GB VRAM)"
    cpu: "Intel i7-13700K (24 cores)"
    ram: "32GB DDR5"
    storage: "1TB NVMe (SSD)"
    bandwidth: "1Gbps uplink"
    
  performance_targets:
    inference_latency: "<100ms per decision"
    model_throughput: "38 decisions/sec (Qwen 14B)"
    embeddings_latency: "<50ms (pgvector local)"
    
  models_cached_locally:
    - qwen2.5-coder:14b        # Reasoning
    - mistral-nemo:12b         # Fast inference
    - llama2:7b                # Backup (lightweight)
    
  databases_local:
    - PostgreSQL + pgvector (100K embeddings)
    - Redis (decision cache, in-memory)
    - SQLite (audit log replica)
```

**Deployment Options:**

| Deployment | Hardware | Cost/mo | Latency | Suitable For |
|-----------|----------|---------|---------|-------------|
| **On-Prem Edge** | RTX 4060 + server | €200 | <100ms | EU enterprises (high security) |
| **AWS EC2** | p3.2xlarge (GPU) | €3k–€4k | <150ms | US SaaS, freemium tier |
| **Alibaba Cloud** | ECS GPU instance | ¥3k–¥4k | <120ms | China partners |
| **Kubernetes Pod** | GPU resource req | €1k–€2k | <200ms | Multi-tenant SaaS |

### 1.2 Control Plane (L1: Kubernetes Cluster)

Each region deploys Kubernetes (EKS/AKS/ACK for cloud) or on-prem K3s:

```yaml
KubernetesCluster:
  # Service mesh
  istio:
    traffic_management: true
    mutual_tls: true
    load_balancing:
      algorithm: "round-robin with health checks"
      timeout: "5s per request"
  
  # Namespaces
  namespaces:
    - sovereignnexus-core      # L1-L8 harness pods
    - sovereignnexus-gateway   # MCP consensus servers
    - sovereignnexus-ledger    # AP2 ledger replication
    - sovereignnexus-observability  # Prometheus + Jaeger
  
  # Workloads
  workloads:
    - harness_executor:        # L1-L8 harness (1-10 replicas)
        image: "sovereignnexus/harness:latest"
        resources:
          requests: "4 CPU, 8GB RAM"
          limits: "8 CPU, 16GB RAM"
        probes:
          liveness: "/health (30s)"
          readiness: "/ready (10s)"
    
    - consensus_gateway:       # MCP consensus_gateway:8005
        image: "sovereignnexus/consensus-gateway:latest"
        port: 8005
        tls: true
        resources:
          requests: "2 CPU, 4GB RAM"
          limits: "4 CPU, 8GB RAM"
    
    - ledger_sync:            # MCP ledger_sync:8006
        image: "sovereignnexus/ledger-sync:latest"
        port: 8006
        tls: true
        resources:
          requests: "2 CPU, 2GB RAM"
          limits: "4 CPU, 4GB RAM"

  # Auto-scaling
  horizontal_pod_autoscaling:
    harness_executor:
      min_replicas: 1
      max_replicas: 10
      target_cpu: 70%
      target_memory: 75%
      scale_up_window: 30s
      scale_down_window: 300s

  # Networking
  network_policies:
    - deny_all_ingress: true
    - allow_consensus_gateway: "from peer regions (TLS mTLS)"
    - allow_ledger_sync: "from peer regions (TLS mTLS)"
    - deny_external_egress: "block outbound except whitelisted APIs"

  # Storage
  persistent_volumes:
    ap2_ledger:
      size: "100Gi"
      storage_class: "fast-ssd"
      mount_path: "/var/lib/sovereignnexus/ap2"
      backup_schedule: "hourly snapshots"
    
    model_cache:
      size: "50Gi"
      storage_class: "fast-ssd"
      mount_path: "/var/lib/sovereignnexus/models"
      read_only: false
```

### 1.3 Data Layer (L2: PostgreSQL + Vector Database)

```yaml
DatabaseTier:
  postgresql:
    version: "15.4"
    deployed_as:
      - Managed: "AWS RDS Aurora (us-east-1)" for US
      - Managed: "Azure Database for PostgreSQL" for EU
      - Self-hosted: "Alibaba RDS for MySQL" for China (not PostgreSQL)
    
    extensions:
      - pgvector: "for semantic search (100K embeddings)"
      - pg_trgm: "for full-text search (BM25)"
      - uuid-ossp: "for distributed IDs"
    
    schemas:
      compliance_rules:
        table: "policy_rules"
        rows: "50K (regulatory documents indexed)"
        indexes:
          - policy_id, article, region
          - article_text_fulltext
      
      decisions_log:
        table: "decisions"
        rows: "1M+ per month"
        indexes:
          - decision_id, timestamp, region
      
      ap2_ledger:
        table: "ledger_entries"
        rows: "append-only, 10M+ per year"
        indexes:
          - ledger_id, merkle_root
      
      pilot_states:
        table: "checkpoint_state"
        rows: "10M checkpoints across 3 pilots"
        indexes:
          - decision_id, checkpoint_seq

  replication:
    eu_replica:
      primary: "on-prem PostgreSQL (Frankfurt DC)"
      replica: "AWS RDS (Frankfurt)"
      lag: "<1s"
    
    us_replica:
      primary: "AWS RDS Aurora (us-east-1)"
      replica: "AWS RDS (us-west-2)"
      lag: "<1s"
    
    china_replica:
      primary: "Alibaba RDS (Beijing)"
      replica: "Alibaba RDS (Shanghai)"
      lag: "<1s"
      note: "MySQL only (PostgreSQL not available in China)"

  performance:
    query_latency_p99: "<100ms"
    insert_throughput: "10k rows/sec"
    backup:
      frequency: "hourly snapshots"
      retention: "30 days"
      location: "region-local (no cross-border)"
```

### 1.4 Observability Stack (Prometheus + Jaeger + CloudWatch/ALiYun)

```yaml
ObservabilityStack:
  # Metrics (Prometheus)
  prometheus:
    scrape_interval: "15s"
    retention: "30 days"
    metrics:
      harness_metrics:
        - decision_latency_seconds (histogram)
        - decision_throughput_per_sec (gauge)
        - consensus_vote_latency (histogram)
        - ap2_ledger_append_time (gauge)
        - model_inference_latency (histogram)
      
      regional_metrics:
        - decisions_per_region_per_hour (counter)
        - consensus_agreement_rate (gauge: 0-100%)
        - merkle_proof_verification_failures (counter)
        - cross_region_message_latency (histogram)
  
  # Tracing (Jaeger)
  jaeger:
    otlp_receiver: "0.0.0.0:4317"
    storage_backend:
      eu: "Jaeger-operator on-prem (Frankfurt)"
      us: "AWS X-Ray (us-east-1)"
      china: "Alibaba SLS (Logging Service)"
    trace_sampling: "10% (1 in 10 requests)"
    retention: "7 days"

  # Logs (ELK / CloudWatch / ALiYun)
  logging:
    eu:
      backend: "Self-hosted ELK stack"
      log_level: "INFO"
      retention: "30 days"
    us:
      backend: "AWS CloudWatch"
      log_group: "/sovereignnexus/harness"
      retention: "7 days (cost optimized)"
    china:
      backend: "Alibaba SLS"
      project: "sovereignnexus-logging"
      retention: "7 days"

  # Alerting
  alerting:
    rules:
      - "Decision latency p99 >2s → Page on-call"
      - "Consensus disagreement >10% → Create incident"
      - "AP2 ledger append failures >0 → Block deployments"
      - "Cross-region message loss >1% → Investigate network"
      
  dashboards:
    - "Regional gateway health (4 regions × 6 metrics)"
    - "Decision latency histogram (p50/p95/p99)"
    - "Consensus voting tally (approve/reject/escalate)"
    - "AP2 ledger Merkle root verification"
    - "Model inference latency per model"
```

---

## 2. NETWORK TOPOLOGY & CONNECTIVITY

### 2.1 Inter-Region Communication (MCP Layer)

```
EU REGION                          US REGION                         CHINA REGION
(On-Prem Frankfurt DC)            (AWS us-east-1)                  (Alibaba Beijing)
│                                  │                                 │
├─ consensus_gateway:8005         ├─ consensus_gateway:8005        ├─ consensus_gateway:8005
│  └─ MCP port (TLS 1.3)          │  └─ MCP port (TLS 1.3)         │  └─ MCP port (TLS mTLS)
├─ ledger_sync:8006               ├─ ledger_sync:8006              ├─ ledger_sync:8006
│  └─ Merkle sync (TLS 1.3)       │  └─ Merkle sync (TLS 1.3)      │  └─ Merkle sync (TLS mTLS)
│                                  │                                 │
└─ IP: 10.0.1.0/24                └─ IP: 10.0.2.0/24               └─ IP: 10.0.3.0/24
   (private DC network)              (AWS VPC)                       (Alibaba VPC)
   
   │◄─── AWS Direct Connect (4Gbps) ──►│
   │         (low latency)                
   │
   └────────────── AWS Direct Connect + ExpressRoute ────────────►│
            (EU-US: <100ms, cross-Pacific: <150ms)

CONNECTIVITY RULES:
──────────────────
Source: EU consensus_gateway
Destination: US consensus_gateway:8005
Protocol: TLS 1.3 + mutual mTLS
Authentication: X.509 certs (pre-distributed)
Rate limit: 100 req/sec per peer (prevent DDoS)
Timeout: 5s (failed peer temporarily ignored)
Retry: Exponential backoff (1s, 2s, 4s, 8s, then circuit breaker)
Failover: If primary unavailable, use secondary region IP
Encryption: End-to-end (no decryption at intermediaries)
Audit: All messages logged to AP2 ledger locally

REGION-INTERNAL COMMUNICATION:
──────────────────────────────
Harness ↔ consensus_gateway: Unix socket (127.0.0.1:8005, no network latency)
Harness ↔ PostgreSQL: TCP (same VPC/DC, <10ms latency)
Harness ↔ Edge node (GPU): InfiniBand or ethernet (<1ms latency)
```

### 2.2 Network Security Policies (Kubernetes NetworkPolicy)

```yaml
NetworkPolicy:
  # 1. Deny all ingress by default
  default_deny_ingress:
    kind: NetworkPolicy
    metadata:
      name: deny-all-ingress
      namespace: sovereignnexus-core
    spec:
      podSelector: {}
      policyTypes:
        - Ingress
  
  # 2. Allow consensus_gateway ingress from peer regions
  allow_consensus_from_peers:
    kind: NetworkPolicy
    metadata:
      name: allow-consensus-peers
    spec:
      podSelector:
        matchLabels:
          app: consensus-gateway
      policyTypes:
        - Ingress
      ingress:
        - from:
            - namespaceSelector:
                matchLabels:
                  region: us
            - namespaceSelector:
                matchLabels:
                  region: china
          ports:
            - protocol: TCP
              port: 8005
  
  # 3. Deny egress (default)
  default_deny_egress:
    kind: NetworkPolicy
    metadata:
      name: deny-all-egress
    spec:
      podSelector: {}
      policyTypes:
        - Egress
  
  # 4. Allow egress to whitelisted APIs only
  allow_egress_whitelist:
    kind: NetworkPolicy
    metadata:
      name: allow-whitelisted-egress
    spec:
      podSelector:
        matchLabels:
          app: harness-executor
      policyTypes:
        - Egress
      egress:
        # Internal DNS + peer regions
        - to:
            - namespaceSelector: {}
          ports:
            - protocol: TCP
              port: 53  # DNS
        
        # PostgreSQL (internal)
        - to:
            - podSelector:
                matchLabels:
                  app: postgres
          ports:
            - protocol: TCP
              port: 5432
        
        # Peer region consensus_gateway (only)
        - to:
            - namespaceSelector:
                matchLabels:
                  region: us
          ports:
            - protocol: TCP
              port: 8005
        - to:
            - namespaceSelector:
                matchLabels:
                  region: china
          ports:
            - protocol: TCP
              port: 8005
        
        # Block all other egress
```

---

## 3. DEPLOYMENT SEQUENCING (COLIBRI ORCHESTRATOR)

Phase 2B uses **Colibri** (cost-optimized hardware orchestrator) to select hardware + cloud provider per region:

### 3.1 Week 1-2: Regional Kubernetes Setup

```bash
# Step 1: Provision base infrastructure (IaC with Terraform)
terraform init
terraform apply -target=aws_eks_cluster.us-east-1
terraform apply -target=alibabacloud_cs_kubernetes.beijing
terraform apply -target=self_hosted_k3s.frankfurt

# Step 2: Deploy Istio (service mesh)
helm repo add istio https://istio-release.storage.googleapis.com/charts
helm repo update
helm install istio-base istio/base -n istio-system --create-namespace
helm install istio-operator istio/istiod -n istio-system

# Step 3: Deploy observability stack
kubectl apply -f prometheus-stack.yaml
kubectl apply -f jaeger-operator.yaml
kubectl apply -f fluentd-daemonset.yaml

# Step 4: Configure network policies (deny all by default)
kubectl apply -f network-policies/
```

### 3.2 Week 3-4: Harness Deployment (L1-L8)

```bash
# Step 5: Build harness Docker image
docker build -f Dockerfile.harness -t sovereignnexus/harness:2b-v1 .
docker push gcr.io/sovereignnexus/harness:2b-v1

# Step 6: Deploy harness + consensus servers to each region
for REGION in eu us china; do
  kubectl set context $REGION
  kubectl apply -f harness-deployment-${REGION}.yaml
  kubectl rollout status deployment/harness-executor
  kubectl apply -f consensus-gateway-${REGION}.yaml
  kubectl apply -f ledger-sync-${REGION}.yaml
done

# Step 7: Verify regional connectivity (MCP handshakes)
./scripts/test_cross_region_connectivity.sh
```

### 3.3 Week 5-6: Data Layer Initialization

```bash
# Step 8: Initialize regional databases
for REGION in eu us china; do
  kubectl exec -it postgres-${REGION}-0 -- psql -c "
    CREATE EXTENSION pgvector;
    CREATE EXTENSION pg_trgm;
  "
done

# Step 9: Load regional policy rules (L2 knowledge graph)
psql -h eu-postgres.sovereignnexus.eu << EOF
\COPY policy_rules FROM 'data/eu_policies.csv' WITH CSV
CREATE INDEX ON policy_rules USING GIN (article_text);
SELECT COUNT(*) FROM policy_rules;  -- Should be ~50K
EOF

# Step 10: Initialize AP2 ledgers (L8)
for REGION in eu us china; do
  kubectl exec -it postgres-${REGION}-0 -- psql << EOF
    CREATE TABLE ledger_entries (
      id BIGSERIAL PRIMARY KEY,
      decision_id UUID NOT NULL,
      merkle_root CHAR(64) NOT NULL,
      signature VARCHAR(256) NOT NULL,
      timestamp TIMESTAMPTZ DEFAULT NOW(),
      region VARCHAR(10) DEFAULT '$REGION'
    );
    CREATE INDEX ON ledger_entries (decision_id, timestamp);
  EOF
done
```

### 3.4 Week 7-8: Pilot Workloads

```bash
# Step 11: Deploy pilot-specific configurations
for PILOT in hotel glass school; do
  for REGION in eu us china; do
    kubectl apply -f pilot-configs/${PILOT}-${REGION}-values.yaml
  done
done

# Step 12: Run E2E test: decision from EU → consensus votes → final AP2 entry
./scripts/e2e_test_hotel_credit.sh
# Expected output: Decision latency <2s, consensus 3/3, Merkle root verified
```

### 3.5 Week 9-12: Scale-Up & Hardening

```bash
# Step 13: Enable auto-scaling
kubectl autoscale deployment harness-executor \
  --min=2 --max=10 \
  --cpu-percent=70 \
  -n sovereignnexus-core

# Step 14: Stress test (100M decisions/month simulation)
./scripts/load_test.sh \
  --decisions-per-sec 38 \
  --duration 1h \
  --regions eu us china

# Step 15: Chaos engineering (partition tolerance test)
./scripts/chaos_test_network_partition.sh

# Step 16: Security audit (TLS cert pinning, rate limits)
./scripts/security_audit.sh
```

---

## 4. MONITORING, ALERTING & INCIDENT RESPONSE

### 4.1 SLO Dashboard (Prometheus Grafana)

```
CRITICAL METRICS:

┌─────────────────────────────────┐
│ Decision Latency (p99)          │
│ Target: <2.0s (green)           │
│ Current: 1.8s [━━━━━━━━━━━▌ ]  │
│ Status: ✅ Healthy              │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│ Consensus Agreement Rate        │
│ Target: >99% (green)            │
│ Current: 99.7% [━━━━━━━━━━━━━] │
│ Status: ✅ Healthy              │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│ Regional Availability           │
│ EU: 99.95% ✅                   │
│ US: 99.93% ✅                   │
│ CN: 99.88% ✅ (network variance)
└─────────────────────────────────┘

┌─────────────────────────────────┐
│ AP2 Ledger Health               │
│ Merkle proofs verified: 99.99%  │
│ Append failures: 0              │
│ Status: ✅ Healthy              │
└─────────────────────────────────┘
```

### 4.2 Alert Rules (Prometheus AlertManager)

```yaml
AlertRules:
  critical_alerts:
    - alert: DecisionLatencyP99ExceededTarget
      expr: histogram_quantile(0.99, decision_latency_seconds) > 2.0
      for: 5m
      annotations:
        summary: "Decision latency {{$value}}s exceeds 2s target"
        action: "Page on-call engineer"
    
    - alert: ConsensusDisagreement
      expr: consensus_agreement_rate < 98
      for: 10m
      annotations:
        summary: "Consensus agreement {{$value}}% below 98% threshold"
        action: "Investigate regional disagreement, check AP2 logs"
    
    - alert: AP2LedgerAppendFailure
      expr: rate(ap2_append_failures_total[5m]) > 0
      for: 1m
      annotations:
        summary: "AP2 ledger append failure detected"
        action: "Critical: Block all new decisions until recovered"
    
    - alert: MerkleProofVerificationFailure
      expr: merkle_proof_failures_total > 0
      for: 1m
      annotations:
        summary: "Merkle proof verification failed"
        action: "Critical: Escalate to security team"
    
    - alert: CrossRegionMessageLoss
      expr: rate(cross_region_message_loss_total[5m]) > 0.01
      for: 5m
      annotations:
        summary: "Cross-region message loss {{$value}}% detected"
        action: "Investigate network connectivity"

  warning_alerts:
    - alert: DecisionLatencyP95Elevated
      expr: histogram_quantile(0.95, decision_latency_seconds) > 1.5
      for: 15m
      annotations:
        summary: "Decision latency trending high"
        action: "Monitor trends, consider scaling up"
```

### 4.3 Incident Response Playbooks

**Playbook 1: One Region Degraded**

```
Trigger: Regional consensus_gateway unavailable >5 min

Action:
1. (Automated) Fail over to secondary region IP
2. (Human) Investigate primary gateway logs (Jaeger trace)
3. (Automated) Increment "region_failures" counter
4. (Human) If recoverable (<30 min): restart gateway pod
5. (Automated) Run Merkle sync to catch up missed entries
6. (Human) Verify consensus votes replayed correctly
7. (Decision) If >30 min downtime: escalate to incident commander
```

**Playbook 2: Consensus Disagreement Detected**

```
Trigger: 2+ regions vote differently (e.g., EU APPROVE, US REJECT)

Action:
1. (Automated) Log conflict to AP2 ledger + escalation queue
2. (Automated) Alert on-call engineer
3. (Human) Review decision + regional evaluations side-by-side
4. (Human) Check: L1 policy differences? L2 knowledge gap? L3 policy conflict?
5. (Decision) Manual arbitration:
   - If L2 gap: update US knowledge graph + re-vote
   - If L3 conflict: policy review required
   - If unfixable: escalate to governance committee
6. (Automated) Document resolution in AP2 ledger
7. (Analytics) Trend analysis: type of disagreement → prevention
```

**Playbook 3: AP2 Ledger Append Failure**

```
Trigger: Decision cannot be written to local AP2 (DB error)

Action:
1. (Automated) BLOCK all new decisions immediately
2. (Automated) Alert CRITICAL + page on-call
3. (Human) SSH into regional database pod
4. (Human) Check: disk full? corruption? lock timeout?
5. (Action) If disk full: delete old logs (>30 days), restart DB
6. (Action) If corruption: restore from hourly snapshot
7. (Human) Verify Merkle chain consistency post-recovery
8. (Automated) Resume decision processing
9. (Post-incident) Root cause analysis + prevention
```

---

## 5. DISASTER RECOVERY & FAILOVER

### 5.1 Regional Backup Strategy

```
BACKUP TIERS:

Tier 1: Local snapshots (hourly)
├─ AP2 ledger: Block-level snapshot every 60 min
├─ PostgreSQL: WAL (Write-Ahead Log) continuous replication
├─ Retention: 24 hours (on-disk)
└─ Recovery time: <5 min (restart from snapshot)

Tier 2: Cross-region replication (near real-time)
├─ PostgreSQL: Streaming replication to secondary DC
├─ AP2 ledger: LEDGER_SYNC daemon (every 30 sec)
├─ Retention: 7 days
└─ Recovery time: <1 min (failover to replica)

Tier 3: Archive (cold storage)
├─ Daily snapshots → S3 (for US), Azure Blob (for EU), OSS (for China)
├─ Retention: 30 days
└─ Recovery time: ~1 hour (restore from archive)

Example: EU region failure scenario
──────────────────────────────────
T0:00 EU primary fails (fire in data center)
      ├─ Last snapshot: T23:30 (30 min ago)
      └─ Replica in Frankfurt: has T23:45 data

T0:02 Failover automated:
      ├─ DNS flip to replica
      ├─ LEDGER_SYNC resync: T23:45 → T00:02 (17 min of decisions)
      └─ Consensus re-routes to US/CN for critical decisions

T0:05 Primary recovered to EU backup DC
      ├─ Restore from T23:30 snapshot
      ├─ Replay WAL logs (23:30 → 00:05)
      └─ Verify Merkle consistency with replica

T0:15 Primary back online, resync with replica
      ├─ All 17 min of decisions (23:45 → 00:02) replayed
      └─ Merkle root verified

T1:00 Full audit: all decisions audited for integrity
```

### 5.2 Kubernetes StatefulSet with PersistentVolumes

```yaml
StatefulSet:
  postgres_primary:
    kind: StatefulSet
    replicas: 1
    serviceName: postgres
    template:
      spec:
        containers:
          - name: postgres
            image: postgres:15-alpine
            env:
              - name: POSTGRES_PASSWORD
                valueFrom:
                  secretKeyRef:
                    name: postgres-secret
                    key: password
              - name: PGDATA
                value: /var/lib/postgresql/data/pgdata
            volumeMounts:
              - name: postgres-storage
                mountPath: /var/lib/postgresql/data
            
            # Liveness probe: restart if unresponsive
            livenessProbe:
              exec:
                command: ["pg_isready", "-U", "postgres"]
              initialDelaySeconds: 30
              periodSeconds: 10
            
            # Readiness probe: don't send traffic if not ready
            readinessProbe:
              exec:
                command: ["pg_isready", "-U", "postgres"]
              initialDelaySeconds: 5
              periodSeconds: 5
    
    volumeClaimTemplates:
      - metadata:
          name: postgres-storage
        spec:
          accessModes: ["ReadWriteOnce"]
          storageClassName: "fast-ssd"
          resources:
            requests:
              storage: 500Gi  # Suitable for 1M decisions/month
```

---

## 6. COST ESTIMATION (YEAR 1)

### 6.1 Single-Region Hardware Cost

```
EU ON-PREM DEPLOYMENT:
├─ RTX 4060 GPU (NVIDIA):        €300 (one-time)
├─ Intel i7-13700K CPU:          €500 (one-time)
├─ 32GB DDR5 RAM:                €200 (one-time)
├─ 1TB NVMe SSD:                 €100 (one-time)
├─ Server chassis + cooling:     €400 (one-time)
├─ Network gear (1Gbps):         €200 (one-time)
├─ Installation + setup:         €500 (one-time)
├─ Power consumption:            €150/mo (24/7 operation)
├─ Facility (shared colocation): €500/mo
├─ Support + maintenance:        €200/mo
└─ **Total EU on-prem:**         **€2,900 one-time + €850/mo**

US AWS DEPLOYMENT (SaaS tier):
├─ AWS EKS cluster:              €500/mo
├─ RDS Aurora PostgreSQL:        €800/mo
├─ EC2 p3.2xlarge (GPU):         €2,000/mo
├─ ElastiCache Redis:            €300/mo
├─ CloudWatch + X-Ray:           €200/mo
├─ Data transfer (egress):       €200/mo
└─ **Total US AWS:**             **€4,000/mo**

CHINA ALIBABA CLOUD DEPLOYMENT:
├─ Alibaba Kubernetes cluster:   ¥3,000/mo (~€400)
├─ Alibaba RDS MySQL:            ¥4,000/mo (~€530)
├─ ECS GPU instance:             ¥6,000/mo (~€800)
├─ SLS logging:                  ¥1,000/mo (~€130)
└─ **Total China:**              **¥14,000/mo (~€1,860)**

3-REGION FOUNDATION (Year 1):
┌────────────────────────────────┐
│ EU on-prem:    €850/mo         │
│ US AWS:        €4,000/mo       │
│ China Alibaba: €1,860/mo       │
├────────────────────────────────┤
│ TOTAL:         €6,710/mo       │
│ Annual:        €80,520         │
└────────────────────────────────┘
```

### 6.2 Scaling to 50+ Deployments (Year 2)

Each customer deployment adds:

```
CUSTOMER DEPLOYMENT (EU proprietary gateway):
├─ Hardware (RTX 4060):          €1,000 (one-time setup)
├─ Kubernetes cluster:           €2,000/mo (managed K3s)
├─ PostgreSQL (managed):         €500/mo
├─ Network/monitoring:           €300/mo
└─ **Per customer:**             **€2,800/mo (after one-time setup)**

20 EU gateways (€2,800/mo each):
├─ Hosting cost:                 €56,000/mo
├─ SovereignNexus margin:        €40,000/mo (at €5k/mo per customer)
└─ Profit per region:            **€40,000/mo (€480k/year)**

US Freemium SaaS (multi-tenant):
├─ AWS shared infrastructure:    €10,000/mo (amortized 20+ customers)
├─ SaaS revenue (freemium→enterprise):
│  ├─ Freemium (1k decisions/mo): Free
│  ├─ Pro ($500/mo × 10 customers): €5,000/mo
│  ├─ Enterprise ($5k/mo × 5 customers): €25,000/mo
│  └─ **US revenue total:**       €30,000/mo
└─ AWS margin: €20,000/mo

China white-label (revenue-share with Alibaba):
├─ Partnership with Alibaba/Baidu (30% revenue share)
├─ 10 deployments × $500k/mo typical SaaS customer = $5M revenue
├─ SovereignNexus take (30%): $1.5M/mo
└─ Alibaba cost (70% goes to Alibaba): $3.5M/mo

SCALING ECONOMICS (Year 2):
┌──────────────────────────┐
│ EU (20 gateways):        │ €480k/year + margin
│ US (freemium):           │ €360k/year (fees only)
│ China (white-label):     │ $18M/year (30% of $60M SaaS revenue)
├──────────────────────────┤
│ TOTAL YEAR 2:            │ €30M–€50M ARR (target)
└──────────────────────────┘
```

---

## 7. DEPLOYMENT CHECKLIST (PRODUCTION LAUNCH)

### Week 1: Kubernetes Infrastructure
- [ ] Provision AWS EKS, Azure AKS, Alibaba ACK (Terraform)
- [ ] Deploy Istio service mesh (TLS, traffic management)
- [ ] Install Prometheus + Jaeger (observability)
- [ ] Verify all 3 regions healthy + networking up
- [ ] Test: DNS SRV record resolution for gateways

### Week 2-3: Harness & MCP Deployment
- [ ] Build + push harness Docker image (multistage build)
- [ ] Deploy harness pods to all 3 regions (1 replica each)
- [ ] Deploy consensus_gateway:8005 (MCP server)
- [ ] Deploy ledger_sync:8006 (MCP server)
- [ ] Test: Cross-region MCP handshakes (TLS mTLS)

### Week 4: Data Layer
- [ ] Initialize PostgreSQL (all 3 regions)
- [ ] Load policy rules (50K rows per region)
- [ ] Create AP2 ledger schema + indexes
- [ ] Configure replication: EU → EU backup, US → US backup, CN → CN backup
- [ ] Test: Query latency <100ms, ledger append <50ms

### Week 5: Consensus & Ledger Sync
- [ ] Test 1-region decision (local only, no consensus needed)
- [ ] Test 3-region decision (EU → vote US + CN → consensus)
- [ ] Verify: All 3 decisions appear in local AP2 ledgers
- [ ] Test: Merkle root consistency across regions
- [ ] Test: Byzantine fault (simulate 1 region corrupted, consensus still works)

### Week 6-7: Pilot Workflows
- [ ] Deploy hotel pilot (L1→L8) to EU
- [ ] Deploy glass pilot (L1→L8) to US
- [ ] Deploy school pilot (L1→L8) to CN
- [ ] End-to-end test: 10 decisions per pilot per region
- [ ] Verify: RAGAS 87%+ accuracy per region

### Week 8-9: Stress Testing
- [ ] Load test: 38 decisions/sec × 3 regions × 1 hour
- [ ] Measure: p50/p95/p99 latency, consensus agreement %
- [ ] Network partition test: disconnect EU from US for 10 min
- [ ] Verify: EU can still decide locally, resync on heal

### Week 10: Disaster Recovery
- [ ] Simulate EU primary failure (kill pod)
- [ ] Verify: Auto-failover to replica (DNS flip)
- [ ] Restore from snapshot + replay WAL
- [ ] Verify: All decisions recovered, Merkle consistency
- [ ] Measure: Recovery time (target: <5 min)

### Week 11-12: Security Audit & Hardening
- [ ] Penetration test: MCP message interception (TLS enforce)
- [ ] Test: Rate limiting (submit 100 req/sec, verify throttle)
- [ ] Test: Replay protection (resend old message, verify reject)
- [ ] Verify: All egress blocked except whitelisted IPs
- [ ] Compliance audit: Data residency (no cross-border flow)

### Final Sign-Off
- [ ] All 3 regions live, 99.9%+ uptime
- [ ] 100M decisions/month capacity proven
- [ ] <2s p99 latency verified
- [ ] All 7 proof artifacts captured (agentacct, AP2, RAGAS, etc.)
- [ ] Production runbooks + incident playbooks complete
- [ ] Go/no-go decision for Phase 3 (Oct 2027)

---

## 8. COLIBRI HARDWARE ORCHESTRATOR (Cost Optimization)

Phase 2B integrates **Colibri** to automatically select hardware + cloud provider based on cost, latency, regulatory constraints:

```rust
// pseudocode: colibri/src/optimizer.rs

pub fn select_deployment(
    region: Region,
    workload: WorkloadType,
    budget_monthly: Money,
    latency_target_ms: u32,
    compliance: ComplianceLevel,
) -> DeploymentOption {
    let candidates = vec![
        // EU
        Option {
            provider: "on-prem",
            hardware: "RTX 4060",
            cost_monthly: Money::eur(850),
            latency_ms: 50,
            compliance: ComplianceLevel::Maximum,
        },
        Option {
            provider: "AWS",
            hardware: "p3.2xlarge",
            cost_monthly: Money::eur(4000),
            latency_ms: 100,
            compliance: ComplianceLevel::High,
        },
        
        // US
        Option {
            provider: "AWS",
            hardware: "p3.2xlarge",
            cost_monthly: Money::usd(3500),
            latency_ms: 80,
            compliance: ComplianceLevel::High,
        },
        Option {
            provider: "GCP",
            hardware: "A100 GPU",
            cost_monthly: Money::usd(4200),
            latency_ms: 90,
            compliance: ComplianceLevel::High,
        },
        
        // China
        Option {
            provider: "Alibaba",
            hardware: "GPU instance",
            cost_monthly: Money::cny(13000),
            latency_ms: 100,
            compliance: ComplianceLevel::Maximum,
        },
    ];
    
    // Filter: must meet compliance + latency
    let viable = candidates
        .iter()
        .filter(|o| o.compliance >= compliance && o.latency_ms <= latency_target_ms)
        .collect::<Vec<_>>();
    
    // Score: lowest cost + acceptable latency
    let best = viable
        .iter()
        .min_by_key(|o| o.cost_monthly)
        .expect("no viable deployment");
    
    best.clone()
}

// Colibri auto-scales: if latency degrades, switch to faster (more expensive) hardware
```

---

## 9. APPENDIX: KUBERNETES MANIFESTS

### Service (MCP endpoint, ClusterIP)

```yaml
apiVersion: v1
kind: Service
metadata:
  name: consensus-gateway
  namespace: sovereignnexus-gateway
  labels:
    app: consensus-gateway
spec:
  type: ClusterIP
  selector:
    app: consensus-gateway
  ports:
    - name: mcp
      port: 8005
      targetPort: 8005
      protocol: TCP
  sessionAffinity: None
```

### Deployment (harness_executor)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: harness-executor
  namespace: sovereignnexus-core
spec:
  replicas: 2
  selector:
    matchLabels:
      app: harness-executor
  template:
    metadata:
      labels:
        app: harness-executor
    spec:
      containers:
        - name: harness
          image: gcr.io/sovereignnexus/harness:2b-v1
          ports:
            - containerPort: 8080
              name: http
          resources:
            requests:
              cpu: "4"
              memory: "8Gi"
            limits:
              cpu: "8"
              memory: "16Gi"
          env:
            - name: REGION
              value: "eu"
            - name: LOG_LEVEL
              value: "INFO"
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /ready
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 5
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              podAffinityTerm:
                labelSelector:
                  matchExpressions:
                    - key: app
                      operator: In
                      values:
                        - harness-executor
                topologyKey: kubernetes.io/hostname
```

---

**Document Version:** 2.0  
**Last Updated:** 2027-07-01  
**Approved By:** Infrastructure & Deployment Team  

**Next Steps:**
1. Finalize Terraform IaC for all 3 regions
2. Create Docker build pipeline (CI/CD)
3. Set up Kubernetes cluster configuration (Helm charts)
4. Configure observability stack (Prometheus + Grafana)
5. Begin Week 1 deployment execution
