# STREAM 1: BaselineCapsule + HarnessCapsule v1 — Architecture Specification
**Status:** Architecture ready for implementation (Aug 1-31)  
**Timeline:** July 30 (architecture finalization) → Aug 1-31 (coding sprint)  
**Deliverable:** Production-grade governance capsule with <500ms latency wrappers

---

## 1. OVERVIEW

### Goal
Productionize the core governance capsule (ReBAC policy enforcement + execution isolation) with <500ms latency adapters for three AI frameworks:
1. **LangChain** — agent orchestration
2. **Ollama** (Qwen/Gemma) — local-first inference  
3. **AutoGPT** — plugin compatibility

### Success Criteria
- [ ] BaselineCapsule compiles and passes all tests
- [ ] All 20+ acceptance tests GREEN
- [ ] LangChain integration: <500ms roundtrip (including LLM inference)
- [ ] Ollama token latency: <100ms per token (GPU-accelerated)
- [ ] AutoGPT shim: full schema compatibility
- [ ] JSON-LD output: spec-compliant with @context
- [ ] Ready for Stream 2 (VisionAPI SDK) to build on top

### Existing Infrastructure
- **BaselineCapsule** (`siss-gatekeeper/baseline_capsule.rs`) — personal truth baseline with Merkle-DAG audit
- **ToolCallCapsule** (`siss-gatekeeper/capsules/tool_call.rs`) — tool authorization with fail-closed gates
- **AP2 Policies** (`siss-behavioral-firewall/ap2.rs`) — ReBAC + attribute-based access control
- **AuditArchiver** (`siss-audit-archiver/lib.rs`) — hot/cold storage with S3 archival
- **CovenantFirewall** (`siss-behavioral-firewall/covenant_firewall.rs`) — behavioral rule enforcement

---

## 2. ARCHITECTURE

```
┌──────────────────────────────────────────────────────────────────┐
│ STREAM 1: BaselineCapsule + HarnessCapsule v1                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─ siss-capsule (NEW CRATE) ──────────────────────────────────┐ │
│  │                                                              │ │
│  │  BaselineCapsule Wrapper                                   │ │
│  │  ├─ Policy Verification (ReBAC)                            │ │
│  │  │  └─ <5ms: Permission checks via AP2                     │ │
│  │  │                                                          │ │
│  │  ├─ Tool Authorization (ToolCallCapsule)                   │ │
│  │  │  └─ <1ms: Hash-based proof generation                   │ │
│  │  │                                                          │ │
│  │  ├─ Execution Context (Isolation)                          │ │
│  │  │  └─ State rollback on failure                           │ │
│  │  │  └─ 1%/99% covenant enforcement                         │ │
│  │  │                                                          │ │
│  │  └─ Audit Logging (AuditArchiver)                          │ │
│  │     └─ <2ms: Trace to hot storage                          │ │
│  │                                                              │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                              ↓                                    │
│  ┌─ HarnessCapsule (v1 Adapters) ────────────────────────────────┐│
│  │                                                               ││
│  │  ┌─ LangChain Adapter ──────────────────────────────────┐   ││
│  │  │ • Intercept tool_use events                          │   ││
│  │  │ • Route through BaselineCapsule                      │   ││
│  │  │ • Return certified decision                          │   ││
│  │  │ • Target: <500ms total (incl. LLM)                  │   ││
│  │  └──────────────────────────────────────────────────────┘   ││
│  │                                                               ││
│  │  ┌─ Ollama Wrapper ─────────────────────────────────────┐   ││
│  │  │ • Local-first inference (Qwen 7B/14B, Gemma 7B)      │   ││
│  │  │ • Streaming response support                         │   ││
│  │  │ • GPU acceleration (Metal/CUDA fallback to CPU)      │   ││
│  │  │ • Target: <100ms per token                           │   ││
│  │  └──────────────────────────────────────────────────────┘   ││
│  │                                                               ││
│  │  ┌─ AutoGPT Shim ───────────────────────────────────────┐   ││
│  │  │ • Map AutoGPT tool schema → ReBAC policy             │   ││
│  │  │ • Certified decision return to AutoGPT loop          │   ││
│  │  │ • Full plugin compatibility                          │   ││
│  │  └──────────────────────────────────────────────────────┘   ││
│  │                                                               ││
│  └──────────────────────────────────────────────────────────────┘│
│                              ↓                                    │
│  ┌─ Capsule Output (Standardized) ──────────────────────────────┐│
│  │                                                               ││
│  │  JSON-LD Format with @context                               ││
│  │  ├─ Creator licensing metadata                              ││
│  │  ├─ Merkle-DAG audit proof                                  ││
│  │  ├─ Execution trace (all phases)                            ││
│  │  └─ Confidence score (γ-operator)                           ││
│  │                                                               ││
│  └──────────────────────────────────────────────────────────────┘│
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

### Phase Dependencies
- **Phase 1:** BaselineCapsule + HarnessCapsule core (siss-capsule + adapters)
- **Phase 2:** Stream 2 (VisionAPI SDK) builds on Phase 1
- **Phase 3:** Stream 3+ use standardized Capsule output format

---

## 3. DETAILED MODULE SPECIFICATION

### Module 1: siss-capsule (NEW CRATE)
**Path:** `/crates/siss-capsule/`

#### Dependencies
```toml
[dependencies]
siss-behavioral-firewall = { path = "../siss-behavioral-firewall" }
siss-gatekeeper = { path = "../siss-gatekeeper" }
siss-audit-archiver = { path = "../siss-audit-archiver" }
uuid.workspace = true
chrono.workspace = true
serde.workspace = true
serde_json.workspace = true
tokio.workspace = true
sha2.workspace = true
```

#### Core Types (`src/lib.rs` + `src/types.rs`)

```rust
/// Result of a BaselineCapsule execution
pub struct CapsuleResult {
    pub id: Uuid,
    pub decision: PolicyDecision,           // Allow / Deny
    pub tool_name: String,
    pub execution_context: ExecutionContext,
    pub merkle_proof: String,               // Hex-encoded SHA-256
    pub confidence_score: f64,              // γ-operator result
    pub execution_latency_ms: f64,
    pub audit_trace_id: Uuid,
    pub timestamp: SystemTime,
}

/// Execution context for isolation & rollback
pub struct ExecutionContext {
    pub state_snapshot: serde_json::Value, // Pre-execution state
    pub isolation_level: IsolationLevel,   // Strict / Standard / Permissive
    pub covenant_enforcement: CovenantEnforcement,
}

/// Covenant 1%/99% split
pub enum CovenantEnforcement {
    Strict,     // 99% conservative: reject on any doubt
    Standard,   // Default: balanced allow/deny
    Permissive, // 1% experimental: allow edge cases
}

/// JSON-LD @context for output
pub struct CapsuleContext {
    pub schema_version: String,
    pub creator: CreatorMetadata,
    pub licensing: LicensingMetadata,
    pub execution_phases: Vec<PhaseTrace>,
}

pub struct CreatorMetadata {
    pub sovereign_id: Uuid,
    pub organization: Option<String>,
    pub certification_chain: Vec<String>,
}

pub struct LicensingMetadata {
    pub license_type: String, // MIT, CC0, Proprietary
    pub expires_at: Option<SystemTime>,
    pub usage_restrictions: Vec<String>,
}

pub struct PhaseTrace {
    pub phase_name: String,
    pub decision: PolicyDecision,
    pub latency_ms: f64,
    pub phase_outcome: serde_json::Value,
}
```

#### Main API (`src/baseline_capsule_executor.rs`)

```rust
pub struct BaselineCapsuleExecutor {
    // Owned components
    policy_engine: Arc<PolicySet>,
    tool_capsule: Arc<ToolCallCapsule>,
    baseline: Arc<RwLock<BaselineCapsule>>,
    auditor: Arc<AuditArchiver>,
    
    // Config
    timeout_ms: u64,
    isolation_level: IsolationLevel,
}

impl BaselineCapsuleExecutor {
    pub fn new(config: CapsuleConfig) -> Self { }
    
    /// Execute user request with full governance stack
    /// Returns: CapsuleResult with all audit metadata
    pub async fn execute_request(
        &self,
        user_id: Uuid,
        tool_name: &str,
        params: serde_json::Value,
        sovereign_attrs: &SovereignAttributes,
    ) -> Result<CapsuleResult, CapsuleError> {
        // Phase 1: Policy Verification (<5ms)
        let policy_decision = self.verify_policy(user_id, tool_name, sovereign_attrs)?;
        
        // Phase 2: Tool Authorization (<1ms)
        let merkle_proof = self.authorize_tool(tool_name, &params)?;
        
        // Phase 3: Execution Isolation
        let exec_context = self.create_isolation_context(&params)?;
        
        // Phase 4: Audit Logging (<2ms)
        let trace_id = self.log_execution(&user_id, tool_name, &policy_decision)?;
        
        // Return standardized Capsule output
        Ok(CapsuleResult { /* ... */ })
    }
    
    /// Export as JSON-LD with full @context
    pub fn export_jsonld(&self, result: &CapsuleResult) -> String { }
    
    fn verify_policy(
        &self,
        user_id: Uuid,
        tool_name: &str,
        attrs: &SovereignAttributes,
    ) -> Result<PolicyDecision, CapsuleError> {
        // Fail-closed: ReBAC check via AP2
    }
    
    fn authorize_tool(
        &self,
        tool_name: &str,
        params: &serde_json::Value,
    ) -> Result<String, CapsuleError> {
        // Merkle proof from ToolCallCapsule
    }
    
    fn create_isolation_context(
        &self,
        params: &serde_json::Value,
    ) -> Result<ExecutionContext, CapsuleError> {
        // State snapshot for rollback
    }
    
    fn log_execution(
        &self,
        user_id: &Uuid,
        tool_name: &str,
        decision: &PolicyDecision,
    ) -> Result<Uuid, CapsuleError> {
        // AuditArchiver trace
    }
}
```

#### Isolation & Rollback (`src/isolation.rs`)

```rust
pub struct StateSnapshot {
    pub pre_execution: serde_json::Value,
    pub post_execution: Option<serde_json::Value>,
    pub committed: bool,
}

impl StateSnapshot {
    pub fn commit(&mut self) -> Result<(), IsolationError> {
        // Merkle-proof validation before commit
    }
    
    pub fn rollback(&mut self) -> Result<(), IsolationError> {
        // Restore pre_execution state
    }
}
```

---

### Module 2: HarnessCapsule LangChain Adapter
**Path:** `/crates/siss-capsule/src/adapters/langchain.rs`

#### API

```rust
pub struct LangChainHarness {
    executor: Arc<BaselineCapsuleExecutor>,
    model_name: String,
    max_tokens: usize,
}

impl LangChainHarness {
    pub async fn intercept_tool_use(
        &self,
        event: &ToolUseEvent,
        agent_id: Uuid,
    ) -> Result<CertifiedDecision, HarnessError> {
        // 1. Extract tool_name and params from LangChain event
        // 2. Route through BaselineCapsuleExecutor
        // 3. Return decision (Allow/Deny) + audit proof
        // 4. Log to audit trail
        // Total latency target: <500ms (incl. LLM time)
    }
    
    /// Run agent with capsule enforcement
    pub async fn run_agent(
        &self,
        system_prompt: &str,
        user_query: &str,
        tools: Vec<ToolDefinition>,
    ) -> Result<AgentResponse, HarnessError> {
        // LangChain agent loop with interception
    }
}

pub struct CertifiedDecision {
    pub tool_name: String,
    pub decision: PolicyDecision,
    pub proof_hash: String,
    pub capsule_result: CapsuleResult,
}
```

#### Implementation Notes
- Intercepts `tool_use` events from LangChain's agent loop
- Does NOT modify LangChain internal code — pure wrapper
- Handles tool parameter validation before delegation
- Returns decision to agent loop for next action selection

---

### Module 3: HarnessCapsule Ollama Wrapper
**Path:** `/crates/siss-capsule/src/adapters/ollama.rs`

#### API

```rust
pub struct OllamaLocalInference {
    base_url: String,
    model_name: String, // "qwen2:7b" or "gemma:7b"
    gpu_enabled: bool,
}

impl OllamaLocalInference {
    pub async fn infer(
        &self,
        prompt: &str,
        context: Option<&str>,
    ) -> Result<InferenceResult, InferenceError> {
        // 1. Check GPU availability (Metal on macOS, CUDA on Linux)
        // 2. Call Ollama /api/generate streaming endpoint
        // 3. Measure token latency: <100ms per token
        // 4. Stream tokens back to caller
        // 5. Aggregate metrics for monitoring
    }
    
    /// Check if Ollama service is running + model available
    pub async fn health_check(&self) -> Result<HealthStatus, InferenceError> {
        // Detect: (a) Ollama service running, (b) Model downloaded
    }
    
    /// Fallback to CPU if GPU not available
    pub fn fallback_to_cpu(&mut self) -> Result<(), InferenceError> {
        // Update config, reconnect
    }
}

pub struct InferenceResult {
    pub text: String,
    pub tokens_generated: u32,
    pub tokens_per_second: f64,
    pub latency_ms: f64,
    pub gpu_used: bool,
}
```

#### Implementation Notes
- Uses Ollama HTTP API (streaming to preserve latency budget)
- Supports both Qwen 7B/14B and Gemma 7B models
- Graceful fallback to CPU if GPU unavailable
- Measures per-token latency (not just total roundtrip)

---

### Module 4: HarnessCapsule AutoGPT Shim
**Path:** `/crates/siss-capsule/src/adapters/autogpt.rs`

#### API

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
        agent_context: &AgentContext,
    ) -> Result<CertifiedExecution, PluginError> {
        // 1. Map AutoGPT action → ReBAC policy check
        // 2. Extract ReBAC attributes from agent_context
        // 3. Call BaselineCapsuleExecutor
        // 4. Return certified decision + audit proof to AutoGPT loop
    }
    
    /// Translate AutoGPT plugin schema to ReBAC policies
    fn map_plugin_to_policy(&self, plugin_schema: &AutoGPTPluginSchema) -> PolicyRule {
        // Convert plugin permissions → AP2 predicate
    }
}

pub struct CertifiedExecution {
    pub plugin_name: String,
    pub action: String,
    pub approved: bool,
    pub deny_reason: Option<String>,
    pub proof_hash: String,
}
```

#### Implementation Notes
- Maps AutoGPT plugin schema to ReBAC policies (bidirectional)
- Does NOT fork or modify AutoGPT core
- Returns structured decisions that AutoGPT can natively consume
- Maintains audit trail for plugin executions

---

## 4. TEST SUITE SPECIFICATION

### Test Categories

#### 4.1 Core BaselineCapsule Tests (6 tests)
Location: `crates/siss-capsule/src/tests/baseline_capsule_tests.rs`

- **test_record_personal_truth:** Record baseline with confidence >0.7
- **test_fail_closed_low_confidence:** Reject records with confidence <0.7
- **test_verify_truth_with_source:** Cryptographic source verification
- **test_merkle_root_deterministic:** Same data → same Merkle root
- **test_export_json_valid:** JSON output contains all fields
- **test_baseline_retrieval:** O(1) baseline lookup by domain

#### 4.2 Policy Verification Tests (5 tests)
Location: `crates/siss-capsule/src/tests/policy_verification_tests.rs`

- **test_policy_allow_high_trust:** TrustLevel >= threshold → Allow
- **test_policy_deny_low_reputation:** Reputation < threshold → Deny
- **test_policy_deny_blacklisted:** Blacklisted attribute → Deny
- **test_policy_and_predicate:** Multiple conditions (AND) evaluate correctly
- **test_policy_fail_closed_default:** No matching rules → Deny

#### 4.3 Tool Authorization Tests (3 tests)
Location: `crates/siss-capsule/src/tests/tool_authorization_tests.rs`

- **test_tool_authorization_success:** Authorized tool → Merkle proof generated
- **test_tool_authorization_fail_closed:** Unauthorized tool → Reject
- **test_concurrent_authorizations:** Thread-safe concurrent calls

#### 4.4 Isolation & Rollback Tests (3 tests)
Location: `crates/siss-capsule/src/tests/isolation_tests.rs`

- **test_state_snapshot_commit:** Snapshot commits successfully
- **test_state_snapshot_rollback:** Failed execution rolls back state
- **test_isolation_level_enforcement:** Strict/Standard/Permissive levels respected

#### 4.5 LangChain Integration Tests (2 tests)
Location: `crates/siss-capsule/src/tests/langchain_integration_tests.rs`

- **test_langchain_tool_use_interception:** tool_use event → capsule routing
- **test_langchain_latency_<500ms:** Roundtrip including LLM inference <500ms

#### 4.6 Ollama Inference Tests (2 tests)
Location: `crates/siss-capsule/src/tests/ollama_tests.rs`

- **test_ollama_inference_streaming:** Token streaming works end-to-end
- **test_ollama_latency_<100ms_per_token:** Per-token latency <100ms (GPU)

#### 4.7 AutoGPT Compatibility Tests (2 tests)
Location: `crates/siss-capsule/src/tests/autogpt_tests.rs`

- **test_autogpt_plugin_schema_mapping:** AutoGPT schema → ReBAC policy
- **test_autogpt_certified_execution:** Decision approved by AutoGPT loop

#### 4.8 JSON-LD Output Tests (2 tests)
Location: `crates/siss-capsule/src/tests/jsonld_output_tests.rs`

- **test_jsonld_schema_valid:** Output conforms to JSON-LD spec
- **test_jsonld_context_required_fields:** @context contains all required fields

---

## 5. JSON-LD OUTPUT SPECIFICATION

### Schema

```json
{
  "@context": {
    "@vocab": "https://sovereignnexus.ai/capsule/v1/",
    "schema": "http://schema.org/",
    "creator": { "@id": "creator_metadata" },
    "licensing": { "@id": "licensing_metadata" },
    "execution": { "@id": "execution_phases" }
  },
  "type": "Capsule",
  "id": "uuid-of-capsule",
  "timestamp": "ISO8601",
  "decision": "Allow|Deny",
  "tool_name": "string",
  "merkle_proof": "hex-encoded-sha256",
  "confidence_score": 0.95,
  "execution_latency_ms": 45.2,
  
  "creator": {
    "sovereign_id": "uuid",
    "organization": "optional-org-name",
    "certification_chain": ["certification-url-1", "certification-url-2"]
  },
  
  "licensing": {
    "type": "MIT|CC0|Proprietary",
    "expires_at": "ISO8601 or null",
    "usage_restrictions": ["restriction-1"]
  },
  
  "execution_phases": [
    {
      "phase": "policy_verification",
      "decision": "Allow",
      "latency_ms": 5.2,
      "details": {}
    },
    {
      "phase": "tool_authorization",
      "decision": "Allow",
      "latency_ms": 0.8,
      "details": {}
    },
    {
      "phase": "isolation_context",
      "decision": "Allow",
      "latency_ms": 12.5,
      "details": {}
    },
    {
      "phase": "audit_logging",
      "decision": "Allow",
      "latency_ms": 1.7,
      "details": {}
    }
  ],
  
  "audit_trace_id": "uuid",
  "covenant_enforcement": "Strict|Standard|Permissive"
}
```

---

## 6. LATENCY BUDGET

### Target Latencies
- **Policy Verification:** <5ms (ReBAC + AP2 cache)
- **Tool Authorization:** <1ms (hash-only, no DB)
- **Execution Context Creation:** <10ms (state snapshot)
- **Audit Logging:** <2ms (in-memory hot storage)
- **Total Capsule Latency:** <20ms (cold path), <10ms (warm path)
- **LangChain Roundtrip:** <500ms (incl. LLM inference)
- **Ollama Token Latency:** <100ms per token (GPU-accelerated)

### Verification Method
All tests include latency assertions via `assert!(elapsed < threshold)`.

---

## 7. IMPLEMENTATION PLAN

### Week 1 (July 30 - Aug 3)
1. Create siss-capsule crate structure + Cargo.toml
2. Implement core types (CapsuleResult, ExecutionContext, etc.)
3. Implement BaselineCapsuleExecutor with 4-phase execution
4. Write 6 core tests (RED → GREEN)

### Week 2 (Aug 5 - Aug 9)
1. Implement isolation & rollback logic
2. Implement JSON-LD export
3. Write 3 isolation tests + 2 JSON-LD tests
4. Test latency budget (all phases <20ms)

### Week 3 (Aug 12 - Aug 16)
1. Implement LangChain adapter
2. Implement Ollama wrapper
3. Implement AutoGPT shim
4. Write integration tests (6 tests total)

### Week 4 (Aug 19 - Aug 23)
1. Latency optimization (benchmark all phases)
2. Full integration test with real LLM inference
3. Documentation + API examples
4. Prepare for Stream 2 hand-off

### Week 5 (Aug 26 - Aug 30)
1. Code review + bug fixes
2. Final latency verification
3. Release candidate tagged
4. Ready for production deployment

---

## 8. SUCCESS CHECKPOINTS

### Checkpoint 1: Core Infrastructure (EOW Aug 2)
- [ ] siss-capsule crate created, compiles
- [ ] BaselineCapsuleExecutor functional
- [ ] 6 core tests GREEN
- [ ] Cold path latency <20ms verified

### Checkpoint 2: Full Test Suite (EOW Aug 9)
- [ ] All 20+ tests GREEN
- [ ] Isolation & rollback working
- [ ] JSON-LD output valid
- [ ] Warm path latency <10ms verified

### Checkpoint 3: Adapter Integration (EOW Aug 16)
- [ ] LangChain adapter working with real agent
- [ ] Ollama inference <100ms per token
- [ ] AutoGPT shim schema mapping complete
- [ ] All integration tests GREEN

### Checkpoint 4: Production Ready (EOW Aug 23)
- [ ] Latency budget verified end-to-end
- [ ] <500ms LangChain roundtrip confirmed
- [ ] Documentation complete
- [ ] Ready for Stream 2 dependency

### Checkpoint 5: Release (EOW Aug 30)
- [ ] Code review complete
- [ ] All bug fixes applied
- [ ] Final verification passing
- [ ] v1.0 release tagged

---

## 9. CONSTRAINTS & ASSUMPTIONS

### Constraints
- Do not modify existing BaselineCapsule or ToolCallCapsule — only wrap and extend
- Do not introduce breaking changes to AP2 policy engine
- Do not modify LangChain, Ollama, or AutoGPT source — wrapper/adapter only
- Token budget: <5000 tokens for STREAM 1 specification

### Assumptions
- Ollama service available at localhost:11434 (configurable)
- LangChain v0.1.x or higher
- AutoGPT compatible with Python 3.10+
- GPU available (Metal on macOS, CUDA on Linux) — graceful fallback to CPU

### Dependencies (Already Available)
- siss-behavioral-firewall: AP2 + ReBAC
- siss-gatekeeper: BaselineCapsule + ToolCallCapsule
- siss-audit-archiver: AuditArchiver for logging

---

## 10. DECISION LOG

### Why siss-capsule as a new crate?
- Aggregates existing governance components (BaselineCapsule, ToolCallCapsule, AP2)
- Provides unified API for Stream 2+ to depend on
- Isolates harness adapters (LangChain, Ollama, AutoGPT) from core

### Why <500ms total latency for LangChain?
- Matches production latency SLA for agentic systems
- Includes LLM inference time (fastest models: 200-300ms for small requests)
- Capsule overhead must be <100ms to stay within budget

### Why Ollama instead of OpenAI API?
- Local-first: no network latency, no API rate limits
- Offline-capable: critical for conflict zones + sneakernet
- Cost: zero per-token cost vs OpenAI
- Models: Qwen (7B/14B) and Gemma (7B) provide good speed/quality trade-off

### Why 1%/99% covenant split?
- 99%: default fail-closed (conservative) for production
- 1%: experimental path for research + edge cases
- Auditable: every non-default decision is logged

---

## APPENDIX: File Structure

```
crates/siss-capsule/
├── Cargo.toml
├── src/
│   ├── lib.rs                              (public API + module exports)
│   ├── types.rs                            (CapsuleResult, ExecutionContext, etc.)
│   ├── baseline_capsule_executor.rs        (core 4-phase execution)
│   ├── isolation.rs                        (StateSnapshot + rollback)
│   ├── jsonld_export.rs                    (@context + serialization)
│   ├── adapters/
│   │   ├── mod.rs
│   │   ├── langchain.rs                    (LangChain agent wrapper)
│   │   ├── ollama.rs                       (local Ollama inference)
│   │   └── autogpt.rs                      (AutoGPT plugin compatibility)
│   └── tests/
│       ├── baseline_capsule_tests.rs       (6 tests)
│       ├── policy_verification_tests.rs    (5 tests)
│       ├── tool_authorization_tests.rs     (3 tests)
│       ├── isolation_tests.rs              (3 tests)
│       ├── langchain_integration_tests.rs  (2 tests)
│       ├── ollama_tests.rs                 (2 tests)
│       ├── autogpt_tests.rs                (2 tests)
│       └── jsonld_output_tests.rs          (2 tests)
└── benches/
    ├── latency_bench.rs                    (measure all phases)
    └── langchain_roundtrip_bench.rs        (verify <500ms)
```

---

## APPROVAL GATES

Before implementation begins:
1. **Architecture Review:** Confirm module structure, API contracts
2. **Latency Budget Validation:** Confirm <20ms cold path is achievable
3. **Test Plan Acceptance:** All 20+ tests understood and estimated
4. **Stream 2 Dependency Mapping:** VisionAPI SDK knows what to expect

**Status:** Ready for approval. Awaiting user confirmation to proceed with Phase 1 coding.

