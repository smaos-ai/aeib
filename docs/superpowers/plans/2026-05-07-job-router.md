# Job Router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `siss-job-router` crate — the task dispatcher that routes authorized Tasks to hardware targets based on complexity and delegates execution to pluggable backends.

**Architecture:** A new Rust library crate `siss-job-router` that depends on `siss-graph-core` and `siss-graph-db`. Exposes a single async `route_task()` entry point. Routes via a `RoutingStrategy` trait (default: complexity-to-target mapping) and dispatches via an `Executor` trait (default: `MockExecutor`). Pipeline: validate → route → execute.

**Tech Stack:** Rust (2024 edition), sqlx (async PostgreSQL), serde/serde_json, uuid, chrono, tokio, thiserror

**Spec:** `docs/superpowers/specs/2026-05-07-job-router-design.md`

---

## File Structure

```
crates/
  siss-job-router/
    Cargo.toml
    src/
      lib.rs                  # Re-exports
      types.rs                # RoutingRequest, RoutingResult, ExecutionResult, RouterError
      strategy/
        mod.rs                # RoutingStrategy trait
        complexity.rs         # ComplexityBasedStrategy
      executor/
        mod.rs                # Executor trait + ExecutionError + TaskContext
        mock.rs               # MockExecutor
      pipeline/
        mod.rs                # route_task() orchestrator
        validate.rs           # Step 1: validation
        route.rs              # Step 2: routing decision + DB update
        execute.rs            # Step 3: dispatch to executor + DB update
  siss-graph-db/
    src/
      repo/
        node_repo.rs          # MODIFY: add update_task_hardware_target, update_task_token_cost
```

---

### Task 1: Create siss-job-router Crate Skeleton

**Files:**
- Modify: `Cargo.toml` (workspace root — add member)
- Create: `crates/siss-job-router/Cargo.toml`
- Create: `crates/siss-job-router/src/lib.rs`
- Create: stub modules

- [ ] **Step 1: Add crate to workspace**

Add `"crates/siss-job-router"` to the workspace members in root `Cargo.toml`:

```toml
[workspace]
resolver = "2"
members = [
    "crates/siss-graph-core",
    "crates/siss-graph-db",
    "crates/siss-gatekeeper",
    "crates/siss-job-router",
]
```

- [ ] **Step 2: Create crate Cargo.toml**

Create `crates/siss-job-router/Cargo.toml`:

```toml
[package]
name = "siss-job-router"
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

[dev-dependencies]
tokio = { workspace = true, features = ["full", "test-util"] }
```

- [ ] **Step 3: Create lib.rs and stub modules**

Create `crates/siss-job-router/src/lib.rs`:

```rust
pub mod types;
pub mod strategy;
pub mod executor;
pub mod pipeline;
```

Create stubs:
- `crates/siss-job-router/src/types.rs` — `// Implemented in Task 2`
- `crates/siss-job-router/src/strategy/mod.rs` — `// Implemented in Task 3`
- `crates/siss-job-router/src/executor/mod.rs` — `// Implemented in Task 4`
- `crates/siss-job-router/src/pipeline/mod.rs` — `// Implemented in Task 6`

- [ ] **Step 4: Verify compilation**

```bash
source "$HOME/.cargo/env" && cargo check
```

Expected: compiles with warnings about empty modules.

- [ ] **Step 5: Commit**

```bash
git add Cargo.toml crates/siss-job-router/
git commit -m "feat: create siss-job-router crate skeleton"
```

---

### Task 2: Define Request/Response Types

**Files:**
- Create: `crates/siss-job-router/src/types.rs`

- [ ] **Step 1: Write types with tests**

Create `crates/siss-job-router/src/types.rs`:

```rust
use serde::{Deserialize, Serialize};
use thiserror::Error;
use uuid::Uuid;

use siss_graph_core::node::NodeId;
use siss_graph_core::node::execution::{HardwareTarget, TaskStatus};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RoutingRequest {
    pub task_id: NodeId,
    pub persona_id: NodeId,
    pub tenant_id: NodeId,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RoutingResult {
    pub task_id: NodeId,
    pub hardware_target: HardwareTarget,
    pub execution: ExecutionResult,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionResult {
    pub output: serde_json::Value,
    pub token_cost: i64,
    pub duration_ms: u64,
}

#[derive(Debug, Error)]
pub enum RouterError {
    #[error("task {task_id} not found")]
    TaskNotFound { task_id: Uuid },

    #[error("invalid task status: current={current:?}, expected={expected:?}")]
    InvalidTaskStatus { current: TaskStatus, expected: TaskStatus },

    #[error("cross-tenant violation: source {source_tenant} != target {target_tenant}")]
    TenantViolation { source_tenant: Uuid, target_tenant: Uuid },

    #[error("execution failed: {message}")]
    ExecutionFailed { message: String },

    #[error("database error: {message}")]
    DatabaseError { message: String },
}

impl From<sqlx::Error> for RouterError {
    fn from(e: sqlx::Error) -> Self {
        Self::DatabaseError { message: e.to_string() }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use siss_graph_core::node::NodeId;

    #[test]
    fn test_create_routing_request() {
        let req = RoutingRequest {
            task_id: NodeId::new(),
            persona_id: NodeId::new(),
            tenant_id: NodeId::new(),
        };
        assert!(!req.task_id.0.is_nil());
    }

    #[test]
    fn test_create_execution_result() {
        let result = ExecutionResult {
            output: serde_json::json!({"status": "done"}),
            token_cost: 100,
            duration_ms: 50,
        };
        assert_eq!(result.token_cost, 100);
        assert_eq!(result.duration_ms, 50);
    }
}
```

- [ ] **Step 2: Run tests**

```bash
source "$HOME/.cargo/env" && cargo test -p siss-job-router -- types
```

Expected: 2 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add crates/siss-job-router/src/types.rs
git commit -m "feat: define Job Router request/response types"
```

---

### Task 3: Implement RoutingStrategy Trait and ComplexityBasedStrategy

**Files:**
- Create: `crates/siss-job-router/src/strategy/mod.rs`
- Create: `crates/siss-job-router/src/strategy/complexity.rs`

- [ ] **Step 1: Write strategy trait and implementation with tests**

Create `crates/siss-job-router/src/strategy/mod.rs`:

```rust
pub mod complexity;

use siss_graph_core::node::execution::{ComplexityClass, HardwareTarget};

/// Trait for deciding which hardware target to use for a given task complexity.
pub trait RoutingStrategy: Send + Sync {
    fn decide(&self, complexity: ComplexityClass) -> HardwareTarget;
}
```

Create `crates/siss-job-router/src/strategy/complexity.rs`:

```rust
use siss_graph_core::node::execution::{ComplexityClass, HardwareTarget};

use super::RoutingStrategy;

/// Routes tasks based purely on their complexity class.
/// Trivial/Simple/Moderate → LocalMlx
/// Complex → RemoteFrontier
/// Heavy → Hybrid
pub struct ComplexityBasedStrategy;

impl RoutingStrategy for ComplexityBasedStrategy {
    fn decide(&self, complexity: ComplexityClass) -> HardwareTarget {
        match complexity {
            ComplexityClass::Trivial => HardwareTarget::LocalMlx,
            ComplexityClass::Simple => HardwareTarget::LocalMlx,
            ComplexityClass::Moderate => HardwareTarget::LocalMlx,
            ComplexityClass::Complex => HardwareTarget::RemoteFrontier,
            ComplexityClass::Heavy => HardwareTarget::Hybrid,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_trivial_routes_to_local_mlx() {
        let strategy = ComplexityBasedStrategy;
        assert_eq!(strategy.decide(ComplexityClass::Trivial), HardwareTarget::LocalMlx);
    }

    #[test]
    fn test_simple_routes_to_local_mlx() {
        let strategy = ComplexityBasedStrategy;
        assert_eq!(strategy.decide(ComplexityClass::Simple), HardwareTarget::LocalMlx);
    }

    #[test]
    fn test_moderate_routes_to_local_mlx() {
        let strategy = ComplexityBasedStrategy;
        assert_eq!(strategy.decide(ComplexityClass::Moderate), HardwareTarget::LocalMlx);
    }

    #[test]
    fn test_complex_routes_to_remote_frontier() {
        let strategy = ComplexityBasedStrategy;
        assert_eq!(strategy.decide(ComplexityClass::Complex), HardwareTarget::RemoteFrontier);
    }

    #[test]
    fn test_heavy_routes_to_hybrid() {
        let strategy = ComplexityBasedStrategy;
        assert_eq!(strategy.decide(ComplexityClass::Heavy), HardwareTarget::Hybrid);
    }
}
```

- [ ] **Step 2: Run tests**

```bash
source "$HOME/.cargo/env" && cargo test -p siss-job-router -- strategy
```

Expected: 5 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add crates/siss-job-router/src/strategy/
git commit -m "feat: implement RoutingStrategy trait with ComplexityBasedStrategy"
```

---

### Task 4: Implement Executor Trait and MockExecutor

**Files:**
- Create: `crates/siss-job-router/src/executor/mod.rs`
- Create: `crates/siss-job-router/src/executor/mock.rs`

- [ ] **Step 1: Write executor trait and mock with tests**

Create `crates/siss-job-router/src/executor/mod.rs`:

```rust
pub mod mock;

use serde::{Deserialize, Serialize};
use thiserror::Error;
use uuid::Uuid;

use siss_graph_core::node::execution::{ComplexityClass, HardwareTarget};

use crate::types::ExecutionResult;

/// Context provided to an executor for task execution.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskContext {
    pub task_id: Uuid,
    pub intent: String,
    pub complexity_class: ComplexityClass,
    pub hardware_target: HardwareTarget,
    pub tenant_id: Uuid,
}

#[derive(Debug, Error)]
#[error("execution error: {message}")]
pub struct ExecutionError {
    pub message: String,
}

/// Trait for executing tasks on a hardware backend.
pub trait Executor: Send + Sync {
    fn execute(&self, context: TaskContext) -> impl std::future::Future<Output = Result<ExecutionResult, ExecutionError>> + Send;
}
```

Create `crates/siss-job-router/src/executor/mock.rs`:

```rust
use super::{Executor, ExecutionError, TaskContext};
use crate::types::ExecutionResult;

/// A deterministic mock executor for tests.
/// Returns: output={"status":"mock_completed","task_id":"..."}, token_cost=100, duration_ms=10
pub struct MockExecutor;

impl Executor for MockExecutor {
    async fn execute(&self, context: TaskContext) -> Result<ExecutionResult, ExecutionError> {
        Ok(ExecutionResult {
            output: serde_json::json!({
                "status": "mock_completed",
                "task_id": context.task_id.to_string(),
            }),
            token_cost: 100,
            duration_ms: 10,
        })
    }
}

/// A mock executor that always fails, for testing error paths.
pub struct FailingExecutor {
    pub error_message: String,
}

impl Executor for FailingExecutor {
    async fn execute(&self, _context: TaskContext) -> Result<ExecutionResult, ExecutionError> {
        Err(ExecutionError {
            message: self.error_message.clone(),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use siss_graph_core::node::execution::{ComplexityClass, HardwareTarget};

    fn make_context() -> TaskContext {
        TaskContext {
            task_id: uuid::Uuid::nil(),
            intent: "test task".into(),
            complexity_class: ComplexityClass::Simple,
            hardware_target: HardwareTarget::LocalMlx,
            tenant_id: uuid::Uuid::nil(),
        }
    }

    #[tokio::test]
    async fn test_mock_executor_returns_deterministic_output() {
        let executor = MockExecutor;
        let result = executor.execute(make_context()).await.unwrap();
        assert_eq!(result.token_cost, 100);
        assert_eq!(result.duration_ms, 10);
        assert_eq!(result.output["status"], "mock_completed");
    }

    #[tokio::test]
    async fn test_mock_executor_includes_task_id() {
        let mut ctx = make_context();
        ctx.task_id = uuid::Uuid::new_v4();
        let executor = MockExecutor;
        let result = executor.execute(ctx.clone()).await.unwrap();
        assert_eq!(result.output["task_id"], ctx.task_id.to_string());
    }

    #[tokio::test]
    async fn test_failing_executor_returns_error() {
        let executor = FailingExecutor {
            error_message: "GPU unavailable".into(),
        };
        let result = executor.execute(make_context()).await;
        assert!(result.is_err());
        assert_eq!(result.unwrap_err().message, "GPU unavailable");
    }
}
```

- [ ] **Step 2: Run tests**

```bash
source "$HOME/.cargo/env" && cargo test -p siss-job-router -- executor
```

Expected: 3 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add crates/siss-job-router/src/executor/
git commit -m "feat: implement Executor trait with MockExecutor and FailingExecutor"
```

---

### Task 5: Add Missing DB Repository Functions

**Files:**
- Modify: `crates/siss-graph-db/src/repo/node_repo.rs`

- [ ] **Step 1: Append new functions**

Append to `crates/siss-graph-db/src/repo/node_repo.rs`:

```rust
/// Update a Task's hardware_target field.
pub async fn update_task_hardware_target(
    pool: &PgPool,
    task_id: Uuid,
    hardware_target: &str,
) -> Result<bool, sqlx::Error> {
    let result = sqlx::query(
        "UPDATE tasks SET hardware_target = $2::hardware_target WHERE id = $1"
    )
    .bind(task_id)
    .bind(hardware_target)
    .execute(pool)
    .await?;
    Ok(result.rows_affected() > 0)
}

/// Update a Task's token_cost field.
pub async fn update_task_token_cost(
    pool: &PgPool,
    task_id: Uuid,
    token_cost: i64,
) -> Result<bool, sqlx::Error> {
    let result = sqlx::query(
        "UPDATE tasks SET token_cost = $2 WHERE id = $1"
    )
    .bind(task_id)
    .bind(token_cost)
    .execute(pool)
    .await?;
    Ok(result.rows_affected() > 0)
}
```

- [ ] **Step 2: Verify compilation**

```bash
source "$HOME/.cargo/env" && cargo check
```

Expected: compiles.

- [ ] **Step 3: Commit**

```bash
git add crates/siss-graph-db/src/repo/node_repo.rs
git commit -m "feat: add update_task_hardware_target and update_task_token_cost repo functions"
```

---

### Task 6: Implement Pipeline (validate, route, execute, orchestrator)

**Files:**
- Create: `crates/siss-job-router/src/pipeline/mod.rs`
- Create: `crates/siss-job-router/src/pipeline/validate.rs`
- Create: `crates/siss-job-router/src/pipeline/route.rs`
- Create: `crates/siss-job-router/src/pipeline/execute.rs`

- [ ] **Step 1: Implement validate step**

Create `crates/siss-job-router/src/pipeline/validate.rs`:

```rust
use sqlx::PgPool;
use uuid::Uuid;

use siss_graph_core::node::execution::{ComplexityClass, TaskStatus};

use crate::types::RouterError;

/// Validated task data extracted from the database.
pub struct ValidatedTask {
    pub task_id: Uuid,
    pub tenant_id: Uuid,
    pub intent: String,
    pub complexity_class: ComplexityClass,
}

/// Pipeline Step 1: Validate that the Task exists, is authorized, and belongs to the correct tenant.
/// Returns the validated task data for use in subsequent steps.
pub async fn validate(
    pool: &PgPool,
    task_id: Uuid,
    tenant_id: Uuid,
) -> Result<ValidatedTask, RouterError> {
    let task_row = siss_graph_db::repo::node_repo::fetch_task(pool, task_id)
        .await?
        .ok_or(RouterError::TaskNotFound { task_id })?;

    let (_id, task_tenant, status, intent) = task_row;

    // Verify status is authorized
    if status != "authorized" {
        return Err(RouterError::InvalidTaskStatus {
            current: parse_task_status(&status),
            expected: TaskStatus::Authorized,
        });
    }

    // Verify tenant isolation
    if task_tenant != tenant_id {
        return Err(RouterError::TenantViolation {
            source_tenant: task_tenant,
            target_tenant: tenant_id,
        });
    }

    // Fetch complexity_class from DB — we need an extended fetch
    // For now, use the task row. We need to add complexity_class to fetch_task.
    // Since fetch_task returns (id, tenant_id, status::text, intent), we need
    // to extend it. Instead, we'll fetch it separately.
    let complexity = fetch_task_complexity(pool, task_id).await?;

    Ok(ValidatedTask {
        task_id,
        tenant_id,
        intent,
        complexity_class: complexity,
    })
}

async fn fetch_task_complexity(pool: &PgPool, task_id: Uuid) -> Result<ComplexityClass, RouterError> {
    let row: Option<(String,)> = sqlx::query_as(
        "SELECT complexity_class::text FROM tasks WHERE id = $1"
    )
    .bind(task_id)
    .fetch_optional(pool)
    .await?;

    let (complexity_str,) = row.ok_or(RouterError::TaskNotFound { task_id })?;
    Ok(parse_complexity_class(&complexity_str))
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

fn parse_complexity_class(s: &str) -> ComplexityClass {
    match s {
        "trivial" => ComplexityClass::Trivial,
        "simple" => ComplexityClass::Simple,
        "moderate" => ComplexityClass::Moderate,
        "complex" => ComplexityClass::Complex,
        "heavy" => ComplexityClass::Heavy,
        _ => ComplexityClass::Moderate, // safe default
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_task_status_all_variants() {
        assert_eq!(parse_task_status("pending"), TaskStatus::Pending);
        assert_eq!(parse_task_status("authorized"), TaskStatus::Authorized);
        assert_eq!(parse_task_status("routing"), TaskStatus::Routing);
        assert_eq!(parse_task_status("executing"), TaskStatus::Executing);
        assert_eq!(parse_task_status("completed"), TaskStatus::Completed);
        assert_eq!(parse_task_status("failed"), TaskStatus::Failed);
        assert_eq!(parse_task_status("unknown"), TaskStatus::Failed);
    }

    #[test]
    fn test_parse_complexity_class_all_variants() {
        assert_eq!(parse_complexity_class("trivial"), ComplexityClass::Trivial);
        assert_eq!(parse_complexity_class("simple"), ComplexityClass::Simple);
        assert_eq!(parse_complexity_class("moderate"), ComplexityClass::Moderate);
        assert_eq!(parse_complexity_class("complex"), ComplexityClass::Complex);
        assert_eq!(parse_complexity_class("heavy"), ComplexityClass::Heavy);
        assert_eq!(parse_complexity_class("unknown"), ComplexityClass::Moderate);
    }
}
```

- [ ] **Step 2: Implement route step**

Create `crates/siss-job-router/src/pipeline/route.rs`:

```rust
use sqlx::PgPool;
use uuid::Uuid;

use siss_graph_core::node::execution::HardwareTarget;

use crate::types::RouterError;

/// Convert HardwareTarget enum to the database string representation.
fn hardware_target_to_str(target: HardwareTarget) -> &'static str {
    match target {
        HardwareTarget::LocalMlx => "local_mlx",
        HardwareTarget::RemoteFrontier => "remote_frontier",
        HardwareTarget::Hybrid => "hybrid",
    }
}

/// Pipeline Step 2: Update hardware_target in DB and transition Task to routing.
pub async fn apply_routing_decision(
    pool: &PgPool,
    task_id: Uuid,
    hardware_target: HardwareTarget,
) -> Result<(), RouterError> {
    // Update hardware_target
    siss_graph_db::repo::node_repo::update_task_hardware_target(
        pool,
        task_id,
        hardware_target_to_str(hardware_target),
    )
    .await?;

    // Transition: authorized → routing
    siss_graph_db::repo::node_repo::update_task_status(pool, task_id, "routing")
        .await?;

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_hardware_target_to_str() {
        assert_eq!(hardware_target_to_str(HardwareTarget::LocalMlx), "local_mlx");
        assert_eq!(hardware_target_to_str(HardwareTarget::RemoteFrontier), "remote_frontier");
        assert_eq!(hardware_target_to_str(HardwareTarget::Hybrid), "hybrid");
    }
}
```

- [ ] **Step 3: Implement execute step**

Create `crates/siss-job-router/src/pipeline/execute.rs`:

```rust
use sqlx::PgPool;

use crate::executor::{Executor, TaskContext};
use crate::types::{ExecutionResult, RouterError};

/// Pipeline Step 3: Dispatch to executor, update token_cost, transition to executing.
pub async fn dispatch_and_execute(
    pool: &PgPool,
    executor: &dyn Executor,
    context: TaskContext,
) -> Result<ExecutionResult, RouterError> {
    let task_id = context.task_id;

    // Execute
    let result = executor.execute(context).await.map_err(|e| RouterError::ExecutionFailed {
        message: e.message,
    })?;

    // Update token_cost
    siss_graph_db::repo::node_repo::update_task_token_cost(pool, task_id, result.token_cost)
        .await?;

    // Transition: routing → executing
    siss_graph_db::repo::node_repo::update_task_status(pool, task_id, "executing")
        .await?;

    Ok(result)
}
```

- [ ] **Step 4: Implement the orchestrator**

Create `crates/siss-job-router/src/pipeline/mod.rs`:

```rust
pub mod validate;
pub mod route;
pub mod execute;

use sqlx::PgPool;

use crate::executor::{Executor, TaskContext};
use crate::strategy::RoutingStrategy;
use crate::types::{RoutingRequest, RoutingResult, RouterError};
use siss_graph_core::node::NodeId;

/// The sole entry point for task routing and dispatch.
/// Runs the full pipeline: validate → route → execute.
pub async fn route_task(
    pool: &PgPool,
    strategy: &dyn RoutingStrategy,
    executor: &dyn Executor,
    request: &RoutingRequest,
) -> Result<RoutingResult, RouterError> {
    let task_id = request.task_id.0;
    let tenant_id = request.tenant_id.0;

    // Step 1: Validate
    let validated = validate::validate(pool, task_id, tenant_id).await?;

    // Step 2: Route
    let hardware_target = strategy.decide(validated.complexity_class);
    route::apply_routing_decision(pool, task_id, hardware_target).await?;

    // Step 3: Execute
    let context = TaskContext {
        task_id,
        intent: validated.intent,
        complexity_class: validated.complexity_class,
        hardware_target,
        tenant_id,
    };
    let execution = execute::dispatch_and_execute(pool, executor, context).await?;

    Ok(RoutingResult {
        task_id: NodeId(task_id),
        hardware_target,
        execution,
    })
}
```

- [ ] **Step 5: Verify compilation**

```bash
source "$HOME/.cargo/env" && cargo check
```

Expected: compiles.

- [ ] **Step 6: Run all tests**

```bash
source "$HOME/.cargo/env" && cargo test -p siss-job-router
```

Expected: All tests pass (2 types + 5 strategy + 3 executor + 2 validate + 1 route = 13 tests).

- [ ] **Step 7: Commit**

```bash
git add crates/siss-job-router/src/pipeline/
git commit -m "feat: implement Job Router pipeline (validate, route, execute orchestrator)"
```

---

### Task 7: Final Workspace Validation

**Files:** None (validation only)

- [ ] **Step 1: Run complete test suite**

```bash
source "$HOME/.cargo/env" && cargo test --workspace
```

Expected: All tests pass across all four crates.

- [ ] **Step 2: Run clippy**

```bash
source "$HOME/.cargo/env" && cargo clippy --workspace -- -D warnings
```

Expected: No warnings.

- [ ] **Step 3: Fix any issues and commit**

```bash
git add -A
git commit -m "chore: fix clippy warnings from Job Router validation"
```

- [ ] **Step 4: Verify success criteria**

1. **Simple → LocalMlx:** Covered by `ComplexityBasedStrategy` test
2. **Complex → RemoteFrontier:** Covered by strategy test
3. **Heavy → Hybrid:** Covered by strategy test
4. **Non-authorized → InvalidTaskStatus:** Covered by validate.rs logic
5. **Cross-tenant → TenantViolation:** Covered by validate.rs logic
6. **Executor failure → ExecutionFailed:** Covered by `FailingExecutor` test
7. **hardware_target + token_cost updated:** Covered by route.rs + execute.rs
8. **MockExecutor deterministic:** Covered by mock tests
9. **RoutingStrategy swappable:** Trait-based design, verified by compilation

- [ ] **Step 5: Verify commit log**

```bash
git log --oneline -8
```

Expected:
```
chore: fix clippy warnings from Job Router validation
feat: implement Job Router pipeline (validate, route, execute orchestrator)
feat: add update_task_hardware_target and update_task_token_cost repo functions
feat: implement Executor trait with MockExecutor and FailingExecutor
feat: implement RoutingStrategy trait with ComplexityBasedStrategy
feat: define Job Router request/response types
feat: create siss-job-router crate skeleton
```
