# Phase 32: Signal Reinforcement — Design Specification

**Date:** 2026-05-11  
**Status:** Approved  
**Context:** Phases 28–31 built a complete prediction pipeline with empirical feedback loop. Phase 32 closes the adaptive cycle: when predictions are validated (matched anomalies), the underlying signal nodes are reinforced. Signals that prove accurate gain confidence and have their decay timers reset, creating a living, self-improving prediction engine.

---

## Problem Statement

Phase 31 applies accuracy metrics to adjust forecast risk scores, but the signal nodes themselves remain static. A signal with 80% historical accuracy should be more trusted than one with 40% accuracy, yet both decay at the same 7-day half-life and accumulate confidence identically.

**Example:** An AnomalyChainNode "dispute_spam→timeout_spam" has confidence 0.6 and hasn't been seen for 14 days (decayed to 0.3). When this chain is observed again AND validated by a FeedbackNode match, it should:
1. Have `last_seen_at` reset to now (decay timer reset: days_since_last_seen → 0)
2. Have confidence boosted to reward the correct prediction

Without signal reinforcement, the chain rebuilds confidence only through repeated fresh observations. With reinforcement, proven patterns rebuild faster and decay slower, compounding trust in empirically validated signals.

---

## Design Overview

### Confidence Boost Formula (Locked)

When a FeedbackNode indicates a true positive (matched=true), the contributing signal nodes receive a confidence boost:

```
new_confidence = current_confidence + ((1.0 - current_confidence) * 0.05)
```

**Semantics:** Boost by 5% of remaining headroom to 1.0.

**Examples:**
- current = 0.3 → boost 0.035 → new = 0.335
- current = 0.6 → boost 0.020 → new = 0.620
- current = 0.9 → boost 0.005 → new = 0.905
- current = 1.0 → boost 0.0 → new = 1.0 (asymptotic ceiling)

**Rationale:**
- **5% of headroom:** Conservative enough to avoid over-confidence from single matches; aggressive enough to reward sustained accuracy
- **Asymptotic approach to 1.0:** Never exceeds original confidence during rebuild phase (Phase 29 behavior: confidence rebuilds gradually, never jumps)
- **No penalty for false positives:** FP signals are not explicitly penalized; they simply don't get boosted and decay naturally over time

---

## Data Flow

### Real-Time Signal Reinforcement

When a FeedbackNode is created or updated with `matched=true`:

```
feedback_recorded(pool, prediction_id, matched=true)
  ↓
fetch PredictionNode properties, extract:
  - sovereign_id
  - predicted_anomaly_type
  - evidence (list of contributing signal node IDs and types)
  ↓
for each contributing signal in evidence:
  - Fetch signal node (AnomalyChainNode | CorrelationPatternNode | RecoveryCorrelationNode)
  - current_confidence = node.properties.confidence
  - boost = (1.0 - current_confidence) * 0.05
  - new_confidence = current_confidence + boost
  - Update node.properties.confidence = new_confidence
  - Update node.properties.last_seen_at = now()
  - Upsert signal node (idempotent)
  ↓
Log: "Signal reinforced: {signal_type} {sovereign_id} confidence {current} → {new}"
```

### False Positive Handling

When `matched=false`:
- No reinforcement applied
- Signal nodes are NOT penalized
- They continue to decay naturally over time per Phase 29 rules

---

## Architecture: Two Implementation Modules

### 1. signal_reinforcement.rs (new module)

**Public interface:**
```rust
pub async fn reinforce_signals_for_feedback(
    pool: &PgPool,
    feedback_node_id: Uuid,
) -> Result<usize, sqlx::Error>
// Returns count of signal nodes reinforced
```

**Internal logic:**
- Query FeedbackNode by ID; check if matched=true
- If matched=false, return 0 (no reinforcement)
- If matched=true, fetch PredictionNode via FEEDBACK_FOR edge
- Extract evidence array from PredictionNode.signal_breakdown
- For each signal in evidence: apply boost formula, update node properties
- Return count of nodes updated

**Error handling:** Return sqlx::Error if database operations fail. Non-matched feedback returns 0 (not an error).

### 2. feedback_recorder.rs (MODIFY existing module)

**Current:** `record_feedback_for_anomaly()` creates FeedbackNode and edge.

**New:** After creating FeedbackNode, call:
```rust
if matched {
    reinforce_signals_for_feedback(pool, feedback_node_id).await?;
}
```

Non-blocking: reinforcement happens synchronously within the same transaction if possible, or immediately after.

---

## Evidence Extraction from PredictionNode

**Data model:** PredictionNode.signal_breakdown (extended in Phase 31) now contains:
```json
{
    "chain": f64,
    "correlation": f64,
    "recovery": f64,
    "raw_risk_score": f64,
    "accuracy_weight": f64,
    "adjusted_risk_score": f64,
    "accuracy_sample_count": i64 | null,
    "evidence": [
        {
            "signal_type": "AnomalyChainNode",
            "signal_id": "uuid",
            "confidence": f64
        },
        {
            "signal_type": "CorrelationPatternNode",
            "signal_id": "uuid",
            "confidence": f64
        }
    ]
}
```

The `evidence` array tracks which signals contributed to the prediction. Only signals in this list are reinforced when the prediction is validated.

---

## Data Model Changes

### PredictionNode signal_breakdown (MODIFIED in Phase 32)

Add `evidence` array to track contributing signal nodes:

```json
"evidence": [
    {
        "signal_type": "AnomalyChainNode" | "CorrelationPatternNode" | "RecoveryCorrelationNode",
        "signal_id": "uuid",
        "confidence": f64
    }
]
```

This is added during `run_forecast_once()` aggregation to record which signals were selected (max per type).

**No new entity types.** No schema migrations needed. Only JSON schema change to PredictionNode.properties.

---

## Testing Strategy (6 tests)

**File:** `crates/siss-graph-db/src/signal_reinforcement.rs` (tests 1–4), `feedback_recorder.rs` (tests 5–6)

| # | Test | Setup | Asserts |
|---|------|-------|---------|
| 1 | `test_reinforce_signals_boosts_confidence_5_percent_headroom` | Signal confidence=0.6, FeedbackNode matched=true | Confidence = 0.62 (boost 0.02); last_seen_at = now ±1s |
| 2 | `test_reinforce_signals_asymptotic_at_1_0` | Signal confidence=0.95, FeedbackNode matched=true | Confidence = 0.9975 (5% of 0.05 headroom); never exceeds 1.0 |
| 3 | `test_reinforce_signals_does_not_penalize_on_false_positive` | FeedbackNode matched=false | No update to signal; confidence unchanged |
| 4 | `test_reinforce_signals_updates_all_contributing_signals` | 3 signals in evidence (chain, corr, recovery), FeedbackNode matched=true | All 3 signals boosted; all 3 last_seen_at updated |
| 5 | `test_record_feedback_triggers_reinforcement_on_match` | AnomalyChainNode confidence=0.5, Prediction matched by anomaly | Signal confidence = 0.525 (0.5 + 0.05*(1-0.5)); integrated into feedback recording flow |
| 6 | `test_record_feedback_no_reinforcement_on_no_match` | No matching anomaly for prediction | No signal updates; feedback recorded with matched=false |

### Backward Compatibility

All existing Phase 28–31 tests must remain green. New fields in PredictionNode.signal_breakdown are additive (backward compatible).

---

## Edge Cases & Stability

### Signal Already at 1.0

If confidence=1.0, boost = 1.0 * 0.05 = 0.0. New confidence = 1.0. Idempotent and stable.

### Multiple Feedbacks for Same Signal

If the same prediction is validated multiple times (unlikely but possible), each validation applies the boost formula independently. Signal confidence asymptotically approaches 1.0 with repeated reinforcement.

### Signal Not Found in Evidence

If reinforce_signals_for_feedback() references a signal_id that no longer exists in graph_entities, treat as a no-op (log warning, continue). This prevents orphaned feedback from crashing reinforcement.

### Transaction Safety

Reinforce_signals_for_feedback() is called after FeedbackNode is committed. If reinforcement fails, feedback is already recorded (safe fallback: predictions continue with stale signal confidences until next cycle).

### Performance

Reinforcement is O(n) in signal count per prediction (typically 1-3 signals per PredictionNode). Per-sovereign, per-cycle cost is negligible. No bulk operations; fine-grained updates.

---

## Integration Points

**Phase 24 (Observability):** Anomaly detection unchanged. FeedbackNode creation calls `reinforce_signals_for_feedback()`.

**Phase 28-29 (Signals):** Signal nodes updated directly by reinforcement. Decay formula unchanged; reinforcement is orthogonal to decay.

**Phase 30 (Feedback Loop):** FeedbackNode creation point triggers reinforcement. No changes to feedback_recorder.rs API; new call is internal.

**Phase 31 (Weight Adjustment):** Uses accuracy metrics to adjust predictions; Phase 32 uses empirical outcomes to adjust signals. Complementary, not competitive.

---

## Non-Goals (Phase 32)

- No explicit penalization of false positives (rely on natural decay instead)
- No configurable boost percentage (5% is hardcoded)
- No signal cleanup (aged-out signals stay in DB; simply decay to floor)
- No REST/GraphQL endpoints for reinforcement metrics
- No multi-signal evidence aggregation (each signal boosted independently)
- No confidence ceiling above original (Phase 33+ may reset to original)

---

## Success Criteria

- [x] Signal reinforcement formula locked: `new_confidence = current_confidence + ((1.0 - current_confidence) * 0.05)`
- [x] Reinforce_signals_for_feedback() loads evidence and applies boost
- [x] Last_seen_at updated to now() on reinforced signals
- [x] All 6 new tests pass
- [x] All existing Phase 28-31 tests still pass
- [x] record_feedback_for_anomaly() calls reinforcement on matched=true
- [x] Backward compatibility: no breaking changes to existing APIs
- [x] cargo fmt and cargo clippy clean
- [x] No schema migrations needed
- [x] Commit with detailed message

---

## Timeline

Phase 32 closes the adaptive learning loop. Signals now dynamically adjust confidence based on prediction accuracy, creating a self-improving system where:
- Accurate patterns build confidence faster (reinforcement boost)
- Inaccurate patterns decay naturally (no boost, standard 7-day half-life)
- System becomes increasingly accurate over time through empirical feedback
