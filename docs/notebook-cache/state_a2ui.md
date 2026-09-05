# A2UI — Execution State & Checkpoints (cached)

**Source:** repo scaffold @ May 20, 2026. Replace with Studio export when available.

## Main branch

| Commit | State |
|--------|-------|
| `aed62d2` | Phase 32 Task 1 DONE — schema, types, mod, `UIRequested` |
| `71b7e85` | `WAVE_2_INITIALIZATION.md` committed |

## Implemented on main

- `crates/siss-agent-shell/src/a2ui/{mod,schema,types}.rs`
- `AgentEvent::UIRequested` in `events/mod.rs`

## Not implemented (Wave 2 targets)

- `validator.rs` (agent pre-emit)
- `siss-cockpit/src/a2ui/{renderer,form_handler}.rs`
- Cockpit SSE handlers (real, not stub)
- `ui/components.js`, `ui/form-handler.js`
- Phase 32 integration tests (Wave 3)

## Worktrees

| Path | Branch | Status |
|------|--------|--------|
| `.claude/worktrees/task1-a2ui-schema` | worktree-task1-a2ui-schema | STALE (superseded by main) |
| `.claude/worktrees/task1-foundation` | worktree-task1-foundation | STALE |
| task1-a2ui-forms | — | **NOT CREATED** |
| task2-a2ui-display | — | **NOT CREATED** |
| task3-a2ui-validator | — | **NOT CREATED** |

## Operator gate

- [x] `docs/notebook-cache/` — 4 artifacts (this commit)
- [ ] Wave 2 dispatch — after `CACHE_COMMITTED` signal
- [ ] Merge order: **display → forms → validator**

## RCE note

A2UI approval forms may pause agent for operator input; resume payload = `FormSubmission`.

## Agent boot checklist

1. Read `.claude/WAVE_2_INITIALIZATION.md`
2. `USE CACHED: @docs/notebook-cache/contract_a2ui.md` (do not re-query NotebookLM)
3. `git status` clean in assigned worktree
4. `cargo check -q` in owned crate only
5. Commit; **do not auto-merge**
