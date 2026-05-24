# Phase 77 Specification: Cross-Sovereign Capability Negotiation & Transitive Delegation

## Goal
Implement capability negotiation protocol across sovereigns with automatic transitive delegation and ceiling tier validation. Enable dynamic capability grants that respect cycle healing and consensus constraints.

## Dependencies
- **Phase 73:** Cycle healing determinism ✅ (v1.0 API)
- **Phase 74:** Agent discovery & routing ✅ (v1.0 API)
- **Phase 75:** Distributed consensus ✅ (v1.0 API with ledger)
- **Phase 76:** Leader election & monitoring ✅ (v1.0 API)
- **Blocks:** Phase 78, 79

## Success Criteria (Verifiable)
- ✅ Capability negotiation protocol implemented (multi-round handshake)
- ✅ Transitive delegation working (A → B → C chains)
- ✅ Ceiling tier enforcement (no capability escalation)
- ✅ 20+ new tests passing
- ✅ All 348+ existing tests still passing
- ✅ Conflict resolution verified (competing requests handled deterministically)

## Architecture

### Components (Phase 77 Ownership)

1. **capability_negotiation.rs** — Multi-round capability request/grant protocol
2. **transitive_delegation_repo.rs** — Transitive chain validation and extension
3. **ceiling_enforcement.rs** — Dynamic ceiling tier checking
4. **capability_grant_ledger.rs** — Immutable record of granted capabilities

### Data Flow
```
Agent A Requests Capability (cross-sovereign)
    ↓ (via Phase 74 routing)
Leader Receives Request
    ↓ (via Phase 76 elected leader)
Verify Cycle Safety (Phase 73)
    ↓
Check Delegation Chain (Phase 74)
    ↓
Validate Ceiling Tier
    ↓
Propose Capability Grant (via Phase 75 consensus)
    ↓
2/3+ Sovereigns Agree
    ↓ (via Phase 75 consensus ledger)
Record Grant (Phase 77 ledger)
    ↓
Notify Agent A
    ↓
Capability Active
```

### Interfaces from Phase 73, 74, 75, 76 (Read-Only)
```rust
// Phase 73 API
pub fn analyze_cycle(cycle_nodes: Vec<Uuid>, graph: &ReputationGraph) 
    -> Result<ReputationCycle, String>

// Phase 74 API
pub async fn verify_cross_sovereign_path(pool: &PgPool, 
    source_sovereign: Uuid, target_sovereign: Uuid) 
    -> Result<bool, sqlx::Error>

// Phase 75 API
pub async fn propose_transaction(pool: &PgPool,
    transaction: MultiSovereignTransaction, proposer: Uuid) 
    -> Result<ConsensusProposal, ConsensusError>

// Phase 76 API
pub async fn get_current_view(pool: &PgPool, sovereign_id: Uuid)
    -> Result<(Uuid, u64), ConsensusError>  // (leader, term)
```

## Implementation Tasks

### Task 1: Capability Negotiation Protocol
**File:** `crates/siss-graph-db/src/repo/capability_negotiation.rs` (NEW)

Multi-round handshake:
```rust
pub struct CapabilityRequest {
    requester_id: Uuid,
    requester_sovereign: Uuid,
    target_resource: String,
    requested_capability: String,
    ceiling_tier_limit: String,
}

pub struct CapabilityGrant {
    request_id: Uuid,
    granted_capability: String,
    ceiling_tier: String,
    expires_at: Timestamp,
}

pub async fn submit_capability_request(
    pool: &PgPool,
    request: CapabilityRequest,
) -> Result<Uuid, NegotiationError>

pub async fn propose_grant(
    pool: &PgPool,
    request_id: Uuid,
    grant: CapabilityGrant,
    proposer_sovereign: Uuid,
) -> Result<(), NegotiationError>

pub async fn accept_grant(
    pool: &PgPool,
    request_id: Uuid,
    accepting_agent: Uuid,
) -> Result<CapabilityGrant, NegotiationError>

pub async fn get_request_status(
    pool: &PgPool,
    request_id: Uuid,
) -> Result<CapabilityRequestStatus, NegotiationError>
```

**Tests:**
- `test_submit_capability_request_creates_record`
- `test_propose_grant_requires_quorum_consensus`
- `test_accept_grant_activates_capability`
- `test_request_timeout_cancels_grant`

### Task 2: Transitive Delegation Repository
**File:** `crates/siss-graph-db/src/repo/transitive_delegation_repo.rs` (NEW)

Chain validation and extension:
```rust
pub struct DelegationChain {
    sovereigns: Vec<Uuid>,  // A -> B -> C
    ceiling_tiers: Vec<String>,  // cumulative ceilings
}

pub async fn verify_transitive_chain(
    pool: &PgPool,
    chain: &DelegationChain,
) -> Result<bool, ValidationError>

pub async fn extend_chain(
    pool: &PgPool,
    existing_chain: &DelegationChain,
    next_sovereign: Uuid,
    next_ceiling: &str,
) -> Result<DelegationChain, ValidationError>

pub async fn get_shortest_path(
    pool: &PgPool,
    source_sovereign: Uuid,
    target_sovereign: Uuid,
) -> Result<Option<DelegationChain>, sqlx::Error>
```

**Tests:**
- `test_verify_transitive_chain_valid`
- `test_verify_chain_detects_cycle`
- `test_extend_chain_maintains_lowest_ceiling`
- `test_shortest_path_finds_direct_delegation`

### Task 3: Ceiling Enforcement Engine
**File:** `crates/siss-graph-db/src/repo/ceiling_enforcement.rs` (NEW)

Dynamic tier checking:
```rust
pub async fn validate_ceiling_compliance(
    pool: &PgPool,
    request: &CapabilityRequest,
    delegation_chain: &DelegationChain,
) -> Result<bool, ValidationError>

pub async fn compute_effective_ceiling(
    pool: &PgPool,
    delegation_chain: &DelegationChain,
) -> Result<String, ValidationError>

pub async fn enforce_ceiling_on_grant(
    pool: &PgPool,
    request_id: Uuid,
    grant_ceiling: &str,
    chain_effective_ceiling: &str,
) -> Result<(), CeilingError>
```

**Tests:**
- `test_ceiling_compliance_rejects_escalation`
- `test_effective_ceiling_computed_correctly`
- `test_enforce_ceiling_allows_lower_tier`
- `test_enforce_ceiling_rejects_equal_tier`

### Task 4: Capability Grant Ledger
**File:** `crates/siss-graph-db/src/repo/capability_grant_ledger.rs` (NEW)

Immutable capability record:
```rust
pub async fn record_grant(
    pool: &PgPool,
    grant: &CapabilityGrant,
    consensus_proof: &TransactionHash,
) -> Result<GrantHash, sqlx::Error>

pub async fn revoke_grant(
    pool: &PgPool,
    grant_id: Uuid,
    reason: &str,
) -> Result<(), sqlx::Error>

pub async fn verify_grant_active(
    pool: &PgPool,
    grant_id: Uuid,
) -> Result<bool, sqlx::Error>

pub async fn get_grant_history(
    pool: &PgPool,
    requester_id: Uuid,
    limit: usize,
) -> Result<Vec<CapabilityGrant>, sqlx::Error>
```

**Tests:**
- `test_record_grant_immutable`
- `test_revoke_grant_invalidates_capability`
- `test_verify_grant_checks_expiry`
- `test_grant_history_ordered_by_timestamp`

### Task 5: Integration Tests
**File:** `crates/siss-agent-card/tests/phase_77_capability_negotiation.rs` (NEW)

End-to-end scenarios:
1. Direct capability grant (A requests, B grants)
2. Transitive delegation (A → B → C, request flows through B)
3. Ceiling enforcement (request capped at B's ceiling)
4. Cycle detection in negotiation (A requests C, cycle detected via Phase 73)
5. Concurrent capability requests (two agents request same capability)
6. Grant revocation (capability revoked mid-transaction)
7. Byzantine validator rejection (Phase 76 leader proposes invalid grant)

## Phase 77 File Ownership
```
✓ capability_negotiation.rs (new, primary)
✓ transitive_delegation_repo.rs (new, primary)
✓ ceiling_enforcement.rs (new, primary)
✓ capability_grant_ledger.rs (new, primary)
✓ tests/phase_77_*.rs (all Phase 77 tests)
  consensus_engine.rs (read-only, Phase 75)
  transaction_log.rs (read-only, Phase 75)
  leader_election.rs (read-only, Phase 76)
  consensus_monitor.rs (read-only, Phase 76)
  agent_discovery.rs (read-only, Phase 74)
  delegation_routing.rs (read-only, Phase 74)
  cycle_forensics.rs (read-only, Phase 73)
  cycle_healing_repo.rs (read-only, Phase 73)
```

## Mocking Strategy (Days 1-2)

Until Phase 76 leader election stable:
```rust
// mock_phase_76.rs
pub async fn mock_get_current_view(...) -> (Uuid, u64) {
    // Return hardcoded leader
}

// mock_phase_75.rs
pub async fn mock_propose_transaction(...) -> ConsensusProposal {
    // Return simulated proposal
}

// mock_phase_74.rs
pub async fn mock_verify_cross_sovereign_path(...) -> bool {
    // Return true for test chains
}
```

## Integration Week (Day 3-4)

Once Phase 76 publishes v1.0 monitoring interface:
1. Replace leader mocks with real Phase 76 elected leader lookup
2. Verify capability grants respect Phase 76 view changes
3. Verify ceiling enforcement respects Phase 73 cycle healing
4. Verify transitive chains use Phase 74 routing paths
5. Run full consensus-backed capability negotiation test

## Timeline
- **Day 1-2:** Capability negotiation + transitive delegation (mocked)
- **Day 3:** Ceiling enforcement + grant ledger
- **Day 4:** Integration with Phase 76 leader election + Phase 75 consensus
- **Day 5:** Full end-to-end tests + concurrent scenario stress tests

## Phase 78+ Dependencies
- **Phase 78:** Smart contracts execute with granted capabilities
- **Phase 79:** Sharding uses capability grants for partition assignment
- **Phase 80+:** Cross-ledger capability delegation

## Non-Goals (Phase 77)
- Smart contract capability isolation (Phase 78+)
- Sharding and partition rebalancing (Phase 79+)
- Cross-ledger capability exchange (Phase 80+)

## Constraints
- Must use Phase 76 leader election API (no leader override)
- Must use Phase 75 consensus ledger (all grants consensus-backed)
- Must respect Phase 74 routing constraints (no direct shortcuts)
- Must use Phase 73 cycle detection (no escalation through cycles)
- All capability grants must include consensus proof
- Grant expiry configurable (default: 24 hours)

## Success Metrics

```bash
cargo test --all
# Must show:
# - 348+ passed (all existing tests)
# - 20+ new Phase 77 tests passing
# - 0 failures
# - Transitive delegation chains verified
# - Ceiling enforcement verified
# - Concurrent request handling deterministic
```

## Conflict Resolution Strategy

When multiple agents request the same capability:
1. First request wins (FIFO ordering per transaction timestamp)
2. Second request added to queue
3. When first grant expires/revoked, second request processed
4. Deterministic ordering via timestamp + requester UUID lexicographic sort

## Special Cases

**Scenario A:** Requester has no delegation path to target
- Negotiation returns `NegotiationError::NoPath`
- Requester notified, can request via different route or ask intermediary

**Scenario B:** Requested capability exceeds all intermediary ceilings
- Ceiling enforcement rejects (returns `CeilingError::Escalation`)
- Requester notified, can request lower capability tier

**Scenario C:** Cycle detected during transitive chain validation
- Chain validation fails immediately (Phase 73 cycle API)
- Request rejected with `ValidationError::CycleDetected`
- Requester notified to break cycle or try different path
