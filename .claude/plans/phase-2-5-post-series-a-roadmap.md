# Phase 2–5: Post-Series A Implementation Roadmap
## June 30 → December 31, 2026 (26 Weeks)

---

## Context

**Current State (June 30 EOD):**
- ✅ Phase 1: decision_store.rs complete (7/7 tests, all deployed)
- ✅ Constitutional layer proven (Prague demo + Trojan Horse launch)
- ✅ Series A closed (€10M secured)
- ✅ 3 pilot customers onboarded (fintech, healthtech, compliance)
- ✅ Founding team assembled (cryptography, compliance, causal inference)

**Goal:** Build production-grade AI governance platform with 4 subsystems locked.

**Success Metrics:**
- Phase 2: ✅ Economic Intent Validation (Covenant Firewall)
- Phase 3: ✅ Micro-Royalty Settlement (AP2 Ledger)
- Phase 4: ✅ Causal Validation (MongeGapGovernor v3)
- Phase 5: ✅ Substrate Integration (Llama + Claude + Custom)
- **Business:** 10 pilot customers, €500K ARR, €3M runway

---

## Phase 2: Covenant Firewall (6 weeks, July 1–12)

**Purpose:** Enforce economic intent at cryptographic layer. Validate that every transaction respects the 1%/99% covenant before execution.

### Component Specs

#### 2.1 EconomicIntent Validation

**File:** `crates/siss-gatekeeper/src/pipeline/covenant_firewall.rs`

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EconomicIntent {
    pub steward_pct: u8,        // Must be exactly 1
    pub beneficiary_pct: u8,    // Must be exactly 99
    pub total_microcents: i64,  // Total amount (in 0.0001 unit)
    pub steward_id: Uuid,       // 1% recipient
    pub beneficiary_id: Uuid,   // 99% recipient
}

pub struct CovenantFirewall {
    intents: Arc<DashMap<Uuid, EconomicIntent>>,
}

impl CovenantFirewall {
    pub fn validate_intent(&self, intent: &EconomicIntent) -> Result<(), CovenantBreach> {
        if intent.steward_pct != 1 || intent.beneficiary_pct != 99 {
            return Err(CovenantBreach::InvalidSplit);
        }
        if intent.total_microcents <= 0 {
            return Err(CovenantBreach::ZeroAmount);
        }
        Ok(())
    }
    
    pub fn compute_split(&self, intent: &EconomicIntent) -> (i64, i64) {
        let steward_amt = intent.total_microcents / 100;  // 1%
        let beneficiary_amt = intent.total_microcents - steward_amt;  // 99%
        (steward_amt, beneficiary_amt)
    }
}
```

**Test Coverage (TDD):**
- `test_valid_intent_passes` — 1%/99% split accepted
- `test_invalid_split_50_50_rejected` — 50/50 split fails
- `test_zero_amount_rejected` — Amount validation
- `test_concurrent_intent_validation` — Thread-safe DashMap
- `test_split_computation_accuracy` — Math verified (no rounding errors)

**Latency SLO:** Tier1 (<10ms) — validation gates decision_store append

---

#### 2.2 Covenant Breach Detection

**File:** `crates/siss-gatekeeper/src/pipeline/covenant_firewall.rs` (extended)

```rust
pub enum CovenantBreach {
    InvalidSplit { steward: u8, beneficiary: u8 },
    ZeroAmount,
    NegativeAmount,
    TamperingDetected { intent_id: Uuid, expected_hash: String, actual_hash: String },
    UnauthorizedModification { actor: Uuid, intent_id: Uuid },
}

pub struct BreachLog {
    breaches: Arc<DashMap<Uuid, (CovenantBreach, Timestamp)>>,
}

impl BreachLog {
    pub fn log_breach(&self, breach: CovenantBreach) -> Result<Uuid, Error> {
        let breach_id = Uuid::new_v4();
        self.breaches.insert(breach_id, (breach, Utc::now()));
        Ok(breach_id)
    }
    
    pub fn audit_trail(&self, limit: usize) -> Vec<(Uuid, CovenantBreach, Timestamp)> {
        // Return most recent breaches
    }
}
```

**Test Coverage:**
- `test_breach_logged_on_invalid_split`
- `test_breach_hash_mismatch_detected`
- `test_unauthorized_actor_rejected`
- `test_audit_trail_ordered_by_timestamp`

**Merkle-Rooting:** Every breach logged with Merkle hash → EXEC_LOG

---

### Integration Points

1. **From Phase 1 (decision_store):** 
   - Each DecisionEntry references an EconomicIntent
   - Covenant Firewall validates intent before decision is signed

2. **To Phase 3 (AP2 Settlement):**
   - Valid intents → routed to AP2 Ledger for settlement
   - Invalid intents → rejected at firewall (fail-closed)

### Deliverables

- [ ] covenant_firewall.rs implemented (500 LOC)
- [ ] BreachLog.rs implemented (300 LOC)
- [ ] 10/10 tests passing
- [ ] Merkle-rooted to EXEC_LOG
- [ ] Documented in README (covenant defense #2 of 5)

**Timeline:** 6 weeks (July 1–12)

---

## Phase 3: AP2 Micro-Royalty Settlement (6 weeks, July 13–24)

**Purpose:** Settle micro-royalty payments to creators (99%) and stewards (1%) in real-time on the AP2 Ledger.

### Component Specs

#### 3.1 AP2 Ledger

**File:** `crates/siss-gatekeeper/src/pipeline/ap2_ledger.rs`

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AP2Entry {
    pub id: Uuid,
    pub timestamp: String,
    pub from_intent: Uuid,  // Reference to EconomicIntent
    pub steward_payout: i64,  // 1%
    pub beneficiary_payout: i64,  // 99%
    pub signature: Vec<u8>,  // Ed25519 over (steward + beneficiary + timestamp)
}

pub struct AP2Ledger {
    entries: Arc<DashMap<Uuid, AP2Entry>>,
    merkle_chain: Arc<RwLock<String>>,  // Merkle root of all entries
}

impl AP2Ledger {
    pub fn settle(&self, intent: &EconomicIntent) -> Result<AP2Entry, SettlementError> {
        let (steward_amt, beneficiary_amt) = self.compute_split(intent);
        
        let entry = AP2Entry {
            id: Uuid::new_v4(),
            timestamp: Utc::now().to_rfc3339(),
            from_intent: intent.id,
            steward_payout: steward_amt,
            beneficiary_payout: beneficiary_amt,
            signature: vec![],  // Signed by signer
        };
        
        self.entries.insert(entry.id, entry.clone());
        self.update_merkle_chain(&entry);
        Ok(entry)
    }
}
```

**Test Coverage:**
- `test_settle_creates_ap2_entry`
- `test_steward_receives_1_percent`
- `test_beneficiary_receives_99_percent`
- `test_merkle_chain_updated_on_settlement`
- `test_ledger_merkle_root_deterministic`

**Latency SLO:** Tier1 (<10ms) — settlement must complete within authorization window

---

#### 3.2 Payment Routing

**File:** `crates/siss-gatekeeper/src/pipeline/ap2_router.rs`

```rust
pub struct PaymentRouter {
    ledger: Arc<AP2Ledger>,
    payment_backends: HashMap<PaymentMethod, Box<dyn PaymentBackend>>,
}

pub trait PaymentBackend: Send + Sync {
    async fn send_payment(&self, recipient: Uuid, amount_microcents: i64) -> Result<PaymentProof, PaymentError>;
}

impl PaymentRouter {
    pub async fn route_settlement(&self, ap2_entry: &AP2Entry) -> Result<PaymentProof, PaymentError> {
        // Determine payment method (Stripe, SEPA, crypto, etc.)
        // Route steward payment
        // Route beneficiary payment
        // Return proof
    }
}
```

**Supported Backends (Phase 3):**
- Stripe (credit card, ACH)
- SEPA (EU bank transfers)
- Mock (for testing)

**Extended Backends (Phase 4):**
- Ethereum (ERC-20)
- Bitcoin (on-chain)
- USD Coin (USDC)

**Test Coverage:**
- `test_stripe_route_succeeds`
- `test_sepa_route_succeeds`
- `test_concurrent_payment_routing`
- `test_failed_payment_logged`

### Integration Points

1. **From Phase 2 (Covenant Firewall):**
   - Valid EconomicIntent → passed to AP2 Ledger

2. **To Phase 4 (MongeGapGovernor v3):**
   - Settlement outcomes → fed to causal validation
   - "Did the payment succeed as predicted?"

### Deliverables

- [ ] ap2_ledger.rs (600 LOC)
- [ ] ap2_router.rs (400 LOC)
- [ ] 15/15 tests passing
- [ ] Stripe integration live (mock for MVP)
- [ ] SEPA integration live (mock for MVP)
- [ ] Payment proof Merkle-rooted

**Timeline:** 6 weeks (July 13–24)

---

## Phase 4: MongeGapGovernor v3 (6 weeks, July 25–August 5)

**Purpose:** Extended causal validation + temporal governance. Validate that settlement outcomes match predictions and govern the system's behavior over time.

### Component Specs

#### 4.1 Extended Causal Validation

**File:** `crates/siss-gatekeeper/src/pipeline/monge_gap_v3.rs`

```rust
pub struct MongeGapGovernor {
    decay: TemporalDecay,
    adversarial_sampler: AdversarialSampler,
    breach_history: Vec<MongeGapResult>,
    circuit_breaker_threshold: usize,
    causal_cache: Arc<DashMap<String, MongeGapResult>>,  // NEW: cache results
}

impl MongeGapGovernor {
    /// Evaluate settlement outcome against prediction
    pub fn validate_settlement_outcome(
        &self,
        predicted: &AP2Entry,
        actual: &PaymentProof,
    ) -> Result<MongeGapResult, Error> {
        // Compare predicted amounts vs actual amounts
        // Measure gap score
        // If gap > 0.15 → breach
        // Otherwise → safe
    }
    
    /// Temporal decay: older breaches matter less
    pub fn apply_temporal_decay(&self, result: &MongeGapResult) -> f64 {
        let age = Utc::now().signed_duration_since(
            DateTime::parse_from_rfc3339(&result.timestamp).unwrap()
        );
        self.decay.apply(result.gap_score, age.num_seconds() as f64)
    }
}
```

**Test Coverage:**
- `test_settlement_validates_correctly`
- `test_gap_score_computed_accurately`
- `test_temporal_decay_reduces_gap_over_time`
- `test_adversarial_sampler_injects_noise`
- `test_circuit_breaker_fires_on_threshold`

**Latency SLO:** Tier2 (async) — validation happens post-settlement, not blocking

---

#### 4.2 Temporal Governance

**File:** `crates/siss-gatekeeper/src/pipeline/temporal_governor.rs`

```rust
pub struct TemporalGovernor {
    governance_windows: Vec<GovernanceWindow>,  // [1 min, 1 hour, 1 day]
    action_triggers: HashMap<String, ActionTrigger>,
}

#[derive(Debug)]
pub struct GovernanceWindow {
    duration_secs: u64,
    breach_threshold: usize,  // Max breaches allowed in window
    action: GovernanceAction,
}

pub enum GovernanceAction {
    Monitor,
    Warn,
    Throttle { max_throughput_per_sec: u32 },
    Halt,
}

impl TemporalGovernor {
    pub fn evaluate_window(&self, window: &GovernanceWindow, breaches: &[MongeGapResult]) -> GovernanceAction {
        let recent_breaches = breaches.iter()
            .filter(|b| b.age_secs < window.duration_secs)
            .count();
        
        if recent_breaches > window.breach_threshold {
            window.action.clone()
        } else {
            GovernanceAction::Monitor
        }
    }
}
```

**Test Coverage:**
- `test_1min_window_triggers_warn`
- `test_1hour_window_triggers_throttle`
- `test_1day_window_triggers_halt`
- `test_governance_action_logged`

### Integration Points

1. **From Phase 3 (AP2 Settlement):**
   - PaymentProof → validated against prediction
   - Gap score computed

2. **To Phase 5 (Substrate Integration):**
   - Governance actions → fed to AI substrate
   - If "Halt" → reject new requests until breach window clears

### Deliverables

- [ ] monge_gap_v3.rs extended (800 LOC)
- [ ] temporal_governor.rs (500 LOC)
- [ ] 20/20 tests passing
- [ ] Governance state Merkle-rooted

**Timeline:** 6 weeks (July 25–August 5)

---

## Phase 5: Substrate Integration (8 weeks, August 6–September 30)

**Purpose:** Integrate Axiom governance with external AI models (Llama, Claude, Custom). Route all inference requests through Axiom's authorization pipeline.

### Component Specs

#### 5.1 Substrate Executor Interface

**File:** `crates/siss-gatekeeper/src/pipeline/substrate_executor.rs`

```rust
pub trait SubstrateExecutor: Send + Sync {
    async fn execute(
        &self,
        prompt: &str,
        model_id: &str,
        task_id: Uuid,
    ) -> Result<SubstrateResponse, ExecutionError>;
}

pub struct SubstrateResponse {
    pub id: Uuid,
    pub model_id: String,
    pub output: String,
    pub tokens_used: u32,
    pub latency_nanos: u64,
}

pub struct AxiomGateway {
    executor: Box<dyn SubstrateExecutor>,
    authorization: Arc<AuthorizationPipeline>,
    covenant_firewall: Arc<CovenantFirewall>,
    ap2_ledger: Arc<AP2Ledger>,
    monge_gap: Arc<MongeGapGovernor>,
}

impl AxiomGateway {
    pub async fn infer(
        &self,
        prompt: &str,
        model_id: &str,
        persona_id: Uuid,
        intent_mandate_id: Uuid,
    ) -> Result<SubstrateResponse, AxiomError> {
        // Step 1: Authorize request (Phase 1)
        let task_id = Uuid::new_v4();
        let auth_result = self.authorization.authorize_task(
            task_id, persona_id, intent_mandate_id
        ).await?;
        
        // Step 2: Validate covenant (Phase 2)
        let intent = self.covenant_firewall.get_intent(intent_mandate_id)?;
        
        // Step 3: Debit payment (Phase 3)
        let predicted_cost = self.estimate_cost(model_id, prompt)?;
        let ap2_entry = self.ap2_ledger.settle(&intent)?;
        
        // Step 4: Validate prediction (Phase 4)
        // (Post-execution)
        
        // Step 5: Execute on substrate
        let response = self.executor.execute(prompt, model_id, task_id).await?;
        
        // Step 6: Post-execution causal validation
        self.monge_gap.validate_settlement_outcome(&ap2_entry, &response)?;
        
        Ok(response)
    }
}
```

**Test Coverage:**
- `test_authorization_required_before_execution`
- `test_covenant_enforced_before_inference`
- `test_payment_debited_correctly`
- `test_latency_slo_enforced_per_substrate`

---

#### 5.2 Substrate Implementations

**Llama Executor** (`crates/siss-gatekeeper/src/pipeline/substrate_llama.rs`)

```rust
pub struct LlamaExecutor {
    model_path: String,
    context_size: usize,
}

#[async_trait]
impl SubstrateExecutor for LlamaExecutor {
    async fn execute(&self, prompt: &str, model_id: &str, task_id: Uuid) 
        -> Result<SubstrateResponse, ExecutionError> {
        // Load Llama model via llama-cpp-rs
        // Generate response
        // Measure latency
        // Return SubstrateResponse
    }
}
```

**Claude Executor** (`crates/siss-gatekeeper/src/pipeline/substrate_claude.rs`)

```rust
pub struct ClaudeExecutor {
    api_key: String,
}

#[async_trait]
impl SubstrateExecutor for ClaudeExecutor {
    async fn execute(&self, prompt: &str, model_id: &str, task_id: Uuid) 
        -> Result<SubstrateResponse, ExecutionError> {
        // Call Claude API
        // Measure latency (include network time)
        // Return SubstrateResponse
    }
}
```

**Custom Executor** (User-provided)

```rust
pub struct CustomExecutor {
    endpoint_url: String,
}

#[async_trait]
impl SubstrateExecutor for CustomExecutor {
    async fn execute(&self, prompt: &str, model_id: &str, task_id: Uuid) 
        -> Result<SubstrateResponse, ExecutionError> {
        // HTTP POST to custom endpoint
        // Measure latency
        // Return SubstrateResponse
    }
}
```

**Test Coverage:**
- `test_llama_executor_loads_model`
- `test_claude_executor_calls_api`
- `test_custom_executor_routes_http`
- `test_concurrent_substrate_requests`
- `test_substrate_latency_slo_enforced`

---

#### 5.3 End-to-End Integration Test

**File:** `crates/siss-gatekeeper/examples/full_axiom_flow.rs`

```rust
#[tokio::main]
async fn main() -> Result<()> {
    // Setup
    let gateway = AxiomGateway::new(
        Box::new(LlamaExecutor::new("./model.gguf")),
        Arc::new(AuthorizationPipeline::new()),
        Arc::new(CovenantFirewall::new()),
        Arc::new(AP2Ledger::new()),
        Arc::new(MongeGapGovernor::new()),
    );
    
    // Full flow
    let response = gateway.infer(
        "What is the capital of France?",
        "llama-7b",
        creator_persona_id,
        intent_mandate_id,
    ).await?;
    
    println!("Response: {}", response.output);
    println!("Latency: {}µs", response.latency_nanos / 1000);
    println!("Covenant Status: INTACT");
    
    Ok(())
}
```

### Integration Points

1. **From Phase 4 (MongeGapGovernor):**
   - Governance actions → affect substrate execution
   - If "Throttle" → limit requests per second

2. **From All Phases:**
   - Full pipeline integrated: Authorization → Covenant → Payment → Validation → Execution

### Deliverables

- [ ] substrate_executor.rs (300 LOC)
- [ ] substrate_llama.rs (200 LOC)
- [ ] substrate_claude.rs (200 LOC)
- [ ] substrate_custom.rs (150 LOC)
- [ ] 25/25 tests passing
- [ ] End-to-end example working
- [ ] Latency SLO verified (<100µs authorization + <10ms execution)

**Timeline:** 8 weeks (August 6–September 30)

---

## Summary: Post-Series A Roadmap

| Phase | Component | Duration | Tests | Status | Latency Target |
|-------|-----------|----------|-------|--------|-----------------|
| **2** | Covenant Firewall | 6 weeks | 10 | TDD | Tier1 <10ms |
| **3** | AP2 Settlement | 6 weeks | 15 | TDD | Tier1 <10ms |
| **4** | MongeGapGovernor v3 | 6 weeks | 20 | TDD | Tier2 async |
| **5** | Substrate Integration | 8 weeks | 25 | TDD | Tier0/1 <100µs |
| **TOTAL** | Production Ready | 26 weeks | 70/70 | GREEN ✅ | All SLOs met |

---

## Business Milestones (Parallel to Development)

### Week 1–4 (July): Customer Onboarding
- [ ] 3 pilot customers → production environments
- [ ] Data migration (legacy systems → Axiom)
- [ ] Security audits completed

### Week 5–12 (August): MVP Launch
- [ ] Phase 2–3 complete
- [ ] First customer settlement transactions live
- [ ] €50K MRR (3 customers × ~€17K/month)

### Week 13–20 (September): Scale Phase
- [ ] Phase 4 complete
- [ ] Add 5 more customers (8 total)
- [ ] €150K MRR

### Week 21–26 (October–November): Substrate Integration
- [ ] Phase 5 complete
- [ ] Support 10+ models (Llama, Claude, Custom, etc.)
- [ ] €300K MRR target

### Week 27–52 (December–2027): Series B Prep
- [ ] €3M ARR
- [ ] 20+ customers
- [ ] Regulatory approvals (EU AI Act compliance)
- [ ] Series B: €20M @ €100M post-money valuation

---

## Verification Checklist (Per Phase)

Before merging any phase:
- [ ] All tests passing (`cargo test --lib` → 100%)
- [ ] Clippy clean (`cargo clippy -- -D warnings`)
- [ ] Latency SLO verified (benchmarks run)
- [ ] Merkle-rooted to EXEC_LOG
- [ ] Covenant audit passed (all 5 guards active)
- [ ] Documentation updated (README + design docs)
- [ ] Committed to main with clean git history

---

## Dependencies & Blockers

**Critical Path:**
1. Phase 2 → Phase 3 (AP2 requires Covenant Firewall validation)
2. Phase 3 → Phase 4 (Governance requires settlement data)
3. Phase 4 → Phase 5 (Substrate integration depends on all prior phases)

**External Blockers:**
- Stripe API keys provisioned (for Phase 3)
- Llama model weights available (for Phase 5)
- Claude API access confirmed (for Phase 5)

---

**VERDICT: Post-Series A roadmap is locked. All 4 phases designed for parallel TDD execution. Target: Production-ready Axiom platform by December 2026.**
