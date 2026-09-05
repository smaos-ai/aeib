# Phase 34: Consolidation Tier Promotion — Design Specification

**Date:** 2026-05-11  
**Status:** Approved  
**Context:** Phases 28–33 created an evolutionary feedback loop: signals that prove accurate gain confidence and resist noise; signals that fail decay rapidly into silence. Phase 34 crystallizes this process: signals that cross > 0.90 confidence are promoted from Episodic (testable) to Semantic tier (structural knowledge), gaining long-term resistance to decay and representing the system's learned ground truth.

---

## Problem Statement

Phases 32–33 create a dynamic equilibrium where accuracy drives confidence up and inaccuracy drives it down. But signals can still decay over time, even proven ones. A signal that achieves 0.95 confidence through months of validation should not risk returning to 0.0 just because it wasn't seen for 30 days.

**Example:** An AnomalyChainNode "dispute_spam→timeout_spam" validates for 90 days, reaching 0.92 confidence. Then the pattern goes quiet (legitimately: disputes disappear in that region). After 7 weeks, the 7-day half-life has decayed it to 0.46. The system has forgotten a proven relationship.

**Solution:** Promote proven signals to Semantic tier. When confidence > 0.90, the signal transitions from Episodic (testable, short memory) to Semantic (structural, long memory). Semantic signals use 30-day half-life, ignore acceleration_mode, and represent crystallized ground truth. If they fail validation (confidence drops below 0.85), they're demoted back to Episodic for re-testing.

---

## Design Overview

### Tier System: Episodic ↔ Semantic

**Episodic Tier (Default)**
- **Purpose:** Patterns being tested and refined
- **Decay:** 7-day half-life (normal) or 2-day (accelerated on FP)
- **Acceleration:** Responds to acceleration_mode flag
- **Memory span:** ~30 days to floor (0.05)
- **Demotion:** When confidence drops below 0.85 in Semantic tier through FPs

**Semantic Tier (Promoted)**
- **Purpose:** Crystallized ground truth; structural knowledge of the domain
- **Decay:** 30-day half-life (constant)
- **Acceleration:** Disabled; ignores acceleration_mode flag entirely
- **Memory span:** ~240 days to floor (0.05) — 8x longer than Episodic
- **Demotion:** When confidence drops below 0.85 through accumulated false positives

### State Machine

```
Episodic (confidence < 0.90)
    ↓ [confidence crosses > 0.90 via TP reinforcement]
Semantic (confidence 0.90+)
    ↓ [confidence drops below 0.85 via accumulated FPs]
Episodic (confidence < 0.85)
    ↑ [can re-promote if re-validates to > 0.90]
```

**Hysteresis Zone (0.85–0.90):** Prevents thrashing. A signal at 0.88 confidence stays Semantic; does not toggle between tiers on minor fluctuations.

### Data Model: Property-Based Mutation

**Signal node properties (extended from Phase 33):**

```json
{
    "tier": "episodic" | "semantic",
    "confidence": f64,
    "acceleration_mode": boolean,
    "last_seen_at": DateTime,
    "promoted_at": DateTime | null,
    "last_demotion_at": DateTime | null
}
```

**Critical constraint:** Tier promotion/demotion updates the `tier` property **in-place** on existing signal nodes. No new nodes created, no edges severed. Historical dependency relationships are preserved.

**Mutation logic:**
```sql
UPDATE graph_entities
SET properties = jsonb_set(properties, '{tier}', '"semantic"')
WHERE id = $signal_id
  AND properties->>'tier' = 'episodic'
  AND (properties->>'confidence')::float > 0.90
```

### Decay Formula (Query-Time)

```rust
fn apply_decay_with_tier(
    confidence: f64,
    last_seen_at: DateTime<Utc>,
    tier: "episodic" | "semantic",
    acceleration_mode: bool
) -> f64 {
    let days_since = (Utc::now() - last_seen_at).num_days() as f64;
    
    let half_life = match tier {
        "semantic" => 30.0,  // Long-term memory
        "episodic" => {
            if acceleration_mode { 2.0 } else { 7.0 }  // Short-term, dynamic
        }
    };
    
    let decayed = confidence * 0.5_f64.powf(days_since / half_life);
    decayed.max(0.05)  // Floor at 5%
}
```

**Key behavior:** Semantic tier ignores `acceleration_mode`. False positives do NOT accelerate decay for Semantic signals; they only reduce confidence through normal 30-day half-life.

### Data Flow

#### 1. Promotion (Episodic → Semantic)

When `reinforce_signals_for_feedback()` boosts a signal and confidence now > 0.90:

```
reinforce_signals_for_feedback(pool, feedback_node_id, matched=true)
  ↓
confidence boosted: current + ((1.0 - current) * 0.05)
  ↓
if new_confidence > 0.90 AND tier == "episodic":
  UPDATE signal SET tier = "semantic", promoted_at = now
  Log: "Signal promoted: {signal_type} {sovereign_id} → Semantic tier"
  ↓
else:
  No promotion (already Semantic or confidence < 0.90)
```

#### 2. Demotion (Semantic → Episodic)

When a Semantic signal accumulates false positives and confidence drops below 0.85:

```
record_feedback_for_anomaly(pool, anomaly, matched=false)
  ↓
accelerate_signal_decay_for_false_positive(pool, feedback_node_id)
  ↓
for each signal in evidence:
  if tier == "semantic":
    confidence_after_decay = apply_decay_with_tier(..., "semantic", false)
    ↓
    if confidence_after_decay < 0.85:
      UPDATE signal SET tier = "episodic", last_demotion_at = now
      Reset acceleration_mode = false (return to normal rules)
      Log: "Signal demoted: {signal_type} {sovereign_id} → Episodic tier"
      ↓
    else:
      No demotion (still above threshold)
```

#### 3. Hysteresis Stability

Signal at 0.88 confidence (in Semantic tier):
- Receives TP reinforcement: 0.88 + 0.06 = 0.94 → stays Semantic
- Receives FP, decays slightly: 0.88 × 0.9999 ≈ 0.879 → stays Semantic
- Never reaches 0.85 threshold → no involuntary demotion
- Prevents thrashing; signal stabilizes in Semantic tier once proven

#### 4. During Forecast (run_forecast_once)

When applying decay during prediction synthesis:

```rust
let tier = signal_props.get("tier").and_then(|v| v.as_str()).unwrap_or("episodic");
let decayed_confidence = apply_decay_with_tier(
    row.confidence,
    row.last_seen_at,
    tier,
    row.acceleration_mode
);
```

Semantic signals use 30-day half-life regardless of acceleration_mode state.

---

## Architecture: Single Module Extension

**File:** `crates/siss-graph-db/src/signal_tier_promotion.rs` (new module)

**Public interface:**

```rust
pub async fn promote_signal_to_semantic_on_validation(
    pool: &PgPool,
    signal_id: Uuid,
    signal_type: &str,
    new_confidence: f64,
) -> Result<bool, sqlx::Error>
// Returns true if promotion occurred, false if already Semantic or below threshold

pub async fn demote_signal_to_episodic_on_failure(
    pool: &PgPool,
    signal_id: Uuid,
    signal_type: &str,
    confidence_after_decay: f64,
) -> Result<bool, sqlx::Error>
// Returns true if demotion occurred, false if stayed Semantic or above threshold
```

**Integration points:**

1. **signal_reinforcement.rs:** After boosting confidence, call `promote_signal_to_semantic_on_validation()`
2. **signal_acceleration.rs:** Before setting acceleration_mode on Semantic signals, check tier
3. **forecast_engine.rs:** Pass tier to decay formula

---

## Data Model: Signal Row Extension

**prediction_query.rs - extend SignalRow:**

```rust
#[derive(Debug, Clone, FromRow)]
pub struct SignalRow {
    pub sovereign_id: Uuid,
    pub signal_type: String,
    pub confidence: f64,
    pub chain_type: Option<String>,
    pub anomaly_type: Option<String>,
    pub last_seen_at: DateTime<Utc>,
    pub acceleration_mode: bool,
    pub tier: String,  // NEW: "episodic" | "semantic"
    pub promoted_at: Option<DateTime<Utc>>,  // NEW: for auditing
}
```

**SQL query update:**

```sql
SELECT
    (properties->>'sovereign_id')::uuid AS sovereign_id,
    label AS signal_type,
    (properties->>'confidence')::float AS confidence,
    properties->>'chain_type' AS chain_type,
    properties->>'anomaly_type' AS anomaly_type,
    (properties->>'last_seen_at')::timestamptz AS last_seen_at,
    COALESCE((properties->>'acceleration_mode')::boolean, false) AS acceleration_mode,
    COALESCE(properties->>'tier', 'episodic') AS tier,
    (properties->>'promoted_at')::timestamptz AS promoted_at
FROM graph_entities
WHERE label IN ('AnomalyChainNode', 'CorrelationPatternNode', 'RecoveryCorrelationNode')
  AND (properties->>'confidence')::float > 0.0
```

---

## Testing Strategy (9 tests)

**File:** `crates/siss-graph-db/src/signal_tier_promotion.rs` (tests 1–5), modified integration tests (6–9)

| # | Test | Setup | Asserts |
|---|------|-------|---------|
| 1 | `test_promote_signal_at_0_90_threshold` | Signal tier=episodic, confidence=0.90 | Promoted to Semantic; promoted_at set |
| 2 | `test_no_promote_below_0_90_threshold` | Signal tier=episodic, confidence=0.89 | Stays Episodic; returns false |
| 3 | `test_demote_signal_at_0_85_threshold` | Signal tier=semantic, confidence=0.85 (after decay) | Demoted to Episodic; last_demotion_at set |
| 4 | `test_no_demote_above_0_85_threshold` | Signal tier=semantic, confidence=0.86 | Stays Semantic; returns false |
| 5 | `test_hysteresis_at_0_88_stays_semantic` | Signal tier=semantic, confidence=0.88, minor FP | Stays Semantic (doesn't hit 0.85) |
| 6 | `test_semantic_decay_uses_30_day_half_life` | Semantic signal, last_seen=30d ago, confidence=0.8 | decayed = 0.4 (0.8 × 0.5^(30/30)) |
| 7 | `test_semantic_decay_ignores_acceleration_mode` | Semantic signal, acceleration_mode=true, last_seen=14d ago | Uses 30-day half-life (not 2-day); decayed ≈ 0.7 |
| 8 | `test_episodic_decay_with_acceleration_uses_2_day_half_life` | Episodic signal, acceleration_mode=true, last_seen=14d ago | Uses 2-day half-life; decayed ≈ 0.008 → floored to 0.05 |
| 9 | `test_promotion_on_reinforcement_integration` | TP reinforcement boosts signal to 0.91, tier=episodic | Signal promoted to Semantic automatically |

### Backward Compatibility

- All existing Phase 28-33 tests remain green
- New `tier` property defaults to "episodic" (COALESCE in SQL query)
- Signals without `promoted_at` are treated as Episodic
- No breaking changes to APIs

---

## Edge Cases & Stability

### Signal Promoted, Then Immediately Fails

Semantic signal at 0.91 receives FP and decays 30% per day (30-day half-life). After 10 days: 0.91 × 0.5^(10/30) ≈ 0.81. Just below threshold; demoted.

This is correct: a signal that fails immediately after promotion loses its status. Must re-validate to regain Semantic tier.

### Re-Promotion After Demotion

A demoted signal (tier=episodic, confidence=0.80) can be re-promoted if it accumulates new TPs and reaches > 0.90 again. No permanent lock-out. System is forgiving but requires proof.

### Multiple Promotions/Demotions

Mutations are idempotent:
- `UPDATE ... SET tier = 'semantic'` applied twice is safe (still Semantic)
- `UPDATE ... SET tier = 'episodic'` applied twice is safe (still Episodic)
- `promoted_at` and `last_demotion_at` are audit timestamps; multiple updates don't violate integrity

### Property-Based Mutation: No Edge Severance

Tier changes update properties in-place via `jsonb_set()`. No node deletion, no node creation, no edge disruption. Historical dependency relationships (PREDICTS, FEEDBACK_FOR, etc.) remain intact and queryable.

### Semantic Signals Don't Panic on FP

Semantic signals receiving false positives:
1. Do NOT enter acceleration_mode (ignored by decay formula)
2. Do NOT decay 3.5x faster (use 30-day half-life regardless)
3. DO decay at normal 30-day rate
4. DO get demoted if confidence falls below 0.85

This is intentional: Semantic signals are defended against noise, but not immune to repeated invalidation.

---

## Integration Points

**Phase 32 (Reinforcement):** After boosting confidence, check if > 0.90; if so, promote to Semantic

**Phase 33 (Acceleration):** Skip setting acceleration_mode if tier == "semantic"; Semantic signals ignore this flag

**Phase 29 (Decay):** Extend `apply_decay()` to accept tier parameter; use appropriate half-life

**Phase 31 (Weighting):** Predictions using Semantic signals are inherently more trustworthy; can optionally apply confidence boost to forecasts from Semantic signals

---

## Performance

- Promotion/demotion: Single UPDATE statement, O(1)
- Decay calculation: Check tier (string comparison), apply appropriate half-life formula, O(1)
- Query: Include tier in SELECT; one extra COALESCE per signal, negligible cost
- No new indexes required; tier is just a property value

---

## Non-Goals (Phase 34)

- No per-signal-type tier promotion rates (chain/corr/recovery all treated uniformly)
- No automatic confidence ceiling reset (Phase 35+ territory)
- No configurable tier thresholds (0.90/0.85/30-day locked in)
- No REST/GraphQL endpoints for tier status
- No visualization of tier distribution
- No bulk tier migration (each signal promoted individually via TP validation)

---

## Success Criteria

- [x] `tier` property added to signal nodes (episodic | semantic)
- [x] Promotion triggered at confidence > 0.90 via reinforcement
- [x] Demotion triggered at confidence < 0.85 via FP decay
- [x] Hysteresis zone (0.85–0.90) prevents thrashing
- [x] Semantic signals use 30-day half-life
- [x] Semantic signals ignore acceleration_mode flag
- [x] Property-based mutation preserves edges and historical context
- [x] All 9 new tests pass
- [x] All existing Phase 28-33 tests still pass (34 tests green)
- [x] cargo fmt and cargo clippy clean
- [x] No schema migrations (property addition only)
- [x] Commit with detailed message

---

## Timeline

Phase 34 transforms signals from ephemeral patterns into structural knowledge. The system now has **long-term memory:**

- **Episodic tier:** Dynamic, testable, 30-day memory span — for patterns under evaluation
- **Semantic tier:** Stable, proven, 240-day memory span — for domain knowledge

Signals that prove themselves through repeated validation become permanent fixtures of the prediction system. The system learns and retains its learning.

**Evolutionary physics summary (Phases 28–34):**
- **Phase 28-29:** Create signals; apply decay
- **Phase 30:** Measure accuracy empirically
- **Phase 31:** Weight predictions by measured accuracy
- **Phase 32:** Reward true positives (boost confidence)
- **Phase 33:** Penalize false positives (accelerate decay)
- **Phase 34:** Crystallize proven patterns (promote to Semantic tier)

The result: A self-learning intelligence system with both short-term adaptability and long-term structural knowledge.
