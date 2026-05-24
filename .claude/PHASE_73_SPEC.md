# Phase 73 Specification: Core Infrastructure & Cycle Healing Determinism

## Goal
Stabilize ReBAC cycle detection and healing mechanisms with guaranteed deterministic behavior. All weakest-link selections must produce identical results across runs.

## Success Criteria (Verifiable)
- ✅ Zero non-deterministic cycle healing behavior (verified by 10x repeat tests)
- ✅ All 348 tests still passing
- ✅ Lexicographic tiebreaking implemented for identical ceiling_tier values
- ✅ Cycle forensics API documented and stable
- ✅ Integration tests prove determinism across different execution contexts

## Architecture

### Core Components
1. **reputation_graph.rs** — Graph node/edge management (READ-ONLY for Phase 73)
2. **cycle_forensics.rs** — Cycle analysis, severity scoring, weakest-link detection
3. **cycle_healing_repo.rs** — Cycle revocation with deterministic grant selection

### Data Flow
```
Reputation Graph
    ↓ (query)
Find Cycles (SCCs)
    ↓ (analyze)
Weakest Link [DETERMINISTIC]
    ↓
Severity Scoring
    ↓
Healing Strategy (revoke weakest link grant)
    ↓
Revoke & Verify
```

### Determinism Guarantee
When multiple edges in a cycle have identical `ceiling_tier`:
- Sort by ceiling_tier (ascending)
- Tiebreak by destination node UUID (lexicographic)
- Always select first (lowest UUID) as weakest link source

## Implementation Tasks

### Task 1: Update cycle_forensics.rs
**File:** `crates/siss-graph-db/src/repo/cycle_forensics.rs`

Modify `analyze_cycle()` to use lexicographic tiebreaking:
```rust
// When ceiling_tier values are equal, use destination UUID as tiebreaker
if edge.ceiling_tier < weakest_link_ceiling
    || (edge.ceiling_tier == weakest_link_ceiling 
        && edge.to_sovereign < weakest_dest_id) {
    weakest_link_ceiling = edge.ceiling_tier;
    weakest_link_id = *node_id;
    weakest_dest_id = edge.to_sovereign;
}
```

**Tests:**
- `test_weakest_link_tiebreaker_identical_ceilings` — Verify tiebreaking works
- `test_determinism_10x_repeat` — Run same cycle analysis 10 times, identical results

### Task 2: Update cycle_healing_repo.rs
**File:** `crates/siss-graph-db/src/repo/cycle_healing_repo.rs`

Ensure grant revocation follows deterministic order:
- Sort candidates by UUID before selection
- Document the selection algorithm

**Tests:**
- `test_heal_cycle_deterministic_revocation` — Verify same grant revoked each time

### Task 3: Integration Tests
**File:** `crates/siss-graph-db/tests/phase_73_cycle_determinism.rs`

Create comprehensive determinism suite:
1. 3-node cycle with identical ceiling tiers
2. 5-node cycle with mixed tiers
3. Large cycle (10+ nodes) with multiple tiebreakers
4. Concurrent execution stress test (10 parallel runs)

## Phase 73 → Phase 74 Interface

**Stable API (exported):**
```rust
pub fn analyze_cycle(cycle_nodes: Vec<Uuid>, graph: &ReputationGraph) 
    -> Result<ReputationCycle, String>

pub async fn heal_cycle(pool: &PgPool, cycle: ReputationCycle) 
    -> Result<Uuid, String>  // returns revoked_grant_id
```

**Contract:**
- `analyze_cycle()` must return identical `ReputationCycle` for same inputs
- `heal_cycle()` must revoke the same grant ID given same `ReputationCycle`
- No randomness in selection; UUID ordering is authoritative

## File Ownership (Phase 73 Team)
```
✓ cycle_forensics.rs (primary)
✓ cycle_healing_repo.rs (primary)
  reputation_graph.rs (read-only)
✓ tests/phase_73_*.rs (all Phase 73 tests)
```

## Phase 74 Dependencies
Phase 74 will mock these Phase 73 APIs initially and integrate once stable:
- `analyze_cycle()` — needed for cross-sovereign cycle detection
- `heal_cycle()` — needed for distributed healing

## Timeline
- **Day 1-2:** Implement tiebreaking + unit tests
- **Day 3:** Integration tests + stress testing
- **Day 4:** Documentation + API review
- **Day 5:** Publish `v1.0` stable interface for Phase 74

## Non-Goals (Phase 74+)
- Cross-sovereign cycle detection (Phase 74)
- Distributed consensus healing (Phase 75+)
- Real-time cycle monitoring (Phase 76+)

## Constraints
- Must not modify database schema (use existing `ceiling_tier` column)
- All changes must be backward compatible
- No external dependencies beyond current Cargo.toml
