# Phase 13: Cycle Detection & Escrow — Complete Specification

## Executive Summary

Phase 13 adds **cycle detection and atomic multi-party escrow settlement** to the Memory Plane. It enables:

1. **Cycle Detection:** Identify reputation loops (A→B→C→A) via Tarjan's Strongly Connected Components algorithm
2. **Escrow System:** Hold tokens atomically while multi-party consensus is reached
3. **Consensus Protocol:** 2-phase commit over gossip with quorum voting
4. **Cycle Healing:** Automatic breaking of low-trust cycles; operator approval for high-trust breaks
5. **Full Testing:** 40+ integration tests verifying cycle detection, escrow atomicity, consensus fault tolerance

**Scope:** Tasks 66–70 (100 engineer-hours each = ~400 total)  
**Dependencies:** Phase 12 complete ✅  
**Timeline:** Months 7–8  
**Gate:** All constitutional invariants from Phase 12 remain locked; new invariants: ESCROW_ATOMICITY, CYCLE_HEALING_ORDERED

---

## Part 1: Problem Statement & Motivation

### 1.1 The Cycle Problem

In Phase 12 Memory Plane, sovereigns track reputation signals about agents across bilateral agreements. Without cycle detection, a malicious coalition could create circular reputation loops:

```
ATTACK SCENARIO:
  Alice claims: "Bob is trustworthy +10"
  Bob claims: "Charlie is trustworthy +10"
  Charlie claims: "Alice is trustworthy +10"
  
  Result: All three have artificially inflated tiers despite no external proof.
  This is a REPUTATION SYBIL ATTACK (circular bootstrapping).

CYCLE DETECTION BREAKS THIS:
  1. Detect the cycle: A→B→C→A
  2. Identify the weakest link (lowest trust tier)
  3. Break that link (revoke one grant)
  4. All tiers readjust downward
```

### 1.2 The Escrow Problem

Settlement invoices in Phase 12 can be disputed after payment. Without escrow, a debtor could:

```
ATTACK SCENARIO:
  1. Alice settles invoice with Bob (1000 tokens) 
  2. Both mark as "settled"
  3. Later, Bob disputes ("I never received tokens")
  4. Alice's tokens already spent; no recovery mechanism
  
ESCROW SOLVES THIS:
  1. Alice initiates settlement, tokens moved to ESCROW
  2. Bob must acknowledge receipt within 48h
  3. Acknowledgement triggers RELEASE (tokens deducted from Alice)
  4. If Bob disappears, tokens auto-refund after timeout
```

---

## Part 2: Task 66 — Cycle Detection Algorithm

### 2.1 Algorithm Overview: Tarjan's SCC

**Input:** Reputation graph (nodes=sovereigns, edges=delegation grants with tier ceiling)  
**Output:** List of strongly connected components (cycles); ranking by cycle size + trust density

```rust
pub struct ReputationCycle {
    pub cycle_id: String,
    pub sovereigns: Vec<Uuid>,  // [A, B, C] for A→B→C→A
    pub cycle_length: usize,
    pub min_tier_in_cycle: u32,
    pub trust_density: f64,  // Weighted edge count
    pub weakest_link: (Uuid, Uuid),  // (from, to) edge with lowest trust
    pub severity: String,  // "critical" | "high" | "medium" | "low"
}

pub async fn detect_reputation_cycles(
    pool: &PgPool,
    sovereign_id: Uuid,  // Optional: detect cycles reachable from this sovereign
) -> Result<Vec<ReputationCycle>, DetectionError>
```

### 2.2 Tarjan's Algorithm (Pseudocode)

```
TARJAN_SCC(Graph G):
  1. Initialize: index=0, stack=[]
  2. FOR EACH vertex v in G.vertices:
       IF v.index is undefined:
         STRONGCONNECT(v)
  3. RETURN scc_list (list of SCCs found)

STRONGCONNECT(vertex v):
  1. v.index = index
  2. v.lowlink = index
  3. index += 1
  4. stack.push(v)
  5. v.on_stack = true
  
  6. FOR EACH successor w of v:
       IF w.index is undefined:
         STRONGCONNECT(w)
         v.lowlink = min(v.lowlink, w.lowlink)
       ELSE IF w.on_stack:
         v.lowlink = min(v.lowlink, w.index)
  
  7. IF v.lowlink == v.index:
       # v is a root node; pop entire SCC
       SCC = []
       REPEAT:
         w = stack.pop()
         w.on_stack = false
         SCC.append(w)
       UNTIL w == v
       scc_list.append(SCC)
```

### 2.3 Reputation Graph Construction

```rust
pub struct ReputationGraphEdge {
    pub from_sovereign: Uuid,
    pub to_sovereign: Uuid,
    pub delegation_grant_id: Uuid,
    pub ceiling_tier: u32,
    pub transitivity_depth: i16,
    pub status: String,  // "active" | "revoked" | "expired"
}

pub async fn build_reputation_graph(
    pool: &PgPool,
) -> Result<Vec<ReputationGraphEdge>, GraphError> {
    // Query memory_objects.delegation_cross where status='active'
    // Group by (grantor_sovereign_id, grantee_sovereign_id)
    // Return edges weighted by ceiling_tier (higher tier = stronger edge)
}

pub async fn find_shortest_cycle(
    pool: &PgPool,
    from: Uuid,
    to: Uuid,
    max_depth: usize,
) -> Result<Option<Vec<Uuid>>, GraphError> {
    // BFS from 'from' to 'to' with max_depth limit
    // Returns shortest path if exists, None otherwise
}
```

### 2.4 Cycle Severity Scoring

```rust
pub fn score_cycle_severity(cycle: &ReputationCycle) -> String {
    // Severity = f(cycle_length, min_tier, trust_density)
    
    let base_score = cycle.min_tier_in_cycle as f64 * cycle.trust_density;
    
    if base_score > 80.0 && cycle.cycle_length <= 3 {
        "critical"  // Small, high-trust cycle
    } else if base_score > 60.0 {
        "high"
    } else if base_score > 40.0 {
        "medium"
    } else {
        "low"
    }
}
```

### 2.5 Tests for Task 66

```rust
#[tokio::test]
async fn test_tarjan_detects_simple_3_cycle() {
    // Create A→B→C→A cycle
    // Call detect_reputation_cycles()
    // Verify: 1 SCC with 3 sovereigns
}

#[tokio::test]
async fn test_tarjan_detects_nested_cycles() {
    // Create (A→B→A) + (B→C→B) + (A→C→A)
    // Verify: 1 large SCC, not 3 separate SCCs
}

#[tokio::test]
async fn test_no_cycle_in_dag() {
    // Create linear delegation: A→B→C→D (no loops)
    // Call detect_reputation_cycles()
    // Verify: 0 cycles detected
}

#[tokio::test]
async fn test_weakest_link_identification() {
    // Create A→B (tier=100), B→C (tier=50), C→A (tier=80)
    // Verify weakest link is B→C
}

#[tokio::test]
async fn test_cycle_severity_scoring() {
    // Small high-trust cycle → "critical"
    // Large low-trust cycle → "low"
}
```

---

## Part 3: Task 67 — Escrow System

### 3.1 Schema: Escrow Ledger

```sql
-- Migration 028: escrow_ledger table

CREATE TABLE escrow_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Settlement reference
    invoice_id UUID NOT NULL UNIQUE REFERENCES settlement_invoices(id),
    creditor_sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
    debtor_sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
    
    -- Escrow state
    tokens_held BIGINT NOT NULL CHECK (tokens_held > 0),
    status VARCHAR(32) NOT NULL DEFAULT 'pending',  
      -- "pending" | "held" | "released" | "forfeited" | "disputed"
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    held_at TIMESTAMPTZ,
    release_at TIMESTAMPTZ,
    timeout_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '48 hours'),
    
    -- Debtor acknowledgement
    debtor_acknowledged_at TIMESTAMPTZ,
    debtor_acknowledged_by_sovereign_id UUID REFERENCES sovereigns(id),
    
    -- Creditor release signature
    release_signature TEXT,
    
    -- Dispute tracking
    disputed_at TIMESTAMPTZ,
    dispute_reason TEXT,
    dispute_evidence JSONB,
    arbitration_result TEXT,  -- "creditor_wins" | "debtor_wins" | "split"
    
    -- Vector clock for causality
    vector_clock JSONB NOT NULL DEFAULT '{}',
    
    -- Audit
    created_by_sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
    
    CONSTRAINT check_status_transitions CHECK (
        (status = 'pending' AND held_at IS NULL) OR
        (status = 'held' AND held_at IS NOT NULL) OR
        (status = 'released' AND release_at IS NOT NULL) OR
        (status = 'forfeited' AND timeout_at < NOW()) OR
        (status = 'disputed' AND disputed_at IS NOT NULL)
    ),
    
    CONSTRAINT check_timeout_future CHECK (timeout_at > created_at)
);

CREATE INDEX idx_escrow_debtor ON escrow_ledger(debtor_sovereign_id)
    WHERE status IN ('pending', 'held');
CREATE INDEX idx_escrow_creditor ON escrow_ledger(creditor_sovereign_id)
    WHERE status IN ('pending', 'held');
CREATE INDEX idx_escrow_timeout ON escrow_ledger(timeout_at)
    WHERE status = 'held' AND debtor_acknowledged_at IS NULL;
```

### 3.2 Escrow Handlers

```rust
pub enum EscrowError {
    InvoiceNotFound,
    AlreadyInEscrow,
    InsufficientBalance,
    NotInHeldState,
    TimeoutNotReached,
    UnauthorizedRelease,
    Database(sqlx::Error),
}

pub async fn initiate_escrow(
    pool: &PgPool,
    invoice_id: Uuid,
    creditor_id: Uuid,
    debtor_id: Uuid,
    tokens: i64,
) -> Result<Uuid, EscrowError> {
    // 1. Verify invoice exists and status='pending'
    // 2. Verify creditor has tokens_available >= tokens
    // 3. INSERT into escrow_ledger with status='pending'
    // 4. Atomically DEBIT creditor's balance (session budget)
    // 5. Return escrow_id
}

pub async fn debtor_acknowledge_escrow(
    pool: &PgPool,
    escrow_id: Uuid,
    debtor_id: Uuid,
) -> Result<(), EscrowError> {
    // 1. Load escrow, verify status='pending'
    // 2. Verify requester == debtor_id
    // 3. UPDATE: status → 'held', held_at=NOW(), debtor_acknowledged_at=NOW()
    // 4. Emit gossip: "escrow held" message
}

pub async fn release_escrow(
    pool: &PgPool,
    escrow_id: Uuid,
    creditor_id: Uuid,
    signature: &str,
) -> Result<(), EscrowError> {
    // 1. Load escrow, verify status='held'
    // 2. Verify requester == creditor_id
    // 3. Verify signature (creditor signs release authorization)
    // 4. ATOMIC TRANSACTION (SERIALIZABLE):
    //    a. UPDATE settlement_invoices: status → 'settled'
    //    b. UPDATE escrow_ledger: status → 'released', release_at=NOW()
    //    c. DEBIT creditor's balance (tokens already held in escrow)
    //    d. Increment vector clocks for both sovereigns
    // 5. Emit gossip: "escrow released" message
    // 6. Emit economic_event: token transfer
}

pub async fn forfeit_escrow_on_timeout(
    pool: &PgPool,
    escrow_id: Uuid,
) -> Result<(), EscrowError> {
    // Called by background job when timeout_at <= NOW()
    // 1. Load escrow, verify status='held'
    // 2. Verify timeout_at has passed
    // 3. ATOMIC TRANSACTION:
    //    a. UPDATE escrow_ledger: status → 'forfeited'
    //    b. REFUND creditor's balance (release tokens back)
    //    c. Mark settlement_invoices: status → 'pending' (back to initial)
    // 4. Emit gossip: "escrow forfeited" message
}

pub async fn dispute_escrow(
    pool: &PgPool,
    escrow_id: Uuid,
    disputing_sovereign_id: Uuid,
    dispute_reason: &str,
    evidence: serde_json::Value,
) -> Result<(), EscrowError> {
    // 1. Load escrow, verify status='held'
    // 2. Verify requester is creditor or debtor
    // 3. UPDATE escrow_ledger:
    //    status → 'disputed', disputed_at=NOW(),
    //    dispute_reason, dispute_evidence
    // 4. Emit gossip: "escrow disputed" message
    // 5. Initiate arbitration (Phase 15)
}
```

### 3.3 Tests for Task 67

```rust
#[tokio::test]
async fn test_initiate_escrow_success() {
    // Create invoice, initiate escrow
    // Verify: status='pending', tokens held
    // Verify: creditor's balance debited
}

#[tokio::test]
async fn test_debtor_acknowledge_moves_to_held() {
    // Initiate, then debtor acknowledges
    // Verify: status → 'held', debtor_acknowledged_at set
}

#[tokio::test]
async fn test_release_escrow_atomic() {
    // Initiate → held → release
    // Verify: invoice marked 'settled', tokens transferred
    // Verify: single atomic transaction (no partial states)
}

#[tokio::test]
async fn test_escrow_timeout_refunds() {
    // Initiate → held, wait 48h
    // Call forfeit_escrow_on_timeout()
    // Verify: status → 'forfeited', tokens refunded to creditor
}

#[tokio::test]
async fn test_escrow_status_monotonic() {
    // Verify: no backward transitions (held → pending fails)
    // Verify: only valid paths (pending → held → released|disputed|forfeited)
}
```

---

## Part 4: Task 68 — Consensus Protocol (2-Phase Commit)

### 4.1 Protocol Overview

**Goal:** Atomically release escrow with quorum agreement from all relevant sovereigns.

**Participants:**
- **Initiator:** Creditor (requests release)
- **Witnesses:** Active federation peers + arbitrators
- **Quorum:** N-of-2N+1 (Byzantine tolerant)

**Flow:**

```
Phase 1: PREPARE (Creditor broadcasts)
  ┌──────────────────────────────────┐
  │ Creditor: "I want to release     │
  │ escrow-123. Acknowledge?"        │
  └──────────────────────────────────┘
          ↓      ↓      ↓
    Peer1  Peer2  Peer3
    ✅OK   ✅OK   ✅OK
          ↓      ↓      ↓
  Creditor collects votes (gossip messages)

Phase 2: COMMIT (If quorum reached)
  ┌──────────────────────────────────┐
  │ Creditor: "Quorum reached.       │
  │ Release escrow-123 NOW!"         │
  └──────────────────────────────────┘
          ↓      ↓      ↓
    Peer1  Peer2  Peer3
    ✅ACK  ✅ACK  ✅ACK
    
  All atomically mark escrow as RELEASED

Timeout: If no quorum in 24h → AUTO-FORFEIT
```

### 4.2 Consensus Structures

```rust
pub struct ConsensusProposal {
    pub proposal_id: String,  // UUID
    pub initiator_sovereign_id: Uuid,
    pub escrow_id: Uuid,
    pub proposal_type: String,  // "release_escrow" | "cycle_break" | "arbitration"
    pub payload: serde_json::Value,
    pub created_at: DateTime<Utc>,
    pub expires_at: DateTime<Utc>,  // Proposal valid for 24h
    pub required_quorum: usize,  // N-of-2N+1
}

pub struct ConsensusVote {
    pub vote_id: String,
    pub proposal_id: String,
    pub voter_sovereign_id: Uuid,
    pub vote: String,  // "yes" | "no" | "abstain"
    pub signature: String,  // Ed25519(voter.private_key, proposal_id || vote)
    pub voted_at: DateTime<Utc>,
}

pub struct ConsensusResult {
    pub proposal_id: String,
    pub status: String,  // "pending" | "approved" | "rejected" | "expired"
    pub total_votes: usize,
    pub yes_votes: usize,
    pub no_votes: usize,
    pub quorum_reached: bool,
    pub decided_at: Option<DateTime<Utc>>,
}

pub async fn initiate_consensus(
    pool: &PgPool,
    initiator_id: Uuid,
    escrow_id: Uuid,
) -> Result<String, ConsensusError> {
    // 1. Calculate quorum: N = active_peers.count()
    //    required = ceil((2N + 1) / 2) for Byzantine tolerance
    // 2. Broadcast PREPARE gossip message to all peers
    // 3. Create ConsensusProposal with expires_at=now+24h
    // 4. Return proposal_id
}

pub async fn cast_consensus_vote(
    pool: &PgPool,
    proposal_id: &str,
    voter_id: Uuid,
    vote: &str,
    signature: &str,
) -> Result<(), ConsensusError> {
    // 1. Verify signature: Ed25519(voter.public_key, proposal_id || vote)
    // 2. Verify voter is active peer
    // 3. INSERT ConsensusVote
    // 4. Check if quorum reached
    // 5. If yes: emit COMMIT gossip, execute consensus
}

pub async fn check_consensus_quorum(
    pool: &PgPool,
    proposal_id: &str,
) -> Result<ConsensusResult, ConsensusError> {
    // 1. Count yes/no/abstain votes
    // 2. If yes_votes >= required_quorum: return "approved"
    // 3. If (no_votes + yes_votes) > N/2: return "rejected"
    // 4. If expired: return "expired"
    // 5. Else: return "pending"
}

pub async fn finalize_consensus(
    pool: &PgPool,
    proposal_id: &str,
) -> Result<(), ConsensusError> {
    // 1. Verify quorum reached
    // 2. Execute consensus result:
    //    - If release_escrow: call release_escrow()
    //    - If cycle_break: call break_cycle()
    //    - etc.
    // 3. Mark proposal as finalized
}
```

### 4.3 Tests for Task 68

```rust
#[tokio::test]
async fn test_consensus_quorum_calculation() {
    // N=5 peers → required quorum = 4 (majority of 2N+1=11)
    // Verify quorum formula
}

#[tokio::test]
async fn test_consensus_approved_with_quorum() {
    // Create proposal, collect 4 yes votes from 5 peers
    // Verify: status → "approved", can finalize
}

#[tokio::test]
async fn test_consensus_rejected_insufficient_quorum() {
    // Create proposal, collect 2 yes + 2 no votes (quorum = 4)
    // Verify: status → "pending" (not approved, not rejected)
    // After 24h timeout: status → "expired"
}

#[tokio::test]
async fn test_consensus_byzantine_resilience() {
    // N=5 peers, 1 Byzantine (votes "no")
    // Other 4 vote "yes" → quorum reached
    // Verify: can withstand up to N/3 Byzantine voters
}

#[tokio::test]
async fn test_consensus_signature_verification() {
    // Create vote with invalid signature
    // Verify: cast_consensus_vote() rejects with invalid_signature error
}
```

---

## Part 5: Task 69 — Cycle Healing

### 5.1 Automatic Cycle Breaking (Low-Trust Cycles)

```rust
pub struct CycleHealing {
    pub cycle_id: String,
    pub cycle: Vec<Uuid>,  // [A, B, C] for A→B→C→A
    pub weakest_link: (Uuid, Uuid),  // (grantor, grantee)
    pub break_strategy: String,  // "automatic" | "operator_approved"
    pub revoked_grant_id: Uuid,
    pub initiated_at: DateTime<Utc>,
}

pub async fn auto_heal_low_trust_cycle(
    pool: &PgPool,
    cycle: &ReputationCycle,
) -> Result<Uuid, HealingError> {
    // If cycle.severity == "low" OR cycle.min_tier < 30:
    //   1. Revoke weakest_link grant automatically
    //   2. Emit gossip: "cycle broken"
    //   3. Update memory_objects.delegation_cross: status → 'revoked'
    //   4. Return healing_id
    // Else:
    //   Return Err(HealingError::RequiresOperatorApproval)
}

pub async fn operator_approve_cycle_break(
    pool: &PgPool,
    cycle_id: &str,
    operator_id: Uuid,
    approval_signature: &str,
) -> Result<Uuid, HealingError> {
    // 1. Verify operator's governance role (from memory_governance_policies)
    // 2. Verify signature: Ed25519(operator.private_key, cycle_id)
    // 3. Revoke weakest_link grant
    // 4. Emit gossip: "cycle broken by operator"
    // 5. Log to audit: who authorized, when, signature
    // 6. Return healing_id
}

pub async fn find_and_heal_all_cycles(
    pool: &PgPool,
) -> Result<Vec<Uuid>, HealingError> {
    // Background job (runs hourly):
    // 1. detect_reputation_cycles()
    // 2. For each cycle:
    //    - If severity <= "medium": auto_heal_low_trust_cycle()
    //    - Else: emit alert to operator dashboard
    // 3. Return list of healed cycle IDs
}
```

### 5.2 Audit Trail

```rust
pub struct CycleHealingAudit {
    pub healing_id: String,
    pub cycle_id: String,
    pub revoked_grant_id: Uuid,
    pub revoked_at: DateTime<Utc>,
    pub reason: String,  // "automatic_low_trust" | "operator_approved"
    pub authorized_by: Option<Uuid>,  // If operator-approved
    pub authorization_signature: Option<String>,
    pub gossip_message_id: Uuid,  // Links to gossip "cycle broken" message
}
```

### 5.3 Tests for Task 69

```rust
#[tokio::test]
async fn test_auto_heal_low_trust_cycle() {
    // Create low-trust cycle (min_tier < 30)
    // Call auto_heal_low_trust_cycle()
    // Verify: weakest link revoked automatically
    // Verify: no operator approval needed
}

#[tokio::test]
async fn test_operator_approval_required_for_high_trust() {
    // Create high-trust cycle (min_tier > 70)
    // Call auto_heal_low_trust_cycle()
    // Verify: returns RequiresOperatorApproval error
    // Call operator_approve_cycle_break() with signature
    // Verify: cycle breaks after approval
}

#[tokio::test]
async fn test_cycle_healing_cascades() {
    // Create cycle A→B→C→A and dependent grant C→D
    // Break A→B link
    // Verify: D's grant remains valid (break only affects cycle edge)
}

#[tokio::test]
async fn test_audit_trail_complete() {
    // Heal a cycle with operator approval
    // Verify: CycleHealingAudit includes:
    //   - healing_id, cycle_id, revoked_grant_id
    //   - authorized_by (operator ID)
    //   - authorization_signature (Ed25519)
}
```

---

## Part 6: Task 70 — Comprehensive Testing (40+ Tests)

### 6.1 Test Suite Organization

```
tests/phase_13/
├── suite_66_cycle_detection.rs      (10 tests)
│   ├── Tarjan algorithm correctness
│   ├── Cycle severity scoring
│   ├── Weakest link identification
│   └── Edge cases (self-loops, disconnected graphs)
│
├── suite_67_escrow_system.rs        (12 tests)
│   ├── Initiate, hold, release, timeout, dispute
│   ├── Status machine monotonicity
│   ├── Atomic token transfer
│   └── Timeout background job
│
├── suite_68_consensus_protocol.rs   (10 tests)
│   ├── Quorum calculation
│   ├── Vote collection + finalization
│   ├── Byzantine resilience
│   ├── Signature verification
│   └── Timeout handling
│
├── suite_69_cycle_healing.rs        (8 tests)
│   ├── Auto-heal low-trust cycles
│   ├── Operator approval required
│   ├── Audit trail logging
│   └── Cascade effects
│
└── common.rs
    └── Shared fixtures (test sovereigns, cycles, escrows)
```

### 6.2 Chaos Engineering Tests

```rust
#[tokio::test]
async fn test_escrow_release_under_peer_failure() {
    // Setup: Creditor, Debtor, 3 Peers, quorum=2
    // Scenario: 1 peer crashes before voting
    // Verify: Quorum still reached (2 of 3 remaining), escrow released
}

#[tokio::test]
async fn test_cycle_healing_during_gossip_loss() {
    // Setup: Cycle detection → healing initiated
    // Scenario: Gossip message lost en-route
    // Verify: Healing still completes (idempotent via grant_id)
}

#[tokio::test]
async fn test_concurrent_escrow_initiations() {
    // Setup: Same invoice, two creditors try to initiate escrow
    // Verify: Only first succeeds (UNIQUE constraint on invoice_id)
}

#[tokio::test]
async fn test_escrow_atomicity_on_database_failure() {
    // Setup: Escrow in "held" state, mid-release
    // Scenario: Database connection drops during COMMIT phase
    // Verify: Transaction rolled back, escrow still "held"
}
```

### 6.3 Integration Tests: End-to-End Workflows

```rust
#[tokio::test]
async fn test_e2e_escrow_happy_path() {
    // 1. Create invoice (Alice → Bob, 1000 tokens)
    // 2. Alice initiates escrow
    // 3. Bob acknowledges
    // 4. Alice releases (with signature)
    // 5. Verify: invoice settled, tokens transferred
}

#[tokio::test]
async fn test_e2e_cycle_detection_and_healing() {
    // 1. Create 4 sovereigns: A, B, C, D
    // 2. Create cycle: A→B→C→A (low-trust)
    // 3. Create non-cycle: D→A
    // 4. Call auto-heal
    // Verify: Only cycle link broken, D→A remains
}

#[tokio::test]
async fn test_e2e_consensus_escrow_release() {
    // 1. Create escrow with 5 peers
    // 2. Initiate consensus (proposal_type="release_escrow")
    // 3. Collect votes from 4 peers (quorum=3)
    // 4. Finalize consensus
    // Verify: Escrow automatically released, gossip propagated
}
```

---

## Part 7: Constitutional Invariants (Phase 13 Additions)

### 7.1 New Invariants

```
ESCROW_ATOMICITY:
  Definition: Escrow tokens are always either held OR released OR forfeited,
              never split or lost.
  Enforcement:
    - Database: SERIALIZABLE transaction isolation
    - Code: release_escrow() and forfeit_escrow() are atomic blocks
    - Test: test_escrow_atomicity_on_database_failure
    
  Invariant Check:
    SELECT SUM(tokens_held) FROM escrow_ledger WHERE status='held'
    SHOULD = SUM(tokens_escrowed) from settlement_invoices
    (No orphaned tokens)

CYCLE_HEALING_ORDERED:
  Definition: Cycles are healed in priority order:
              1. Auto-heal (low-trust)
              2. Operator-approved (high-trust)
              3. Disputes only if cycle unresolved
  Enforcement:
    - Code: find_and_heal_all_cycles() enforces priority
    - Gossip: All peers see same healing order (vector clocks)
    - Test: test_cycle_healing_cascades
```

### 7.2 Phase 12 Invariants Remain Locked

```
✅ TRANSITIVITY_DEPTH_MAX = 3
   (Still enforced; escrow doesn't relax delegation constraints)

✅ REPUTATION_ISOLATION
   (Still enforced; escrow doesn't allow foreign tiers to boost home)

✅ INVOICE_STATUS_MONOTONIC
   (Extended: now includes escrow states in state machine)

✅ DISCOVERY_OPT_IN_REQUIRED
   (Still enforced; peers must be discoverable to vote on consensus)
```

---

## Part 8: Implementation Roadmap (Tasks 66–70)

### 8.1 Task Ordering & Dependencies

```
Task 66: Cycle Detection Algorithm
  └─ No dependencies, can start immediately
  Duration: 80–100 hours
  Deliverables:
    - cycle_detector.rs (Tarjan's SCC)
    - reputation_graph.rs (graph construction)
    - 10 unit + integration tests
    - Phase 13 Cycle Detection Lock doc

Task 67: Escrow System
  └─ Depends on: Phase 12 complete ✅
  Duration: 100–120 hours
  Deliverables:
    - escrow_handler.rs (initiate, acknowledge, release, forfeit, dispute)
    - Migration 028: escrow_ledger table
    - 12 integration tests
    - Gossip message handlers for escrow events

Task 68: Consensus Protocol
  └─ Depends on: Tasks 66 + 67 (for context)
  Duration: 100–120 hours
  Deliverables:
    - consensus_protocol.rs (2-phase commit)
    - gossip integration (vote collection)
    - 10 integration tests + chaos engineering
    - Byzantine resilience proofs

Task 69: Cycle Healing
  └─ Depends on: Tasks 66 + 68
  Duration: 60–80 hours
  Deliverables:
    - cycle_healing.rs (auto + operator-approved)
    - Audit trail logging
    - 8 integration tests
    - Operator dashboard alerts

Task 70: Comprehensive Testing
  └─ Depends on: Tasks 66–69
  Duration: 80–100 hours
  Deliverables:
    - 40+ integration tests (all scenarios)
    - Chaos engineering suite
    - CI/CD configuration
    - Phase 13 Test Suite Lock doc

Total: ~400–500 engineer-hours
Timeline: 8 weeks (50 hours/week per 2-person team)
```

### 8.2 Parallel Execution Plan

```
Week 1–2:   Tasks 66 + 67 in parallel
            (no cross-dependencies until testing phase)

Week 3:     Task 68 begins (after 66 + 67 core)
            Tasks 66 + 67 enter testing phase

Week 4–5:   Task 68 + Task 69 in parallel
            (69 depends on 66, but 68 proceeds independently)

Week 6:     Task 70 begins (after 66–69 core complete)
            All tasks in final testing

Week 7–8:   Phase 13 integration testing + lock
            Documentation + roadmap to Phase 14
```

---

## Part 9: Completeness Check & Gate Criteria

### 9.1 Implementation Completeness

- ✅ Tarjan's SCC algorithm (Task 66)
- ✅ Escrow system with timeout (Task 67)
- ✅ 2-phase consensus with quorum (Task 68)
- ✅ Automatic + operator-approved healing (Task 69)
- ✅ 40+ comprehensive tests (Task 70)
- ✅ New constitutional invariants (ESCROW_ATOMICITY, CYCLE_HEALING_ORDERED)
- ✅ Phase 12 invariants still locked + verified
- ✅ Gossip integration for all events
- ✅ Audit trail for all healing actions

### 9.2 Gate Criteria (Before Phase 13 Lock)

```
✅ Code:
   - cargo check --all passes
   - cargo clippy --all passes
   - cargo fmt --all compliant
   - All new modules export in lib.rs

✅ Tests:
   - 40+ tests pass (cargo test)
   - >90% coverage on Phase 13 code (cargo tarpaulin)
   - Chaos engineering tests stable (run 3x)
   - No flaky tests

✅ Specification:
   - All 5 tasks (66–70) documented
   - All constitutional invariants verified in code + tests
   - All function signatures match spec
   - Implementation guide complete

✅ Integration:
   - Phase 12 Memory Plane still operates normally
   - New gossip messages (escrow, consensus) integrated
   - Background jobs (timeout, healing, consensus check) scheduled
   - Audit logs updated

✅ Documentation:
   - Phase 13 Architecture Lock document written
   - Roadmap to Phase 14 drafted
   - Known unknowns listed
   - Performance assumptions documented
```

---

## Part 10: Known Unknowns & Research Items

### 10.1 Algorithm Efficiency

```
Question: Is Tarjan's SCC optimal for real-time cycle detection?
  - Current: O(V+E) time complexity
  - Alternative: Incremental cycle detection on grant changes
  - Research: Benchmark both for N=100 sovereigns, E=500 grants
  - Decision point: Phase 13 testing
```

### 10.2 Consensus Timeout Strategy

```
Question: Should consensus timeout be adaptive (based on network latency)?
  - Current: Fixed 24h timeout
  - Alternative: Exponential backoff (1h → 3h → 12h)
  - Research: Measure peer responsiveness in Phase 13
  - Decision point: Task 68 implementation
```

### 10.3 Escrow Dispute Resolution

```
Question: Should disputed escrow go to arbitration (Phase 15)?
  - Current: Defer to Phase 15 (full arbitration)
  - Alternative: Simple split (50/50 token return)
  - Decision point: Phase 13 lock (discuss with stakeholders)
```

---

## Conclusion

**Phase 13 is SPECIFICATION LOCKED.** All 5 tasks (66–70) are fully detailed with:

- Algorithms (Tarjan's SCC, 2-phase commit)
- Data structures (ReputationCycle, EscrowLedger, ConsensusProposal)
- Rust function signatures (exact parameter types, return types)
- Database schema (SQL migrations, CHECK constraints)
- Tests (40+ tests covering happy path, edge cases, chaos)
- Invariants (2 new constitutional laws + Phase 12 locks)

**Ready for implementation immediately upon Phase 12 acceptance.**

---

**Tasks 66–70 Implementation Status:** Ready to Begin ✅  
**Estimated Effort:** 400–500 engineer-hours  
**Timeline:** 8 weeks (with 2-person team, 50 hrs/week)  
**Parallel Execution:** Yes (66+67 → 68+69 → 70)  
**Dependencies:** Phase 12 complete ✅  
**Next Gate:** Phase 13 Lock Document (after all tests pass)  
