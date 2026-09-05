# WAVE_ORCHESTRATOR.md — Phase 31 Locked Interface Contract

**This file is the single source of truth for all 5 parallel agents. Do not deviate from this contract.**

---

## EXECUTIVE SUMMARY

Phase 31: Real-Time Agent Observability (AG-UI Foundation). 5 atomic tasks, 3 waves, zero merge conflicts (file-orthogonal).

---

## LOCKED INTERFACE CONTRACTS (Immutable)

### Task 1: Workspace Foundation
**Owns:** Root `Cargo.toml`, `crates/siss-cockpit/Cargo.toml`, `crates/siss-cockpit/src/lib.rs`  
**Delivers:** Workspace dependencies + empty crate skeleton  
**Exit Criteria:** `cargo check -p siss-cockpit` + `cargo check --all` pass  
**Merge:** To `main`  

**Contract:**
```toml
# Add to [workspace.dependencies]:
axum = { version = "0.7", features = ["json"] }
tokio-stream = "0.1"
async-stream = "0.3"

# Add to [workspace] members:
"crates/siss-cockpit"
```

---

### Task 2: Dispatcher Event Integration
**Owns:** `crates/siss-dispatcher/src/executor.rs`, `crates/siss-dispatcher/Cargo.toml`  
**Depends On:** Task 1 merged to `main`  
**Delivers:** Event emission on task assignment/completion  
**Exit Criteria:** `cargo check -p siss-dispatcher` passes, event emit calls compile  
**Merge:** To `main`  

**Contract:**
```rust
// In Executor struct:
pub emitter: Box<dyn EventEmitter>

// In spawn_agents():
self.emitter.emit(AgentEvent::SessionStarted { /* */ });

// In assign_next_task():
self.emitter.emit(AgentEvent::TaskCreated { /* */ });

// In finalize_tasks():
self.emitter.emit(AgentEvent::IntentCompleted { /* */ });
```

**Dependency:** Add `siss-agent-shell` to `Cargo.toml`. Use `EventEmitter` trait from `siss-agent-shell/src/events/emitter.rs`.

---

### Task 3: Cockpit SSE Server
**Owns:** `crates/siss-cockpit/src/server.rs`, `handlers/stream.rs`, `handlers/control.rs`, `state.rs`  
**Depends On:** Task 1 merged to `main`  
**Delivers:** Axum SSE endpoint + pause/resume/abort endpoints  
**Exit Criteria:** `cargo check -p siss-cockpit` passes, SSE handler compiles  
**Merge:** To `main`  

**Contract:**
```rust
// GET /api/agents/stream
// SSE endpoint: broadcast AgEvent to all subscribers
// On reconnect: send buffered events (max 1000) first

// POST /api/agents/:id/pause
// POST /api/agents/:id/resume
// POST /api/agents/:id/abort
// Return: StatusCode::ACCEPTED (202)
```

**Pattern:** Clone from `siss-enclave/src/api/ag_ui.rs` (async_stream + broadcast + Sse::new())

---

### Task 4: Dashboard UI
**Owns:** `crates/siss-cockpit/ui/index.html`, `dashboard.js`  
**Depends On:** Task 3 deployed (but can write in parallel)  
**Delivers:** Single-page dashboard, 5 agent cards, live controls  
**Exit Criteria:** Opens in browser without console errors, renders SSE events  
**Merge:** To `main`  

**Contract:**
```javascript
// GET /api/agents/stream (EventSource)
// Display 5 agent cards: ID, task, status, output, buttons
// POST /api/agents/:id/pause (and resume, abort)
// Auto-reconnect on disconnect (exponential backoff)
```

---

### Task 5: Integration Tests
**Owns:** `crates/demo-app/tests/phase_31_ag_ui_integration_test.rs`  
**Depends On:** Tasks 2 and 3 merged to `main`  
**Delivers:** 8 integration tests  
**Exit Criteria:** All 8 tests pass, no regressions in Phase 30 tests  
**Merge:** To `main`  

**Contract:** Write these 8 tests:
1. `test_ag_ui_broadcaster_emits_event_on_task_assignment`
2. `test_cockpit_sse_stream_broadcasts_all_events`
3. `test_cockpit_pause_signal_pauses_agent_execution`
4. `test_cockpit_resume_signal_resumes_from_checkpoint`
5. `test_event_ordering_maintained_under_5_concurrent_agents`
6. `test_sse_connection_loss_and_reconnect_with_buffered_events`
7. `test_pause_idempotency`
8. `test_abort_releases_control_signal`

All must pass: `cargo test --test phase_31_ag_ui_integration_test -p demo-app`

---

## WAVE EXECUTION SEQUENCE

### WAVE 1 — Sequential (Foundation)
**Task 1 ONLY.** Must complete and merge to `main` before Wave 2 starts.

```bash
cargo check -p siss-cockpit
cargo check --all
# Merge to main
```

### WAVE 2 — Parallel (Implementation)
**Tasks 2, 3, 4 run concurrently.** File-orthogonal (zero merge conflicts).

```bash
# Task 2: Dispatcher
cargo check -p siss-dispatcher
cargo test -p siss-dispatcher

# Task 3: Cockpit SSE
cargo check -p siss-cockpit
cargo test -p siss-cockpit

# Task 4: Dashboard UI
# No tests (pure HTML/JS). Load in browser.
```

**All three merge to `main` in any order.**

### WAVE 3 — Sequential (Integration)
**Task 5 ONLY.** Runs after Tasks 2 and 3 are in `main`.

```bash
cargo test --test phase_31_ag_ui_integration_test -p demo-app
cargo test --test orchestration_integration_test -p demo-app
```

---

## CRITICAL FILES TO READ (Before Touching Code)

| File | Why |
|------|-----|
| `siss-agent-shell/src/events/emitter.rs` | `EventEmitter` trait to inject |
| `siss-agent-shell/src/events/mod.rs` | `AgentEvent` variants (13 types) |
| `siss-enclave/src/api/ag_ui.rs` | SSE pattern to clone |
| `siss-enclave/src/events/sse_emitter.rs` | `broadcast::Sender` pattern |
| `siss-dispatcher/src/executor.rs` | Where to emit events |
| `Cargo.toml` (root) | Workspace structure |

---

## SUCCESS CRITERIA (Global)

After all 5 tasks merge to `main`:

```bash
cargo check --all              # ✅ Zero errors
cargo test --all               # ✅ All tests pass (including Phase 30)
cargo clippy --all             # ✅ Zero new warnings
```

Expected: 8/8 Phase 31 tests pass, no regressions, clean compile.

---

## AGENT INSTRUCTIONS

**All agents:** Read this entire file before starting. Follow the locked interface contract exactly. Do not deviate. Do not over-engineer.

**Exit criteria for each agent:** When your task's success criteria are met (and all tests pass), commit, push, and report completion with exit code 0.

**If you encounter ambiguity:** Check the corresponding section in `HANDOFF.md` (detailed task specification) or `spec.md` (Phase 31 architecture).

---

---

# PHASE 32 EXTENSION — A2UI Locked Interface Contracts

### Task 1: A2UI Schema Foundation
**Owns:** `siss-agent-shell/src/a2ui/`, `siss-agent-shell/src/events/mod.rs`  
**Delivers:** All 18 component types + UIRequested event variant  
**Exit Criteria:** `cargo check -p siss-agent-shell` passes  
**Merge:** To `main`  

**Contract:**
```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum A2UIComponent {
    // 8 Display types
    Text { content: String, size: String },
    Badge { label: String, color: String },
    Alert { message: String, level: String },
    Progress { value: u32, max: u32, label: Option<String> },
    Divider,
    Link { text: String, href: String },
    Tooltip { text: String, content: String },
    Breadcrumb { items: Vec<String> },
    
    // 6 Form types (all require id field)
    Input { id: String, label: String, placeholder: String, required: bool },
    Textarea { id: String, label: String, rows: u32 },
    Select { id: String, label: String, options: Vec<SelectOption> },
    Checkbox { id: String, label: String },
    Radio { id: String, label: String, options: Vec<RadioOption> },
    Button { id: String, label: String, action: String },
    
    // 4 Layout types
    Card { title: String, children: Vec<A2UIComponent> },
    Grid { columns: u32, children: Vec<A2UIComponent> },
    Modal { id: String, title: String, children: Vec<A2UIComponent> },
    Table { headers: Vec<String>, rows: Vec<Vec<String>> },
}

// In AgentEvent:
UIRequested { task_id: Uuid, components: Vec<A2UIComponent>, form_id: Option<String>, timestamp: DateTime<Utc> }
```

---

### Task 2: Agent-Side Validator
**Owns:** `siss-agent-shell/src/a2ui/validator.rs`  
**Delivers:** Pre-emit validation (Fail-Closed)  
**Exit Criteria:** Validator rejects malformed components  
**Merge:** To `main`  

**Contract:**
```rust
impl A2UIComponent {
    pub fn validate(&self) -> Result<(), ValidationError> { /* ... */ }
}

// ValidationError variants:
// - MissingId(component_type)
// - MissingLabel(component_type)
// - InvalidValue(field)
```

---

### Task 3: Cockpit SSE + Renderer
**Owns:** `siss-cockpit/src/state.rs`, `handlers/`, `a2ui/renderer.rs`  
**Delivers:** Real Axum handlers + HTML renderer for 18 components + form-submit endpoint  
**Exit Criteria:** `cargo check -p siss-cockpit` passes  
**Merge:** To `main`  

**Contract:**
```rust
// GET /api/agents/stream → SSE (pattern: siss-enclave/src/api/ag_ui.rs)
// POST /api/agents/:id/{pause,resume,abort} → 202 Accepted
// POST /api/agents/:id/form-submit { form_id, values } → FormSubmission emitted back via SSE

// Renderer:
pub fn render_component(comp: &A2UIComponent) -> String { /* HTML */ }
```

---

### Task 4: Dashboard UI Components
**Owns:** `siss-cockpit/ui/components.js`, `siss-cockpit/ui/form-handler.js`  
**Delivers:** DOM rendering + form submission  
**Exit Criteria:** Opens in browser, renders all 18 types  
**Merge:** To `main`  

**Contract:**
```javascript
// renderComponent(comp) → DOM node
// handleFormSubmit(formId, agentId) → POST /api/agents/:id/form-submit
// Auto-reconnect on SSE disconnect
```

---

### Task 5: Integration Tests
**Owns:** `demo-app/tests/phase_32_a2ui_integration_test.rs`  
**Delivers:** 8 integration tests  
**Exit Criteria:** All 8 tests pass, no regressions  
**Merge:** To `main`  

---

## WAVE 3+ EXECUTION SEQUENCE (Phase 32)

### WAVE 1 — Sequential (Schema Foundation)
**Task 1 ONLY.** Must complete before Wave 2.

### WAVE 2 — Parallel (Implementation)
**Tasks 2, 3, 4 run concurrently.** File-orthogonal (zero merge conflicts).

### WAVE 3 — Sequential (Integration)
**Task 5 ONLY.** Runs after Tasks 2 and 3 merge.

---

**Generated:** 2026-05-20  
**Phases:** Phase 31 Locked | Phase 32 Locked  
**Protocol:** ADVANCED REFACTOR PROTOCOL v2 — Thin Vertical Slices + Locked Interface Contracts  
**Orchestrator:** Agent of Empires (AoE) with tmux isolation
