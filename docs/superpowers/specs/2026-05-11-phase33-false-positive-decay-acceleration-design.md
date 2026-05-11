# Phase 33: False Positive Decay Acceleration — Design Specification

**Date:** 2026-05-11  
**Status:** Approved  
**Context:** Phase 32 rewards true positives by boosting signal confidence. Phase 33 completes the feedback loop by penalizing false positives: signals that repeatedly fire and miss are forced into accelerated decay, silencing hallucinated patterns before they consume the attention budget.

---

## Problem Statement

Phase 32 reinforces accurate signals (boost confidence + reset decay timer). But signals that produce false positives are treated passively: they simply don't get boosted and decay naturally over 7 days. 

**Example:** A signal fires 5 times and matches 1 prediction, 4 misses. It receives +5% confidence boost once but decays at normal rate the other 4 times. Net result: signal slowly decays over weeks, but keeps producing false alerts during that window.

**Solution:** Accelerate decay on false positives. When matched=false, the signal immediately enters acceleration mode: decay half-life drops from 7 days to 2 days. This rapidly silences noisy patterns. When the signal validates again (matched=true), revert to normal 7-day decay.

---

## Design Overview

### Decay Acceleration Mechanism

**Default decay (Phase 29):**
```
decayed_confidence = original_confidence × 0.5^(days_since_last_seen / 7)
```
Half-life: 7 days

**Accelerated decay (Phase 33, on false positive):**
```
decayed_confidence = original_confidence × 0.5^(days_since_last_seen / 2)
```
Half-life: 2 days (3.5x faster decay)

### State Machine

Signal nodes can be in one of two decay modes:

| Mode | Half-life | Trigger | Reset Trigger |
|------|-----------|---------|---------------|
| Normal | 7 days | Default; signal validates (matched=true) | Signal fires and misses |
| Accelerated | 2 days | Signal fires and misses (matched=false) | Signal validates (matched=true) |

**Data model:** Add property to signal nodes:
```json
{
    "acceleration_mode": boolean  // false = normal (7d), true = accelerated (2d)
}
```

### Data Flow

#### 1. On False Positive (matched=false)

When `record_feedback_for_anomaly()` creates a FeedbackNode with matched=false:

```
feedback_created(pool, feedback_node_id, matched=false)
  ↓
fetch FeedbackNode.signal_id (via evidence)
  ↓
for each signal in evidence:
  signal.properties.acceleration_mode = true
  Update signal node
  ↓
Log: "Signal accelerated: {signal_type} {sovereign_id} → 2-day half-life"
```

#### 2. On True Positive (matched=true)

When FeedbackNode with matched=true:
- Signal confidence boosted (Phase 32)
- **NEW:** Reset acceleration_mode = false
- Decay reverts to normal 7-day half-life
- Log: "Signal recovery: {signal_type} {sovereign_id} → 7-day half-life"

#### 3. During Forecast (run_forecast_once)

When applying decay in forecast cycle, check acceleration_mode:

```rust
fn apply_decay_with_acceleration(
    confidence: f64,
    last_seen_at: DateTime<Utc>,
    acceleration_mode: bool
) -> f64 {
    let days_since = (Utc::now() - last_seen_at).num_days() as f64;
    let half_life = if acceleration_mode { 2.0 } else { 7.0 };
    confidence * 0.5_f64.powf(days_since / half_life)
}
```

---

## Architecture: Two Implementation Modules

### 1. signal_acceleration.rs (new module)

**Public interface:**
```rust
pub async fn accelerate_signal_decay_for_false_positive(
    pool: &PgPool,
    feedback_node_id: Uuid,
) -> Result<usize, sqlx::Error>
// Returns count of signals accelerated
```

**Internal logic:**
- Query FeedbackNode by ID; check if matched=false
- If matched=true, return 0 (no acceleration on TP)
- Fetch PredictionNode via FEEDBACK_FOR edge
- Extract evidence from signal_breakdown
- For each signal: set acceleration_mode=true
- Upsert signal nodes
- Return count

**Error handling:** Return sqlx::Error on database failures. Non-false-positive feedback returns 0 (not an error).

### 2. feedback_recorder.rs + forecast_engine.rs (MODIFY)

**feedback_recorder.rs:**
- After creating FeedbackNode with matched=false, call `accelerate_signal_decay_for_false_positive()`
- After creating FeedbackNode with matched=true, reset acceleration_mode=false on contributing signals

**forecast_engine.rs:**
- Modify `apply_decay()` to accept acceleration_mode parameter
- Use 2-day half-life if acceleration_mode=true, else 7-day

---

## Data Model

### Signal Node Properties (Extended)

All signal node types (AnomalyChainNode, CorrelationPatternNode, RecoveryCorrelationNode):

**New property:**
```json
{
    "acceleration_mode": boolean,  // false = normal (7d), true = accelerated (2d)
    "last_seen_at": DateTime,      // existing; used for decay calculation
    "confidence": f64              // existing; subject to decay
}
```

**Default:** acceleration_mode = false (normal decay on creation)

---

## Testing Strategy (8 tests)

**File:** `crates/siss-graph-db/src/signal_acceleration.rs` (tests 1–5), `feedback_recorder.rs` (tests 6–8)

| # | Test | Setup | Asserts |
|---|------|-------|---------|
| 1 | `test_accelerate_signal_sets_acceleration_mode_true` | Signal confidence=0.8, FeedbackNode matched=false | Signal.acceleration_mode=true; count=1 |
| 2 | `test_accelerate_signal_does_nothing_on_true_positive` | FeedbackNode matched=true | count=0; signal.acceleration_mode remains false |
| 3 | `test_accelerate_signal_applies_to_all_contributing_signals` | 3 signals in evidence, FeedbackNode matched=false | All 3 have acceleration_mode=true; count=3 |
| 4 | `test_accelerate_signal_resets_on_validation` | Signal in acceleration_mode=true, FeedbackNode matched=true | Signal.acceleration_mode=false; reverted to normal decay |
| 5 | `test_apply_decay_with_acceleration_uses_2_day_half_life` | confidence=0.8, last_seen_at=14d ago, acceleration_mode=true | decayed_confidence ≈ 0.2 (0.8 × 0.5^(14/2) = 0.00781, floor at 0.05) |
| 6 | `test_apply_decay_without_acceleration_uses_7_day_half_life` | confidence=0.8, last_seen_at=14d ago, acceleration_mode=false | decayed_confidence ≈ 0.2 (0.8 × 0.5^(14/7) = 0.2, not floored) |
| 7 | `test_record_feedback_false_positive_triggers_acceleration` | Prediction with signal, anomaly doesn't match | Signal.acceleration_mode=true; FeedbackNode created |
| 8 | `test_record_feedback_true_positive_resets_acceleration` | Signal in acceleration_mode=true, anomaly matches | Signal.acceleration_mode=false; confidence boosted |

### Backward Compatibility

All existing Phase 28-32 tests remain green. New acceleration_mode property defaults to false (backward compatible).

---

## Edge Cases & Stability

### Signal Already Accelerated

If acceleration_mode=true and another FP occurs, idempotent: set acceleration_mode=true again (no change). Multiple FPs don't "stack" or compound; acceleration is binary.

### Acceleration Mode Persistence

Signal stays in acceleration_mode=true until it validates (matched=true). If it never validates, it decays rapidly to floor (0.05) and is ignored in forecasts per Phase 29 rules.

### Clock Skew

If last_seen_at is in future (clock skew), decay returns original confidence without decay per Phase 29. Acceleration mode doesn't change behavior.

### Mixed Signal Types

If a PredictionNode has chain + correlation + recovery signals in evidence, and feedback is matched=false:
- All 3 get acceleration_mode=true
- Each decays at 2-day half-life
- All revert to normal 7-day on next TP

### Forecast Cycle Integration

During `run_forecast_once()`:
- Fetch signal nodes with their acceleration_mode flag
- Apply decay with appropriate half-life
- Signals below floor (0.05) are skipped per Phase 29
- Accelerated signals hit floor much faster (2 days vs 7 days)

---

## Integration Points

**Phase 29 (Decay):** Decay formula extended with acceleration_mode parameter. Backward compatible; default mode uses 7-day half-life.

**Phase 30 (Feedback):** No changes to feedback_recorder.rs API; new call to accelerate_signal_decay is internal.

**Phase 31 (Weight Adjustment):** Unaffected; uses accuracy metrics independent of signal state.

**Phase 32 (Reinforcement):** True positive handling extended: boost confidence AND reset acceleration_mode.

**Phase 28 (Forecast):** Modified to accept acceleration_mode when computing decay during signal aggregation.

---

## Performance

Acceleration check is O(1) per signal (boolean property). No additional database queries. Decay calculation: same as Phase 29 (single exponentiation). No performance regression.

---

## Non-Goals (Phase 33)

- No signal deletion (aged-out signals stay in DB; simply ignored)
- No tier promotion (Phase 34)
- No explicit confidence penalty (acceleration is penalty enough)
- No configurable half-life values (2 days locked in for acceleration)
- No per-signal-type acceleration rates (all signal types treated uniformly)
- No REST/GraphQL endpoints for acceleration metrics

---

## Success Criteria

- [x] acceleration_mode property added to signal nodes
- [x] accelerate_signal_decay_for_false_positive() loads evidence and sets mode
- [x] apply_decay() extended with acceleration_mode parameter
- [x] run_forecast_once() passes acceleration_mode to decay function
- [x] record_feedback_for_anomaly() calls acceleration on matched=false
- [x] feedback_recorder.rs resets acceleration_mode on matched=true
- [x] All 8 new tests pass
- [x] All existing Phase 28-32 tests still pass
- [x] cargo fmt and cargo clippy clean
- [x] No schema migrations needed (JSON property only)
- [x] Commit with detailed message

---

## Timeline

Phase 33 completes the feedback penalty system. False positives are now actively suppressed, not just passively ignored. Combined with Phase 32 reinforcement:

- **True positives:** Confidence boosted, decay reset (7-day half-life)
- **False positives:** Acceleration mode enabled (2-day half-life, 3.5x faster decay)

Result: Accurate signals accelerate toward 1.0; inaccurate signals crash toward floor. System naturally evolves toward high-signal, low-noise prediction landscape.
