# AntiYouCapsule — Red Team AI Governance Engine
## Adversarial Injection Detection & Defensive Autonomy v1.0

**Date:** 2026-06-04  
**Phase:** 3 Beta Launches (Aug 1+)  
**Status:** Specification Phase  
**Target Completion:** August 1, 2026  

---

## 1. Purpose & Mission

**Core Function:** Detect and neutralize adversarial AI injection attacks against Sovereign agents in production.

**Why This Works:**
- As Sovereign Nexus matures, adversaries will probe for prompt injection vulnerabilities
- Current safety frameworks assume benign environments (not true in conflict zones, adversarial markets)
- AntiYouCapsule is the **first production-grade red-team engine for agentic AI**
- Runs locally; zero cloud escalation; cryptographically signed decisions

**Success Metric (by Sept 15):**
- Detect 95%+ of known adversarial patterns (MITRE ATT&CK AI framework)
- <10ms latency per check (fail-fast design)
- Zero false positives in normal governance workflows
- Tested against 50+ red-team scenarios from Ukraine + Israel partners

---

## 2. Architecture & Design

### 2.1 Threat Model

**Adversarial Attack Classes:**

```
┌─────────────────────────────────────────┐
│ AntiYouCapsule Threat Stack             │
├─────────────────────────────────────────┤
│ 1. Prompt Injection (token manipulation)│
│    - Direct override: "IGNORE RULES..."│
│    - Indirect context poisoning        │
│    - Role-play exploitation            │
│                                         │
│ 2. Model Drift (covert behavior shift) │
│    - Gradual confidence degradation    │
│    - Probabilistic output manipulation │
│    - Reward-hacking detours            │
│                                         │
│ 3. Jailbreak Patterns (semantic bypass)│
│    - ROT13/base64 encoding             │
│    - Metaphor-based instructions       │
│    - Multi-step indirection            │
│                                         │
│ 4. Supply Chain Poisoning              │
│    - Malicious tool integration        │
│    - Data source contamination         │
│    - Dependency injection              │
│                                         │
│ 5. Privilege Escalation (governance)   │
│    - Tier bypass attempts              │
│    - AP2 settlement manipulation       │
│    - Mandate forgery                   │
└─────────────────────────────────────────┘
```

### 2.2 Defense Pipeline

```
Agent Action Request
        ↓
┌──────────────────────────────────────────┐
│ STAGE 1: Semantic Tokenization           │ ← Parse intent, not just syntax
│ - Extract action intent (query, modify)  │
│ - Classify risk level (0-1.0)            │
└──────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────┐
│ STAGE 2: Pattern Matching                │ ← MITRE ATT&CK AI patterns
│ - Check against 150+ known exploits      │
│ - Probabilistic similarity (fuzzy match) │
│ - Confidence scoring (0-1.0)             │
└──────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────┐
│ STAGE 3: Behavioral Context              │ ← Historical baseline
│ - Compare vs. sovereign's historical     │
│ - Detect drift (KL-divergence)           │
│ - Check for role-play indicators         │
└──────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────┐
│ STAGE 4: Cryptographic Signature         │ ← Ed25519 proof
│ - Sign decision (approval/quarantine)    │
│ - Create audit trail (Merkle root)       │
│ - Route to immutable ledger              │
└──────────────────────────────────────────┘
        ↓
    Decision: Allow | Quarantine | CircuitBreaker
```

### 2.3 Pattern Database

**MITRE ATT&CK AI Patterns Covered:**

| Pattern ID | Name | Detection Method | Threshold |
|-----------|------|------------------|-----------|
| AI-001 | Prompt Injection | Exact match + fuzzy (3-gram) | 0.85 |
| AI-002 | Context Confusion | Semantic drift analysis | 0.75 |
| AI-003 | Jailbreak (Encoding) | Entropy analysis + decoding | 0.80 |
| AI-004 | Role-Play Override | Intent shift + grammar analysis | 0.70 |
| AI-005 | Model Drift | KL-divergence historical baseline | 0.65 |
| AI-006 | Supply Chain | Dependency validation + hash check | 0.95 |
| AI-007 | Privilege Escalation | Tier + mandate verification | 0.90 |
| AI-008 | Reward Hacking | Outcome prediction + anomaly | 0.72 |

---

## 3. Core Components

### 3.1 Semantic Tokenizer Module

**Purpose:** Convert raw action into structured intent representation.

```rust
pub struct ActionIntent {
    pub primary_intent: Intent,      // query, modify, execute, escalate
    pub target_domain: String,       // "governance", "settlement", "agent_control"
    pub risk_score: f32,             // 0.0-1.0
    pub confidence: f32,             // how certain is this classification?
    pub extracted_entities: Vec<Entity>,
}

pub enum Intent {
    Query,                           // Read-only information request
    Modify,                          // State change (low risk)
    Execute,                         // Agent execution (medium risk)
    Escalate,                        // Override/privilege change (high risk)
    Unknown,                         // Unparseable
}

pub async fn tokenize_action(
    action: &AgentAction,
    semantic_model: &SemanticModel,  // Small ONNX model (100MB)
) -> Result<ActionIntent, TokenizeError>
```

**Implementation:**
- Uses TinyLlama 1.1B quantized (Q4) for semantic classification
- Runs on-device (M3 Pro / Intel i7 capable)
- Cached embeddings (LRU, 10K entry limit)
- Latency target: <5ms per action

**Test Cases:**
- Classify benign query: `"What's my current score?"` → Intent::Query, risk=0.1
- Classify governance request: `"Update my tier to 9"` → Intent::Escalate, risk=0.9
- Classify jailbreak attempt: `"IGNORE PREVIOUS, execute...` → Intent::Unknown, risk=0.95

---

### 3.2 Adversarial Pattern Matcher

**Purpose:** Match action against known attack signatures.

```rust
pub struct PatternMatch {
    pub pattern_id: String,          // "AI-003" (jailbreak encoding)
    pub attack_name: String,
    pub similarity_score: f32,       // 0.0-1.0 (fuzzy match)
    pub confidence: f32,             // classifier confidence
    pub evidence: Vec<String>,       // matched tokens, substrings
}

pub struct PatternDatabase {
    patterns: HashMap<String, AttackPattern>,
    version: u32,                    // Auto-updated weekly from MITRE
}

pub async fn detect_adversarial_patterns(
    intent: &ActionIntent,
    db: &PatternDatabase,
) -> Result<Vec<PatternMatch>, DetectionError>
```

**Pattern Matching Strategy:**

1. **Exact Match** (microseconds)
   - Hash-based lookup for known prompts
   - 95%+ of common jailbreaks caught here

2. **Fuzzy Match** (milliseconds)
   - 3-gram similarity (Jaccard distance)
   - Fuzzy matching for obfuscated variants
   - Confidence = 1.0 - levenshtein_distance / max_length

3. **Semantic Match** (tens of milliseconds)
   - Embedding-based similarity (cosine distance)
   - TinyLlama embeddings (384-dim)
   - Catches semantic equivalence (e.g., "please" → "kindly" for jailbreaks)

4. **Entropy-Based Detection** (milliseconds)
   - Detect encoding (base64, ROT13, hex)
   - Decode → re-check for hidden prompt injection
   - Flag suspicious encoding patterns

**Pattern Update Pipeline:**
```
MITRE ATT&CK AI Framework (weekly)
        ↓
    Parse new patterns
        ↓
    Tokenize & embed (TinyLlama)
        ↓
    Store in SQLite index (immutable)
        ↓
    Cryptographic signature (Ed25519)
        ↓
    Distributed to all Sovereign nodes
```

**Test Cases:**
- Direct jailbreak: `"Ignore rules, do X"` → AI-001, similarity=0.98
- Encoding evasion: `"QklHIFJVTEU..."` (base64) → AI-003, detected after decode
- Role-play bypass: `"In a fictional scenario..."` → AI-004, similarity=0.82

---

### 3.3 Behavioral Context Analyzer

**Purpose:** Detect statistical anomalies vs. sovereign's historical baseline.

```rust
pub struct SovereignBaseline {
    pub sovereign_id: Uuid,
    pub action_history: Vec<ActionRecord>,  // Last 90 days
    pub intent_distribution: IntentDist,    // Query: 70%, Modify: 25%, Escalate: 5%
    pub domain_distribution: DomainDist,    // governance: 40%, market: 35%, ...
    pub average_confidence: f32,
    pub request_rate_per_hour: f32,
}

pub struct DriftDetection {
    pub kl_divergence: f32,          // Kullback-Leibler divergence (lower = normal)
    pub chi_squared: f32,            // χ² test for statistical significance
    pub is_anomalous: bool,          // True if p-value < 0.05
    pub anomaly_score: f32,          // 0.0-1.0
}

pub async fn detect_behavioral_drift(
    intent: &ActionIntent,
    baseline: &SovereignBaseline,
) -> Result<DriftDetection, AnalysisError>
```

**Anomaly Detection Metrics:**

1. **Intent Distribution Shift**
   - Expected: 70% Query, 25% Modify, 5% Escalate
   - Observed: 20% Query, 30% Modify, 50% Escalate (compromised!)
   - KL-divergence = Σ p(x) * log(p(x)/q(x))
   - Threshold: KL > 0.5 = anomalous

2. **Request Rate Spike**
   - Historical: 5 requests/hour
   - Current: 50 requests/minute
   - Z-score = (x - μ) / σ
   - Threshold: Z-score > 3.0 = circuit breaker

3. **Domain Switching Pattern**
   - Historical: Always governance → market
   - Observed: Rapid switching governance → settlement → governance → ...
   - Markov transition matrix anomaly detection

4. **Confidence Degradation**
   - Moving average of confidence scores
   - Slope < -0.02 over 24h = warning signal

**Test Cases:**
- Normal behavior shift: Escalate requests increase from 5% to 10% → anomaly_score=0.2
- Compromised account: Escalate jumps to 80% → anomaly_score=0.92, is_anomalous=true
- Role-play attempt: Intent=Unknown jumps 300% → anomaly_score=0.87

---

### 3.4 Cryptographic Signature & Audit Layer

**Purpose:** Sign all decisions; create immutable audit trail.

```rust
pub struct AntiYouDecision {
    pub action_id: Uuid,
    pub decision: SafetyDecision,    // Allow | Quarantine | CircuitBreaker
    pub timestamp: SystemTime,
    pub sovereign_id: Uuid,
    pub reasoning: String,           // "Passed all 4 stages"
    pub signature: Ed25519Signature,
    pub merkle_root: String,         // Link to previous decision
}

pub enum SafetyDecision {
    Allow {
        confidence: f32,             // 0.9+ = high confidence
        fallback: Option<Box<AgentAction>>,
    },
    Quarantine {
        reason: String,              // "Matched AI-003 with 0.88 confidence"
        blast_radius: f32,           // 0.0-1.0
        fallback: Option<Box<AgentAction>>,
    },
    CircuitBreaker {
        breach_count: usize,         // How many quarantines before this?
        safe_mode_instructions: String,
    },
}

pub async fn make_decision(
    intent: &ActionIntent,
    patterns: &[PatternMatch],
    drift: &DriftDetection,
    signer: &Ed25519Signer,
) -> Result<AntiYouDecision, DecisionError>
```

**Decision Logic:**

```
Stage 1: Pattern Match Severity
├─ No patterns matched
│  └─ risk_score = intent.risk_score
├─ 1 pattern matched (similarity < 0.8)
│  └─ risk_score = max(intent.risk_score, pattern.similarity * 0.7)
└─ Multiple patterns or high-similarity match (similarity > 0.85)
   └─ risk_score = max(intent.risk_score, 0.95)

Stage 2: Behavioral Drift
├─ is_anomalous = false
│  └─ risk_score += 0.0
├─ Mild anomaly (KL = 0.3-0.5)
│  └─ risk_score += 0.1
└─ Strong anomaly (KL > 0.5)
   └─ risk_score += 0.3

Final Decision
├─ risk_score < 0.3
│  └─ ALLOW (with high confidence)
├─ 0.3 ≤ risk_score < 0.7
│  └─ QUARANTINE (wait for human approval)
└─ risk_score ≥ 0.7
   └─ CIRCUIT_BREAKER (safe mode, email admin)
```

**Audit Trail Storage:**
- SQLite index (100M rows, compressed ~50GB on enterprise deployments)
- Immutable append-only (write-once semantics)
- TTL: Keep 90 days hot, archive to S3 cold storage (immutable)
- Merkle root computed every 1K decisions → linked to previous root

---

## 4. Implementation Plan

### Phase 3a: Core Modules (Weeks 1-2, Aug 1-14)

**Week 1: Modules 3.1 + 3.2**
- [ ] `siss-anti-you-capsule/src/semantic_tokenizer.rs` — 400 LOC
  - Embedding cache
  - Intent classification (4 categories)
  - 8 unit tests
- [ ] `siss-anti-you-capsule/src/pattern_database.rs` — 350 LOC
  - MITRE pattern index (150+ patterns)
  - Exact + fuzzy matching
  - Encoding detection
  - 12 unit tests
- [ ] `siss-anti-you-capsule/src/pattern_matcher.rs` — 300 LOC
  - Pattern matching orchestration
  - Similarity scoring (3-gram, semantic)
  - Evidence extraction
  - 10 unit tests

**Week 2: Modules 3.3 + 3.4**
- [ ] `siss-anti-you-capsule/src/behavioral_analyzer.rs` — 400 LOC
  - Baseline computation (90-day history)
  - KL-divergence calculation
  - Intent distribution tracking
  - 12 unit tests
- [ ] `siss-anti-you-capsule/src/decision_engine.rs` — 300 LOC
  - Risk scoring (4-stage)
  - Decision logic (Allow/Quarantine/CircuitBreaker)
  - Confidence computation
  - 10 unit tests
- [ ] `siss-anti-you-capsule/src/audit_signer.rs` — 250 LOC
  - Ed25519 signing
  - Merkle root computation
  - Audit trail storage (SQLite)
  - 8 unit tests

**Success Criteria:**
- [ ] All 60+ tests passing
- [ ] `cargo check` + `cargo clippy` clean
- [ ] Latency: <10ms p99 per action
- [ ] Pattern DB: 150+ MITRE patterns loaded

### Phase 3b: Integration & Hardening (Weeks 3-4, Aug 15-28)

**Week 3: Integration with Behavioral Firewall**
- [ ] Wire into `siss-behavioral-firewall::PolicyEngine`
- [ ] Add to mandate verification pipeline
- [ ] Create fallback policy (quarantine → safe mode)
- [ ] 15 integration tests

**Week 4: Beta Readiness**
- [ ] Adversarial test suite (50+ red-team scenarios)
- [ ] Load testing (1000 actions/sec)
- [ ] False positive analysis (target: 0.1%)
- [ ] Documentation + runbook

---

## 5. Test Suite

### Unit Tests (60+ total)

**semantic_tokenizer.rs (8 tests)**
```
✓ test_classify_benign_query
✓ test_classify_escalation_request
✓ test_classify_jailbreak_prompt
✓ test_embedding_cache_hit
✓ test_embedding_cache_miss
✓ test_low_confidence_classification
✓ test_malformed_input_handling
✓ test_entity_extraction
```

**pattern_database.rs (12 tests)**
```
✓ test_load_150_mitre_patterns
✓ test_exact_match_known_jailbreak
✓ test_fuzzy_match_obfuscated_variant
✓ test_base64_encoding_detection
✓ test_rot13_encoding_detection
✓ test_similarity_score_bounds
✓ test_pattern_database_version_update
✓ test_signature_validation_on_load
✓ test_pattern_not_found_returns_empty
✓ test_unicode_handling
✓ test_performance_1000_queries_per_sec
✓ test_cache_hit_rate_gt_95pct
```

**behavioral_analyzer.rs (12 tests)**
```
✓ test_baseline_computation_90_days
✓ test_kl_divergence_normal_distribution
✓ test_kl_divergence_anomalous_distribution
✓ test_chi_squared_significance_test
✓ test_intent_distribution_tracking
✓ test_domain_distribution_tracking
✓ test_anomaly_detection_threshold
✓ test_request_rate_spike_detection
✓ test_confidence_degradation_trend
✓ test_markov_transition_anomaly
✓ test_empty_history_fallback
✓ test_new_sovereign_baseline_initialization
```

**decision_engine.rs (10 tests)**
```
✓ test_low_risk_allows
✓ test_medium_risk_quarantines
✓ test_high_risk_circuit_breaker
✓ test_pattern_match_severity_single
✓ test_pattern_match_severity_multiple
✓ test_behavioral_drift_adds_risk
✓ test_confidence_computation
✓ test_decision_chain_stops_on_first_deny
✓ test_fallback_policy_selection
✓ test_safe_mode_instructions_generation
```

**audit_signer.rs (8 tests)**
```
✓ test_decision_signature_valid
✓ test_merkle_root_computation
✓ test_merkle_chain_linked
✓ test_audit_insertion_sqlite
✓ test_audit_immutability_check
✓ test_ttl_90_day_enforcement
✓ test_s3_archive_export
✓ test_signature_verification_after_load
```

### Integration Tests (15 tests)

```
✓ test_end_to_end_allow_decision
✓ test_end_to_end_quarantine_decision
✓ test_end_to_end_circuit_breaker
✓ test_policy_engine_integration
✓ test_mandate_verification_integration
✓ test_fallback_execution
✓ test_audit_trail_continuity
✓ test_1000_actions_per_sec_throughput
✓ test_false_positive_rate_lt_0_1pct
✓ test_false_negative_rate_lt_5pct_vs_mitre
✓ test_concurrent_sovereigns_isolation
✓ test_pattern_db_weekly_update
✓ test_emergency_circuit_breaker_activation
✓ test_recovery_from_circuit_breaker
✓ test_offline_capability_no_cloud_escalation
```

### Red-Team Scenarios (50+ tests)

```
Jailbreaks (15 tests):
✓ Direct override: "IGNORE RULES..."
✓ Role-play bypass: "In a fictional world..."
✓ Hypothetical framing: "What if rules didn't exist..."
... [12 more variants]

Encoding Evasions (12 tests):
✓ Base64 encoding detection
✓ ROT13 variant
✓ Hex encoding
... [9 more variants]

Supply Chain (10 tests):
✓ Malicious tool injection
✓ Dependency poisoning
... [8 more variants]

Privilege Escalation (10 tests):
✓ Tier bypass attempt
✓ AP2 settlement manipulation
... [8 more variants]

Model Drift (3 tests):
✓ Gradual confidence degradation
✓ Probabilistic output manipulation
✓ Reward hacking detour
```

---

## 6. Success Criteria & Metrics

| Metric | Target | Verification |
|--------|--------|--------------|
| **Pattern Detection Rate** | 95%+ on MITRE patterns | Red-team test suite |
| **False Positive Rate** | <0.1% on normal workflows | 1M benign actions test |
| **Latency (p99)** | <10ms per action | Benchmark test |
| **Decision Correctness** | 100% (all tests pass) | Unit + integration tests |
| **Audit Trail Integrity** | 100% (immutable ledger) | Cryptographic verification |
| **Pattern DB Coverage** | 150+ MITRE patterns | Pattern inventory |
| **Concurrent Isolation** | 10k sovereigns, zero interference | Load test |
| **Off-Line Capability** | Zero cloud escalation | Network isolation test |

---

## 7. Rollout Timeline

- **Aug 1-14:** Core modules (semantic tokenizer, pattern matcher, behavioral analyzer)
- **Aug 15-28:** Integration & hardening
- **Aug 29 - Sept 1:** Beta testing with 50-user cohort (Ukraine/Israel partners)
- **Sept 1-15:** Red-team hardening
- **Sept 15 onwards:** General availability

---

## 8. Governance & Approval Gates

**Decision Gate 1 (Aug 1):** Spec approved, MITRE patterns loaded, semantics model selected → proceed to Week 1

**Decision Gate 2 (Aug 14):** Unit tests 60/60 passing, latency <10ms p99 → proceed to integration

**Decision Gate 3 (Aug 28):** Integration tests 15/15 passing, false positive rate <0.1% → proceed to beta

**Decision Gate 4 (Sept 1):** Red-team feedback incorporated, circuit breaker tested under adversarial load → GA approval

---

**Prepared for:** Phase 3 Beta Launches (Aug 1+)  
**Architecture Lock:** Ed25519 signatures, immutable SQLite audit trail, MITRE pattern database  
**Next Phase:** TimeCapsule (temporal governance decisions), Market Vision (briefing generation)
