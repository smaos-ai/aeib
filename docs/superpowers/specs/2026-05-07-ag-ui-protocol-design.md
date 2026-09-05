# AG-UI Protocol Design — Phase 2

**Date:** 2026-05-07
**Status:** Approved
**Scope:** SSE event streaming for agent shell observability
**Depends on:** Agent Shell Phase 1

---

## 1. Overview

AG-UI (Agent-User Interaction) is the streaming observability protocol for the agent shell. It makes every pipeline step visible to the Operator Plane (AoE) via typed, timestamped events emitted through an `EventEmitter` trait.

---

## 2. EventEmitter Trait

```rust
pub trait EventEmitter: Send + Sync {
    fn emit(&self, event: AgentEvent);
}
```

Injected into `AgentSession` at `start()`. Called at every pipeline step.

---

## 3. Event Types (13 total)

| Event | When | Key Fields |
|-------|------|------------|
| SessionStarted | Session created | session_id, persona_id |
| SessionClosed | Session ended | session_id |
| HookFired | Any lifecycle hook runs | hook_name, hook_point, result |
| TaskCreated | Task inserted in DB | task_id, intent |
| Authorized | Gatekeeper passes | task_id, mandate_id |
| Routed | Router assigns target | task_id, hardware_target |
| OutputChunk | Executor produces output | task_id, chunk, index |
| Executing | Execution completes | task_id, token_cost, duration_ms |
| FirewallInspected | Firewall renders verdict | task_id, verdict, violation_count |
| Scored | Quality score computed | task_id, quality_score |
| Crystallized | Memories produced | task_id, memory_count |
| IntentCompleted | Full loop done | task_id, quality_score |
| Error | Any failure | message |

All events carry a `timestamp: DateTime<Utc>`.

---

## 4. Emitter Implementations

| Emitter | Purpose |
|---------|---------|
| NoOpEmitter | Default — discards events |
| CollectingEmitter | Tests — stores in Arc<Mutex<Vec>> |
| CallbackEmitter | AoE — calls Box<dyn Fn(AgentEvent)> |

---

## 5. Success Criteria

1. Every pipeline step emits the correct event type.
2. Events are ordered chronologically within an intent.
3. CollectingEmitter captures all events for test assertions.
4. NoOpEmitter has zero overhead.
5. CallbackEmitter calls the provided closure for each event.
6. OutputChunk events include sequential index numbers.
7. HookFired events include the hook name, point, and result summary.
