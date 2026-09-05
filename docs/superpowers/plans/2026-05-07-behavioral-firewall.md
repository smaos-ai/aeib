# Behavioral Firewall Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `siss-behavioral-firewall` crate — the post-execution output validator that runs budget, tool, and content safety checks against execution results and renders a severity-tiered verdict.

**Architecture:** A new Rust library crate `siss-behavioral-firewall` that depends on `siss-graph-core` and `siss-graph-db`. Exposes a single async `inspect_output()` entry point. Three hardcoded checkers behind a `FirewallChecker` trait: BudgetComplianceChecker, ToolComplianceChecker, ContentSafetyChecker. Non-short-circuit: all violations collected, worst severity determines verdict.

**Tech Stack:** Rust (2024 edition), sqlx (async PostgreSQL), regex, serde/serde_json, uuid, chrono, tokio, thiserror

**Spec:** `docs/superpowers/specs/2026-05-07-behavioral-firewall-design.md`

---

## File Structure

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
      verdict.rs              # Verdict rendering logic
      pipeline/
        mod.rs                # inspect_output() orchestrator
        validate.rs           # Validation + transition to guarding
        inspect.rs            # Build context + run checkers
        act.rs                # Render verdict + act on it (log, freeze, fail)
```

---

### Task 1: Create siss-behavioral-firewall Crate Skeleton

**Files:**
- Modify: `Cargo.toml` (workspace root)
- Create: `crates/siss-behavioral-firewall/Cargo.toml`
- Create: `crates/siss-behavioral-firewall/src/lib.rs`
- Create: stub modules

- [ ] **Step 1: Add crate to workspace and create structure**

Add `"crates/siss-behavioral-firewall"` to workspace members. Add `regex = "1"` to `[workspace.dependencies]`.

Create `crates/siss-behavioral-firewall/Cargo.toml`:

```toml
[package]
name = "siss-behavioral-firewall"
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
regex.workspace = true

[dev-dependencies]
tokio = { workspace = true, features = ["full", "test-util"] }
```

Create `crates/siss-behavioral-firewall/src/lib.rs`:

```rust
pub mod types;
pub mod context;
pub mod checker;
pub mod verdict;
pub mod pipeline;
```

Create stubs for all modules.

- [ ] **Step 2: Verify compilation and commit**

```bash
source "$HOME/.cargo/env" && cargo check
git add Cargo.toml crates/siss-behavioral-firewall/
git commit -m "feat: create siss-behavioral-firewall crate skeleton"
```

---

### Task 2: Define Types and InspectionContext

**Files:**
- Create: `crates/siss-behavioral-firewall/src/types.rs`
- Create: `crates/siss-behavioral-firewall/src/context.rs`

- [ ] **Step 1: Implement types with tests**

Create `crates/siss-behavioral-firewall/src/types.rs`:

```rust
use serde::{Deserialize, Serialize};
use thiserror::Error;
use uuid::Uuid;

use siss_graph_core::node::NodeId;
use siss_graph_core::node::execution::TaskStatus;
use siss_graph_core::node::governance::Severity;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InspectionRequest {
    pub task_id: NodeId,
    pub persona_id: NodeId,
    pub intent_mandate_id: NodeId,
    pub tenant_id: NodeId,
    pub execution_output: serde_json::Value,
    pub token_cost: i64,
    pub authorized_tools: Vec<Uuid>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InspectionResult {
    pub task_id: NodeId,
    pub verdict: Verdict,
    pub violations: Vec<Violation>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Verdict {
    Clear,
    Blocked,
    CriticalBlocked,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Violation {
    pub checker: String,
    pub severity: Severity,
    pub message: String,
}

#[derive(Debug, Error)]
pub enum FirewallError {
    #[error("task {task_id} not found")]
    TaskNotFound { task_id: Uuid },

    #[error("invalid task status: current={current:?}, expected={expected:?}")]
    InvalidTaskStatus { current: TaskStatus, expected: TaskStatus },

    #[error("cross-tenant violation: source {source_tenant} != target {target_tenant}")]
    TenantViolation { source_tenant: Uuid, target_tenant: Uuid },

    #[error("database error: {message}")]
    DatabaseError { message: String },
}

impl From<sqlx::Error> for FirewallError {
    fn from(e: sqlx::Error) -> Self {
        Self::DatabaseError { message: e.to_string() }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_verdict_equality() {
        assert_eq!(Verdict::Clear, Verdict::Clear);
        assert_ne!(Verdict::Clear, Verdict::Blocked);
        assert_ne!(Verdict::Blocked, Verdict::CriticalBlocked);
    }

    #[test]
    fn test_create_violation() {
        let v = Violation {
            checker: "budget_compliance".into(),
            severity: Severity::Critical,
            message: "overspent".into(),
        };
        assert_eq!(v.checker, "budget_compliance");
        assert_eq!(v.severity, Severity::Critical);
    }
}
```

- [ ] **Step 2: Implement InspectionContext**

Create `crates/siss-behavioral-firewall/src/context.rs`:

```rust
use uuid::Uuid;

/// The validated context available to all firewall checkers.
#[derive(Debug, Clone)]
pub struct InspectionContext {
    pub task_id: Uuid,
    pub token_cost: i64,
    pub output: serde_json::Value,
    pub authorized_tools: Vec<Uuid>,
    pub budget_remaining: i64,
}
```

- [ ] **Step 3: Run tests and commit**

```bash
source "$HOME/.cargo/env" && cargo test -p siss-behavioral-firewall -- types
git add crates/siss-behavioral-firewall/src/types.rs crates/siss-behavioral-firewall/src/context.rs
git commit -m "feat: define Firewall types (InspectionRequest, Verdict, Violation) and InspectionContext"
```

---

### Task 3: Implement FirewallChecker Trait and BudgetComplianceChecker

**Files:**
- Create: `crates/siss-behavioral-firewall/src/checker/mod.rs`
- Create: `crates/siss-behavioral-firewall/src/checker/budget.rs`

- [ ] **Step 1: Define trait and implement budget checker with tests**

Create `crates/siss-behavioral-firewall/src/checker/mod.rs`:

```rust
pub mod budget;
pub mod tools;
pub mod content;

use crate::context::InspectionContext;
use crate::types::Violation;

/// Trait for firewall validation checkers.
pub trait FirewallChecker: Send + Sync {
    fn name(&self) -> &str;
    fn check(&self, context: &InspectionContext) -> Vec<Violation>;
}
```

Create `crates/siss-behavioral-firewall/src/checker/budget.rs`:

```rust
use siss_graph_core::node::governance::Severity;

use crate::context::InspectionContext;
use crate::types::Violation;
use super::FirewallChecker;

/// Checks whether actual token_cost exceeds the mandate's remaining budget.
pub struct BudgetComplianceChecker;

impl FirewallChecker for BudgetComplianceChecker {
    fn name(&self) -> &str {
        "budget_compliance"
    }

    fn check(&self, context: &InspectionContext) -> Vec<Violation> {
        if context.token_cost > context.budget_remaining {
            vec![Violation {
                checker: self.name().into(),
                severity: Severity::Critical,
                message: format!(
                    "Execution cost {} exceeded remaining budget {}",
                    context.token_cost, context.budget_remaining
                ),
            }]
        } else {
            vec![]
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_context(token_cost: i64, budget_remaining: i64) -> InspectionContext {
        InspectionContext {
            task_id: uuid::Uuid::nil(),
            token_cost,
            output: serde_json::json!({}),
            authorized_tools: vec![],
            budget_remaining,
        }
    }

    #[test]
    fn test_within_budget_no_violation() {
        let checker = BudgetComplianceChecker;
        let ctx = make_context(100, 500);
        assert!(checker.check(&ctx).is_empty());
    }

    #[test]
    fn test_exact_budget_no_violation() {
        let checker = BudgetComplianceChecker;
        let ctx = make_context(500, 500);
        assert!(checker.check(&ctx).is_empty());
    }

    #[test]
    fn test_over_budget_critical_violation() {
        let checker = BudgetComplianceChecker;
        let ctx = make_context(501, 500);
        let violations = checker.check(&ctx);
        assert_eq!(violations.len(), 1);
        assert_eq!(violations[0].severity, Severity::Critical);
        assert_eq!(violations[0].checker, "budget_compliance");
    }
}
```

- [ ] **Step 2: Run tests and commit**

```bash
source "$HOME/.cargo/env" && cargo test -p siss-behavioral-firewall -- checker::budget
git add crates/siss-behavioral-firewall/src/checker/
git commit -m "feat: implement FirewallChecker trait and BudgetComplianceChecker"
```

---

### Task 4: Implement ToolComplianceChecker

**Files:**
- Create: `crates/siss-behavioral-firewall/src/checker/tools.rs`

- [ ] **Step 1: Implement with tests**

Create `crates/siss-behavioral-firewall/src/checker/tools.rs`:

```rust
use siss_graph_core::node::governance::Severity;
use uuid::Uuid;

use crate::context::InspectionContext;
use crate::types::Violation;
use super::FirewallChecker;

/// Scans output JSON for UUID-like strings not in the authorized_tools list.
pub struct ToolComplianceChecker;

impl FirewallChecker for ToolComplianceChecker {
    fn name(&self) -> &str {
        "tool_compliance"
    }

    fn check(&self, context: &InspectionContext) -> Vec<Violation> {
        if context.authorized_tools.is_empty() {
            return vec![]; // No tools to check against
        }

        let output_str = context.output.to_string();
        let mut violations = Vec::new();

        // Find all UUID-like strings in the output
        for uuid_str in extract_uuids(&output_str) {
            if let Ok(found_uuid) = Uuid::parse_str(&uuid_str) {
                if !context.authorized_tools.contains(&found_uuid) {
                    violations.push(Violation {
                        checker: self.name().into(),
                        severity: Severity::Enforced,
                        message: format!("Output references unauthorized tool {}", found_uuid),
                    });
                }
            }
        }

        violations
    }
}

/// Extract UUID-formatted strings from text.
/// Matches the standard 8-4-4-4-12 hex format.
fn extract_uuids(text: &str) -> Vec<String> {
    let mut uuids = Vec::new();
    // Simple pattern: 8-4-4-4-12 hex digits
    let bytes = text.as_bytes();
    let len = bytes.len();
    let mut i = 0;

    while i + 36 <= len {
        let candidate = &text[i..i + 36];
        if is_uuid_format(candidate) {
            uuids.push(candidate.to_string());
            i += 36;
        } else {
            i += 1;
        }
    }

    uuids
}

fn is_uuid_format(s: &str) -> bool {
    if s.len() != 36 {
        return false;
    }
    let bytes = s.as_bytes();
    for (i, &b) in bytes.iter().enumerate() {
        match i {
            8 | 13 | 18 | 23 => {
                if b != b'-' {
                    return false;
                }
            }
            _ => {
                if !b.is_ascii_hexdigit() {
                    return false;
                }
            }
        }
    }
    true
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_context_with_output(output: serde_json::Value, tools: Vec<Uuid>) -> InspectionContext {
        InspectionContext {
            task_id: Uuid::nil(),
            token_cost: 100,
            output,
            authorized_tools: tools,
            budget_remaining: 1000,
        }
    }

    #[test]
    fn test_no_uuids_in_output_no_violation() {
        let checker = ToolComplianceChecker;
        let ctx = make_context_with_output(
            serde_json::json!({"result": "hello world"}),
            vec![Uuid::new_v4()],
        );
        assert!(checker.check(&ctx).is_empty());
    }

    #[test]
    fn test_authorized_uuid_no_violation() {
        let tool_id = Uuid::new_v4();
        let checker = ToolComplianceChecker;
        let ctx = make_context_with_output(
            serde_json::json!({"tool_used": tool_id.to_string()}),
            vec![tool_id],
        );
        assert!(checker.check(&ctx).is_empty());
    }

    #[test]
    fn test_unauthorized_uuid_enforced_violation() {
        let authorized = Uuid::new_v4();
        let unauthorized = Uuid::new_v4();
        let checker = ToolComplianceChecker;
        let ctx = make_context_with_output(
            serde_json::json!({"tool_used": unauthorized.to_string()}),
            vec![authorized],
        );
        let violations = checker.check(&ctx);
        assert_eq!(violations.len(), 1);
        assert_eq!(violations[0].severity, Severity::Enforced);
        assert_eq!(violations[0].checker, "tool_compliance");
    }

    #[test]
    fn test_empty_authorized_tools_skips_check() {
        let checker = ToolComplianceChecker;
        let ctx = make_context_with_output(
            serde_json::json!({"tool_used": Uuid::new_v4().to_string()}),
            vec![],
        );
        assert!(checker.check(&ctx).is_empty());
    }

    #[test]
    fn test_extract_uuids_finds_uuid() {
        let uuid = Uuid::new_v4();
        let text = format!("prefix {} suffix", uuid);
        let found = extract_uuids(&text);
        assert_eq!(found.len(), 1);
        assert_eq!(found[0], uuid.to_string());
    }

    #[test]
    fn test_is_uuid_format() {
        assert!(is_uuid_format("550e8400-e29b-41d4-a716-446655440000"));
        assert!(!is_uuid_format("not-a-uuid-at-all-nope-definitely"));
        assert!(!is_uuid_format("short"));
    }
}
```

- [ ] **Step 2: Run tests and commit**

```bash
source "$HOME/.cargo/env" && cargo test -p siss-behavioral-firewall -- checker::tools
git add crates/siss-behavioral-firewall/src/checker/tools.rs
git commit -m "feat: implement ToolComplianceChecker with UUID extraction"
```

---

### Task 5: Implement ContentSafetyChecker

**Files:**
- Create: `crates/siss-behavioral-firewall/src/checker/content.rs`

- [ ] **Step 1: Implement with tests**

Create `crates/siss-behavioral-firewall/src/checker/content.rs`:

```rust
use regex::Regex;
use siss_graph_core::node::governance::Severity;

use crate::context::InspectionContext;
use crate::types::Violation;
use super::FirewallChecker;

/// A forbidden pattern with its name, regex, and severity.
#[derive(Debug, Clone)]
pub struct ForbiddenPattern {
    pub name: String,
    pub pattern: String,
    pub severity: Severity,
}

/// Configuration for the content safety checker.
#[derive(Debug, Clone)]
pub struct ContentSafetyConfig {
    pub patterns: Vec<ForbiddenPattern>,
}

impl Default for ContentSafetyConfig {
    fn default() -> Self {
        Self {
            patterns: vec![
                ForbiddenPattern {
                    name: "shell_dangerous".into(),
                    pattern: r"rm\s+-rf|sudo\s+|chmod\s+777".into(),
                    severity: Severity::Critical,
                },
                ForbiddenPattern {
                    name: "sql_destructive".into(),
                    pattern: r"(?i)DROP\s+TABLE|DELETE\s+FROM\s+\w+\s*$".into(),
                    severity: Severity::Enforced,
                },
                ForbiddenPattern {
                    name: "code_injection".into(),
                    pattern: r"eval\s*\(|exec\s*\(".into(),
                    severity: Severity::Enforced,
                },
            ],
        }
    }
}

/// Scans execution output text for forbidden patterns.
pub struct ContentSafetyChecker {
    config: ContentSafetyConfig,
}

impl ContentSafetyChecker {
    pub fn new(config: ContentSafetyConfig) -> Self {
        Self { config }
    }

    pub fn with_defaults() -> Self {
        Self::new(ContentSafetyConfig::default())
    }
}

impl FirewallChecker for ContentSafetyChecker {
    fn name(&self) -> &str {
        "content_safety"
    }

    fn check(&self, context: &InspectionContext) -> Vec<Violation> {
        let output_str = context.output.to_string();
        let mut violations = Vec::new();

        for fp in &self.config.patterns {
            if let Ok(re) = Regex::new(&fp.pattern) {
                if re.is_match(&output_str) {
                    violations.push(Violation {
                        checker: self.name().into(),
                        severity: fp.severity,
                        message: format!("Forbidden pattern '{}' detected in output", fp.name),
                    });
                }
            }
        }

        violations
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_context_with_output(output: serde_json::Value) -> InspectionContext {
        InspectionContext {
            task_id: uuid::Uuid::nil(),
            token_cost: 100,
            output,
            authorized_tools: vec![],
            budget_remaining: 1000,
        }
    }

    #[test]
    fn test_clean_output_no_violations() {
        let checker = ContentSafetyChecker::with_defaults();
        let ctx = make_context_with_output(serde_json::json!({"result": "hello world"}));
        assert!(checker.check(&ctx).is_empty());
    }

    #[test]
    fn test_rm_rf_critical_violation() {
        let checker = ContentSafetyChecker::with_defaults();
        let ctx = make_context_with_output(serde_json::json!({"command": "rm -rf /"}));
        let violations = checker.check(&ctx);
        assert_eq!(violations.len(), 1);
        assert_eq!(violations[0].severity, Severity::Critical);
        assert!(violations[0].message.contains("shell_dangerous"));
    }

    #[test]
    fn test_sudo_critical_violation() {
        let checker = ContentSafetyChecker::with_defaults();
        let ctx = make_context_with_output(serde_json::json!({"command": "sudo apt install"}));
        let violations = checker.check(&ctx);
        assert_eq!(violations.len(), 1);
        assert_eq!(violations[0].severity, Severity::Critical);
    }

    #[test]
    fn test_eval_enforced_violation() {
        let checker = ContentSafetyChecker::with_defaults();
        let ctx = make_context_with_output(serde_json::json!({"code": "eval('malicious')"}));
        let violations = checker.check(&ctx);
        assert_eq!(violations.len(), 1);
        assert_eq!(violations[0].severity, Severity::Enforced);
        assert!(violations[0].message.contains("code_injection"));
    }

    #[test]
    fn test_drop_table_enforced_violation() {
        let checker = ContentSafetyChecker::with_defaults();
        let ctx = make_context_with_output(serde_json::json!({"sql": "DROP TABLE users"}));
        let violations = checker.check(&ctx);
        assert_eq!(violations.len(), 1);
        assert_eq!(violations[0].severity, Severity::Enforced);
    }

    #[test]
    fn test_multiple_patterns_multiple_violations() {
        let checker = ContentSafetyChecker::with_defaults();
        let ctx = make_context_with_output(serde_json::json!({
            "commands": "sudo rm -rf / && eval('bad')"
        }));
        let violations = checker.check(&ctx);
        // shell_dangerous matches "rm -rf" and "sudo", code_injection matches "eval("
        assert!(violations.len() >= 2);
    }

    #[test]
    fn test_custom_pattern() {
        let config = ContentSafetyConfig {
            patterns: vec![ForbiddenPattern {
                name: "custom".into(),
                pattern: r"FORBIDDEN_WORD".into(),
                severity: Severity::Advisory,
            }],
        };
        let checker = ContentSafetyChecker::new(config);
        let ctx = make_context_with_output(serde_json::json!({"text": "contains FORBIDDEN_WORD here"}));
        let violations = checker.check(&ctx);
        assert_eq!(violations.len(), 1);
        assert_eq!(violations[0].severity, Severity::Advisory);
    }
}
```

- [ ] **Step 2: Run tests and commit**

```bash
source "$HOME/.cargo/env" && cargo test -p siss-behavioral-firewall -- checker::content
git add crates/siss-behavioral-firewall/src/checker/content.rs
git commit -m "feat: implement ContentSafetyChecker with configurable forbidden patterns"
```

---

### Task 6: Implement Verdict Rendering

**Files:**
- Create: `crates/siss-behavioral-firewall/src/verdict.rs`

- [ ] **Step 1: Implement verdict logic with tests**

Create `crates/siss-behavioral-firewall/src/verdict.rs`:

```rust
use siss_graph_core::node::governance::Severity;

use crate::types::{Verdict, Violation};

/// Determine the verdict from a list of violations.
/// No violations → Clear
/// Worst severity advisory → Clear (logged only)
/// Worst severity enforced → Blocked
/// Worst severity critical → CriticalBlocked
pub fn render_verdict(violations: &[Violation]) -> Verdict {
    if violations.is_empty() {
        return Verdict::Clear;
    }

    let worst = violations
        .iter()
        .map(|v| severity_rank(v.severity))
        .max()
        .unwrap_or(0);

    match worst {
        0 => Verdict::Clear,       // advisory only
        1 => Verdict::Blocked,     // enforced
        2 => Verdict::CriticalBlocked, // critical
        _ => Verdict::Clear,
    }
}

fn severity_rank(s: Severity) -> u8 {
    match s {
        Severity::Advisory => 0,
        Severity::Enforced => 1,
        Severity::Critical => 2,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_violation(severity: Severity) -> Violation {
        Violation {
            checker: "test".into(),
            severity,
            message: "test".into(),
        }
    }

    #[test]
    fn test_no_violations_clear() {
        assert_eq!(render_verdict(&[]), Verdict::Clear);
    }

    #[test]
    fn test_advisory_only_clear() {
        let v = vec![make_violation(Severity::Advisory)];
        assert_eq!(render_verdict(&v), Verdict::Clear);
    }

    #[test]
    fn test_enforced_blocked() {
        let v = vec![make_violation(Severity::Enforced)];
        assert_eq!(render_verdict(&v), Verdict::Blocked);
    }

    #[test]
    fn test_critical_critical_blocked() {
        let v = vec![make_violation(Severity::Critical)];
        assert_eq!(render_verdict(&v), Verdict::CriticalBlocked);
    }

    #[test]
    fn test_mixed_worst_wins() {
        let v = vec![
            make_violation(Severity::Advisory),
            make_violation(Severity::Enforced),
            make_violation(Severity::Critical),
        ];
        assert_eq!(render_verdict(&v), Verdict::CriticalBlocked);
    }

    #[test]
    fn test_advisory_and_enforced_blocked() {
        let v = vec![
            make_violation(Severity::Advisory),
            make_violation(Severity::Enforced),
        ];
        assert_eq!(render_verdict(&v), Verdict::Blocked);
    }
}
```

- [ ] **Step 2: Run tests and commit**

```bash
source "$HOME/.cargo/env" && cargo test -p siss-behavioral-firewall -- verdict
git add crates/siss-behavioral-firewall/src/verdict.rs
git commit -m "feat: implement verdict rendering with severity-based logic"
```

---

### Task 7: Implement Pipeline (validate, inspect, act, orchestrator)

**Files:**
- Create: `crates/siss-behavioral-firewall/src/pipeline/mod.rs`
- Create: `crates/siss-behavioral-firewall/src/pipeline/validate.rs`
- Create: `crates/siss-behavioral-firewall/src/pipeline/inspect.rs`
- Create: `crates/siss-behavioral-firewall/src/pipeline/act.rs`

- [ ] **Step 1: Implement validate step**

Create `crates/siss-behavioral-firewall/src/pipeline/validate.rs`:

```rust
use sqlx::PgPool;
use uuid::Uuid;

use siss_graph_core::node::execution::TaskStatus;

use crate::types::FirewallError;

/// Validate the task exists, is in executing status, and matches the tenant.
/// Transitions the task to guarding.
pub async fn validate_and_transition(
    pool: &PgPool,
    task_id: Uuid,
    tenant_id: Uuid,
) -> Result<(), FirewallError> {
    let task_row = siss_graph_db::repo::node_repo::fetch_task(pool, task_id)
        .await?
        .ok_or(FirewallError::TaskNotFound { task_id })?;

    let (_id, task_tenant, status, _intent) = task_row;

    if status != "executing" {
        return Err(FirewallError::InvalidTaskStatus {
            current: parse_task_status(&status),
            expected: TaskStatus::Executing,
        });
    }

    if task_tenant != tenant_id {
        return Err(FirewallError::TenantViolation {
            source_tenant: task_tenant,
            target_tenant: tenant_id,
        });
    }

    // Transition: executing → guarding
    siss_graph_db::repo::node_repo::update_task_status(pool, task_id, "guarding")
        .await?;

    Ok(())
}

fn parse_task_status(s: &str) -> TaskStatus {
    match s {
        "pending" => TaskStatus::Pending,
        "authorized" => TaskStatus::Authorized,
        "routing" => TaskStatus::Routing,
        "executing" => TaskStatus::Executing,
        "guarding" => TaskStatus::Guarding,
        "crystallizing" => TaskStatus::Crystallizing,
        "completed" => TaskStatus::Completed,
        "failed" => TaskStatus::Failed,
        _ => TaskStatus::Failed,
    }
}
```

- [ ] **Step 2: Implement inspect step**

Create `crates/siss-behavioral-firewall/src/pipeline/inspect.rs`:

```rust
use sqlx::PgPool;
use uuid::Uuid;

use crate::checker::FirewallChecker;
use crate::context::InspectionContext;
use crate::types::{FirewallError, Violation};

/// Build InspectionContext and run all checkers.
pub async fn run_checkers(
    pool: &PgPool,
    task_id: Uuid,
    intent_mandate_id: Uuid,
    token_cost: i64,
    output: serde_json::Value,
    authorized_tools: Vec<Uuid>,
    checkers: &[&dyn FirewallChecker],
) -> Result<Vec<Violation>, FirewallError> {
    // Fetch mandate to get budget_remaining
    let mandate_row = siss_graph_db::repo::node_repo::fetch_intent_mandate(pool, intent_mandate_id)
        .await?
        .ok_or(FirewallError::TaskNotFound { task_id: intent_mandate_id })?;

    let (_id, _tenant, budget_limit, budget_spent, _risk_class, _allowed_tools) = mandate_row;
    let budget_remaining = budget_limit - budget_spent;

    let context = InspectionContext {
        task_id,
        token_cost,
        output,
        authorized_tools,
        budget_remaining,
    };

    // Run all checkers, collect all violations
    let mut all_violations = Vec::new();
    for checker in checkers {
        let violations = checker.check(&context);
        all_violations.extend(violations);
    }

    Ok(all_violations)
}
```

- [ ] **Step 3: Implement act step**

Create `crates/siss-behavioral-firewall/src/pipeline/act.rs`:

```rust
use sqlx::PgPool;
use uuid::Uuid;

use crate::types::{FirewallError, Verdict, Violation};

/// Act on the verdict: log violations, freeze persona if critical, fail task if critical.
pub async fn act_on_verdict(
    pool: &PgPool,
    task_id: Uuid,
    persona_id: Uuid,
    tenant_id: Uuid,
    verdict: &Verdict,
    violations: &[Violation],
) -> Result<(), FirewallError> {
    // Log all violations as VIOLATED_BY edges (using edge_repo directly)
    for violation in violations {
        let _ = siss_graph_db::repo::edge_repo::insert_edge(
            pool,
            task_id, // source: the task that violated
            task_id, // target: self-referential for task-level violations
            "violated_by",
            tenant_id,
            serde_json::json!({
                "checker": violation.checker,
                "severity": format!("{:?}", violation.severity),
                "message": violation.message,
            }),
        )
        .await;
    }

    match verdict {
        Verdict::Clear => {
            // No action needed
        }
        Verdict::Blocked => {
            // Task stays in guarding — caller can retry or escalate
        }
        Verdict::CriticalBlocked => {
            // Freeze persona
            let _ = siss_graph_db::repo::node_repo::freeze_persona(pool, persona_id).await;
            // Transition task to failed
            let _ = siss_graph_db::repo::node_repo::update_task_status(pool, task_id, "failed").await;
        }
    }

    Ok(())
}
```

- [ ] **Step 4: Implement the orchestrator**

Create `crates/siss-behavioral-firewall/src/pipeline/mod.rs`:

```rust
pub mod validate;
pub mod inspect;
pub mod act;

use sqlx::PgPool;

use siss_graph_core::node::NodeId;

use crate::checker::FirewallChecker;
use crate::types::{FirewallError, InspectionRequest, InspectionResult};
use crate::verdict::render_verdict;

/// The sole entry point for output inspection.
/// Validates → transitions to guarding → runs checkers → renders verdict → acts.
pub async fn inspect_output(
    pool: &PgPool,
    checkers: &[&dyn FirewallChecker],
    request: &InspectionRequest,
) -> Result<InspectionResult, FirewallError> {
    let task_id = request.task_id.0;
    let persona_id = request.persona_id.0;
    let intent_mandate_id = request.intent_mandate_id.0;
    let tenant_id = request.tenant_id.0;

    // Step 1+2: Validate and transition to guarding
    validate::validate_and_transition(pool, task_id, tenant_id).await?;

    // Steps 3+4: Build context and run checkers
    let violations = inspect::run_checkers(
        pool,
        task_id,
        intent_mandate_id,
        request.token_cost,
        request.execution_output.clone(),
        request.authorized_tools.clone(),
        checkers,
    )
    .await?;

    // Step 5: Render verdict
    let verdict = render_verdict(&violations);

    // Step 6: Act on verdict
    act::act_on_verdict(pool, task_id, persona_id, tenant_id, &verdict, &violations).await?;

    Ok(InspectionResult {
        task_id: NodeId(task_id),
        verdict,
        violations,
    })
}
```

- [ ] **Step 5: Verify compilation**

```bash
source "$HOME/.cargo/env" && cargo check
```

- [ ] **Step 6: Commit**

```bash
git add crates/siss-behavioral-firewall/src/pipeline/
git commit -m "feat: implement Firewall inspection pipeline (validate, inspect, act, orchestrator)"
```

---

### Task 8: Final Workspace Validation

**Files:** None (validation only)

- [ ] **Step 1: Run complete test suite**

```bash
source "$HOME/.cargo/env" && cargo test --workspace
```

Expected: All tests pass across all six crates.

- [ ] **Step 2: Run clippy**

```bash
source "$HOME/.cargo/env" && cargo clippy --workspace -- -D warnings
```

Expected: No warnings.

- [ ] **Step 3: Fix any issues and commit**

```bash
git add -A
git commit -m "chore: fix clippy warnings from Behavioral Firewall validation"
```

- [ ] **Step 4: Verify success criteria**

1. **Clean output → Clear:** verdict.rs tests
2. **Over budget → CriticalBlocked:** budget.rs tests
3. **Unauthorized tool UUID → Blocked:** tools.rs tests
4. **rm -rf → CriticalBlocked:** content.rs tests
5. **eval( → Blocked:** content.rs tests
6. **Multiple violations collected:** content.rs test_multiple_patterns
7. **Advisory logged but Clear:** verdict.rs test_advisory_only_clear
8. **CriticalBlocked freezes Persona + fails Task:** pipeline/act.rs
9. **Blocked doesn't freeze or fail:** pipeline/act.rs
10. **Wrong status → InvalidTaskStatus:** pipeline/validate.rs
11. **Cross-tenant → TenantViolation:** pipeline/validate.rs
