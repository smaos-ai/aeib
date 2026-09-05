# PHASE 2C: COMPLIANCE AUTOMATION SPECIFICATION
**Oct 1, 2027 - Dec 31, 2027 (16 weeks)**  
**Target:** €100M-€150M ARR via auto-generated regulatory dossiers + dynamic policy learning  
**Parallel:** Phase 2B design (Weeks 1-3 overlap)

---

## EXECUTIVE SUMMARY

Phase 2C automates regulatory compliance dossier generation at scale. Every decision made by SMAOS (2,200+ decisions/month Phase 1 baseline, 100M+ Phase 2B federated) flows into an immutable AP2 ledger, gets validated against governance policy, and feeds into monthly Annex III/IV auto-generation. A learned ML model adapts compliance policy to real decision patterns, reducing manual remediation by 94%.

**Deliverables:**
- **Auto-Annex III/IV Generator** (1200+ LOC): Month-end dossier assembly in <1 hour
- **Dynamic Policy Learning** (400+ LOC): ML model (Logistic Regression + Tree) learns from decisions  
- **Evidence Chain SDK** (300+ LOC): Merkle proof + KMS signature + regulatory submission
- **Multi-language Support** (200+ LOC): Czech, English, Chinese (Mandarin/Simplified)
- **RAGAS Compliance Validator** (300+ LOC): 50-question real-world compliance set (target 98%+ accuracy)
- **Regulatory Approval Engine** (200+ LOC): Pre-submission scoring, remediation suggestions

**Success Metrics:**
- Monthly dossier generation: 99%+ accuracy, <1 hour wall-clock time
- Regulatory approval rate: 98%+ first-pass (Annex III Dec 2, Annex I Aug 2 deadlines)
- Policy adaptation: ML model reaches 92%+ confidence on unseen decision patterns
- Cost per dossier: <€50 (compute + storage)
- Zero rejected submissions due to evidence quality

---

## 1. PRODUCT THESIS

SMAOS operates under three regulatory regimes:
1. **Annex III** (Hotels/Spas): Dec 2, 2027 deadline — transparency requirements
2. **Annex I** (Glass/Auto): Aug 2, 2028 deadline — pre-execution gates required
3. **Post-Annex:** CAC (China), SEC (US), FCA (UK) compliance variants

Today: Monthly dossiers = manual work (40 hours/operator). Phase 2C: Zero-manual dossiers. Every decision (action, intent, approval, result) is cryptographically signed, stored in AP2 ledger, and fed into compliance proof.

**Competitive Moat:** Only platform with:
- **Proof-as-first-class:** Decisions → Merkle tree → Ledger anchor → KMS signature
- **Dynamic Policy:** Real decisions teach governance rules (not vice versa)
- **Pre-submission accuracy:** 98%+ first-pass approval (regulators require <2% remediation)

---

## 2. ARCHITECTURE

### 2.1 Data Flow

```
┌──────────────────────────────────────────────────────────────────┐
│         SMAOS DECISION LIFECYCLE (Every L1→L8 flow)              │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  User Intent  → Policy Check (L1) → Tool Access (L3) → Action   │
│      ↓                ↓                   ↓                ↓     │
│  Decision ID  ← Approval (L4) ← Permit (L3) ← Audit (L8)        │
│                                                                   │
│  [ALL 8 LAYERS CAPTURED IN AP2 LEDGER]                           │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
                          ↓
                    AP2 Ledger Entry
                    (Merkle digest)
                          ↓
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
  Compliance Bin    Policy Analyzer   Evidence Aggregator
  (Categorize)      (Pattern learn)    (KMS sign)
        │                 │                 │
        └─────────────────┼─────────────────┘
                          ▼
                  Dossier Assembly
                  (Annex III/IV/I)
                          ▼
            Regulatory Submission (PDF + JSON)
```

### 2.2 Core Components

#### 2.2.1 Decision Capture (Enhanced L8)
```rust
pub struct Decision {
    id: Uuid,
    timestamp: DateTime<Utc>,
    agent_id: String,
    policy_rule: String,                    // L1 input
    tool_requested: String,                  // L3 gate
    tool_approved: bool,                     // L3 outcome
    reason_approved: String,                 // L4 justification
    action_taken: String,                    // Execution
    outcome_success: bool,
    merkle_proof: String,                    // Hash chain
    kms_signature: String,                   // Ed25519 PQC
}

pub struct DecisionBatch {
    decisions: Vec<Decision>,
    period: (DateTime<Utc>, DateTime<Utc>),
    batch_merkle_root: String,
    compliance_category: ComplianceCategory,  // Annex I/III/Other
}
```

#### 2.2.2 Policy Learning (NEW L9)
```rust
pub struct PolicyLearner {
    // Input: 100M decisions (Phase 2B federated)
    // Output: Policy probabilities (should decisions be approved?)
    
    model: LogisticRegressionModel,          // Fast, explainable
    features: [
        "tool_type" (embedding),
        "agent_experience_days",
        "policy_rule_index",
        "time_of_day_utc",
        "prior_approval_rate",
    ],
    
    confidence: f32,                         // 0.0-1.0
    last_retrain: DateTime<Utc>,
    accuracy_on_holdout: f32,                // Target 92%+
}

impl PolicyLearner {
    pub fn predict(&self, decision_context: &DecisionContext) -> (bool, f32) {
        // Returns: (should_approve, confidence)
    }
    
    pub fn retrain_weekly(&mut self, decisions: &[Decision]) -> MetricsReport {
        // Update model on new decisions
        // Target: retraining every Sunday 0200 UTC
    }
    
    pub fn explain(&self, decision: &Decision) -> ExplanationReport {
        // SHAP-style feature importance for regulatory audits
    }
}
```

#### 2.2.3 Dossier Assembly
```rust
pub struct RegulatoryDossier {
    // Annex III (Transparency) — Hotels/Spas (Dec 2, 2027)
    section_1: HighLevelRisk,                // Overall risk assessment
    section_2: DecisionFrequency,            // Monthly aggregate stats
    section_3: ToolAccessPatterns,           // Which tools accessed, how often
    section_4: PolicyViolations,             // 0 expected, but tracked
    section_5: AppealSuccessRate,            // Agent disputes (if any)
    section_6: IncidentLog,                  // Security/compliance incidents
    
    // Annex I (Pre-execution Gates) — Glass/Auto (Aug 2, 2028)
    section_7: PreExecutionGates,            // L3 permit accuracy
    section_8: RollbackLog,                  // Actions reversed (risk assessment)
    section_9: ComplianceTimeline,           // Weeks of compliance history
    
    // Shared
    evidence_root: String,                   // Merkle root of all decisions
    kms_signature: String,                   // Ed25519 signature
    submission_timestamp: DateTime<Utc>,
    pdf_rendered: Vec<u8>,                   // Pre-rendered PDF (no font subsetting issues)
    json_structured: Value,                  // Machine-readable JSON
}

impl RegulatoryDossier {
    pub fn generate_from_batch(batch: &DecisionBatch) -> Result<Self, ComplianceError> {
        // Takes 2,200+ decisions/month
        // Returns dossier ready for regulatory submission
        // Target: <60 seconds wall-clock time
    }
    
    pub fn validate_against_rules(rules: &PolicySet) -> ValidationReport {
        // Catches pre-submission errors (2% target)
    }
    
    pub fn suggest_remediation(&self) -> Vec<RemediationSuggestion> {
        // ML learns from regulatory feedback
        // Suggests improvements for next submission
    }
}
```

---

## 3. FEATURE BREAKDOWN (9 weeks implementation)

### WEEK 1-2: Evidence Chain (L8 Enhancement)
**Goal:** Merkle proof + KMS signature on every decision

| Component | LOC | Tests | Time | Deliverable |
|-----------|-----|-------|------|-------------|
| Decision capture (enhanced) | 280 | 12 | 4 days | Rust struct + serde |
| Merkle tree construction | 200 | 8 | 3 days | Incremental hash chain |
| KMS integration (Ed25519 PQC) | 120 | 6 | 2 days | Signing pipeline |
| Batch aggregation | 150 | 10 | 3 days | Merkle root + timestamp |

**Total:** 750 LOC, 36 tests, 5 days  
**Blockers:** None (independent from Phase 2B)

### WEEK 3-4: Policy Learning (L9)
**Goal:** ML model learns approval patterns

| Component | LOC | Tests | Time | Deliverable |
|-----------|-----|-------|------|-------------|
| Feature engineering | 220 | 14 | 4 days | Embedding + normalization |
| Logistic regression impl | 180 | 12 | 3 days | Training loop (no external ML lib — too heavy) |
| Weekly retraining loop | 140 | 8 | 2 days | Cron job + metrics logging |
| SHAP-style explanations | 160 | 10 | 3 days | Feature importance scoring |

**Total:** 700 LOC, 44 tests, 5 days  
**Blockers:** Requires Week 1-2 decision batch format

### WEEK 5-6: Multi-language Dossier
**Goal:** Annex III/IV/I template assembly + i18n

| Component | LOC | Tests | Time | Deliverable |
|-----------|-----|-------|------|-------------|
| Dossier struct + validation | 320 | 16 | 4 days | 9-section enum + serde JSON |
| Czech translation strings | 200 | 0 | 2 days | KARP compliance language |
| English + Mandarin i18n | 180 | 0 | 2 days | CAC + EU compliance regions |
| PDF rendering (headless) | 250 | 12 | 3 days | Zero font issues, fast |

**Total:** 950 LOC, 28 tests, 5 days  
**Blockers:** Needs Week 3-4 policy learning baseline

### WEEK 7: Dossier Generator
**Goal:** Month-end assembly, <1 hour execution

| Component | LOC | Tests | Time | Deliverable |
|-----------|-----|-------|------|-------------|
| Batch reader from ledger | 180 | 10 | 2 days | pgvector → DecisionBatch |
| Section 1-9 population | 280 | 18 | 3 days | Logic for each regulatory section |
| Merkle proof validation | 120 | 8 | 1 day | Spot-check evidence chain |
| KMS signing + hash finalization | 100 | 6 | 1 day | Ed25519 + commit to ledger |

**Total:** 680 LOC, 42 tests, 5 days  
**Blockers:** None (all upstream complete)

### WEEK 8: RAGAS Compliance Validator
**Goal:** 50-question test set, 98%+ accuracy

| Component | LOC | Tests | Time | Deliverable |
|-----------|-----|-------|------|-------------|
| 50-question golden set | 180 | 50 | 2 days | Real regulatory questions |
| Eval harness (LangSmith) | 120 | 50 | 2 days | Real-time scoring |
| Dossier answerer (LLM) | 240 | 50 | 2 days | Claude 3.5 (or local Qwen) |
| Accuracy tracking | 80 | 10 | 1 day | Weekly metrics dashboard |

**Total:** 620 LOC, 160 tests, 5 days  
**Blockers:** None (parallel with Week 7)

### WEEK 9: Regulatory Approval Engine
**Goal:** Pre-submission scoring + remediation suggestions

| Component | LOC | Tests | Time | Deliverable |
|-----------|-----|-------|------|-------------|
| Pre-submission checks | 200 | 14 | 2 days | 15-point checklist |
| Remediation suggestion ML | 160 | 12 | 2 days | Learned from regulatory feedback |
| Dashboard UI (CLI + web) | 280 | 8 | 2 days | Progress tracking |
| Integration test (full flow) | 120 | 20 | 1 day | End-to-end dossier generation |

**Total:** 760 LOC, 54 tests, 5 days  
**Blockers:** None

---

## 4. TECHNICAL DESIGN

### 4.1 Merkle Proof Chain

Every decision flows into an incremental Merkle tree:

```
Month N (Oct 1-31):
  Day 1: 100 decisions → Leaf 1-100
  Day 2: 98 decisions  → Leaf 101-198
  ...
  Day 31: 72 decisions → Leaf 2100-2172

                     ┌─ Root Hash (Oct)
                     │
           ┌─────────┼─────────┐
           │         │         │
      [Days 1-10]  [Days 11-20] [Days 21-31]
           │         │         │
      ┌────┼────┐ ┌──┼───┐   [...]
    [D1]  [D2]  [D3]  [D4]  [D5]
      │    │    │    │    │
    [Dec] [Dec] [Dec] [Dec] [Dec]  ← Individual signed decisions

Merkle Root (Oct) → KMS Signature → Regulatory Submission
```

### 4.2 Evidence Chain Validation

Regulators receive:
```json
{
  "dossier_id": "annex-iii-2027-10-01",
  "period": ["2027-10-01T00:00:00Z", "2027-10-31T23:59:59Z"],
  "merkle_root": "0x8a4f...",
  "kms_signature": "ed25519.sig.base64",
  "evidence_url": "https://smaos.io/verify/{merkle_root}",
  "sections": {
    "1_high_level_risk": { "value": 0.03, "confidence": 0.97 },
    "2_decision_frequency": { "approved": 2145, "rejected": 55 },
    "3_tool_access_patterns": { "hr_tools": 890, "finance": 234 },
    ...
  },
  "quality_score": 0.98,  // Pre-submission ML check
  "audit_trail_size_bytes": 234567890
}
```

Verification (regulator side):
```bash
curl https://smaos.io/verify/0x8a4f...
# Returns: "✅ Valid. 2172 decisions, merkle chain intact, KMS signature verified."
```

### 4.3 Policy Learning Integration

Weekly retraining:

```rust
// Sunday 0200 UTC, every week

pub async fn retrain_policy_model() {
    // Fetch all decisions from past 30 days (ledger)
    let decisions = ledger.fetch_batch(Duration::days(30)).await;
    
    // Extract features: agent experience, policy rules, tool types, time patterns
    let X: Matrix = decisions.iter()
        .map(|d| vec![
            normalize(d.tool_embeddings),
            d.agent_experience_days as f32 / 365.0,
            encode_rule_id(d.policy_rule),
            sin(d.timestamp.hour() as f32 * 2π / 24.0),  // Cyclical time
            d.prior_approval_rate as f32,
        ])
        .collect();
    
    // Labels: was decision approved?
    let y: Vec<f32> = decisions.iter()
        .map(|d| if d.approved { 1.0 } else { 0.0 })
        .collect();
    
    // Train logistic regression (closed-form: no epochs, O(n^2) matrix inversion)
    policy_model.fit(X, y, learning_rate=0.01, max_iters=100);
    
    // Validate on holdout set (20% of data)
    let accuracy = validate(&policy_model, &X_holdout, &y_holdout);
    
    // Log metrics
    metrics.log_policy_accuracy(accuracy);
    metrics.log_retrain_timestamp(Utc::now());
    
    // Persist model (msgpack for speed)
    persist_model_checkpoint(&policy_model).await;
}
```

Expected accuracy: 92%+ (i.e., model correctly predicts "approve/reject" on 92% of unseen decisions).

### 4.4 Dossier Generation Pipeline

```
┌─ Month-End Batch (2200+ decisions)
│
├─ Categorize by Annex Type
│  ├─ Annex III (Hotels/Spas): 1800 decisions
│  ├─ Annex I (Glass/Auto): 350 decisions
│  └─ Other: 50 decisions
│
├─ For each category:
│  ├─ Compute Section 1 (risk) → ML model.predict() over decisions
│  ├─ Compute Section 2 (frequency) → Counts + aggregates
│  ├─ Compute Section 3 (tool patterns) → Tool access heatmap
│  ├─ Compute Section 4 (violations) → Policy breaches (target: 0)
│  ├─ Compute Section 5 (appeals) → Dispute log
│  ├─ Compute Section 6 (incidents) → Security log
│  └─ [For Annex I only: Sections 7-9 pre-execution gates, rollbacks, timeline]
│
├─ Merkle Proof
│  ├─ Hash all 2200 decisions
│  ├─ Build incremental tree
│  └─ Root = Month's cryptographic digest
│
├─ KMS Signing
│  ├─ Sign root with Ed25519 (PQC-resistant)
│  └─ Attach signature to JSON + PDF
│
├─ Render PDF
│  ├─ Czech version (KARP compliance)
│  ├─ English version (EU standard)
│  └─ Chinese version (CAC compliance)
│
└─ Store + Submit
   ├─ Upload to regulatory portal (FTP/API)
   ├─ Log submission timestamp
   └─ Begin waiting for approval (target: <2 weeks)
```

**Time budget per phase:**
- Categorize: 5 sec
- Compute sections: 20 sec (parallel per section)
- Merkle proof: 30 sec
- KMS signing: 2 sec
- PDF render: 3 sec
- **Total: <60 seconds**

---

## 5. REGULATORY COMPLIANCE

### 5.1 Annex III (Dec 2, 2027)

**Requirement:** Transparency dossier for hotel booking systems

| Section | Data | Target | Implementation |
|---------|------|--------|-----------------|
| 1. Risk Assessment | Overall risk score (0-1) | <0.1 (low risk) | Policy model confidence |
| 2. Decision Freq | Approvals vs rejections | 95%+ approval rate | Decision count |
| 3. Tool Access | Which hotel features used | Heatmap | Tool registry |
| 4. Policy Compliance | Breaches detected | 0 | Permit gate check |
| 5. Appeal Rate | Disputes from agents | <2% | Ledger audit log |
| 6. Incident Log | Security/system issues | <1 per month | Audit trail |
| 7. (NEW) Model Accuracy | Policy learning confidence | 92%+ | Weekly retraining |
| 8. (NEW) Merkle Proof | Evidence chain | 100% integrity | Cryptographic digest |
| 9. (NEW) Submission Timestamp | Month-end proof | Exact UTC | Ledger anchor |

**Submission:** Every month (first business day). Target approval time: 2 weeks.

### 5.2 Annex I (Aug 2, 2028)

**Requirement:** Pre-execution gates for automotive/glass manufacturing

| Section | Data | Target | Implementation |
|---------|------|--------|-----------------|
| 1-6 | Same as Annex III | Same | Same |
| 7. Pre-exec Gates | Tool approval rates | 99.5%+ | L3 permit accuracy |
| 8. Rollback Log | Actions reversed | <0.1% of decisions | Execution ledger |
| 9. Timeline | 6+ months compliance history | Continuous | Merkle chain |

**Key constraint:** Pre-execution decision MUST be recorded before tool execution. No retroactive approval allowed.

### 5.3 Multi-Region Variants

**Czech (KARP):** Native language, GDPR compliance, CZK pricing  
**English (EU):** Standard EU language, GDPR, EUR pricing  
**Mandarin (CAC):** Simplified Chinese, CAC 3.0 alignment, CNY pricing

All three variants share identical data, differ only in language + regulatory footnotes.

---

## 6. SUCCESS METRICS

### 6.1 Quality Gates (Delivery)

- [ ] Evidence chain: 100% of decisions merkle-hashed + KMS-signed
- [ ] Policy model: 92%+ accuracy on holdout set (weekly retraining)
- [ ] Dossier generation: <60 second wall-clock time
- [ ] RAGAS compliance: 98%+ accuracy on 50-question golden set
- [ ] Regulatory approval: 98%+ first-pass (May 2028 baseline)

### 6.2 Revenue Metrics

| Metric | Baseline (Phase 2B) | Phase 2C Target | Path to €100M |
|--------|-----------------|-----------------|-----------------|
| ARR | €50M | €100M-€150M | -100% costs + 3x volume |
| Dossiers/month | 200 (manual) | 500 (auto) | 5x volume growth |
| Cost per dossier | €400 (operator time) | €25 (compute) | 94% margin gain |
| Regional variants | 1 (Czech) | 3 (Czech/EN/CN) | TAM expansion 3x |
| Approval rate | 92% | 98% | Reduced remediation cost |

### 6.3 Operational Metrics

| Metric | Target | Method |
|--------|--------|--------|
| Monthly uptime | 99.99% | Ledger + backup replicas |
| Dossier generation latency | P95 <90 sec | Performance benchmarks |
| Policy model retraining | Weekly | Cron + metrics logging |
| Regulatory feedback loop | <2 weeks | Submission → approval tracking |
| KMS availability | 99.99% | HSM failover (AWS CloudHSM) |

---

## 7. RISK MITIGATION

### 7.1 Regulatory Rejection

**Risk:** Regulator rejects dossier (wrong format, missing evidence).  
**Mitigation:**
- Pre-submission checker (15-point audit) catches 98% of issues
- RAGAS evaluator validates dossier content against real questions
- Remediation suggestions learned from past rejections (ML model adaptation)

### 7.2 KMS Key Loss

**Risk:** Ed25519 PQC key compromised or lost.  
**Mitigation:**
- Key stored in AWS CloudHSM (FIPS 140-2 Level 3)
- Duplicate keys in 2 regions (EU + US)
- Rotation every 90 days (new key, re-sign past dossiers)

### 7.3 Merkle Chain Corruption

**Risk:** Decision ledger corrupted; merkle proofs invalid.  
**Mitigation:**
- Ledger stored in immutable Postgres WAL (write-ahead log)
- Hourly snapshot to S3 (versioning enabled)
- Weekly audit: recompute merkle roots from raw decisions
- Checksum verification on every read

### 7.4 Policy Model Drift

**Risk:** ML model accuracy drops below 90% (new decision patterns not seen in training).  
**Mitigation:**
- Weekly retraining (captures new patterns in 7 days)
- Holdout set validation (detect accuracy drop immediately)
- Fallback: disable ML-based approval suggestions if accuracy < 85%

---

## 8. WEEK-BY-WEEK IMPLEMENTATION

### WEEKS 1-2: Evidence Chain

```
Mon Oct 1: Start evidence capture enhancement
  - Decision struct with merkle_proof field
  - KMS signing pipeline (Ed25519)
  
Tue Oct 2-3: Merkle tree construction
  - Incremental hash chain
  - Batch aggregation
  
Wed Oct 4: Integration + testing
  - 36 tests passing
  - Performance: <10ms per decision hash
  
Thu Oct 5: Code review + doc
  - Proof-of-concept dossier with merkle root
```

**Deliverable:** DecisionBatch with merkle_root + kms_signature fields.

### WEEKS 3-4: Policy Learning

```
Mon Oct 8: Feature engineering
  - Agent experience, tool embeddings, time patterns
  
Tue Oct 9-10: Logistic regression model
  - Training loop (closed-form, no external deps)
  - Holdout validation
  
Wed Oct 11: Weekly retraining loop
  - Cron job Sunday 0200 UTC
  - Metrics dashboard
  
Thu Oct 12: SHAP explanations
  - Feature importance for audit trails
  - Integration test: train on Phase 2B data (10M sample)
```

**Deliverable:** PolicyLearner model with 92%+ accuracy on holdout set.

### WEEKS 5-6: Multi-language Dossier

```
Mon Oct 15: Dossier struct + validation
  - 9-section enum
  - Serde JSON/YAML
  
Tue Oct 16-17: Translation strings
  - Czech (KARP native)
  - English (EU standard)
  - Mandarin Simplified (CAC)
  
Wed Oct 18: PDF rendering
  - Headless Chrome (no font subsetting)
  - Fast (target <5 sec per PDF)
  
Thu Oct 19: Integration
  - End-to-end dossier generation
```

**Deliverable:** RegulatoryDossier struct for Annex III + I with full i18n.

### WEEK 7: Dossier Generator

```
Mon Oct 22: Batch reader + section population
Tue Oct 23: Section logic (1-9)
Wed Oct 24: Merkle + KMS integration
Thu Oct 25: Full pipeline test (2200 decisions → dossier in <60 sec)
```

**Deliverable:** generate_dossier() function, monthly automation ready.

### WEEK 8: RAGAS Validator

```
Mon Oct 29: 50-question golden set (real regulatory questions)
Tue Oct 30: Eval harness (LangSmith integration)
Wed Oct 31: LLM dossier answerer + scoring
Thu Nov 1: Dashboard + weekly reporting
```

**Deliverable:** 50-question compliance test suite, 98%+ accuracy baseline.

### WEEK 9: Approval Engine

```
Mon Nov 5: Pre-submission checks (15-point audit)
Tue Nov 6: Remediation suggestion ML
Wed Nov 7: Dashboard UI (CLI + web)
Thu Nov 8: Full integration test + documentation
```

**Deliverable:** Pre-submission scoring, ready for Annex III deadline (Dec 2).

---

## 9. INTEGRATION WITH PHASE 2B

Phase 2B (Aug-Sep 2027) delivers federated gateways (50+ regional nodes).  
Phase 2C runs parallel (Oct-Dec) but depends on Phase 2B ledger format.

**Dependency Chain:**
```
Phase 2B: 100M decisions → 50 regional gateways → Unified ledger
                                                          ↓
                                                   Phase 2C: Policy Learning
                                                   (weekly retraining)
                                                          ↓
                                             Monthly Dossier Assembly
                                                   (Dec 2 deadline)
```

**SLA:** Phase 2B must produce standardized decision format by Sep 30, 2027.  
Phase 2C integration testing begins Oct 1 with synthetic ledger (10K sample decisions).

---

## 10. ANNEX III DEADLINE PREPARATION

**Dec 2, 2027: Annex III compliance goes live**

Weeks leading up:
- Week 9 (Nov 8): First production dossier generated (live data)
- Week 10 (Nov 15): Submit to Czech regulator (AGENTURA PRO OCHRANU OSOBNÍCH ÚDAJŮ)
- Week 11-12 (Nov 22-29): Regulatory feedback loop, remediation if needed
- Nov 30 - Dec 1: Final submission batches
- **Dec 2:** Deadline. SMAOS must have dossier on file.

---

## 11. ANNEX I DEADLINE PREPARATION

**Aug 2, 2028: Annex I compliance required**

Phase 2C deliverables used for:
- Pre-execution gate accuracy (Section 7)
- Rollback log (Section 8)
- 6+ months compliance history (Section 9)

Preparation:
- Jan 2028: Glass/Auto pilots begin (Phase 3 starts)
- Mar 2028: First Annex I dossier generated (glass industry)
- May 2028: Final remediation round
- **Aug 2:** Deadline. All glass/auto systems must have pre-exec gates proven.

---

## 12. COST MODEL

### Implementation Cost (Phase 2C, 16 weeks)

| Component | Engineer Weeks | Compute Cost | Total |
|-----------|----------------|--------------|-------|
| Evidence Chain | 2 | €200 | €8k |
| Policy Learning | 2 | €500 | €8.5k |
| Dossier Assembly | 2 | €300 | €8.3k |
| Multi-language i18n | 1.5 | €100 | €6k |
| RAGAS Validator | 1.5 | €800 | €7.3k |
| Approval Engine | 1 | €200 | €5.2k |
| QA + Integration | 2 | €400 | €8.2k |
| Documentation + Regulatory review | 1.5 | €100 | €6.5k |
| **TOTAL** | **14 weeks** | **€2.6k** | **€57.9k** |

**Margin:** €100k - €57.9k = €42.1k (43% contribution margin)

### Per-Dossier Cost (Operations)

| Cost Center | Monthly | per Dossier (500/mo) |
|-------------|---------|---------------------|
| Compute (dossier generation) | €200 | €0.40 |
| KMS operations (AWS CloudHSM) | €500 | €1.00 |
| Ledger storage (Postgres) | €300 | €0.60 |
| Regulatory portal API | €100 | €0.20 |
| Support + QA | €1000 | €2.00 |
| **Total** | **€2.1k** | **€4.20** |

**Gross Margin per Dossier:** €100 (subscription) - €4.20 = €95.80 (95.8% margin)

---

## 13. DELIVERABLES SUMMARY

| Artifact | Size | Audience | Format |
|----------|------|----------|--------|
| Compliance Automation Harness | 4800 LOC | Engineers | Rust crates |
| Merkle Proof Library | 600 LOC | Security auditors | Ed25519 + Merkle tree docs |
| Policy Learning Model | 400 LOC | Data scientists | Logistic regression + weekly metrics |
| Multi-language Dossier | 950 LOC | Regulators | Czech/EN/CN PDF + JSON |
| RAGAS Compliance Suite | 620 LOC | Compliance leads | 50-question test set + evals |
| API Documentation | 80 pages | Integration partners | OpenAPI spec + examples |
| Annex III/I Submission Toolkit | 200 LOC | Regulatory teams | CLI + web dashboard |
| Weekly Operations Runbook | 50 pages | Operations | SOP for monthly dossier submission |

**Total Deliverable Size:** 10,000+ LOC + documentation

---

## CONCLUSION

Phase 2C transforms compliance from manual (40 hours/operator) to fully automated (<60 seconds compute). Every decision is cryptographically proven, every dossier is pre-validated for regulatory approval, and every month produces 500 compliant submissions (vs. 200 today).

**Competitive Advantage:**
- **Only platform** with Merkle-proof evidence chains
- **Only platform** with dynamic policy learning from real decisions
- **Only platform** with 98%+ first-pass regulatory approval rate

**Path to €100M ARR:**
- €50M (Phase 2B baseline) + 5x volume growth (2,200 → 11,000 decisions/month)
- 3x regional expansion (Czech → Czech/EN/CN)
- 94% cost reduction per dossier
- 98% regulatory approval = zero remediation overhead

**Readiness for Annex III (Dec 2, 2027) + Annex I (Aug 2, 2028):** Delivery by Week 9 of Phase 2C (Nov 8, 2027) provides 24-day buffer for regulatory feedback.
