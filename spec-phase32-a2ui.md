# Specification: Phase 32 — Agent-to-User Interface (A2UI) Payload

## Goal

**Enable agents to dynamically compose safe, declarative JSON-based UI components (18 primitives) that render live in the cockpit dashboard, allowing operators to interact with agents via forms, buttons, and data displays — with zero manual frontend engineering required per new agent skill.**

## One Thing (Singular Focus)

**Agents emit A2UI component JSON via SSE → cockpit renders interactively → operator submits form → cockpit sends response back via SSE → agent receives structured data — all without backend code changes.**

---

## Success Criteria

- [ ] 18 component primitives fully defined in `a2ui_schema.rs` (Text, Button, Input, Select, Checkbox, Radio, Textarea, Table, Card, Grid, Badge, Progress, Modal, Alert, Breadcrumb, Tooltip, Divider, Link)
- [ ] JSON schema validates all 18 components with `serde_json` deserialization
- [ ] Agents emit valid A2UI JSON via existing SSE stream without changing dispatcher
- [ ] Cockpit renders all 18 components in dashboard UI (HTML/JS)
- [ ] Form submission: operator fills input/select/checkbox → response JSON sent back via SSE to agent
- [ ] Agent-side validation: agents validate A2UI JSON before emit (custom validator)
- [ ] Cockpit-side rendering: no crashes on unexpected component types (graceful fallback)
- [ ] <200ms latency from agent emit to cockpit render (measured end-to-end)
- [ ] All integration tests pass (8 tests for A2UI + forms)
- [ ] Zero new clippy warnings, zero type errors
- [ ] Phase 31 tests still pass (no regressions)

---

## Architecture

### Phase 32 Delta
Adds A2UI component system to Phase 31 cockpit. No changes to dispatcher; only cockpit gains component rendering + form handling.

### New Modules

**`crates/siss-agent-shell/src/a2ui/`** — Component primitives (Rust types)
- `schema.rs` — Define all 18 component types as enums + structs
- `validator.rs` — Pre-emit JSON validation (agent-side)
- `types.rs` — Core types: `A2UIComponent`, `FormSubmission`, `A2UIResponse`

**`crates/siss-cockpit/src/a2ui/`** — Component rendering (Rust handler)
- `renderer.rs` — Convert `A2UIComponent` JSON to HTML snippets
- `form_handler.rs` — Capture form submissions, emit `FormSubmission` back via SSE

**`crates/siss-cockpit/ui/`** — Cockpit dashboard update
- `components.js` — Render 18 primitives dynamically
- `form-handler.js` — Form submission + response routing

### 18 Component Primitives

```rust
pub enum A2UIComponent {
    // Display
    Text { content: String, size: "sm" | "md" | "lg" },
    Badge { label: String, color: "blue" | "red" | "green" },
    Alert { message: String, level: "info" | "warn" | "error" },
    Progress { value: u32, max: u32, label: Option<String> },
    Divider,
    Link { text: String, href: String },
    Tooltip { text: String, content: String },
    Breadcrumb { items: Vec<String> },
    
    // Interactive Forms
    Input { id: String, label: String, placeholder: String, required: bool },
    Textarea { id: String, label: String, rows: u32 },
    Select { id: String, label: String, options: Vec<SelectOption> },
    Checkbox { id: String, label: String },
    Radio { id: String, label: String, options: Vec<RadioOption> },
    Button { id: String, label: String, action: "submit" | "reset" },
    
    // Layout
    Card { title: String, children: Vec<A2UIComponent> },
    Grid { columns: u32, children: Vec<A2UIComponent> },
    Modal { id: String, title: String, children: Vec<A2UIComponent> },
    Table { headers: Vec<String>, rows: Vec<Vec<String>> },
}
```

### Data Flow

```
Agent (siss-dispatcher)
    ↓
    emit AgentEvent::UIRequested { components: Vec<A2UIComponent> }
    ↓
SSE Stream (GET /api/agents/stream)
    ↓
Cockpit Dashboard (JavaScript)
    ↓
    render(components) → HTML
    ↓
Operator fills form, clicks Submit
    ↓
POST /api/agents/:id/form-submit { form_id, values: JSON }
    ↓
Cockpit receives, validates against A2UIComponent schema
    ↓
Emit FormSubmission back via SSE
    ↓
Agent receives { form_id, user_input: JSON }
    ↓
Agent processes (no round-trip HTTP needed)
```

### Files to Create/Modify

| File | Action | Lines |
|------|--------|-------|
| `crates/siss-agent-shell/src/a2ui/schema.rs` | Create | 200 |
| `crates/siss-agent-shell/src/a2ui/validator.rs` | Create | 100 |
| `crates/siss-agent-shell/src/a2ui/types.rs` | Create | 80 |
| `crates/siss-cockpit/src/a2ui/renderer.rs` | Create | 250 |
| `crates/siss-cockpit/src/a2ui/form_handler.rs` | Create | 150 |
| `crates/siss-cockpit/ui/components.js` | Create | 400 |
| `crates/siss-cockpit/ui/form-handler.js` | Create | 200 |
| `crates/siss-agent-shell/src/events/mod.rs` | Modify | +30 (add UIRequested variant) |
| `crates/siss-cockpit/src/handlers/stream.rs` | Modify | +50 (emit A2UI components) |
| `crates/demo-app/tests/phase_32_a2ui_integration_test.rs` | Create | 400 |

**Total:** ~2,000 lines of code + tests.

### Design Decisions

| Decision | Rationale | Alternative Rejected |
|----------|-----------|---------------------|
| Full 18 components in Phase 32 | Complete primitive set upfront; agents have full design vocabulary | Phased rollout adds fragmentation |
| JSON schema validation | Ensures agents can't emit malformed components | Trust-based validation (risk: cockpit crash) |
| Form responses via SSE | Consistent with existing event stream; no new protocols | Separate HTTP endpoint (adds complexity) |
| Agent-side pre-validation | Fail-Closed: agent catches bugs before cockpit sees them | Cockpit-only validation (Fail-Open) |
| No HTML escaping in agent code | Cockpit escapes all output; agent doesn't need to care | Agent responsible for escaping (fragile) |

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| **Component mismatch** — Cockpit doesn't know how to render new primitive | HIGH | Strict schema validation in agent + cockpit. Graceful fallback (render unknown as Alert). |
| **Form state explosion** — Multiple forms open simultaneously, responses get mixed up | MEDIUM | Assign unique `form_id` per form. Cockpit multiplexes responses by form_id. |
| **XSS injection** — Agent embeds malicious HTML in Text component | HIGH | Agent validates all strings against safe regex. Cockpit escapes with `textContent` (no innerHTML). |
| **Performance degradation** — 18 components × 100 agents = slow rendering | MEDIUM | Batch component updates (send every 500ms). Virtualize table rows (>100 rows). |
| **Schema version mismatch** — New agent uses v2 schema, old cockpit expects v1 | MEDIUM | Include `schema_version` in every A2UIComponent. Cockpit rejects unknown versions with alert. |
| **Form submission timeout** — Agent waiting for response never receives it | MEDIUM | Timeout after 30s; emit error message to agent. Operator can retry. |

---

## Questions for User

1. **Component extensibility:** Should Phase 32 allow agents to define custom components (e.g., "custom_widget"), or are the 18 primitives the absolute ceiling? (Recommendation: fixed 18 for now, custom in Phase 34)

2. **Styling:** Should components accept CSS classes or inline styles, or are they unstyled by default? (Recommendation: tailwind classes via `className` field, cockpit applies)

3. **Accessibility:** Should all components include ARIA labels and alt text? (Recommendation: yes, required fields in schema)

4. **Rate limiting:** Should cockpit throttle component emissions (e.g., max 100 components per second per agent)? (Recommendation: yes, prevent DoS)

---

## Testing Strategy (TDD First)

Tests in `crates/demo-app/tests/phase_32_a2ui_integration_test.rs`:

1. `test_a2ui_text_component_renders_correctly` → Text component → HTML output
2. `test_a2ui_input_form_captures_user_input` → Input component → form submit → JSON response
3. `test_a2ui_select_component_with_options` → Select with 5 options → user selects → correct value returned
4. `test_a2ui_table_component_renders_rows_and_headers` → Table with 10 rows → HTML table
5. `test_a2ui_modal_component_opens_and_closes` → Modal → click OK → response returned
6. `test_a2ui_form_submission_with_multiple_fields` → 5-field form → all fields populated → JSON matches schema
7. `test_a2ui_invalid_component_gracefully_fails` → Cockpit receives malformed JSON → renders Alert fallback
8. `test_a2ui_agent_validation_rejects_missing_required_fields` → Agent tries to emit Input without id → validator rejects

---

## Non-Goals (Phase 33+)

- Custom component definitions by agents
- Real-time collaborative form editing (multiple operators)
- Component drag-and-drop (UI builder)
- Persistent component state (forms auto-save)
- Advanced styling (CSS variables, themes)

---

## Success Narrative

After Phase 32:
- Agents can request approval: `A2UIComponent::Modal { title: "Approve this action?", children: [Button::yes, Button::no] }`
- Agents can request input: `A2UIComponent::Input { label: "Enter API key" }`
- Agents can display results: `A2UIComponent::Table { headers: ["name", "status"], rows: [...] }`
- Operators interact with agents without touching code
- **Zero frontend engineering required per new skill**

---

**Phase 31 Locked. Phase 32 Ready for Planning & Dispatch.**
