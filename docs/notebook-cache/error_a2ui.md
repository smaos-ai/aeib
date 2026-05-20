# A2UI — Failure Modes & Validation (cached)

**Source:** repo scaffold. Replace with Studio export when available.

## Fail-closed gates (mandatory)

1. **Pre-emit (agent):** `A2UIComponent::validate()` → `Err(ValidationError)` blocks SSE emit
2. **Post-receive (cockpit):** unknown `type` → graceful HTML fallback, no panic
3. **Form submit:** reject empty `id` on Input/Select/Checkbox/Radio; reject malformed JSON body

## ValidationError (validator.rs)

- `MissingId(component_name)`
- `MissingLabel(component_name)`
- `InvalidValue(detail)`

## Required fields by primitive

| Component | Required |
|-----------|----------|
| Input, Textarea, Select, Checkbox, Radio, Button, Modal | non-empty `id` |
| Input, Textarea, Select, Checkbox, Radio, Button | non-empty `label` |
| Select, Radio | non-empty `options` |
| Card, Grid, Modal | valid nested `children` (recursive validate) |
| Table | `headers.len() == row[i].len()` for all rows |
| Progress | `max > 0`, `value <= max` |

## Common failure modes

- **Empty form id** — operator submission cannot route to agent
- **>18 custom types** — reject; enum is ceiling, no `custom_widget` in Phase 32
- **Recursive depth bomb** — Card/Grid/Modal children: cap depth in validator (recommend max 8)
- **SSE buffer overflow** — CockpitState buffer max 1000 events; drop oldest
- **Merge conflict** — two agents touch same file → violates Golden Rule

## Tests before merge (per worktree)

```bash
cargo check -p siss-agent-shell   # validator
cargo check -p siss-cockpit       # renderer + form_handler
cargo clippy -p siss-agent-shell -p siss-cockpit -- -D warnings
```

## Chaos / safety

- Firewall still applies to agent output; A2UI does not bypass `siss-behavioral-firewall`
- Form payloads are `serde_json::Value` — validate schema before forwarding to agent
