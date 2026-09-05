# Phase 76 Specification: Real-Time Consensus Monitoring & Byzantine Leader Election

## Goal
Implement Byzantine leader election and real-time monitoring of distributed consensus across multi-sovereign networks. Enable automatic view changes and faulty leader detection.

## Dependencies
- **Phase 73:** Cycle healing determinism ✅ (v1.0 API)
- **Phase 74:** Agent discovery & routing ✅ (v1.0 API)
- **Phase 75:** Distributed consensus ✅ (v1.0 API with ledger)
- **Blocks:** Phase 77, 78

## Success Criteria (Verifiable)
- ✅ Byzantine leader election implemented (Raft-style voting)
- ✅ Real-time consensus monitoring across 3+ sovereigns
- ✅ Automatic view change on leader failure (≤2s detection)
- ✅ 25+ new tests passing
- ✅ All 348+ existing tests still passing
- ✅ Byzantine leader isolation verified (system survives 1 faulty leader)

## Architecture

### Components (Phase 76 Ownership)

1. **consensus_monitor.rs** — Real-time consensus health tracking
2. **leader_election.rs** — Byzantine-resistant leader selection
3. **view_change_manager.rs** — Automatic view transitions on failure
4. **consensus_metrics.rs** — Monitoring and telemetry collection

### Data Flow
```
Active Consensus Ledger (Phase 75)
    ↓ (monitor proposals)
Consensus Monitor
    ↓ (track leader health)
Leader Status Evaluator
    ↓ (detect timeout/failure)
Trigger View Change?
    ↓ (yes: initiate election)
Leader Election Protocol (Raft-style)
    ↓ (quorum votes)
New Leader Elected
    ↓ (broadcast to sovereigns)
Resume Consensus (Phase 75)
```

### Interfaces from Phase 73, 74, 75 (Read-Only)
```rust
// Phase 75 API
pub async fn get_consensus_status(pool: &PgPool, proposal_id: Uuid) 
    -> Result<ConsensusState, String>

pub async fn get_transaction_log_tail(pool: &PgPool, limit: usize) 
    -> Result<Vec<TransactionHash>, String>

// Phase 74 API (for routing to elected leader)
pub async fn route_request(pool: &PgPool, source_agent: Uuid, 
    target_sovereign: Uuid, capability: &str) 
    -> Result<RoutingDecision, RoutingError>
```

## Implementation Tasks

### Task 1: Consensus Monitor
**File:** `crates/siss-graph-db/src/repo/consensus_monitor.rs` (NEW)

Real-time health tracking:
```rust
pub struct ConsensusMetrics {
    leader_id: Uuid,
    term: u64,
    last_heartbeat: Instant,
    committed_index: u64,
    proposal_latency_ms: f64,
}

pub async fn track_proposal_latency(
    pool: &PgPool,
    proposal_id: Uuid,
    latency_ms: f64,
) -> Result<(), sqlx::Error>

pub async fn get_leader_heartbeat(
    pool: &PgPool,
    sovereign_id: Uuid,
) -> Result<Instant, sqlx::Error>

pub async fn detect_leader_timeout(
    pool: &PgPool,
    timeout_ms: u64,
) -> Result<Option<Uuid>, sqlx::Error>
```

**Tests:**
- `test_monitor_tracks_heartbeat_timestamp`
- `test_monitor_detects_timeout_after_threshold`
- `test_monitor_records_proposal_latency`

### Task 2: Leader Election
**File:** `crates/siss-graph-db/src/repo/leader_election.rs` (NEW)

Byzantine-resistant voting:
```rust
pub struct VoteRequest {
    term: u64,
    candidate_id: Uuid,
    last_log_index: u64,
}

pub async fn request_vote(
    pool: &PgPool,
    vote_req: VoteRequest,
    voter_id: Uuid,
) -> Result<bool, ConsensusError>

pub async fn tally_votes(
    pool: &PgPool,
    term: u64,
    candidate_id: Uuid,
) -> Result<(usize, usize), ConsensusError>  // (votes_for, total_voters)

pub async fn elect_leader(
    pool: &PgPool,
    term: u64,
) -> Result<Option<Uuid>, ConsensusError>  // Returns elected leader or None if no quorum
```

**Tests:**
- `test_request_vote_grants_vote_to_higher_term`
- `test_request_vote_rejects_old_term`
- `test_elect_leader_quorum_consensus`
- `test_byzantine_leader_detection_1_faulty`

### Task 3: View Change Manager
**File:** `crates/siss-graph-db/src/repo/view_change_manager.rs` (NEW)

Automatic leader transitions:
```rust
pub struct ViewChange {
    old_leader: Uuid,
    new_leader: Uuid,
    term: u64,
    initiated_at: Timestamp,
}

pub async fn initiate_view_change(
    pool: &PgPool,
    sovereign_id: Uuid,
    reason: &str,
) -> Result<ViewChange, ConsensusError>

pub async fn apply_view_change(
    pool: &PgPool,
    view_change: ViewChange,
) -> Result<(), ConsensusError>

pub async fn get_current_view(
    pool: &PgPool,
    sovereign_id: Uuid,
) -> Result<(Uuid, u64), ConsensusError>  // (current_leader, term)
```

**Tests:**
- `test_view_change_on_leader_timeout`
- `test_view_change_increments_term`
- `test_concurrent_view_changes_converge`

### Task 4: Metrics & Telemetry
**File:** `crates/siss-graph-db/src/repo/consensus_metrics.rs` (NEW)

Observability:
```rust
pub async fn record_leader_change(
    pool: &PgPool,
    old_leader: Uuid,
    new_leader: Uuid,
    reason: &str,
) -> Result<(), sqlx::Error>

pub async fn get_consensus_health(
    pool: &PgPool,
    time_window_seconds: u64,
) -> Result<HealthMetrics, sqlx::Error>

pub struct HealthMetrics {
    avg_proposal_latency_ms: f64,
    view_changes_count: u64,
    leader_uptime_pct: f64,
}
```

**Tests:**
- `test_record_leader_change_tracks_history`
- `test_health_metrics_aggregation`

### Task 5: Integration Tests
**File:** `crates/siss-agent-card/tests/phase_76_consensus_monitoring.rs` (NEW)

End-to-end scenarios:
1. Leader election with 3 sovereigns (quorum: 2/3)
2. Leader failure detection (heartbeat timeout)
3. View change and new leader elected
4. Byzantine leader (sends conflicting proposals) — network isolates and recovers
5. Concurrent leader timeouts (race condition) — single view change wins
6. Leader change during active transaction — proposal retried with new leader

## Phase 76 File Ownership
```
✓ consensus_monitor.rs (new, primary)
✓ leader_election.rs (new, primary)
✓ view_change_manager.rs (new, primary)
✓ consensus_metrics.rs (new, primary)
✓ tests/phase_76_*.rs (all Phase 76 tests)
  consensus_engine.rs (read-only, Phase 75)
  transaction_log.rs (read-only, Phase 75)
  agent_discovery.rs (read-only, Phase 74)
  delegation_routing.rs (read-only, Phase 74)
  cycle_forensics.rs (read-only, Phase 73)
```

## Mocking Strategy (Days 1-2)

Until Phase 75 monitoring APIs stable:
```rust
// mock_phase_75.rs
pub async fn mock_get_consensus_status(...) -> ConsensusState { ... }
pub async fn mock_detect_leader_timeout(...) -> Option<Uuid> { ... }
```

## Integration Week (Day 3-4)

Once Phase 75 publishes v1.1 monitoring interface:
1. Replace mocks with real consensus ledger queries
2. Verify view changes respect Phase 74 routing constraints
3. Verify Phase 73 cycle healing doesn't conflict with leader election
4. Stress test: 10 concurrent view changes

## Timeline
- **Day 1-2:** Consensus monitor + leader election
- **Day 3:** View change manager + metrics
- **Day 4:** Integration with Phase 75 consensus ledger
- **Day 5:** Byzantine resilience stress tests + Phase 75/74/73 integration

## Phase 77+ Dependencies
- **Phase 77:** Capability negotiation uses leader info for routing decisions
- **Phase 78:** Smart contracts execute on elected leader
- **Phase 79+:** Sharding uses view changes for partition rebalancing

## Non-Goals (Phase 76)
- Sharding or partition rebalancing (Phase 79+)
- Smart contract execution (Phase 78+)
- Cross-ledger consensus (Phase 80+)

## Constraints
- Must use Phase 75 consensus ledger API (no reimplementation)
- Must respect Phase 74 routing for new leader announcement
- Must not modify Phase 73, 74, 75 code (read-only integration)
- Heartbeat timeout configurable (default: 500ms)
- Election timeout configurable (default: 1000ms)

## Success Metrics

```bash
cargo test --all
# Must show:
# - 348+ passed (all existing tests)
# - 25+ new Phase 76 tests passing
# - 0 failures
# - Byzantine leader isolation verified
# - Leader election under 2s latency
```
