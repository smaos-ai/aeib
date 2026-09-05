# MEMORY.md — Crystallized Architectural Patterns (Phase 31+)

**Last Updated:** 2026-05-20  
**Protocol:** ADVANCED REFACTOR PROTOCOL v2  
**Status:** Phase 31 Complete. Operator Plane Locked. Ready for Phase 32.

---

## 1. THE 4 SOVEREIGN RULES FOR EXPLORATION (Non-Negotiable)

Future agents MUST follow these rules to avoid context bloat and token waste:

### Rule 1: Leverage GitNexus (No More Blind Grepping)
- **What:** Use GitNexus MCP tools (`context()`, `impact()`) instead of `grep` / `find`
- **Why:** Pre-computed AST graph gives instant, deterministic answers. 10x faster than text search.
- **When:** Before reading files, ask GitNexus: "What calls this symbol?" or "What breaks if I change X?"
- **Example:** `gitnexus_context({name: "EventEmitter"})` returns all callers + callees instantly

### Rule 2: Narrow Scope with @ Mentions
- **What:** Point agents directly to files using `@Cargo.toml`, `@crates/siss-dispatcher/src/executor.rs`
- **Why:** Skips the expensive "find it" process entirely. Agent goes straight to the code.
- **When:** You already know the general vicinity (e.g., "explore @WAVE_ORCHESTRATOR.md and @HANDOFF.md")
- **Example:** "Review @Cargo.toml and @crates/siss-cockpit to add new crate" (not "find the workspace structure")

### Rule 3: Downgrade Model for Scouts (Use Haiku)
- **What:** Spawn Explore agents with explicit `model: "haiku"` parameter
- **Why:** Haiku is 10x cheaper and faster for reading/summarizing. Save Opus/Sonnet for reasoning.
- **When:** Pure exploration, file reading, summarization tasks
- **Example:** "Spawn an explore subagent using Haiku model to read @file.rs and return 3-bullet summary"

### Rule 4: Prevent Infinite Exploration with Strict Output Bounds
- **What:** Always give Explore agents a termination condition (max files, output format)
- **Why:** Without bounds, agents read hundreds of files and auto-compact, wasting tokens
- **When:** Every exploration task must have: "Stop after reading maximum of 5 files. Return ONLY a bulleted list."
- **Example:** "Explore dispatcher patterns. Max 5 files. Return: 3-bullet list of what needs to change in each."

### Rule 5: Swarm Test Verification — One Target, Exponential Backoff
- **What:** Run only `cargo test --test orchestration_integration_test -p demo-app` for swarm checks. No parallel `cargo test | grep` loops.
- **Why:** Multiple hung integration tests consumed 600+ CPU-minutes (2026-05-21 incident).
- **Polling:** If waiting on a long test, check status at 1m → 2m → 4m intervals (`sleep 60 && tail -5 log`). Never spawn redundant grep/tail shells.
- **Cleanup:** Before a new run, ensure no stale `orchestration_integration_test` processes (`pkill -f orchestration_integration_test` only if hung).

---

## 2. LOCKED INTERFACE CONTRACTS (From WAVE_ORCHESTRATOR.md)

These contracts are **immutable** for any phase that builds on Phase 31. All agents reference `WAVE_ORCHESTRATOR.md` as single source of truth.

### Task 1: Workspace Foundation ✅
```toml
# [workspace.dependencies]
axum = { version = "0.7", features = ["json"] }
tokio-stream = "0.1"
async-stream = "0.3"

# [workspace] members
"crates/siss-cockpit"
```

### Task 2: Dispatcher Event Integration ✅
```rust
// In Executor struct:
pub emitter: Box<dyn EventEmitter>

// In spawn_agents():
self.emitter.emit(AgentEvent::SessionStarted { ... });

// In assign_next_task():
self.emitter.emit(AgentEvent::TaskCreated { ... });

// In finalize_tasks():
self.emitter.emit(AgentEvent::IntentCompleted { ... });
```
**Dependency:** `siss-agent-shell` (EventEmitter trait)

### Task 3: Cockpit SSE Server ✅
```rust
// GET /api/agents/stream → SSE endpoint
// POST /api/agents/:id/{pause,resume,abort} → ControlSignal
// Buffer: max 1000 AgEvent, sent on reconnect
```
**Pattern:** Clone from `siss-enclave/src/api/ag_ui.rs` (broadcast + async_stream + Sse::new())

### Task 4: Dashboard UI ✅
```javascript
// EventSource('/api/agents/stream')
// Display 5 agent cards with status/output/buttons
// Auto-reconnect (exponential backoff)
```

### Task 5: Integration Tests ✅
8 tests validating E2E SSE streaming, pause/resume, event buffering, load testing

---

## 3. PHASE 31 SUCCESS METRICS

| Dimension | Result | Status |
|-----------|--------|--------|
| **Execution Waves** | 3 waves (sequential → parallel → sequential) | ✅ |
| **Atomic Tasks** | 5 file-orthogonal tasks | ✅ |
| **Merge Conflicts** | 0 (Golden Rule enforced) | ✅ |
| **Tests Passing** | 8/8 Phase 31 + Phase 30 regressions | ✅ |
| **Compilation** | `cargo check --all` clean | ✅ |
| **Linting** | Zero new warnings | ✅ |
| **Token Cache** | Preserved (auto-memory disabled during Wave 2) | ✅ |
| **Architecture** | Deterministic, repeatable, scalable | ✅ |

---

## 4. OPERATOR PLANE OPERATIONAL CHECKLIST

Use this checklist before deploying Phase 31 agents to production:

- [ ] `WAVE_ORCHESTRATOR.md` exists and is checked into git
- [ ] `HANDOFF.md` defines all task scopes, success criteria, file ownership
- [ ] `spec.md` documents Phase 31 architecture, risks, non-goals
- [ ] All 3 workspace deps added: `axum`, `tokio-stream`, `async-stream`
- [ ] `siss-cockpit` crate compiles: `cargo check -p siss-cockpit`
- [ ] All crates compile: `cargo check --all`
- [ ] Dispatcher emits events on task lifecycle
- [ ] SSE endpoint broadcasts AgEvent to all subscribers
- [ ] Control endpoints (pause/resume/abort) return 202 Accepted
- [ ] Event buffer persists max 1000 events, sends on reconnect
- [ ] Dashboard UI opens in browser without console errors
- [ ] Dashboard connects to SSE stream and renders live events
- [ ] 8/8 integration tests pass
- [ ] Phase 30 orchestration tests still pass (zero regressions)
- [ ] All 3 Wave 2 agents merged to `main` with zero merge conflicts
- [ ] Git log shows clean commit history (no revert/cherry-pick)

---

## 5. DARK MATTER TRAP: Auto-Memory During Parallel Execution

**Critical:** If auto-memory is enabled when 3+ agents run in parallel on same project:
1. Agent A modifies `MEMORY.md`
2. Agent A's modification invalidates **prompt cache prefix** for Agents B and C
3. Agents B and C incur cold cache reads (100x token cost increase)
4. Result: catastrophic token burn

**Mitigation:** Always disable auto-memory before Wave 2+ dispatch:
```json
{ "autoMemoryEnabled": false }
```

---

## 6. FILE-ORTHOGONAL TASK DESIGN (The Golden Rule)

**Pattern:** Assign tasks so that no two concurrent agents touch the same file.

```
Task 2 owns: crates/siss-dispatcher/src/executor.rs
Task 3 owns: crates/siss-cockpit/src/{server,state,handlers}
Task 4 owns: crates/siss-cockpit/ui/{index.html,dashboard.js}
                        ↑ Different directories = Zero merge conflicts
```

**Why it works:** Git merge conflicts only happen when two branches modify the same file. By design, Phase 31 tasks modify disjoint file sets. Merge order becomes irrelevant.

---

## 7. NEXT PHASE: Phase 32 (A2UI Payload)

**Goal:** Allow agents to dynamically compose UI via declarative JSON.

**Components:** 18 safe UI primitives (rows, columns, buttons, text fields, etc.)

**Architecture:** Agents emit `A2UIComponent` JSON via SSE → `siss-cockpit` renders on-the-fly → zero frontend engineering required.

**When:** After Phase 31 is crystallized and Phase 32 spec is reviewed.

---

## REFERENCES

- `WAVE_ORCHESTRATOR.md` — Locked interface contracts (single source of truth)
- `HANDOFF.md` — Detailed task specifications, success criteria
- `spec.md` — Phase 31 architecture, risks, non-goals
- `CLAUDE.md` — Core operations doctrine + Golden Rule
- `.claude/settings.json` — Workspace configuration

---

**Crystallization Complete. Phase 31 Knowledge Now Persistent.**

Future agent sessions will read this file on startup and operate with instant context. No more reinventing patterns. No more token waste on exploration.
