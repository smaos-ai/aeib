# Night Cycle: Project Lick Phase 3A-3B Launch Plan

**Date:** May 27, 2026  
**Timeline:** 9pm May 27 → 6am May 28  
**Budget:** $85.52 remaining  
**Est. Cost:** $12–16 (based on Cycles 1-11 costs)  
**Execution:** Two parallel agents (zero file overlap)  

---

## Scope Clarity

### Project Lick Status
- **60% Complete:** Data structures, search engine, Ebbinghaus decay, hybrid ranking
- **40% Missing:** Confidence scoring algorithm + graph integration

### Phase 3A: Confidence Scoring Engine
**Files:** `crates/siss-context-cartography/src/confidence_scorer.rs` (new)  
**Tests:** `crates/siss-context-cartography/tests/confidence_scorer.rs` (new)  
**Owner:** night-lick-1 (worktree-night-lick-1-confidence)

**5 Tests:**
1. Source trust weights vary by type (Human=0.95, LLM=0.70, API=0.60, Document=0.75)
2. Corroboration increases confidence (multi-source boost up to +0.15)
3. Contradiction marks fact stale (supersession chain creation)
4. Temporal decay with Ebbinghaus (7-day lambda, exponential falloff)
5. Deterministic calculation (no variance, 100x reproducibility)

**Deliverables:**
- confidence_scorer.rs (100-150 lines)
- 5 passing tests
- CONFIDENCE_SCORER_REPORT.md
- merkle_proof.json (SHA256 of test output)

---

### Phase 3B: Graph Integration & Search Wiring
**Files:** `crates/siss-graph-db/src/graph_builder.rs` (new)  
**Tests:** `crates/siss-graph-db/tests/graph_builder.rs` (new)  
**Owner:** night-lick-2 (worktree-night-lick-2-graph)

**5 Tests:**
1. Relationship extraction finds relevant pairs (>0.80 similarity threshold)
2. Graph insertion maintains bidirectional links (no orphans)
3. Graph traversal returns ranked neighbors (BFS by relevance)
4. Search ranking incorporates graph relevance (related facts boosted)
5. Deterministic graph construction (identical structure 10x runs)

**Deliverables:**
- graph_builder.rs (150-200 lines)
- 5 passing tests
- GRAPH_BUILDER_REPORT.md
- merkle_proof.json (SHA256 of test output)

---

## Parallel Architecture (Zero Conflicts)

| Component | Ownership | Files | Input | Output |
|-----------|-----------|-------|-------|--------|
| **3A: Confidence** | night-lick-1 | siss-context-cartography | SemanticFact list | confidence_score computed |
| **3B: Graph** | night-lick-2 | siss-graph-db | SemanticFact list | graph HashMap built |
| **Integration Point** | HybridSearchEngine.search() | siss-context-cartography | Both outputs | merged ranking |

**Key:** Each agent owns isolated crate. Interface is SemanticFact struct and HybridSearchEngine (both already exist).

---

## Timeline

| Time | Phase 3A (night-lick-1) | Phase 3B (night-lick-2) |
|------|------------------------|------------------------|
| 9:00pm | Setup worktree, review spec | Setup worktree, review spec |
| 9:15pm | Tests failing (red) | Tests failing (red) |
| 10:30pm | 50% implementation (2-3 tests pass) | 50% implementation (2-3 tests pass) |
| 12:00am | Implementation complete, refine | Implementation complete, refine |
| 1:00am | All 5 tests passing, report generation | All 5 tests passing, report generation |
| 2:00am | Merkle hash verification, final commit | Merkle hash verification, final commit |
| 6:00am | User review phase |  |

---

## Success Criteria

### For Each Agent
✓ All 5 tests passing  
✓ Zero warnings from `cargo clippy`  
✓ Zero `cargo check` errors  
✓ Deterministic output (reproducible scores, identical graphs)  
✓ Report written (CONFIDENCE_SCORER_REPORT.md or GRAPH_BUILDER_REPORT.md)  
✓ Merkle hash verified  

### Integration
✓ Phase 3A output (confidence_score) feeds Phase 3B (used in relationship weighting)  
✓ Phase 3B output (graph HashMap) integrates into HybridSearchEngine.search()  
✓ No file conflicts (git merge clean)  
✓ Full test suite passes: `cargo test -p siss-context-cartography && cargo test -p siss-graph-db`  

---

## Cost Projection

**Baseline (from Cycles 1-11):**
- Per-agent cost: $2–4 (depending on implementation complexity)
- Parallel discount: -20% (shared context, no sequential overhead)
- Infrastructure (CI, merge): $1–2

**Estimate:**
- night-lick-1 (Confidence): $2.50
- night-lick-2 (Graph): $3.00
- Merge + Report: $1.50
- **Total:** ~$7–8 (leaving $77+ cushion at $85.52 start)

---

## Worktrees Created

```
.claude/worktrees/night-lick-1-confidence
  └─ branch: worktree-night-lick-1-confidence
  
.claude/worktrees/night-lick-2-graph
  └─ branch: worktree-night-lick-2-graph
```

Both branches will merge back to `main` after testing.

---

## Launch Command (for tmux)

See NIGHT_CYCLE_3AB_LAUNCH.sh (below)

---

## Post-Cycle Actions (6:00am+)

1. **Verify Merge:** Check git diff between main and both branches
2. **Full Test Suite:** Run `cargo test` on main
3. **Generate Report:** Create NIGHT_CYCLE_3AB_COMPLETION.md
4. **Investor Readiness:** LLM Wiki v2 now 80% complete (intelligence layer done)
5. **Next Cycle Planning:** Phase 3C (Auto-crystallizing sessions) or Phase 3D (Contradiction detection post-write)

---

## Known Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Network similarity heuristic breaks on domain-specific text | Scope to English, document limitations |
| Graph traversal depth explosion | Cap max_depth=2, relevance threshold >0.1 |
| Confidence score variance in Ebbinghaus decay | Use fixed timestamp for test reproducibility |
| Merge conflicts if both agents touch HybridSearchEngine | Agent 3A doesn't touch search; 3B only adds graph integration |

---

## Deferred (Post-v2.2)

- Phase 3C: Auto-crystallizing sessions into knowledge
- Phase 3D: Contradiction detection on write
- Phase 3E: Multi-agent knowledge scoping
- Relationship strength decay, visualization, export
- Recursive contradiction handling
