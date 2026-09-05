# Phase 34: Feedback-Driven Anomaly Refinement — Delta-Only Spec

**Status:** DESIGN (2026-05-12)  
**Tests:** 0/9 pending  
**Implementation:** Ready for build sequence

---

## Overview

Phase 34 augments Phase 30's feedback loop with **anomaly type confidence scoring** and **misclassification detection**. Given precision/recall metrics from Phase 30, Phase 34 identifies which anomaly types are frequently misclassified, flags anomalies with low confidence, and exposes a confidence score to projection queries and downstream systems.

**Key insight:** Feedback alone is data; actionable feedback requires confidence. When precision for `timeout_spam` drops to 60% (Phase 30 metric), Phase 34 marks historical timeout_spam detections as "low confidence" and surfaces this uncertainty to operators and projections.

---

## Delta Summary

**Adds:**
- `AnomalyConfidenceScore` entity (tracks confidence by anomaly_type per sovereign)
- `anomaly_confidence` float column in phase 30's AnomalyEventNode
- `feedback_refinement_task` background extractor (refines confidence every 2 minutes)
- REST endpoint: `GET /api/graph/anomalies/:anomaly_id/confidence`
- Tests: 9 covering confidence computation, edge cases, idempotency

**Modifies:**
- `siss-graph-db/src/repo/anomaly_repo.rs` — add fetch_anomaly_with_confidence()
- `siss-graph-db/src/metrics_aggregator.rs` — track misclassification rates
- Migration 042 — add confidence index on AnomalyEventNode

**Removes:** Nothing

---

## Intelligence Graph Schema

### New Entity Label: `AnomalyConfidenceScore`

Aggregates confidence by anomaly type and sovereign, derived from Phase 30 feedback metrics.

| Property | Type | Phase 34 Notes |
|----------|------|---|
| `sovereign_id` | UUID | Sovereign this score applies to |
| `anomaly_type` | VARCHAR(32) | One of: dispute_spam, timeout_spam, revocation_pattern |
| `confidence_score` | FLOAT | 0.0–1.0, derived from precision; formula: `min(1.0, precision * (1 - false_positive_rate))` |
| `sample_count` | BIGINT | Feedback events used to compute this score (Phase 30) |
| `precision_last_30d` | FLOAT | Precision over past 30 days (from Phase 30 metrics) |
| `false_positive_rate` | FLOAT | 1.0 - precision |
| `computed_at` | TIMESTAMPTZ | When this score was last updated |

**Idempotency index (migration 042):**
```sql
CREATE UNIQUE INDEX idx_anomaly_confidence_sovereign_type
    ON graph_entities ((properties->>'sovereign_id'), (properties->>'anomaly_type'))
    WHERE label = 'AnomalyConfidenceScore';
```

### Modified Entity: AnomalyEventNode (from Phase 23)

Add computed field at ingestion time:

| Property (NEW) | Type | Phase 34 Notes |
|---|---|---|
| `confidence_at_detection` | FLOAT | Confidence score for this anomaly_type at time of detection (populated by Phase 34 refinement task) |

**Index (migration 042):**
```sql
CREATE INDEX idx_anomaly_confidence_score
    ON graph_entities ((properties->>'confidence_at_detection'))
    WHERE label = 'AnomalyEventNode';
```

### New Relationship: EXHIBITS_CONFIDENCE

From AnomalyConfidenceScore to AnomalyEventNode (for audit trail).

---

## Rust Data Model

### `AnomalyConfidenceScoreRecord`

```rust
pub struct AnomalyConfidenceScoreRecord {
    pub sovereign_id: Uuid,
    pub anomaly_type: String,           // "dispute_spam", etc.
    pub confidence_score: f64,           // min(1.0, precision * (1 - fpr))
    pub sample_count: i64,
    pub precision_last_30d: f64,
    pub false_positive_rate: f64,        // 1.0 - precision
    pub computed_at: DateTime<Utc>,
}
```

### Computation Function

```rust
pub(crate) async fn compute_confidence_score(
    pool: &PgPool,
    sovereign_id: Uuid,
    anomaly_type: &str,
) -> Result<Option<AnomalyConfidenceScoreRecord>, sqlx::Error>
```

Reads from Phase 30's `prediction_feedback` table:
1. Count true positives: feedback.is_correct = true
2. Count false positives: feedback.is_correct = false
3. Compute precision = tp / (tp + fp)
4. Compute confidence = min(1.0, precision * (1 - fpr))
5. Upsert AnomalyConfidenceScore entity

---

## Misclassification Detection

### Threshold Logic

When `confidence_score < 0.65` for an anomaly_type:
1. Flag as "low confidence"
2. Log operator alert (fire-and-forget)
3. Mark all AnomalyEventNode(type) from past 7 days with `confidence_at_detection < 0.65`

### Backfill Strategy

On Phase 34 boot, backfill all AnomalyEventNode entities with current confidence scores (snapshot-in-time).

---

## Background Extractor

### Function Signature

```rust
pub async fn refine_anomaly_confidence_once(
    pool: &PgPool,
) -> Result<usize, sqlx::Error>
```

Returns count of AnomalyConfidenceScore entities created/updated.

### Ticker Loop

```rust
pub fn start_feedback_refinement_task(
    pool: Arc<PgPool>,
    interval: Duration,  // default: 120 seconds
) -> JoinHandle<()>
```

- No boot lookback (runs on all sovereigns every cycle)
- Poll interval: 120 seconds (configurable)
- Error handling: fire-and-forget
- Pattern: Similar to Phase 25 causal_extractor

---

## REST Endpoint

### GET /api/graph/anomalies/:anomaly_id/confidence

**Response:**
```json
{
    "anomaly_id": "<uuid>",
    "anomaly_type": "dispute_spam",
    "sovereign_id": "<uuid>",
    "detected_at": "2026-05-12T10:30:00Z",
    "confidence_at_detection": 0.82,
    "confidence_score_current": 0.79,
    "precision_last_30d": 0.79,
    "false_positive_rate": 0.21,
    "sample_count": 142,
    "trend": "declining"  // "stable", "improving", "declining"
}
```

---

## Test Coverage

**Location:** `crates/siss-graph-db/src/repo/anomaly_confidence_repo.rs` (tests module)

| # | Test | Coverage |
|---|------|----------|
| 1 | `test_compute_confidence_score_from_feedback` | Precision formula applied correctly |
| 2 | `test_confidence_score_accounts_for_false_positives` | FPR reduces confidence correctly |
| 3 | `test_confidence_clamped_at_1_0` | min(1.0, score) enforced |
| 4 | `test_upsert_anomaly_confidence_creates_entity` | Entity created in graph |
| 5 | `test_upsert_anomaly_confidence_idempotent` | Same (sovereign_id, anomaly_type) → same UUID |
| 6 | `test_low_confidence_flag_when_precision_below_threshold` | Confidence < 0.65 marked |
| 7 | `test_backfill_anomaly_events_with_confidence_at_detection` | Historical events get scored |
| 8 | `test_refine_confidence_once_updates_all_sovereigns` | Extractor runs on all sovereigns |
| 9 | `test_confidence_trend_detection_declining_improving_stable` | Trend computation correct |

**All 9 tests:** Pending (TBD)

---

## Migration 042

**File:** `crates/siss-graph-db/src/migrations/042_add_phase34_confidence_indexes.sql`

```sql
-- AnomalyConfidenceScore indexes
CREATE UNIQUE INDEX IF NOT EXISTS idx_anomaly_confidence_sovereign_type
    ON graph_entities ((properties->>'sovereign_id'), (properties->>'anomaly_type'))
    WHERE label = 'AnomalyConfidenceScore';

CREATE INDEX IF NOT EXISTS idx_anomaly_confidence_score
    ON graph_entities ((properties->>'confidence_score') DESC)
    WHERE label = 'AnomalyConfidenceScore';

-- AnomalyEventNode confidence field index
CREATE INDEX IF NOT EXISTS idx_anomaly_event_confidence
    ON graph_entities ((properties->>'confidence_at_detection'))
    WHERE label = 'AnomalyEventNode';

-- Trend query: anomaly types by confidence over time
CREATE INDEX IF NOT EXISTS idx_anomaly_event_type_time
    ON graph_entities ((properties->>'anomaly_type'), created_at DESC)
    WHERE label = 'AnomalyEventNode';
```

---

## Integration with Phase 30

### Reads from Phase 30

Phase 34 **reads** from Phase 30's tables:
- `prediction_feedback` — for precision/recall metrics
- Computes confidence = precision * (1 - false_positive_rate)

### Writes to Graph

- **AnomalyConfidenceScore:** Aggregate entity per (sovereign_id, anomaly_type)
- **EXHIBITS_CONFIDENCE:** From AnomalyConfidenceScore to AnomalyEventNode

### Query Patterns

Example: "What's the confidence of this anomaly?"
```sql
SELECT
    properties->>'anomaly_type',
    properties->>'confidence_at_detection',
    properties->>'detected_at'
FROM graph_entities
WHERE id = '<anomaly_event_id>';
```

Example: "List low-confidence anomaly types for this sovereign"
```sql
SELECT
    properties->>'anomaly_type',
    properties->>'confidence_score',
    properties->>'precision_last_30d'
FROM graph_entities
WHERE label = 'AnomalyConfidenceScore'
    AND (properties->>'sovereign_id') = '<sovereign_uuid>'
    AND (properties->>'confidence_score')::float < 0.65
ORDER BY (properties->>'confidence_score')::float ASC;
```

---

## Non-Goals (Phase 34)

- **No model retraining** — Confidence is purely derived from precision; no Bayesian update
- **No threshold API** — 0.65 threshold is a code constant; requires recompile to adjust
- **No per-sovereign feedback weighting** — All feedback weighted equally
- **No temporal decay** — 30-day window is fixed; older feedback has same weight
- **No anomaly reclassification** — Low confidence doesn't change anomaly_type; only flags uncertainty
- **No REST projection integration** — Confidence exposed via separate endpoint, not folded into Phase 31-33 projections yet

---

## Phase 35+ Vision

**Adaptive Anomaly Classification:**
- Use Phase 34 confidence scores to trigger re-analysis of low-confidence anomalies
- Optional: feed confidence into Phase 25 causal extraction (weight edges by confidence)

**Projection Integration:**
- Fold Phase 34 confidence into Phase 31-33 projections
- Example: "Root cause chain filtered to high-confidence anomalies only"

**Model Feedback Loop Closure:**
- Confidence scores → operator feedback → Phase 30 metrics → Phase 34 refinement (closed loop)

---

**Last Updated:** 2026-05-12 | **By:** Claude Haiku 4.5
