# UniFFI Binding Strategy — siss-ios-core

**Status:** LOCKED (May 29, 2026)  
**Effective:** Phase 32 Merge (June 11, 2026)  
**Author:** Architecture Planning (TRACK H)  
**Purpose:** Define Rust→Swift FFI boundary for all callable functions

---

## 1. Overview

UniFFI (Mozilla) is the FFI framework generating Safe Rust→Swift bindings. All Swift code calls Rust functions through auto-generated Swift wrappers. No hand-written C/C++ bridge code.

**Process:**
1. Rust side: Mark functions with `#[uniffi::export]`
2. Build: `cargo build --features uniffi` generates `SovereignCoreLib.swift` module
3. Swift side: `import SovereignCoreLib` and call functions directly
4. Type safety: UniFFI handles type marshalling (Rust→Swift and back)

---

## 2. Exposed Rust Crates (Locked)

Only these crates expose functions to Swift. All others remain internal.

| Crate | Reason | Stability |
|-------|--------|-----------|
| `siss-gatekeeper` | AP2 policy evaluation (core access control) | Stable |
| `siss-agent-shell` | Agent execution + A2UI rendering | Stable |
| `siss-context-cartography` | Context mapping + memory tier queries | Stable |
| `siss-behavioral-firewall` | ReBAC rule enforcement + audit logging | Stable |

---

## 3. Type Mapping (Rust → Swift)

UniFFI automatically maps common types. For complex types, define `.udl` files.

### Primitive Types (Auto-Mapped)

| Rust | Swift |
|------|-------|
| `bool` | `Bool` |
| `i32` | `Int32` |
| `u64` | `UInt64` |
| `String` | `String` |
| `Result<T, E>` | `throws` (Swift error) |

### Custom Types (Require `.udl`)

```rust
// Rust: siss-gatekeeper/src/lib.rs
#[derive(uniffi::Record)]
pub struct Policy {
    pub id: String,
    pub rules: Vec<Rule>,
}

#[derive(uniffi::Record)]
pub struct Context {
    pub operator_id: String,
    pub action: String,
    pub resource: String,
}

#[derive(uniffi::Enum)]
pub enum Decision {
    Allow,
    Deny { reason: String },
    RequireMFA,
}
```

**Swift side (auto-generated):**
```swift
public struct Policy {
    public let id: String
    public let rules: [Rule]
}

public struct Context {
    public let operatorId: String
    public let action: String
    public let resource: String
}

public enum Decision {
    case allow
    case deny(reason: String)
    case requireMFA
}
```

---

## 4. Callable Functions (Locked List)

### From `siss-gatekeeper`

```rust
#[uniffi::export]
pub fn evaluate_policy(
    policy: Policy,
    context: Context,
) -> Result<Decision> {
    // Returns Allow | Deny | RequireMFA
    // Used for: operator actions (exec, deploy, delete)
}

#[uniffi::export]
pub fn create_mandate(
    operator_id: String,
    action: String,
    duration_secs: u64,
) -> Result<Mandate> {
    // Returns signed Mandate (AP2 ledger entry)
    // Used for: time-limited authority delegation
}

#[uniffi::export]
pub fn verify_mandate(
    mandate: Mandate,
    context: Context,
) -> Result<bool> {
    // Returns true if mandate is valid, signed, not expired
    // Used for: audit trail validation
}
```

**Swift Usage:**
```swift
let decision = try evaluatePolicy(policy: myPolicy, context: ctx)
if case .allow = decision {
    let mandate = try createMandate(operatorId: "op-1", action: "deploy", durationSecs: 3600)
    // Use mandate for AP2 signing
}
```

### From `siss-agent-shell`

```rust
#[uniffi::export]
pub fn execute_agent(
    agent_id: String,
    input: String, // JSON-encoded AgentInput
) -> Result<AgentResult> {
    // Returns agent execution result
    // Used for: running agents on device (inference, decision-making)
}

#[uniffi::export]
pub fn render_a2ui(
    component_json: String, // JSON-encoded A2UI component
) -> Result<String> {
    // Returns HTML string (rendered A2UI)
    // Used for: UI rendering in WebView
}
```

**Swift Usage:**
```swift
let agentInput = AgentInput(agentId: "agent-1", prompt: "analyze this...")
let result = try executeAgent(agentId: "agent-1", input: agentInput.toJSON())

let a2uiHtml = try renderA2UI(componentJson: myComponentJSON)
webView.loadHTMLString(a2uiHtml, baseURL: nil)
```

### From `siss-context-cartography`

```rust
#[uniffi::export]
pub fn query_context(
    query: ContextQuery, // Structured query
) -> Result<ContextMap> {
    // Returns context map (operators, agents, decisions, audit trail)
    // Used for: operator awareness, decision replay
}

#[uniffi::export]
pub fn get_memory_tier(
    operator_id: String,
) -> Result<MemoryTier> {
    // Returns which tier (ephemeral, session, persistent)
    // Used for: determining credential lifetime
}
```

**Swift Usage:**
```swift
let query = ContextQuery(operatorId: "op-1", timeWindow: 3600)
let contextMap = try queryContext(query: query)
print("Active agents: \(contextMap.activeAgents)")

let tier = try getMemoryTier(operatorId: "op-1")
// tier.ttl determines how long credentials persist
```

### From `siss-behavioral-firewall`

```rust
#[uniffi::export]
pub fn log_audit_event(
    event: AuditEvent,
) -> Result<()> {
    // Writes event to local audit log
    // Used for: compliance, debugging
}

#[uniffi::export]
pub fn get_audit_log(
    operator_id: String,
    limit: u32,
) -> Result<Vec<AuditEvent>> {
    // Returns last N audit events for operator
    // Used for: operator activity review
}
```

**Swift Usage:**
```swift
let event = AuditEvent(
    operatorId: "op-1",
    action: "deploy",
    timestamp: Date(),
    success: true
)
try logAuditEvent(event: event)

let log = try getAuditLog(operatorId: "op-1", limit: 50)
for event in log {
    print("\(event.action): \(event.success ? "OK" : "FAILED")")
}
```

---

## 5. Error Handling

All functions return `Result<T>` (Rust) → `throws` (Swift).

```rust
#[derive(uniffi::Enum)]
pub enum ApiError {
    PolicyDenied { reason: String },
    InvalidInput { field: String },
    Unauthorized,
    InternalError { message: String },
}

// In Swift, caught as Error:
do {
    let decision = try evaluatePolicy(policy: p, context: c)
} catch let error as ApiError {
    switch error {
    case .policyDenied(let reason):
        print("Access denied: \(reason)")
    case .unauthorized:
        print("Operator not authenticated")
    default:
        print("Error: \(error)")
    }
}
```

---

## 6. Testing Strategy

### Swift Unit Tests

```swift
// siss-ios-core/Tests/SovereignCoreTests/GatekeeperTests.swift

import XCTest
@testable import SovereignCoreLib

class GatekeeperTests: XCTestCase {
    func testEvaluatePolicyReturnsAllow() throws {
        let policy = Policy(id: "p-1", rules: [])
        let context = Context(
            operatorId: "op-1",
            action: "view",
            resource: "data"
        )
        let decision = try evaluatePolicy(policy: policy, context: context)
        XCTAssertEqual(decision, .allow)
    }
    
    func testCreateMandateReturnsSignedMandate() throws {
        let mandate = try createMandate(
            operatorId: "op-1",
            action: "deploy",
            durationSecs: 3600
        )
        XCTAssertFalse(mandate.signature.isEmpty)
    }
    
    func testEvaluatePolicyDeniesUnauthorized() throws {
        let policy = Policy(id: "p-restrict", rules: [
            // Restrictive rules
        ])
        let context = Context(
            operatorId: "op-unknown",
            action: "delete",
            resource: "critical"
        )
        let decision = try evaluatePolicy(policy: policy, context: context)
        if case .deny(let reason) = decision {
            XCTAssertFalse(reason.isEmpty)
        } else {
            XCTFail("Expected .deny, got \(decision)")
        }
    }
}
```

### Integration Tests

- [ ] Test all functions with real siss-gatekeeper compiled
- [ ] Verify type marshalling (Rust↔Swift) for all custom types
- [ ] Test error propagation (Rust→Swift exceptions)
- [ ] Load test: Call functions 1000x in tight loop (measure latency, memory)

---

## 7. Build Configuration

### Cargo.toml (siss-gatekeeper)

```toml
[package]
name = "siss-gatekeeper"
version = "0.1.0"

[lib]
crate-type = ["cdylib"]  # Dynamic library for iOS

[features]
default = []
uniffi = ["uniffi/bindgen-rust"]

[dependencies]
uniffi = { version = "0.28", features = ["bindgen-rust"] }
```

### Build Script

```bash
# Week 5-6 (June 11-25)
cd crates/siss-gatekeeper
cargo build --features uniffi --release --target aarch64-apple-ios

# Generates:
# - crates/siss-gatekeeper/target/aarch64-apple-ios/release/libsiss_gatekeeper.a (static lib)
# - SovereignCoreLib.swift (auto-generated FFI module)
```

### Xcode Integration

1. Add static library to Xcode build phases
2. Import generated module: `import SovereignCoreLib`
3. Swift Package Manager (optional): Wrap in SPM package for distribution

---

## 8. Migration Plan (If Rust Crates Change)

**Problem:** If Rust API changes after June 11, Swift code breaks.

**Solution:**
- Rust crate versions are pinned in `Cargo.lock` (frozen at Phase 32 merge)
- If bugs found post-June 11: Create patch releases only (0.1.0 → 0.1.1)
- Major changes (0.2.0) → Requires Swift re-integration (async task)

**Versioning Rule:**
- `major.minor.patch`: iOS dev tracks `major.minor` (e.g., gatekeeper 0.1.*)
- Patch updates (0.1.0 → 0.1.1) = re-compile library, auto-update FFI bindings
- Minor+ updates = Require iOS feature branch

---

## 9. Deployment Checklist

- [ ] All 4 crates have `#[uniffi::export]` on public API functions
- [ ] `.udl` files define custom types (Policy, Context, Decision, etc.)
- [ ] Compile-time verification: `cargo build --features uniffi` passes
- [ ] All functions return `Result<T>` (no panics)
- [ ] Swift unit tests pass (all 4 test suites)
- [ ] Xcode project links against generated module
- [ ] Package.swift (SPM) published to private repo or local filesystem

---

## 10. Locked Decision Log

| Decision | Rationale | Lock Date |
|----------|-----------|-----------|
| UniFFI (not hand-written FFI) | Auto-generated = fewer bugs, easier maintenance | May 29 |
| Expose 4 crates only | Minimal API surface = easier testing + support | May 29 |
| All functions return Result<T> | Consistent error handling in Swift | May 29 |
| Compile-time type safety | UniFFI marshalling prevents runtime type errors | May 29 |

---

## References

- [UniFFI Guide](https://mozilla.github.io/uniffi-rs/)
- [Swift FFI Best Practices](https://developer.apple.com/documentation/swift/c-interoperability)
- Phase 32 Completion: siss-gatekeeper, siss-agent-shell, siss-context-cartography, siss-behavioral-firewall
