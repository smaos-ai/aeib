# Agent Shell Design — Phase 1

**Date:** 2026-05-07
**Status:** Approved
**Scope:** Core AgentSession runtime with deterministic lifecycle hooks
**Depends on:** Steps A-F (all Cognitive Plane crates)

---

## 1. Overview

The `siss-agent-shell` is the constitutional runtime — the membrane between the Operator Plane (AoE) and the Cognitive Plane (SISS). It wires all 5 pipeline crates into a single `AgentSession` API with deterministic lifecycle hooks at every safety-critical boundary.

This is Phase 1: the core session orchestrator. Phase 2 (AG-UI streaming) and Phase 3 (A2A agent cards) layer on top.

---

## 2. Architecture

A new Rust library crate `siss-agent-shell` that depends on all Cognitive Plane crates. It exposes `AgentSession` with three methods: `start()`, `submit_intent()`, `close()`.

### Crate Dependencies

```
siss-agent-shell
  ├── siss-graph-core
  ├── siss-graph-db
  ├── siss-gatekeeper
  ├── siss-job-router
  ├── siss-context-cartography
  ├── siss-behavioral-firewall
  └── siss-feedback-router
```

### Key Design Principles

1. **Constitutional runtime** — not a wrapper, a governed lifecycle manager
2. **Deterministic hooks** — 6 hook points, first Deny wins, all hooks run in order
3. **Single wiring point** — the shell is the only place crates connect to each other
4. **Session-scoped** — holds Persona + Session + Visible Field across multiple intents

---

## 3. AgentSession

```rust
pub struct AgentSession {
    pool: PgPool,
    persona_id: NodeId,
    tenant_id: NodeId,
    session_id: NodeId,
    intent_mandate_id: NodeId,
    visible_field: Option<VisibleField>,
    hooks: Vec<Box<dyn LifecycleHook>>,
    signer: Box<dyn Signer>,
    strategy: Box<dyn RoutingStrategy>,
    executor: Box<dyn Executor>,
    checkers: Vec<Box<dyn FirewallChecker>>,
    scorer: Box<dyn Scorer>,
    crystallizer: Box<dyn Crystallizer>,
}
```

### SessionConfig

| Field | Type | Description |
|-------|------|-------------|
| `persona_id` | `NodeId` | The Persona operating in this session |
| `tenant_id` | `NodeId` | Tenant isolation boundary |
| `budget_limit` | `i64` | Total AP2 budget for this session |
| `token_budget` | `i64` | Token budget for Visible Field |
| `retrieval_config` | `RetrievalConfig` | Memory retrieval parameters |

---

## 4. Lifecycle Hooks

### Trait

```rust
pub trait LifecycleHook: Send + Sync {
    fn name(&self) -> &str;
    fn on_session_start(&self, ctx: &SessionContext) -> HookResult { HookResult::Continue }
    fn on_pre_execution(&self, ctx: &ExecutionContext) -> HookResult { HookResult::Continue }
    fn on_post_execution(&self, ctx: &ExecutionContext) -> HookResult { HookResult::Continue }
    fn on_pre_tool_use(&self, ctx: &ToolUseContext) -> HookResult { HookResult::Continue }
    fn on_post_tool_use(&self, ctx: &ToolUseContext) -> HookResult { HookResult::Continue }
    fn on_stop(&self, ctx: &SessionContext) -> HookResult { HookResult::Continue }
}
```

### HookResult

| Variant | Meaning |
|---------|---------|
| `Continue` | Proceed normally |
| `Halt { reason }` | Stop execution — not an error, soft stop |
| `Deny { reason }` | Block the action — safety violation |

### Hook Ordering

Hooks run in registration order. First `Deny` wins — remaining hooks are skipped. `Halt` stops execution but isn't a violation.

### Context Structs

| Context | Fields | Used At |
|---------|--------|---------|
| `SessionContext` | session_id, persona_id, tenant_id | SessionStart, Stop |
| `ExecutionContext` | task_id, intent, estimated_cost, verdict (post only), quality_score (post only) | PreExecution, PostExecution |
| `ToolUseContext` | task_id, tool_id, tool_name | PreToolUse, PostToolUse |

### Default Hooks

| Hook | What it does | Fires at |
|------|-------------|----------|
| `GatekeeperHook` | Verifies Persona not frozen before each execution | PreExecution |
| `BudgetGuardHook` | Checks remaining AP2 budget before each intent | PreExecution |
| `AuditLogHook` | Logs all lifecycle events to the knowledge graph | All 6 points |

---

## 5. Session Lifecycle

### start()

1. Validate Persona exists, not frozen, correct tenant
2. Create IntentMandate (budget envelope for this session)
3. Build initial Visible Field via Cartography
4. Register default hooks (GatekeeperHook, BudgetGuardHook, AuditLogHook)
5. Fire hooks: SessionStart → if any Deny: abort
6. Return AgentSession

### submit_intent(intent, requested_tools, estimated_cost)

1. Fire hooks: PreExecution → if Deny: return IntentDenied; if Halt: return IntentHalted
2. Create Task (status: pending)
3. Gatekeeper: authorize_task() → pending → authorized
4. Router: route_task() → authorized → routing → executing
5. Firewall: inspect_output() → executing → guarding → if CriticalBlocked: return FirewallBlocked
6. Feedback: complete_task() → guarding → crystallizing → completed
7. Fire hooks: PostExecution
8. Return IntentResult

### close()

1. Fire hooks: Stop
2. Mark Session as completed in DB

---

## 6. Types

### IntentResult

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | `NodeId` | The completed Task |
| `output` | `serde_json::Value` | Execution output |
| `verdict` | `Verdict` | Firewall verdict |
| `quality_score` | `f64` | Feedback Router score |
| `crystallized_memories` | `Vec<CrystallizedMemory>` | Produced memories |

### AgentShellError

| Variant | Description |
|---------|-------------|
| `SessionStartDenied { reason }` | Hook denied session start |
| `IntentDenied { reason }` | Hook denied intent execution |
| `IntentHalted { reason }` | Hook halted intent (soft stop) |
| `GatekeeperError(GatekeeperError)` | Authorization failed |
| `RouterError(RouterError)` | Routing/execution failed |
| `FirewallBlocked { verdict, violations }` | Output blocked by firewall |
| `FeedbackError(FeedbackError)` | Completion failed |
| `CartographyError(CartographyError)` | Context building failed |
| `DatabaseError { message }` | Infrastructure failure |

---

## 7. File Structure

```
crates/
  siss-agent-shell/
    Cargo.toml
    src/
      lib.rs              # Re-exports
      types.rs            # IntentResult, AgentShellError, SessionConfig
      session.rs          # AgentSession struct + start/submit_intent/close
      hooks/
        mod.rs            # LifecycleHook trait, HookResult, context structs
        gatekeeper.rs     # GatekeeperHook
        budget.rs         # BudgetGuardHook
        audit.rs          # AuditLogHook
        runner.rs         # Hook runner: iterates hooks, handles Deny/Halt/Continue
      pipeline.rs         # Internal: wires Gatekeeper→Router→Firewall→Feedback for one intent
```

---

## 8. Success Criteria

1. `AgentSession::start()` creates a Session, IntentMandate, and Visible Field, and fires SessionStart hooks.
2. `submit_intent()` runs the full value loop (Gatekeeper → Router → Firewall → Feedback) and returns IntentResult.
3. Multiple intents can be submitted within the same session.
4. `close()` marks the Session as completed and fires Stop hooks.
5. A `GatekeeperHook` that detects a frozen Persona returns `Deny` and blocks execution.
6. A `BudgetGuardHook` that detects insufficient budget returns `Deny`.
7. An `AuditLogHook` logs events at all 6 hook points.
8. First `Deny` from any hook stops remaining hooks from running.
9. `Halt` stops execution without being treated as an error.
10. A Firewall `CriticalBlocked` verdict is surfaced as `FirewallBlocked` error.
11. The shell can be constructed with custom trait objects (Signer, Strategy, Executor, etc.) for testing.
