# A2UI — Dependency Map (cached)

**Source:** repo scaffold from `aed62d2` + HANDOFF-PHASE32. Replace with Studio export when available.

## Upstream (emit path)

- `siss-agent-shell/src/a2ui/schema.rs` — `A2UIComponent` (18 primitives, serde tag=`type`)
- `siss-agent-shell/src/a2ui/types.rs` — `FormSubmission`, `A2UIResponse`
- `siss-agent-shell/src/events/mod.rs` — `AgentEvent::UIRequested { task_id, components, form_id?, timestamp }`
- Dispatcher / executor — emits `UIRequested` on agent UI intent (no dispatcher changes in Phase 32 delta)

## Downstream (consume path)

- `siss-cockpit/src/a2ui/renderer.rs` — **CREATE** JSON → HTML (Task 2 / task2-a2ui-display)
- `siss-cockpit/src/a2ui/form_handler.rs` — **CREATE** operator submit → SSE back (Task 1 / task1-a2ui-forms)
- `siss-cockpit/src/handlers/stream.rs` — SSE `GET /api/agents/stream` (extend, do not fork pattern)
- `siss-cockpit/src/handlers/control.rs` — pause/resume/abort (existing skeleton)
- `siss-cockpit/ui/components.js`, `form-handler.js` — **CREATE** (HANDOFF Task 4; optional Wave 3)
- `siss-agent-shell/src/a2ui/validator.rs` — **CREATE** pre-emit fail-closed (Task 3 / task3-a2ui-validator)

## Reference pattern (clone, do not import)

- `siss-enclave/src/api/ag_ui.rs` — `broadcast::Sender`, buffer, `async_stream`, Axum `Sse::new`
- `siss-enclave/src/api/router.rs` — route wiring

## Blast radius

| Change | Risk |
|--------|------|
| `schema.rs` enum shape | **CRITICAL** — breaks serde + renderer + validator |
| `UIRequested` fields | **HIGH** — SSE consumers |
| New cockpit files only | **LOW** — file-orthogonal Wave 2 |

## GitNexus rule

Run `gitnexus_impact` before editing `A2UIComponent`, `UIRequested`, or `AgentEvent`.
