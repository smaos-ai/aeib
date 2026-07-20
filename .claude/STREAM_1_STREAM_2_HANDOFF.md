# Stream 1 → Stream 2 Integration Handoff
## What Stream 1 Delivers. What Stream 2 Consumes.

**Document Status:** Integration specification (July 18, 2026)  
**Audience:** Both Stream 1 and Stream 2 implementation teams  
**Purpose:** Clear API contracts and integration points

---

## STREAM 1 DELIVERABLES (Aug 1-30)

### What Stream 1 Produces

#### 1. siss-capsule Crate v1.0
**Location:** `crates/siss-capsule/`

**Public Types (must export):**
```rust
pub struct BaselineCapsuleExecutor {
    // Opaque internal state
}

pub struct CapsuleResult {
    pub id: Uuid,
    pub creator_id: Uuid,
    pub execution_latency_ms: f64,
    pub decision: PolicyDecision,
    pub execution_phases: Vec<ExecutionPhase>,
    pub isolation_level: IsolationLevel,
    pub merkle_proof: String,
    pub json_ld: serde_json::Value,
}

pub struct ExecutionContext {
    pub user_id: Uuid,
    pub tool_name: String,
    pub params: serde_json::Value,
    pub attributes: SovereignAttributes,
    pub isolation_level: IsolationLevel,
}

pub enum PolicyDecision {
    Allow,
    Deny(String),
}

pub enum IsolationLevel {
    Strict,     // 99% conservative
    Standard,   // Default
    Permissive, // 1% experimental
}

pub struct ExecutionPhase {
    pub phase: Phase,
    pub status: PhaseStatus,
    pub latency_ms: f64,
}

pub enum Phase {
    PolicyVerification,
    ToolAuthorization,
    IsolationContext,
    AuditLogging,
}

pub enum PhaseStatus {
    Success,
    Failed(String),
    Timeout,
}
```

**Public API (must implement):**
```rust
impl BaselineCapsuleExecutor {
    pub fn new(config: CapsuleConfig) -> Self;
    
    pub async fn execute_request(
        &self,
        user_id: Uuid,
        tool_name: &str,
        params: serde_json::Value,
        attrs: &SovereignAttributes,
    ) -> Result<CapsuleResult, CapsuleError>;
    
    pub async fn record_baseline(
        &self,
        domain: &str,
        baseline: f64,
        confidence: f64,
    ) -> Result<(), CapsuleError>;
    
    pub async fn verify_baseline(
        &self,
        domain: &str,
        baseline: f64,
    ) -> Result<bool, CapsuleError>;
    
    pub async fn export_json_ld(
        &self,
        capsule_result: &CapsuleResult,
    ) -> Result<serde_json::Value, CapsuleError>;
}
```

**Cargo.toml Entry:**
```toml
[package]
name = "siss-capsule"
version = "0.1.0"
edition = "2024"

[dependencies]
uuid = { version = "1", features = ["v4", "serde"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
tokio = { version = "1", features = ["full"] }
ed25519-dalek = { version = "2", features = ["serde"] }
siss-behavioral-firewall = { path = "../siss-behavioral-firewall" }
siss-gatekeeper = { path = "../siss-gatekeeper" }
siss-audit-archiver = { path = "../siss-audit-archiver" }
```

#### 2. 20+ Passing Tests
**Location:** `crates/siss-capsule/src/tests/`

**Test Categories:**
1. **Baseline Tests (6):**
   - `test_record_personal_truth` ✓
   - `test_fail_closed_low_confidence` ✓
   - `test_verify_truth_with_source` ✓
   - `test_merkle_root_deterministic` ✓
   - `test_export_json_valid` ✓
   - `test_baseline_retrieval` ✓

2. **Isolation Tests (3):**
   - `test_state_snapshot_commit` ✓
   - `test_state_snapshot_rollback` ✓
   - `test_isolation_level_enforcement` ✓

3. **JSON-LD Tests (2):**
   - `test_jsonld_schema_valid` ✓
   - `test_jsonld_context_required_fields` ✓

4. **Policy Tests (5):**
   - `test_policy_allow_high_trust` ✓
   - `test_policy_deny_low_reputation` ✓
   - `test_policy_deny_blacklisted` ✓
   - `test_policy_and_predicate` ✓
   - `test_policy_fail_closed_default` ✓

5. **Tool Authorization Tests (3):**
   - `test_tool_authorization_success` ✓
   - `test_tool_authorization_fail_closed` ✓
   - `test_concurrent_authorizations` ✓

6. **Integration Tests (2+):**
   - `test_langchain_tool_use_interception` ✓
   - `test_ollama_inference_streaming` ✓

#### 3. JSON-LD Output Format
**Location:** `crates/siss-capsule/src/jsonld_export.rs`

**Format (W3C JSON-LD):**
```json
{
  "@context": "https://axiom.local/ctx/capsule/v1",
  "id": "capsule-decision-2026-08-01-001",
  "type": "CapsuleResult",
  "creator_id": "creator-xyz",
  "execution_timestamp": "2026-08-01T10:30:00Z",
  "decision": "Allow",
  "execution_latency_ms": 18.5,
  "execution_phases": [
    {
      "phase": "PolicyVerification",
      "status": "Success",
      "latency_ms": 4.2
    },
    {
      "phase": "ToolAuthorization",
      "status": "Success",
      "latency_ms": 0.8
    },
    {
      "phase": "IsolationContext",
      "status": "Success",
      "latency_ms": 9.1
    },
    {
      "phase": "AuditLogging",
      "status": "Success",
      "latency_ms": 1.9
    }
  ],
  "merkle_proof": "0xa1b2c3d4e5f6...",
  "verifiable": true
}
```

#### 4. Latency Guarantees
**Measured & Verified (cargo bench):**
- Cold path (all phases): <20ms
- Warm path (with caching): <10ms
- Policy verification: <5ms
- Tool authorization: <1ms
- Isolation context: <10ms
- Audit logging: <2ms

#### 5. Documentation
**Location:** `crates/siss-capsule/`
- README.md — overview, quick start
- docs/INTEGRATION_GUIDE.md — API reference, usage examples
- docs/JSON_LD_SPEC.md — output format spec
- docs/LATENCY_PROFILE.md — benchmark results

---

## STREAM 2 CONSUMPTION (Aug 15 - Oct 31)

### What Stream 2 Imports from Stream 1

**In Cargo.toml (siss-vision-sdk-core):**
```toml
[dependencies]
siss-capsule = { path = "../siss-capsule", version = "0.1.0" }
```

**In Rust code:**
```rust
use siss_capsule::{
    BaselineCapsuleExecutor,
    CapsuleResult,
    ExecutionContext,
    PolicyDecision,
    IsolationLevel,
};
```

### How Stream 2 Uses Stream 1

#### 1. Core Execution Path
```rust
// In siss-vision-sdk-core/src/client.rs

pub struct VisionAPIClient {
    capsule_executor: Arc<BaselineCapsuleExecutor>,  // From Stream 1
    policy_engine: Arc<PolicySet>,                   // From siss-gatekeeper
    creator_registry: Arc<CreatorRegistry>,          // Stream 2 specific
    revenue_router: Arc<RevenueRouter>,              // Stream 2 specific
}

impl VisionAPIClient {
    pub async fn evaluate_decision(
        &self,
        creator_id: Uuid,
        platform: &str,
        action: &str,
        context: &DecisionContext,
    ) -> Result<DecisionGate, VisionError> {
        // 1. Check creator policy (PolicySet from siss-gatekeeper)
        // 2. Compute blast_radius (MongeGapGovernor)
        // 3. Return DecisionGate (low risk → auto-approve)
    }

    pub async fn execute_with_governance(
        &self,
        creator_id: Uuid,
        platform: &str,
        action: &str,
        params: serde_json::Value,
    ) -> Result<CapsuleResult, VisionError> {
        // Step 1: Check policy first
        let decision = self.evaluate_decision(
            creator_id,
            platform,
            action,
            &context,
        ).await?;

        if let DecisionGate::Denied { reason } = decision {
            return Err(VisionError::PolicyDenied(reason));
        }

        // Step 2: Execute through Stream 1 capsule
        let capsule_result = self.capsule_executor.execute_request(
            creator_id,
            action,                    // tool name
            params,                    // params
            &sovereign_attrs,          // attributes
        ).await?;

        // Step 3: Detect value + settle revenue (Stream 2 specific)
        if capsule_result.decision == PolicyDecision::Allow {
            let platform_adapter = self.get_adapter(platform)?;
            let action_result = platform_adapter.execute_action(
                &platform_auth,
                action,
                params.clone(),
                self,  // pass self for governance calls
            ).await?;

            let value = platform_adapter.extract_value_signal(&action_result).await?;
            
            self.revenue_router.settle(
                creator_id,
                capsule_result.id,
                value,
            ).await?;
        }

        Ok(capsule_result)  // Returns Stream 1 CapsuleResult
    }
}
```

#### 2. Audit Trail Integration
```rust
// Stream 2 exports audit trails in Stream 1's JSON-LD format

pub async fn export_audit_trail(
    &self,
    creator_id: Uuid,
    time_range: TimeRange,
) -> Result<Vec<AuditEntry>, VisionError> {
    let audit_entries = self.audit_log.query(creator_id, time_range).await?;
    
    let mut result = Vec::new();
    for entry in audit_entries {
        // Extract JSON-LD from Stream 1 CapsuleResult
        let json_ld = entry.capsule_result.json_ld.clone();
        
        // Augment with Stream 2 data (revenue, platform)
        let mut enhanced_ld = json_ld;
        enhanced_ld["platform"] = json!(entry.platform);
        enhanced_ld["revenue_split"] = json!({
            "platform_fee": entry.revenue_split.platform_fee,
            "creator_payout": entry.revenue_split.creator_payout,
        });
        
        result.push(AuditEntry {
            id: entry.id,
            creator_id,
            platform: entry.platform.clone(),
            action: entry.action.clone(),
            timestamp: entry.timestamp,
            approved: entry.capsule_result.decision == PolicyDecision::Allow,
            execution_latency_ms: entry.capsule_result.execution_latency_ms,
            merkle_proof: entry.capsule_result.merkle_proof.clone(),
            json_ld: enhanced_ld,
        });
    }
    
    Ok(result)
}
```

#### 3. Latency Budget (Stream 2 ⊆ <100ms total)
```
Creator Decision
    ├─ VisionAPI.evaluate_decision(): <50ms (policy check + decision gate)
    └─ BaselineCapsuleExecutor.execute_request(): <20ms (from Stream 1)
    └─ Platform API call: 200-5000ms (network-dependent)
    └─ Revenue settlement: <10ms (async, non-blocking)
        ↓
    Total Stream 2 orchestration: <100ms (excluding platform API)
    Total end-to-end (decision + execution): <50ms SDK + platform time
```

---

## INTEGRATION CHECKLIST

### Pre-Kickoff (Aug 1-14)

**Stream 1 Team:**
- [x] Create siss-capsule crate
- [x] Implement BaselineCapsuleExecutor (stub first)
- [x] Write 20+ tests (RED phase)
- [x] Implement to make tests pass (GREEN phase)
- [x] Benchmark latency (<20ms cold path)
- [x] Export as v0.1.0 in workspace Cargo.toml

**Stream 2 Team (prep only):**
- [x] Read STREAM_1_IMPLEMENTATION_PLAN.md
- [x] Read VISION_API_INTEGRATION_SPEC.md
- [x] Understand BaselineCapsuleExecutor API
- [x] Understand JSON-LD output format

### Week 1 (Aug 15-21) — Stream 2 Kickoff

**Stream 2 Kickoff Activities:**
- [ ] Verify siss-capsule compiles + all tests GREEN
- [ ] Verify workspace Cargo.toml includes siss-capsule
- [ ] Create siss-vision-sdk-core package
- [ ] Import siss-capsule as dependency
- [ ] Implement VisionAPIClient stub
- [ ] Write core tests (RED phase)

**Verification Command:**
```bash
cd /Users/andriileukhin/Documents/SovereignNexus

# Verify Stream 1 complete
cargo test --package siss-capsule --lib
# Expected: 20+ tests GREEN

# Verify Stream 2 can import Stream 1
cargo new --lib crates/siss-vision-sdk-core
cd crates/siss-vision-sdk-core
# Add to workspace Cargo.toml
# Import siss-capsule
cargo check
# Expected: compiles without errors
```

### Week 3 (Aug 29 - Sep 4) — Adapter Integration Starts

**Stream 2 Adapter Development:**
- [ ] Implement first 5 adapters (Substack, Patreon, Notion, Zapier, YouTube)
- [ ] Each adapter uses VisionAPIClient.execute_with_governance()
- [ ] Each adapter receives CapsuleResult from Stream 1
- [ ] Each adapter converts to platform-specific format

**Example (Substack Adapter):**
```rust
pub struct SubstackAdapter { }

#[async_trait]
impl PlatformAdapter for SubstackAdapter {
    async fn execute_action(
        &self,
        platform_auth: &PlatformAuth,
        action: &str,
        params: serde_json::Value,
        vision_api: &VisionAPIClient,  // Stream 2 VisionAPIClient
    ) -> Result<ActionResult, AdapterError> {
        // 1. Call VisionAPI to evaluate decision
        let decision = vision_api.evaluate_decision(
            platform_auth.user_id,
            "substack",
            action,
            &context,
        ).await?;

        // 2. If approved, execute through Stream 1
        let capsule_result = vision_api.execute_with_governance(
            platform_auth.user_id,
            "substack",
            action,
            params.clone(),
        ).await?;

        // 3. Call Substack API
        let response = self.call_substack_api(&platform_auth, action, &params).await?;

        // 4. Return result with capsule_result embedded
        Ok(ActionResult {
            action: action.to_string(),
            status: ActionStatus::Success,
            response,
            latency_ms: capsule_result.execution_latency_ms + api_latency,
        })
    }
}
```

### Week 6-8 (Sep 19 - Oct 9) — Analytics Integration

**Stream 2 Analytics Integration:**
- [ ] Implement DecisionAuditLog (reads CapsuleResult.json_ld)
- [ ] Augment with Stream 2 data (platform, revenue)
- [ ] Export audit trail as JSON-LD (compatible with Stream 1 format)
- [ ] Dashboard queries audit trail for display

**Example (Dashboard Query):**
```rust
pub async fn get_audit_trail(
    &self,
    creator_id: Uuid,
) -> Result<Vec<serde_json::Value>, DashboardError> {
    let audit_entries = self.audit_log.query(creator_id, TimeRange::Last30Days).await?;
    
    let mut json_ld_results = Vec::new();
    for entry in audit_entries {
        // entry.capsule_result comes from Stream 1
        let mut ld = entry.capsule_result.json_ld.clone();
        
        // Add Stream 2 fields
        ld["platform"] = json!(entry.platform);
        ld["creator_revenue"] = json!(entry.revenue_split.creator_payout);
        ld["verified_by_merkle"] = json!(
            verify_merkle_proof(&ld["merkle_proof"].as_str().unwrap())
        );
        
        json_ld_results.push(ld);
    }
    
    Ok(json_ld_results)
}
```

### Final Verification (Week 11-12, Oct 24 - Nov 6)

**Both Teams Verify Integration:**
- [ ] Stream 1 tests still passing (regression)
- [ ] Stream 2 imports Stream 1 without errors
- [ ] Full execution chain works (decision → capsule → platform → revenue)
- [ ] Audit trail complete (JSON-LD, Merkle-verified)
- [ ] Latency budget met (decision <100ms, execution <20ms)
- [ ] No breaking changes to Stream 1 API

**Final Test Command:**
```bash
# Verify full integration
cargo test --workspace

# Expected:
# - All Stream 1 tests passing
# - All Stream 2 tests passing (150+)
# - Zero integration issues

# Verify latency
cargo bench --workspace

# Expected:
# - Stream 1 cold path: <20ms
# - Stream 2 decision eval: <100ms
# - Full chain: meets budget
```

---

## DEPENDENCY COMPATIBILITY MATRIX

| Component | Stream 1 Requirement | Stream 2 Usage | Compatibility |
|-----------|---------------------|----------------|---------------|
| BaselineCapsuleExecutor | v0.1.0 | Injected via Arc | ✓ |
| CapsuleResult | Returns structured output | Reads fields + embeds in JSON-LD | ✓ |
| JSON-LD format | W3C standard, @context | Augments with Stream 2 fields | ✓ |
| PolicySet | From siss-gatekeeper | Reuses for creator policies | ✓ |
| AuditArchiver | From siss-audit-archiver | Calls record() for each decision | ✓ |
| PolicyDecision | Allow/Deny/Timeout | Maps to DecisionGate | ✓ |
| Merkle proof | String output | Includes in audit trail | ✓ |

---

## BREAKING CHANGE POLICY

### During Stream 1 Implementation (Aug 1-30)
- **Before Aug 15:** Stream 1 can refactor freely (no Stream 2 dependencies yet)
- **Aug 15 onwards:** Stream 1 API frozen (Stream 2 depends on it)

### During Stream 2 Implementation (Aug 15 - Oct 31)
- **Stream 1:** Bug fixes only, no API changes
- **Stream 2:** Can iterate freely (only imports Stream 1, doesn't modify it)

### Post-Release (Nov onwards)
- **Stream 1 Changes:** Require major version bump (0.1.0 → 0.2.0)
- **Stream 2 Compatibility:** Major version bump if Stream 1 API changes

---

## TROUBLESHOOTING COMMON ISSUES

### Issue: Stream 2 can't find siss-capsule
**Symptom:** `error: failed to resolve: use of undeclared crate 'siss_capsule'`

**Diagnosis:**
1. Verify workspace Cargo.toml includes `"crates/siss-capsule"`
2. Verify Stream 2 Cargo.toml has `siss-capsule = { path = "../siss-capsule" }`
3. Run `cargo clean` + `cargo build`

### Issue: BaselineCapsuleExecutor API changed
**Symptom:** Stream 2 compile fails with method not found errors

**Diagnosis:**
1. Check if Stream 1 released a new version (git log crates/siss-capsule)
2. Verify compatibility matrix above
3. File issue if breaking change (should not happen)

### Issue: Latency exceeds budget
**Symptom:** Benchmarks show >20ms for Stream 1 cold path

**Diagnosis:**
1. Run `cargo bench --package siss-capsule` for Stream 1 only
2. Run `cargo bench --package siss-vision-sdk-core` for Stream 2 only
3. Identify bottleneck (policy check? audit logging?)
4. Profile with `perf` or `flamegraph`

### Issue: JSON-LD audit trail format mismatch
**Symptom:** Dashboard can't parse audit trail entries

**Diagnosis:**
1. Verify Stream 1 output matches JSON_LD_SPEC.md
2. Verify Stream 2 augmentation preserves @context
3. Validate output against JSON-LD validator (https://www.w3.org/2018/jsonld-cg/WGs/json-ld/)
4. Check Merkle proof field is correctly nested

---

## HANDOFF ARTIFACTS

### Files Stream 1 Must Deliver (by Aug 30)

```
crates/siss-capsule/
├── Cargo.toml (v0.1.0)
├── src/
│   ├── lib.rs (public API)
│   ├── types.rs (CapsuleResult, ExecutionContext, etc.)
│   ├── executor.rs (BaselineCapsuleExecutor)
│   ├── isolation.rs (StateSnapshot, rollback logic)
│   ├── jsonld_export.rs (serialize_to_jsonld function)
│   └── tests/
│       ├── baseline_capsule_tests.rs (6 tests)
│       ├── isolation_tests.rs (3 tests)
│       ├── jsonld_output_tests.rs (2 tests)
│       ├── policy_verification_tests.rs (5 tests)
│       ├── tool_authorization_tests.rs (3 tests)
│       └── full_integration_test.rs (2+ tests)
├── benches/
│   ├── latency_bench.rs (measure <20ms cold path)
│   └── langchain_roundtrip_bench.rs (measure <500ms LLM roundtrip)
├── docs/
│   ├── INTEGRATION_GUIDE.md
│   ├── JSON_LD_SPEC.md
│   └── LATENCY_PROFILE.md
└── README.md

Workspace Cargo.toml:
├── [workspace.members] includes "crates/siss-capsule"
└── [workspace.dependencies] exports all public types
```

### Files Stream 2 Must Deliver (by Oct 31)

```
crates/siss-vision-sdk/
├── crates/siss-vision-sdk-core/ (VisionAPIClient, CreatorRegistry, DecisionGate)
├── crates/siss-vision-sdk-adapters/ (50 platform adapters)
├── crates/siss-vision-sdk-auth/ (OAuth2, TokenManager)
├── crates/siss-vision-sdk-policy/ (PolicyDSL, PolicyCompiler)
├── crates/siss-vision-sdk-analytics/ (DecisionAuditLog, Dashboard)
└── crates/siss-vision-sdk-tests/ (150+ integration tests)

Workspace Cargo.toml:
├── [workspace.members] includes all 6 siss-vision-sdk packages
└── [dependencies.siss-capsule] version = "0.1.0"
```

---

## APPROVAL & SIGN-OFF

### Stream 1 Completion (Aug 30)
**Approval Required:**
- [ ] All 20+ tests GREEN
- [ ] Cold path latency <20ms verified
- [ ] JSON-LD output valid
- [ ] Documentation complete

**Sign-Off:**
- Stream 1 Lead: _________________  Date: _______
- Stream 2 Lead (review): _________________  Date: _______

### Stream 2 Completion (Oct 31)
**Approval Required:**
- [ ] All 150+ tests GREEN
- [ ] Decision evaluation <100ms
- [ ] All 50 adapters working
- [ ] Audit trail verified
- [ ] Stream 1 integration confirmed

**Sign-Off:**
- Stream 2 Lead: _________________  Date: _______
- Stream 1 Lead (verification): _________________  Date: _______

---

**Document Status:** Ready for both teams (Aug 1 kickoff).

