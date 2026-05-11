# Phase 29: Temporal Signal Decay — Design Specification

**Date:** 2026-05-11  
**Status:** Approved  
**Context:** Phases 25–28 built a complete signal synthesis pipeline. Phase 29 adds temporal decay so predictions stay current and don't perpetuate stale patterns.

---

## Problem Statement

Signal nodes (CorrelationPatternNode, AnomalyChainNode, RecoveryCorrelationNode) persist with constant confidence values. Without decay, old signals keep influencing forecasts indefinitely, causing predictions to reflect dead patterns and misleading risk assessments for sovereigns that have recovered.

**Example:** A sovereign had frequent timeout anomalies 60 days ago. The chain signal still has confidence 0.8. Without decay, the forecast continues to predict timeout spam even though the pattern stopped months ago.

---

## Design Overview

**Core principle:** Exponential decay is applied at **query time** during prediction synthesis. Signal nodes in the database remain immutable; decay is computed fresh each forecast cycle using the half-life model.

### Decay Model

**Formula:**
```
decayed_confidence = original_confidence × 0.5^(days_since_last_seen / 7)
```

**Half-life:** 7 days  
**Rationale:** 
- 3 days is too twitchy; thrashes predictions for slower sovereigns
- 14 days keeps dead patterns alive too long; muddies forecasts
- 7 days matches week-scale operational cycles (chains, recovery windows, ops rhythms) and keeps system responsive without being jumpy

**Confidence floor:** 0.05 (5%)  
**Behavior:** Signals with decayed confidence < 0.05 are skipped in aggregation; they no longer contribute to risk scores.

---

## Data Flow

1. **Signal storage (unchanged):**  
   CorrelationPatternNode, AnomalyChainNode, RecoveryCorrelationNode store `confidence` and `last_seen_at` as immutable observations.

2. **Forecast cycle:**  
   `run_forecast_once()` reads all signals, applies decay calculation in Rust using `last_seen_at` and `Utc::now()`.

3. **Aggregation:**  
   Only signals with `decayed_confidence ≥ 0.05` are aggregated into per-sovereign signal maps.  
   Floored signals are silently skipped (no error, no warning).

4. **Risk scoring:**  
   PredictionNode risk score = 0.5×(max decayed chain confidence) + 0.3×(max decayed correlation confidence) + 0.2×(max decayed recovery confidence).  
   PredictionNode is naturally regenerated each run with fresh decay applied.

5. **Refresh behavior:**  
   - When a signal re-occurs (e.g., chain detected again), `last_seen_at` updates to now
   - Decay timer resets: `days_since_last_seen` becomes 0 or near-0
   - **Confidence does NOT jump:** It stays at current decayed level and rebuilds gradually through repeated observations
   - Over subsequent cycles, if the pattern continues, confidence asymptotically rebuilds toward original through repeated reinforcement

### Example Timeline

Signal: AnomalyChainNode "dispute_spam→timeout_spam" for Sovereign A  
Original confidence: 0.80

| Time | Event | last_seen_at | days_since | decayed_confidence | In forecast? |
|------|-------|--------------|------------|--------------------|--------------|
| Day 0 | First observed | Day 0 | 0 | 0.80 | ✓ |
| Day 7 | Not refreshed | Day 0 | 7 | 0.40 | ✓ |
| Day 14 | Not refreshed | Day 0 | 14 | 0.20 | ✓ |
| Day 21 | Not refreshed | Day 0 | 21 | 0.10 | ✓ |
| Day 28 | Not refreshed | Day 0 | 28 | 0.05 | ✓ (edge) |
| Day 30 | Not refreshed | Day 0 | 30 | 0.044 | ✗ (floored) |
| Day 35 | **Chain re-occurs** | Day 35 | 0 | 0.044 | ✓ (reset, no jump) |
| Day 42 | Not refreshed again | Day 35 | 7 | 0.022 | ✗ (floored) |

---

## Implementation

### Code Changes

**File:** `crates/siss-graph-db/src/forecast_engine.rs`

**Add helper function:**
```rust
/// Compute decayed confidence using 7-day exponential half-life.
/// Returns original confidence if days_since_last_seen < 0 (clock skew protection).
fn apply_decay(confidence: f64, last_seen_at: DateTime<Utc>) -> f64 {
    let days_since_last_seen = (Utc::now() - last_seen_at).num_days() as f64;
    if days_since_last_seen < 0.0 {
        confidence // Clock skew: assume no decay
    } else {
        confidence * 0.5_f64.powf(days_since_last_seen / 7.0)
    }
}
```

**Modify signal aggregation in `run_forecast_once()`:**
- In the loop over `signals`, compute `decayed_confidence = apply_decay(row.confidence, row.last_seen_at)`
- Skip signals where `decayed_confidence < 0.05`
- Use `decayed_confidence` instead of `row.confidence` for aggregation

**No schema changes.** Decay is pure query-side logic.

### Testing Strategy (4 tests)

**Test 1: `test_decay_at_zero_days_is_identity`**  
- Insert signal with last_seen_at = now, confidence = 0.8
- Run forecast
- Assert decayed_confidence ≈ 0.8 (no decay at time 0)

**Test 2: `test_decay_at_seven_days_is_half`**  
- Insert signal with last_seen_at = 7 days ago, confidence = 0.8
- Run forecast
- Assert decayed_confidence ≈ 0.4 (50% of original)

**Test 3: `test_decay_below_floor_is_skipped`**  
- Insert signal with last_seen_at = 40 days ago, confidence = 0.8
  - Decayed: 0.8 × 0.5^(40/7) ≈ 0.028 < 0.05
- Run forecast
- Assert signal does NOT aggregate into sovereign signal map

**Test 4: `test_forecast_with_decayed_signals_lowers_risk`**  
- Insert fresh chain signal (confidence 0.6, last_seen_at = now)
- Insert correlation signal (confidence 0.5, last_seen_at = 14 days ago)  
  - Decayed: 0.5 × 0.5^(14/7) = 0.25
- Run forecast
- Assert risk_score = 0.5×0.6 + 0.3×0.25 + 0.2×0 = 0.375
- Verify it's lower than if correlation were fresh (0.5×0.6 + 0.3×0.5 = 0.45)

---

## Edge Cases & Stability

### Clock Skew
If `last_seen_at` is in the future (clock skew), `days_since_last_seen` is negative. Return original confidence without decay. This prevents anomalous behavior if system clocks drift.

### Signal Never Refreshed
Confidence asymptotically approaches 0 but never reaches it. Decay continues until floor (0.05) is crossed, after which the signal is ignored. This is stable and expected.

### Refresh Behavior (No Jump)
When a signal re-occurs:
1. `last_seen_at` updates to now
2. Confidence stays at current decayed level (does NOT reset to original)
3. On next cycle, decay resets (days_since = 0), confidence stays as-is
4. Over subsequent cycles, if the pattern persists, confidence gradually rebuilds through repeated observations

This prevents sudden jumps in risk scores while still responding to pattern recurrence.

### PredictionNode Volatility
PredictionNode is recomputed each cycle from decayed signals. Risk score naturally stabilizes because decay is deterministic. If patterns persist, confidence gradually rebuilds; if they stop, risk naturally falls off.

---

## Integration with Phases 25–28

- **Phase 25 (CorrelationPatternNode):** Decay applied at query time; confidence property unchanged
- **Phase 26 (AnomalyChainNode):** Decay applied at query time; confidence property unchanged
- **Phase 27 (RecoveryCorrelationNode):** Decay applied at query time; confidence property unchanged
- **Phase 28 (Forecast engine):** Aggregation loop modified to apply decay; risk score uses only non-floored signals

No changes to upstream extraction engines (causal_extractor, chain_extractor, recovery_extractor). They continue to upsert signals as before.

---

## Success Criteria

- [x] Decayed confidence follows 0.5^(days/7) formula
- [x] Signals below 0.05 floor are skipped in aggregation
- [x] Refresh resets decay timer without jumping confidence
- [x] All 4 tests pass
- [x] cargo fmt and cargo clippy clean
- [x] No schema migrations needed

---

## Non-Goals (Phase 29)

- No decay for PredictionNode itself (derived from signals; naturally decays)
- No configurable half-life (fixed at 7 days)
- No decay tracking metadata (fresh compute each cycle)
- No bulk signal cleanup (aged-out signals stay in DB; simply ignored)
- No user-facing decay metrics (internal implementation detail)
