# STREAM 1: Implementation Plan — BaselineCapsule + HarnessCapsule v1
**Status:** Ready for execution starting Aug 1, 2026  
**Duration:** 5 weeks (Aug 1-30)  
**Author:** Architecture team  
**Approval:** Pending user sign-off

---

## EXECUTIVE SUMMARY

### Goal
Deliver a production-grade governance capsule (500ms latency wrapper) that standardizes tool execution across LangChain, Ollama, and AutoGPT. This is the **foundation for Stream 2-8**.

### Deliverables
1. **siss-capsule crate** — unified governance capsule API
2. **20+ passing tests** — comprehensive coverage + latency proofs
3. **LangChain adapter** — <500ms tool execution enforcement
4. **Ollama wrapper** — <100ms token latency (GPU-accelerated)
5. **AutoGPT shim** — ReBAC policy compatibility
6. **JSON-LD output** — standardized capsule format
7. **Documentation** — API reference + integration guide

### Timeline
```
Week 1: Core infrastructure (July 30 - Aug 3)
Week 2: Isolation + JSON-LD (Aug 5 - Aug 9)
Week 3: Adapters (Aug 12 - Aug 16)
Week 4: Optimization + integration (Aug 19 - Aug 23)
Week 5: Polish + release (Aug 26 - Aug 30)
```

### Success Criteria
- [x] Architecture approved by stakeholders
- [ ] All 20+ tests GREEN
- [ ] <20ms cold path latency (siss-capsule only)
- [ ] <500ms LangChain roundtrip (incl. LLM)
- [ ] <100ms Ollama token latency
- [ ] JSON-LD output validated
- [ ] Stream 2 can depend on siss-capsule v1.0

---

## PHASE BREAKDOWN (SPEC-DRIVEN)

### PHASE 1: Core Infrastructure (Week 1, Jul 30 - Aug 3)

#### 1.1 Create siss-capsule Crate Structure
**Subtask:** Bootstrap new crate with correct dependencies and module layout

**Steps:**
1. Create `/crates/siss-capsule/` directory
2. Create `Cargo.toml` with workspace dependencies
3. Create `src/lib.rs` with module declarations
4. Create `src/types.rs` with data structures
5. Add to workspace `/Cargo.toml` members list

**Test:** `cargo build` succeeds, `cargo test` discovers tests (none yet)

**Acceptance:**
- [ ] `Cargo.toml` has all required dependencies (siss-behavioral-firewall, siss-gatekeeper, siss-audit-archiver)
- [ ] `lib.rs` exports public API
- [ ] Types compile without warnings
- [ ] `cargo test --lib` runs (0 tests at this stage)

---

#### 1.2 Define Core Types
**Subtask:** Implement CapsuleResult, ExecutionContext, PolicyDecision, CapsuleError

**Location:** `src/types.rs`

**Code Structure:**
```rust
// enums
pub enum PolicyDecision {
    Allow,
    Deny(String),
}

pub enum CapsuleError {
    PolicyDenied(String),
    UnauthorizedTool,
    ExecutionTimeout,
    AuditFailure(String),
}

pub enum IsolationLevel {
    Strict,     // 99% conservative
    Standard,   // Default
    Permissive, // 1% experimental
}

// structs
pub struct CapsuleResult { /* fields */ }
pub struct ExecutionContext { /* fields */ }
pub struct CreatorMetadata { /* fields */ }
pub struct LicensingMetadata { /* fields */ }
pub struct PhaseTrace { /* fields */ }
```

**Test:** `cargo check` succeeds, no dead code warnings

**Acceptance:**
- [ ] All types defined (8 types minimum)
- [ ] All implement serde::Serialize/Deserialize
- [ ] All implement Debug + Clone
- [ ] No unused fields or variants

---

#### 1.3 Implement BaselineCapsuleExecutor
**Subtask:** Implement 4-phase execution engine

**Location:** `src/baseline_capsule_executor.rs`

**Code Structure:**
```rust
pub struct BaselineCapsuleExecutor {
    policy_engine: Arc<PolicySet>,
    tool_capsule: Arc<ToolCallCapsule>,
    baseline: Arc<RwLock<BaselineCapsule>>,
    auditor: Arc<AuditArchiver>,
    timeout_ms: u64,
}

impl BaselineCapsuleExecutor {
    pub fn new(config: CapsuleConfig) -> Self { }
    
    pub async fn execute_request(
        &self,
        user_id: Uuid,
        tool_name: &str,
        params: serde_json::Value,
        attrs: &SovereignAttributes,
    ) -> Result<CapsuleResult, CapsuleError> {
        // Phase 1: verify_policy() -> <5ms
        // Phase 2: authorize_tool() -> <1ms
        // Phase 3: create_isolation_context() -> <10ms
        // Phase 4: log_execution() -> <2ms
        // Return: CapsuleResult
    }
}
```

**Test:** Compile, no warnings

**Acceptance:**
- [ ] 4 private methods (verify_policy, authorize_tool, create_isolation_context, log_execution)
- [ ] Each method returns appropriate type (PolicyDecision, String, ExecutionContext, Uuid)
- [ ] Main API: async execute_request() -> Result<CapsuleResult>
- [ ] Config struct with timeout_ms and isolation_level

---

#### 1.4 Write Core Tests (RED → GREEN)
**Subtask:** Create failing tests that define BaselineCapsule behavior

**Location:** `src/tests/baseline_capsule_tests.rs`

**6 Tests (all should FAIL initially):**
1. `test_record_personal_truth` — baseline recorded with confidence >0.7
2. `test_fail_closed_low_confidence` — rejected with confidence <0.7
3. `test_verify_truth_with_source` — source hash verified correctly
4. `test_merkle_root_deterministic` — same data = same root
5. `test_export_json_valid` — JSON contains all fields
6. `test_baseline_retrieval` — O(1) lookup works

**Test Pattern:**
```rust
#[tokio::test]
async fn test_record_personal_truth() {
    let executor = BaselineCapsuleExecutor::new(test_config());
    let result = executor.record_baseline("health", 72.5, 0.85).await;
    assert!(result.is_ok());
    // Additional assertions
}
```

**Acceptance:**
- [ ] All 6 tests compile
- [ ] All 6 tests FAIL before implementation
- [ ] Test names describe exact behavior
- [ ] Setup code reusable (helper functions)

---

#### 1.5 Implement to Make Tests PASS
**Subtask:** Implement BaselineCapsule methods to satisfy all 6 tests

**Location:** `src/baseline_capsule_executor.rs` (new methods)

**Methods to Implement:**
- `record_baseline(domain, baseline, confidence)` → Result<()>
- `verify_baseline(domain, baseline)` → bool
- `export_json()` → String
- `get_baseline(domain)` → Option<f64>

**Test:** `cargo test --lib baseline_capsule_tests` → all 6 GREEN

**Acceptance:**
- [ ] All 6 tests GREEN
- [ ] No clippy warnings
- [ ] Code follows existing style (siss-gatekeeper baseline_capsule.rs)

---

### PHASE 2: Isolation, JSON-LD, and Testing (Week 2, Aug 5 - Aug 9)

#### 2.1 Implement Isolation & Rollback
**Subtask:** StateSnapshot + commit/rollback logic

**Location:** `src/isolation.rs`

**Code Structure:**
```rust
pub struct StateSnapshot {
    pre_execution: serde_json::Value,
    post_execution: Option<serde_json::Value>,
    committed: bool,
}

impl StateSnapshot {
    pub fn new(pre_state: serde_json::Value) -> Self { }
    pub fn commit(&mut self) -> Result<(), IsolationError> { }
    pub fn rollback(&mut self) -> Result<(), IsolationError> { }
    pub fn verify_merkle() -> Result<(), IsolationError> { }
}
```

**Test:** Compile, unit tests for commit/rollback logic

**Acceptance:**
- [ ] StateSnapshot struct defined + serializable
- [ ] commit() changes committed flag
- [ ] rollback() restores pre_execution state
- [ ] merkle proof validation before commit

---

#### 2.2 Implement JSON-LD Export
**Subtask:** CapsuleResult → JSON-LD with @context

**Location:** `src/jsonld_export.rs`

**Code Structure:**
```rust
pub fn serialize_to_jsonld(result: &CapsuleResult) -> serde_json::Value {
    // Build @context
    // Add all required fields (id, timestamp, decision, etc.)
    // Nest execution_phases
    // Include creator + licensing metadata
    // Return: valid JSON-LD
}

pub fn validate_jsonld_schema(value: &serde_json::Value) -> Result<(), String> {
    // Check required fields exist
    // Check @context is valid
    // Check confidential fields are encrypted if sensitive
}
```

**Test:** `cargo test --lib jsonld` (no tests yet, but structure ready for Phase 3)

**Acceptance:**
- [ ] serialize_to_jsonld() produces valid JSON
- [ ] @context contains required vocabulary
- [ ] All CapsuleResult fields represented
- [ ] Execution phases nested as array

---

#### 2.3 Write Isolation Tests (3 tests)
**Subtask:** State snapshot + commit + rollback

**Location:** `src/tests/isolation_tests.rs`

**3 Tests (RED → GREEN):**
1. `test_state_snapshot_commit` — snapshot commits successfully
2. `test_state_snapshot_rollback` — failed execution rolls back state
3. `test_isolation_level_enforcement` — Strict/Standard/Permissive respected

**Test Pattern:**
```rust
#[tokio::test]
async fn test_state_snapshot_commit() {
    let snapshot = StateSnapshot::new(serde_json::json!({"x": 1}));
    let result = snapshot.commit();
    assert!(result.is_ok());
}
```

**Acceptance:**
- [ ] All 3 tests compile
- [ ] All 3 tests FAIL initially
- [ ] After implementation, all 3 GREEN

---

#### 2.4 Write JSON-LD Tests (2 tests)
**Subtask:** JSON-LD output validation

**Location:** `src/tests/jsonld_output_tests.rs`

**2 Tests (RED → GREEN):**
1. `test_jsonld_schema_valid` — output conforms to JSON-LD spec
2. `test_jsonld_context_required_fields` — @context complete

**Acceptance:**
- [ ] Both tests compile
- [ ] Both FAIL initially
- [ ] After implementation, both GREEN

---

#### 2.5 Write Policy Verification Tests (5 tests)
**Subtask:** ReBAC policy enforcement

**Location:** `src/tests/policy_verification_tests.rs`

**5 Tests (RED → GREEN):**
1. `test_policy_allow_high_trust` — TrustLevel >= threshold → Allow
2. `test_policy_deny_low_reputation` — Reputation < threshold → Deny
3. `test_policy_deny_blacklisted` — Blacklisted → Deny
4. `test_policy_and_predicate` — Multiple conditions (AND)
5. `test_policy_fail_closed_default` — No rules → Deny

**Acceptance:**
- [ ] All 5 tests compile + FAIL initially
- [ ] Tests integrate with existing AP2 PolicySet
- [ ] All 5 GREEN after implementation

---

#### 2.6 Write Tool Authorization Tests (3 tests)
**Subtask:** ToolCallCapsule authorization

**Location:** `src/tests/tool_authorization_tests.rs`

**3 Tests (RED → GREEN):**
1. `test_tool_authorization_success` — Authorized tool → Merkle proof
2. `test_tool_authorization_fail_closed` — Unauthorized → Reject
3. `test_concurrent_authorizations` — Thread-safe concurrent calls

**Acceptance:**
- [ ] All 3 compile + FAIL
- [ ] Tests use Arc<ToolCallCapsule> for threading
- [ ] All 3 GREEN after implementation

---

#### 2.7 Checkpoint 1 Verification
**Subtask:** Verify Week 1-2 deliverables

**Checklist:**
- [ ] `cargo test --lib` → 18 GREEN (6 + 3 + 2 + 5 + 3 - 1 duplicate)
- [ ] `cargo clippy -- -D warnings` → 0 warnings
- [ ] `cargo fmt --check` → all files formatted
- [ ] Latency assertions in tests (not just logic)
- [ ] Documentation comments on all public functions

---

### PHASE 3: Adapter Implementation (Week 3, Aug 12 - Aug 16)

#### 3.1 Implement LangChain Adapter
**Subtask:** Tool use event interception + routing

**Location:** `src/adapters/langchain.rs`

**Code Structure:**
```rust
pub struct LangChainHarness {
    executor: Arc<BaselineCapsuleExecutor>,
    model_name: String,
}

impl LangChainHarness {
    pub async fn intercept_tool_use(
        &self,
        event: &ToolUseEvent,
        agent_id: Uuid,
    ) -> Result<CertifiedDecision, HarnessError> {
        // 1. Extract tool_name, params from event
        // 2. Call executor.execute_request()
        // 3. Return CertifiedDecision
        // Latency target: <500ms total (incl. LLM)
    }
}
```

**Test:** Compile, integration test (Phase 3.4)

**Acceptance:**
- [ ] LangChainHarness struct defined
- [ ] intercept_tool_use() returns CertifiedDecision
- [ ] Latency measurement included
- [ ] Error handling for network/timeout

---

#### 3.2 Implement Ollama Wrapper
**Subtask:** Local inference with GPU acceleration

**Location:** `src/adapters/ollama.rs`

**Code Structure:**
```rust
pub struct OllamaLocalInference {
    base_url: String,
    model_name: String,
    gpu_enabled: bool,
}

impl OllamaLocalInference {
    pub async fn infer(&self, prompt: &str) -> Result<InferenceResult, InferenceError> {
        // 1. Check GPU availability (Metal/CUDA/CPU)
        // 2. Stream tokens from /api/generate endpoint
        // 3. Measure per-token latency <100ms
        // 4. Return aggregated metrics
    }
    
    pub async fn health_check(&self) -> Result<HealthStatus, InferenceError> {
        // Verify Ollama running + model available
    }
}
```

**Test:** Compile, integration test (Phase 3.4)

**Acceptance:**
- [ ] OllamaLocalInference struct defined
- [ ] infer() supports streaming
- [ ] health_check() detects GPU vs CPU
- [ ] Fallback logic if GPU unavailable

---

#### 3.3 Implement AutoGPT Shim
**Subtask:** Plugin schema mapping + compatibility

**Location:** `src/adapters/autogpt.rs`

**Code Structure:**
```rust
pub struct AutoGPTCompatibilityShim {
    executor: Arc<BaselineCapsuleExecutor>,
    schema_mapper: AutoGPTSchemaMapper,
}

impl AutoGPTCompatibilityShim {
    pub async fn validate_plugin_execution(
        &self,
        plugin_name: &str,
        action: &str,
        params: serde_json::Value,
        context: &AgentContext,
    ) -> Result<CertifiedExecution, PluginError> {
        // 1. Map plugin action → ReBAC policy
        // 2. Call executor.execute_request()
        // 3. Return CertifiedExecution
    }
}
```

**Test:** Compile, integration test (Phase 3.4)

**Acceptance:**
- [ ] AutoGPTCompatibilityShim struct defined
- [ ] validate_plugin_execution() maps schema
- [ ] Returns CertifiedExecution (approved/denied)
- [ ] Audit trail maintained

---

#### 3.4 Write LangChain Integration Tests (2 tests)
**Subtask:** End-to-end with real agent loop

**Location:** `src/tests/langchain_integration_tests.rs`

**2 Tests (RED → GREEN):**
1. `test_langchain_tool_use_interception` — tool_use → routing → decision
2. `test_langchain_latency_<500ms` — roundtrip <500ms (incl. LLM)

**Test Pattern:**
```rust
#[tokio::test]
async fn test_langchain_tool_use_interception() {
    let harness = LangChainHarness::new(...);
    let event = ToolUseEvent { ... };
    let decision = harness.intercept_tool_use(&event, agent_id).await;
    assert!(decision.is_ok());
    assert!(decision.unwrap().capsule_result.execution_latency_ms < 500.0);
}
```

**Acceptance:**
- [ ] Both tests compile + FAIL
- [ ] Latency measurement in test assertions
- [ ] Mock LangChain event structure
- [ ] Both GREEN after implementation

---

#### 3.5 Write Ollama Tests (2 tests)
**Subtask:** Token streaming + latency

**Location:** `src/tests/ollama_tests.rs`

**2 Tests (RED → GREEN):**
1. `test_ollama_inference_streaming` — tokens streamed end-to-end
2. `test_ollama_latency_<100ms_per_token` — per-token <100ms

**Acceptance:**
- [ ] Both compile + FAIL
- [ ] Mock Ollama HTTP responses
- [ ] Per-token latency measured
- [ ] GPU availability mocked
- [ ] Both GREEN after implementation

---

#### 3.6 Write AutoGPT Tests (2 tests)
**Subtask:** Plugin schema compatibility

**Location:** `src/tests/autogpt_tests.rs`

**2 Tests (RED → GREEN):**
1. `test_autogpt_plugin_schema_mapping` — schema → policy
2. `test_autogpt_certified_execution` — decision approved

**Acceptance:**
- [ ] Both compile + FAIL
- [ ] Mock AutoGPT plugin schema
- [ ] Both GREEN after implementation

---

#### 3.7 Checkpoint 2 Verification
**Subtask:** Verify Week 3 deliverables

**Checklist:**
- [ ] `cargo test --lib` → 24 GREEN (all previous + 6 new)
- [ ] LangChain adapter compiles without warnings
- [ ] Ollama wrapper compiles without warnings
- [ ] AutoGPT shim compiles without warnings
- [ ] All latency assertions present
- [ ] Integration test setup complete

---

### PHASE 4: Optimization & Integration (Week 4, Aug 19 - Aug 23)

#### 4.1 Latency Optimization
**Subtask:** Benchmark all phases, identify bottlenecks

**Location:** `benches/latency_bench.rs`

**Benchmarks:**
- Phase 1: Policy verification (<5ms)
- Phase 2: Tool authorization (<1ms)
- Phase 3: Isolation context (<10ms)
- Phase 4: Audit logging (<2ms)
- Total cold path (<20ms)
- Total warm path (with caching) (<10ms)

**Test:** `cargo bench --bench latency_bench` → all targets <threshold

**Acceptance:**
- [ ] All phases measured individually
- [ ] Warm path (cached) is 2x faster than cold
- [ ] Bottlenecks identified and documented
- [ ] Optimization candidates marked for future

---

#### 4.2 LangChain Roundtrip Benchmark
**Subtask:** Measure total latency with real LLM

**Location:** `benches/langchain_roundtrip_bench.rs`

**Benchmark:**
- Full roundtrip: user query → LLM inference → tool call → capsule → decision → return
- Target: <500ms

**Test:** `cargo bench --bench langchain_roundtrip_bench` → <500ms

**Acceptance:**
- [ ] Benchmark includes network time
- [ ] Measures real LLM inference (Ollama or similar)
- [ ] Multiple iterations (10+) for variance
- [ ] Results documented

---

#### 4.3 Full Integration Test
**Subtask:** End-to-end test with all 3 adapters

**Location:** `src/tests/full_integration_test.rs` (new)

**Test Scenario:**
1. User submits policy + attributes
2. Three adapters execute in parallel
3. All return CertifiedDecision within SLA
4. Audit trail shows all executions

**Acceptance:**
- [ ] Test compiles
- [ ] All 3 adapters execute successfully
- [ ] Latency SLAs verified
- [ ] Audit trail complete

---

#### 4.4 Documentation + Examples
**Subtask:** API reference + integration guide

**Location:** `README.md`, `docs/INTEGRATION_GUIDE.md`

**Content:**
- API overview (public types + functions)
- Usage examples (LangChain, Ollama, AutoGPT)
- Configuration guide (timeout, isolation level, etc.)
- Troubleshooting section

**Acceptance:**
- [ ] README.md documents crate purpose
- [ ] Examples are copy-paste ready
- [ ] Configuration documented
- [ ] Error handling guide included

---

#### 4.5 Checkpoint 3 Verification
**Subtask:** Verify Week 4 deliverables

**Checklist:**
- [ ] All 24 tests GREEN
- [ ] `cargo bench` shows all latencies <threshold
- [ ] LangChain roundtrip <500ms verified
- [ ] Full integration test passing
- [ ] Documentation complete + accurate

---

### PHASE 5: Polish & Release (Week 5, Aug 26 - Aug 30)

#### 5.1 Code Review
**Subtask:** Self-review + cleanup

**Checklist:**
- [ ] All code follows siss-gatekeeper style
- [ ] No clippy warnings (run `cargo clippy -- -D warnings`)
- [ ] No dead code (run `cargo dead-code-detector`)
- [ ] Comments accurate + up-to-date
- [ ] Tests are deterministic (no flakes)

---

#### 5.2 Bug Fixes & Edge Cases
**Subtask:** Address any test failures or issues

**Process:**
1. Run full test suite (`cargo test --release`)
2. Document any failures
3. Fix root causes (not workarounds)
4. Verify fixes don't introduce regressions

---

#### 5.3 Final Verification
**Subtask:** Execute all checkpoints one more time

**Checklist:**
- [ ] `cargo test --lib` → all GREEN (no flakes)
- [ ] `cargo bench` → latencies stable
- [ ] `cargo clippy -- -D warnings` → 0 warnings
- [ ] `cargo fmt --check` → all formatted
- [ ] Documentation reviewed + accurate

---

#### 5.4 Release Tagging
**Subtask:** Tag v1.0 for Stream 2 dependency

**Steps:**
1. Verify version in Cargo.toml: `0.1.0` (workspace version)
2. Create git tag: `git tag -a siss-capsule-v1.0 -m "STREAM 1: BaselineCapsule + HarnessCapsule v1.0"`
3. Push tag: `git push origin siss-capsule-v1.0`
4. Document in RELEASE_NOTES.md

---

#### 5.5 Final Checkpoint
**Subtask:** Confirm readiness for Stream 2

**Checklist:**
- [ ] All 24+ tests GREEN
- [ ] Latency budgets verified
- [ ] Documentation complete
- [ ] v1.0 tagged
- [ ] Stream 2 can depend on siss-capsule = "0.1.0"

---

## SUCCESS METRICS

### Code Quality
- Zero clippy warnings
- Zero dead code
- 100% public API documented
- All tests deterministic (no flakes)

### Latency
- Cold path: <20ms (all phases)
- Warm path: <10ms (with caching)
- LangChain roundtrip: <500ms (incl. LLM)
- Ollama token latency: <100ms per token

### Test Coverage
- 20+ tests total
- 100% of public API covered
- All acceptance criteria tested
- Latency assertions in all integration tests

### Documentation
- README.md with examples
- Integration guide for each adapter
- Configuration reference
- Troubleshooting section

---

## RISK MITIGATION

### Risk 1: Latency Budget Exceeded
**Probability:** Medium  
**Impact:** High (blocks Stream 2)  
**Mitigation:**
- Benchmark early (Week 1)
- Identify bottlenecks Week 2
- Optimize Week 4
- Fallback: prioritize cold path <20ms over <500ms LangChain

### Risk 2: LangChain API Changes
**Probability:** Low  
**Impact:** Medium (adapter breaks)  
**Mitigation:**
- Use stable LangChain v0.1.x API
- Wrap tool_use event structure in adapter
- Version pin in Cargo.toml

### Risk 3: Ollama Not Available
**Probability:** Medium  
**Impact:** Low (integration test skipped)  
**Mitigation:**
- Detect Ollama availability in health_check()
- Skip tests if unavailable
- Document fallback to CPU

### Risk 4: Test Flakiness
**Probability:** Medium (concurrency, timing)  
**Impact:** Medium (release delay)  
**Mitigation:**
- Use tokio::test with seed for determinism
- Add retries for integration tests
- Document flaky tests + root causes

---

## DEPENDENCIES & BLOCKERS

### Hard Dependencies (Must Complete Before PHASE 1)
- [x] siss-behavioral-firewall compiled
- [x] siss-gatekeeper compiled
- [x] siss-audit-archiver compiled
- [x] Cargo workspace accepts new members

### Soft Dependencies (Nice to Have)
- [ ] Ollama installed on dev machine (for Ollama tests)
- [ ] LangChain v0.1.x available (pip install)
- [ ] AutoGPT available (pip install)

---

## TEAM ASSIGNMENTS (If Parallel Work)

### Single-Agent Execution (Recommended)
All 5 phases executed sequentially by one agent with TDD discipline.

### Multi-Agent Execution (If Needed)
- **Agent A:** Phases 1-2 (Core + Isolation)
- **Agent B:** Phases 3-5 (Adapters + Polish)
- **Sync point:** EOW Aug 16 (before Phase 3)

---

## HANDOFF TO STREAM 2

### What Stream 2 Can Depend On
- siss-capsule = "0.1.0" (in Cargo.toml)
- Public API: BaselineCapsuleExecutor, CapsuleResult, ExecutionContext
- Latency SLA: <20ms cold path, <500ms roundtrip
- JSON-LD output format (schema defined)

### What Stream 2 Must Do
1. Consume siss-capsule::BaselineCapsuleExecutor
2. Extend with VisionAPI-specific capsule types
3. Integrate with Stream 1 audit trail
4. Reference Stream 1 JSON-LD @context

### Documentation Stream 2 Needs
- siss-capsule/INTEGRATION_GUIDE.md (BaselineCapsuleExecutor API)
- siss-capsule/JSON_LD_SPEC.md (output format)
- siss-capsule/LATENCY_PROFILE.md (benchmarks)

---

## APPROVAL SIGNATURES

### Architecture Review
- [ ] Stakeholder: Approved
- [ ] Date: ___________

### Implementation Kickoff
- [ ] Lead Agent: Ready to start
- [ ] Date: ___________

### Final Release Approval
- [ ] QA Lead: All tests GREEN
- [ ] Date: ___________

---

## APPENDIX: DETAILED TASK BREAKDOWN

### Week 1 Day-by-Day
- **Mon (Jul 30):** 1.1-1.2 (crate setup + types) → cargo build succeeds
- **Tue (Jul 31):** 1.3 (BaselineCapsuleExecutor) → compiles
- **Wed (Aug 1):** 1.4-1.5 (tests RED → GREEN) → 6 tests passing
- **Thu-Fri (Aug 2-3):** Checkpoint 1 verification

### Week 2 Day-by-Day
- **Mon (Aug 5):** 2.1 (isolation) + 2.2 (JSON-LD) → compile
- **Tue (Aug 6):** 2.3-2.5 (tests RED) → all tests failing
- **Wed (Aug 7):** 2.3-2.5 (tests GREEN) → implementations complete
- **Thu-Fri (Aug 8-9):** Checkpoint 2 verification

### Week 3 Day-by-Day
- **Mon (Aug 12):** 3.1-3.3 (adapters RED) → test structure ready
- **Tue-Wed (Aug 13-14):** 3.1-3.3 (adapters GREEN) → all compile
- **Thu-Fri (Aug 15-16):** 3.4-3.6 (integration tests) → Checkpoint 2 verify

### Week 4 Day-by-Day
- **Mon-Tue (Aug 19-20):** 4.1-4.2 (benchmarks) → latency verified
- **Wed (Aug 21):** 4.3-4.4 (full integration + docs) → GREEN
- **Thu-Fri (Aug 22-23):** Checkpoint 3 verification

### Week 5 Day-by-Day
- **Mon-Tue (Aug 26-27):** 5.1-5.2 (code review + fixes)
- **Wed (Aug 28):** 5.3-5.4 (final verification + tagging)
- **Thu-Fri (Aug 29-30):** Buffer + release prep

---

**Status:** Ready for sign-off. All phases detailed, acceptance criteria clear, risks identified.

