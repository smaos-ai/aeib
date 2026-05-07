# Governance Gatekeeper Design — Step B

**Date:** 2026-05-07
**Status:** Approved
**Scope:** Step B — The authorization gateway for the SISS value loop
**Depends on:** Step A (Knowledge Graph Schema)

---

## 1. Overview

The Governance Gatekeeper is the sole entry point for every transaction in the SISS substrate. No Task executes without passing through the Gatekeeper. It is the component that transitions a Task from `pending` to `authorized` by orchestrating three concurrent checks: ReBAC access control, AP2 budget verification, and GovernanceRule evaluation.

The Gatekeeper does not own any data. It is a pure coordinator that calls existing invariants from `siss-graph-core` and persistence from `siss-graph-db`, wrapping the entire authorization pipeline in a single database transaction.

### Position in the Value Loop

```
1. [Sense & Authorize] ← GATEKEEPER (this component)
2. [Orient & Preload]  ← Context Cartography (Step D)
3. [Decide & Execute]  ← Job Router (Step C)
4. [Act & Guard]       ← Behavioral Firewall (Step E)
5. [Learn & Crystallize] ← Feedback Router (Step F)
```

---

## 2. Architecture

A new Rust library crate `siss-gatekeeper` that depends on `siss-graph-core` and `siss-graph-db`. It exposes a single async entry point `authorize_task` and a `Signer` trait for cryptographic mandate signing.

### Crate Dependencies

```
siss-gatekeeper
  ├── siss-graph-core   (node types, edge types, invariant logic)
  └── siss-graph-db     (PostgreSQL repositories)
```

### Key Design Principles

1. **Pure coordinator** — no owned state, no data storage, just orchestration
2. **Single transaction** — the entire pipeline runs in one DB transaction; failure rolls back everything
3. **Sequential pipeline** — ReBAC → AP2 → Governance, in order (AP2 debit only after access is confirmed)
4. **Trait-based signing** — `Signer` trait with `LocalEd25519Signer` default and `MockSigner` for tests

---

## 3. Request/Response Types

### AuthorizationRequest

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | `NodeId` | The Task to authorize |
| `persona_id` | `NodeId` | The Persona requesting authorization |
| `intent_mandate_id` | `NodeId` | The IntentMandate providing budget |
| `requested_tools` | `Vec<NodeId>` | Tools/Skills this Task needs to execute |
| `estimated_cost` | `i64` | Estimated token spend in microunits |
| `tenant_id` | `NodeId` | Tenant isolation boundary |

### AuthorizationResult

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | `NodeId` | The authorized Task |
| `payment_mandate_id` | `NodeId` | The created PaymentMandate |
| `signature` | `Vec<u8>` | Ed25519 signature of the PaymentMandate |
| `authorized_at` | `DateTime<Utc>` | Timestamp of authorization |

### GatekeeperError

Errors are split into two categories that determine Task behavior:

**Hard failures** — Task transitions to `failed`:

| Variant | Description |
|---------|-------------|
| `TenantViolation` | Cross-tenant operation attempted |
| `PersonaFrozen` | The requesting Persona is frozen |
| `CriticalRuleViolation` | A `critical` GovernanceRule was violated; Persona is frozen |

**Soft failures** — Task stays `pending`, caller can retry:

| Variant | Description |
|---------|-------------|
| `AccessDenied` | ReBAC denied access to a requested Tool |
| `BudgetExceeded` | IntentMandate has insufficient remaining budget |
| `ToolNotAuthorized` | Requested Tool is not in the IntentMandate's allowed_tools list |
| `EnforcedRuleViolation` | An `enforced` GovernanceRule was violated |

**Infrastructure errors:**

| Variant | Description |
|---------|-------------|
| `TaskNotFound` | Task ID does not exist |
| `InvalidTaskStatus` | Task is not in `pending` status |
| `SigningError` | Cryptographic signing failed |
| `DatabaseError` | Database operation failed |

---

## 4. Authorization Pipeline

The `authorize_task` function executes the following steps sequentially, all within a single database transaction.

### Step 1: VALIDATE

- Fetch Task from DB; verify `status == Pending`
- Fetch Persona from DB; verify `is_frozen == false`
- Check tenant isolation: `task.tenant_id == persona.tenant_id == request.tenant_id`
- On any failure: **hard fail** (Task → `failed` for tenant violation or frozen persona; `InvalidTaskStatus`/`TaskNotFound` for infrastructure issues)

### Step 2: REBAC

- For each `tool_id` in `requested_tools`:
  - Call `rebac_repo::check_access(persona_id, tool_id, "can_execute", "deny_execute", tenant_id)`
  - First `false` result → **soft fail** with `AccessDenied`
- All tools must pass before proceeding

### Step 3: AP2

- Fetch IntentMandate from DB
- For each `tool_id` in `requested_tools`:
  - Verify tool is in `mandate.allowed_tools`
  - On failure → **soft fail** with `ToolNotAuthorized`
- Verify `mandate.has_budget(estimated_cost)`
  - On failure → **soft fail** with `BudgetExceeded`
- Atomically debit: `ap2_repo::debit_mandate(mandate_id, estimated_cost)`
  - DB CHECK constraint provides concurrent safety

### Step 4: GOVERNANCE

- Call `governance_repo::find_active_rules(pool, "Task", tenant_id)`
- For each rule, evaluate the predicate against the current context:
  - GovernanceRule expressions are evaluated via a `RuleEvaluator` that matches rule names to hardcoded predicate functions (e.g., `budget_cannot_exceed_limit` → check budget invariant). A full DSL interpreter is a future enhancement.
  - `Advisory` violation → log via `governance_repo::log_violation()`, continue
  - `Enforced` violation → abort, **soft fail** with `EnforcedRuleViolation`
  - `Critical` violation → abort, freeze Persona, log violation, **hard fail** with `CriticalRuleViolation`

### Step 5: SIGN + COMMIT

- Create a `PaymentMandate` record (amount = estimated_cost, risk_class from IntentMandate)
- Serialize the mandate payload: `task_id | intent_mandate_id | amount | timestamp`
- Sign via `Signer::sign(payload)` → `signature`
- Store the signed PaymentMandate with the cryptographic signature
- Create edges:
  - `AUTHORIZED_BY`: PaymentMandate → IntentMandate
  - `GOVERNED_BY`: Task → IntentMandate
  - `INITIATED_BY`: Task → Persona
- Transition Task: `pending` → `authorized`
- Commit the database transaction
- Return `AuthorizationResult`

### Transaction Rollback Behavior

If any step after the AP2 debit (Step 3) fails, the entire database transaction rolls back, automatically restoring the IntentMandate's budget. This is guaranteed by PostgreSQL's ACID properties.

---

## 5. Signer Trait

```rust
pub trait Signer: Send + Sync {
    fn sign(&self, payload: &[u8]) -> Result<Vec<u8>, SigningError>;
    fn verify(&self, payload: &[u8], signature: &[u8]) -> Result<bool, SigningError>;
}
```

### Implementations

| Implementation | Description | Use Case |
|---------------|-------------|----------|
| `LocalEd25519Signer` | Holds an `ed25519_dalek::SigningKey` in memory. Signs and verifies locally. | Default for sovereign local-first deployment |
| `MockSigner` | Returns deterministic `[0xAA; 64]` signatures. Always verifies true. | Unit and integration tests |

### Signing Payload Format

The payload to sign is a deterministic byte sequence:

```
task_id (16 bytes, UUID) ||
intent_mandate_id (16 bytes, UUID) ||
amount (8 bytes, i64 big-endian) ||
timestamp (8 bytes, Unix epoch seconds i64 big-endian)
```

This produces a 48-byte payload that is signed with Ed25519, producing a 64-byte signature.

---

## 6. GovernanceRule Evaluation Strategy

At launch, GovernanceRule expressions are not interpreted from a DSL. Instead, a `RuleEvaluator` maps rule names to predefined Rust functions:

| Rule Name | Predicate Function |
|-----------|-------------------|
| `budget_cannot_exceed_limit` | Verify IntentMandate budget constraint (already checked in Step 3, so this is a no-op confirmation) |
| `cross_tenant_edge_forbidden` | Verify all entities share the same tenant_id (already checked in Step 1) |
| `task_fsm_valid_transitions` | Verify Task is in valid state for authorization (already checked in Step 1) |
| `session_token_budget` | Not applicable during authorization — skip |
| `memory_gc_threshold` | Not applicable during authorization — skip |

Rules with `applies_to` containing `"Task"` are evaluated. Rules that don't match any predefined predicate function are logged as `advisory` warnings (unknown rule).

This approach means:
- All five seeded GovernanceRules work correctly at launch
- New custom rules can be added to the database, but only predefined predicates are enforced
- The DSL interpreter is a future enhancement that replaces the name→function map

---

## 7. File Structure

```
crates/
  siss-gatekeeper/
    Cargo.toml
    src/
      lib.rs              # Re-exports
      types.rs            # AuthorizationRequest, AuthorizationResult, GatekeeperError
      signer/
        mod.rs            # Signer trait
        local.rs          # LocalEd25519Signer
        mock.rs           # MockSigner for tests
      pipeline/
        mod.rs            # authorize_task() orchestrator
        validate.rs       # Step 1: validation
        rebac.rs          # Step 2: ReBAC checks
        ap2.rs            # Step 3: AP2 budget + tool auth
        governance.rs     # Step 4: GovernanceRule evaluation
        commit.rs         # Step 5: sign, persist, transition
      evaluator/
        mod.rs            # RuleEvaluator: rule name → predicate function map
```

---

## 8. Success Criteria

The Gatekeeper is correct when:

1. A valid AuthorizationRequest with sufficient budget, correct ReBAC edges, and no rule violations returns an `AuthorizationResult` with a signed PaymentMandate and the Task in `authorized` status.
2. A request for a Tool the Persona lacks `CAN_EXECUTE` on returns `AccessDenied`, and the Task remains `pending`.
3. A request exceeding the IntentMandate's budget returns `BudgetExceeded`, the Task remains `pending`, and no budget was debited.
4. A request that passes ReBAC and AP2 but violates a `critical` GovernanceRule returns `CriticalRuleViolation`, the Task transitions to `failed`, the Persona is frozen, and the budget debit is rolled back.
5. A request from a frozen Persona returns `PersonaFrozen` and the Task transitions to `failed`.
6. A cross-tenant request returns `TenantViolation` and the Task transitions to `failed`.
7. The PaymentMandate signature can be verified using the corresponding public key.
8. Advisory GovernanceRule violations are logged via `VIOLATED_BY` edges but do not block authorization.
9. The entire authorization pipeline is atomic — partial failures leave no orphaned state.
