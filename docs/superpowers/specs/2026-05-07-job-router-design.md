# Job Router Design — Step C

**Date:** 2026-05-07
**Status:** Approved
**Scope:** Step C — Task routing and dispatch for the SISS value loop
**Depends on:** Step A (Knowledge Graph Schema), Step B (Governance Gatekeeper)

---

## 1. Overview

The Job Router receives Tasks that have been authorized by the Governance Gatekeeper (status = `authorized`) and dispatches them for execution. It evaluates the task's complexity to determine the optimal hardware target, then delegates execution to a pluggable `Executor` backend.

The Router is a pure dispatcher — it does not interpret execution results. The Behavioral Firewall (Step E) handles output inspection.

### Position in the Value Loop

```
1. [Sense & Authorize] ← Governance Gatekeeper (Step B) ✅
2. [Orient & Preload]  ← Context Cartography (Step D)
3. [Decide & Execute]  ← JOB ROUTER (this component)
4. [Act & Guard]       ← Behavioral Firewall (Step E)
5. [Learn & Crystallize] ← Feedback Router (Step F)
```

---

## 2. Architecture

A new Rust library crate `siss-job-router` that depends on `siss-graph-core` and `siss-graph-db`. It exposes a single async entry point `route_task` and two pluggable traits: `RoutingStrategy` (decides where to run) and `Executor` (runs the task).

### Crate Dependencies

```
siss-job-router
  ├── siss-graph-core   (node types: Task, ComplexityClass, HardwareTarget, TaskStatus)
  └── siss-graph-db     (PostgreSQL repositories for task fetch/update)
```

### Key Design Principles

1. **Pure dispatcher** — no owned state, no data storage, just routing decisions and execution delegation
2. **Trait-based extensibility** — `RoutingStrategy` and `Executor` are swappable
3. **Mock-first** — `MockExecutor` is the only executor in Step C; real backends (Rapid-MLX, frontier APIs) plug in later
4. **Simple routing** — pure complexity-to-target mapping; load-balancing and budget-awareness are future enhancements

---

## 3. Request/Response Types

### RoutingRequest

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | `NodeId` | The authorized Task to route |
| `persona_id` | `NodeId` | The Persona that owns this task |
| `tenant_id` | `NodeId` | Tenant isolation boundary |

### RoutingResult

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | `NodeId` | The routed Task |
| `hardware_target` | `HardwareTarget` | Where the task was dispatched |
| `execution` | `ExecutionResult` | Output from the executor |

### ExecutionResult

| Field | Type | Description |
|-------|------|-------------|
| `output` | `serde_json::Value` | Opaque JSON output from execution |
| `token_cost` | `i64` | Actual tokens consumed |
| `duration_ms` | `u64` | Execution wall-clock time in milliseconds |

### RouterError

| Variant | Description |
|---------|-------------|
| `TaskNotFound` | Task ID does not exist |
| `InvalidTaskStatus` | Task is not in `authorized` status |
| `TenantViolation` | Cross-tenant operation attempted |
| `ExecutionFailed` | Executor returned an error |
| `DatabaseError` | Database operation failed |

All errors cause the Task to transition to `failed`. There is no soft/hard failure distinction — the Router either succeeds or the task fails.

---

## 4. Routing Strategy

### Trait

```rust
pub trait RoutingStrategy: Send + Sync {
    fn decide(&self, complexity: ComplexityClass) -> HardwareTarget;
}
```

### Default: ComplexityBasedStrategy

| ComplexityClass | HardwareTarget | Rationale |
|-----------------|---------------|-----------|
| Trivial | LocalMlx | Fast, cheap, local GPU handles it |
| Simple | LocalMlx | Same |
| Moderate | LocalMlx | Still within SLM capability |
| Complex | RemoteFrontier | Needs frontier model reasoning |
| Heavy | Hybrid | Split across local + frontier |

This is a pure function with no side effects — easy to test and easy to replace.

---

## 5. Executor Trait

### Trait

```rust
pub trait Executor: Send + Sync {
    async fn execute(&self, context: TaskContext) -> Result<ExecutionResult, ExecutionError>;
}
```

### TaskContext

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | `Uuid` | Task identifier |
| `intent` | `String` | The original request/goal |
| `complexity_class` | `ComplexityClass` | Task complexity |
| `hardware_target` | `HardwareTarget` | Assigned target |
| `tenant_id` | `Uuid` | Tenant isolation |

### ExecutionError

```rust
pub struct ExecutionError {
    pub message: String,
}
```

### Implementations

| Implementation | Description | Use Case |
|---------------|-------------|----------|
| `MockExecutor` | Returns deterministic output: `{"status": "mock_completed", "task_id": "..."}`, token_cost=100, duration_ms=10 | Unit and integration tests |

Real executors (Rapid-MLX for LocalMlx, frontier API client for RemoteFrontier) are built in later steps.

---

## 6. Routing Pipeline

The `route_task` function executes the following steps sequentially.

### Step 1: VALIDATE

- Fetch Task from DB; verify `status == Authorized`
- Fetch task's `complexity_class` and `intent`
- Verify tenant isolation: `task.tenant_id == request.tenant_id`
- On failure: transition Task to `failed`, return RouterError

### Step 2: ROUTE

- Call `strategy.decide(complexity_class)` → `hardware_target`
- Update `task.hardware_target` in DB
- Transition Task: `authorized` → `routing`

### Step 3: EXECUTE

- Build `TaskContext` from task data + routing decision
- Call `executor.execute(context)` → `ExecutionResult`
- On executor failure: transition Task to `failed`, return `ExecutionFailed`
- On success: update `task.token_cost` in DB
- Transition Task: `routing` → `executing`

### Step 4: RETURN

- Return `RoutingResult` containing the hardware target and execution output
- The Task is now in `executing` status, ready for the Behavioral Firewall (Step E)

---

## 7. DB Functions Needed

The Router needs these additional repo functions (some may already exist from Step B):

| Function | Description |
|----------|-------------|
| `update_task_hardware_target(pool, task_id, target)` | Set the hardware_target field |
| `update_task_token_cost(pool, task_id, cost)` | Set the token_cost field |

Functions already available from Steps A/B: `fetch_task`, `update_task_status`.

---

## 8. File Structure

```
crates/
  siss-job-router/
    Cargo.toml
    src/
      lib.rs              # Re-exports
      types.rs            # RoutingRequest, RoutingResult, ExecutionResult, RouterError
      strategy/
        mod.rs            # RoutingStrategy trait
        complexity.rs     # ComplexityBasedStrategy
      executor/
        mod.rs            # Executor trait + ExecutionError + TaskContext
        mock.rs           # MockExecutor
      pipeline/
        mod.rs            # route_task() orchestrator
        validate.rs       # Step 1: validation
        route.rs          # Step 2: routing decision + DB update
        execute.rs        # Step 3: dispatch to executor + DB update
```

---

## 9. Success Criteria

The Job Router is correct when:

1. An authorized Task with `complexity_class = Simple` is routed to `LocalMlx` and transitions to `executing` with an `ExecutionResult`.
2. An authorized Task with `complexity_class = Complex` is routed to `RemoteFrontier`.
3. An authorized Task with `complexity_class = Heavy` is routed to `Hybrid`.
4. A Task not in `authorized` status returns `InvalidTaskStatus` and transitions to `failed`.
5. A cross-tenant request returns `TenantViolation` and the Task transitions to `failed`.
6. An executor failure returns `ExecutionFailed` and the Task transitions to `failed`.
7. The Task's `hardware_target` and `token_cost` fields are correctly updated in the database after routing.
8. The `MockExecutor` returns deterministic output for predictable testing.
9. The `RoutingStrategy` trait can be swapped without changing the pipeline.
