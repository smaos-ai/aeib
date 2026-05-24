# Phase 74 Specification: Sovereign Agent Networking & Delegation Graph Extensions

## Goal
Extend ReBAC delegation model to support cross-sovereign agent discovery, routing, and capability delegation across multiple independent sovereigns.

## Success Criteria (Verifiable)
- ✅ Agent discovery API implemented (query agents across sovereigns)
- ✅ Cross-sovereign delegation graph working
- ✅ 20+ new tests passing (agent discovery, routing, delegation)
- ✅ All existing 348 tests still passing
- ✅ Integration with Phase 73 cycle healing verified

## Architecture

### Components (Phase 74 Ownership)

1. **agent_discovery.rs** — Service discovery for agents across sovereigns
2. **cross_sovereign_delegation_repo.rs** — Extend delegation graph beyond single tenant
3. **delegation_routing.rs** — Route requests through delegation chains
4. **distributed_consensus.rs** — Prepare for Phase 75+ multi-sovereign consensus

### Data Flow
```
Request from Agent A (Sovereign 1)
    ↓ (lookup via phase-74 routing)
Agent Discovery Service
    ↓ (query)
Find target Agent B (Sovereign 2)
    ↓ (check delegation chain)
Verify Capability Delegation
    ↓ (use Phase 73 API)
Check Cycles & Healing Status
    ↓
Route Request + Execute
```

### Interfaces from Phase 73 (Read-Only)
```rust
// Phase 73 stable API (Phase 74 depends on)
pub fn analyze_cycle(cycle_nodes: Vec<Uuid>, graph: &ReputationGraph) 
    -> Result<ReputationCycle, String>

pub async fn heal_cycle(pool: &PgPool, cycle: ReputationCycle) 
    -> Result<Uuid, String>
```

## Implementation Tasks

### Task 1: Agent Discovery Service
**File:** `crates/siss-graph-db/src/repo/agent_discovery.rs` (NEW)

Create agent registry and discovery:
```rust
pub async fn register_agent(
    pool: &PgPool,
    sovereign_id: Uuid,
    agent_id: Uuid,
    agent_type: &str,
    capabilities: &[String],
) -> Result<(), sqlx::Error>

pub async fn discover_agents(
    pool: &PgPool,
    sovereign_id: Uuid,
    capability_filter: Option<&str>,
) -> Result<Vec<AgentInfo>, sqlx::Error>
```

**Tests:**
- `test_register_agent_succeeds`
- `test_discover_agents_by_capability`
- `test_cross_sovereign_discovery`

### Task 2: Cross-Sovereign Delegation
**File:** `crates/siss-graph-db/src/repo/cross_sovereign_delegation_repo.rs` (NEW)

Extend delegation edges across sovereigns:
```rust
pub async fn create_cross_sovereign_delegation(
    pool: &PgPool,
    source_sovereign: Uuid,
    target_sovereign: Uuid,
    delegated_agent_id: Uuid,
    ceiling_envelope: &str,
) -> Result<Uuid, sqlx::Error>

pub async fn verify_cross_sovereign_path(
    pool: &PgPool,
    source_sovereign: Uuid,
    target_sovereign: Uuid,
) -> Result<bool, sqlx::Error>
```

**Tests:**
- `test_create_cross_sovereign_delegation`
- `test_verify_path_acyclic`
- `test_verify_path_respects_ceiling`

### Task 3: Delegation Routing
**File:** `crates/siss-gatekeeper/src/delegation_routing.rs` (NEW)

Route requests through delegation chains:
```rust
pub async fn route_request(
    pool: &PgPool,
    source_agent: Uuid,
    target_sovereign: Uuid,
    capability: &str,
) -> Result<RoutingDecision, RoutingError>

pub struct RoutingDecision {
    pub path: Vec<Uuid>,  // sovereigns in routing path
    pub allowed: bool,
    pub reason: String,
}
```

**Tests:**
- `test_route_direct_delegation`
- `test_route_transitive_delegation`
- `test_route_blocked_by_cycle`
- `test_route_blocked_by_ceiling`

### Task 4: Integration Tests
**File:** `crates/siss-agent-card/tests/phase_74_agent_networking.rs` (NEW)

End-to-end scenario tests:
1. Two sovereigns, Agent A → Agent B delegation
2. Three-hop chain (A → B → C)
3. Cycle prevention (A → B → A should fail)
4. Ceiling enforcement (request exceeds delegated capability)
5. Concurrent routing from multiple agents

## Phase 74 File Ownership
```
✓ agent_discovery.rs (new, primary)
✓ cross_sovereign_delegation_repo.rs (new, primary)
✓ delegation_routing.rs (new, primary)
✓ tests/phase_74_*.rs (all Phase 74 tests)
  cycle_forensics.rs (read-only, Phase 73)
  cycle_healing_repo.rs (read-only, Phase 73)
```

## Mocking Strategy (Days 1-3)

Until Phase 73 stabilizes, mock the Phase 73 API:
```rust
// mock_cycle_forensics.rs
pub fn mock_analyze_cycle(cycle_nodes: Vec<Uuid>) -> ReputationCycle {
    // Return deterministic mock
}

pub async fn mock_heal_cycle(cycle: ReputationCycle) -> Result<Uuid, String> {
    // Return hardcoded grant ID
}
```

## Integration Week (Day 4-5)

Once Phase 73 publishes v1.0 stable:
1. Replace mocks with real Phase 73 API calls
2. Run full integration test suite
3. Verify cycles detected and healed correctly in cross-sovereign scenarios
4. Document integration points

## Timeline
- **Day 1-2:** Agent discovery service + mocked Phase 73
- **Day 3:** Cross-sovereign delegation + routing (mocked)
- **Day 4:** Integration with Phase 73 real API
- **Day 5:** Full stress tests + documentation

## Phase 75 Dependencies
Phase 74 output (stable agent routing) feeds into:
- **Phase 75:** Distributed consensus for multi-sovereign transactions
- **Phase 76:** Real-time cycle monitoring across sovereigns
- **Phase 77:** Cross-sovereign capability negotiation

## Non-Goals (Phase 74)
- Real-time monitoring (Phase 76)
- Consensus protocols (Phase 75)
- Byzantine fault tolerance (Phase 76+)
- Smart contract integration (Phase 78+)

## Constraints
- Must use Phase 73 cycle detection API (no reimplementation)
- No database schema changes without Phase 73 team review
- All new tables must follow existing naming conventions
- Must remain backward compatible with Phase 73 data model

## Cross-Team Coordination
**Weekly Sync Points:**
- Monday: Phase 73 publishes API contract + mocks
- Wednesday: Phase 74 integration test results
- Friday: Handoff doc + next week priorities

**Blocking Issues Protocol:**
- If Phase 74 discovers Phase 73 API issue → escalate immediately
- If Phase 74 mocking fails → escalate to Phase 73 lead
- Both teams commit to 24hr response time for blockers
