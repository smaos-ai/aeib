# SMAOS Phase 2B: Federated Governance-as-a-Service (GaaS) Scaling Specification
**Timeline:** Jul 1 - Sep 30, 2027 (12 weeks, solo engineer, parallel with Phase 2A design)  
**Completion Target:** May 31, 2027 (aligns with Annex III compliance Dec 2, 2027)  
**Revenue Target:** €30M–€50M ARR (2-3x Phase 2A baseline of €15M–€20M)  
**Success Criteria:** 50+ regional deployments, 100M+ decisions/month, <2s latency p99

---

## EXECUTIVE SUMMARY

Phase 2B scales SMAOS from single-region governance harness (Phase 1) + egress controls (Phase 2A) to a federated, multi-tenant regional GaaS platform. Three regional variants deploy independently but coordinate decisions through Byzantine-fault-tolerant consensus:

- **Tier 1 (EU, on-prem):** Proprietary harness, owned by SovereignNexus, €5k–€50k/mo per gateway
- **Tier 2 (US, AWS/GCP):** Open-source core harness, freemium SaaS upsell, $5M–$10M ARR
- **Tier 3 (China, Alibaba/Baidu):** White-label variant, revenue-share partnership, $3M–$10M ARR

Each regional gateway:
1. Runs full L1–L8 harness locally (no cloud dependency)
2. Publishes decisions to cross-region AP2 ledger (Merkle-rooted, Ed25519-signed)
3. Accepts consensus corrections from 2+ peer regions (Byzantine fault tolerance)
4. Maintains region-specific compliance rules (Annex III for EU, HIPAA for US, CAC for China)
5. Communicates via MCP/A2A gateways (encrypted, rate-limited, audited)

**Blocking Dependency:** Completes after Phase 2A intent verification (Jul 31, 2027). Phase 2B implementation runs Jul-Sep 2027 while Phase 2A design wraps up.

---

## 1. ARCHITECTURE: FEDERATED REGIONAL CONSENSUS

### 1.1 Regional Gateway Structure

Each region deploys identical harness with region-specific configs:

```
REGION (EU / US / China)
├── L1: Policy Router
│   ├── Articles: EU AI Act (EU), NIST AI RMF (US), 生成式AI (China)
│   └── Config: region_policies.json
├── L2: Knowledge Graph
│   ├── pgvector: Region-specific compliance rules
│   ├── BM25: Local regulatory docs (GDPR/HIPAA/CAC)
│   └── RRF: Hybrid search tuned per jurisdiction
├── L3: Permit Gates
│   ├── Enforcement: Article 37 (EU), high-risk rules per region
│   ├── Egress Control: Whitelist per region (Phase 2A)
│   └── Intent Verification: Approved actions per region (Phase 2A)
├── L4: Orchestration
│   ├── Pilots: Localized workflows (hotel-EU, hospital-US, school-CN)
│   └── Checkpoints: Cross-region traceable
├── L5: MCP Communication
│   ├── Inbound: Consensus corrections from peer regions
│   ├── Outbound: Decision publication to AP2 ledger
│   └── Protocol: JSON-RPC 2.0 encrypted channels
├── L6: Infrastructure
│   ├── Hardware: Regional edge nodes (RTX 4060 → AWS/Alibaba)
│   ├── Models: Local cached, no cloud egress
│   └── Colibri: Model selection per region
├── L7: RAGAS
│   ├── Golden Set: Region-specific 50Q
│   └── Target: 87%+ accuracy per region
└── L8: Proof
    ├── Local AP2: Region's immutable ledger
    └── Signature: Ed25519 per decision

↓↓↓ CROSS-REGION CONSENSUS ↓↓↓

CONSENSUS LAYER (NEW)
├── Decision Aggregation (Byzantine Byzantine Fault Tolerance)
├── Merkle Tree: Cross-region ledger root
├── Voting: 3+ regions → 2/3 majority required
└── Conflict Resolution: Last-write-wins + audit trail
```

### 1.2 Cross-Region Decision Flow

```
SCENARIO: EU hotel requests €1M credit decision
Initiated by: EU gateway (HOTEL-001)

PHASE 1: LOCAL EXECUTION (EU, <200ms)
┌─────────────────────────────────────┐
│ EU Gateway (SovereignNexus)         │
│ ├─ L1: Policy Router                │
│ │  └─ Article 37 (high-risk)        │
│ ├─ L3: Permit Gates                 │
│ │  └─ Human review required         │
│ ├─ L4: Orchestration                │
│ │  └─ Checkpoint: C001_EU           │
│ └─ Decision: "APPROVE_WITH_REVIEW"  │
│    Proof: signature_EU               │
└─────────────────────────────────────┘
         ↓ (publish via MCP)
         
PHASE 2: PARALLEL PEER VERIFICATION (US + China, <1s)
┌──────────────────────┐  ┌──────────────────────┐
│ US Gateway (AWS)     │  │ China Gateway (Ali)  │
│ ├─ Receives: HOTEL-  │  │ ├─ Receives: HOTEL-  │
│ │  001 decision_EU   │  │ │  001 decision_EU   │
│ ├─ Re-evaluates:     │  │ ├─ Re-evaluates:     │
│ │  NIST AI RMF       │  │ │  生成式AI CAC       │
│ ├─ Runs: L1→L3       │  │ ├─ Runs: L1→L3       │
│ │  (local check)     │  │ │  (local check)     │
│ └─ Vote: APPROVE ✓   │  │ └─ Vote: APPROVE ✓   │
│    (confidence: 92%) │  │    (confidence: 88%) │
└──────────────────────┘  └──────────────────────┘
         ↓ (publish votes)
         
PHASE 3: CONSENSUS AGGREGATION (<300ms)
┌──────────────────────────────────────┐
│ Consensus Layer (any region)         │
│ ├─ Votes received: EU ✓ US ✓ CN ✓    │
│ ├─ Tally: 3/3 APPROVE                │
│ ├─ Confidence: min(92%, 88%) = 88%   │
│ ├─ Status: CONSENSUS REACHED         │
│ └─ Merkle root: hash(prev + this)    │
└──────────────────────────────────────┘
         ↓ (MCP broadcast)
         
PHASE 4: FINALIZATION (<100ms)
All regions receive final decision + merkle proof
├─ EU: Store in local AP2, update L7 RAGAS
├─ US: Store in local AP2, log to CloudWatch
└─ CN: Store in local AP2, encrypt key per CAC

Total latency: ~1.5s (well under 2s p99 target)
Audit trail: All 3 decisions + votes + consensus in AP2 ledgers
```

### 1.3 Byzantine Fault Tolerance (Simplified)

**Problem:** One region corrupted or network-partitioned. How do 2+ regions trust each other?

**Solution:** 3-region voting + cryptographic proof

```
Scenario: US region returns erroneous decision

EU submits decision → EU ✓ US ✗ (disagrees) CN ✓
Status: 2/3 agree (majority wins) → CONSENSUS: EU/CN vote used
Issue: US region marked as "degraded" in consensus log

Recovery:
1. US re-syncs L2 knowledge graph from EU
2. US re-evaluates L3 permit gates
3. US resubmits vote
4. If still disagree: human arbitration (audit trail shows conflict)

Ledger audit trail:
{
  "decision_id": "HOTEL-001",
  "region_votes": {
    "EU": { "vote": "APPROVE", "confidence": 92%, "signature": "sig_eu" },
    "US": { "vote": "REJECT", "confidence": 45%, "signature": "sig_us" },
    "CN": { "vote": "APPROVE", "confidence": 88%, "signature": "sig_cn" }
  },
  "consensus": {
    "result": "APPROVE_BY_MAJORITY",
    "tally": "2/3",
    "merkle_root": "hash(...)",
    "note": "US disagreed (45% confidence) — flagged for audit review"
  },
  "timestamp": "2027-07-15T09:30:00Z"
}
```

**Consensus Rules:**
- 1 region: Local decision only (no consensus required)
- 2 regions: Both must agree (no tie-breaking)
- 3+ regions: 2/3 majority (Byzantine tolerance)
- Disagreement threshold: >10 percentage points = escalate to human reviewer

---

## 2. MCP/A2A COMMUNICATION LAYER (L5 EXTENSION)

### 2.1 Cross-Region Message Protocol

```
Message Types:

1. PUBLISH_DECISION
   From: [source_region]_gateway
   To: consensus_aggregator (all regions)
   Payload:
   {
     "type": "publish_decision",
     "source_region": "EU",
     "decision_id": "HOTEL-001",
     "decision": {
       "action": "APPROVE_WITH_REVIEW",
       "articles_cited": ["37", "50"],
       "checkpoints": [c1_hash, c2_hash, c3_hash],
       "confidence": 92.0,
       "timestamp": "2027-07-15T09:30:00Z"
     },
     "proof": {
       "signature": "ed25519_sig_hex",
       "ledger_root": "merkle_hash_before"
     }
   }

2. REQUEST_CONSENSUS_VOTE
   From: consensus_aggregator
   To: [peer_regions]_gateway
   Payload:
   {
     "type": "request_vote",
     "decision_id": "HOTEL-001",
     "original_decision": { ... },
     "source_region": "EU",
     "timeout_ms": 1000
   }

3. CAST_VOTE
   From: [voter_region]_gateway
   To: consensus_aggregator
   Payload:
   {
     "type": "cast_vote",
     "decision_id": "HOTEL-001",
     "voter_region": "US",
     "vote": "APPROVE",
     "confidence": 92.0,
     "re_evaluation": {
       "l1_policy": "NIST AI RMF Article 6",
       "l3_check": "HIPAA compliant",
       "reasoning": "High-risk decision but has human review flag"
     },
     "signature": "ed25519_sig_us"
   }

4. PUBLISH_CONSENSUS
   From: consensus_aggregator
   To: all_regions
   Payload:
   {
     "type": "publish_consensus",
     "decision_id": "HOTEL-001",
     "consensus_result": "APPROVE",
     "votes_received": {
       "EU": { "vote": "APPROVE", "confidence": 92.0 },
       "US": { "vote": "APPROVE", "confidence": 92.0 },
       "CN": { "vote": "APPROVE", "confidence": 88.0 }
     },
     "tally": "3/3",
     "merkle_root": "new_ledger_hash",
     "timestamp": "2027-07-15T09:30:00.300Z"
   }

5. SYNC_LEDGER
   From: any_region
   To: any_other_region
   Purpose: Keep AP2 ledgers in eventual consistency
   Payload:
   {
     "type": "sync_ledger",
     "source_region": "EU",
     "target_region": "US",
     "ledger_segment": [decision_hashes],
     "merkle_root": "current_root",
     "last_sync_timestamp": "2027-07-15T08:00:00Z"
   }

6. CONFLICT_ESCALATION
   From: [region]_gateway
   To: arbitration_queue
   Purpose: Manual review needed
   Payload:
   {
     "type": "escalate",
     "decision_id": "HOTEL-001",
     "conflict_type": "consensus_disagreement",
     "regions_disagreed": ["EU", "US"],
     "confidence_diff": 47.0,  # |92% - 45%|
     "reasoning": "US detected potential HIPAA violation; EU missed"
   }
```

### 2.2 MCP Server Deployment (Regional Gateways)

Each region runs 4 MCP servers (existing from Phase 1) + 2 new federation servers:

```
EU REGION
├─ request_mcp:8001       (L5 old)
├─ policy_mcp:8002        (L5 old)
├─ audit_mcp:8003         (L5 old)
├─ feedback_mcp:8004      (L5 old)
├─ consensus_gateway:8005 (NEW) — handles PUBLISH_DECISION, CAST_VOTE
└─ ledger_sync:8006       (NEW) — SYNC_LEDGER, replication

US REGION
├─ request_mcp:8001
├─ policy_mcp:8002
├─ audit_mcp:8003
├─ feedback_mcp:8004
├─ consensus_gateway:8005
└─ ledger_sync:8006

CHINA REGION
├─ request_mcp:8001
├─ policy_mcp:8002
├─ audit_mcp:8003
├─ feedback_mcp:8004
├─ consensus_gateway:8005
└─ ledger_sync:8006

Discovery: DNS SRV records (e.g., _consensus._tcp.eu.sovereignnexus.io)
            or hardcoded region addresses (production)
```

### 2.3 Network Security (MCP Layer)

```
Encryption:
├─ TLS 1.3 for all inter-region communication
├─ Mutual TLS: Regional gateways authenticate each other
├─ Certificate pinning: Pre-distributed region public keys
└─ Session tokens: JWT signed with region's Ed25519 key (exp: 1h)

Rate Limiting:
├─ Per region: 100 decisions/sec (aggregate)
├─ Per peer: 10 decision/sec (prevent flooding)
└─ Backpressure: If queue >1000, reject new decisions with 503

Audit:
├─ All MCP messages logged to local AP2 ledger
├─ Timestamps: UTC with microsecond precision
├─ Signature: Each message signed before transmission
└─ Replay protection: Message sequence numbers per peer pair

Failover:
├─ If consensus_gateway:8005 unreachable:
│  └─ Route through backup gateway (secondary region IP)
├─ If ledger_sync:8006 fails:
│  └─ Queue syncs locally, retry with exponential backoff
└─ Partition tolerance: Region can decide locally, resync on heal
```

---

## 3. CROSS-REGION AP2 LEDGER (L8 EXTENSION)

### 3.1 Merkle Tree Consensus

Each region maintains a local AP2 ledger. Consensus requires agreement on ledger roots across regions.

```
LEDGER STRUCTURE (per region)

EU AP2 Ledger:
Entry 1: hash(hotel_decision_1)
Entry 2: hash(glass_decision_1)
Entry 3: hash(school_decision_1)
Entry 4: hash(consensus_votes_1_3)
...

Merkle Tree (EU):
         root_EU_hash_N
        /              \
    hash_left       hash_right
    /       \       /       \
  e1 e2   e3 e4   e5 e6   e7 e8

root_EU_hash_N = SHA256(
  consensus_votes_1_3_hash +
  previous_root_hash_EU_N-1
)

Cross-Region Merkle Root:
root_consensus = SHA256(
  root_EU + root_US + root_CN
)

This root is published to:
1. All three regions' L8 ledgers (cross-region entry)
2. Public git repository (immutable proof)
3. Blockchain-like timestamped log (optional: Merkle Inclusion Proof service)
```

### 3.2 Eventual Consistency Model

```
Timeline:

T0:00:00 EU decision published
         EU AP2 entry created
         Decision ID: HOTEL-001
         
T0:00:05 EU sends PUBLISH_DECISION to consensus_gateway
         US, CN receive via MCP
         
T0:00:10 US votes APPROVE (re-evaluates locally)
         US AP2 entry: "VOTED_ON_HOTEL_001"
         
T0:00:15 CN votes APPROVE
         CN AP2 entry: "VOTED_ON_HOTEL_001"
         
T0:00:20 Consensus finalized (3/3)
         - EU updates: decision_status="CONSENSUS_REACHED"
         - US updates: decision_status="CONSENSUS_REACHED"
         - CN updates: decision_status="CONSENSUS_REACHED"
         - All regions commit new merkle_root_consensus to AP2
         
T0:00:30 LEDGER_SYNC: EU → US (catch-up)
         US receives missing entries from T0:00:00-T0:00:20
         US verifies merkle proof
         
T0:01:00 LEDGER_SYNC: EU → CN (catch-up)
         CN receives missing entries
         CN verifies merkle proof
         
Guarantee: After CONSENSUS_REACHED + 2 × LEDGER_SYNC_TIMEOUT,
           all regions have identical entry set
           (eventually consistent, conflict-free)

Failure case: US offline T0:00:00-T0:02:00
             ├─ EU, CN reach consensus without US
             ├─ Decision marked: "CONSENSUS_REACHED_2/3"
             └─ When US comes back: receives SYNC_LEDGER + resyncs
                (US updates local status retrospectively)
```

---

## 4. REGIONAL VARIANTS (L1-L3 CUSTOMIZATION)

### 4.1 EU Variant (SovereignNexus-owned)

**Policy Router (L1):**
- Primary articles: 37 (high-risk), 50 (transparency), 51 (governance), 14 (record-keeping)
- Deny-by-default: Requests must cite valid EU AI Act article
- Scope: Financial services, HR, access control, civic decision-making

**Knowledge Graph (L2):**
- Indexed rules: GDPR, NIS2, eIDAS, EU Data Act
- Regulatory timeline: Annex III (Dec 2, 2027), Annex I (Aug 2, 2028)
- Data residency: All vectors stored in EU data centers (no cloud egress)

**Permit Gates (L3):**
- Article 37: Financial/HR decisions require human review + explainability
- Egress control: Whitelist only EU credit bureaus + internal APIs
- Intent verification: Approved actions for each pilot type

**Example Policy Rule:**
```yaml
article_37_credit_decision:
  trigger: decision_type == "financial" AND amount > 50000
  article: "37"  # High-risk AI
  enforcement:
    human_review_required: true
    explanation_required: true
    audit_trail_required: true
  egress_whitelist: [equifax.com, experian.com, sovereignnexus.eu]
  regions: ["EU"]
  compliance_level: "maximum"
```

**Hardware:** On-prem or EU AWS/Azure (e.g., Frankfurt, Ireland data centers)

**Pilots:**
- Hotel (Czech chains): Credit scoring (L1→L8)
- Glass (EU OEM): CAD design review (L1→L8)
- School (GDPR-sensitive): Access control (L1→L8)

---

### 4.2 US Variant (Open-Source + Freemium SaaS)

**Policy Router (L1):**
- Primary articles: NIST AI RMF (Measure, Monitor, Manage), HIPAA (healthcare), FCRA (credit)
- Compliance flexibility: Multiple frameworks supported (NIST, HIPAA, GLBA, CAN-SPAM)
- Scope: More permissive than EU (no high-risk ban, just mitigation required)

**Knowledge Graph (L2):**
- Indexed rules: NIST AI RMF, HIPAA Privacy Rule, Equal Credit Opportunity Act
- Open-source knowledge base (GitHub): Community-contributed regulatory rules
- Data residency: AWS (us-east-1, us-west-2 options)

**Permit Gates (L3):**
- Risk assessment: Uses NIST AI RMF categories (malicious use, privacy, cybersecurity)
- Mitigation required: If risk >7/10, customer must implement 2+ mitigations
- Freemium tier: Capped at 1000 decisions/month (SaaS upsell: 100k/month = $500/mo)

**Example Policy Rule:**
```yaml
nist_high_risk_ai:
  trigger: risk_score > 7
  framework: "NIST AI RMF"
  enforcement:
    mitigation_required: true
    mitigations_needed: 2
    options:
      - human_review
      - explainability_audit
      - bias_detection_test
      - regular_monitoring
  egress_whitelist: [github.com, nist.gov, aws.amazon.com]
  tier: "freemium" (capped) or "enterprise" (unlimited)
```

**Hardware:** AWS auto-scaling (Lambda + RDS for small orgs, EC2 + Aurora for large)

**Pilots:**
- Healthcare: HIPAA-compliant diagnostic AI review
- Banking: FCRA-compliant loan approval
- E-commerce: Fairness audit for product recommendation AI

**Open-Source Contribution:**
- Core harness (L1-L8) released on GitHub under AGPL 3.0
- Community can fork and customize for local regulations
- SovereignNexus contributes L7 (RAGAS) + L8 (AP2 ledger) as premium add-on

---

### 4.3 China Variant (White-Label Partnership)

**Policy Router (L1):**
- Primary articles: 生成式AI 临时办法 (generative AI interim measures), CAC content rules
- Content filtering: All decisions must avoid prohibited topics (Tibet, Xinjiang, etc.)
- Localization: Chinese regulatory documents only

**Knowledge Graph (L2):**
- Indexed rules: CAC guidelines, Industry-specific regulations (telecom, finance)
- Data residency: Alibaba/Baidu regional data centers (China-only)
- Approved models: Qwen, Baichuan (no OpenAI/Anthropic exports)

**Permit Gates (L3):**
- Content compliance: Every decision checked against CAC prohibited list
- Data governance: All PII encrypted with KMS (key stored in China)
- Export restrictions: No cross-border data flow without explicit approval

**Example Policy Rule:**
```yaml
cac_content_compliance:
  trigger: decision_involves_text_generation
  regulatory_framework: "生成式AI 临时办法"
  enforcement:
    content_filter: true
    prohibited_topics: [
      "反党反社会主义",
      "违反民族宗教政策",
      "泄露国家机密"
    ]
    approved_models_only: true
    local_kms_required: true
  egress_whitelist: [alibaba.com, aliyun.com, baidu.com]
  data_residency: "China-only"
```

**Hardware:** Alibaba Cloud (阿里云) or Baidu AI Cloud (百度AI云)

**Revenue Model:** Revenue-share with Alibaba/Baidu (30% of SaaS revenue)

**Pilots:**
- Bank loan decision approval (CAC-compliant)
- E-commerce recommendation system (content filtering)
- Telecom customer service automation (approved models only)

---

## 5. IMPLEMENTATION ROADMAP (9 WEEKS)

### Week 1-2: Core Federation Framework
- [ ] Design consensus algorithm (Byzantine FT)
- [ ] Define MCP protocol extensions (consensus_gateway, ledger_sync servers)
- [ ] Implement 3-region voting logic (Rust structs)
- [ ] Set up regional environment configs (EU/US/China)
- **Deliverable:** Consensus protocol spec + regional configs + voting tests
- **Tests:** 12 unit tests (vote aggregation, tie-breaking, byzantine faults)
- **Commits:** 3 atomic (protocol, configs, tests)

### Week 3-4: Regional Variants
- [ ] EU variant L1 (policy router for EU AI Act articles)
- [ ] US variant L1 (policy router for NIST AI RMF)
- [ ] China variant L1 (policy router for CAC rules)
- [ ] L2 knowledge graph customization per region
- [ ] L3 permit gates per region
- **Deliverable:** 3 regional policy files + customized L1-L3 code
- **Tests:** 18 integration tests (1 per region × L1/L2/L3)
- **Commits:** 3 atomic (one per region)

### Week 5: MCP Communication (L5 Extension)
- [ ] Implement consensus_gateway MCP server
- [ ] Implement ledger_sync MCP server
- [ ] Add PUBLISH_DECISION, CAST_VOTE protocol handlers
- [ ] Add network security layer (TLS 1.3, rate limiting, audit logging)
- **Deliverable:** 2 new MCP servers + protocol handlers + security tests
- **Tests:** 22 MCP protocol tests (message routing, encryption, backpressure)
- **Commits:** 2 atomic (servers, security)

### Week 6-7: Cross-Region AP2 Ledger (L8 Extension)
- [ ] Implement Merkle tree consensus (per-region + cross-region)
- [ ] Implement eventual consistency model (LEDGER_SYNC)
- [ ] Add conflict detection + escalation logic
- [ ] Implement Merkle proof verification
- **Deliverable:** L8 ledger extensions + merkle tree tests
- **Tests:** 16 ledger tests (merkle proof, consistency, conflict resolution)
- **Commits:** 2 atomic (merkle logic, consistency model)

### Week 8: Integration & L7 RAGAS Update
- [ ] Integrate all layers L1→L8 for federated decision flow
- [ ] Update L7 RAGAS with region-specific golden sets
- [ ] End-to-end test: EU decision → consensus votes → final AP2 entry
- [ ] Deploy 3 regional gateways (dev environment)
- **Deliverable:** E2E test harness + regional golden sets
- **Tests:** 28 integration tests (full L1→L8 per region)
- **Commits:** 2 atomic (integration, RAGAS update)

### Week 9: Performance & Stress Testing
- [ ] Latency benchmarks (<2s p99 for 3-region consensus)
- [ ] Throughput test: 100M decisions/month simulation
- [ ] Network partition test (1 region isolated)
- [ ] Byzantine fault injection (1 region returns bad data)
- **Deliverable:** Performance report + stress test results
- **Tests:** 12 stress tests (throughput, latency, partition tolerance)
- **Commits:** 1 atomic (performance baseline)

### Weeks 10-12: Documentation, Hardening, Prep for Production
- [ ] Write regional deployment guides (EU/US/China)
- [ ] Create runbooks for consensus failure recovery
- [ ] Security audit: MCP encryption, rate limiting
- [ ] Prepare for Phase 2B pilot deployments (Week 13+)
- **Deliverable:** Deployment documentation + security audit report
- **Tests:** 8 manual security tests (TLS cert pinning, replay attacks)
- **Commits:** 2 atomic (docs, security hardening)

**Total Implementation:** 9 weeks (complete by mid-Sep 2027)

**Parallel Design (Weeks 1-3 with Phase 2A):**
- Phase 2A: Finalize egress controls + intent verification
- Phase 2B: Design consensus protocol + MCP extensions
- Handoff: Phase 2A → Phase 2B integration at Week 4

---

## 6. SYSTEM DIAGRAMS

### 6.1 Regional Deployment Topology

```
┌─────────────────────────────────────┐
│         INTERNET (Public)           │
└─────────────────────────────────────┘
   ↑                    ↑                    ↑
   │                    │                    │
   │ (TLS 1.3)         │ (TLS 1.3)         │ (TLS 1.3)
   │ Mutual mTLS       │ Mutual mTLS       │ Mutual mTLS
   │                    │                    │
┌──▼────────────┐  ┌──▼────────────┐  ┌──▼────────────┐
│  EU GATEWAY   │  │  US GATEWAY   │  │ CHINA GATEWAY │
│  (On-Prem)    │  │  (AWS)        │  │ (Alibaba)     │
│               │  │               │  │               │
│ L1-L8 Harness │  │ L1-L8 Harness │  │ L1-L8 Harness │
│ + Consensus   │  │ + Consensus   │  │ + Consensus   │
└─────┬─────────┘  └─────┬─────────┘  └─────┬─────────┘
      │                  │                  │
      └──────────────────┼──────────────────┘
           (MCP routing)  │
                          │
                    ┌─────▼──────┐
                    │ Consensus  │
                    │  Processor │
                    │ (any region)
                    └─────┬──────┘
                          │
           ┌──────────────┼──────────────┐
           │              │              │
      ┌────▼────┐     ┌────▼────┐    ┌──▼─────┐
      │ AP2 EU  │     │ AP2 US  │    │AP2 CHINA
      │ Ledger  │     │ Ledger  │    │ Ledger
      │ (local) │     │ (local) │    │ (local)
      └────┬────┘     └────┬────┘    └──┬─────┘
           │              │              │
           └──────────────┼──────────────┘
                    ┌─────▼──────┐
                    │Cross-Region│
                    │ Merkle Root│
                    │ + GitHub   │
                    │(immutable) │
                    └────────────┘
```

### 6.2 Decision Flow with Timing

```
EU Request (t=0)
├─ L1 Router (t=0-5ms)
├─ L2 Knowledge (t=5-50ms)
├─ L3 Permit Gates (t=50-100ms)
├─ L4 Orchestration (t=100-150ms)
├─ L5 MCP: PUBLISH_DECISION (t=150-200ms)
│  └─ Sent to US + CN consensus_gateway
├─ L6 Infrastructure check (t=200-250ms)
├─ L8 EU AP2: Record decision (t=250-300ms)
│
├─ [WAITING FOR CONSENSUS VOTES] (t=300-1000ms)
│
│  US Gateway (parallel, t=300-500ms)
│  ├─ Receives: PUBLISH_DECISION
│  ├─ L1 Router (US policy)
│  ├─ L3 Permit (HIPAA check)
│  ├─ Vote: APPROVE (92% confidence)
│  ├─ L8 US AP2: Record vote
│  └─ MCP: CAST_VOTE → consensus_gateway
│
│  CN Gateway (parallel, t=300-500ms)
│  ├─ Receives: PUBLISH_DECISION
│  ├─ L1 Router (CAC policy)
│  ├─ L3 Permit (content filter)
│  ├─ Vote: APPROVE (88% confidence)
│  ├─ L8 CN AP2: Record vote
│  └─ MCP: CAST_VOTE → consensus_gateway
│
├─ Consensus aggregator (t=1000-1300ms)
│  ├─ Receives: EU✓ US✓ CN✓
│  ├─ Tally: 3/3 APPROVE
│  ├─ Merkle: hash(prev + votes)
│  └─ MCP: PUBLISH_CONSENSUS → all regions
│
├─ EU receives PUBLISH_CONSENSUS (t=1300-1400ms)
│  ├─ Update decision status: CONSENSUS_REACHED
│  ├─ Update L7 RAGAS score (99%)
│  ├─ L8 AP2: Record consensus
│  └─ L5 MCP: Notify requestor
│
└─ FINAL DECISION READY (t=1400ms)
   [Under 2s p99 target]
```

---

## 7. QUALITY GATES & SUCCESS CRITERIA

### 7.1 Performance SLAs

| Metric | Target | Measurement |
|--------|--------|-------------|
| Single-region decision | <500ms | L1→L8 local execution |
| Consensus latency (3-region) | <2.0s p99 | End-to-end with voting |
| Ledger sync time | <1.0s | SYNC_LEDGER message + verification |
| Regional consensus availability | 99.9% | Uptime across 3 regions |
| Throughput | 100M decisions/month | ~38 decision/sec per region |

### 7.2 Security Gates

| Control | Requirement | Verification |
|---------|-------------|--------------|
| MCP encryption | TLS 1.3 + mTLS | Certificate pinning test + packet capture |
| Rate limiting | <10 req/sec per peer | Load test with burst traffic |
| Message signing | Ed25519 on all decisions | Cryptographic verification test |
| Replay protection | Sequence numbers enforced | Replay injection test |
| Network isolation | No plaintext cross-region | tcpdump inspection |

### 7.3 Compliance Gates

| Framework | Requirement | Proof |
|-----------|-------------|-------|
| EU AI Act (Annex III) | Articles 37, 50 enforced per region | Policy audit trail in AP2 |
| NIST AI RMF (US) | Risk categories mapped | L1 policy config + test results |
| CAC (China) | Content filtering enforced | Prohibited topic test results |
| GDPR (all regions) | Data residency enforced | Cloud egress denied, local-only |

### 7.4 Regional Deployment Checklist

**EU Variant (On-Prem):**
- [ ] Policy router: EU AI Act articles mapped
- [ ] Knowledge graph: GDPR + Annex III rules indexed
- [ ] Egress whitelist: Only EU credit bureaus
- [ ] Pilot: Hotel credit decision (10 test cases)
- [ ] RAGAS: 87%+ accuracy on EU golden set
- [ ] Hardware: RTX 4060 on-prem or EU AWS
- [ ] Audit: 3 L1→L8 decisions logged + signed

**US Variant (AWS):**
- [ ] Policy router: NIST AI RMF categories mapped
- [ ] Knowledge graph: HIPAA, FCRA rules indexed
- [ ] Freemium tier: 1000 decisions/month cap enforced
- [ ] Pilot: HIPAA healthcare decision (5 test cases)
- [ ] RAGAS: 87%+ accuracy on US golden set
- [ ] Hardware: AWS Lambda + RDS auto-scaling
- [ ] Audit: 3 L1→L8 decisions logged + signed

**China Variant (Alibaba):**
- [ ] Policy router: CAC rules enforced
- [ ] Knowledge graph: Chinese regulatory docs
- [ ] Content filter: Prohibited topics blocked
- [ ] Data encryption: KMS-protected (China key)
- [ ] Pilot: Bank loan decision (5 test cases)
- [ ] RAGAS: 87%+ accuracy on China golden set
- [ ] Hardware: Alibaba Cloud regional
- [ ] Audit: 3 L1→L8 decisions logged + signed

---

## 8. REGULATORY ALIGNMENT

### 8.1 EU AI Act Compliance (Annex III Deadline: Dec 2, 2027)

Phase 2B federated architecture addresses:

- **Article 37 (High-risk AI):** Three-region consensus ensures no single region can override high-risk classification. Human review mandatory + logged.
- **Article 50 (Transparency):** All decisions cite articles in L1. AP2 ledger provides immutable audit trail.
- **Article 51 (Human Oversight):** Consensus voting ensures human judgment applies across regions. Escalation workflow for disagreements.
- **Annex III compliance:** Regional variants enforce education/employment exemptions per jurisdiction.

**Proof artifacts:**
- L1 policy configs: EU AI Act article mapping
- L8 AP2 ledger: 50+ signed decisions per region showing article citation
- RAGAS golden set: 50-question test covering transparency/oversight

### 8.2 US Regulatory Alignment (NIST AI RMF, HIPAA, FCRA)

- **NIST AI RMF:** Risk assessment required before decision. L3 permit gates enforce mitigation.
- **HIPAA:** US variant enforces data residency (AWS only) + encryption. No EU/China access to healthcare PII.
- **FCRA:** Credit decisions must cite reason. L1 router enforces explanation + audit trail.

**Proof artifacts:**
- NIST RMF policy config: Risk categories mapped
- HIPAA audit: Data residency check + encryption proof
- FCRA compliance: Credit decision explanations logged

### 8.3 China CAC Compliance

- **生成式AI 临时办法:** Content filtering enforced for all decisions. Prohibited topics blocked at L3.
- **Data sovereignty:** All data encrypted with China KMS. No cross-border flow.
- **Model approval:** Only approved models (Qwen, Baichuan) allowed.

**Proof artifacts:**
- CAC policy config: Prohibited topics list + filtering logic
- Data residency: Alibaba-only deployment proof
- Model approval: Whitelisted models log

---

## 9. COST STRUCTURE & SCALING

### 9.1 Per-Region Hardware (Year 1)

| Component | Cost | Quantity | Total |
|-----------|------|----------|-------|
| RTX 4060 (edge node) | €300 | 3 | €900 |
| Kubernetes cluster (small) | €1000/mo | 3 | €3000/mo |
| Database (pgvector) | €500/mo | 3 | €1500/mo |
| Network (inter-region) | €200/mo | 3 | €600/mo |
| **Total per region** | — | — | **€6000/mo** |
| **Total 3 regions** | — | — | **€18k/mo** |

### 9.2 Scaling to 50+ Deployments (Year 2)

- EU: 20 regional gateways (customers) × €5k–€50k/mo = €2.5M–€25M ARR
- US: 15+ AWS deployments (freemium→SaaS upsell) = $5M–$10M ARR
- China: 10+ Alibaba partnerships (revenue-share 30%) = $3M–$10M ARR

**Total Target Phase 2B:** €30M–€50M ARR

---

## 10. DEPENDENCY MAP & CRITICAL PATH

```
BLOCKING DEPENDENCY (only one):
─────────────────────────────────
Phase 2A (egress controls + intent verification)
         ↓ (complete by Jul 31, 2027)
         ↓
Phase 2B Weeks 1-9 (federal framework + regional variants)
         ↓ (complete by mid-Sep 2027)
         ↓
Phase 2B Weeks 10-12 (production hardening + pilot prep)
         ↓ (complete by Sep 30, 2027)
         ↓
Phase 3 (Production rollout, Oct 2027+)

CRITICAL PATH (Weeks 1-9):
───────────────────────────
Week 1-2: Consensus algorithm (gates all regional variants)
Week 3-4: Regional variants (gate MCP layer)
Week 5: MCP communication (gate L8 ledger)
Week 6-7: L8 cross-region ledger (gate integration)
Week 8: Full L1→L8 integration + RAGAS
Week 9: Performance testing + stress test

NO OTHER BLOCKERS: All tracks can execute in parallel after Week 2
```

---

## 11. DELIVERABLES SUMMARY

| Component | Format | Size | Owner | Status |
|-----------|--------|------|-------|--------|
| Consensus algorithm | Rust + pseudocode | 1500+ LOC | Engineer | Design spec complete |
| Regional L1-L3 variants | YAML + Rust | 1200+ LOC | Engineer | Config templates ready |
| MCP servers (consensus_gateway, ledger_sync) | Rust | 800+ LOC | Engineer | Protocol spec ready |
| L8 Merkle ledger extension | Rust | 600+ LOC | Engineer | Design ready |
| E2E integration tests | Rust tests | 400+ LOC | Engineer | Test framework ready |
| Regional deployment guides | Markdown | 500+ lines | Engineer | To be written Week 10-11 |
| Performance benchmark report | JSON + markdown | 50+ pages | Engineer | Baseline will be Week 9 |
| Security audit report | Markdown | 30+ pages | Engineer | To be written Week 12 |

**Total Phase 2B:** 5500+ LOC, 100+ pages documentation, 9 weeks implementation

---

## 12. APPENDIX: CONSENSUS PSEUDOCODE

```python
def consensus_voting(decision_id, source_region_vote):
    """
    Three-region consensus algorithm.
    Returns: (consensus_result, tally, merkle_root, audit_log)
    """
    
    # Phase 1: Collect votes from all regions
    votes = {source_region: source_region_vote}
    for peer_region in PEER_REGIONS:
        if peer_region == source_region:
            continue
        vote = request_vote_from(peer_region, decision_id)
        if vote is not None:
            votes[peer_region] = vote
        else:
            votes[peer_region] = "ABSTAIN"  # Timeout = abstain
    
    # Phase 2: Count votes
    approve_count = sum(1 for v in votes.values() if v.vote == "APPROVE")
    reject_count = sum(1 for v in votes.values() if v.vote == "REJECT")
    abstain_count = sum(1 for v in votes.values() if v.vote == "ABSTAIN")
    total_regions = len(votes)
    
    # Phase 3: Determine consensus
    if total_regions == 1:
        # Single region: local decision only
        consensus_result = source_region_vote.vote
        tally = "1/1"
    elif total_regions == 2:
        # Two regions: both must agree
        if approve_count == 2:
            consensus_result = "APPROVE"
            tally = "2/2"
        elif reject_count == 2:
            consensus_result = "REJECT"
            tally = "2/2"
        else:
            # Tie: escalate to human review
            consensus_result = "ESCALATE"
            tally = f"{approve_count}/{total_regions}"
    else:
        # Three+ regions: majority (2/3) wins
        if approve_count >= 2:
            consensus_result = "APPROVE"
            tally = f"{approve_count}/{total_regions}"
        elif reject_count >= 2:
            consensus_result = "REJECT"
            tally = f"{reject_count}/{total_regions}"
        else:
            # No majority: escalate
            consensus_result = "ESCALATE"
            tally = f"{approve_count} approve, {reject_count} reject, {abstain_count} abstain"
    
    # Phase 4: Conflict detection
    if total_regions >= 3:
        confidences = [v.confidence for v in votes.values()]
        confidence_diff = max(confidences) - min(confidences)
        if confidence_diff > 10.0:  # Threshold: 10 percentage points
            log_conflict_alert(decision_id, votes, confidence_diff)
    
    # Phase 5: Generate merkle proof
    ledger_entries = [v.signature for v in votes.values()]
    merkle_root = hash(ledger_entries + previous_root)
    
    # Phase 6: Audit log
    audit_log = {
        "decision_id": decision_id,
        "votes": {k: {"vote": v.vote, "confidence": v.confidence} for k, v in votes.items()},
        "consensus_result": consensus_result,
        "tally": tally,
        "merkle_root": merkle_root,
        "timestamp": now_utc(),
    }
    
    return consensus_result, tally, merkle_root, audit_log
```

---

**Document Version:** 2.0  
**Last Updated:** 2027-07-01  
**Author:** SovereignNexus Phase 2B Architecture Team  
**Approval:** Required before Week 1 implementation  

**Next Steps:**
1. Finalize consensus algorithm (review pseudocode)
2. Define MCP protocol (consensus_gateway, ledger_sync servers)
3. Create regional policy templates (EU/US/China)
4. Set up development environment (3 Kubernetes clusters)
5. Begin Week 1 implementation (Sep 1, 2027)
