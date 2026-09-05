# STATE.md Template — Compressed Checkpoint Format

## Minimum Viable Checkpoint

```markdown
# Execution State (Auto-Resumable)

## Checkpoint
- **Commit:** [HASH] [message]
- **Timestamp:** [ISO8601]
- **Phase:** [name]
- **Status:** [RED|GREEN|REFACTOR|MERGED]

## Context (3 Lines Max)
[What are we building? Why?]

## Last Action
[What was just completed?]

## Next Step
[What comes next?]

## Blockers (if any)
[What's preventing progress?]

## Test Status
[X/Y tests passing. Failures: [...]]

## Modified Files (Scope)
- [relative paths only, @file scoping]

## Git Command (Resume)
```
git checkout [branch]
git pull origin main
cargo test --lib
```
```

---

## Compressed Encoding (Session-Local)

Use this template to checkpoint after EACH meaningful phase:

```
# After RED Phase
Commit: 83979c3
Status: RED (38 tests created, all #[ignore])
Next: Implement handlers and hooks (GREEN phase)

# After GREEN Phase
Commit: 11dfc03
Status: GREEN (22 tests passing + 0 new failures)
Next: Implement SQL queries (REFACTOR phase)

# After REFACTOR Phase
Commit: cfb8d11
Status: REFACTOR (14 integration tests passing)
Next: Manual verification + merge to main
```

---

## Why This Works

1. **No redundancy:** Only encode what changed, not the full context
2. **Git as backup:** If STATE.md is lost, git log recovers everything
3. **Resume-safe:** Read STATE.md → cargo test → understand blockers in 30 seconds
4. **Token-efficient:** 10 lines instead of 100

---

## Canonical Fields

| Field | Purpose | Example |
|-------|---------|---------|
| Commit | Exact git hash + message | `5ec1c19 fix: resolve RawObservation import` |
| Timestamp | When state was captured | `2026-05-21T01:30:00Z` |
| Phase | Development phase | `RED`, `GREEN`, `REFACTOR`, `MERGED` |
| Status | Current state signal | `ALL_TESTS_PASSING`, `4_BLOCKERS`, `READY_FOR_REVIEW` |
| Test Status | Quantified pass/fail | `331 passed; 17 failed; 0 ignored` |
| Next Step | Explicit action for next session | "Implement SQL queries for projections" |
| Blockers | What's preventing forward motion | "Database schema missing column X" |

---

## Anti-Patterns

❌ **DO NOT:** Write full context (that's what git log is for)
❌ **DO NOT:** Describe every change (use git diff)
❌ **DO NOT:** Include error messages (they rot)
✅ **DO:** Point to line numbers if ambiguous
✅ **DO:** Update Commit after every merge
✅ **DO:** Keep Next Step actionable

---

## Example: Phase 24 Task 1 Checkpoint

```markdown
# Execution State

## Checkpoint
- **Commit:** cfb8d11 phase-24-task-1(refactor): implement real SQL queries with testcontainers
- **Timestamp:** 2026-05-21T01:22:00Z
- **Phase:** Phase 24 Task 1 (Real-Time Projections)
- **Status:** GREEN + REFACTOR (14/14 integration tests passing)

## Context
Implemented real SQL queries for /api/graph/projections/* endpoints using Phase 23 schemas.
All 38 tests passing (22 backend + 11 frontend + 5 handler tests).
Ready for: Manual server verification + merge to main.

## Last Action
Implemented fetch_agent_actions(), fetch_anomalies(), fetch_recovery() with testcontainers PostgreSQL.
Un-ignored Test Suite 8, verified 14 integration tests pass.

## Next Step
Boot siss-cockpit server (cargo run -p siss-cockpit).
Manual curl tests: GET /api/graph/projections/{agent-actions|anomalies|recovery}?sovereign_id=[UUID]

## Test Status
- Backend: 331 passed, 17 failed (pre-existing), 0 ignored
- Phase 24 contribution: +14 tests passing
- Frontend: 11 tests (pending npm test)
- Handler: 6 tests (passing)

## Modified Files (Scope)
- crates/siss-graph-db/src/repo/projections_repo.rs
- crates/siss-graph-db/src/repo/projections_repo_integration_tests.rs
- crates/siss-cockpit/src/handlers/projections.rs
- crates/demo-app/src/hooks/useProjections.ts

## Blockers
None. All tests passing. Ready for production integration.
```

