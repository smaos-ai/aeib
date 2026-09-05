# Night Cycle 12: Project Lick Phase 3A-3B — Execution Checklist

**Launch Time:** 9:00 PM May 27, 2026  
**Target Completion:** 6:00 AM May 28, 2026  
**Budget Start:** $85.52  
**Est. Cost:** $7–8 (leaving $77+ buffer)  

---

## Pre-Launch (Now)

- [x] Specs written (Phase 3A + 3B)
- [x] Test files created (10 tests total, TDD structure)
- [x] Implementation stubs (confidence_scorer.rs + graph_builder.rs)
- [x] Worktrees created (night-lick-1-confidence + night-lick-2-graph)
- [x] lib.rs updated (both crates export modules)
- [x] Plan documented (NIGHT_CYCLE_PROJECT_LICK_3AB_PLAN.md)

---

## Agent 1: Phase 3A (Confidence Scoring)

**Worktree:** `.claude/worktrees/night-lick-1-confidence`  
**Duration:** 9pm → 3am (6 hours)  
**Owner:** night-lick-1

### Checkpoint 1: Tests Red (9:15pm)
```bash
cd /Users/andriileukhin/Documents/SovereignNexus/.claude/worktrees/night-lick-1-confidence
cargo test --test confidence_scorer
# Expected: 5 failures (tests not yet implemented)
```

**Deliverable:** Screenshot or log showing 5 failing tests

### Checkpoint 2: Implementation in Progress (10:30pm)
```bash
# Implement confidence_scorer.rs:
# - compute_source_weight(SourceType) → f64
# - compute_corroboration_boost(count) → f64
# - detect_contradiction(fact, existing) → Option<Uuid>
# - calculate_confidence(sources, existing) → (f64, Option<Uuid>)
# - semantic_similarity() helper
# - contradicts() helper

cargo test --test confidence_scorer
# Expected: 2–3 tests passing
```

**Deliverable:** At least 3 tests passing

### Checkpoint 3: All Tests Passing (1:00am)
```bash
cargo test --test confidence_scorer -- --nocapture
# Expected: 5 tests passing, 100% pass rate

cargo clippy --test confidence_scorer
# Expected: 0 warnings

cargo check -p siss-context-cartography
# Expected: 0 errors
```

**Deliverable:** All 5 tests green, zero clippy warnings

### Checkpoint 4: Report & Merkle Verification (2:00am)
```bash
# Create CONFIDENCE_SCORER_REPORT.md:
# - What was implemented
# - Which tests passed
# - Confidence calculation algorithm summary
# - Key metrics (determinism, performance)

# Generate merkle proof:
# SHA256(test_run.json) → merkle_proof.json

# Commit:
git add -A
git commit -m "Phase 3A: Confidence Scoring Engine — 5/5 tests passing"
```

**Deliverable:** CONFIDENCE_SCORER_REPORT.md + merkle_proof.json

---

## Agent 2: Phase 3B (Graph Integration)

**Worktree:** `.claude/worktrees/night-lick-2-graph`  
**Duration:** 9pm → 3am (6 hours, parallel with Agent 1)  
**Owner:** night-lick-2

### Checkpoint 1: Tests Red (9:15pm)
```bash
cd /Users/andriileukhin/Documents/SovereignNexus/.claude/worktrees/night-lick-2-graph
cargo test --test graph_builder
# Expected: 5 failures (tests not yet implemented)
```

**Deliverable:** Screenshot or log showing 5 failing tests

### Checkpoint 2: Implementation in Progress (10:30pm)
```bash
# Implement graph_builder.rs:
# - extract_relationships(facts) → Vec<GraphRelationship>
# - determine_relationship_type(fact_a, fact_b) → RelationType
# - build_graph(relationships) → HashMap<Uuid, Vec<(Uuid, f64)>>
# - traverse_graph(root_id, graph, max_depth) → Vec<(Uuid, f64)>
# - semantic_similarity() helper

cargo test --test graph_builder
# Expected: 2–3 tests passing
```

**Deliverable:** At least 3 tests passing

### Checkpoint 3: All Tests Passing (1:00am)
```bash
cargo test --test graph_builder -- --nocapture
# Expected: 5 tests passing, 100% pass rate

cargo clippy --test graph_builder
# Expected: 0 warnings

cargo check -p siss-graph-db
# Expected: 0 errors
```

**Deliverable:** All 5 tests green, zero clippy warnings

### Checkpoint 4: Report & Merkle Verification (2:00am)
```bash
# Create GRAPH_BUILDER_REPORT.md:
# - What was implemented
# - Which tests passed
# - Relationship extraction algorithm summary
# - Graph traversal performance metrics

# Generate merkle proof:
# SHA256(test_run.json) → merkle_proof.json

# Commit:
git add -A
git commit -m "Phase 3B: Graph Integration & Search Wiring — 5/5 tests passing"
```

**Deliverable:** GRAPH_BUILDER_REPORT.md + merkle_proof.json

---

## Integration & Final Verification (3am–6am)

### Merge Phase 3A + 3B to main
```bash
# Back in main directory
git checkout main
git merge worktree-night-lick-1-confidence
git merge worktree-night-lick-2-graph
# Expected: 0 conflicts (file-orthogonal by design)
```

**Deliverable:** Clean merge with no conflicts

### Full Test Suite
```bash
cargo test -p siss-context-cartography --test confidence_scorer
# Expected: 5 passing

cargo test -p siss-graph-db --test graph_builder
# Expected: 5 passing

cargo test
# Expected: all tests in workspace passing (or at least no new failures)
```

**Deliverable:** 10 tests passing (5 + 5), zero regressions

### Clippy & Check
```bash
cargo clippy
# Expected: 0 new warnings

cargo check
# Expected: 0 errors
```

**Deliverable:** Zero clippy warnings, clean check

### Generate Final Report (5:00am)
```markdown
# Night Cycle 12: Project Lick Phase 3A-3B — Completion Report

## Summary
- Phase 3A: Confidence Scoring Engine — ✅ 5/5 tests passing
- Phase 3B: Graph Integration & Search Wiring — ✅ 5/5 tests passing
- Total: 10 tests, 100% pass rate, zero data loss

## Metrics
- Execution time: 8 hours
- Actual cost: $X.XX (see Anthropic console)
- Remaining budget: $Y.YY
- Code lines added: 250–300 (estimate)

## Integration
- Confidence scores computed by Phase 3A
- Graph relationships built and traversed by Phase 3B
- HybridSearchEngine.search() now uses both
- Deterministic output verified 10x

## Next Steps
1. Review both reports: CONFIDENCE_SCORER_REPORT.md + GRAPH_BUILDER_REPORT.md
2. Verify merkle proofs match
3. Decide on Phase 3C (Auto-crystallizing) or Phase 3D (Contradiction detection on write)
4. Schedule Phase 13 (if continuing)

## Investor Value
- Project Lick v2.2 now 80% complete
- Intelligence layer implemented (confidence + graph)
- Self-improving knowledge loop foundation ready
- Production-grade determinism verified

**Status:** PRODUCTION READY FOR DEPLOYMENT
```

**Deliverable:** NIGHT_CYCLE_12_COMPLETION_REPORT.md

---

## Success Criteria Summary

### At 6:00 AM, You Should Have:

✅ **10 Passing Tests**
- 5 from Phase 3A (confidence_scorer)
- 5 from Phase 3B (graph_builder)

✅ **Two Clean Reports**
- CONFIDENCE_SCORER_REPORT.md
- GRAPH_BUILDER_REPORT.md

✅ **Merkle Verification**
- merkle_proof.json for each phase
- SHA256 hashes match test output

✅ **Clean Merge**
- Both branches merged to main
- Zero conflicts
- Full test suite passes

✅ **Code Quality**
- Zero clippy warnings
- Zero check errors
- Deterministic output verified

✅ **Cost Within Budget**
- Estimated $7–8 spent
- $77+ remaining for future cycles

---

## If Issues Arise

### Test Failing
1. Read error message carefully
2. Check the implementation against the test expectation
3. Verify helper functions (semantic_similarity, contradicts)
4. Ensure no floating-point comparison issues (use ranges, not exact equality)

### Merge Conflict
- **Expected:** NONE (file-orthogonal design)
- **If it happens:** Inspect git diff, manually resolve in favor of spec

### Budget Overrun
- Stop and report actual spend
- Don't proceed to next cycle without approval

### Time Running Behind
- Prioritize: tests → code → polish
- Skip polish if time is tight
- Report on schedule in morning brief

---

## Morning Handoff (6:00 AM)

**User Review:**
1. Read NIGHT_CYCLE_12_COMPLETION_REPORT.md
2. Check both detailed reports
3. Verify merkle hashes
4. Decide next phase (3C, 3D, or different direction)

**Expected Time:** 10 minutes

**Outcome:** Either
- ✅ Deploy to staging for integration testing
- ⏳ Schedule Phase 13 for next night
- 🔄 Fix issues and re-run (only if tests failed)

---

**Let the night cycle begin. Agents are staged and ready. 🚀**
