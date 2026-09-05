# Phase 21: Hybrid Trust Topology Engine — Complete Specification

**Date:** 2026-05-11  
**Phase:** Phase 21: Hybrid Trust Topology (SMAOS Foundation Layer 3)  
**Status:** 🔴 Pre-Implementation (Spec + Failing Tests Ready)  
**Foundation:** Phase 20 (Intelligence Graph + SSE Events + Cockpit) + Phase 19 (Signal Integration) + Phase 11 (Transitive Trust)

---

## 1. Executive Summary

Phase 21 implements **Hybrid Trust Topology**—a directed, interaction-gated, decay-aware peer-to-peer trust scoring system that leverages the Phase 20 SMAOS foundation to measure trust relationships between sovereigns. Trust is **directional** (A→B ≠ B→A), **earned** (5 AP2 settlements or 7 days active), and **advisory** (never used in authorization gates).

**The Hybrid Score Combines:**
- **Explicit Component** — direct endorsements by peers (confidence ∈ [0.0, 1.0])
- **Implicit Component** — Phase 19 behavioral signals (slash/anomaly/settlement penalties/bonuses)
- **Decay Penalty** — linear erosion over 30 days of inactivity
- **Transitive Boost** — Phase 11 delegation grants (max 3 hops, capped +15)

**Formula:** `trust_score(A→B) = clamp(explicit + implicit + decay + transitive, 0, 100)`

**Example:** Sovereign A (defense contractor) explicitly trusts Sovereign B (analytics agent) at 0.8 confidence → explicit_base = 80. B has incurred 2 recent slashes (Phase 19 penalty −20). 15 days since A and B last settled an invoice (decay −50). No transitive delegation path. **Final score = 80 − 20 − 50 + 0 = 10** ← B is trustworthy but somewhat degraded.

---

## 2. Architectural Constraints

### 2.1 Security-Critical Design Decisions

| Decision | Rationale | Non-Negotiable Invariant |
|----------|-----------|--------------------------|
| **Directional Edges** | In a federated sovereign ecosystem, A's trust in B ≠ B's trust in A. A defense contractor may trust a public analytics agent; the agent does not automatically gain reciprocal authority. Mirrors AP2 spending mandates (one-way cryptographic boundaries). | `TRUST_EDGE_DIRECTIONALITY`: One row per ordered pair (A→B) only. |
| **Interaction Gating** | Prevent Sybil attacks: no explicit trust edges until 5 settled AP2 invoices OR 7 days active/probation. | `SYBIL_RESISTANCE`: `check_trust_eligibility()` enforces threshold before `record_explicit_trust()` writes. |
| **3-Hop Transitive Cap** | Unbounded transitive traversal causes latency spikes (Context Cartography doctrine: govern active context boundaries). Transitive queries must enforce `WHERE transitivity_depth <= 3`. | `DEPTH_BUDGET`: Hard `WHERE` limit in transitive boost query. No graph algorithms. |
| **Trust Never Bypasses Quarantine** | Phase 15 quarantine is fail-closed; Phase 21 is informational. Trust scores must never short-circuit `pipeline/validate.rs` checks. | `QUARANTINE_SUPREMACY`: `trust_network_edges` has NO FK to `sessions` or authorization tables. Never read inside `pipeline/`. |

### 2.2 Blast Radius Pre-Check (GitNexus)

**Files Analyzed:** `consensus_repo.rs`, `peer_scoring_repo.rs`, `transitive_resolver.rs`, `federation_repo.rs`

| File | Risk | Mitigation | Status |
|------|------|-----------|--------|
| `consensus_repo.rs` (Phase 15 Quarantine) | Trust score could bypass quarantine gate | Trust scores stored in separate `trust_network_edges` table; never read by `is_tenant_sovereign_quarantined()` or its callers | ✅ Isolated |
| `peer_scoring_repo.rs` (Phase 20 Recovery) | Trust modifier could corrupt recovery graduation | `compute_and_upsert_score()` recovery branch explicitly excludes `trust_modifier` — applies only to `"active"` status | ✅ Guarded |
| `transitive_resolver.rs` (Phase 11 Tiers) | Trust score (i16 [0–100]) could inflate tier ceilings (u32) | Phase 11 uses distinct numeric space. Transitive boost capped at +15 points; never modifies `grant_ceiling_tier` | ✅ Type-Safe |
| `federation_repo.rs` (Phase 10 Settlement) | Trust score gates transactions | Trust is advisory — transactions proceed; trust affects routing preference only, never access control | ✅ Architectural |

**Guarantee:** Phase 21 adds zero new authorization gates and zero new quarantine bypass paths.

---

## 3. Data Model

### 3.1 Migration 034: `trust_network_edges` Schema

**File:** `crates/siss-graph-db/src/migrations/034_add_phase21_trust_topology.sql`

```sql
-- Phase 21: Hybrid Trust Topology Engine
-- Constitutional Invariants:
--   DIRECTIONALITY: (source_id, target_id) is ordered; A→B ≠ B→A
--   ELIGIBILITY_GATE: explicit_confidence writes require 5 settlements OR 7 days active
--   DEPTH_LIMIT: 3-hop max (enforced at query layer, not schema)
--   QUARANTINE_SUPREMACY: This table has no FK to sessions/authorization/tiers

CREATE TABLE trust_network_edges (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Directed edge: source is the truster (A), target is the trusted (B)
    source_sovereign_id     UUID NOT NULL REFERENCES sovereigns(id) ON DELETE CASCADE,
    target_sovereign_id     UUID NOT NULL REFERENCES sovereigns(id) ON DELETE CASCADE,

    -- Explicit endorsement strength [0.00 – 1.00] by source about target
    -- NULL until source writes an explicit TRUSTS edge (interaction gating)
    explicit_confidence     NUMERIC(3,2)    CHECK (explicit_confidence BETWEEN 0.00 AND 1.00),

    -- Computed hybrid trust score [0 – 100]
    hybrid_trust_score      SMALLINT        NOT NULL DEFAULT 0
                                            CHECK (hybrid_trust_score BETWEEN 0 AND 100),

    -- Component breakdown (for cockpit detail view + audit trail)
    explicit_component      SMALLINT        NOT NULL DEFAULT 0,
    implicit_component      SMALLINT        NOT NULL DEFAULT 0,
    decay_component         SMALLINT        NOT NULL DEFAULT 0,
    transitive_component    SMALLINT                 DEFAULT NULL,

    -- Decay anchor: last interaction (settlement or explicit endorsement)
    last_interaction_at     TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    -- Interaction gate tracking (for eligibility dashboard)
    settled_invoice_count   INT             NOT NULL DEFAULT 0
                                            CHECK (settled_invoice_count >= 0),
    is_explicit_eligible    BOOLEAN         NOT NULL DEFAULT FALSE,
    eligibility_met_at      TIMESTAMPTZ,

    -- Endorsement history (for CockpitEnhance: how many times has source endorsed target)
    voucher_count           INT             NOT NULL DEFAULT 0
                                            CHECK (voucher_count >= 0),

    -- Timestamps
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    last_updated_at         TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    -- One directed edge per ordered pair (A, B)
    CONSTRAINT uq_trust_edge_pair
        UNIQUE (source_sovereign_id, target_sovereign_id),

    -- No self-loops: A cannot trust itself
    CONSTRAINT check_no_self_trust
        CHECK (source_sovereign_id != target_sovereign_id)
);

-- Index 1: Truster's outbound edges (A's trust graph)
CREATE INDEX idx_trust_edges_source
    ON trust_network_edges(source_sovereign_id, hybrid_trust_score DESC);

-- Index 2: Who trusts B (inbound edges for reputation aggregation)
CREATE INDEX idx_trust_edges_target
    ON trust_network_edges(target_sovereign_id, hybrid_trust_score DESC);

-- Index 3: Decay sweep (find stale edges)
CREATE INDEX idx_trust_edges_decay_sweep
    ON trust_network_edges(last_interaction_at ASC);

-- Index 4: Eligibility gate (find eligible-but-not-explicit edges)
CREATE INDEX idx_trust_edges_eligible
    ON trust_network_edges(source_sovereign_id)
    WHERE is_explicit_eligible = TRUE AND explicit_confidence IS NULL;

-- Partition hint (optional; add if table grows >1M rows):
-- PARTITION BY RANGE (created_at) (
--   PARTITION part_2026_01 VALUES LESS THAN ('2026-02-01'),
--   PARTITION part_2026_02 VALUES LESS THAN ('2026-03-01'),
--   ...
-- );
```

**Migration Registration:** Add to `crates/siss-graph-db/src/migrations/mod.rs` MIGRATIONS slice:
```rust
(
    "034_add_phase21_trust_topology",
    include_str!("034_add_phase21_trust_topology.sql"),
),
```

**Transaction Safety:** No `ALTER TYPE ... ADD VALUE` (no enum extensions). Runs safely inside the standard transaction wrapper in `run_all()`.

---

## 4. Pure Functions — Core Scoring Logic

**File:** `crates/siss-graph-db/src/repo/trust_topology_repo.rs`

### 4.1 `explicit_trust_score(confidence: f32) -> i16`

**Purpose:** Convert a peer's explicit confidence endorsement [0.0, 1.0] to a score component [0, 100].

**Formula:** `(confidence × 100).round() as i16`

**Examples:**
- 1.0 → 100
- 0.8 → 80
- 0.5 → 50
- 0.0 → 0

**Invariants:**
- Deterministic (same input → same output)
- Range: [0, 100]

### 4.2 `trust_decay(last_interaction_at: DateTime<Utc>) -> i16`

**Purpose:** Compute linear decay penalty based on days since last interaction (settlement or explicit endorsement).

**Formula:**
```
days_since = max(0, (now - last_interaction_at).num_days())
penalty = -(days_since / 30) × 100, floor at −100
result = max(penalty, -100)
```

**Timeline:**
- Day 0 (now) → 0
- Day 15 → −50
- Day 30 → −100
- Day 60+ → −100 (clamped)

**Rationale:** Trust erodes linearly. After 30 days without interaction, the decay penalty alone brings any edge to 0 score (unless other components offset it). Interaction resets the timer.

**Invariants:**
- Monotonically non-increasing (more time → worse penalty)
- Never goes below −100
- Resets on interaction

### 4.3 `implicit_signal_contribution(slash_count: i64, anomaly_count: i64, settled_count: i64) -> i16`

**Purpose:** Compute the implicit behavioral signal adjustment (Phase 19 penalties + bonuses).

**Formula (reusing Phase 19):**
```
slash_penalty = min(30, slash_count × 10)
anomaly_penalty = min(20, anomaly_count × 8)
settlement_bonus = min(20, settled_count × 5)

result = -(slash_penalty + anomaly_penalty) + settlement_bonus
```

**Windows:**
- Slashes, anomalies: last 30 days only
- Settlements: all-time

**Examples:**
- 0 signals → 0
- 2 slashes → −20
- 2 slashes + 1 anomaly → −20 − 8 = −28
- 4 settlements → +20 (capped)
- 3 slashes + 2 anomalies + 2 settlements → −30 − 16 + 10 = −36

**Rationale:** Reuse existing Phase 19 infrastructure. Sovereign that commits slashes loses trust; sovereign that settles invoices gains it. Same penalty/bonus formulas ensure signal consistency across phases.

**Invariants:**
- Clamped penalties (slash ≤ 30, anomaly ≤ 20, settlement ≤ 20)
- Range: [−50, +20]

### 4.4 `compute_hybrid_trust_score(explicit_base: i16, implicit_adj: i16, decay_penalty: i16, transitive_boost: Option<i16>) -> i16`

**Purpose:** Combine all four components into the final trust score [0, 100].

**Formula:**
```
transitive = transitive_boost.unwrap_or(0)
raw_score = explicit_base + implicit_adj + decay_penalty + transitive
result = raw_score.clamp(0, 100)
```

**Examples:**
- (80, 0, 0, None) → 80
- (80, −20, 0, None) → 60
- (80, −20, −50, None) → clamp(10, 0, 100) → 10
- (80, −20, −100, None) → clamp(−40, 0, 100) → 0 (decay dominates)
- (0, 0, 0, Some(15)) → 15 (transitive without explicit)
- (90, +20, 0, None) → clamp(110, 0, 100) → 100 (capped)

**Rationale:** Simple linear combination. Trust is the sum of all factors. Clamping [0, 100] ensures it fits the peer_scoring interface (scores are always [0, 100]).

**Invariants:**
- Output always [0, 100]
- Pure function
- Additive composition

---

## 5. Async Database Functions

**File:** `crates/siss-graph-db/src/repo/trust_topology_repo.rs`

### 5.1 `check_trust_eligibility(pool: &PgPool, source_id: Uuid, target_id: Uuid) -> Result<TrustEligibilityStatus, sqlx::Error>`

**Purpose:** Determine whether source_sovereign is eligible to write an explicit TRUSTS edge to target_sovereign.

**Gate Conditions:** Eligible if EITHER:
- Count of `settlement_invoices WHERE debtor_sovereign_id = source_id AND status = 'settled'` ≥ 5, OR
- Sovereign `established_at ≤ NOW() - INTERVAL '7 days' AND status IN ('active', 'probation')`

**Disqualifications:**
- source is `'quarantined'` → `SourceQuarantined`
- source is `'recovering'` → `SourceQuarantined` (reuse same failure mode)
- target does not exist or is `'quarantined'` → `TargetUnavailable`

**Return Type:**
```rust
pub enum TrustEligibilityStatus {
    Eligible { settled_count: i64, days_active: i64 },
    NotEligible { settled_count: i64, days_active: i64 },
    SourceQuarantined,
    TargetUnavailable,
}
```

**Queries:**
```sql
-- Query 1: Count settled invoices
SELECT COUNT(*) FROM settlement_invoices
  WHERE debtor_sovereign_id = $source_id AND status = 'settled'

-- Query 2: Check source sovereignty
SELECT established_at, status FROM sovereigns WHERE id = $source_id

-- Query 3: Check target sovereignty
SELECT status FROM sovereigns WHERE id = $target_id
```

**Logic:**
```
1. Fetch source (Query 2); return SourceQuarantined if status ∈ {quarantined, recovering}
2. Fetch target (Query 3); return TargetUnavailable if not found OR status = quarantined
3. Count settlements (Query 1)
4. Calculate days_active = (now - source.established_at).num_days()
5. If settled_count ≥ 5 OR (days_active ≥ 7 AND status ∈ {active, probation})
     → return Eligible { settled_count, days_active }
   Else
     → return NotEligible { settled_count, days_active }
```

### 5.2 `record_explicit_trust(pool: &PgPool, source_id: Uuid, target_id: Uuid, confidence: f32) -> Result<(), sqlx::Error>`

**Purpose:** Write or update an explicit TRUSTS edge if source_id is eligible.

**Steps:**
1. Call `check_trust_eligibility()` → fail if not Eligible
2. UPSERT `trust_network_edges` with:
   - explicit_confidence ← confidence
   - incremented voucher_count
   - is_explicit_eligible ← true
   - eligibility_met_at ← now (on first write only)
   - last_updated_at ← now

**SQL Pattern:**
```sql
INSERT INTO trust_network_edges
    (source_sovereign_id, target_sovereign_id, explicit_confidence, voucher_count,
     is_explicit_eligible, eligibility_met_at, last_updated_at)
VALUES ($1, $2, $3, 1, TRUE, NOW(), NOW())
ON CONFLICT (source_sovereign_id, target_sovereign_id) DO UPDATE
    SET explicit_confidence = EXCLUDED.explicit_confidence,
        voucher_count = trust_network_edges.voucher_count + 1,
        is_explicit_eligible = TRUE,
        eligibility_met_at = COALESCE(trust_network_edges.eligibility_met_at, NOW()),
        last_updated_at = NOW()
RETURNING id
```

**Side Effects:**
- Creates or updates edge row in `trust_network_edges`
- Does NOT compute hybrid score (caller must call `compute_and_upsert_trust_score()`)
- Does NOT emit event (caller must emit)

### 5.3 `fetch_implicit_signals(pool: &PgPool, target_id: Uuid) -> Result<(i64, i64, i64), sqlx::Error>` [Private Helper]

**Purpose:** Fetch Phase 19 signal counts for computing implicit_component.

**Queries:**
```sql
-- Slashes in last 30 days
SELECT COUNT(*) FROM slashing_events
  WHERE sovereign_id = $target_id AND slashed_at >= NOW() - INTERVAL '30 days'

-- Anomalies in last 30 days (high/critical only)
SELECT COUNT(*) FROM behavioral_anomalies
  WHERE sovereign_id = $target_id AND severity IN ('high', 'critical')
    AND detected_at >= NOW() - INTERVAL '30 days'

-- Settlements all-time
SELECT COUNT(*) FROM settlement_invoices
  WHERE debtor_sovereign_id = $target_id AND status = 'settled'
```

**Returns:** `(slash_count, anomaly_count, settled_count)`

### 5.4 `fetch_transitive_boost(pool: &PgPool, source_id: Uuid, target_id: Uuid) -> Result<Option<i16>, sqlx::Error>` [Private Helper]

**Purpose:** Look up Phase 11 transitive delegation grants to compute transitive_component.

**Query (3-hop hard limit):**
```sql
SELECT ceiling_tier, transitivity_depth
FROM cross_sovereign_delegation_grants
WHERE grantor_sovereign_id = $source_id
  AND grantee_sovereign_id = $target_id
  AND transitivity_depth <= 3
  AND status = 'active'
  AND (expires_at IS NULL OR expires_at > NOW())
  AND revoked_at IS NULL
ORDER BY ceiling_tier DESC
LIMIT 1
```

**Logic:**
- If found: return `Some((ceiling_tier as i16).min(15))`
  - Rationale: Cap transitive boost at +15 to prevent delegation grants from inflating trust scores unboundedly
- If not found: return `None`

**Invariant:** `WHERE transitivity_depth <= 3` is a **hard limit** — enforces max 3 hops.

### 5.5 `compute_and_upsert_trust_score(pool: &PgPool, source_id: Uuid, target_id: Uuid) -> Result<i16, sqlx::Error>`

**Purpose:** Orchestrate the complete trust score computation: fetch all signals, call pure functions, upsert edge, write intelligence graph node, emit event.

**Steps:**
```
1. Fetch edge from trust_network_edges (or use defaults)
2. explicit_confidence ← edge.explicit_confidence.unwrap_or(0.0)
3. Call fetch_implicit_signals() → (slash_count, anomaly_count, settled_count)
4. Call fetch_transitive_boost() → Option<i16>
5. explicit_base = explicit_trust_score(explicit_confidence)
6. implicit_adj = implicit_signal_contribution(slash_count, anomaly_count, settled_count)
7. decay_pen = trust_decay(edge.last_interaction_at)
8. hybrid_score = compute_hybrid_trust_score(explicit_base, implicit_adj, decay_pen, transitive_boost)
9. UPSERT trust_network_edges:
     hybrid_trust_score ← hybrid_score
     explicit_component ← explicit_base
     implicit_component ← implicit_adj
     decay_component ← decay_pen
     transitive_component ← transitive_boost
     last_updated_at ← NOW()
10. Call intelligence_graph_repo::write_trust_relationship(
      source_id, target_id, hybrid_score,
      evidence = {"explicit":explicit_base, "implicit":implicit_adj, ...},
      confidence = hybrid_score / 100.0
    )
11. Emit TrustTopologyEvent::TrustScoreUpdated { ... }
12. Return hybrid_score
```

**SQL Upsert:**
```sql
INSERT INTO trust_network_edges
    (source_sovereign_id, target_sovereign_id,
     hybrid_trust_score, explicit_component, implicit_component,
     decay_component, transitive_component, last_updated_at)
VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
ON CONFLICT (source_sovereign_id, target_sovereign_id) DO UPDATE
    SET hybrid_trust_score   = EXCLUDED.hybrid_trust_score,
        explicit_component   = EXCLUDED.explicit_component,
        implicit_component   = EXCLUDED.implicit_component,
        decay_component      = EXCLUDED.decay_component,
        transitive_component = EXCLUDED.transitive_component,
        last_updated_at      = NOW()
```

### 5.6 `sweep_trust_decay(pool: &PgPool) -> Result<TrustDecaySweepResult, sqlx::Error>`

**Purpose:** Daily sweep job that recalculates all trust edges, applying current decay.

**Steps:**
```
1. SELECT * FROM trust_network_edges
     JOIN sovereigns s1 ON s1.id = source_sovereign_id
     JOIN sovereigns s2 ON s2.id = target_sovereign_id
     WHERE s1.status NOT IN ('quarantined', 'recovering')
       AND s2.status NOT IN ('quarantined', 'recovering')
     ORDER BY last_interaction_at ASC (for batch processing)
     LIMIT 1000 (batch size)
2. For each edge in batch:
     a. Call compute_and_upsert_trust_score(pool, source_id, target_id)
     b. Track: edges_recomputed++, edges_zeroed++ (if score went to 0)
3. Loop until no edges remain
4. Return TrustDecaySweepResult { edges_recomputed, edges_zeroed, errors }
```

**Return Type:**
```rust
pub struct TrustDecaySweepResult {
    pub edges_recomputed: u64,
    pub edges_zeroed: u64,
    pub errors: u64,
}
```

**Rationale:** Quarantined and recovering sovereigns are excluded from the sweep to preserve the integrity of the Phase 15 quarantine firewall and Phase 20 recovery state machine.

---

## 6. Test-Driven Development: 12 Failing Tests

**File:** `crates/siss-graph-db/src/repo/trust_topology_repo.rs` (tests section)

### 6.1 Test Group 1: `explicit_trust_score()` Pure Function

```rust
#[test]
fn test_explicit_trust_score_full_confidence() {
    // confidence 1.0 → exactly 100
    assert_eq!(explicit_trust_score(1.0), 100);
}

#[test]
fn test_explicit_trust_score_partial_confidence() {
    // confidence 0.8 → exactly 80
    assert_eq!(explicit_trust_score(0.8), 80);
}
```

### 6.2 Test Group 2: `trust_decay()` Pure Function

```rust
#[test]
fn test_trust_decay_none_at_day_0() {
    // Interaction just now → 0 decay
    let now = Utc::now();
    assert_eq!(trust_decay(now), 0);
}

#[test]
fn test_trust_decay_full_at_day_30() {
    // 30 days ago → -100
    let thirty_days_ago = Utc::now() - Duration::days(30);
    assert_eq!(trust_decay(thirty_days_ago), -100);
}

#[test]
fn test_trust_decay_partial_at_day_15() {
    // 15 days ago → -50
    let fifteen_days_ago = Utc::now() - Duration::days(15);
    assert_eq!(trust_decay(fifteen_days_ago), -50);
}
```

### 6.3 Test Group 3: `compute_hybrid_trust_score()` Pure Function

```rust
#[test]
fn test_hybrid_score_no_decay_clean() {
    // explicit 80, no signals (0 implicit), no decay → 80
    let score = compute_hybrid_trust_score(80, 0, 0, None);
    assert_eq!(score, 80);
}

#[test]
fn test_hybrid_score_decay_takes_full_effect() {
    // explicit 80, no signals, -100 decay → clamp to 0
    let score = compute_hybrid_trust_score(80, 0, -100, None);
    assert_eq!(score, 0);
}

#[test]
fn test_implicit_signals_drag_explicit_down() {
    // explicit 80, 3 slashes → implicit = -30, no decay → 50
    let implicit = implicit_signal_contribution(3, 0, 0);
    assert_eq!(implicit, -30);
    let score = compute_hybrid_trust_score(80, implicit, 0, None);
    assert_eq!(score, 50);
}

#[test]
fn test_implicit_override_severe_penalty() {
    // explicit 90, 3 slashes + 2 anomalies + 1 settlement
    // slash = min(30, 30) = 30
    // anomaly = min(20, 16) = 16
    // settlement = min(20, 5) = 5
    // implicit = -(30+16) + 5 = -41
    // score = 90 - 41 = 49
    let implicit = implicit_signal_contribution(3, 2, 1);
    assert_eq!(implicit, -41);
    let score = compute_hybrid_trust_score(90, implicit, 0, None);
    assert_eq!(score, 49);
}

#[test]
fn test_transitive_boost_without_direct() {
    // explicit 0, 0 signals, 0 decay, +15 transitive → 15
    let score = compute_hybrid_trust_score(0, 0, 0, Some(15));
    assert_eq!(score, 15);
}

#[test]
fn test_hybrid_score_clamped_to_100() {
    // explicit 90, settlement bonus = +20 → implicit = +20, no decay → 110 → clamped 100
    let implicit = implicit_signal_contribution(0, 0, 4); // 4*5=20
    assert_eq!(implicit, 20);
    let score = compute_hybrid_trust_score(90, implicit, 0, None);
    assert_eq!(score, 100);
}

#[test]
fn test_hybrid_score_clamped_to_0() {
    // explicit 30, -50 signals, -60 decay → 30 - 50 - 60 = -80 → clamped 0
    let score = compute_hybrid_trust_score(30, -50, -60, None);
    assert_eq!(score, 0);
}
```

### 6.4 Test Correctness Verification

**Test 9 (`test_implicit_override_severe_penalty`):**
- Inputs: 3 slashes, 2 anomalies, 1 settlement
- Calculation:
  - slash_penalty = min(30, 3×10=30) = 30
  - anomaly_penalty = min(20, 2×8=16) = 16
  - settlement_bonus = min(20, 1×5=5) = 5
  - implicit = -(30+16) + 5 = **−41** ✓
- Score: 90 + (−41) + 0 + 0 = **49** ✓

---

## 7. Intelligence Graph Integration

### 7.1 New Function: `write_trust_relationship()`

**File:** `crates/siss-graph-db/src/repo/intelligence_graph_repo.rs`

**Function Signature:**
```rust
pub async fn write_trust_relationship(
    pool: &PgPool,
    source_id: Uuid,
    target_id: Uuid,
    trust_score: i16,
    evidence: serde_json::Value,  // {"explicit":80,"implicit":-10,"decay":0,"transitive":null}
    confidence: f64,              // trust_score / 100.0
) -> Result<Uuid, sqlx::Error>
```

**Purpose:** Write a `TrustNetworkNode` to the intelligence graph with full component breakdown and audit trail.

**Steps:**
```
1. Generate entity_id = Uuid::new_v4()
2. Build properties JSON:
   {
     "source_sovereign_id": source_id,
     "target_sovereign_id": target_id,
     "trust_score": trust_score,
     "evidence": evidence,
     "timestamp": now (RFC 3339)
   }
3. INSERT into graph_entities: (entity_id, label="TrustNetworkNode", properties)
4. Fetch or create SovereignNode for source_id
5. Fetch or create SovereignNode for target_id
6. INSERT TRUSTS edge: source_sovereign_node → entity_id (confidence)
7. INSERT EXPLAINS edge: entity_id → target_sovereign_node (confidence)
8. Return entity_id
```

**Graph Structure:**
```
SovereignNode(source_id)
  -[TRUSTS confidence=0.9]→ TrustNetworkNode
                              ↓ [EXPLAINS confidence=0.9]
                           SovereignNode(target_id)
```

**Evidence Payload Example:**
```json
{
  "explicit": 80,
  "implicit": -20,
  "decay": -50,
  "transitive": null,
  "windows": {
    "slash_30d": 2,
    "anomaly_30d": 1,
    "settlement_all_time": 5
  }
}
```

---

## 8. Event System Extension

### 8.1 New Event Type: `TrustTopologyEvent`

**File:** `crates/siss-agent-shell/src/events/trust_events.rs` (new file)

**Rationale:** Create a separate enum from `AgentEvent` to avoid breaking the existing `test_all_13_event_types` assertion.

**Enum Definition:**
```rust
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Trust topology lifecycle events emitted by Phase 21.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TrustTopologyEvent {
    /// A new trust edge was created between two sovereigns.
    TrustEntered {
        source_id: Uuid,
        target_id: Uuid,
        initial_score: i16,
        timestamp: DateTime<Utc>,
    },

    /// A trust score was recomputed with full component breakdown.
    TrustScoreUpdated {
        source_id: Uuid,
        target_id: Uuid,
        new_score: i16,
        explicit_component: i16,
        implicit_component: i16,
        decay_component: i16,
        transitive_component: Option<i16>,
        timestamp: DateTime<Utc>,
    },

    /// A trust score reached 0 (or near-zero) after decay sweep.
    TrustDecayed {
        source_id: Uuid,
        target_id: Uuid,
        final_score: i16,
        timestamp: DateTime<Utc>,
    },
}

impl TrustTopologyEvent {
    pub fn event_type(&self) -> &'static str {
        match self {
            Self::TrustEntered { .. }       => "trust_entered",
            Self::TrustScoreUpdated { .. }  => "trust_score_updated",
            Self::TrustDecayed { .. }       => "trust_decayed",
        }
    }
}
```

**Registration:** In `crates/siss-agent-shell/src/events/mod.rs`:
```rust
pub mod trust_events;
pub use trust_events::TrustTopologyEvent;
```

---

## 9. Cockpit Extension

### 9.1 Trust Network Panel

**File:** `crates/siss-agent-card/static/cockpit.html`

**Location:** Add after the 3 existing panels (Recovery Status, Recent Transitions, Signal Activity) inside `<div class="panels">`.

**Panel Structure:**
```html
<div class="panel" id="panel-trust-network">
  <h2>Trust Network</h2>
  <table id="trust-table">
    <thead>
      <tr>
        <th>Source</th>
        <th>Target</th>
        <th>Score</th>
        <th>Explicit</th>
        <th>Implicit</th>
        <th>Decay</th>
        <th>Transitive</th>
        <th>Updated</th>
      </tr>
    </thead>
    <tbody id="trust-table-body"></tbody>
  </table>
</div>
```

**Styling:**
- `trust-high` (score ≥ 70): green background
- `trust-mid` (30–69): yellow background
- `trust-low` (< 30): red background

**JavaScript Function:**
```javascript
function updateTrustNetwork(data) {
    const key = `${data.source_id}→${data.target_id}`;
    let row = document.querySelector(`tr[data-trust-key="${key}"]`);
    
    if (!row) {
        row = document.createElement('tr');
        row.setAttribute('data-trust-key', key);
        document.getElementById('trust-table-body').appendChild(row);
    }
    
    const scoreClass = data.new_score >= 70 ? 'trust-high'
                     : data.new_score >= 30 ? 'trust-mid'
                     : 'trust-low';
    
    row.className = scoreClass;
    row.innerHTML = `
        <td>${data.source_id.substring(0, 8)}...</td>
        <td>${data.target_id.substring(0, 8)}...</td>
        <td>${data.new_score}</td>
        <td>${data.explicit_component}</td>
        <td>${data.implicit_component}</td>
        <td>${data.decay_component}</td>
        <td>${data.transitive_component ?? '—'}</td>
        <td>${new Date(data.timestamp).toLocaleTimeString()}</td>
    `;
}

// In handleEvent():
case 'TrustEntered':
case 'TrustScoreUpdated':
case 'TrustDecayed':
    updateTrustNetwork(event);
    break;
```

---

## 10. Peer Scoring Integration

### 10.1 Modification to `peer_scoring_repo.rs`

**File:** `crates/siss-graph-db/src/repo/peer_scoring_repo.rs`

**Change 1: Update Function Signature**
```rust
pub async fn compute_and_upsert_score(
    pool: &PgPool,
    sovereign_id: Uuid,
    trust_modifier: Option<i16>,  // NEW PARAMETER
) -> Result<i16, sqlx::Error>
```

**Change 2: Add Backward-Compatible Wrapper**
```rust
pub async fn compute_and_upsert_score_default(
    pool: &PgPool,
    sovereign_id: Uuid,
) -> Result<i16, sqlx::Error> {
    compute_and_upsert_score(pool, sovereign_id, None).await
}
```

**Change 3: Guard the Recovering Branch**
```rust
"recovering" => {
    // Phase 21: trust_modifier intentionally NOT applied to recovering sovereigns.
    // Recovery scoring is governed exclusively by reputation_recovery_repo::compute_recovery_score.
    // Trust modifier only applies to "active" status to preserve recovery state machine integrity.
    compute_recovery_score(weeks, slash_count, anomaly_count, settled_count)
}

"active" => {
    let base_score = compute_enriched_score(100, slash_count, anomaly_count, settled_count);
    // Apply trust modifier only for active sovereigns
    match trust_modifier {
        Some(modifier) => {
            let adjusted = (base_score as i32 + modifier as i32).clamp(0, 100) as i16;
            adjusted
        }
        None => base_score,
    }
}
```

**Change 4: Update Call Site in `run_scoring_pass()`**
```rust
pub async fn run_scoring_pass(pool: &PgPool) -> Result<u64, sqlx::Error> {
    let sovereigns: Vec<Uuid> = sqlx::query_scalar("SELECT id FROM sovereigns")
        .fetch_all(pool)
        .await?;

    let mut count = u64 = 0;
    for sovereign_id in sovereigns {
        // Use default (no trust modifier) for the standard scoring sweep
        if compute_and_upsert_score_default(pool, sovereign_id).await.is_ok() {
            count += 1;
        }
    }

    Ok(count)
}
```

---

## 11. Build Sequence (9 Phases)

| Phase | Task | Green Criteria |
|-------|------|---|
| **A** | Create `trust_topology_repo.rs` with function stubs + 12 failing tests | `cargo test trust_topology` → 12 FAIL |
| **B** | Implement 4 pure functions | `cargo test trust_topology` → 12 PASS |
| **C** | Write migration 034 + register in `mod.rs` | Existing migration tests pass |
| **D** | Implement 4 async DB functions | `cargo test -p siss-graph-db` → no regressions |
| **E** | Add `write_trust_relationship()` to intelligence graph | Existing graph tests pass |
| **F** | Create `trust_events.rs` + register | `test_all_13_event_types` still passes (13 not 16) |
| **G** | Update `peer_scoring_repo.rs` with trust_modifier guard | All peer scoring tests pass |
| **H** | Add Trust Network panel to `cockpit.html` | HTML valid, panel renders |
| **I** | Final verification | `cargo test`, `cargo clippy`, `cargo fmt --check` all pass |

---

## 12. Safety Invariants (Constitutional)

1. **QUARANTINE_SUPREMACY**
   - `trust_network_edges` has no FK to `sessions`, `trust_policy_nodes`, or authorization tables.
   - Trust scores never read by `pipeline/validate.rs`, `pipeline/rebac.rs`, `pipeline/ap2.rs`, `pipeline/governance.rs`.
   - **Verification**: No imports from `trust_topology_repo` inside `siss-gatekeeper/src/pipeline/*`.

2. **RECOVERY_ISOLATION**
   - `compute_and_upsert_score()` recovery branch explicitly guards `trust_modifier` as `None`.
   - Trust modifier applies only to `"active"` status.
   - **Verification**: Code review of `"recovering"` match arm in `peer_scoring_repo.rs`.

3. **TIER_CEILING_PRESERVATION**
   - `transitive_component` capped at +15 points; never modifies `grant_ceiling_tier` in Phase 11 tables.
   - Phase 11 uses `u32` tier space; Phase 21 uses `i16` score space — no type collision.
   - **Verification**: No UPDATE on `cross_sovereign_delegation_grants` in Phase 21 code.

4. **SYBIL_RESISTANCE**
   - `check_trust_eligibility()` enforces 5 settlements OR 7 days before any explicit edge write.
   - **Verification**: Integration test: attempt to write explicit trust before threshold, confirm error.

5. **DEPTH_BUDGET**
   - Transitive boost query includes hard `WHERE transitivity_depth <= 3` limit.
   - **Verification**: No unbounded graph traversal logic in Phase 21.

---

## 13. Future Extensions (Phase 22+)

1. **Peer Cohort Analytics** — batch reporting on trust network density, average trust by status/phase
2. **Graduated Explicit Endorsements** — allow partial confidence updates (not all-or-nothing)
3. **Trust Appeals** — sovereigns can appeal low trust scores with evidence
4. **Transitive Boost Decay** — longer paths → lower boost (currently flat +15 cap)
5. **Reputation Insurance** — bonds that extend trust window in exchange for capital lock

---

## 14. Success Criteria (QA Checklist)

- [ ] 12 unit tests for pure functions all pass
- [ ] 4 async DB functions implement and pass integration tests
- [ ] Migration 034 applies cleanly on clean database
- [ ] Intelligence graph writes create `TrustNetworkNode` + edges correctly
- [ ] `TrustTopologyEvent` emits are captured by SSE stream
- [ ] Cockpit Trust Network panel displays live trust updates with color coding
- [ ] `compute_and_upsert_score()` applies trust_modifier only for active sovereigns
- [ ] Quarantine gate prevents explicit trust writes from quarantined sovereigns
- [ ] Decay sweep skips quarantined/recovering sovereigns
- [ ] No regression in existing Phase 15/19/20 tests
- [ ] `cargo clippy` → 0 warnings specific to Phase 21 code
- [ ] `cargo fmt --check` passes
- [ ] Code review sign-off: 5 invariants verified

---

## 15. References

- **Phase 20 Handoff:** `/Users/andriileukhin/Documents/SovereignNexus/HANDOFF.md`
- **Phase 19 Scoring:** `peer_scoring_repo.rs` (slash/anomaly/settlement formulas)
- **Phase 15 Quarantine:** `consensus_repo.rs` + `pipeline/validate.rs`
- **Phase 11 Transitive:** `transitive_resolver.rs` + `cross_sovereign_delegation_grants` table
- **Phase 10 Settlement:** `settlement_invoices` table schema
- **Intelligence Graph:** `intelligence_graph_repo.rs` + Apache AGE schema

---

**Specification Status: ✅ READY FOR IMPLEMENTATION**

This spec is feature-complete, blast-radius analyzed, and test-cases defined. Proceed to Phase A (TDD test scaffolding) with confidence.

---

**Last Updated:** 2026-05-11  
**Spec Format Version:** 1.0 (SMAOS Foundation Phase Specs)
