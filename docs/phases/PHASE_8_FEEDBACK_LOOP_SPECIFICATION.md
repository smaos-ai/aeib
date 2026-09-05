# Phase 8: Behavioral Governance — Feedback Loop Specification

**Status:** 🔵 SPECIFICATION LOCKED (Ready for Implementation)  
**Date:** 2026-05-10  
**Scope:** Behavior event schema, scoring contract, tier coupling, budget feedback  
**Locked Decisions:** 3 (see Architecture Lock section)

---

## Executive Summary

Phase 8 closes the trust feedback loop: every attestation refresh generates a **behavior event**, which is scored deterministically, which adjusts the agent's **trust tier**, which immediately impacts the next refresh's **token cost**. This creates a self-reinforcing cycle: good behavior (high-trust operations) → lower token cost → easier to maintain tier; bad behavior (revocations, failed validations) → tier drop → higher cost → budget pressure as secondary feedback.

The system is **lineage-safe** (parent behavior doesn't affect children) and **atomic** (tier adjustment + cost recalculation happen together or fail together).

---

## Architecture: Event → Score → Tier → Cost

```
┌─────────────────────────────────────────────────────────────────┐
│                     Refresh Handler (13 steps)                   │
├─────────────────────────────────────────────────────────────────┤
│ Steps 1–5: Validate request, load attestations, compute tier    │
│                           ↓                                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Step 5.5 (NEW): Capture Behavior Event                  │   │
│  │  - event_type: refresh_success | revocation | delegation│   │
│  │  - tier_before: u32 (from Step 5)                       │   │
│  │  - cost_incurred: u64 (from Phase 7)                    │   │
│  │  - attestation_count: usize                             │   │
│  │  - timestamp: DateTime<Utc>                             │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           ↓                                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Step 6.5 (NEW): Score & Adjust Tier                     │   │
│  │  - Load behavior window (sliding, last N days)          │   │
│  │  - Score event deterministically                        │   │
│  │  - Apply exponential decay to old events                │   │
│  │  - Compute tier_after                                   │   │
│  │  - Return: ΔTier adjustment                             │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           ↓                                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Step 7 (MODIFIED): Recalculate Cost with New Tier       │   │
│  │  - Use tier_after instead of tier_before                │   │
│  │  - Recompute token_cost(tier_after, ...)                │   │
│  │  - If cost increased: check remaining budget (may deny) │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           ↓                                       │
│ Steps 8–13: Persist refresh, persist tier adjustment, persist   │
│             behavior event atomically                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Locked Architecture Decisions

### Decision 1: Scoring Runs on Refresh, Affects Next Refresh

**Invariant:** Behavior scoring is **not** real-time. It only runs during attestation refresh.

**Rationale:**
- Real-time scoring requires continuous monitoring/event streaming (out of scope for Phase 8).
- Refresh-time scoring is **deterministic** (scores same events identically across runs) and **auditable** (every score change is logged as a refresh event).
- Agents see tier changes after their next refresh attempt, which gives them a chance to correct behavior.

**Coupling:**
- Tier adjustment from refresh N affects token cost of refresh N+1.
- If behavior is bad, tier drops, cost increases, budget tightens → agent feels pressure.

### Decision 2: Behavior Window is Immutable During Scoring (Snapshot Model)

**Invariant:** Behavior window is a **snapshot** taken at the start of Step 6.5, frozen for that refresh's scoring.

**Rationale:**
- Prevents TOCTOU (time-of-check-to-time-of-use) bugs where concurrent events corrupt the window during scoring.
- Scoring logic is pure (same snapshot → same score every time).
- Window updates happen **only after** successful refresh persistence (Step 13).

**Implementation:**
```rust
// Step 6.5: Load snapshot
let behavior_window_snapshot = load_behavior_window(session_id).await;

// Pure scoring function (no side effects, no DB access)
let tier_adjustment = score_behavior_window(&behavior_window_snapshot);

// Step 13: Persist adjustment + new events atomically
update_session_tier(session_id, tier_adjustment).await;
persist_behavior_event(session_id, event).await;
```

### Decision 3: Tier Drop is the Primary Feedback; Budget Exhaustion is Secondary

**Invariant:** The tier system (Phases 4–6) is the **primary** feedback mechanism. Budget exhaustion (Phase 7) is a **safety limit**.

**Rationale:**
- Tier directly measures trust; it's the agent's reputation score.
- Budget is a resource constraint; it can change (resets, manual top-ups, quota transfers in Phase 9).
- An agent with degraded tier (low trust) will eventually run out of budget (high cost) — this is the intended feedback cascade.
- An agent with good tier can operate cheaply, even if absolute budget is limited.

**Coupling Examples:**
- Tier 1 (FULL): 100-token base cost → easy operations, encourages good behavior
- Tier 3 (MINIMAL): 100-token base cost → moderate cost, encourages recovery
- Tier 6 (degraded): 100 - 150 = -50 penalty = 50-token floor → squeezed, but not blocked (feedback loop, not lockout)
- Tier 13 (very low): 50-token floor enforced → still callable, but every call is maximal cost

---

## Behavior Event Schema

### BehaviorEvent (Database Table: `behavior_events`)

```sql
CREATE TABLE behavior_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  event_type VARCHAR(32) NOT NULL,  -- 'refresh_success', 'revocation', 'delegation_created'
  tier_before SMALLINT NOT NULL,    -- Trust tier at time of event (u32 as SMALLINT)
  tier_after SMALLINT NOT NULL,     -- Trust tier after scoring (u32 as SMALLINT)
  tier_delta SMALLINT NOT NULL,     -- tier_after - tier_before (can be negative)
  cost_incurred BIGINT NOT NULL,    -- Token cost of this refresh
  attestation_count SMALLINT NOT NULL,  -- How many attestations in request
  revocation_reason TEXT,            -- NULL unless event_type='revocation'
  scored_at TIMESTAMPTZ NOT NULL,   -- When scoring happened (= refresh timestamp)
  lineage_safe BOOLEAN NOT NULL DEFAULT TRUE,  -- FALSE if parent revocation affected this
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_behavior_events_session_id ON behavior_events(session_id);
CREATE INDEX idx_behavior_events_scored_at ON behavior_events(scored_at);
CREATE INDEX idx_behavior_events_lineage ON behavior_events(session_id, lineage_safe);
```

### Event Types

| Type | Trigger | Tier Impact | Example |
|------|---------|------------|---------|
| `refresh_success` | Successful attestation refresh | +1 to +5 (reward good behavior) | 3 refreshes in 24h with Tier 1 = +5 |
| `refresh_failure` | Failed validation (bad attestation) | -1 to -3 (penalize) | Hardware integrity check fails = -2 |
| `revocation_by_parent` | Parent session revoked (lineage cascade) | -1 to -10 (harsh penalty) | Parent revoked = -10 |
| `revocation_self` | Self-revoked or admin revocation | -5 to -10 | Explicit revocation = -10 |
| `delegation_created` | New child session delegated from this | 0 (neutral) | Just audit, no tier impact |
| `budget_pressure` | Budget dropped below 20% of initial | -1 (gentle warning) | Spending too fast = -1 (optional future) |

---

## Behavior Window Model

### Sliding Window Definition

**Window:** Last N days of events (N = 7 by default, configurable).

**Stored as:** JSON array in `sessions` table column `behavior_window` (Phase 8 migration).

```sql
ALTER TABLE sessions ADD COLUMN behavior_window JSONB DEFAULT '{"events": [], "last_refresh_at": null}';
```

**Structure:**
```json
{
  "events": [
    {
      "event_type": "refresh_success",
      "tier_delta": 2,
      "scored_at": "2026-05-09T14:30:00Z",
      "age_days": 0.5
    },
    {
      "event_type": "refresh_failure",
      "tier_delta": -1,
      "scored_at": "2026-05-08T08:15:00Z",
      "age_days": 1.5
    }
  ],
  "last_updated_at": "2026-05-10T09:00:00Z"
}
```

### Exponential Decay: Score Computation

**Formula:**
```
adjusted_delta = tier_delta × e^(-age_days / decay_half_life)

decay_half_life = 3.5 days (default)
  meaning: event from 3.5 days ago counts as 50% of its original impact
           event from 7 days ago counts as ~25% of original impact
           event from 14 days ago counts as ~6% of original impact
```

**Example Scoring:**

```
Behavior window (last 7 days):
  Day 0 (today):    refresh_success  (+2, age=0.0)   → 2.0
  Day 0.5:          refresh_success  (+3, age=0.5)   → 2.95
  Day 2:            refresh_failure  (-1, age=2.0)   → -0.71
  Day 5:            refresh_success  (+1, age=5.0)   → 0.21

Sum of adjusted deltas: 2.0 + 2.95 - 0.71 + 0.21 = 4.45

Tier adjustment: round(4.45) = +4
```

### Window Renewal Rules

**Cleanup (automatic during Step 6.5):**
```
For each event in behavior_window:
  if (now - event.scored_at) > 7 days:
    remove from window
  else:
    recompute age_days = (now - event.scored_at) / 86400
```

**Edge Cases:**
- New session: behavior_window = empty → no events to score → tier stays at tier_initial (usually 3)
- Window < 1 event: sum = 0 → tier adjustment = 0 (no change)
- All events decayed to ~0: sum ≈ 0 → tier drifts toward baseline over time (recovery mechanism)

---

## Deterministic Scoring Contract

### Input (Step 6.5)

```rust
pub fn score_behavior_window(
    window: &BehaviorWindow,
    tier_before: u32,
    timestamp_now: DateTime<Utc>,
) -> Result<i32, ScoringError> {
    // tier_before: current tier (for validation, not used in calc)
    // window: snapshot of events
    // timestamp_now: fixed point for age calculation
}
```

### Output

```
Result<i32, ScoringError>
  Ok(tier_delta):
    - Range: [-10, +10]
    - Meaning: Add to current tier to get tier_after
    - tier_after = max(1, min(13, tier_before + tier_delta))

  Err(ScoringError::WindowCorrupted):
    - Behavior window JSON unparseable
    - Missing required fields (event_type, scored_at)
    - Fail-closed: deny refresh, return 500 with "behavior_window_corrupted"

  Err(ScoringError::DecoderMismatch):
    - Event type not in allowed set
    - Fail-closed: deny refresh, return 400 with "invalid_event_type"
```

### Determinism Contract

**Invariant:** `score_behavior_window()` is a **pure function**.

**Given:**
- Same BehaviorWindow snapshot
- Same timestamp_now
- Same decay_half_life constant

**Then:**
- Output is **always identical** (byte-for-byte)
- No randomness, no external state, no time-dependent logic

**Verification (automated test):**
```rust
#[test]
fn test_scoring_determinism() {
    let window = BehaviorWindow { /* fixed */ };
    let now = DateTime::parse_from_rfc3339("2026-05-10T12:00:00Z").unwrap();
    
    let result1 = score_behavior_window(&window, 3, now);
    let result2 = score_behavior_window(&window, 3, now);
    
    assert_eq!(result1, result2);  // Must be identical
}
```

---

## Integration Points: 13-Step Refresh Handler

### Step 5.5 (NEW): Capture Behavior Event

**When:** After Step 5 (tier computed), before constraints checked (Step 6).

**What:**
```rust
let behavior_event = BehaviorEvent {
    event_type: match validation_result {
        Ok(_) => "refresh_success",
        Err(_) => "refresh_failure",
    },
    tier_before: tier,  // From Step 5
    cost_incurred: 0,   // Will be filled in Step 7
    attestation_count: request.attestations.len(),
    timestamp: Utc::now(),
};
```

**Side Effects:** None (just captures state for Step 6.5).

### Step 6.5 (NEW): Score & Adjust Tier

**When:** After Step 6 (constraints loaded), before recalculating cost (Step 7).

**What:**
```rust
// Load behavior window snapshot (immutable during this refresh)
let window_snapshot = load_behavior_window(&state.pool, session_id).await?;

// Pure scoring
let tier_delta = score_behavior_window(
    &window_snapshot,
    tier,  // tier from Step 5
    Utc::now(),
)?;

// Compute new tier
let tier_after = max(1, min(13, (tier as i32 + tier_delta) as u32));

// Store for Step 7 + Step 13
behavior_event.tier_after = tier_after;
behavior_event.tier_delta = tier_delta as i16;
```

**Side Effects:** None (snapshot is read-only).

**Error Handling:**
- If window_snapshot fails to load: return 500 "behavior_window_fetch_failed" (best-effort logging)
- If scoring fails (corrupted window): return 500 "behavior_window_corrupted" (fail-closed)

### Step 7 (MODIFIED): Recalculate Token Cost with New Tier

**Previously:** `token_cost = compute_token_cost(tier, attestations.len(), is_delegated)`

**Now:**
```rust
// Use tier_after instead of tier
let token_cost = compute_token_cost(
    tier_after,          // NEW: from Step 6.5
    request.attestations.len(),
    is_delegated,
);

// Check if cost increased significantly
let cost_delta = token_cost.total_cost as i64 - cost_from_initial_tier;
if cost_delta > 0 && cost_delta > remaining_budget as i64 {
    // Tier drop caused budget exhaustion
    return (StatusCode::PAYMENT_REQUIRED, Json(error_budget_exhausted(...))).into_response();
}

behavior_event.cost_incurred = token_cost.total_cost;
```

**Invariant:** If tier drops during refresh, the refresh might be denied due to budget (fail-safe). This is **intended feedback**: bad behavior → lower tier → higher cost → budget exhaustion.

### Step 13 (MODIFIED): Persist Tier Adjustment + Behavior Event

**Previously:** Persist refresh result + budget deduction.

**Now:**
```rust
// Atomic transaction
let mut tx = state.pool.begin().await?;

// Update session tier
sqlx::query(
    "UPDATE sessions SET trust_tier = $1 WHERE id = $2"
)
.bind(tier_after as i16)
.bind(session_id)
.execute(&mut *tx)
.await?;

// Insert behavior event (with tier_delta, cost_incurred)
sqlx::query(
    "INSERT INTO behavior_events (session_id, event_type, tier_before, tier_after, tier_delta, cost_incurred, attestation_count, scored_at)
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8)"
)
.bind(session_id)
.bind(&behavior_event.event_type)
.bind(behavior_event.tier_before as i16)
.bind(behavior_event.tier_after as i16)
.bind(behavior_event.tier_delta)
.bind(behavior_event.cost_incurred as i64)
.bind(behavior_event.attestation_count as i16)
.bind(behavior_event.timestamp)
.execute(&mut *tx)
.await?;

// Persist updated behavior window (add event, cleanup old)
update_behavior_window(&mut *tx, session_id, &behavior_event).await?;

tx.commit().await?;
```

**Atomicity:** All three operations (tier update, event insert, window update) succeed together or fail together. If any fails, entire refresh fails and agent retries.

---

## Budget/Tier Coupling Rules

### Tier-to-Cost Mapping (from Phase 7, now dynamic)

```
Tier 1 (FULL):       base=100, penalty=+100  → 200+ tokens (easiest)
Tier 2 (STANDARD):   base=100, penalty=+50   → 150+ tokens
Tier 3 (MINIMAL):    base=100, penalty=0     → 100+ tokens (reference)
Tier 4–12 (degraded): base=100, penalty=-50×(tier-3) → 100-400+ tokens
Tier 13 (floor):     base=100, penalty=-500  → max(50, -400) = 50 tokens (hardest)
```

### Feedback Cascade Example

**Initial state:** Agent A is Tier 3, budget 1M, zero behavior events.

**Scenario: 5 failed validations in 3 days**

```
Refresh 1: refresh_failure → window=[{-1}] → tier_delta=-1 → Tier 2
           cost=150 tokens (base + tier penalty) → budget: 1M-150=999,850

Refresh 2: refresh_failure → window=[{-1, age=0.5}, {-1, age=0}] 
           → tier_delta = -0.96 + (-1) ≈ -2 → Tier 1
           cost=200 tokens → budget: 999,850-200=999,650

Refresh 3: refresh_failure → window=[{-1, age=1}, {-1, age=0.5}, {-1, age=0}]
           → tier_delta ≈ -2.5 → Tier 1 (clamped at 1)
           cost=200 tokens → budget: 999,650-200=999,450

Refresh 4: refresh_success → window=[{-1, age=1.5}, {-1, age=1}, {-1, age=0.5}, {+2, age=0}]
           → tier_delta ≈ -2 + 1.96 ≈ 0 → Tier stays 1
           cost=200 tokens → budget: 999,450-200=999,250

Refresh 5 (1 day later): refresh_success → window=[{-1, age=2.5}, {-1, age=2}, {-1, age=1.5}, {+2, age=1}, {+3, age=0}]
           → tier_delta ≈ -1.4 + 1.96 + 2.94 ≈ +2.5 → Tier 3
           cost=100 tokens → budget: 999,250-100=999,150
```

**Observation:** Agent recovers through consistent good behavior, tier climbs back, cost drops.

---

## Error Semantics

### Scoring Failures (Step 6.5)

| Error | Cause | HTTP Status | Response |
|-------|-------|------------|----------|
| `behavior_window_corrupted` | JSON parse fails, missing fields | 500 INTERNAL_SERVER_ERROR | `{"status": "error", "reason": "behavior_window_corrupted", "detail": "..."}` |
| `invalid_event_type` | Unknown event_type in window | 400 BAD_REQUEST | `{"status": "error", "reason": "invalid_event_type", "detail": "..."}` |
| `behavior_window_fetch_failed` | DB timeout loading window | 500 INTERNAL_SERVER_ERROR | `{"status": "error", "reason": "behavior_window_fetch_failed"}` |

**Fail-Closed Policy:** All scoring errors deny refresh. Never proceed with stale/unknown tier.

### Tier Adjustment with Budget Exhaustion (Step 7)

| Condition | HTTP Status | Reason |
|-----------|------------|--------|
| Tier drops, new cost > remaining budget | 402 PAYMENT_REQUIRED | `budget_exhausted` (with remediation: "Improve behavior to restore tier and lower cost") |
| Tier improves, cost decreases | 200 OK | Proceeds normally (budget check passes) |
| Tier stays same | 200 OK (or 402 if already low) | Depends on absolute budget state |

**Example:**
```
Tier 3 → Tier 4 (cost increases by 50 tokens)
Remaining budget: 40 tokens
Result: 402 PAYMENT_REQUIRED

Remediation: "Your behavior has degraded (tier 4). Next successful refresh will improve tier and reduce cost. 
Retry after improving attestations or request manual tier reset from administrator."
```

---

## Lineage Safety: Behavior Propagation

### Core Invariant: Parent Behavior Does NOT Affect Children

**Rule:** A child session's behavior scoring uses **only** events in the child's behavior_window. Parent events are invisible.

**Rationale:**
- Delegation (Phase 6) grants autonomy; child is accountable for its own actions, not parent's mistakes.
- Prevents "blame cascade" (parent fails → all children penalized).
- Preserves delegation semantics: "I trust you to act independently."

**Implementation:**
```rust
// In score_behavior_window(), fetch only this session_id's events
let window = load_behavior_window(&pool, session_id).await?;
// Query: SELECT * FROM behavior_events WHERE session_id = $1 AND scored_at > now() - interval 7 days
// No parent_session_id join.
```

### Exception: Parent Revocation → Mark Events as "lineage_safe=false"

**When:** Parent session is revoked (Phase 6.1 cascade).

**What:** Descendant sessions' behavior events are marked (but not deleted).

```rust
// In revoke_cascade_handler (Phase 6.1):
sqlx::query(
    "UPDATE behavior_events 
     SET lineage_safe = FALSE 
     WHERE session_id IN (SELECT id FROM sessions WHERE parent_session_id = $1 OR ancestor_ids @> $2)"
)
.bind(parent_id)
.execute(&state.pool)
.await?;
```

**Effect on Scoring:**
- If window contains events with `lineage_safe=false`, they are **ignored** during tier_delta calculation (treated as if they don't exist).
- Tier drop during revocation cascade happens at the parent level (parent's tier drops) and cascades via `revocation_by_parent` event in each child's window.

**Example:**
```
Parent (Tier 3) revoked.
Child A's window: [{refresh_success, +1}, {refresh_failure, -1}, {revocation_by_parent, -10}]

At revocation time:
  - Insert {revocation_by_parent, -10, lineage_safe=false} into Child A's window
  - Child's next refresh scores as: (+1 - 1 + (-10)) / weights = -10 delta → Tier drops to 1

At next refresh:
  - revocation_by_parent event is read but lineage_safe=false, so it's excluded from scoring
  - Window effectively: {+1, -1} → small delta, tier stabilizes
```

**Invariant:** Revocation by parent is a **one-time penalty**, not a persistent curse.

---

## Migration for Phase 8

### Migration: `013_add_phase8_behavior_columns.sql`

```sql
-- Add behavior window to sessions
ALTER TABLE sessions
  ADD COLUMN behavior_window JSONB DEFAULT '{"events": [], "last_updated_at": null}';

-- Create behavior events table
CREATE TABLE behavior_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  event_type VARCHAR(32) NOT NULL,
  tier_before SMALLINT NOT NULL,
  tier_after SMALLINT NOT NULL,
  tier_delta SMALLINT NOT NULL,
  cost_incurred BIGINT NOT NULL,
  attestation_count SMALLINT NOT NULL,
  revocation_reason TEXT,
  scored_at TIMESTAMPTZ NOT NULL,
  lineage_safe BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_behavior_events_session_id ON behavior_events(session_id);
CREATE INDEX idx_behavior_events_scored_at ON behavior_events(scored_at);
CREATE INDEX idx_behavior_events_lineage ON behavior_events(session_id, lineage_safe)
  WHERE lineage_safe = TRUE;

-- Ensure all sessions start with baseline tier 3 (if not already set)
UPDATE sessions SET trust_tier = 3 WHERE trust_tier IS NULL;
```

### Backward Compatibility

- **Phase 5/6/7 sessions:** behavior_window initialized as empty JSON (no events, no scoring effect).
- **Phase 8 code:** Handles empty windows gracefully (tier_delta = 0, no change).
- **Zero-downtime:** Columns added with defaults; existing refreshes work without scoring.
- **Rollback:** Phase 7 code ignores behavior_window and new behavior_events table (harmless).

---

## Known Limitations & Future Work

### Phase 8 Limitations

1. **No real-time scoring:** Behavior is scored only at refresh time, not during other operations (no continuous monitoring).
2. **Simple decay model:** Exponential decay with fixed half-life. No custom per-event-type decay rates.
3. **No capability pruning:** Tier affects cost but not which operations are allowed (phase 9+).
4. **Window snapshot semantics:** Concurrent refreshes may see inconsistent windows (snapshot taken asynchronously). Expected behavior: idempotent scoring (same refresh retried = same result).

### Future Enhancements

- **Phase 9:** Capability pruning (tie trust tier directly to allowed API endpoints, e.g., tier 13 can't create new delegations).
- **Phase 10:** Real-time event streaming (events scored immediately, not at refresh).
- **Phase 10:** Per-event-type decay rates (e.g., revocation events decay slower than refresh_success).
- **Phase 10:** Behavior event replay & audit trail (full history with immutable proof).

---

## Specification Compliance Checklist

- [ ] Behavior window (sliding 7-day, immutable snapshot during refresh)
- [ ] Exponential decay model (half-life 3.5 days)
- [ ] BehaviorEvent schema (5 event types: refresh_success, refresh_failure, revocation_by_parent, revocation_self, delegation_created)
- [ ] Deterministic scoring contract (pure function, same input → same output)
- [ ] Step 5.5 integration (capture event)
- [ ] Step 6.5 integration (score & adjust tier)
- [ ] Step 7 integration (recalculate cost with new tier)
- [ ] Step 13 integration (atomic persistence of tier + event + window)
- [ ] Budget/tier coupling rules (tier drop → cost increase → budget pressure)
- [ ] Error semantics (500 on corruption, 402 if cost increases beyond budget)
- [ ] Lineage safety (parent events invisible, revocation marked but ignored)
- [ ] Migration 013 (adds behavior_window, behavior_events table, indexes)

---

## Summary: The Feedback Loop

**Phase 5:** Attestations → Trust tier (static per refresh).  
**Phase 6:** Delegation → Immutable tier ceilings (governance).  
**Phase 7:** Economics → Token cost tied to tier (resource control).  
**Phase 8:** Behavior → Tier adjustment → Dynamic cost (feedback).

Every refresh is an event. Events score to a tier adjustment. Tier adjusts immediately. Cost recalculates. Budget tightens or loosens. Next refresh feels the pressure. Agent corrects or degrades. Loop continues.

Deterministic, atomic, lineage-safe, fail-closed.
