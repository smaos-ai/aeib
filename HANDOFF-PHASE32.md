# Phase 32 HANDOFF — Agent-to-User Interface (A2UI) Payload

## Overview

5 atomic tasks. Wave 1 sequential (foundation). Wave 2 parallel (3 agents, file-orthogonal). Wave 3 sequential (integration tests).

**The Golden Rule applies:** Each task owns distinct files. Zero merge conflicts by design.

---

## Task 1: A2UI Schema Foundation *(Wave 1 — must complete first)*

**Goal:** Define all 18 A2UIComponent primitives and add UIRequested event to the dispatcher event stream.

**Owns (may modify only these files):**
- `crates/siss-agent-shell/src/a2ui/mod.rs` (create)
- `crates/siss-agent-shell/src/a2ui/schema.rs` (create)
- `crates/siss-agent-shell/src/a2ui/types.rs` (create)
- `crates/siss-agent-shell/src/events/mod.rs` (modify: add UIRequested variant)
- `crates/siss-agent-shell/src/lib.rs` (modify: add pub mod a2ui)

**Success Criteria:**
- [ ] All 18 component types defined in `A2UIComponent` enum with `#[derive(Serialize, Deserialize)]`
- [ ] Each component variant has required and optional fields (see spec-phase32-a2ui.md)
- [ ] `UIRequested` variant added to `AgentEvent` enum at line 82 in events/mod.rs
- [ ] `event_type()` match block updated for `UIRequested`
- [ ] `cargo check -p siss-agent-shell` passes
- [ ] `cargo clippy -p siss-agent-shell` zero warnings

**Implementation Details:**

1. Create `siss-agent-shell/src/a2ui/schema.rs`:
```rust
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum A2UIComponent {
    // Display (8 types)
    Text { content: String, size: String },
    Badge { label: String, color: String },
    Alert { message: String, level: String },
    Progress { value: u32, max: u32, label: Option<String> },
    Divider,
    Link { text: String, href: String },
    Tooltip { text: String, content: String },
    Breadcrumb { items: Vec<String> },
    
    // Forms (6 types)
    Input { id: String, label: String, placeholder: String, required: bool },
    Textarea { id: String, label: String, rows: u32 },
    Select { id: String, label: String, options: Vec<SelectOption> },
    Checkbox { id: String, label: String },
    Radio { id: String, label: String, options: Vec<RadioOption> },
    Button { id: String, label: String, action: String },
    
    // Layout (4 types)
    Card { title: String, children: Vec<A2UIComponent> },
    Grid { columns: u32, children: Vec<A2UIComponent> },
    Modal { id: String, title: String, children: Vec<A2UIComponent> },
    Table { headers: Vec<String>, rows: Vec<Vec<String>> },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SelectOption { pub value: String, pub label: String }

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RadioOption { pub value: String, pub label: String }
```

2. Create `siss-agent-shell/src/a2ui/types.rs`:
```rust
use serde::{Deserialize, Serialize};
use uuid::Uuid;
use super::schema::A2UIComponent;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FormSubmission {
    pub task_id: Uuid,
    pub form_id: String,
    pub values: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct A2UIResponse {
    pub component_type: String,
}
```

3. In `crates/siss-agent-shell/src/events/mod.rs` at line 82:
   - Add `UIRequested { task_id: Uuid, components: Vec<A2UIComponent>, form_id: Option<String>, timestamp: DateTime<Utc> },`
   - Update event_type() match: `Self::UIRequested { .. } => "ui_requested",`

4. In `crates/siss-agent-shell/src/lib.rs`:
   - Add: `pub mod a2ui;`

**Test Verification:**
```bash
cargo check -p siss-agent-shell
cargo clippy -p siss-agent-shell
```

---

## Task 2: Agent-Side Validator *(Wave 2 — parallel with Tasks 3 and 4)*

**Goal:** Implement Fail-Closed validation: agents reject malformed components before emitting.

**Owns (may modify only these files):**
- `crates/siss-agent-shell/src/a2ui/validator.rs` (create)

**Context (read before touching):**
- `spec-phase32-a2ui.md` — Component field requirements
- `siss-agent-shell/src/a2ui/schema.rs` — Component definitions

**Success Criteria:**
- [ ] `A2UIComponent::validate()` method returns `Result<(), ValidationError>`
- [ ] All Form components (Input, Select, Checkbox, Radio) must have non-empty `id`
- [ ] All components with `label` field must have non-empty label
- [ ] Invalid component rejected with descriptive ValidationError
- [ ] `cargo check -p siss-agent-shell` passes
- [ ] All Form components validate correctly

**Implementation Details:**
```rust
// In validator.rs
#[derive(Debug, Clone)]
pub enum ValidationError {
    MissingId(String),
    MissingLabel(String),
    InvalidValue(String),
}

impl A2UIComponent {
    pub fn validate(&self) -> Result<(), ValidationError> {
        match self {
            A2UIComponent::Input { id, label, .. } if id.is_empty() => 
                Err(ValidationError::MissingId("Input".to_string())),
            A2UIComponent::Select { id, label, .. } if id.is_empty() =>
                Err(ValidationError::MissingId("Select".to_string())),
            // ... repeat for Checkbox, Radio
            _ => Ok(()),
        }
    }
}
```

---

## Task 3: Cockpit SSE + Renderer *(Wave 2 — parallel with Tasks 2 and 4)*

**Goal:** Implement real Axum SSE handlers, A2UI component renderer, and form submission endpoint.

**Owns (may modify only these files):**
- `crates/siss-cockpit/src/state.rs` (implement full CockpitState)
- `crates/siss-cockpit/src/server.rs` (create real server)
- `crates/siss-cockpit/src/handlers/stream.rs` (implement SSE handler)
- `crates/siss-cockpit/src/handlers/control.rs` (implement pause/resume/abort)
- `crates/siss-cockpit/src/handlers/form_submit.rs` (create)
- `crates/siss-cockpit/src/a2ui/mod.rs` (create)
- `crates/siss-cockpit/src/a2ui/renderer.rs` (create)

**Context (read before touching):**
- `siss-enclave/src/api/ag_ui.rs` — SSE handler pattern
- `siss-enclave/src/events/sse_emitter.rs` — broadcast::Sender pattern
- `spec-phase32-a2ui.md` — Component rendering requirements

**Success Criteria:**
- [ ] CockpitState wraps `broadcast::Sender<AgEvent>` and `Arc<Mutex<VecDeque<AgEvent>>>`
- [ ] Event buffer stores max 1000 events, sends on reconnect
- [ ] `GET /api/agents/stream` returns SSE with live events
- [ ] `POST /api/agents/:id/pause`, `/resume`, `/abort` send ControlSignal, return 202
- [ ] `POST /api/agents/:id/form-submit` accepts form JSON, emits FormSubmission back via SSE
- [ ] A2UIComponent renderer converts all 18 types to valid HTML strings
- [ ] `cargo check -p siss-cockpit` passes
- [ ] All handlers compile without warnings

**Implementation Pattern:**
- SSE: Clone pattern from `siss-enclave/src/api/ag_ui.rs` (async_stream + broadcast + Sse::new)
- Renderer: Match on `A2UIComponent`, return `String` containing HTML
- Form submit: Receive JSON, validate schema, emit FormSubmission to agent

---

## Task 4: Dashboard UI Components *(Wave 2 — parallel with Tasks 2 and 3)*

**Goal:** Render all 18 A2UIComponent primitives in the cockpit dashboard and handle form submissions.

**Owns (may modify only these files):**
- `crates/siss-cockpit/ui/components.js` (create)
- `crates/siss-cockpit/ui/form-handler.js` (create)

**Context:**
- `spec-phase32-a2ui.md` — Component specifications
- siss-cockpit/src/a2ui/renderer.rs — Component HTML format (read after Task 3)

**Success Criteria:**
- [ ] `components.js` exports `renderComponent(comp)` function
- [ ] All 18 component types render without console errors
- [ ] `form-handler.js` intercepts form submits and sends JSON to `/api/agents/:id/form-submit`
- [ ] Form responses received via SSE are routed correctly to agent
- [ ] Opens in Chrome, no CORS errors
- [ ] Dashboard shows all component types rendering correctly

**Implementation Details:**

Pure vanilla JS, no framework. Functions:
- `renderComponent(comp)` — switch on `comp.type`, return DOM node
- `handleFormSubmit(formId, agentId)` — capture values, POST to cockpit, await response
- Auto-reconnect on SSE disconnect (exponential backoff)

---

## Task 5: Integration Tests *(Wave 3 — after Tasks 2 and 3 merged)*

**Goal:** Validate complete A2UI flow: agent emits components → cockpit renders → operator submits form → agent receives response.

**Owns (may modify only these files):**
- `crates/demo-app/tests/phase_32_a2ui_integration_test.rs` (create)

**Tests to write (see spec-phase32-a2ui.md for full details):**
1. `test_a2ui_text_component_renders_correctly`
2. `test_a2ui_input_form_captures_user_input`
3. `test_a2ui_select_component_with_options`
4. `test_a2ui_table_component_renders_rows_and_headers`
5. `test_a2ui_modal_component_opens_and_closes`
6. `test_a2ui_form_submission_with_multiple_fields`
7. `test_a2ui_invalid_component_gracefully_fails`
8. `test_a2ui_agent_validation_rejects_missing_required_fields`

**Success Criteria:**
- [ ] All 8 tests pass: `cargo test --test phase_32_a2ui_integration_test -p demo-app`
- [ ] Phase 31 tests still pass (no regressions)
- [ ] Phase 30 orchestration tests still pass
- [ ] No new clippy warnings

---

## Merge Order (Topological)

```
Task 1 → merge first (unblocks all others)
Tasks 2, 3, 4 → merge in any order (no dependencies between them)
Task 5 → merge last (depends on 2 and 3 being in main)
```

---

## Final Verification (after all merges)

```bash
cargo check --all
cargo clippy --all -- -D warnings
cargo test --test phase_32_a2ui_integration_test -p demo-app
cargo test --test phase_31_ag_ui_integration_test -p demo-app
cargo test --test orchestration_integration_test -p demo-app
```

Expected: All 8 Phase 32 tests pass, no regressions, zero warnings, clean compile.
