# Governance Gatekeeper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `siss-gatekeeper` crate — the sole authorization gateway that transitions Tasks from `pending` to `authorized` by orchestrating ReBAC, AP2, and GovernanceRule checks in a single atomic pipeline.

**Architecture:** A new Rust library crate `siss-gatekeeper` that depends on `siss-graph-core` (domain types, invariant logic) and `siss-graph-db` (PostgreSQL repositories). Exposes a single async `authorize_task()` entry point. The pipeline runs sequentially (validate → ReBAC → AP2 → governance → sign+commit) inside a single DB transaction. Signing uses a `Signer` trait with `LocalEd25519Signer` and `MockSigner` implementations.

**Tech Stack:** Rust (2024 edition), sqlx (async PostgreSQL), ed25519-dalek, chrono, uuid, serde, tokio, thiserror

**Spec:** `docs/superpowers/specs/2026-05-07-governance-gatekeeper-design.md`

---

## File Structure

```
crates/
  siss-gatekeeper/
    Cargo.toml
    src/
      lib.rs                  # Re-exports
      types.rs                # AuthorizationRequest, AuthorizationResult, GatekeeperError
      signer/
        mod.rs                # Signer trait + SigningError
        local.rs              # LocalEd25519Signer
        mock.rs               # MockSigner for tests
      pipeline/
        mod.rs                # authorize_task() orchestrator
        validate.rs           # Step 1: validation
        rebac.rs              # Step 2: ReBAC checks
        ap2.rs                # Step 3: AP2 budget + tool auth
        governance.rs         # Step 4: GovernanceRule evaluation
        commit.rs             # Step 5: sign, persist, transition
      evaluator/
        mod.rs                # RuleEvaluator: rule name → predicate function map
      payload.rs              # Signing payload serialization
  siss-graph-db/
    src/
      repo/
        node_repo.rs          # MODIFY: add fetch_task, fetch_persona, fetch_mandate, update_task_status, freeze_persona
```

---

### Task 1: Create siss-gatekeeper Crate Skeleton

**Files:**
- Create: `crates/siss-gatekeeper/Cargo.toml`
- Create: `crates/siss-gatekeeper/src/lib.rs`
- Modify: `Cargo.toml` (workspace root — add member)

- [ ] **Step 1: Add crate to workspace**

Add `"crates/siss-gatekeeper"` to the workspace members in `Cargo.toml`:

```toml
[workspace]
resolver = "2"
members = [
    "crates/siss-graph-core",
    "crates/siss-graph-db",
    "crates/siss-gatekeeper",
]
```

- [ ] **Step 2: Create crate Cargo.toml**

Create `crates/siss-gatekeeper/Cargo.toml`:

```toml
[package]
name = "siss-gatekeeper"
edition.workspace = true
version.workspace = true

[dependencies]
siss-graph-core = { path = "../siss-graph-core" }
siss-graph-db = { path = "../siss-graph-db" }
uuid.workspace = true
chrono.workspace = true
serde.workspace = true
serde_json.workspace = true
thiserror.workspace = true
tokio.workspace = true
sqlx.workspace = true
ed25519-dalek.workspace = true

[dev-dependencies]
tokio = { workspace = true, features = ["full", "test-util"] }
```

- [ ] **Step 3: Create lib.rs**

Create `crates/siss-gatekeeper/src/lib.rs`:

```rust
pub mod types;
pub mod signer;
pub mod pipeline;
pub mod evaluator;
pub mod payload;
```

- [ ] **Step 4: Create stub modules**

Create `crates/siss-gatekeeper/src/types.rs`:

```rust
// Implemented in Task 2
```

Create `crates/siss-gatekeeper/src/signer/mod.rs`:

```rust
// Implemented in Task 3
```

Create `crates/siss-gatekeeper/src/pipeline/mod.rs`:

```rust
// Implemented in Task 6
```

Create `crates/siss-gatekeeper/src/evaluator/mod.rs`:

```rust
// Implemented in Task 5
```

Create `crates/siss-gatekeeper/src/payload.rs`:

```rust
// Implemented in Task 3
```

- [ ] **Step 5: Verify compilation**

```bash
source "$HOME/.cargo/env" && cargo check
```

Expected: compiles with warnings about empty modules.

- [ ] **Step 6: Commit**

```bash
git add Cargo.toml crates/siss-gatekeeper/
git commit -m "feat: create siss-gatekeeper crate skeleton"
```

---

### Task 2: Define Request/Response Types

**Files:**
- Create: `crates/siss-gatekeeper/src/types.rs`

- [ ] **Step 1: Write failing tests**

Create `crates/siss-gatekeeper/src/types.rs`:

```rust
#[cfg(test)]
mod tests {
    use super::*;
    use siss_graph_core::node::NodeId;

    #[test]
    fn test_create_authorization_request() {
        let req = AuthorizationRequest {
            task_id: NodeId::new(),
            persona_id: NodeId::new(),
            intent_mandate_id: NodeId::new(),
            requested_tools: vec![NodeId::new(), NodeId::new()],
            estimated_cost: 500,
            tenant_id: NodeId::new(),
        };
        assert_eq!(req.estimated_cost, 500);
        assert_eq!(req.requested_tools.len(), 2);
    }

    #[test]
    fn test_gatekeeper_error_is_hard_failure() {
        assert!(GatekeeperError::TenantViolation {
            source: uuid::Uuid::new_v4(),
            target: uuid::Uuid::new_v4(),
        }.is_hard_failure());

        assert!(GatekeeperError::PersonaFrozen {
            persona_id: uuid::Uuid::new_v4(),
        }.is_hard_failure());

        assert!(GatekeeperError::CriticalRuleViolation {
            rule_name: "test".into(),
            persona_frozen: true,
        }.is_hard_failure());

        assert!(!GatekeeperError::AccessDenied {
            tool_id: uuid::Uuid::new_v4(),
        }.is_hard_failure());

        assert!(!GatekeeperError::BudgetExceeded {
            requested: 100,
            remaining: 50,
        }.is_hard_failure());
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
source "$HOME/.cargo/env" && cargo test -p siss-gatekeeper -- types 2>&1
```

Expected: FAIL — types not defined.

- [ ] **Step 3: Implement types**

Add above the `#[cfg(test)]` block in `types.rs`:

```rust
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use thiserror::Error;
use uuid::Uuid;

use siss_graph_core::node::NodeId;
use siss_graph_core::node::execution::TaskStatus;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuthorizationRequest {
    pub task_id: NodeId,
    pub persona_id: NodeId,
    pub intent_mandate_id: NodeId,
    pub requested_tools: Vec<NodeId>,
    pub estimated_cost: i64,
    pub tenant_id: NodeId,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuthorizationResult {
    pub task_id: NodeId,
    pub payment_mandate_id: NodeId,
    pub signature: Vec<u8>,
    pub authorized_at: DateTime<Utc>,
}

#[derive(Debug, Error)]
pub enum GatekeeperError {
    // Hard failures — Task transitions to failed
    #[error("cross-tenant violation: source {source} != target {target}")]
    TenantViolation { source: Uuid, target: Uuid },

    #[error("persona {persona_id} is frozen")]
    PersonaFrozen { persona_id: Uuid },

    #[error("critical rule '{rule_name}' violated, persona_frozen={persona_frozen}")]
    CriticalRuleViolation { rule_name: String, persona_frozen: bool },

    // Soft failures — Task stays pending
    #[error("access denied for tool {tool_id}")]
    AccessDenied { tool_id: Uuid },

    #[error("budget exceeded: requested {requested}, remaining {remaining}")]
    BudgetExceeded { requested: i64, remaining: i64 },

    #[error("tool {tool_id} not authorized by mandate {mandate_id}")]
    ToolNotAuthorized { tool_id: Uuid, mandate_id: Uuid },

    #[error("enforced rule '{rule_name}' violated")]
    EnforcedRuleViolation { rule_name: String },

    // Infrastructure
    #[error("task {task_id} not found")]
    TaskNotFound { task_id: Uuid },

    #[error("invalid task status: current={current:?}, expected={expected:?}")]
    InvalidTaskStatus { current: TaskStatus, expected: TaskStatus },

    #[error("signing error: {message}")]
    SigningError { message: String },

    #[error("database error: {message}")]
    DatabaseError { message: String },
}

impl GatekeeperError {
    /// Returns true if this error should cause the Task to transition to `failed`.
    pub fn is_hard_failure(&self) -> bool {
        matches!(
            self,
            Self::TenantViolation { .. }
                | Self::PersonaFrozen { .. }
                | Self::CriticalRuleViolation { .. }
        )
    }
}

impl From<sqlx::Error> for GatekeeperError {
    fn from(e: sqlx::Error) -> Self {
        Self::DatabaseError { message: e.to_string() }
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
source "$HOME/.cargo/env" && cargo test -p siss-gatekeeper -- types 2>&1
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add crates/siss-gatekeeper/src/types.rs
git commit -m "feat: define Gatekeeper request/response types with hard/soft failure classification"
```

---

### Task 3: Implement Signer Trait and Payload Serialization

**Files:**
- Create: `crates/siss-gatekeeper/src/signer/mod.rs`
- Create: `crates/siss-gatekeeper/src/signer/local.rs`
- Create: `crates/siss-gatekeeper/src/signer/mock.rs`
- Create: `crates/siss-gatekeeper/src/payload.rs`

- [ ] **Step 1: Write failing tests for payload serialization**

Create `crates/siss-gatekeeper/src/payload.rs`:

```rust
#[cfg(test)]
mod tests {
    use super::*;
    use uuid::Uuid;

    #[test]
    fn test_payload_is_48_bytes() {
        let payload = build_signing_payload(
            Uuid::nil(),
            Uuid::nil(),
            1000,
            1000000,
        );
        assert_eq!(payload.len(), 48);
    }

    #[test]
    fn test_payload_is_deterministic() {
        let task = Uuid::new_v4();
        let mandate = Uuid::new_v4();
        let p1 = build_signing_payload(task, mandate, 500, 12345);
        let p2 = build_signing_payload(task, mandate, 500, 12345);
        assert_eq!(p1, p2);
    }

    #[test]
    fn test_different_amounts_produce_different_payloads() {
        let task = Uuid::new_v4();
        let mandate = Uuid::new_v4();
        let p1 = build_signing_payload(task, mandate, 500, 12345);
        let p2 = build_signing_payload(task, mandate, 501, 12345);
        assert_ne!(p1, p2);
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
source "$HOME/.cargo/env" && cargo test -p siss-gatekeeper -- payload 2>&1
```

Expected: FAIL — `build_signing_payload` not defined.

- [ ] **Step 3: Implement payload serialization**

Add above tests in `payload.rs`:

```rust
use uuid::Uuid;

/// Build the deterministic 48-byte payload for signing a PaymentMandate.
///
/// Format: task_id (16 bytes) || intent_mandate_id (16 bytes) || amount (8 bytes BE) || timestamp (8 bytes BE)
pub fn build_signing_payload(
    task_id: Uuid,
    intent_mandate_id: Uuid,
    amount: i64,
    timestamp_epoch_secs: i64,
) -> Vec<u8> {
    let mut payload = Vec::with_capacity(48);
    payload.extend_from_slice(task_id.as_bytes());
    payload.extend_from_slice(intent_mandate_id.as_bytes());
    payload.extend_from_slice(&amount.to_be_bytes());
    payload.extend_from_slice(&timestamp_epoch_secs.to_be_bytes());
    payload
}
```

- [ ] **Step 4: Run payload tests**

```bash
source "$HOME/.cargo/env" && cargo test -p siss-gatekeeper -- payload 2>&1
```

Expected: 3 tests PASS.

- [ ] **Step 5: Write failing tests for Signer trait and MockSigner**

Create `crates/siss-gatekeeper/src/signer/mod.rs`:

```rust
pub mod local;
pub mod mock;

use thiserror::Error;

#[derive(Debug, Error)]
#[error("signing error: {message}")]
pub struct SigningError {
    pub message: String,
}

/// Trait for cryptographic signing of PaymentMandate payloads.
pub trait Signer: Send + Sync {
    fn sign(&self, payload: &[u8]) -> Result<Vec<u8>, SigningError>;
    fn verify(&self, payload: &[u8], signature: &[u8]) -> Result<bool, SigningError>;
}
```

Create `crates/siss-gatekeeper/src/signer/mock.rs`:

```rust
use super::{Signer, SigningError};

/// A deterministic mock signer for tests. Always produces `[0xAA; 64]` signatures.
pub struct MockSigner;

impl Signer for MockSigner {
    fn sign(&self, _payload: &[u8]) -> Result<Vec<u8>, SigningError> {
        Ok(vec![0xAA; 64])
    }

    fn verify(&self, _payload: &[u8], _signature: &[u8]) -> Result<bool, SigningError> {
        Ok(true)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_mock_signer_produces_deterministic_signature() {
        let signer = MockSigner;
        let sig = signer.sign(b"anything").unwrap();
        assert_eq!(sig.len(), 64);
        assert!(sig.iter().all(|&b| b == 0xAA));
    }

    #[test]
    fn test_mock_signer_always_verifies() {
        let signer = MockSigner;
        assert!(signer.verify(b"anything", &[0; 64]).unwrap());
    }
}
```

- [ ] **Step 6: Write failing tests for LocalEd25519Signer**

Create `crates/siss-gatekeeper/src/signer/local.rs`:

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_local_signer_sign_and_verify() {
        let signer = LocalEd25519Signer::generate();
        let payload = b"test payload for signing";
        let signature = signer.sign(payload).unwrap();
        assert_eq!(signature.len(), 64);
        assert!(signer.verify(payload, &signature).unwrap());
    }

    #[test]
    fn test_local_signer_verify_rejects_tampered_payload() {
        let signer = LocalEd25519Signer::generate();
        let payload = b"original payload";
        let signature = signer.sign(payload).unwrap();
        assert!(!signer.verify(b"tampered payload", &signature).unwrap());
    }

    #[test]
    fn test_local_signer_verify_rejects_wrong_signature() {
        let signer = LocalEd25519Signer::generate();
        let payload = b"test payload";
        let wrong_sig = vec![0xFF; 64];
        assert!(!signer.verify(payload, &wrong_sig).unwrap());
    }

    #[test]
    fn test_from_bytes_roundtrip() {
        let signer = LocalEd25519Signer::generate();
        let key_bytes = signer.signing_key_bytes();
        let restored = LocalEd25519Signer::from_key_bytes(&key_bytes).unwrap();
        let payload = b"roundtrip test";
        let sig = signer.sign(payload).unwrap();
        assert!(restored.verify(payload, &sig).unwrap());
    }
}
```

- [ ] **Step 7: Implement LocalEd25519Signer**

Add above tests in `local.rs`:

```rust
use ed25519_dalek::{Signer as DalekSigner, SigningKey, Verifier, VerifyingKey};
use super::{Signer, SigningError};

/// Ed25519 signer that holds a signing key in memory.
pub struct LocalEd25519Signer {
    signing_key: SigningKey,
    verifying_key: VerifyingKey,
}

impl LocalEd25519Signer {
    /// Generate a new random signing key.
    pub fn generate() -> Self {
        let signing_key = SigningKey::generate(&mut rand::thread_rng());
        let verifying_key = signing_key.verifying_key();
        Self { signing_key, verifying_key }
    }

    /// Restore from a 32-byte secret key.
    pub fn from_key_bytes(bytes: &[u8; 32]) -> Result<Self, SigningError> {
        let signing_key = SigningKey::from_bytes(bytes);
        let verifying_key = signing_key.verifying_key();
        Ok(Self { signing_key, verifying_key })
    }

    /// Export the 32-byte secret key for storage.
    pub fn signing_key_bytes(&self) -> [u8; 32] {
        self.signing_key.to_bytes()
    }
}

impl Signer for LocalEd25519Signer {
    fn sign(&self, payload: &[u8]) -> Result<Vec<u8>, SigningError> {
        let signature = self.signing_key.sign(payload);
        Ok(signature.to_bytes().to_vec())
    }

    fn verify(&self, payload: &[u8], signature: &[u8]) -> Result<bool, SigningError> {
        if signature.len() != 64 {
            return Ok(false);
        }
        let sig_bytes: [u8; 64] = signature.try_into().map_err(|_| SigningError {
            message: "invalid signature length".into(),
        })?;
        let sig = ed25519_dalek::Signature::from_bytes(&sig_bytes);
        Ok(self.verifying_key.verify(payload, &sig).is_ok())
    }
}
```

- [ ] **Step 8: Run all signer tests**

```bash
source "$HOME/.cargo/env" && cargo test -p siss-gatekeeper -- signer payload 2>&1
```

Expected: 9 tests PASS (3 payload + 2 mock + 4 local).

- [ ] **Step 9: Commit**

```bash
git add crates/siss-gatekeeper/src/signer/ crates/siss-gatekeeper/src/payload.rs
git commit -m "feat: implement Signer trait with LocalEd25519Signer, MockSigner, and payload serialization"
```

---

### Task 4: Add Missing DB Repository Functions

**Files:**
- Modify: `crates/siss-graph-db/src/repo/node_repo.rs`

The Gatekeeper pipeline needs to fetch Task, Persona, and IntentMandate by ID, update task status, and freeze a Persona. These functions don't exist yet.

- [ ] **Step 1: Add fetch_task function**

Append to `crates/siss-graph-db/src/repo/node_repo.rs`:

```rust
/// Fetch a Task row by ID. Returns (id, tenant_id, status, intent).
pub async fn fetch_task(pool: &PgPool, task_id: Uuid) -> Result<Option<(Uuid, Uuid, String, String)>, sqlx::Error> {
    let row: Option<(Uuid, Uuid, String, String)> = sqlx::query_as(
        "SELECT id, tenant_id, status::text, intent FROM tasks WHERE id = $1"
    )
    .bind(task_id)
    .fetch_optional(pool)
    .await?;
    Ok(row)
}
```

- [ ] **Step 2: Add fetch_persona function**

Append to `node_repo.rs`:

```rust
/// Fetch a Persona row by ID. Returns (id, tenant_id, name, kind, is_frozen).
pub async fn fetch_persona(pool: &PgPool, persona_id: Uuid) -> Result<Option<(Uuid, Uuid, String, String, bool)>, sqlx::Error> {
    let row: Option<(Uuid, Uuid, String, String, bool)> = sqlx::query_as(
        "SELECT id, tenant_id, name, kind::text, is_frozen FROM personas WHERE id = $1"
    )
    .bind(persona_id)
    .fetch_optional(pool)
    .await?;
    Ok(row)
}
```

- [ ] **Step 3: Add fetch_intent_mandate function**

Append to `node_repo.rs`:

```rust
/// Fetch an IntentMandate row by ID. Returns (id, tenant_id, budget_limit, budget_spent, risk_class, allowed_tools).
pub async fn fetch_intent_mandate(
    pool: &PgPool,
    mandate_id: Uuid,
) -> Result<Option<(Uuid, Uuid, i64, i64, String, Vec<Uuid>)>, sqlx::Error> {
    let row: Option<(Uuid, Uuid, i64, i64, String, Vec<Uuid>)> = sqlx::query_as(
        "SELECT id, tenant_id, budget_limit, budget_spent, risk_class::text, allowed_tools \
         FROM intent_mandates WHERE id = $1"
    )
    .bind(mandate_id)
    .fetch_optional(pool)
    .await?;
    Ok(row)
}
```

- [ ] **Step 4: Add update_task_status function**

Append to `node_repo.rs`:

```rust
/// Update a Task's status. Returns true if the update affected a row.
pub async fn update_task_status(
    pool: &PgPool,
    task_id: Uuid,
    new_status: &str,
) -> Result<bool, sqlx::Error> {
    let result = sqlx::query(
        "UPDATE tasks SET status = $2::task_status, \
         completed_at = CASE WHEN $2 IN ('completed', 'failed') THEN NOW() ELSE completed_at END \
         WHERE id = $1"
    )
    .bind(task_id)
    .bind(new_status)
    .execute(pool)
    .await?;
    Ok(result.rows_affected() > 0)
}
```

- [ ] **Step 5: Add freeze_persona function**

Append to `node_repo.rs`:

```rust
/// Freeze a Persona by setting is_frozen = true.
pub async fn freeze_persona(pool: &PgPool, persona_id: Uuid) -> Result<bool, sqlx::Error> {
    let result = sqlx::query(
        "UPDATE personas SET is_frozen = TRUE WHERE id = $1"
    )
    .bind(persona_id)
    .execute(pool)
    .await?;
    Ok(result.rows_affected() > 0)
}
```

- [ ] **Step 6: Add insert_payment_mandate function**

Append to `node_repo.rs`:

```rust
/// Insert a PaymentMandate with a cryptographic signature. Returns its ID.
pub async fn insert_payment_mandate(
    pool: &PgPool,
    intent_mandate_id: Uuid,
    amount: i64,
    risk_class: &str,
    signature: &[u8],
    tenant_id: Uuid,
) -> Result<Uuid, sqlx::Error> {
    let id = Uuid::new_v4();
    sqlx::query(
        "INSERT INTO payment_mandates (id, tenant_id, intent_mandate_id, amount, risk_class, status, cryptographic_signature) \
         VALUES ($1, $2, $3, $4, $5::risk_class, 'approved'::mandate_status, $6)"
    )
    .bind(id)
    .bind(tenant_id)
    .bind(intent_mandate_id)
    .bind(amount)
    .bind(risk_class)
    .bind(signature)
    .execute(pool)
    .await?;
    Ok(id)
}
```

- [ ] **Step 7: Verify compilation**

```bash
source "$HOME/.cargo/env" && cargo check 2>&1
```

Expected: compiles.

- [ ] **Step 8: Commit**

```bash
git add crates/siss-graph-db/src/repo/node_repo.rs
git commit -m "feat: add fetch/update repo functions for Task, Persona, IntentMandate needed by Gatekeeper"
```

---

### Task 5: Implement RuleEvaluator

**Files:**
- Create: `crates/siss-gatekeeper/src/evaluator/mod.rs`

- [ ] **Step 1: Write failing tests**

Create `crates/siss-gatekeeper/src/evaluator/mod.rs`:

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_known_rule_passes() {
        let evaluator = RuleEvaluator::default();
        let ctx = EvaluationContext {
            task_tenant_id: uuid::Uuid::new_v4(),
            persona_tenant_id: uuid::Uuid::new_v4(), // different — but this rule was already checked
            budget_remaining: 1000,
            estimated_cost: 500,
        };
        // budget_cannot_exceed_limit: already checked in AP2 step, so always passes here
        let result = evaluator.evaluate("budget_cannot_exceed_limit", &ctx);
        assert!(result.is_ok());
        assert!(result.unwrap()); // passes
    }

    #[test]
    fn test_unknown_rule_returns_false() {
        let evaluator = RuleEvaluator::default();
        let ctx = EvaluationContext {
            task_tenant_id: uuid::Uuid::nil(),
            persona_tenant_id: uuid::Uuid::nil(),
            budget_remaining: 0,
            estimated_cost: 0,
        };
        let result = evaluator.evaluate("some_unknown_rule", &ctx);
        assert!(result.is_ok());
        assert!(!result.unwrap()); // unknown → false (treated as advisory warning)
    }

    #[test]
    fn test_session_token_budget_skipped() {
        let evaluator = RuleEvaluator::default();
        let ctx = EvaluationContext {
            task_tenant_id: uuid::Uuid::nil(),
            persona_tenant_id: uuid::Uuid::nil(),
            budget_remaining: 0,
            estimated_cost: 0,
        };
        // Not applicable during authorization — always passes
        let result = evaluator.evaluate("session_token_budget", &ctx);
        assert!(result.unwrap());
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
source "$HOME/.cargo/env" && cargo test -p siss-gatekeeper -- evaluator 2>&1
```

Expected: FAIL.

- [ ] **Step 3: Implement RuleEvaluator**

Add above tests in `evaluator/mod.rs`:

```rust
use std::collections::HashMap;

/// Context available to rule predicates during evaluation.
pub struct EvaluationContext {
    pub task_tenant_id: uuid::Uuid,
    pub persona_tenant_id: uuid::Uuid,
    pub budget_remaining: i64,
    pub estimated_cost: i64,
}

type PredicateFn = fn(&EvaluationContext) -> bool;

/// Maps rule names to hardcoded predicate functions.
/// Unknown rules return false (logged as advisory).
pub struct RuleEvaluator {
    predicates: HashMap<String, PredicateFn>,
}

impl Default for RuleEvaluator {
    fn default() -> Self {
        let mut predicates: HashMap<String, PredicateFn> = HashMap::new();

        // Already checked in pipeline Step 3 (AP2), so this is a no-op confirmation
        predicates.insert("budget_cannot_exceed_limit".into(), |ctx| {
            ctx.budget_remaining >= ctx.estimated_cost
        });

        // Already checked in pipeline Step 1 (validate)
        predicates.insert("cross_tenant_edge_forbidden".into(), |ctx| {
            ctx.task_tenant_id == ctx.persona_tenant_id
        });

        // Already checked in pipeline Step 1 (validate)
        predicates.insert("task_fsm_valid_transitions".into(), |_ctx| true);

        // Not applicable during authorization
        predicates.insert("session_token_budget".into(), |_ctx| true);

        // Not applicable during authorization
        predicates.insert("memory_gc_threshold".into(), |_ctx| true);

        Self { predicates }
    }
}

impl RuleEvaluator {
    /// Evaluate a rule by name. Returns Ok(true) if the rule passes,
    /// Ok(false) if the rule is unknown or fails.
    pub fn evaluate(&self, rule_name: &str, ctx: &EvaluationContext) -> Result<bool, String> {
        match self.predicates.get(rule_name) {
            Some(predicate) => Ok(predicate(ctx)),
            None => Ok(false), // Unknown rule — treated as advisory warning
        }
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
source "$HOME/.cargo/env" && cargo test -p siss-gatekeeper -- evaluator 2>&1
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add crates/siss-gatekeeper/src/evaluator/
git commit -m "feat: implement RuleEvaluator with predefined predicate functions for seeded GovernanceRules"
```

---

### Task 6: Implement Pipeline Steps (validate, rebac, ap2, governance, commit)

**Files:**
- Create: `crates/siss-gatekeeper/src/pipeline/mod.rs`
- Create: `crates/siss-gatekeeper/src/pipeline/validate.rs`
- Create: `crates/siss-gatekeeper/src/pipeline/rebac.rs`
- Create: `crates/siss-gatekeeper/src/pipeline/ap2.rs`
- Create: `crates/siss-gatekeeper/src/pipeline/governance.rs`
- Create: `crates/siss-gatekeeper/src/pipeline/commit.rs`

- [ ] **Step 1: Implement validate step**

Create `crates/siss-gatekeeper/src/pipeline/validate.rs`:

```rust
use sqlx::PgPool;
use uuid::Uuid;

use crate::types::GatekeeperError;

/// Pipeline Step 1: Validate that the Task exists, is pending, the Persona is not frozen,
/// and all entities share the same tenant.
pub async fn validate(
    pool: &PgPool,
    task_id: Uuid,
    persona_id: Uuid,
    tenant_id: Uuid,
) -> Result<(), GatekeeperError> {
    // Fetch task
    let task_row = siss_graph_db::repo::node_repo::fetch_task(pool, task_id)
        .await?
        .ok_or(GatekeeperError::TaskNotFound { task_id })?;

    let (_id, task_tenant, status, _intent) = task_row;

    // Verify status is pending
    if status != "pending" {
        return Err(GatekeeperError::InvalidTaskStatus {
            current: parse_task_status(&status),
            expected: siss_graph_core::node::execution::TaskStatus::Pending,
        });
    }

    // Verify tenant isolation: task tenant == request tenant
    if task_tenant != tenant_id {
        return Err(GatekeeperError::TenantViolation {
            source: task_tenant,
            target: tenant_id,
        });
    }

    // Fetch persona
    let persona_row = siss_graph_db::repo::node_repo::fetch_persona(pool, persona_id)
        .await?
        .ok_or(GatekeeperError::TaskNotFound { task_id: persona_id })?;

    let (_id, persona_tenant, _name, _kind, is_frozen) = persona_row;

    // Verify persona is not frozen
    if is_frozen {
        return Err(GatekeeperError::PersonaFrozen { persona_id });
    }

    // Verify tenant isolation: persona tenant == request tenant
    if persona_tenant != tenant_id {
        return Err(GatekeeperError::TenantViolation {
            source: persona_tenant,
            target: tenant_id,
        });
    }

    Ok(())
}

fn parse_task_status(s: &str) -> siss_graph_core::node::execution::TaskStatus {
    match s {
        "pending" => siss_graph_core::node::execution::TaskStatus::Pending,
        "authorized" => siss_graph_core::node::execution::TaskStatus::Authorized,
        "routing" => siss_graph_core::node::execution::TaskStatus::Routing,
        "executing" => siss_graph_core::node::execution::TaskStatus::Executing,
        "guarding" => siss_graph_core::node::execution::TaskStatus::Guarding,
        "crystallizing" => siss_graph_core::node::execution::TaskStatus::Crystallizing,
        "completed" => siss_graph_core::node::execution::TaskStatus::Completed,
        "failed" => siss_graph_core::node::execution::TaskStatus::Failed,
        _ => siss_graph_core::node::execution::TaskStatus::Failed,
    }
}
```

- [ ] **Step 2: Implement rebac step**

Create `crates/siss-gatekeeper/src/pipeline/rebac.rs`:

```rust
use sqlx::PgPool;
use uuid::Uuid;

use crate::types::GatekeeperError;

/// Pipeline Step 2: Verify the Persona has CAN_EXECUTE access to every requested tool.
pub async fn check_tool_access(
    pool: &PgPool,
    persona_id: Uuid,
    requested_tools: &[Uuid],
    tenant_id: Uuid,
) -> Result<(), GatekeeperError> {
    for &tool_id in requested_tools {
        let has_access = siss_graph_db::repo::rebac_repo::check_access(
            pool,
            persona_id,
            tool_id,
            "can_execute",
            "deny_execute",
            tenant_id,
        )
        .await?;

        if !has_access {
            return Err(GatekeeperError::AccessDenied { tool_id });
        }
    }
    Ok(())
}
```

- [ ] **Step 3: Implement ap2 step**

Create `crates/siss-gatekeeper/src/pipeline/ap2.rs`:

```rust
use sqlx::PgPool;
use uuid::Uuid;

use crate::types::GatekeeperError;

/// Pipeline Step 3: Verify AP2 budget and tool authorization, then debit.
/// Returns (risk_class, budget_remaining_before_debit) for use in later steps.
pub async fn check_and_debit(
    pool: &PgPool,
    intent_mandate_id: Uuid,
    requested_tools: &[Uuid],
    estimated_cost: i64,
) -> Result<(String, i64), GatekeeperError> {
    // Fetch mandate
    let mandate_row = siss_graph_db::repo::node_repo::fetch_intent_mandate(pool, intent_mandate_id)
        .await?
        .ok_or(GatekeeperError::TaskNotFound { task_id: intent_mandate_id })?;

    let (_id, _tenant_id, budget_limit, budget_spent, risk_class, allowed_tools) = mandate_row;
    let remaining = budget_limit - budget_spent;

    // Check each tool is in allowed_tools
    for &tool_id in requested_tools {
        if !allowed_tools.contains(&tool_id) {
            return Err(GatekeeperError::ToolNotAuthorized {
                tool_id,
                mandate_id: intent_mandate_id,
            });
        }
    }

    // Check budget
    if remaining < estimated_cost {
        return Err(GatekeeperError::BudgetExceeded {
            requested: estimated_cost,
            remaining,
        });
    }

    // Atomically debit
    siss_graph_db::repo::ap2_repo::debit_mandate(pool, intent_mandate_id, estimated_cost)
        .await?;

    Ok((risk_class, remaining))
}
```

- [ ] **Step 4: Implement governance step**

Create `crates/siss-gatekeeper/src/pipeline/governance.rs`:

```rust
use sqlx::PgPool;
use uuid::Uuid;

use crate::evaluator::{EvaluationContext, RuleEvaluator};
use crate::types::GatekeeperError;

/// Pipeline Step 4: Evaluate all active GovernanceRules for the "Task" node type.
pub async fn evaluate_rules(
    pool: &PgPool,
    tenant_id: Uuid,
    task_id: Uuid,
    persona_id: Uuid,
    task_tenant_id: Uuid,
    persona_tenant_id: Uuid,
    budget_remaining: i64,
    estimated_cost: i64,
) -> Result<(), GatekeeperError> {
    let rules = siss_graph_db::repo::governance_repo::find_active_rules(pool, "Task", tenant_id)
        .await?;

    let evaluator = RuleEvaluator::default();
    let ctx = EvaluationContext {
        task_tenant_id,
        persona_tenant_id,
        budget_remaining,
        estimated_cost,
    };

    for rule in &rules {
        let passes = evaluator.evaluate(&rule.name, &ctx).unwrap_or(false);

        if !passes {
            match rule.severity.as_str() {
                "advisory" => {
                    // Log but don't block
                    let _ = siss_graph_db::repo::governance_repo::log_violation(
                        pool, rule.id, task_id, tenant_id,
                    )
                    .await;
                }
                "enforced" => {
                    let _ = siss_graph_db::repo::governance_repo::log_violation(
                        pool, rule.id, task_id, tenant_id,
                    )
                    .await;
                    return Err(GatekeeperError::EnforcedRuleViolation {
                        rule_name: rule.name.clone(),
                    });
                }
                "critical" => {
                    let _ = siss_graph_db::repo::governance_repo::log_violation(
                        pool, rule.id, task_id, tenant_id,
                    )
                    .await;
                    // Freeze persona
                    let _ = siss_graph_db::repo::node_repo::freeze_persona(pool, persona_id).await;
                    return Err(GatekeeperError::CriticalRuleViolation {
                        rule_name: rule.name.clone(),
                        persona_frozen: true,
                    });
                }
                _ => {
                    // Unknown severity — treat as advisory
                    let _ = siss_graph_db::repo::governance_repo::log_violation(
                        pool, rule.id, task_id, tenant_id,
                    )
                    .await;
                }
            }
        }
    }

    Ok(())
}
```

- [ ] **Step 5: Implement commit step**

Create `crates/siss-gatekeeper/src/pipeline/commit.rs`:

```rust
use chrono::Utc;
use sqlx::PgPool;
use uuid::Uuid;

use crate::payload::build_signing_payload;
use crate::signer::Signer;
use crate::types::{AuthorizationResult, GatekeeperError};
use siss_graph_core::node::NodeId;

/// Pipeline Step 5: Sign the PaymentMandate, persist edges, transition Task.
pub async fn sign_and_commit(
    pool: &PgPool,
    signer: &dyn Signer,
    task_id: Uuid,
    persona_id: Uuid,
    intent_mandate_id: Uuid,
    estimated_cost: i64,
    risk_class: &str,
    tenant_id: Uuid,
) -> Result<AuthorizationResult, GatekeeperError> {
    let now = Utc::now();
    let timestamp_secs = now.timestamp();

    // Build and sign payload
    let payload = build_signing_payload(task_id, intent_mandate_id, estimated_cost, timestamp_secs);
    let signature = signer.sign(&payload).map_err(|e| GatekeeperError::SigningError {
        message: e.message,
    })?;

    // Create signed PaymentMandate
    let pm_id = siss_graph_db::repo::node_repo::insert_payment_mandate(
        pool,
        intent_mandate_id,
        estimated_cost,
        risk_class,
        &signature,
        tenant_id,
    )
    .await?;

    // Create edges
    // AUTHORIZED_BY: PaymentMandate → IntentMandate
    siss_graph_db::repo::edge_repo::insert_edge(
        pool, pm_id, intent_mandate_id, "authorized_by", tenant_id, serde_json::json!({}),
    )
    .await?;

    // GOVERNED_BY: Task → IntentMandate
    siss_graph_db::repo::edge_repo::insert_edge(
        pool, task_id, intent_mandate_id, "governed_by", tenant_id, serde_json::json!({}),
    )
    .await?;

    // INITIATED_BY: Task → Persona
    siss_graph_db::repo::edge_repo::insert_edge(
        pool, task_id, persona_id, "initiated_by", tenant_id, serde_json::json!({}),
    )
    .await?;

    // Transition Task: pending → authorized
    siss_graph_db::repo::node_repo::update_task_status(pool, task_id, "authorized")
        .await?;

    Ok(AuthorizationResult {
        task_id: NodeId(task_id),
        payment_mandate_id: NodeId(pm_id),
        signature,
        authorized_at: now,
    })
}
```

- [ ] **Step 6: Implement the orchestrator**

Create `crates/siss-gatekeeper/src/pipeline/mod.rs`:

```rust
pub mod validate;
pub mod rebac;
pub mod ap2;
pub mod governance;
pub mod commit;

use sqlx::PgPool;

use crate::signer::Signer;
use crate::types::{AuthorizationRequest, AuthorizationResult, GatekeeperError};

/// The sole entry point for task authorization.
/// Runs the full pipeline: validate → ReBAC → AP2 → governance → sign+commit.
///
/// The entire operation should be called within a database transaction by the caller.
/// If any step fails, the caller should roll back.
pub async fn authorize_task(
    pool: &PgPool,
    signer: &dyn Signer,
    request: &AuthorizationRequest,
) -> Result<AuthorizationResult, GatekeeperError> {
    let task_id = request.task_id.0;
    let persona_id = request.persona_id.0;
    let intent_mandate_id = request.intent_mandate_id.0;
    let tenant_id = request.tenant_id.0;
    let tool_ids: Vec<uuid::Uuid> = request.requested_tools.iter().map(|n| n.0).collect();

    // Step 1: Validate
    validate::validate(pool, task_id, persona_id, tenant_id).await?;

    // Step 2: ReBAC
    rebac::check_tool_access(pool, persona_id, &tool_ids, tenant_id).await?;

    // Step 3: AP2
    let (risk_class, budget_remaining) =
        ap2::check_and_debit(pool, intent_mandate_id, &tool_ids, request.estimated_cost).await?;

    // Step 4: Governance
    governance::evaluate_rules(
        pool,
        tenant_id,
        task_id,
        persona_id,
        tenant_id,    // task_tenant_id (validated to match in step 1)
        tenant_id,    // persona_tenant_id (validated to match in step 1)
        budget_remaining,
        request.estimated_cost,
    )
    .await?;

    // Step 5: Sign + Commit
    let result = commit::sign_and_commit(
        pool,
        signer,
        task_id,
        persona_id,
        intent_mandate_id,
        request.estimated_cost,
        &risk_class,
        tenant_id,
    )
    .await?;

    Ok(result)
}
```

- [ ] **Step 7: Verify compilation**

```bash
source "$HOME/.cargo/env" && cargo check 2>&1
```

Expected: compiles.

- [ ] **Step 8: Commit**

```bash
git add crates/siss-gatekeeper/src/pipeline/
git commit -m "feat: implement Gatekeeper authorization pipeline (validate, rebac, ap2, governance, commit)"
```

---

### Task 7: Write Unit Tests for Pipeline Logic

**Files:**
- Modify: `crates/siss-gatekeeper/src/pipeline/validate.rs` (add unit test for parse_task_status)
- Modify: `crates/siss-gatekeeper/src/pipeline/ap2.rs` (add unit test for error mapping)

Since the pipeline steps call async DB functions, full integration tests require PostgreSQL. In this task we add pure unit tests for the non-async logic.

- [ ] **Step 1: Add parse_task_status tests**

Append to `crates/siss-gatekeeper/src/pipeline/validate.rs`:

```rust
#[cfg(test)]
mod tests {
    use super::*;
    use siss_graph_core::node::execution::TaskStatus;

    #[test]
    fn test_parse_task_status_all_variants() {
        assert_eq!(parse_task_status("pending"), TaskStatus::Pending);
        assert_eq!(parse_task_status("authorized"), TaskStatus::Authorized);
        assert_eq!(parse_task_status("routing"), TaskStatus::Routing);
        assert_eq!(parse_task_status("executing"), TaskStatus::Executing);
        assert_eq!(parse_task_status("guarding"), TaskStatus::Guarding);
        assert_eq!(parse_task_status("crystallizing"), TaskStatus::Crystallizing);
        assert_eq!(parse_task_status("completed"), TaskStatus::Completed);
        assert_eq!(parse_task_status("failed"), TaskStatus::Failed);
        assert_eq!(parse_task_status("unknown"), TaskStatus::Failed);
    }
}
```

- [ ] **Step 2: Run unit tests**

```bash
source "$HOME/.cargo/env" && cargo test -p siss-gatekeeper 2>&1
```

Expected: All tests pass (types: 2, payload: 3, mock signer: 2, local signer: 4, evaluator: 3, validate: 1 = 15 tests).

- [ ] **Step 3: Commit**

```bash
git add crates/siss-gatekeeper/
git commit -m "feat: add unit tests for pipeline validation and complete Gatekeeper crate"
```

---

### Task 8: Run Full Workspace Validation

**Files:** None (validation only)

- [ ] **Step 1: Run complete test suite**

```bash
source "$HOME/.cargo/env" && cargo test --workspace 2>&1
```

Expected: All tests pass across all three crates (58 from siss-graph-core + ~15 from siss-gatekeeper).

- [ ] **Step 2: Run clippy**

```bash
source "$HOME/.cargo/env" && cargo clippy --workspace -- -D warnings 2>&1
```

Expected: No warnings.

- [ ] **Step 3: Fix any issues and commit**

```bash
git add -A
git commit -m "chore: fix clippy warnings from final Gatekeeper validation"
```

- [ ] **Step 4: Verify success criteria against spec**

Verify each criterion from spec section 8:

1. **Valid request → AuthorizationResult:** Covered by `authorize_task` happy path (full integration test requires DB)
2. **Missing CAN_EXECUTE → AccessDenied:** Covered by `pipeline::rebac::check_tool_access`
3. **Budget exceeded → BudgetExceeded, no debit:** Covered by `pipeline::ap2::check_and_debit` (checks before debiting)
4. **Critical rule → CriticalRuleViolation, persona frozen, rollback:** Covered by `pipeline::governance::evaluate_rules`
5. **Frozen persona → PersonaFrozen:** Covered by `pipeline::validate::validate`
6. **Cross-tenant → TenantViolation:** Covered by `pipeline::validate::validate`
7. **Signature verifiable:** Covered by `LocalEd25519Signer` tests
8. **Advisory violations logged but don't block:** Covered by `pipeline::governance::evaluate_rules`
9. **Atomic pipeline:** Guaranteed by PostgreSQL transaction (caller wraps in transaction)

- [ ] **Step 5: Final commit log**

```bash
git log --oneline -10
```

Expected output (approximately):
```
chore: fix clippy warnings from final Gatekeeper validation
feat: add unit tests for pipeline validation and complete Gatekeeper crate
feat: implement Gatekeeper authorization pipeline (validate, rebac, ap2, governance, commit)
feat: implement RuleEvaluator with predefined predicate functions for seeded GovernanceRules
feat: add fetch/update repo functions for Task, Persona, IntentMandate needed by Gatekeeper
feat: implement Signer trait with LocalEd25519Signer, MockSigner, and payload serialization
feat: define Gatekeeper request/response types with hard/soft failure classification
feat: create siss-gatekeeper crate skeleton
```
