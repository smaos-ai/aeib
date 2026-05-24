# Parallel Execution Guide: Phase 73 & 74

## Quick Start

**Team A (Phase 73):**
```bash
cd /Users/andriileukhin/Documents/SovereignNexus/.claude/worktrees/phase-73-cycle-healing
# Read spec: cat ../../PHASE_73_SPEC.md
# Start: Enter Plan Mode (Shift+Tab)
cargo test --all  # Verify baseline (348/348)
```

**Team B (Phase 74):**
```bash
cd /Users/andriileukhin/Documents/SovereignNexus/.claude/worktrees/phase-74-agent-networking
# Read spec: cat ../../PHASE_74_SPEC.md
# Start: Enter Plan Mode (Shift+Tab)
cargo test --all  # Verify baseline (348/348)
```

## File Ownership Matrix

| File | Phase 73 | Phase 74 | Status |
|------|----------|----------|--------|
| cycle_forensics.rs | ✅ Primary | 🔒 Read-only | Stable API |
| cycle_healing_repo.rs | ✅ Primary | 🔒 Read-only | Stable API |
| reputation_graph.rs | 🔒 Read-only | 🔒 Read-only | Frozen |
| agent_discovery.rs | — | ✅ Primary (NEW) | New file |
| cross_sovereign_delegation_repo.rs | — | ✅ Primary (NEW) | New file |
| delegation_routing.rs | — | ✅ Primary (NEW) | New file |

**Rule:** Each team owns its files exclusively. If Phase 74 needs Phase 73 data, use its public API.

## Coordination Checkpoints

### Day 1 (Monday)
- ✅ Both teams read specs
- ✅ Both teams enter Plan Mode and draft implementation plans
- ✅ Cross-team review of plans (30 min sync)
- ⏹️ Both teams get plan approval

### Day 2-3 (Tue-Wed)
- Phase 73: Implement cycle_forensics.rs + unit tests
- Phase 74: Create agent_discovery.rs (with mocked Phase 73 API)
- **No blockers expected** (Phase 73 API not needed yet)

### Day 4 (Thursday)
- Phase 73: Complete cycle_healing_repo.rs, publish v1.0 stable interface
- Phase 74: Replace mocks with Phase 73 real API, integration tests
- **Sync point:** 10 min call to verify integration

### Day 5 (Friday)
- Phase 73: Stress tests, finalize, write HANDOFF.md
- Phase 74: Full integration test suite, finalize, write HANDOFF.md
- **Wrap-up:** Both teams commit to main with handoff docs

## Preventing Cache Collisions

**⚠️ CRITICAL:** Both teams must follow this to avoid tanking performance:

```bash
# In ~/.claude/settings.json (DISABLE AUTO-MEMORY)
{
  "memory": {
    "enabled": false
  }
}
```

**Why?** Both parallel sessions share the same `MEMORY.md`. If one writes, it invalidates the other's prompt cache.

**Instead:** Use explicit handoff docs at end of day.

## Merge Conflict Prevention

```bash
# Team A branch: phase-73-cycle-healing
# Team B branch: phase-74-agent-networking

# No overlapping files = no conflicts
# Both branches merge cleanly to main after Day 5
```

## Handoff Document Template

**At end of each day (or session), each team writes:**

```markdown
# Phase 73 Handoff (Day X)

## Completed
- ✅ cycle_forensics.rs tiebreaking implemented
- ✅ 8/10 unit tests passing
- ✅ Mock integration test setup

## In Progress
- Strengthening determinism test suite

## Blockers
- None

## Next Steps (for next session)
- Implement cycle_healing_repo.rs deterministic revocation
- Add stress tests (10x repeat runs)

## API Status
- `analyze_cycle()` → **STABLE** (v1.0)
- `heal_cycle()` → **IN PROGRESS**
```

## Real-Time Communication

| Issue | Channel | Response Time |
|-------|---------|----------------|
| Quick question | GitHub Discussion | 1 hour |
| Code review needed | GitHub PR comment | 2 hours |
| **BLOCKER** | Slack/Signal | 15 min |
| API change | Team sync call | Immediate |

## Test Success Criteria

### Phase 73 Exit Criteria
```bash
cargo test --all
# Must show:
# - 348 passed (all existing tests still pass)
# - 10+ new Phase 73 tests passing
# - 0 failures
# - Determinism verified (10x repeat tests)
```

### Phase 74 Exit Criteria
```bash
cargo test --all
# Must show:
# - 348 passed (all existing tests still pass)
# - 20+ new Phase 74 tests passing
# - 0 failures
# - Integration with Phase 73 API verified
```

## Rollback Plan

If either team gets stuck:

**Option A:** Revert to single-phase execution
```bash
git checkout main
# Both teams work sequentially instead
```

**Option B:** Isolate blocker
```bash
# If Phase 74 blocked on Phase 73 API:
# Phase 74 continues with mocks, Phase 73 fixes and publishes hotfix
```

## Success Metrics

By end of Day 5:
- [ ] Phase 73: 348 + 10+ tests passing, determinism verified
- [ ] Phase 74: 348 + 20+ tests passing, integration verified
- [ ] Zero conflicts during merge to main
- [ ] Both handoff docs written and reviewed
- [ ] Phase 75 can start Monday (no tech debt)

## Important Notes

1. **Disables on first day failure** → Both teams pivot to sequential execution
2. **One blocker = immediate escalation** → Don't wait until Day 5
3. **Cache is team's responsibility** → Disable auto-memory proactively
4. **File ownership is sacred** → No exceptions without explicit approval
5. **Public APIs are contracts** → Phase 73 team cannot break Phase 74's mocks

---

**TL;DR:**
- Phase 73 team: Owns cycle_* files, publishes stable API
- Phase 74 team: Owns agent_* files, mocks Phase 73, integrates Day 4
- No shared files = no conflicts
- Disable auto-memory globally = cache stays fast
- Daily handoff docs = context stays clean
