# Phase 12: Memory Plane Specification

**Version:** 2026-05-10  
**Status:** ARCHITECTURAL FOUNDATION (Pre-Implementation)  
**Authority:** Phase Architects  
**Scope:** Epistemic Substrate for Phases 4–11 + SMAOS Planes  

---

## Executive Summary

The **Memory Plane** is the unified epistemic substrate that consolidates all state from Phases 4–11 (identity, attestation, delegation, governance, behavior, federation, reputation) into a coherent, queryable, time-aware world-model consumed by:

- **SMAOS Operator Plane** (policy governance, operator decisions, federation coordination)
- **SMAOS Execution Plane** (agent runtime, task execution, decision-making)

**Core Thesis:** Memory is not scattered across tables. It is a *single unified namespace* partitioned by domain (identity, trust, delegation, economics, behavior, federation) with:
- **Temporal guarantees** (append-only, immutable versions, causal ordering, time-travel reconstruction)
- **Isolation boundaries** (home sovereign, foreign sovereign, bilateral shared space)
- **Governance hooks** (SISS tier ceilings, federation caps, behavior scoring feedback loops)
- **Atomicity** (transactional intents guarantee consistency across domains)

This specification defines the **physics** of that substrate.

---

## 1. Core Principles

### 1.1 Single Epistemic Truth

**Rule:** There is one canonical representation of each agent/sovereign's state at any moment.  
**Consequence:** No shadow copies, no eventual consistency caches, no stale replicas.  
**Guarantee:** All queries against the Memory Plane return the same truth, every time.

### 1.2 Append-Only Immutability

**Rule:** Once written, memory events are never updated or deleted.  
**Consequence:** Complete audit trail preserved forever.  
**Guarantee:** Forensic reconstruction of any past state is always possible.

### 1.3 Temporal Causality

**Rule:** Events are ordered by causality (happened-before relation), not clock time.  
**Consequence:** Distributed agents can reconstruct consistent timelines without global clock.  
**Guarantee:** Causal consistency across sovereigns without synchronized time.

### 1.4 Fail-Closed Access

**Rule:** Memory queries honor SISS tier ceilings and federation agreements.  
**Consequence:** Access denial is the default; grants must be explicit.  
**Guarantee:** No information leakage across sovereignty boundaries.

### 1.5 Governance Integration

**Rule:** SMAOS Operator Plane policies enforce all memory access constraints.  
**Consequence:** Memory Plane becomes the enforcement point for all governance.  
**Guarantee:** Operator decisions are immediately reflected in what agents can read/write.

---

## 2. Memory Object Types

### 2.1 Identity Objects

**Namespace:** `/sovereign/{sovereign_id}/identity/*`  
**Lifetime:** Immutable (created once, never modified)

```
IdentityObject {
  id: Uuid                      (unique per sovereign)
  object_type: "identity"
  sovereign_id: Uuid
  sovereign_name: String
  public_key_pem: String        (Ed25519)
  endpoint_url: Option<String>
  created_at: DateTime<Utc>
  
  // Phase 11: Discovery fields
  is_discoverable: bool
  discovery_metadata: Option<serde_json::Value>
  
  // Governance
  operator_policy_version: u32  (which Operator policy applies)
  isolation_level: "home" | "foreign"
}
```

**Governance Hooks:**
- Operator Plane policy `discovery_allowed` gates `is_discoverable=true` writes
- Execution Plane can read full identity only if tier ≥ 2
- Foreign sovereigns see endpoint_url only if `is_discoverable=true`

**Mutation Rules:** IMMUTABLE (no updates after creation)

---

### 2.2 Trust Objects

**Namespace:** `/sovereign/{sovereign_id}/trust/*`  
**Lifetime:** Versioned (new version on each state change)

```
TrustObject {
  id: Uuid                      (agent_id for home, shadow_persona_id for foreign)
  version: u64                  (monotonically increasing)
  object_type: "trust"
  
  // Phase 4–5: Attestation & Tier
  attestations: Vec<Attestation>
  trust_score: u32              (0–120)
  tier: u32                     (1=FULL, 2=STANDARD, 3=MINIMAL, null=DENY)
  
  // Phase 8: Behavior Scoring
  behavior_events: Vec<BehaviorEvent>
  behavior_score_delta: i32     (net tier adjustment from behavior)
  effective_tier: u32           (tier + behavior_delta, clamped)
  
  // Phase 9: Federation
  lineage_safe: bool            (true=home, false=foreign)
  source_sovereign_id: Uuid     (if foreign)
  
  // Phase 11: Reputation
  reputation_signals: Vec<ReputationSignal>
  blended_tier: Option<u32>     (if foreign reputation available)
  
  // Temporal
  computed_at: DateTime<Utc>
  valid_until: DateTime<Utc>
  previous_version_id: Option<Uuid>
  
  // Governance
  federation_peer_id: Option<Uuid>  (if cross-sovereign)
  operator_policy_version: u32
}
```

**Governance Hooks:**
- Tier ceilings from SISS Phase 6 delegation envelope enforced on `effective_tier`
- Tier ceilings from Phase 9 bilateral federation agreements enforced on `effective_tier`
- Tier ceilings from Phase 11 cross-sovereign delegation grants enforced on `effective_tier`
- Behavior scoring (Phase 8) automatically updates `behavior_score_delta` on event insertion
- Reputation blending (Phase 11) automatically updates `blended_tier` when new signals arrive
- REPUTATION_ISOLATION invariant enforced: `blended_tier ≤ home_tier` always

**Mutation Rules:** VERSIONED (create new version, never modify existing)

---

### 2.3 Delegation Objects

**Namespace:** `/sovereign/{sovereign_id}/delegation/*`

#### 2.3a Intra-Sovereign Delegation (Phase 6)

```
DelegationObject {
  id: Uuid                      (delegation_edge_id)
  version: u64
  object_type: "delegation/intra"
  
  parent_agent_id: String
  child_agent_id: String
  parent_persona_id: Uuid
  child_persona_id: Uuid
  
  // Immutable Ceiling
  ceiling_tier: u32
  ceiling_delegations: Vec<String>
  ceiling_constraints: JSONB    (rate_limit, burst, interval, concurrent)
  
  // Budget
  budget_initial: i64
  budget_remaining: i64
  budget_consumed: i64
  
  // Temporal
  delegated_at: DateTime<Utc>
  expires_at: Option<DateTime<Utc>>
  revoked_at: Option<DateTime<Utc>>
  status: "active" | "expired" | "revoked"
  
  // Governance
  tenant_id: Uuid
  delegation_certificate: String  (signed by parent)
}
```

**Governance Hooks:**
- Operator Plane policy `max_delegation_depth` enforces acyclicity
- Parent tier ceiling immutable; cannot be renegotiated mid-session
- Revocation cascades to all descendants (Phase 6.1)
- Budget cannot be relaxed (only tightened via new delegation)

#### 2.3b Cross-Sovereign Delegation (Phase 11)

```
CrossSovereignDelegationObject {
  id: Uuid
  version: u64
  object_type: "delegation/cross_sovereign"
  
  grantor_agent_id: String
  grantor_sovereign_id: Uuid
  grantee_agent_id: String
  grantee_sovereign_id: Uuid
  
  // Federation context
  federation_peer_id: Uuid      (bilateral agreement)
  
  // Ceiling (immutable)
  ceiling_tier: i16
  ceiling_attestation_types: Vec<String>
  
  // TRANSITIVITY_DEPTH_MAX enforcement
  transitivity_depth: i16       (1–3, immutable)
  parent_grant_id: Option<Uuid> (link to grantor's grant)
  
  // Temporal
  granted_at: DateTime<Utc>
  expires_at: Option<DateTime<Utc>>
  revoked_at: Option<DateTime<Utc>>
  status: "active" | "expired" | "revoked"
  
  // Cryptographic commitment
  grant_signature: String       (Ed25519 over canonical payload)
  
  // Governance
  operator_policy_version: u32
}
```

**Governance Hooks:**
- TRANSITIVITY_DEPTH_MAX=3 enforced by DB CHECK + code validation
- Depth never decreases (if parent is depth 2, child must be depth 3)
- Revocation cascades to all derived grants (depth chains)
- Grant signature verified on creation; cannot be modified
- Federation peer must be active; otherwise grant blocks tier capping

**Mutation Rules:**
- Intra-sovereign: VERSIONED
- Cross-sovereign: immutable after creation (status updates only for revocation)

---

### 2.4 Session Objects

**Namespace:** `/sovereign/{sovereign_id}/session/*`

```
SessionObject {
  id: Uuid
  version: u64
  object_type: "session"
  
  // Identity
  agent_id: String              (home agent)
  persona_id: Uuid
  session_token: String         (opaque JWT or UUID)
  
  // Trust at issuance
  trust_tier_at_issue: u32
  trust_score_at_issue: u32
  
  // Delegation context (Phase 6)
  parent_session_id: Option<Uuid>
  delegation_ceiling_tier: Option<u32>
  delegation_constraints: Option<JSONB>
  
  // Budget (Phase 7)
  token_budget_initial: i64
  token_budget_remaining: i64
  token_budget_consumed: i64
  
  // Temporal
  issued_at: DateTime<Utc>
  valid_until: DateTime<Utc>
  last_refreshed_at: DateTime<Utc>
  revoked_at: Option<DateTime<Utc>>
  status: "active" | "refreshing" | "revoked" | "expired"
  
  // Rate limiting (Phase 7)
  rate_limit_violations: u32
  last_refresh_rate_check: DateTime<Utc>
  
  // Federation (Phase 9–10)
  is_federated: bool
  source_sovereign_id: Option<Uuid>  (if federated)
  bilateral_agreement_id: Option<Uuid>
  
  // Governance
  operator_policy_version: u32
  lineage_cache: JSONB          (ancestor UUIDs for OPSEC)
}
```

**Governance Hooks:**
- Budget cannot exceed parent's remaining budget (Phase 7)
- Tier cannot exceed delegation ceiling (Phase 6)
- Rate limits inherited from delegation; cannot be relaxed
- Revocation cascades to all child sessions (Phase 6.1)
- Foreign sessions subject to bilateral federation agreement tier caps (Phase 9)
- Federated foreign sessions subject to cross-sovereign delegation grant ceilings (Phase 11)

**Mutation Rules:** VERSIONED

---

### 2.5 Reputation Objects

**Namespace:** `/sovereign/{sovereign_id}/reputation/*`

```
ReputationObject {
  id: Uuid
  version: u64
  object_type: "reputation"
  
  // Identity
  source_sovereign_id: Uuid
  subject_agent_id: String
  
  // Signals (Phase 11)
  signals: Vec<ReputationSignal> {
    strength: i16               (-10 to +10)
    signal_type: "positive" | "negative" | "neutral"
    observed_at: DateTime<Utc>
    source_gossip_message_id: Option<Uuid>
    signal_signature: String
    
    // REPUTATION_ISOLATION enforcement
    lineage_safe: bool          (always false for foreign signals)
  }
  
  // Aggregates
  signal_count: u32
  net_signal_strength: i32
  signal_window_days: i64       (e.g., 7 days)
  
  // Blending configuration (Phase 11)
  federation_peer_id: Uuid
  reputation_blend_weight: f64  (0.0–1.0)
  
  // Temporal
  created_at: DateTime<Utc>
  last_signal_at: DateTime<Utc>
  decay_applies: bool           (exponential decay with 3.5-day half-life)
  
  // Governance
  operator_policy_version: u32
  REPUTATION_ISOLATION_enforced: bool  (always true)
}
```

**Governance Hooks:**
- REPUTATION_ISOLATION invariant enforced: all foreign signals have `lineage_safe=false`
- Blend weight (0.0–1.0) configured per bilateral federation peer
- Exponential decay applied at read time (half-life 3.5 days, Phase 8 pattern)
- Operator Plane policy `reputation_blending_allowed` gates blend weight changes

**Mutation Rules:** Signals are APPEND-ONLY; aggregates are COMPUTED at read time

---

### 2.6 Federation Objects

**Namespace:** `/sovereign/{sovereign_id}/federation/*`

#### 2.6a Bilateral Agreement (Phase 9)

```
BilateralAgreementObject {
  id: Uuid                      (federation_peer_id)
  version: u64
  object_type: "federation/bilateral"
  
  // Parties
  sovereign_a_id: Uuid
  sovereign_b_id: Uuid
  
  // Tier & Attestation (Phase 9)
  max_admitted_tier: i16        (immutable)
  granted_attestation_types: Vec<String>
  
  // Economics (Phase 9)
  foreign_agent_budget_cap: i64 (immutable)
  foreign_agent_budget_consumed: i64
  
  // Reputation blending (Phase 11)
  reputation_blend_weight: f64  (0.0–1.0)
  
  // Temporal
  established_at: DateTime<Utc>
  valid_from: DateTime<Utc>
  expires_at: Option<DateTime<Utc>>
  renegotiated_at: Option<DateTime<Utc>>
  status: "active" | "superseded" | "revoked"
  
  // Governance
  agreement_signature: String   (Ed25519)
  operator_policy_version: u32
}
```

**Governance Hooks:**
- Tier ceiling immutable after creation; enforced on all federated sessions
- Budget cap enforced atomically (Phase 11 Gap 2 fix)
- Superseded agreements remain in table for audit (never deleted)
- Operator Plane policy `federation_allowed` gates creation/renegotiation

#### 2.6b Dynamic Renegotiation (Phase 10)

```
RenegotiationEventObject {
  id: Uuid
  version: u64
  object_type: "federation/renegotiation"
  
  old_agreement_id: Uuid
  new_agreement_id: Uuid
  renegotiated_by: Uuid         (which agent initiated)
  
  // What changed
  tier_change_delta: i16
  budget_change_delta: i64
  attestation_types_delta: Vec<String>
  reputation_blend_weight_delta: f64
  
  // Temporal
  occurred_at: DateTime<Utc>
  effective_at: DateTime<Utc>   (may be retroactive)
  
  // Cryptographic commitment
  renegotiation_signature: String  (Ed25519)
  
  // Governance
  operator_policy_version: u32
}
```

**Governance Hooks:**
- Old agreement marked "superseded" (Phase 10)
- New caps take effect on next refresh pull
- Active sessions continue under old caps until refresh
- Operator Plane policy `renegotiation_allowed` gates creation

---

### 2.7 Behavior Event Objects

**Namespace:** `/sovereign/{sovereign_id}/behavior/*`

```
BehaviorEventObject {
  id: Uuid
  version: u64
  object_type: "behavior_event"
  
  // Identity
  agent_id: String
  persona_id: Uuid
  
  // Event
  event_type: String            (e.g., "successful_execution", "policy_violation", "rate_limit_exceeded")
  tier_delta: i16               (-10 to +10)
  magnitude: f32                (semantic strength)
  
  // Temporal
  occurred_at: DateTime<Utc>
  recorded_at: DateTime<Utc>
  
  // Decay
  lineage_safe: bool            (Phase 9: poison-pill defense)
  decay_applies: bool           (exponential decay, half-life 3.5 days)
  weight_at_read_time: f64      (computed on query)
  
  // Governance
  behavior_scorer_version: u32
  operator_policy_version: u32
}
```

**Governance Hooks:**
- Lineage safety enforced: foreign behavior events have `lineage_safe=false` always
- Behavior scorer (Phase 8) automatically applies decay at read time
- Operator Plane policy `behavior_scoring_enabled` gates event recording
- Tier delta clamped to [MIN_TIER_DELTA, MAX_TIER_DELTA] at scorer

**Mutation Rules:** APPEND-ONLY

---

### 2.8 Economic Event Objects

**Namespace:** `/sovereign/{sovereign_id}/economics/*`

```
EconomicEventObject {
  id: Uuid
  version: u64
  object_type: "economic_event"
  
  // Transaction
  event_type: "token_issuance" | "token_consumption" | "budget_allocation" | "credit_entry" | "invoice"
  
  // Parties
  actor_id: Option<String>      (if applicable)
  creditor_sovereign_id: Option<Uuid>
  debtor_sovereign_id: Option<Uuid>
  
  // Values
  tokens: i64
  tier_at_time: u32             (what tier triggered the cost)
  attestation_count: u32        (for cost calculation)
  
  // Temporal
  occurred_at: DateTime<Utc>
  session_id: Option<Uuid>
  
  // Audit
  cost_breakdown: JSONB         (base + tier_penalty + attestation_cost)
  
  // Governance
  budget_remaining_after: i64
  operator_policy_version: u32
}
```

**Governance Hooks:**
- Token issuance respects session budget remaining (Phase 7)
- Cost calculation respects tier (Phase 7)
- Credit entries append-only (Phase 9)
- Operator Plane policy `token_issuance_allowed` gates issuance

**Mutation Rules:** APPEND-ONLY

---

### 2.9 Convergence & Gossip Objects

**Namespace:** `/sovereign/{sovereign_id}/gossip/*`

```
GossipMessageObject {
  id: Uuid
  version: u64
  object_type: "gossip_message"
  
  // Message
  message_type: "revocation" | "renegotiation" | "heartbeat" | "reputation_signal" | "peer_announcement"
  
  // Source
  source_sovereign_id: Uuid
  gossip_seq: i64               (monotonically increasing per source)
  
  // Content
  payload: serde_json::Value
  payload_signature: String     (Ed25519)
  
  // Delivery
  received_at: DateTime<Utc>
  processed_at: Option<DateTime<Utc>>
  processed_action: Option<String>  (e.g., "revoked_agent", "updated_agreement", "inserted_signal")
  
  // Idempotency (Phase 10)
  idempotency_key: (source_sovereign_id, gossip_seq)
  
  // Governance
  operator_policy_version: u32
}
```

**Governance Hooks:**
- Idempotency enforced via UNIQUE(source_sovereign_id, gossip_seq)
- gossip_seq monotonically updated (Phase 11 Gap 1 fix)
- Signature verified before processing
- Operator Plane policy `gossip_broadcast_allowed` gates broadcast authorization

**Mutation Rules:** APPEND-ONLY + processed_at/processed_action can be set once

---

### 2.10 Dispute & Resolution Objects

**Namespace:** `/sovereign/{sovereign_id}/dispute/*`

```
DisputeObject {
  id: Uuid                      (invoice_id)
  version: u64
  object_type: "dispute"
  
  // Invoice context
  creditor_sovereign_id: Uuid
  debtor_sovereign_id: Uuid
  invoice_id: Uuid
  
  // Lifecycle (Phase 11)
  invoice_status: "pending" | "acknowledged" | "disputed" | "settled"
  
  // Dispute details
  dispute_reason: Option<String>
  dispute_evidence: Option<JSONB>
  disputed_at: Option<DateTime<Utc>>
  
  // Resolution
  dispute_resolution: Option<String>  ("upheld" | "rejected" | "partial")
  dispute_resolved_at: Option<DateTime<Utc>>
  
  // Temporal
  acknowledged_at: Option<DateTime<Utc>>
  settled_at: Option<DateTime<Utc>>
  
  // Governance
  operator_policy_version: u32
}
```

**Governance Hooks:**
- INVOICE_STATUS_MONOTONIC enforced: pending→acknowledged→(settled|disputed) only
- Dispute requires creditor acknowledgment OR debtor initiation
- Resolution recorded but doesn't auto-execute (Phase 12 escrow)
- Operator Plane policy `dispute_allowed` gates dispute initiation

**Mutation Rules:** VERSIONED (status transitions create new versions)

---

## 3. Temporal Guarantees

### 3.1 Append-Only History

**Rule:** All events are immutable after creation. Updates never overwrite; new versions are created.

**Consequence:** Complete forensic audit trail.

**Example:** Trust tier changes don't delete old events; new versions are created with `previous_version_id` link.

### 3.2 Causal Ordering

**Rule:** Events are ordered by causality (happened-before), not wall-clock time.

**Consequence:** Distributed agents reconstruct consistent timelines without synchronized clocks.

**Implementation:**
- Each Memory object carries `vector_clock` (lamport clock per domain)
- Cross-domain causality via `parent_event_id` references
- Queries return events in causal order, not timestamp order

### 3.3 Version Chains

**Rule:** Versioned objects link to previous versions via `previous_version_id`.

**Consequence:** Time-travel queries can reconstruct any past state.

**Example:** Query trust object at `trust_snapshot_at(agent_id, datetime)` returns exact tier + attestations at that moment.

### 3.4 Time-Travel Reconstruction

**Rule:** Given a datetime, Memory Plane returns the state that was valid at that moment.

**Implementation:**
- For VERSIONED objects: traverse `previous_version_id` chain until you find `created_at ≤ query_time`
- For APPEND-ONLY objects: filter `recorded_at ≤ query_time`, aggregate current state
- Decayed values (behavior, reputation) recalculated at `query_time`, not original time

**Example:**
```
memory.trust_at_time(agent_id, "2026-04-01T12:00:00Z")
  → returns tier, score, attestations, behavior_events as they were on that date
  → behavior events decayed as if evaluated on 2026-04-01, not now
```

---

## 4. Isolation Boundaries

### 4.1 Home Sovereign Memory

**Namespace:** `/sovereign/{home_sovereign_id}/*`  
**Visibility:** Full (home agents with sufficient tier can read all home memory)  
**Mutability:** Home sovereign can write all object types

**Example:** Home agent with tier 1 can read all identity, trust, delegation, behavior of other home agents (subject to Operator Plane policy).

### 4.2 Foreign Sovereign Memory (Shadow)

**Namespace:** `/sovereign/{home_sovereign_id}/federation/{foreign_sovereign_id}/shadow/*`  
**Visibility:** Limited to delegation context (what was granted in bilateral agreement)  
**Mutability:** Read-only (foreign agents cannot write to home shadow)

**Rule:** Foreign agent identity, trust, delegation, behavior visible to home only if:
1. Bilateral agreement exists AND is active
2. Home tier ≥ 2 (STANDARD or FULL)
3. Foreign attestation types match `granted_attestation_types`

**Example:** If bilateral agreement grants "SovereignOrigin" attestations only, home cannot see "HardwareEnclave" attestations from foreign agent.

### 4.3 Bilateral Shared Memory

**Namespace:** `/shared/{sovereign_a_id}+{sovereign_b_id}/*`  
**Visibility:** Both sovereigns (full mutual visibility for federation data)  
**Mutability:** Both can read; limited write (e.g., invoice settlement requires debtor write)

**Example:**
- `/shared/sovereign_a+sovereign_b/settlement_invoices/` — shared invoice ledger
- Both sovereigns query invoices, but debtor must write settlement acknowledgment

### 4.4 Cross-Sovereignty Gossip Propagation

**Rule:** Gossip messages propagate only to sovereigns with active bilateral agreements.

**Example:** 
- Sovereign A revokes agent X
- Revocation gossip broadcast to all sovereigns in active bilateral agreements with A
- Non-federated sovereigns never see the message

**Consequence:** Revocation cascades only follow federation topology, not flood all sovereigns.

---

## 5. Governance Hooks (SMAOS Integration)

### 5.1 Operator Plane Policy Enforcement

**Integration Point:** Every Memory Plane write is gated by `operator_policy_version`.

**Pattern:**
```
IF memory.write(object, value):
  policy = operator_plane.get_policy(operator_policy_version)
  IF NOT policy.permits(object_type, value, actor_tier):
    DENY (403)
  ELSE:
    WRITE and update object.operator_policy_version
```

**Examples:**

| Policy | Enforcement |
|--------|-------------|
| `discovery_allowed` | Blocks writes to `is_discoverable=true` unless policy permits |
| `federation_allowed` | Blocks bilateral agreement creation if policy forbids |
| `reputation_blending_allowed` | Blocks reputation_blend_weight updates if policy forbids |
| `behavior_scoring_enabled` | Blocks behavior event recording if policy disabled |
| `gossip_broadcast_allowed` | Blocks gossip message broadcast if policy forbids |
| `token_issuance_allowed` | Blocks token issuance if policy forbids |

### 5.2 SISS Tier Ceiling Enforcement

**Integration Point:** All tier calculations respect SISS delegation + federation + cross-sovereign ceilings.

**Pattern:**
```
effective_tier = min(
  attestation_tier,                                      // Phase 4–5
  delegation_ceiling_tier || ∞,                          // Phase 6
  bilateral_federation_admitted_tier || ∞,              // Phase 9
  cross_sovereign_delegation_grant.ceiling_tier || ∞    // Phase 11
)
```

**Enforcement Location:** `TrustObject.effective_tier` updated on:
1. Attestation change → new attestation_tier computed
2. Delegation change → new delegation_ceiling_tier applied
3. Bilateral agreement renegotiation → new federation ceiling applied
4. Cross-sovereign grant creation/revocation → new grant ceiling applied

### 5.3 Behavior Scoring Feedback Loop

**Integration Point:** Behavior events automatically update trust tier via scorer.

**Pattern:**
```
behavior_event.write(event)
  ↓
behavior_scorer.apply_decay(event, now)
  ↓
tier_delta = scorer.compute_tier_delta(all_events, now)
  ↓
trust_object.behavior_score_delta = tier_delta
  ↓
trust_object.effective_tier = min(tier + tier_delta, ceiling)
```

**Consequence:** Behavior automatically feeds into trust tier without explicit refresh.

### 5.4 Reputation Blending & REPUTATION_ISOLATION

**Integration Point:** Foreign reputation signals feed into trust via blender.

**Pattern:**
```
reputation_signal.write(signal, source_sovereign_id=FOREIGN)
  ↓
signal.lineage_safe = false  // enforced by DB CHECK
  ↓
reputation_blender.reputation_signals_to_behavior_events(signals)
  ↓
foreign_scorer = BehaviorScorer(foreign_events, now)
  ↓
foreign_tier = foreign_scorer.apply_tier_delta(home_tier)
  ↓
blended = home_tier * (1 - weight) + foreign_tier * weight
  ↓
REPUTATION_ISOLATION: blended_tier = min(blended, home_tier)  // enforced in blender
  ↓
trust_object.blended_tier = blended_tier
```

**Guarantee:** Foreign signals never boost tier above home-only tier.

### 5.5 Budget Consumption Tracking

**Integration Point:** Token issuance atomically decrements budget.

**Pattern:**
```
token_issuance_request(session_id, attestation_count)
  ↓
cost = base(100) + tier_penalty(tier) + attestation_cost(10 * count)
  ↓
IF session.budget_remaining < cost:
  DENY (402 insufficient budget)
  ↓
ELSE:
  atomic {
    session.budget_consumed += cost
    session.budget_remaining -= cost
    economic_event.write(token_issuance, cost_breakdown)
  }
```

### 5.6 Foreign Agent Budget Cap Enforcement

**Integration Point:** Federated sessions consume from bilateral cap.

**Pattern (Phase 11 Gap 2 fix):**
```
federated_session_request(source_sovereign_id, agent_id)
  ↓
bilateral = federation_agreement(home, source_sovereign)
  ↓
IF bilateral.foreign_agent_budget_consumed + tokens_needed > bilateral.foreign_agent_budget_cap:
  DENY (402 budget cap exceeded)
  ↓
ELSE:
  atomic {
    bilateral.foreign_agent_budget_consumed += tokens_needed
    credit_entry.write(consumed_by=agent_id)
  }
```

### 5.7 Gossip Monotonic Sequencing

**Integration Point:** gossip_seq enforced monotonic per (source_sovereign, session).

**Pattern (Phase 11 Gap 1 fix):**
```
gossip_receive(source_sovereign_id, gossip_seq, payload)
  ↓
federation_peer = lookup(source_sovereign_id)
  ↓
IF gossip_seq <= federation_peer.gossip_seq:
  WARN "out-of-order gossip"
  ↓
ELSE:
  atomic {
    federation_peer.gossip_seq = max(federation_peer.gossip_seq, gossip_seq)
    gossip_message.write(payload)
  }
```

---

## 6. Atomicity & Transactional Intents

### 6.1 Memory Intent API

**Rule:** All Memory Plane writes are transactional intents (not direct writes).

**Pattern:**
```
MemoryIntent {
  intent_id: Uuid
  intent_type: "Read" | "Write" | "Subscribe" | "Revoke" | "Trace"
  actor_id: String
  actor_tier: u32
  target_object: Object
  target_value: Value
  governance_check: PolicyEvaluation
  status: "pending" | "committed" | "failed"
  timestamp: DateTime<Utc>
}
```

### 6.2 Write Atomicity

**Rule:** All writes are all-or-nothing with governance checks.

**Example (Session Refresh):**
```
RefreshIntent {
  session_id, new_attestations, proof
  ↓
  1. Compute new trust_tier
  2. Apply behavior_score_delta
  3. Apply reputation_blending
  4. Cap to delegation_ceiling
  5. Cap to federation_ceiling
  6. Cap to cross_sovereign_ceiling
  7. Check budget_remaining
  8. Compute token_cost
  9. Create new TrustObject version
  10. Create new SessionObject version
  11. Create EconomicEventObject
  12. Persist all 3 atomically OR ABORT ALL
}
```

**Guarantee:** Either all updates succeed or none do; no partial state.

### 6.3 Subscribe (Temporal Materialization)

**Rule:** Agents can subscribe to memory object changes and receive deltas.

**Example:**
```
memory.subscribe("/sovereign/{id}/trust/{agent_id}", "version_delta")
  → emits: {old_version, new_version, changed_fields, timestamp}
```

**Use Case:** Agent dashboards materialize trust tier changes in real-time.

### 6.4 Trace (Forensic Reconstruction)

**Rule:** Operators can trace causality chain of any decision.

**Example:**
```
memory.trace(agent_id, "tier_changed_to_2", datetime)
  ↓
  Shows:
    1. Attestation added → score changed → tier changed
    2. Behavior event added → score_delta changed → tier changed
    3. Reputation signal added → blended_tier changed
    4. Federation agreement superseded → effective_tier changed
    5. (All causality chains in order)
```

---

## 7. Query Language Fundamentals

### 7.1 Object Queries

**Pattern:**
```
memory.get(object_type, object_id)
  → returns current version

memory.get_version(object_type, object_id, version_id)
  → returns specific version

memory.get_at_time(object_type, object_id, datetime)
  → returns state valid at that datetime

memory.find(object_type, {filters})
  → returns all matching objects (respecting access control)

memory.find_at_time(object_type, {filters}, datetime)
  → returns all matching objects as they were at datetime
```

### 7.2 Aggregation Queries

**Pattern:**
```
memory.aggregate("trust_score", object_type="trust", filters={agent_id, home_only=true})
  → returns sum of trust_scores for agent across all sovereigns

memory.aggregate_at_time("trust_score", ..., datetime)
  → aggregate as it was at datetime
```

### 7.3 Causality Queries

**Pattern:**
```
memory.causality_chain(object_id)
  → returns all events that led to current state
  
memory.depends_on(object_id)
  → returns all objects that depend on this one
  
memory.depended_by(object_id)
  → returns all objects this one depends on
```

---

## 8. Constitutional Invariants (Enforced)

### 8.1 TRANSITIVITY_DEPTH_MAX = 3

**Enforcement:**
- DB CHECK: `cross_sovereign_delegation_grants.transitivity_depth BETWEEN 1 AND 3`
- Code: `insert_cross_sovereign_grant()` rejects if depth > 3
- Memory Hook: `CrossSovereignDelegationObject.transitivity_depth` validated before commit

### 8.2 REPUTATION_ISOLATION

**Enforcement:**
- DB CHECK: `federated_reputation_signals.lineage_safe = FALSE` (immutable)
- Code: `reputation_blender.blend_reputation_scores()` enforces `blended_tier ≤ home_tier`
- Memory Hook: `ReputationObject.REPUTATION_ISOLATION_enforced` always true

### 8.3 INVOICE_STATUS_MONOTONIC

**Enforcement:**
- Code: `acknowledge_invoice()` only succeeds if status = 'pending'
- Code: `dispute_invoice()` only succeeds if status = 'acknowledged'
- Code: `mark_invoice_settled_v2()` only succeeds if status ∈ ['pending', 'acknowledged']
- Memory Hook: `DisputeObject.invoice_status` transition validated before commit

### 8.4 DISCOVERY_OPT_IN_REQUIRED

**Enforcement:**
- Code: `set_sovereign_discoverable(true)` requires endpoint_url IS NOT NULL
- DB CHECK: `is_discoverable=true` with endpoint_url IS NULL prevented at DB layer
- Memory Hook: `IdentityObject.is_discoverable` write gated by endpoint_url presence

---

## 9. Example: Complete Trust Refresh Materialization

### 9.1 Agent Requests Token Refresh

**Input:**
```
RefreshRequest {
  session_token: "...",
  attestations: [HardwareEnclave, SovereignOrigin],
  proof_signature: "...",
  agent_id: "agent_a",
  source_sovereign_id: home_id or foreign_id
}
```

### 9.2 Memory Plane Orchestration

**Step-by-step memory state transitions:**

```
1. SessionObject lookup by token
   → version N: status=active, tier=2

2. TrustObject lookup for agent_a
   → version M: attestations=[old_hw], trust_score=70, tier=2, behavior_score_delta=+1

3. Insert new BehaviorEvent
   → "refresh_request_received", tier_delta=0 (neutral event)

4. Recalculate TrustObject based on new attestations
   → new_attestations = [HardwareEnclave, SovereignOrigin]
   → new_trust_score = 95
   → new_tier = 2 (STANDARD)

5. Apply behavior scoring
   → behavior_events = [refresh_request_received]
   → score_delta = +0 (no delta)
   → effective_tier = min(2, 0 + 2) = 2

6. Check delegation ceiling
   → parent_session_id ≠ null → delegation_ceiling_tier = 2
   → effective_tier = min(2, 2) = 2

7. Check federation ceiling (if federated)
   → bilateral_admitted_tier = 3
   → effective_tier = min(2, 3) = 2

8. Check cross-sovereign delegation ceiling (if applicable)
   → grant.ceiling_tier = 2
   → effective_tier = min(2, 2) = 2

9. Compute token cost
   → cost = base(100) + tier_penalty(-20 for tier 2) + attestation_cost(20)
   → cost = 100

10. Check session budget
    → session.budget_remaining = 50000
    → IF 50000 < 100: DENY (402)
    → ELSE: PROCEED

11. Create new TrustObject version
    → version N+1: tier=2, effective_tier=2, attestations=[new], timestamp=now

12. Create new SessionObject version
    → version P+1: issued_at=now, valid_until=now+5min, budget_remaining=49900

13. Create EconomicEventObject
    → tokens=100, cost_breakdown={base: 100, tier_penalty: -20, attestation_cost: 20}

14. Commit all 3 objects atomically
    → If any governance check fails, ABORT all

15. Emit MemoryIntent subscription notifications
    → agents subscribed to agent_a's trust receive: {old_version=M, new_version=N+1}
    → agents subscribed to session receive: {old_version=P, new_version=P+1}

16. Return RefreshResponse
    → new_session_token, capability_token, tier=2, valid_until
```

**Final State:**
- TrustObject version N+1: tier=2, effective_tier=2
- SessionObject version P+1: budget_remaining=49900
- EconomicEventObject: cost tracked
- All 3 atomically persisted

---

## 10. Governance Policy Integration (Placeholder)

### 10.1 Policy Evaluation Hooks

Each Memory Plane write consults the Operator Plane policy:

```
operator_policy.evaluate(
  actor_id, actor_tier, intent_type, target_object, target_value
)
  ↓ returns: "PERMIT" | "DENY" | "REQUIRE_ESCALATION"
```

**Policy Dimensions:**
- `federation_allowed`: Can agents create bilateral agreements?
- `discovery_allowed`: Can sovereigns opt-in to discovery?
- `behavior_scoring_enabled`: Are behavior events recorded?
- `reputation_blending_allowed`: Can foreign reputation influence tier?
- `gossip_broadcast_allowed`: Can gossip messages broadcast to peers?
- `token_issuance_allowed`: Can tokens be issued to agents?
- `dispute_allowed`: Can invoices be disputed?

**Implementation:** Phase 12 task (not in this spec).

---

## 11. API Surface Preview (Sketch for Phase 12)

**Not formalized here, but preview:**

```rust
// Read
memory.get::<TrustObject>(agent_id)
memory.get_at_time::<TrustObject>(agent_id, datetime)

// Write (via Intent)
memory.write(RefreshIntent {
  session_id, new_attestations, proof, actor_id, actor_tier
})

// Subscribe
memory.subscribe::<TrustObject>(agent_id, callback)

// Trace
memory.trace(agent_id, "tier_delta_applied", datetime)

// Query
memory.find::<SessionObject>({agent_id, status: "active"})
```

---

## 12. Roadmap: Phase 12 Implementation

### Tasks 59–65: Namespace Schema + Implementation

1. **Task 59:** Namespace Schema (design partition hierarchy, visibility rules, indices)
2. **Task 60:** View Definition DSL (query language for forensics)
3. **Task 61:** API Surface Formalization (Intent types, response protocols)
4. **Task 62:** Memory Plane Persistence Layer (Postgres schema mapping, migration 024+)
5. **Task 63:** Governance Hook Integration (operator policy evaluation at write time)
6. **Task 64:** Full Test Suite (integration tests for all object types, governance enforcement)
7. **Task 65:** Architecture Lock (Memory Plane final specification + Phases 12+ roadmap)

---

## Conclusion

The Memory Plane unifies Phases 4–11 into a single epistemic substrate with:
- **Immutable, append-only history** (complete forensic audit)
- **Temporal guarantees** (causal ordering, time-travel reconstruction)
- **Isolation boundaries** (home, foreign, bilateral shared)
- **Governance hooks** (SMAOS Operator/Execution Plane integration)
- **Constitutional invariants** (TRANSITIVITY_DEPTH_MAX, REPUTATION_ISOLATION, INVOICE_STATUS_MONOTONIC, DISCOVERY_OPT_IN_REQUIRED)

This is the **physics** of the epistemic substrate.  
Phases 12–14 will implement the **structure** and **interfaces**.

---

**Status:** SPECIFICATION LOCKED  
**Authority:** Phase Architects  
**Next Phase:** Namespace Schema (Task 59)
