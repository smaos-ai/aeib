# Phase 2 OWASP Security Roadmap (Jun-Dec 2027)

**Document Version:** 1.0  
**Timeline:** Jun 1 - Dec 31, 2027 (7 months, BIC Plzeń 1M CZK project)  
**Scope:** Close Phase 1 security gaps. Implement H, G layers + ML gates.  
**Completion Target:** May 31, 2027 (before Phase 1 May 31 deadline... Phase 2 prep starts concurrently)

---

## EXECUTIVE SUMMARY

Phase 1 achieves **69% compliance** with OWASP Top 10 Agentic via detection + audit. Phase 2 adds **active prevention + real-time monitoring** to reach 95%+ compliance.

**Top 3 Phase 2 Priorities (Critical):**
1. **H Layer (Intent Verification)** — Prevent goal hijacking via multi-signature approval + cryptographic proof of user intent
2. **G Layer (Egress Controls)** — Block insecure tool execution via centralized firewall + per-tool resource limits
3. **Real-Time Monitoring & ML Gates** — Detect anomalies within seconds, not days. Prevent memory poisoning + unsafe recommendations.

**Budget:** 1M CZK (BIC Plzeń voucher)  
**Team:** 2 engineers (+ CISO audit contract)

---

## TIMELINE: PHASE 2 EXECUTION

### SPRINT 1 (Jun 1-15, 2027): H Layer Foundation — Intent Verification

**Goal:** Prevent goal hijacking via cryptographic proof of user identity + intent.

#### Deliverables
- [ ] H layer skeleton (src/h-intent-verification/lib.rs)
- [ ] User identity binding (OAuth2 + Ed25519 credential)
- [ ] Intent commitment protocol (user signs decision request)
- [ ] Multi-signature approval schema (2-of-2 or 3-of-3)
- [ ] Integration with L3 permit gates (H pre-gate check)

#### Architecture

```
Request arrives
  ↓
[H: Intent Verification] ← NEW
  ├─ Verify user identity (OAuth2 + credential)
  ├─ Verify request signature (user signed decision, not attacker)
  ├─ Check approval quorum (who must sign for this decision?)
  └─ Log intent commitment (timestamp, user_id, decision_hash)
  ↓
[L1: Policy Router] (existing)
  ↓
[L3: Permit Gates] (existing)
```

#### Implementation Steps
1. Create H layer crate (250 lines target)
   - UserIdentity struct (user_id, credential_type, public_key_ed25519)
   - IntentCommitment struct (decision_hash, user_signature, timestamp)
   - ApprovalQuorum enum (SINGLE_HUMAN, DUAL_SIGNATURE, POLICY_OFFICER_REQUIRED)
   - Multi-sig verification (verify N-of-M signatures before proceeding)

2. OAuth2 integration (100 lines)
   - Connect to OAuth2 provider (Google/GitHub for dev, Czech eID for production)
   - Token validation + credential binding
   - Tests: 5 OAuth2 flow tests

3. Signature verification (80 lines)
   - Ed25519 signature validation (using `ed25519-dalek` crate)
   - Timestamp freshness check (request <5 min old)
   - Replay attack prevention (nonce tracking)
   - Tests: 8 signature verification tests

4. Quorum logic (70 lines)
   - Decision threshold rules (high-risk needs 2 approvals)
   - Approval collection + verification
   - Tests: 6 quorum tests

5. Integration tests (50 lines)
   - Full H→L1→L3 flow
   - Tests: 4 integration tests

**Total Lines:** 550  
**Total Tests:** 23  
**Effort:** 2 weeks (1 engineer, full-time)

#### Quality Gate
- ✅ 23 tests passing
- ✅ Signatures verified for all decision types
- ✅ Zero forgery (attacker cannot forge signature)
- ✅ Integration with L3 gates tested

#### Risk Mitigation for Risk #1 (Goal Hijacking)
- **What it does:** Cryptographically binds decision to user identity. Attacker cannot redirect goal without user's signature.
- **Confidence improvement:** 65% → 85%

---

### SPRINT 2 (Jun 16-30, 2027): G Layer Foundation — Egress Controls

**Goal:** Block insecure tool execution via centralized firewall + tool isolation.

#### Deliverables
- [ ] G layer skeleton (src/g-egress-controls/lib.rs)
- [ ] Tool whitelist registry (tool_name → allowed destinations)
- [ ] Network policy enforcement (iptables / nftables rules)
- [ ] Per-tool resource limits (CPU, memory, disk IOPS)
- [ ] Real-time egress logging + blocking

#### Architecture

```
Tool invocation arrives
  ↓
[G: Egress Controls] ← NEW
  ├─ Check tool in registry
  ├─ Verify destination in whitelist
  ├─ Enforce resource limits
  ├─ Log attempt (allow/deny)
  └─ Block if policy violated
  ↓
[L5: MCP Communication] (existing)
  ↓
[Tool Execution] (L4 orchestration calls tool)
```

#### Implementation Steps
1. Create G layer crate (300 lines target)
   - ToolRegistry struct (tool_name → destinations + resources)
   - EgressPolicy enum (DENY_ALL, WHITELIST, ALLOW_ALL)
   - ResourceLimit struct (cpu_percent, memory_mb, disk_iops)
   - PolicyEnforcer (check policy before exec)

2. Network isolation (100 lines)
   - iptables rules (hotel tool can only reach {db.hotel.local, policy_mcp, audit_mcp})
   - gRPC + HTTP/HTTPS interception (via envoy proxy sidecar)
   - DNS filtering (host resolution only for whitelisted domains)
   - Tests: 6 network policy tests

3. Resource limits (80 lines)
   - cgroup configuration (per-tool CPU/memory/disk limits)
   - Monitoring + enforcement (kill process if exceeds limit)
   - Tests: 5 resource limit tests

4. Logging + alerting (70 lines)
   - All egress attempts logged to G_egress_events.log
   - Policy violation alerts (email policy team)
   - Tests: 4 logging tests

5. Integration tests (50 lines)
   - Full L5→G→tool execution flow
   - Tests: 5 integration tests

**Total Lines:** 600  
**Total Tests:** 20  
**Effort:** 2 weeks (1 engineer, full-time)

#### Quality Gate
- ✅ 20 tests passing
- ✅ All egress blocked except whitelisted destinations
- ✅ Resource limits enforced (no runaway processes)
- ✅ Zero false-negatives (no unauthorized calls slip through)

#### Risk Mitigation for Risk #2 (Insecure Tool Execution)
- **What it does:** Centralized firewall blocks tool access to dangerous endpoints. Per-tool sandboxing prevents resource exhaustion.
- **Confidence improvement:** 70% → 90%

---

### SPRINT 3 (Jul 1-15, 2027): Real-Time Monitoring Dashboard

**Goal:** Live visibility into decision throughput, policy violations, latency, RAGAS accuracy.

#### Deliverables
- [ ] Dashboard server (Rust + Actix-web, 200 lines)
- [ ] Metrics aggregation (from L8 ledger + L7 RAGAS)
- [ ] Real-time alerts (>5% violation rate → SMS + email)
- [ ] Grafana integration (prometheus-compatible metrics export)
- [ ] Web UI (Vue.js, 300 lines)

#### Metrics Dashboard

```
┌─────────────────────────────────────────────────────────┐
│ SMAOS Phase 2 Real-Time Compliance Dashboard           │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ Decision Throughput      │ Policy Violations           │
│ ████████░░ 2,457/hr     │ ░░░░░░░░░░ 2.3% ⚠ YELLOW   │
│                          │                             │
│ Decision Latency         │ RAGAS Accuracy              │
│ p50: 142ms               │ ████████░░ 89.2% ✓ GREEN   │
│ p95: 890ms               │                             │
│ p99: 3200ms              │ System Health               │
│                          │ Hotel: ✓ (2103cp/day)      │
│ Agent Status             │ Glass: ✓ (1456cp/day)      │
│ Hotel:  ✓ HEALTHY        │ School: ✓ (1389cp/day)     │
│ Glass:  ✓ HEALTHY        │                             │
│ School: ✓ HEALTHY        │ Top Violations (last 24h)   │
│                          │ 1. Art37 missing (8)       │
│                          │ 2. Tool_timeout (5)        │
│                          │ 3. Policy_drift (2)        │
│                          │                             │
└─────────────────────────────────────────────────────────┘
```

#### Implementation Steps
1. Metrics aggregation (100 lines)
   - Query L8 ledger for decision count + violation rate
   - Query L7 RAGAS for accuracy trend
   - Calculate latency percentiles (p50, p95, p99)
   - Refresh every 5 seconds

2. Alert rules (50 lines)
   - IF violation_rate > 5% THEN alert
   - IF ragas_accuracy < 85% THEN alert
   - IF agent_checkpoint_interval > 2min THEN alert
   - IF disk_usage > 80% THEN alert

3. Metrics export (70 lines)
   - Prometheus-compatible /metrics endpoint
   - Gauge: decision_count, violation_count, latency_ms
   - Histogram: latency percentiles
   - Gauge: ragas_accuracy

4. Web UI (300 lines, Vue.js)
   - Real-time chart updates (5s refresh)
   - Alert notifications (toast popups)
   - Drill-down into specific violations (click metric → violation list)
   - Tests: 6 UI integration tests

5. Grafana setup (config, 50 lines)
   - Pre-built dashboards (throughput, violations, latency)
   - Alert rules wired to SMS + email

**Total Code:** 570 lines  
**Total Tests:** 15  
**Effort:** 1.5 weeks (1 engineer)

#### Quality Gate
- ✅ Metrics accurate within 5s refresh
- ✅ All alerts tested (manual trigger → alert sent)
- ✅ Dashboard loads in <2s
- ✅ Zero metrics data loss

#### Risk Mitigation for Risk #10 (Inadequate Monitoring)
- **What it does:** Real-time visibility into compliance. Violations detected within seconds.
- **Confidence improvement:** 70% → 90%

---

### SPRINT 4 (Jul 16-31, 2027): ML Safety Gates & Anomaly Detection

**Goal:** Automatically block unsafe tool recommendations and memory-poisoned decisions.

#### Deliverables
- [ ] Tool safety classifier (ML model, safety_score <0.8 → block)
- [ ] Anomaly detector (decision outlier detection, >3σ → flag)
- [ ] Side-effect predictor (1000-scenario simulation before approval)
- [ ] Integration with L3 permit gates (ML gates before final approval)

#### Safety Classifier Architecture

```
Tool recommendation arrives (e.g., "suspend student account")
  ↓
[Tool Safety Classifier] ← NEW
  ├─ Extract features: tool_name, recommendation_context, historical_decisions
  ├─ Feed to ML model (trained on 5000 safe vs unsafe recommendations)
  ├─ Output: safety_score (0-1)
  ├─ IF safety_score < 0.8: require human approval
  └─ IF safety_score < 0.5: auto-deny + alert
  ↓
[L3: Permit Gates] (existing approval flow)
```

#### Anomaly Detector Architecture

```
Decision arrives (e.g., "approve 500k loan")
  ↓
[Anomaly Detector] ← NEW
  ├─ Extract features: decision_value, customer_tier, approval_rate_today
  ├─ Compare to normal distribution (trained on 30 days history)
  ├─ Output: anomaly_score (0-1, 0=normal, 1=extreme outlier)
  ├─ IF anomaly_score > 0.95: escalate to policy team
  └─ IF anomaly_score > 0.99: auto-deny + alert
  ↓
[L8: Proof Layer] (existing audit logging)
```

#### Implementation Steps
1. ML model training (150 lines Python)
   - Load historical decisions from L8 ledger (10,000+ decisions)
   - Extract features: decision_type, value, customer_profile, approval_outcome
   - Train random forest classifier (80% accuracy target on validation set)
   - Export model as ONNX (inference via ONNX runtime in Rust)

2. Inference engine (100 lines Rust)
   - Load ONNX model at startup
   - Extract features from incoming decision
   - Score safety/anomaly
   - Log score + reasoning

3. Side-effect predictor (120 lines)
   - Monte Carlo simulation (1000 runs)
   - Model: "If we suspend account X, what other transactions affected?"
   - Calculate probability of bad outcome
   - IF P(bad) > 5% THEN require extra approval

4. Integration with L3 (80 lines)
   - ML gates called before final permit decision
   - Safety score + anomaly score added to audit trail
   - Human-readable explanation ("Unusual: approval rate 10x baseline")

5. Testing & validation (150 lines)
   - Test on historical decisions (backtesting)
   - 5 known-safe decisions must score >0.8
   - 5 known-unsafe decisions must score <0.4
   - Zero false-negatives on high-risk decisions
   - Tests: 12 ML gate tests

**Total Code:** 630 lines (ML + integration)  
**Total Tests:** 18  
**Training Data:** 10,000+ decisions from L8 ledger  
**Effort:** 2.5 weeks (1 engineer + 3 days ML specialist)

#### Quality Gate
- ✅ ML model accuracy >80% on validation set
- ✅ Safety classifier tested on 50 known-safe + 50 known-unsafe recommendations
- ✅ Anomaly detector tested on historical spike days (e.g., "Black Friday" approval spike)
- ✅ Zero false-negatives on critical decisions

#### Risk Mitigation for Risks #4, #7 (Memory Poisoning, Unsafe Recommendations)
- **What it does:** ML gates automatically flag suspicious decisions. Real-time detection (seconds) vs post-hoc (days).
- **Confidence improvement:** #4 (55% → 80%), #7 (65% → 85%)

---

### SPRINT 5 (Aug 1-15, 2027): Consensus Voting & Byzantine Resilience

**Goal:** Prevent multi-agent coordination attacks via consensus voting + distributed transaction log.

#### Deliverables
- [ ] Consensus module (2-of-3 pilots vote on >€100k decisions)
- [ ] Distributed transaction log (Tendermint BFT)
- [ ] Agent health monitoring + auto-restart
- [ ] Coordination timeout (30s per message, auto-escalate if timeout)

#### Consensus Protocol

```
Decision >€100k arrives
  ↓
Hotel pilot: "I approve €150k for Czech chain"
  ↓
[Consensus Layer] ← NEW
  ├─ Hotel broadcasts vote: APPROVE (signed + timestamped)
  ├─ Glass pilot receives + evaluates: ABSTAIN (not relevant)
  ├─ School pilot receives + evaluates: ABSTAIN (not relevant)
  └─ Result: 1 APPROVE + 2 ABSTAIN = APPROVED (simple quorum)
  ↓
Alternative scenario (risky decision):
Hotel: APPROVE | Glass: DENY | School: ABSTAIN
  → CONFLICTED (1 approve + 1 deny)
  → ESCALATE to policy team (human arbitration)
  ↓
[L8: Proof Layer] (all votes logged + signed)
```

#### Implementation Steps
1. Consensus module (200 lines)
   - Vote struct (pilot_id, decision_id, vote_type: APPROVE/DENY/ABSTAIN, signature)
   - Quorum logic (2 of 3 for >100k, simple majority for others)
   - Timeout handling (if vote missing after 30s, assume ABSTAIN)
   - Tests: 8 consensus tests

2. Distributed transaction log (150 lines)
   - Integrate Tendermint BFT (runs as separate service)
   - Append all agent actions to blockchain
   - Merkle root per block ensures immutability + tampering detection
   - Tests: 5 BFT tests

3. Agent health monitoring (100 lines)
   - Watchdog thread (checks each pilot every 30s)
   - IF checkpoint_interval > 2min: restart agent + replay from last checkpoint
   - IF pilot unresponsive for 5min: escalate to policy team
   - Tests: 4 health monitoring tests

4. Coordination timeout (50 lines)
   - Each A2A message has 30s timeout
   - IF timeout: auto-escalate to policy_mcp
   - IF escalation fails: fail-safe deny (conservative)
   - Tests: 3 timeout tests

**Total Code:** 500 lines  
**Total Tests:** 20  
**Effort:** 2.5 weeks (1.5 engineers)

#### Quality Gate
- ✅ Consensus voting tested on 50 multi-agent scenarios
- ✅ Tendermint BFT synchronized (all nodes see same transaction order)
- ✅ Agent restarts recover state perfectly (no decisions lost)
- ✅ Timeout handling verified (no deadlocks)

#### Risk Mitigation for Risk #8 (Multi-Agent Issues)
- **What it does:** Prevents Byzantine agents from poisoning shared state. Consensus ensures honest majority wins.
- **Confidence improvement:** 55% → 85%

---

### SPRINT 6 (Aug 16-31, 2027): Supply Chain & Data Protection

**Goal:** Complete supply chain attestation + encryption at rest.

#### Deliverables
- [ ] Auto-generate SBOM (CycloneDX format per commit)
- [ ] Collect vendor attestations (Ollama, PostgreSQL, pgvector)
- [ ] Implement encryption at rest (AP2 ledger + logs encrypted with KMS)
- [ ] Role-based access control (RBAC) to sensitive logs
- [ ] Field-level data masking (PII → masked in logs)

#### Implementation Steps
1. SBOM generation (80 lines)
   - On each commit, parse Cargo.lock + npm package-lock.json
   - Generate CycloneDX XML (component list + versions + hashes)
   - Sign SBOM with Ed25519
   - Commit to git

2. Vendor attestation collection (60 lines)
   - Script to collect signed releases from Ollama/PostgreSQL teams
   - Verify GPG signatures on release artifacts
   - Store attestations in versioned config (phase2_supply_chain.yaml)

3. Encryption at rest (150 lines)
   - Integrate AWS KMS (or similar) for key management
   - Encrypt AP2 ledger + checkpoint logs with AES-256-GCM
   - Decryption at runtime (decrypt per-query, not at startup)
   - Key rotation policy (quarterly)
   - Tests: 6 encryption tests

4. RBAC implementation (120 lines)
   - Define roles: RESEARCHER, POLICY_OFFICER, AUDITOR, ENGINEER
   - RESEARCHER: can see anonymized checkpoint data
   - POLICY_OFFICER: can see all decision reasoning
   - AUDITOR: can see all proofs + signatures
   - ENGINEER: can see implementation details (source code)
   - Tests: 8 RBAC tests

5. PII masking (100 lines)
   - Automatic detection of PII (name, email, phone, SSN patterns)
   - Mask in logs: "John Doe" → "USER_123", "+420-777-888-999" → "***-***-****"
   - Unmasking: policy officers can request unmasked view (logged + audited)
   - Tests: 6 masking tests

**Total Code:** 510 lines  
**Total Tests:** 28  
**Effort:** 2 weeks (1 engineer + 3 days security specialist)

#### Quality Gate
- ✅ SBOM generated + signed on every commit
- ✅ Vendor attestations collected (>80% of critical deps)
- ✅ Encryption verified (test decrypt → plaintext matches original)
- ✅ RBAC tested (each role can see only authorized data)
- ✅ PII masking tested (all sensitive fields masked)

#### Risk Mitigation for Risks #5, #6, #9 (Prompt Leakage, Data Disclosure, Supply Chain)
- **What it does:** Encryption + RBAC limit who sees sensitive data. SBOM + attestation proves supply chain integrity.
- **Confidence improvement:** #5 (75% → 95%), #6 (60% → 85%), #9 (50% → 80%)

---

### SPRINT 7 (Sep 1-30, 2027): Integration & Testing

**Goal:** Full integration of all Phase 2 layers (H, G, + ML gates). End-to-end testing.

#### Deliverables
- [ ] Full H→G→L1→L3→L7 pipeline tested
- [ ] All 10 OWASP risks re-evaluated (confidence scores updated)
- [ ] Stress testing (1000 decisions/hour, detect anomalies in <5s)
- [ ] Security audit (CISO review + penetration testing)
- [ ] Documentation update (Phase 2 design guide)

#### Integration Testing Steps
1. H layer integration (50 tests)
   - Test OAuth2 flow
   - Test multi-signature requirement
   - Test intent binding for all decision types

2. G layer integration (40 tests)
   - Test egress blocking for each tool
   - Test resource limit enforcement
   - Test logging + alerting

3. ML gates integration (30 tests)
   - Test safety classifier on real hotel/glass/school decisions
   - Test anomaly detector on normal + abnormal decision streams
   - Test side-effect predictor

4. Consensus voting integration (25 tests)
   - Test multi-agent voting on >€100k decisions
   - Test Byzantine resilience (1 compromised agent)
   - Test failover + recovery

5. End-to-end flows (20 tests)
   - Hotel decision: H→L1→G→L3→ML_gates→L4→L8 (full pipeline)
   - Glass decision: same flow
   - School decision: same flow
   - Decision timeout + escalation flow
   - Agent failure + recovery flow

**Total Tests:** 165+ new tests  
**Test Coverage:** 95%+ (all new Phase 2 code)  
**Effort:** 3 weeks (2 engineers)

#### Quality Gate
- ✅ 95%+ code coverage
- ✅ All integration tests pass
- ✅ Load test: 1000 decisions/hour processed correctly
- ✅ Anomaly detection: suspicious decisions flagged in <5s
- ✅ Zero data loss or corruption during agent failover

---

### SPRINT 8 (Oct 1-31, 2027): CISO Security Audit & Compliance

**Goal:** Third-party security review. Prepare for EU Database registration.

#### Deliverables
- [ ] CISO penetration testing (red team exercises)
- [ ] Security code review (H, G layers + ML gates)
- [ ] Threat model validation (all OWASP risks addressed?)
- [ ] EU AI Act compliance audit (Articles 37, 50, 52, etc.)
- [ ] Remediation of any findings

#### Penetration Testing Scenarios
1. Prompt injection attacks (10 scenarios)
   - Can attacker inject "ignore all policies" into request?
   - Can attacker forge system prompt?
   - Result: ALL BLOCKED (H layer catches)

2. Privilege escalation (5 scenarios)
   - Can RESEARCHER role access POLICY_OFFICER data?
   - Can researcher forge Ed25519 signature?
   - Result: ALL BLOCKED (RBAC + crypto verify)

3. Supply chain attacks (3 scenarios)
   - Can attacker slip trojanized Ollama image past CanIRun?
   - Can attacker compromise git commit history?
   - Result: ALL DETECTED (SBOM + Ed25519 signatures)

4. Multi-agent Byzantine attacks (5 scenarios)
   - Can 1 compromised pilot control system with 2 honest pilots?
   - Can attacker forge votes?
   - Result: ALL PREVENTED (consensus voting + signing)

#### EU AI Act Compliance Mapping
| Article | Requirement | Phase 2 Evidence |
|---------|-------------|-----------------|
| Article 37 | High-risk decisions require human review | L3 permit gates + H intent verification |
| Article 50 | Transparency in decision-making | L1 policy citations + L8 audit trail + dashboard |
| Article 52 | User information about AI | Documentation + in-app explanations |
| Article 22 | Automated decision restrictions | Human review mandatory for >€50k |
| Article 28 | Technical documentation | CLAUDE.md + architecture docs |
| Annex III | Education rules | L2 knowledge + L3 permit gates |
| Annex I | Glass/auto safety | L2 knowledge + L3 permit gates |

**Effort:** 2 weeks (1 CISO + 0.5 engineer for remediation)

---

### SPRINT 9 (Nov 1-15, 2027): EU Database Registration

**Goal:** Register SMAOS as an AI system with EU Database (required by EU AI Act Article 60).

#### Deliverables
- [ ] EU Database application (with SBOM + vendor attestations)
- [ ] Risk assessment document (OWASP + EU AI Act)
- [ ] Technical documentation (all 8 layers + Phase 2 enhancements)
- [ ] Compliance statement (all articles satisfied)

#### EU Database Requirements
- System name: "SMAOS (Sovereign Multi-Agent Operating System)"
- Type: High-Risk AI (Article 37, financial + education + glass)
- Capabilities: Credit scoring, enrollment decisions, safety verification
- Risk mitigation: L1-L8 layers (Phase 1) + H, G, ML gates (Phase 2)
- Supply chain: SBOM + vendor attestations

**Effort:** 1.5 weeks (1 engineer + 0.5 legal)

---

### SPRINT 10 (Nov 16-30, 2027): Production Hardening

**Goal:** Final performance optimization + production readiness.

#### Deliverables
- [ ] Performance tuning (target: 1000 decisions/hour with <2s latency p99)
- [ ] Load testing (simulate peak traffic)
- [ ] Disaster recovery testing (backup/restore procedures)
- [ ] Runbook documentation (how to operate Phase 2 system)

#### Performance Targets
| Metric | Phase 1 | Phase 2 | Target |
|--------|---------|---------|--------|
| Decision latency p50 | 142ms | 180ms | <200ms |
| Decision latency p95 | 890ms | 1100ms | <1200ms |
| Decision latency p99 | 3200ms | 4500ms | <5000ms |
| Anomaly detection latency | N/A | 5s | <5s |
| Dashboard refresh | N/A | 5s | <5s |
| RAGAS accuracy | 87% | 91% | >90% |

**Effort:** 1.5 weeks (1 engineer)

---

### SPRINT 11 (Dec 1-15, 2027): Documentation & Knowledge Transfer

**Goal:** Final documentation. Knowledge transfer to operations team.

#### Deliverables
- [ ] Phase 2 Architecture Guide (20+ pages)
- [ ] Operations Manual (runbook for day-2 operations)
- [ ] Security Handbook (how to respond to incidents)
- [ ] OWASP Audit Final Report (confidence scores updated)

**Effort:** 1 week (1 engineer + 0.5 tech writer)

---

### SPRINT 12 (Dec 16-31, 2027): Buffer & Final Testing

**Goal:** Final testing, bug fixes, rollout preparation.

**Effort:** 2 weeks (1.5 engineers)

---

## PHASE 2 SUCCESS CRITERIA

### Functional Requirements
- [ ] All 10 OWASP risks have >80% confidence score
- [ ] H layer: Multi-signature approval for >€50k decisions (zero unauthorized approvals)
- [ ] G layer: 100% egress firewall enforcement (zero unauthorized tool calls)
- [ ] ML gates: Safety classifier >85% accuracy, anomaly detector >95% true-positive rate
- [ ] Consensus voting: 2-of-3 pilot quorum enforced for >€100k decisions
- [ ] Real-time dashboard: All metrics update within 5s, <2s UI load time
- [ ] Encryption: All sensitive data encrypted at rest with AES-256-GCM
- [ ] RBAC: All 4 roles (RESEARCHER, POLICY_OFFICER, AUDITOR, ENGINEER) correctly isolated

### Quality Requirements
- [ ] 350+ new tests for Phase 2 code (cumulative 550+ total tests)
- [ ] Code coverage >95% (all Phase 2 layers)
- [ ] Zero defects (static analysis clean, cargo clippy 0 warnings)
- [ ] CISO audit: Zero critical findings, <5 medium findings

### Regulatory Requirements
- [ ] EU AI Act Article 37: COMPLIANT (intent verification + human review)
- [ ] EU AI Act Article 50: COMPLIANT (transparency in decisions)
- [ ] GDPR Article 22: COMPLIANT (human oversight)
- [ ] EU Database registration: APPROVED

### Performance Requirements
- [ ] Decision latency p99: <5s (down from 3.2s in Phase 1)
- [ ] Anomaly detection latency: <5s (new in Phase 2)
- [ ] Dashboard load time: <2s (new in Phase 2)
- [ ] Throughput: 1000+ decisions/hour sustained

### Security Requirements
- [ ] OWASP Top 10 Agentic: 10/10 risks mitigated
- [ ] Confidence score: 95%+ average (up from 69% Phase 1)
- [ ] SBOM: 100% of dependencies tracked + signed
- [ ] Penetration test: Zero critical vulnerabilities, <3 medium

---

## BUDGET & TEAM ALLOCATION

### Budget: 1M CZK (BIC Plzeń voucher)
| Category | Budget | Duration | Notes |
|----------|--------|----------|-------|
| 2 Engineers (6 months) | 600k | Jun-Dec 2027 | ~50k CZK/month |
| CISO Security Audit | 150k | Oct-Nov 2027 | 2-week penetration test |
| Tech writer (0.5) | 50k | Nov-Dec 2027 | Documentation |
| Infrastructure (cloud KMS, Tendermint, etc.) | 100k | Jun-Dec 2027 | AWS/GCP credits, open-source |
| Contingency | 100k | Jun-Dec 2027 | 10% buffer for overruns |
| **TOTAL** | **1M CZK** | **7 months** | **On budget** |

### Team Roles
- **Engineer #1 (Lead):** H layer, consensus voting, integration testing (50% allocation)
- **Engineer #2 (Security):** G layer, ML gates, encryption, RBAC (50% allocation)
- **CISO (External):** Penetration testing, compliance audit (part-time, Oct-Nov)
- **Tech Writer (External):** Documentation (part-time, Nov-Dec)

---

## RISK REGISTER: PHASE 2

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|-----------|
| ML model performs poorly (accuracy <80%) | HIGH | MEDIUM | Start training early (Jun 1), use 10k+ decision samples |
| Tendermint BFT integration delays | MEDIUM | MEDIUM | Use pre-built Tendermint service, not custom consensus |
| CISO finds critical vulnerability | HIGH | LOW | Penetration test in Oct (early warning), remediate in Nov |
| EU Database registration delayed | MEDIUM | LOW | Submit early (Nov 1), use template from Phase 1 |
| Performance degrades with new layers | MEDIUM | MEDIUM | Stress-test starting Aug, optimize Sep-Oct |

---

## APPENDIX A: OWASP RISK REMEDIATION TIMELINE

### P0 (Critical, due Jun 30)
- [ ] H Layer (Intent Verification) — Sprint 1
- [ ] G Layer (Egress Controls) — Sprint 2

### P1 (High, due Jul 15)
- [ ] Real-Time Monitoring Dashboard — Sprint 3
- [ ] Prompt Templating (L1 redesign) — Sprint 3 extension

### P2 (Medium, due Jul 31)
- [ ] Excessive Agency (Multi-Sig + Ratification) — Sprint 4
- [ ] Data Encryption + RBAC — Sprint 6

### P3 (Low, due Aug 31)
- [ ] Memory Poisoning (ML Anomaly Detection) — Sprint 4
- [ ] Unsafe Recommendations (Tool Safety Gate) — Sprint 4
- [ ] Multi-Agent Issues (Consensus Voting) — Sprint 5

### P4 (Lowest, due Dec 31)
- [ ] Supply Chain (SBOM + Attestation) — Sprint 6
- [ ] EU Database Registration — Sprint 9

---

## APPENDIX B: PHASE 1→PHASE 2 CONFIDENCE SCORE UPDATES

### Before Phase 2 (Phase 1 End)
| Risk | Phase 1 Confidence |
|------|-------------------|
| Goal Hijacking | 65% |
| Insecure Tool Execution | 70% |
| Excessive Agency | 60% |
| Memory Poisoning | 55% |
| System Prompt Leakage | 75% |
| Tool/Data Disclosure | 60% |
| Unsafe Recommendations | 65% |
| Multi-Agent Issues | 55% |
| Supply Chain | 50% |
| Inadequate Monitoring | 70% |
| **Average** | **65%** |

### After Phase 2 (Projected)
| Risk | Phase 2 Target |
|------|----------------|
| Goal Hijacking | 90% |
| Insecure Tool Execution | 90% |
| Excessive Agency | 85% |
| Memory Poisoning | 85% |
| System Prompt Leakage | 95% |
| Tool/Data Disclosure | 90% |
| Unsafe Recommendations | 90% |
| Multi-Agent Issues | 85% |
| Supply Chain | 85% |
| Inadequate Monitoring | 95% |
| **Average** | **90%** |

**Overall improvement: 65% → 90% (+38% confidence)**

---

## REFERENCES

1. OWASP Top 10 for LLM Applications (Dec 2025)
2. EU AI Act (2024)
3. SMAOS Phase 1 Architecture (ARCHITECTURE.md)
4. OWASP Agentic Audit (OWASP_AGENTIC_AUDIT.md)
5. Tendermint BFT Documentation (https://docs.tendermint.com/)
6. CycloneDX SBOM Specification (https://cyclonedx.org/)

