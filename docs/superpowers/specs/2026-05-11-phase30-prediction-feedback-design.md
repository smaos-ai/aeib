# Phase 30: Prediction Feedback Loop — Design Specification

**Date:** 2026-05-11  
**Status:** Approved  
**Context:** Phases 25–29 built a complete prediction pipeline. Phase 30 adds measurement and closes the loop: recording how well predictions perform against reality, computing accuracy metrics, and laying groundwork for Phase 31+ to refine signal weights based on empirical data.

---

## Problem Statement

Phases 28–29 produce PredictionNodes with risk scores and predicted anomaly types. But without measuring accuracy, we have no way to know if predictions are calibrated correctly or if certain signal types are systematically wrong. Phase 30 solves this by:

1. **Recording:** When an AnomalyEventNode occurs, check if it matches any active prediction. Create a FeedbackNode capturing the outcome.
2. **Aggregating:** Periodically compute precision, recall, and confidence statistics per (sovereign, anomaly_type).
3. **Enabling refinement:** Phase 31+ will use these metrics to adjust signal weights in forecast_engine.

---

## Design Overview

### Matching Logic

**Exact match:** An anomaly matches a prediction if:
- Anomaly sovereignty matches prediction sovereignty
- Anomaly anomaly_type equals prediction predicted_anomaly_type
- Anomaly detected_at falls within [prediction last_computed_at, last_computed_at + 4 hours]

One prediction per sovereign. One active prediction → at most one matched anomaly per prediction.

### Data Model

#### FeedbackNode (new graph entity)

Records a single prediction-anomaly evaluation. One FeedbackNode per matched or missed prediction.

**Properties:**
| Property | Type | Semantics |
|---|---|---|
| prediction_node_id | UUID | FK to the PredictionNode being evaluated |
| sovereign_id | UUID | The sovereign (denormalized for query efficiency) |
| predicted_anomaly_type | String | What type we predicted |
| matched | Boolean | true = anomaly occurred within window; false = no match |
| anomaly_detected_at | DateTime | When anomaly occurred (null if matched=false) |
| prediction_risk_score | f64 | Risk score from PredictionNode (captured for later weighting) |
| created_at | DateTime | When feedback was recorded |

**Idempotency:** One FeedbackNode per PredictionNode per evaluation window. If re-running feedback logic for the same prediction, update existing FeedbackNode (idempotent via UNIQUE index on (prediction_node_id)).

#### AccuracyMetricsNode (new graph entity)

Aggregated metrics per (sovereign, anomaly_type) updated periodically.

**Properties:**
| Property | Type | Semantics |
|---|---|---|
| sovereign_id | UUID | The sovereign |
| anomaly_type | String | The anomaly type being evaluated |
| true_positives | i64 | Count of predictions that matched |
| false_positives | i64 | Count of predictions with no matching anomaly |
| false_negatives | i64 | Count of anomalies with no matching prediction |
| precision | f64 | TP / (TP + FP), or null if TP+FP=0 |
| recall | f64 | TP / (TP + FN), or null if TP+FN=0 |
| avg_risk_score_correct | f64 | Mean risk_score of matched predictions |
| avg_risk_score_incorrect | f64 | Mean risk_score of unmatched predictions |
| sample_count | i64 | Total predictions evaluated (TP + FP) |
| last_updated_at | DateTime | When this node was last aggregated |

**Idempotency:** One AccuracyMetricsNode per (sovereign, anomaly_type) pair. Upserted on each aggregation cycle.

#### FEEDBACK_FOR Edge (new relationship)

**Type:** FEEDBACK_FOR  
**Source:** FeedbackNode  
**Target:** PredictionNode  
**Semantics:** "This feedback evaluates that prediction"

Idempotent via existing (source, target, type) UNIQUE constraint.

### Data Flow

#### 1. Real-Time Feedback Recording

When an AnomalyEventNode is created (Phase 24 observability):

```
anomaly_event = {sovereign_id, anomaly_type, detected_at}
call record_feedback_for_anomaly(pool, anomaly_event)
  ↓
query PredictionNode for anomaly_event.sovereign_id
  ↓
for each active prediction (last_computed_at > now - 24h):
  if anomaly_type == predicted_anomaly_type 
     AND detected_at in [last_computed_at, last_computed_at + 4h]:
    matched = true
    break
  else:
    matched = false
  ↓
  create FeedbackNode {
    prediction_node_id,
    sovereign_id,
    predicted_anomaly_type,
    matched,
    anomaly_detected_at (or null),
    prediction_risk_score,
    created_at = now
  }
  ↓
  create FEEDBACK_FOR edge: FeedbackNode → PredictionNode
```

#### 2. Periodic Metric Aggregation

Background ticker (e.g., hourly):

```
for each (sovereign_id, anomaly_type) in active_predictions:
  feedback_rows = query FeedbackNode WHERE 
    sovereign_id = ?
    AND predicted_anomaly_type = ?
    AND created_at > last_metric_update_time
  
  tp = COUNT(*) WHERE matched = true
  fp = COUNT(*) WHERE matched = false
  fn = COUNT(DISTINCT anomaly FROM AnomalyEventNode)
        WHERE anomaly_type = ?
        AND detected_at > prediction_window
        AND NO FeedbackNode matched it
  
  precision = tp / (tp + fp) or null
  recall = tp / (tp + fn) or null
  avg_risk_correct = AVG(prediction_risk_score) WHERE matched = true
  avg_risk_incorrect = AVG(prediction_risk_score) WHERE matched = false
  
  upsert AccuracyMetricsNode {
    sovereign_id,
    anomaly_type,
    true_positives: tp,
    false_positives: fp,
    false_negatives: fn,
    precision,
    recall,
    avg_risk_score_correct,
    avg_risk_score_incorrect,
    sample_count: tp + fp,
    last_updated_at: now
  }
```

---

## Architecture: Three Implementation Modules

### 1. feedback_recorder.rs

**Public interface:**
```rust
pub async fn record_feedback_for_anomaly(
    pool: &PgPool,
    anomaly: &AnomalyEvent,  // sovereign_id, anomaly_type, detected_at
) -> Result<Option<Uuid>, sqlx::Error>
// Returns Some(feedback_node_id) if feedback was created, None if no matching prediction
```

**Internal logic:**
- Query active PredictionNodes for the sovereign
- Iterate through predictions in recency order (most recent first)
- On first exact match, create FeedbackNode with matched=true
- If no match found, create FeedbackNode with matched=false
- Create FEEDBACK_FOR edge
- Return feedback_node_id

**Error handling:** Return sqlx::Error if database operations fail. Anomalies without matching predictions are not errors (matched=false is valid).

### 2. feedback_query.rs

**Helper functions:**

```rust
pub struct FeedbackRow {
    pub feedback_node_id: Uuid,
    pub prediction_node_id: Uuid,
    pub sovereign_id: Uuid,
    pub predicted_anomaly_type: String,
    pub matched: bool,
    pub prediction_risk_score: f64,
    pub created_at: DateTime<Utc>,
}

pub async fn fetch_unprocessed_feedback(
    pool: &PgPool,
    since: DateTime<Utc>,  // Only feedback created after this time
) -> Result<Vec<FeedbackRow>, sqlx::Error>
```

Fetches FeedbackNodes created since last aggregation run. Used by metrics_aggregator to know what's new.

### 3. metrics_aggregator.rs

**Public interface:**
```rust
pub const DEFAULT_AGGREGATION_INTERVAL: Duration = Duration::from_secs(3600);  // 1 hour

pub async fn aggregate_metrics_once(pool: &PgPool) -> Result<usize, sqlx::Error>
// Returns count of AccuracyMetricsNodes created/updated

pub fn start_metrics_aggregator(pool: Arc<PgPool>, interval: Duration) -> JoinHandle<()>
// Background ticker, similar to forecast_engine::start_forecast_engine
```

**Logic:**
1. Query all (sovereign_id, anomaly_type) pairs from recent FeedbackNodes
2. For each pair, compute precision, recall, avg_risk_scores
3. Upsert AccuracyMetricsNode with aggregated values
4. Return count of metrics nodes updated

---

## Edge Cases & Stability

### No Matching Prediction

If an anomaly occurs but no active PredictionNode exists for that (sovereign, anomaly_type):
- Anomaly is still recorded in the database (AnomalyEventNode)
- record_feedback_for_anomaly returns None (no FeedbackNode created)
- Metrics aggregation counts this as false_negative (anomaly occurred, we didn't predict it)

### Prediction Expires

After 24 hours, a PredictionNode is considered "stale" and not queried for new matches. Anomalies occurring >24h after a prediction do not match it.

### Multiple Anomalies in Window

If two anomalies of the same type occur within one prediction's 4h window:
- First anomaly matches the prediction, creates FeedbackNode with matched=true
- Second anomaly does not create a new FeedbackNode (prediction already has feedback)
- No duplicate FeedbackNodes via UNIQUE index on (prediction_node_id)

### Stale Metrics

If a (sovereign, anomaly_type) pair hasn't been active for 7 days:
- Stop updating its AccuracyMetricsNode
- Keep existing metrics for Phase 31+ to inspect
- If new predictions resume, aggregation resumes

### Small Sample Sizes

Precision/recall are only meaningful with sufficient data. If sample_count < 5:
- Set precision/recall to null
- Still store mean risk scores and sample_count
- Phase 31+ will not use metrics to adjust weights until sample_count threshold is met

### False Negatives Computation

Computing false_negatives is more complex than TP/FP:
```
fn_count = anomalies in recent window WHERE:
  - anomaly_type matches
  - anomaly_detected_at is within [prediction_window_start, now]
  - NO FeedbackNode exists for this anomaly
```

This requires joining AnomalyEventNode with FeedbackNode to find uncovered anomalies.

---

## Testing Strategy (8 tests)

**File:** `crates/siss-graph-db/src/feedback_recorder.rs` (tests 1–4), `metrics_aggregator.rs` (tests 5–8)

| Test | Asserts |
|---|---|
| 1. test_record_feedback_exact_match | Anomaly within 4h window with matching type creates FeedbackNode with matched=true |
| 2. test_record_feedback_no_match | Anomaly with no matching prediction creates FeedbackNode with matched=false |
| 3. test_record_feedback_outside_window | Anomaly > 4h after prediction does not match |
| 4. test_record_feedback_idempotent | Re-running feedback logic for same anomaly doesn't create duplicate FeedbackNode |
| 5. test_metrics_precision_calculation | precision = TP / (TP+FP) computed correctly |
| 6. test_metrics_recall_calculation | recall = TP / (TP+FN) computed correctly from unmatched anomalies |
| 7. test_metrics_risk_score_weighting | avg_risk_score_correct and _incorrect computed separately |
| 8. test_aggregation_periodic | Background ticker runs and updates metrics at interval |

---

## Integration Points

**Phase 24 (Observability):** Observability watcher calls `record_feedback_for_anomaly(pool, anomaly)` when AnomalyEventNode is created. No changes to Phase 24; just a new function call at the right place.

**Phase 28-29 (Forecast):** No changes in Phase 30. Phase 31+ will modify forecast_engine.rs to query AccuracyMetricsNode and adjust signal weights.

**Database:** New migration needed to create FeedbackNode and AccuracyMetricsNode entity labels, plus UNIQUE indexes for idempotency.

---

## Non-Goals (Phase 30)

- No signal weight adjustment (Phase 31+)
- No REST/GraphQL endpoints for metrics (Phase 32+)
- No visualization (cockpit integration, Phase 32+)
- No ML-based threshold tuning (manual review of metrics)
- No multi-step prediction evaluation (only 4h horizon)
- No automated remediation based on low metrics (monitoring only)

---

## Success Criteria

- [x] FeedbackNode created for each anomaly-prediction evaluation
- [x] AccuracyMetricsNode computed periodically with precision/recall
- [x] Idempotency: re-running doesn't create duplicates
- [x] All 8 tests pass
- [x] cargo fmt and cargo clippy clean
- [x] No changes to Phase 24-29 behavior
- [x] Database migration for new entity types
