# Night Cycle 12: Project Lick Phase 3A-3B

## Quick Start (9 PM Tonight)

You have **two independent agents** running in parallel. They do not conflict.

### Agent 1: Phase 3A (Confidence Scoring)
```bash
cd /Users/andriileukhin/Documents/SovereignNexus/.claude/worktrees/night-lick-1-confidence

# 1. Read the spec
cat /Users/andriileukhin/Documents/SovereignNexus/.claude/specs/PHASE_3A_CONFIDENCE_SCORING.md

# 2. Run tests (will fail initially)
cargo test --test confidence_scorer

# 3. Implement confidence_scorer.rs (follow TDD: tests → code → refine)
# 4. Make all 5 tests pass
# 5. Write CONFIDENCE_SCORER_REPORT.md
# 6. Commit when done
```

### Agent 2: Phase 3B (Graph Integration)
```bash
cd /Users/andriileukhin/Documents/SovereignNexus/.claude/worktrees/night-lick-2-graph

# 1. Read the spec
cat /Users/andriileukhin/Documents/SovereignNexus/.claude/specs/PHASE_3B_GRAPH_INTEGRATION.md

# 2. Run tests (will fail initially)
cargo test --test graph_builder

# 3. Implement graph_builder.rs (follow TDD: tests → code → refine)
# 4. Make all 5 tests pass
# 5. Write GRAPH_BUILDER_REPORT.md
# 6. Commit when done
```

---

## What They Do

**Phase 3A: Confidence Scoring**
- Computes how confident we are in each fact
- Weighs sources (human=0.95, LLM=0.70, API=0.60, document=0.75)
- Boosts confidence when multiple sources agree
- Detects contradictions and marks old facts as stale
- Applies Ebbinghaus decay (facts fade over 7 days)
- Output: `SemanticFact.confidence_score` field

**Phase 3B: Graph Integration**
- Finds relationships between facts (semantic similarity > 0.80)
- Builds bidirectional graph (no orphans)
- Traverses graph with BFS to find related facts
- Integrates into search ranking (related facts ranked higher)
- Output: `HybridSearchEngine.graph` HashMap

---

## Timeline

| Time | What's Happening |
|------|-----------------|
| 9:00 PM | Both agents start; tests failing (red) |
| 10:30 PM | 50% implementation; 2–3 tests passing per agent |
| 12:00 AM | Implementation complete; 5 tests passing per agent |
| 2:00 AM | Reports written, merkle proofs generated |
| 3:00 AM | Merge to main, full test suite verification |
| 6:00 AM | Ready for user review |

---

## Success = 6 AM Tomorrow

✅ Agent 1: 5 tests passing, CONFIDENCE_SCORER_REPORT.md, merkle_proof.json  
✅ Agent 2: 5 tests passing, GRAPH_BUILDER_REPORT.md, merkle_proof.json  
✅ Merged to main: zero conflicts, all tests green  
✅ Budget: $7–8 spent, $77+ remaining  

---

## Files You Need

**Specs (read these first):**
- `.claude/specs/PHASE_3A_CONFIDENCE_SCORING.md`
- `.claude/specs/PHASE_3B_GRAPH_INTEGRATION.md`

**Implementation files (test-first structure):**
- `crates/siss-context-cartography/tests/confidence_scorer.rs` (tests)
- `crates/siss-context-cartography/src/confidence_scorer.rs` (code stubs)
- `crates/siss-graph-db/tests/graph_builder.rs` (tests)
- `crates/siss-graph-db/src/graph_builder.rs` (code stubs)

**Execution guides:**
- `.claude/reports/night-cycle/NIGHT_CYCLE_PROJECT_LICK_3AB_PLAN.md` (big picture)
- `.claude/reports/night-cycle/NIGHT_CYCLE_3AB_EXECUTION_CHECKLIST.md` (detailed checkpoints)
- `.claude/reports/night-cycle/NIGHT_CYCLE_3AB_LAUNCH.sh` (tmux automation script)

---

## Key Guarantees

🔒 **Zero File Conflicts**
- Agent 1 only touches `siss-context-cartography/`
- Agent 2 only touches `siss-graph-db/`
- Interface: `SemanticFact` struct + `HybridSearchEngine`

🔒 **Deterministic Output**
- Each test verifies reproducibility (run 10x, same result)
- No randomness, no floating-point variance
- Merkle hash proves immutability

🔒 **TDD Structure**
- Tests written first (you'll see 5 failures initially)
- Code implements to make tests pass
- Refine for clarity and performance

---

## Monitoring

**Check progress from another terminal:**
```bash
# See Agent 1 tests
cd /Users/andriileukhin/Documents/SovereignNexus/.claude/worktrees/night-lick-1-confidence
cargo test --test confidence_scorer -- --nocapture 2>&1 | tail -20

# See Agent 2 tests
cd /Users/andriileukhin/Documents/SovereignNexus/.claude/worktrees/night-lick-2-graph
cargo test --test graph_builder -- --nocapture 2>&1 | tail -20

# Check git status in main
cd /Users/andriileukhin/Documents/SovereignNexus
git status
```

---

## What to Do if Tests Fail

1. **Read the test carefully.** What does it expect?
2. **Check your implementation.** Does it match the spec?
3. **Look for edge cases.** Empty lists, duplicates, boundary values?
4. **Verify helper functions.** `semantic_similarity()`, `contradicts()` must be correct.
5. **Determinism issue?** Avoid floating-point exact comparisons; use ranges.

---

## Morning Handoff (6 AM)

You'll have:
- 10 passing tests (5 + 5)
- 2 detailed reports
- 2 merkle proofs
- Clean merge to main
- Ready for next phase (3C: Auto-crystallizing, or 3D: Contradiction detection)

---

## Budget Check

**Starting:** $85.52  
**Estimated burn:** $7–8  
**Estimated end:** $77–78  

Check actual at: https://console.anthropic.com/account/billing/overview

---

## Good luck! 🚀

Two agents. Six hours each. Zero conflicts. Full intelligence layer for Project Lick.

**Start time:** 9:00 PM May 27, 2026  
**Target end:** 6:00 AM May 28, 2026  

Go.
