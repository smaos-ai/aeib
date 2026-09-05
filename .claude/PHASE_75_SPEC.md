# Phase 75 Specification: Distributed Consensus for Multi-Sovereign Transactions

## Goal
Implement Byzantine Fault Tolerant (BFT) consensus for transactions spanning multiple sovereigns. Enable atomic operations across delegation boundaries.

## Dependencies
- **Phase 73:** Cycle healing determinism ✅ (v1.0 API)
- **Phase 74:** Agent discovery & routing ✅ (v1.0 API)
- **Blocks:** Phase 76, 77

## Success Criteria (Verifiable)
- ✅ Consensus protocol implemented (PBFT-lite variant)
- ✅ Atomic transaction commit across 3+ sovereigns
- ✅ 30+ new tests passing
- ✅ All 348 existing tests still passing
- ✅ Byzantine fault tolerance verified (tolerate 1/3 faulty nodes)

## Architecture

### Components (Phase 75 Ownership)

1. **consensus_engine.rs** — PBFT consensus state machine
2. **transaction_log.rs** — Immutable transaction ledger
3. **byzantine_validator.rs** — Signature verification & Byzantine checks
4. **multi_sovereign_transaction.rs** — Cross-sovereign transaction model

### Data Flow
```
Multi-Sovereign Transaction Request
    ↓ (route via Phase 74)
Consensus Engine
    ↓ (PBFT prepare)
Propose Block
    ↓ (collect signatures)
2/3+ Nodes Agree
    ↓ (commit)
Atomic Write (all or nothing)
    ↓ (verify Phase 73 cycle safety)
Transaction Committed
```

### Interfaces from Phase 73 & 74 (Read-Only)
```rust
// Phase 73 API
pub fn analyze_cycle(cycle_nodes: Vec<Uuid>, graph: &ReputationGraph) 
    -> Result<ReputationCycle, String>

pub async fn heal_cycle(pool: &PgPool, cycle: ReputationCycle) 
    -> Result<Uuid, String>

// Phase 74 API
pub async fn route_request(pool: &PgPool, source_agent: Uuid, 
    target_sovereign: Uuid, capability: &str) 
    -> Result<RoutingDecision, RoutingError>
```

## Implementation Tasks

### Task 1: Consensus Engine
**File:** `crates/siss-graph-db/src/repo/consensus_engine.rs` (NEW)

Implement PBFT-lite consensus:
```rust
pub struct ConsensusState {
    phase: ConsensusPhase,  // Prepare | Commit | Decided
    view: u64,
    sequence: u64,
    proposal: Vec<u8>,
    signatures: HashMap<Uuid, Signature>,
}

pub async fn propose_transaction(
    pool: &PgPool,
    transaction: MultiSovereignTransaction,
    proposer: Uuid,
) -> Result<ConsensusProposal, ConsensusError>

pub async fn prepare_vote(
    pool: &PgPool,
    proposal_id: Uuid,
    voter_id: Uuid,
) -> Result<(), ConsensusError>

pub async fn commit_if_consensus(
    pool: &PgPool,
    proposal_id: Uuid,
) -> Result<bool, ConsensusError>
```

**Tests:**
- `test_consensus_prepare_phase`
- `test_consensus_commit_phase`
- `test_byzantine_fault_tolerance_1_faulty`
- `test_consensus_liveness` (no deadlock)

### Task 2: Transaction Log
**File:** `crates/siss-graph-db/src/repo/transaction_log.rs` (NEW)

Immutable transaction ledger:
```rust
pub async fn append_transaction(
    pool: &PgPool,
    transaction: MultiSovereignTransaction,
    signatures: &[Signature],
) -> Result<TransactionHash, sqlx::Error>

pub async fn verify_transaction_integrity(
    pool: &PgPool,
    tx_hash: TransactionHash,
) -> Result<bool, sqlx::Error>
```

**Tests:**
- `test_append_immutable`
- `test_verify_signatures`
- `test_merkle_tree_consistency`

### Task 3: Byzantine Validator
**File:** `crates/siss-graph-db/src/repo/byzantine_validator.rs` (NEW)

Cryptographic validation:
```rust
pub fn validate_signature(
    proposal: &[u8],
    signature: &Signature,
    validator_key: &PublicKey,
) -> Result<bool, ValidationError>

pub fn detect_byzantine_behavior(
    proposal: &[u8],
    signatures: &[Signature],
    threshold: usize,
) -> Result<Vec<Uuid>, ValidationError>
```

**Tests:**
- `test_signature_validation`
- `test_equivocation_detection`
- `test_forged_signature_rejection`

### Task 4: Integration Tests
**File:** `crates/siss-agent-card/tests/phase_75_distributed_consensus.rs` (NEW)

End-to-end consensus scenarios:
1. Two sovereigns, atomic transaction
2. Three sovereigns, 2/3 consensus
3. Byzantine node (1/3 faulty) — system survives
4. Network partition recovery
5. Concurrent transaction ordering (no forks)

## Phase 75 File Ownership
```
✓ consensus_engine.rs (new, primary)
✓ transaction_log.rs (new, primary)
✓ byzantine_validator.rs (new, primary)
✓ multi_sovereign_transaction.rs (new, primary)
✓ tests/phase_75_*.rs (all Phase 75 tests)
  cycle_forensics.rs (read-only, Phase 73)
  agent_discovery.rs (read-only, Phase 74)
```

## Mocking Strategy (Days 1-2)

Until Phase 73 & 74 v1.0 APIs stable:
```rust
// mock_phase_73_74.rs
pub fn mock_analyze_cycle(...) -> ReputationCycle { ... }
pub async fn mock_route_request(...) -> RoutingDecision { ... }
```

## Integration Week (Day 3-4)

Once Phase 73 & 74 publish v1.0:
1. Replace mocks with real API calls
2. Verify transactions respect cycle healing decisions
3. Verify routing constraints enforced in consensus
4. Document integration points

## Timeline
- **Day 1-2:** Consensus engine + Byzantine validator
- **Day 3:** Transaction log + integration testing
- **Day 4:** Full stress tests + Phase 73/74 integration
- **Day 5:** Finalize + handoff for Phase 76

## Phase 76+ Dependencies
- **Phase 76:** Real-time monitoring needs consensus ledger
- **Phase 77:** Capability negotiation uses transaction log
- **Phase 78+:** Smart contracts execute via consensus

## Non-Goals (Phase 75)
- Byzantine leader election (Phase 76)
- Byzantine view change (Phase 77)
- Smart contracts (Phase 78+)
- Sharding (Phase 79+)

## Constraints
- Must use Phase 73 cycle API (validate all transactions safe)
- Must respect Phase 74 routing decisions (no bypass)
- No schema changes without team approval
- Backward compatible with Phases 1-72 data

## Success Metrics

```bash
cargo test --all
# Must show:
# - 348 passed (all existing tests)
# - 30+ new Phase 75 tests passing
# - 0 failures
# - Byzantine tolerance verified
# - Liveness verified (no deadlock)
```
