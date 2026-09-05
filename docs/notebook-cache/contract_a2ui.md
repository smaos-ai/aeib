# A2UI — Locked Interface Contract (cached)

**Source:** repo scaffold from `schema.rs` + HANDOFF-PHASE32. Replace with Studio export when available.

## JSON wire format

- Externally tagged: `{ "type": "input", "id": "...", "label": "...", ... }`
- Rust: `#[serde(tag = "type", rename_all = "snake_case")]` on `A2UIComponent`

## 18 primitives (fixed ceiling)

**Display (8):** text, badge, alert, progress, divider, link, tooltip, breadcrumb  
**Forms (6):** input, textarea, select, checkbox, radio, button  
**Layout (4):** card, grid, modal, table

No 19th type in Phase 32.

## SSE event contract

```rust
UIRequested {
    task_id: Uuid,
    components: Vec<A2UIComponent>,
    form_id: Option<String>,  // set when form submission expected
    timestamp: DateTime<Utc>,
}
```

- `event_type()` → `"ui_requested"`

## Cockpit HTTP contract

| Method | Path | Response |
|--------|------|----------|
| GET | `/api/agents/stream` | SSE stream, replay ≤1000 buffered events on reconnect |
| POST | `/api/agents/:id/pause` | 202 Accepted |
| POST | `/api/agents/:id/resume` | 202 Accepted |
| POST | `/api/agents/:id/abort` | 202 Accepted |
| POST | `/api/agents/:id/form-submit` | 202 + emit `FormSubmission` on SSE |

## FormSubmission (types.rs)

```rust
FormSubmission {
    task_id: Uuid,
    form_id: String,
    values: serde_json::Value,
}
```

## Renderer contract

- Input: `fn render(&A2UIComponent) -> String` (HTML snippet, escaped user content)
- Fail-closed: unknown variant → `<div class="a2ui-unknown">...</div>`

## File ownership (Wave 2 — zero overlap)

| Worktree | Owns only |
|----------|-----------|
| task2-a2ui-display | `siss-cockpit/src/a2ui/renderer.rs`, handler wiring per HANDOFF Task 3 |
| task1-a2ui-forms | `siss-cockpit/src/a2ui/form_handler.rs` |
| task3-a2ui-validator | `siss-agent-shell/src/a2ui/validator.rs` |

## Exit criteria

- `<200ms` agent emit → cockpit render (integration test, Wave 3)
- Zero new clippy warnings on touched crates
