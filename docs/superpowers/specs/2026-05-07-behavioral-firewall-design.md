# Behavioral Firewall Design — Step E

**Date:** 2026-05-07
**Status:** Approved
**Scope:** Step E — Post-execution output validation for the SISS value loop
**Depends on:** Step A (Knowledge Graph Schema), Step C (Job Router — ExecutionResult type)

---

## 1. Overview

The Behavioral Firewall is the "Act & Guard" step of the SISS value loop. It receives a Task in `executing` status along with its `ExecutionResult`, runs three hardcoded validation checkers, and either clears the output or blocks it based on violation severity.

The Firewall is a post-execution validator — it does not intercept streaming output. It inspects the completed execution result and renders a verdict: Clear, Blocked, or CriticalBlocked.

### Position in the Value Loop

```
1. [Sense & Authorize] ← Governance Gatekeeper (Step B) ✅
2. [Orient & Preload]  ← Context Cartography (Step D) ✅
3. [Decide & Execute]  ← Job Router (Step C) ✅
4. [Act & Guard]       ← BEHAVIORAL FIREWALL (this component)
5. [Learn & Crystallize] ← Feedback Router (Step F)
```

---

## 2. Architecture

A new Rust library crate `siss-behavioral-firewall` that depends on `siss-graph-core` and `siss-graph-db`. It exposes a single async entry point `inspect_output` and uses a `FirewallChecker` trait for pluggable validation.

### Crate Dependencies

```
siss-behavioral-firewall
  ├── siss-graph-core   (node types: TaskStatus, Severity)
  ├── siss-graph-db     (PostgreSQL repositories)
  └── regex             (content safety pattern matching)
```

### Key Design Principles

1. **Post-execution validation** — inspects completed output, not streaming
2. **Severity-tiered** — reuses advisory/enforced/critical model from Gatekeeper
3. **Violations are data, not errors** — `InspectionResult` always contains a verdict; errors are only for infrastructure failures
4. **Non-short-circuit** — all checkers run; all violations are collected before rendering verdict
5. **Trait-based checkers** — `FirewallChecker` trait makes adding new checkers trivial

---

## 3. Request/Response Types

### InspectionRequest

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | `NodeId` | The Task being inspected |
| `persona_id` | `NodeId` | The Persona that executed the task |
| `intent_mandate_id` | `NodeId` | The IntentMandate that authorized this task |
| `tenant_id` | `NodeId` | Tenant isolation boundary |
| `execution_result` | `ExecutionResult` | The output from the Job Router's executor (output JSON, token_cost, duration_ms) |
| `authorized_tools` | `Vec<Uuid>` | Tool IDs authorized by the IntentMandate |

### InspectionResult

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | `NodeId` | The inspected Task |
| `verdict` | `Verdict` | Clear, Blocked, or CriticalBlocked |
| `violations` | `Vec<Violation>` | All violations found (may be empty) |

### Verdict

| Variant | Description |
|---------|-------------|
| `Clear` | All checks passed, or only advisory violations found. Task proceeds. |
| `Blocked` | At least one `enforced` violation. Output rejected. Task stays in `guarding`. |
| `CriticalBlocked` | At least one `critical` violation. Output rejected. Persona frozen. Task transitions to `failed`. |

### Violation

| Field | Type | Description |
|-------|------|-------------|
| `checker` | `String` | Which checker caught it (e.g., `"budget_compliance"`) |
| `severity` | `Severity` | advisory, enforced, or critical |
| `message` | `String` | Human-readable description |

### FirewallError

| Variant | Description |
|---------|-------------|
| `TaskNotFound` | Task ID does not exist |
| `InvalidTaskStatus` | Task is not in `executing` status |
| `TenantViolation` | Cross-tenant operation attempted |
| `DatabaseError` | Database operation failed |

---

## 4. FirewallChecker Trait

```rust
pub trait FirewallChecker: Send + Sync {
    fn name(&self) -> &str;
    fn check(&self, context: &InspectionContext) -> Vec<Violation>;
}
```

### InspectionContext

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | `Uuid` | Task identifier |
| `token_cost` | `i64` | Actual tokens consumed by execution |
| `output` | `serde_json::Value` | The execution output JSON |
| `authorized_tools` | `Vec<Uuid>` | Tools authorized by the mandate |
| `budget_remaining` | `i64` | Budget remaining on the IntentMandate before this task's execution |

---

## 5. Launch Checkers

### 5.1 BudgetComplianceChecker

Checks whether the executor's actual `token_cost` exceeds the IntentMandate's remaining budget.

| Condition | Severity | Message |
|-----------|----------|---------|
| `token_cost > budget_remaining` | `critical` | "Execution cost {token_cost} exceeded remaining budget {budget_remaining}" |

### 5.2 ToolComplianceChecker

Scans the output JSON for any tool ID references that are not in `authorized_tools`. Looks for UUID-formatted strings in the output and checks them against the whitelist.

| Condition | Severity | Message |
|-----------|----------|---------|
| Output contains UUID not in `authorized_tools` | `enforced` | "Output references unauthorized tool {tool_id}" |

Note: this is a heuristic. It scans for UUID-like strings in the output. False positives are possible but the enforced severity means the output is blocked, not the Persona frozen.

### 5.3 ContentSafetyChecker

Scans the output text for forbidden patterns using regex matching.

**Default patterns:**

| Pattern Name | Regex | Severity |
|-------------|-------|----------|
| `shell_dangerous` | `rm\s+-rf\|sudo\s+\|chmod\s+777` | `critical` |
| `sql_destructive` | `(?i)DROP\s+TABLE\|DELETE\s+FROM\s+\w+\s*$` | `enforced` |
| `code_injection` | `eval\s*\(\|exec\s*\(` | `enforced` |

**Configuration:**

```rust
pub struct ContentSafetyConfig {
    pub patterns: Vec<ForbiddenPattern>,
}

pub struct ForbiddenPattern {
    pub name: String,
    pub pattern: String,    // Regex
    pub severity: Severity,
}

impl Default for ContentSafetyConfig {
    // Provides the three default patterns above
}
```

New patterns can be added via `ContentSafetyConfig` without code changes to the checker itself.

---

## 6. Inspection Pipeline

The `inspect_output` function executes the following steps:

### Step 1: VALIDATE

- Fetch Task from DB; verify `status == Executing`
- Verify tenant isolation: `task.tenant_id == request.tenant_id`
- On failure: return `FirewallError`

### Step 2: TRANSITION TO GUARDING

- Transition Task: `executing` → `guarding`

### Step 3: FETCH BUDGET

- Fetch IntentMandate to get `budget_remaining` (budget_limit - budget_spent)
- Build `InspectionContext` from request data + budget info

### Step 4: RUN CHECKERS

- Run all three checkers against the `InspectionContext`
- Collect all `Violation` instances into a single list
- Do not short-circuit — run every checker regardless of prior violations

### Step 5: RENDER VERDICT

- If no violations: `Verdict::Clear`
- If worst severity is `advisory`: `Verdict::Clear` (advisory doesn't block)
- If worst severity is `enforced`: `Verdict::Blocked`
- If worst severity is `critical`: `Verdict::CriticalBlocked`

### Step 6: ACT ON VERDICT

- **Clear:** No action needed. Task stays in `guarding` (Feedback Router takes over).
- **Blocked:** Log all violations as `VIOLATED_BY` edges. Task stays in `guarding` for retry or manual review.
- **CriticalBlocked:** Log all violations as `VIOLATED_BY` edges. Freeze the Persona. Transition Task to `failed`.

### Step 7: RETURN

- Return `InspectionResult` with verdict and full violation list.

---

## 7. DB Functions Needed

All needed functions already exist from previous steps:

- `node_repo::fetch_task` — validate task exists and get status
- `node_repo::fetch_intent_mandate` — get budget info
- `node_repo::update_task_status` — transition to guarding/failed
- `node_repo::freeze_persona` — freeze on critical violation
- `governance_repo::log_violation` — create VIOLATED_BY edges
- `edge_repo::insert_edge` — alternative for violation logging

No new DB functions needed.

---

## 8. File Structure

```
crates/
  siss-behavioral-firewall/
    Cargo.toml
    src/
      lib.rs                  # Re-exports
      types.rs                # InspectionRequest, InspectionResult, Verdict, Violation, FirewallError
      context.rs              # InspectionContext
      checker/
        mod.rs                # FirewallChecker trait
        budget.rs             # BudgetComplianceChecker
        tools.rs              # ToolComplianceChecker
        content.rs            # ContentSafetyChecker + ContentSafetyConfig + ForbiddenPattern
      verdict.rs              # Verdict rendering logic (collect violations → determine verdict)
      pipeline/
        mod.rs                # inspect_output() orchestrator
        validate.rs           # Step 1: validation + Step 2: transition to guarding
        inspect.rs            # Steps 3-4: build context + run checkers
        act.rs                # Steps 5-6: render verdict + act on it
```

---

## 9. Success Criteria

The Behavioral Firewall is correct when:

1. A clean execution result with `token_cost` within budget and no forbidden patterns returns `Verdict::Clear` with zero violations.
2. An execution where `token_cost` exceeds `budget_remaining` returns `Verdict::CriticalBlocked` with a `budget_compliance` violation.
3. An execution whose output contains a UUID not in `authorized_tools` returns `Verdict::Blocked` with a `tool_compliance` violation.
4. An execution whose output contains `rm -rf` returns `Verdict::CriticalBlocked` with a `content_safety` violation.
5. An execution whose output contains `eval(` returns `Verdict::Blocked` with a `content_safety` violation.
6. Multiple violations from different checkers are all collected and returned — no short-circuiting.
7. Advisory violations are logged via `VIOLATED_BY` edges but the verdict is still `Clear`.
8. A `CriticalBlocked` verdict freezes the Persona and transitions the Task to `failed`.
9. A `Blocked` verdict logs violations but does NOT freeze the Persona or transition the Task to `failed`.
10. A Task not in `executing` status returns `InvalidTaskStatus`.
11. Cross-tenant requests return `TenantViolation`.
