# Phase 31 HANDOFF — Real-Time Agent Observability

## Overview

5 atomic tasks. Wave 1 runs first (foundation). Wave 2 runs in parallel (Tasks 2/3/4 are file-orthogonal). Wave 3 runs after 2 and 3 complete.

**The Golden Rule:** Each task owns a specific set of files. No task modifies another task's files. Zero merge conflicts by design.

---

## Task 1: Workspace Foundation *(Wave 1 — must complete first)*

**Goal:** Add missing workspace dependencies and create siss-cockpit crate skeleton so Tasks 2, 3, 4 can compile against it.

**Owns (may modify only these files):**
- `Cargo.toml` (root workspace)
- `crates/siss-cockpit/Cargo.toml` (create new)
- `crates/siss-cockpit/src/lib.rs` (create new, stub only)

**Constraints:**
- Do NOT implement any logic. Create a minimal crate that compiles empty.
- Do NOT modify any existing crate's `Cargo.toml` yet (that's Task 2's job for dispatcher).
- The `lib.rs` should be literally: `pub mod server; pub mod state; pub mod handlers;` with empty stub modules.

**Success Criteria:**
- [ ] Root `Cargo.toml` contains `axum = { version = "0.7", features = ["json"] }` in `[workspace.dependencies]`
- [ ] Root `Cargo.toml` contains `tokio-stream = "0.1"` in `[workspace.dependencies]`
- [ ] Root `Cargo.toml` contains `async-stream = "0.3"` in `[workspace.dependencies]`
- [ ] Root `Cargo.toml` has `"crates/siss-cockpit"` in `members` array
- [ ] `cargo check -p siss-cockpit` passes (empty crate compiles)
- [ ] `cargo check --all` passes (no existing crates broken)

---

## Task 2: Dispatcher Event Integration *(Wave 2 — parallel with Tasks 3 and 4)*

**Goal:** Wire the Phase 30 dispatcher to emit `AgentEvent` lifecycle events using the existing `EventEmitter` trait from `siss-agent-shell`.

**Owns (may modify only these files):**
- `crates/siss-dispatcher/src/executor.rs`
- `crates/siss-dispatcher/Cargo.toml`

**Context (read before touching):**
- `siss-agent-shell/src/events/emitter.rs` — `EventEmitter` trait: `fn emit(&self, event: AgentEvent)`
- `siss-agent-shell/src/events/mod.rs` — `AgentEvent` enum variants
- `siss-dispatcher/src/executor.rs` — `Executor` struct, `run_loop()`, `spawn_agents()`, `assign_next_task()`, `finalize_tasks()`

**Work:**
1. Add `siss-agent-shell` to `crates/siss-dispatcher/Cargo.toml` deps
2. Add `emitter: Box<dyn EventEmitter>` field to `Executor` struct (default: `NoOpEmitter`)
3. In `spawn_agents()`: emit `AgentEvent::SessionStarted` per agent
4. In `assign_next_task()`: emit `AgentEvent::TaskCreated` when task assigned
5. In `finalize_tasks()`: emit `AgentEvent::IntentCompleted` per completed task
6. Add `pub fn set_emitter(&mut self, emitter: Box<dyn EventEmitter>)` on `Executor`

**Constraints:**
- Do NOT change any other file. Only `executor.rs` and `Cargo.toml`.
- Do NOT break existing Phase 30 behavior — event emission is additive.
- `NoOpEmitter` remains the default so existing tests pass without changes.

**Success Criteria:**
- [ ] `cargo check -p siss-dispatcher` passes
- [ ] `Executor::set_emitter()` is a public method
- [ ] `executor.rs` calls `self.emitter.emit(...)` at task assignment, completion, and spawn
- [ ] Existing `cargo test -p siss-dispatcher` (if any tests) still pass
- [ ] No new clippy warnings in `siss-dispatcher`

---

## Task 3: Cockpit SSE Server *(Wave 2 — parallel with Tasks 2 and 4)*

**Goal:** Build a standalone Axum HTTP server (port 8080) that fans out agent events via SSE and accepts pause/resume/abort control signals.

**Owns (may modify only these files):**
- `crates/siss-cockpit/src/server.rs` (create)
- `crates/siss-cockpit/src/state.rs` (create)
- `crates/siss-cockpit/src/handlers/stream.rs` (create)
- `crates/siss-cockpit/src/handlers/control.rs` (create)
- `crates/siss-cockpit/src/lib.rs` (overwrite Task 1's stub with full module declarations)

**Context (read before touching — copy the pattern, not the code):**
- `siss-enclave/src/events/sse_emitter.rs` — `SseEmitter` with `broadcast::Sender`
- `siss-enclave/src/api/ag_ui.rs` — Axum SSE handler: `async_stream::stream!` + `broadcast::Receiver` + `Sse::new().keep_alive()`
- `siss-enclave/src/api/router.rs` — `Router` mounting pattern

**Work:**
1. `state.rs`: `CockpitState { broadcast: broadcast::Sender<AgEvent>, buffer: Arc<Mutex<VecDeque<AgEvent>>> }`. Buffer max 1000 events. Methods: `send_event()`, `subscribe()`, `get_buffer_snapshot()`.
2. `handlers/stream.rs`: `GET /api/agents/stream` — on connect, send buffered events first, then live stream via `broadcast::Receiver`. `Sse::new(stream).keep_alive(KeepAlive::default())`.
3. `handlers/control.rs`: `POST /api/agents/:id/pause`, `POST /api/agents/:id/resume`, `POST /api/agents/:id/abort` — send `ControlSignal` to `mpsc::Sender`. Return 202 Accepted.
4. `server.rs`: `CockpitServer::run(port: u16)` — creates Axum router, mounts all routes, spawns tokio server.

**Constraints:**
- Do NOT write any HTML/JS. That's Task 4's scope.
- Do NOT touch `siss-dispatcher`. Integration is Task 2's job.
- Follow siss-enclave's SSE pattern exactly — do not invent a different approach.

**Success Criteria:**
- [ ] `cargo check -p siss-cockpit` passes
- [ ] `GET /api/agents/stream` compiles as SSE endpoint
- [ ] `POST /api/agents/:id/pause` compiles and returns `StatusCode::ACCEPTED`
- [ ] `CockpitState::send_event()` stores event in buffer + broadcasts to all subscribers
- [ ] On reconnect, buffer snapshot is sent before live stream begins
- [ ] No clippy warnings in `siss-cockpit`

---

## Task 4: Dashboard UI *(Wave 2 — parallel, fully independent)*

**Goal:** Build a single-page HTML dashboard that reads SSE events from `/api/agents/stream` and displays live agent status with pause/resume/abort controls.

**Owns (may modify only these files):**
- `crates/siss-cockpit/ui/index.html` (create)
- `crates/siss-cockpit/ui/dashboard.js` (create)

**Context:**
- Dashboard talks to `GET /api/agents/stream` (SSE endpoint from Task 3)
- Dashboard sends `POST /api/agents/:id/pause`, `/resume`, `/abort` (control endpoints from Task 3)
- Events are JSON: `{ event_type: "TaskAssigned" | "ToolCall" | "IntentCompleted", agent_id, task_id, payload, timestamp }`

**Work:**
1. `index.html`: Grid of 5 agent cards. Each card shows: agent ID, current task, status badge (idle/working/paused/completed), streaming output textarea, Pause/Resume/Abort buttons.
2. `dashboard.js`:
   - `EventSource('/api/agents/stream')` with auto-reconnect (exponential backoff, max 30s)
   - On event: parse JSON, update correct agent card
   - Buttons: `fetch('/api/agents/${id}/pause', { method: 'POST' })` etc.
   - Handle SSE disconnect: show "Reconnecting..." indicator, re-attempt with backoff
   - Keep last 500 lines of output per agent in textarea

**Constraints:**
- Pure HTML + vanilla JS only. No React, Vue, or bundler.
- No build step. File must work when served as static file.
- Do NOT modify any Rust code.

**Success Criteria:**
- [ ] `index.html` opens in Chrome without console errors
- [ ] Dashboard shows 5 agent card slots with status badges
- [ ] Pause button sends POST to correct endpoint
- [ ] Auto-reconnect logic is present in `dashboard.js`
- [ ] Textarea shows streaming output (last 500 lines)

---

## Task 5: Integration Tests *(Wave 3 — after Tasks 2 and 3 complete)*

**Goal:** Write 8 integration tests for Phase 31 that verify the full observability stack works end-to-end.

**Owns (may modify only these files):**
- `crates/demo-app/tests/phase_31_ag_ui_integration_test.rs` (create)

**Context (read before touching):**
- `crates/demo-app/tests/orchestration_integration_test.rs` — Phase 30 test pattern to follow
- `siss-agent-shell/src/events/` — AgentEvent types used in assertions
- `siss-cockpit/src/state.rs` — CockpitState API for test setup

**Tests to write:**

1. `test_ag_ui_broadcaster_emits_event_on_task_assignment`
2. `test_cockpit_sse_stream_broadcasts_all_events`
3. `test_cockpit_pause_signal_pauses_agent_execution`
4. `test_cockpit_resume_signal_resumes_from_checkpoint`
5. `test_event_ordering_maintained_under_5_concurrent_agents`
6. `test_sse_connection_loss_and_reconnect_with_buffered_events`
7. `test_pause_idempotency`
8. `test_abort_releases_control_signal`

**Constraints:**
- Do NOT modify Tasks 2 or 3 source files. Tests must work with APIs as-built.
- Follow Phase 30 test patterns from `orchestration_integration_test.rs`.
- No live network calls in tests — use in-process server setup (bind to random port).

**Success Criteria:**
- [ ] All 8 tests compile without errors
- [ ] All 8 tests pass: `cargo test --test phase_31_ag_ui_integration_test -p demo-app`
- [ ] No `#[ignore]` or `#[should_panic]` markers (all tests verify real behavior)
- [ ] Phase 30 tests still pass: `cargo test --test orchestration_integration_test -p demo-app`

---

## Merge Order (Topological)

```
Task 1 → merge first (unblocks all others)
Tasks 2, 3, 4 → merge in any order (no dependencies between them)
Task 5 → merge last (depends on 2 and 3 being in main)
```

## Final Verification (after all merges)

```bash
cargo check --all
cargo test --test phase_31_ag_ui_integration_test -p demo-app
cargo test --test orchestration_integration_test -p demo-app
cargo clippy --all -- -D warnings
```

Expected: All tests pass, zero warnings, clean compile.
