# Phase 30: Prediction Feedback Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement feedback recording and accuracy metrics aggregation to measure prediction performance and close the observability loop.

**Architecture:** Real-time feedback recording captures anomaly-prediction matches; periodic background aggregation computes precision/recall metrics per (sovereign, anomaly_type). Data model includes FeedbackNode (one per anomaly-prediction evaluation) and AccuracyMetricsNode (aggregated metrics).

**Tech Stack:** Rust, PostgreSQL, sqlx, tokio, testcontainers

---

## Task 1: Create migration 041 for feedback and metrics indexes

**Files:**
- Create: `crates/siss-graph-db/src/migrations/041_add_phase30_feedback_indexes.sql`
- Modify: `crates/siss-graph-db/src/migrations/mod.rs`

- [ ] **Step 1: Create migration file with all indexes**

Create `crates/siss-graph-db/src/migrations/041_add_phase30_feedback_indexes.sql`:

```sql
-- Phase 30: Feedback Node and Accuracy Metrics Node support

-- Create UNIQUE index for FeedbackNode idempotency
CREATE UNIQUE INDEX IF NOT EXISTS idx_feedback_prediction_node_id
    ON graph_entities ((properties->>'prediction_node_id')::uuid)
    WHERE label = 'FeedbackNode';

-- Query index for feedback by sovereign and creation time
CREATE INDEX IF NOT EXISTS idx_feedback_sovereign_created
    ON graph_entities (
        ((properties->>'sovereign_id')::uuid) ASC,
        ((properties->>'created_at')::timestamptz) DESC
    )
    WHERE label = 'FeedbackNode';

-- UNIQUE index for AccuracyMetricsNode per (sovereign, anomaly_type)
CREATE UNIQUE INDEX IF NOT EXISTS idx_metrics_sovereign_anomaly_type
    ON graph_entities (
        ((properties->>'sovereign_id')::uuid),
        (properties->>'anomaly_type')
    )
    WHERE label = 'AccuracyMetricsNode';

-- Query index for metrics by sovereign and update time
CREATE INDEX IF NOT EXISTS idx_metrics_sovereign_updated
    ON graph_entities (
        ((properties->>'sovereign_id')::uuid) ASC,
        ((properties->>'last_updated_at')::timestamptz) DESC
    )
    WHERE label = 'AccuracyMetricsNode';
```

- [ ] **Step 2: Register migration in mod.rs**

Modify `crates/siss-graph-db/src/migrations/mod.rs` to add the migration to the list:

```rust
pub async fn run_all(pool: &PgPool) -> Result<(), sqlx::migrate::MigrateError> {
    // ... existing migrations ...
    run_migration(pool, "040_add_phase28_prediction_indexes").await?;
    run_migration(pool, "041_add_phase30_feedback_indexes").await?;
    
    Ok(())
}
```

- [ ] **Step 3: Verify migration runs**

Run: `cargo test --lib migrations::tests` (or equivalent test that exercises migrations)
Expected: Migration 041 runs without error

- [ ] **Step 4: Commit**

```bash
git add crates/siss-graph-db/src/migrations/041_add_phase30_feedback_indexes.sql
git add crates/siss-graph-db/src/migrations/mod.rs
git commit -m "feat(phase30): add feedback and metrics indexes"
```

---

## Task 2: Create feedback_recorder.rs with failing tests

**Files:**
- Create: `crates/siss-graph-db/src/repo/feedback_recorder.rs`
- Test: Tests 1–4 embedded in the same file

- [ ] **Step 1: Write the 4 failing tests**

Create `crates/siss-graph-db/src/repo/feedback_recorder.rs` with test stubs:

```rust
use chrono::{DateTime, Utc};
use sqlx::PgPool;
use uuid::Uuid;

/// Represents an anomaly event to be evaluated against predictions.
#[derive(Debug, Clone)]
pub struct AnomalyEvent {
    pub sovereign_id: Uuid,
    pub anomaly_type: String,
    pub detected_at: DateTime<Utc>,
}

/// Record feedback for an anomaly by matching it against active predictions.
/// Returns Some(feedback_node_id) if feedback was created, None if no matching prediction found.
pub async fn record_feedback_for_anomaly(
    pool: &PgPool,
    anomaly: &AnomalyEvent,
) -> Result<Option<Uuid>, sqlx::Error> {
    todo!()
}

#[cfg(test)]
mod tests {
    use super::*;
    use testcontainers::runners::AsyncRunner;
    use testcontainers::{GenericImage, ImageExt, core::WaitFor};

    async fn setup_test_db() -> (testcontainers::ContainerAsync<GenericImage>, PgPool) {
        let container = GenericImage::new("postgres", "16")
            .with_wait_for(WaitFor::message_on_stderr(
                "database system is ready to accept connections",
            ))
            .with_env_var("POSTGRES_PASSWORD", "postgres")
            .with_env_var("POSTGRES_DB", "siss_test")
            .start()
            .await
            .expect("postgres started");

        let port = container.get_host_port_ipv4(5432).await.unwrap();
        let url = format!("postgres://postgres:postgres@127.0.0.1:{port}/siss_test");
        let pool = PgPool::connect(&url).await.expect("pool connect");
        crate::migrations::run_all(&pool).await.expect("migrations");
        (container, pool)
    }

    #[tokio::test]
    async fn test_record_feedback_exact_match() {
        let (_container, pool) = setup_test_db().await;
        let sovereign_id = Uuid::new_v4();
        
        // Create a PredictionNode with last_computed_at = now
        let now = Utc::now();
        let prediction = crate::repo::prediction_repo::PredictionRecord {
            sovereign_id,
            predicted_anomaly_type: "timeout_spam".to_string(),
            prediction_horizon_hours: 4,
            risk_score: 0.65,
            signal_breakdown: serde_json::json!({"chain": 0.6}),
            evidence: serde_json::json!({"top_chain_type": "dispute_spam→timeout_spam"}),
            last_computed_at: now,
        };
        let _pred_id = crate::repo::prediction_repo::upsert_prediction(&pool, &prediction)
            .await
            .expect("upsert prediction");
        
        // Create anomaly within 4h window with matching type
        let anomaly = AnomalyEvent {
            sovereign_id,
            anomaly_type: "timeout_spam".to_string(),
            detected_at: now + chrono::Duration::hours(2),
        };
        
        let feedback_id = record_feedback_for_anomaly(&pool, &anomaly)
            .await
            .expect("record feedback");
        
        assert!(feedback_id.is_some(), "Should create feedback for exact match");
        
        // Verify FeedbackNode was created with matched=true
        let result: (bool,) = sqlx::query_as(
            "SELECT (properties->>'matched')::boolean FROM graph_entities WHERE id = $1 AND label = 'FeedbackNode'",
        )
        .bind(feedback_id.unwrap())
        .fetch_one(&pool)
        .await
        .expect("query feedback");
        
        assert_eq!(result.0, true, "matched should be true");
    }

    #[tokio::test]
    async fn test_record_feedback_no_match() {
        let (_container, pool) = setup_test_db().await;
        let sovereign_id = Uuid::new_v4();
        
        let now = Utc::now();
        let prediction = crate::repo::prediction_repo::PredictionRecord {
            sovereign_id,
            predicted_anomaly_type: "timeout_spam".to_string(),
            prediction_horizon_hours: 4,
            risk_score: 0.65,
            signal_breakdown: serde_json::json!({"chain": 0.6}),
            evidence: serde_json::json!({"top_chain_type": "dispute_spam→timeout_spam"}),
            last_computed_at: now,
        };
        let _pred_id = crate::repo::prediction_repo::upsert_prediction(&pool, &prediction)
            .await
            .expect("upsert prediction");
        
        // Create anomaly with DIFFERENT type
        let anomaly = AnomalyEvent {
            sovereign_id,
            anomaly_type: "dispute_spam".to_string(),
            detected_at: now + chrono::Duration::hours(2),
        };
        
        let feedback_id = record_feedback_for_anomaly(&pool, &anomaly)
            .await
            .expect("record feedback");
        
        assert!(feedback_id.is_some(), "Should create feedback even with no match");
        
        let result: (bool,) = sqlx::query_as(
            "SELECT (properties->>'matched')::boolean FROM graph_entities WHERE id = $1 AND label = 'FeedbackNode'",
        )
        .bind(feedback_id.unwrap())
        .fetch_one(&pool)
        .await
        .expect("query feedback");
        
        assert_eq!(result.0, false, "matched should be false");
    }

    #[tokio::test]
    async fn test_record_feedback_outside_window() {
        let (_container, pool) = setup_test_db().await;
        let sovereign_id = Uuid::new_v4();
        
        let now = Utc::now();
        let prediction = crate::repo::prediction_repo::PredictionRecord {
            sovereign_id,
            predicted_anomaly_type: "timeout_spam".to_string(),
            prediction_horizon_hours: 4,
            risk_score: 0.65,
            signal_breakdown: serde_json::json!({"chain": 0.6}),
            evidence: serde_json::json!({"top_chain_type": "dispute_spam→timeout_spam"}),
            last_computed_at: now,
        };
        let _pred_id = crate::repo::prediction_repo::upsert_prediction(&pool, &prediction)
            .await
            .expect("upsert prediction");
        
        // Create anomaly OUTSIDE 4h window (5 hours after prediction)
        let anomaly = AnomalyEvent {
            sovereign_id,
            anomaly_type: "timeout_spam".to_string(),
            detected_at: now + chrono::Duration::hours(5),
        };
        
        let feedback_id = record_feedback_for_anomaly(&pool, &anomaly)
            .await
            .expect("record feedback");
        
        assert!(feedback_id.is_some(), "Should create feedback");
        
        let result: (bool,) = sqlx::query_as(
            "SELECT (properties->>'matched')::boolean FROM graph_entities WHERE id = $1 AND label = 'FeedbackNode'",
        )
        .bind(feedback_id.unwrap())
        .fetch_one(&pool)
        .await
        .expect("query feedback");
        
        assert_eq!(result.0, false, "matched should be false for outside window");
    }

    #[tokio::test]
    async fn test_record_feedback_idempotent() {
        let (_container, pool) = setup_test_db().await;
        let sovereign_id = Uuid::new_v4();
        
        let now = Utc::now();
        let prediction = crate::repo::prediction_repo::PredictionRecord {
            sovereign_id,
            predicted_anomaly_type: "timeout_spam".to_string(),
            prediction_horizon_hours: 4,
            risk_score: 0.65,
            signal_breakdown: serde_json::json!({"chain": 0.6}),
            evidence: serde_json::json!({"top_chain_type": "dispute_spam→timeout_spam"}),
            last_computed_at: now,
        };
        let _pred_id = crate::repo::prediction_repo::upsert_prediction(&pool, &prediction)
            .await
            .expect("upsert prediction");
        
        let anomaly = AnomalyEvent {
            sovereign_id,
            anomaly_type: "timeout_spam".to_string(),
            detected_at: now + chrono::Duration::hours(2),
        };
        
        // Record feedback twice
        let feedback_id_1 = record_feedback_for_anomaly(&pool, &anomaly)
            .await
            .expect("record feedback first");
        
        let feedback_id_2 = record_feedback_for_anomaly(&pool, &anomaly)
            .await
            .expect("record feedback second");
        
        // Should be the same UUID (idempotent)
        assert_eq!(feedback_id_1, feedback_id_2, "Should return same UUID on re-record");
        
        // Verify no duplicate FeedbackNodes were created
        let count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_entities WHERE label = 'FeedbackNode' AND properties->>'sovereign_id' = $1",
        )
        .bind(sovereign_id.to_string())
        .fetch_one(&pool)
        .await
        .expect("query count");
        
        assert_eq!(count.0, 1, "Should have exactly one FeedbackNode");
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cargo test --lib repo::feedback_recorder --` from `crates/siss-graph-db`
Expected: 4 tests fail with "not yet implemented" or "todo!()" errors

- [ ] **Step 3: Add module to repo/mod.rs (stub)**

Modify `crates/siss-graph-db/src/repo/mod.rs`:

```rust
pub mod feedback_recorder;
```

- [ ] **Step 4: Commit failing tests**

```bash
git add crates/siss-graph-db/src/repo/feedback_recorder.rs
git add crates/siss-graph-db/src/repo/mod.rs
git commit -m "test(phase30): add failing feedback recorder tests"
```

---

## Task 3: Implement record_feedback_for_anomaly()

**Files:**
- Modify: `crates/siss-graph-db/src/repo/feedback_recorder.rs`

- [ ] **Step 1: Implement record_feedback_for_anomaly()**

Replace the `todo!()` with the full implementation:

```rust
pub async fn record_feedback_for_anomaly(
    pool: &PgPool,
    anomaly: &AnomalyEvent,
) -> Result<Option<Uuid>, sqlx::Error> {
    // Query active PredictionNodes for this sovereign (last_computed_at > 24h ago)
    let cutoff = Utc::now() - chrono::Duration::hours(24);
    let predictions: Vec<(Uuid, String, f64, DateTime<Utc>)> = sqlx::query_as(
        "SELECT id, properties->>'predicted_anomaly_type', (properties->>'risk_score')::float, (properties->>'last_computed_at')::timestamptz
         FROM graph_entities
         WHERE label = 'PredictionNode' 
         AND properties->>'sovereign_id' = $1
         AND (properties->>'last_computed_at')::timestamptz > $2
         ORDER BY (properties->>'last_computed_at')::timestamptz DESC",
    )
    .bind(anomaly.sovereign_id.to_string())
    .bind(cutoff)
    .fetch_all(pool)
    .await?;

    // Try to find exact match
    let mut matched = false;
    let mut matched_prediction_id = None;
    let mut risk_score = 0.0;

    for (pred_id, predicted_type, score, last_computed_at) in predictions {
        // Check if anomaly type matches
        if anomaly.anomaly_type == predicted_type {
            // Check if detected_at falls within [last_computed_at, last_computed_at + 4h]
            let window_end = last_computed_at + chrono::Duration::hours(4);
            if anomaly.detected_at >= last_computed_at && anomaly.detected_at <= window_end {
                matched = true;
                matched_prediction_id = Some(pred_id);
                risk_score = score;
                break;
            }
        }
    }

    // If no matching prediction found, use first prediction (or none)
    if matched_prediction_id.is_none() && !predictions.is_empty() {
        matched_prediction_id = Some(predictions[0].0);
        risk_score = predictions[0].2;
    }

    // Create FeedbackNode if we have a prediction to evaluate
    if let Some(pred_id) = matched_prediction_id {
        let properties = serde_json::json!({
            "prediction_node_id": pred_id.to_string(),
            "sovereign_id": anomaly.sovereign_id.to_string(),
            "predicted_anomaly_type": anomaly.anomaly_type,
            "matched": matched,
            "anomaly_detected_at": if matched { Some(anomaly.detected_at.to_rfc3339()) } else { None },
            "prediction_risk_score": risk_score,
            "created_at": Utc::now().to_rfc3339(),
        });

        let feedback_id: Uuid = sqlx::query_scalar(
            "INSERT INTO graph_entities (label, properties, graph_id)
             VALUES ('FeedbackNode', $1, 0)
             ON CONFLICT ((properties->>'prediction_node_id')::uuid) WHERE label = 'FeedbackNode'
             DO UPDATE SET properties = EXCLUDED.properties, updated_at = NOW()
             RETURNING id",
        )
        .bind(properties)
        .fetch_one(pool)
        .await?;

        // Create FEEDBACK_FOR edge
        let _edge = sqlx::query(
            "INSERT INTO graph_relationships (source_id, target_id, rel_type, graph_id)
             VALUES ($1, $2, 'FEEDBACK_FOR', 0)
             ON CONFLICT (source_id, target_id, rel_type) DO NOTHING",
        )
        .bind(feedback_id)
        .bind(pred_id)
        .execute(pool)
        .await?;

        Ok(Some(feedback_id))
    } else {
        Ok(None)
    }
}
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cargo test --lib repo::feedback_recorder --` from `crates/siss-graph-db`
Expected: All 4 tests pass

- [ ] **Step 3: Commit implementation**

```bash
git add crates/siss-graph-db/src/repo/feedback_recorder.rs
git commit -m "feat(phase30): implement record_feedback_for_anomaly"
```

---

## Task 4: Create feedback_query.rs module

**Files:**
- Create: `crates/siss-graph-db/src/repo/feedback_query.rs`

- [ ] **Step 1: Write feedback_query.rs**

Create `crates/siss-graph-db/src/repo/feedback_query.rs`:

```rust
use chrono::{DateTime, Utc};
use sqlx::{FromRow, PgPool};
use uuid::Uuid;

/// A single feedback row for aggregation.
#[derive(Debug, Clone, FromRow)]
pub struct FeedbackRow {
    pub feedback_node_id: Uuid,
    pub prediction_node_id: Uuid,
    pub sovereign_id: Uuid,
    pub predicted_anomaly_type: String,
    pub matched: bool,
    pub prediction_risk_score: f64,
    pub created_at: DateTime<Utc>,
}

/// Fetch all unprocessed feedback created since a given timestamp.
pub async fn fetch_unprocessed_feedback(
    pool: &PgPool,
    since: DateTime<Utc>,
) -> Result<Vec<FeedbackRow>, sqlx::Error> {
    let rows = sqlx::query_as(
        "SELECT
            id AS feedback_node_id,
            (properties->>'prediction_node_id')::uuid AS prediction_node_id,
            (properties->>'sovereign_id')::uuid AS sovereign_id,
            properties->>'predicted_anomaly_type' AS predicted_anomaly_type,
            (properties->>'matched')::boolean AS matched,
            (properties->>'prediction_risk_score')::float AS prediction_risk_score,
            (properties->>'created_at')::timestamptz AS created_at
         FROM graph_entities
         WHERE label = 'FeedbackNode'
         AND (properties->>'created_at')::timestamptz > $1
         ORDER BY (properties->>'created_at')::timestamptz ASC",
    )
    .bind(since)
    .fetch_all(pool)
    .await?;

    Ok(rows)
}
```

- [ ] **Step 2: Register in repo/mod.rs**

Modify `crates/siss-graph-db/src/repo/mod.rs`:

```rust
pub mod feedback_query;
```

- [ ] **Step 3: Verify cargo check passes**

Run: `cargo check --lib` from `crates/siss-graph-db`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add crates/siss-graph-db/src/repo/feedback_query.rs
git add crates/siss-graph-db/src/repo/mod.rs
git commit -m "feat(phase30): add feedback_query module"
```

---

## Task 5: Create metrics_aggregator.rs with failing tests

**Files:**
- Create: `crates/siss-graph-db/src/metrics_aggregator.rs`

- [ ] **Step 1: Write the 4 failing tests**

Create `crates/siss-graph-db/src/metrics_aggregator.rs`:

```rust
use chrono::{DateTime, Duration, Utc};
use sqlx::PgPool;
use std::collections::HashMap;
use std::sync::Arc;
use tokio::task::JoinHandle;
use uuid::Uuid;

pub const DEFAULT_AGGREGATION_INTERVAL: Duration = Duration::hours(1);

/// Aggregate metrics once: compute precision/recall for all active (sovereign, anomaly_type) pairs.
pub async fn aggregate_metrics_once(pool: &PgPool) -> Result<usize, sqlx::Error> {
    todo!()
}

/// Start background ticker for periodic metric aggregation.
pub fn start_metrics_aggregator(pool: Arc<PgPool>, interval: Duration) -> JoinHandle<()> {
    tokio::spawn(async move {
        let mut interval = tokio::time::interval(std::time::Duration::from_secs(interval.num_seconds() as u64));
        loop {
            interval.tick().await;
            let _ = aggregate_metrics_once(&pool).await;
        }
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use testcontainers::runners::AsyncRunner;
    use testcontainers::{GenericImage, ImageExt, core::WaitFor};

    async fn setup_test_db() -> (testcontainers::ContainerAsync<GenericImage>, PgPool) {
        let container = GenericImage::new("postgres", "16")
            .with_wait_for(WaitFor::message_on_stderr(
                "database system is ready to accept connections",
            ))
            .with_env_var("POSTGRES_PASSWORD", "postgres")
            .with_env_var("POSTGRES_DB", "siss_test")
            .start()
            .await
            .expect("postgres started");

        let port = container.get_host_port_ipv4(5432).await.unwrap();
        let url = format!("postgres://postgres:postgres@127.0.0.1:{port}/siss_test");
        let pool = PgPool::connect(&url).await.expect("pool connect");
        crate::migrations::run_all(&pool).await.expect("migrations");
        (container, pool)
    }

    #[tokio::test]
    async fn test_metrics_precision_calculation() {
        let (_container, pool) = setup_test_db().await;
        let sovereign_id = Uuid::new_v4();
        
        // Create 2 FeedbackNodes: 1 matched (TP), 1 unmatched (FP)
        let props_tp = serde_json::json!({
            "prediction_node_id": Uuid::new_v4().to_string(),
            "sovereign_id": sovereign_id.to_string(),
            "predicted_anomaly_type": "timeout_spam",
            "matched": true,
            "anomaly_detected_at": Utc::now().to_rfc3339(),
            "prediction_risk_score": 0.6,
            "created_at": Utc::now().to_rfc3339(),
        });

        let props_fp = serde_json::json!({
            "prediction_node_id": Uuid::new_v4().to_string(),
            "sovereign_id": sovereign_id.to_string(),
            "predicted_anomaly_type": "timeout_spam",
            "matched": false,
            "anomaly_detected_at": serde_json::json!(null),
            "prediction_risk_score": 0.3,
            "created_at": Utc::now().to_rfc3339(),
        });

        sqlx::query("INSERT INTO graph_entities (label, properties, graph_id) VALUES ('FeedbackNode', $1, 0)")
            .bind(&props_tp)
            .execute(&pool)
            .await
            .expect("insert TP feedback");

        sqlx::query("INSERT INTO graph_entities (label, properties, graph_id) VALUES ('FeedbackNode', $1, 0)")
            .bind(&props_fp)
            .execute(&pool)
            .await
            .expect("insert FP feedback");

        // Run aggregation
        let count = aggregate_metrics_once(&pool).await.expect("aggregate");
        assert!(count > 0, "Should update at least one metrics node");

        // Verify AccuracyMetricsNode was created with correct precision
        let result: (f64, i64, i64) = sqlx::query_as(
            "SELECT (properties->>'precision')::float, (properties->>'true_positives')::int, (properties->>'false_positives')::int
             FROM graph_entities 
             WHERE label = 'AccuracyMetricsNode' 
             AND properties->>'sovereign_id' = $1
             AND properties->>'anomaly_type' = 'timeout_spam'",
        )
        .bind(sovereign_id.to_string())
        .fetch_one(&pool)
        .await
        .expect("query metrics");

        // precision = TP / (TP + FP) = 1 / 2 = 0.5
        assert_eq!(result.0, 0.5, "precision should be 0.5");
        assert_eq!(result.1, 1, "true_positives should be 1");
        assert_eq!(result.2, 1, "false_positives should be 1");
    }

    #[tokio::test]
    async fn test_metrics_recall_calculation() {
        let (_container, pool) = setup_test_db().await;
        let sovereign_id = Uuid::new_v4();
        
        // Create feedback: 1 TP
        let props = serde_json::json!({
            "prediction_node_id": Uuid::new_v4().to_string(),
            "sovereign_id": sovereign_id.to_string(),
            "predicted_anomaly_type": "timeout_spam",
            "matched": true,
            "anomaly_detected_at": Utc::now().to_rfc3339(),
            "prediction_risk_score": 0.6,
            "created_at": Utc::now().to_rfc3339(),
        });

        sqlx::query("INSERT INTO graph_entities (label, properties, graph_id) VALUES ('FeedbackNode', $1, 0)")
            .bind(&props)
            .execute(&pool)
            .await
            .expect("insert feedback");

        // Create AnomalyEventNode (1 FN: anomaly with no matching feedback)
        let anomaly_props = serde_json::json!({
            "sovereign_id": sovereign_id.to_string(),
            "anomaly_type": "timeout_spam",
            "detected_at": (Utc::now() - Duration::hours(1)).to_rfc3339(),
        });

        sqlx::query("INSERT INTO graph_entities (label, properties, graph_id) VALUES ('AnomalyEventNode', $1, 0)")
            .bind(&anomaly_props)
            .execute(&pool)
            .await
            .expect("insert anomaly");

        let count = aggregate_metrics_once(&pool).await.expect("aggregate");
        assert!(count > 0, "Should update metrics");

        // Verify recall
        let result: (f64, i64) = sqlx::query_as(
            "SELECT (properties->>'recall')::float, (properties->>'false_negatives')::int
             FROM graph_entities 
             WHERE label = 'AccuracyMetricsNode' 
             AND properties->>'sovereign_id' = $1",
        )
        .bind(sovereign_id.to_string())
        .fetch_one(&pool)
        .await
        .expect("query metrics");

        // recall = TP / (TP + FN) = 1 / 2 = 0.5
        assert_eq!(result.0, 0.5, "recall should be 0.5");
        assert_eq!(result.1, 1, "false_negatives should be 1");
    }

    #[tokio::test]
    async fn test_metrics_risk_score_weighting() {
        let (_container, pool) = setup_test_db().await;
        let sovereign_id = Uuid::new_v4();
        
        // Create matched feedback with risk_score 0.8
        let props_correct = serde_json::json!({
            "prediction_node_id": Uuid::new_v4().to_string(),
            "sovereign_id": sovereign_id.to_string(),
            "predicted_anomaly_type": "timeout_spam",
            "matched": true,
            "anomaly_detected_at": Utc::now().to_rfc3339(),
            "prediction_risk_score": 0.8,
            "created_at": Utc::now().to_rfc3339(),
        });

        // Create unmatched feedback with risk_score 0.2
        let props_incorrect = serde_json::json!({
            "prediction_node_id": Uuid::new_v4().to_string(),
            "sovereign_id": sovereign_id.to_string(),
            "predicted_anomaly_type": "timeout_spam",
            "matched": false,
            "anomaly_detected_at": serde_json::json!(null),
            "prediction_risk_score": 0.2,
            "created_at": Utc::now().to_rfc3339(),
        });

        sqlx::query("INSERT INTO graph_entities (label, properties, graph_id) VALUES ('FeedbackNode', $1, 0)")
            .bind(&props_correct)
            .execute(&pool)
            .await
            .expect("insert correct feedback");

        sqlx::query("INSERT INTO graph_entities (label, properties, graph_id) VALUES ('FeedbackNode', $1, 0)")
            .bind(&props_incorrect)
            .execute(&pool)
            .await
            .expect("insert incorrect feedback");

        aggregate_metrics_once(&pool).await.expect("aggregate");

        let result: (f64, f64) = sqlx::query_as(
            "SELECT (properties->>'avg_risk_score_correct')::float, (properties->>'avg_risk_score_incorrect')::float
             FROM graph_entities 
             WHERE label = 'AccuracyMetricsNode' 
             AND properties->>'sovereign_id' = $1",
        )
        .bind(sovereign_id.to_string())
        .fetch_one(&pool)
        .await
        .expect("query metrics");

        assert_eq!(result.0, 0.8, "avg_risk_score_correct should be 0.8");
        assert_eq!(result.1, 0.2, "avg_risk_score_incorrect should be 0.2");
    }

    #[tokio::test]
    async fn test_aggregation_periodic() {
        let (_container, pool) = setup_test_db().await;
        let pool = Arc::new(pool);
        
        // Start the background aggregator with a very short interval (100ms)
        let aggregator = start_metrics_aggregator(pool.clone(), Duration::milliseconds(100));

        // Give it a moment to run
        tokio::time::sleep(tokio::time::Duration::from_millis(150)).await;

        // Verify it's running (no panics)
        assert!(!aggregator.is_finished(), "Aggregator should still be running");

        // Clean up
        drop(aggregator);
    }
}
```

- [ ] **Step 2: Register in lib.rs**

Modify `crates/siss-graph-db/src/lib.rs`:

```rust
pub mod metrics_aggregator;
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cargo test --lib metrics_aggregator --` from `crates/siss-graph-db`
Expected: 4 tests fail with "not yet implemented"

- [ ] **Step 4: Commit failing tests**

```bash
git add crates/siss-graph-db/src/metrics_aggregator.rs
git add crates/siss-graph-db/src/lib.rs
git commit -m "test(phase30): add failing metrics aggregator tests"
```

---

## Task 6: Implement aggregate_metrics_once()

**Files:**
- Modify: `crates/siss-graph-db/src/metrics_aggregator.rs`

- [ ] **Step 1: Implement aggregate_metrics_once()**

Replace the `todo!()` in `aggregate_metrics_once()`:

```rust
pub async fn aggregate_metrics_once(pool: &PgPool) -> Result<usize, sqlx::Error> {
    // Query all unique (sovereign_id, anomaly_type) pairs from recent FeedbackNodes
    let pairs: Vec<(Uuid, String)> = sqlx::query_as(
        "SELECT DISTINCT (properties->>'sovereign_id')::uuid, properties->>'predicted_anomaly_type'
         FROM graph_entities
         WHERE label = 'FeedbackNode'",
    )
    .fetch_all(pool)
    .await?;

    let mut count = 0;

    for (sovereign_id, anomaly_type) in pairs {
        // Count TP: matched=true
        let tp_count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_entities
             WHERE label = 'FeedbackNode'
             AND properties->>'sovereign_id' = $1
             AND properties->>'predicted_anomaly_type' = $2
             AND (properties->>'matched')::boolean = true",
        )
        .bind(sovereign_id.to_string())
        .bind(&anomaly_type)
        .fetch_one(pool)
        .await?;

        // Count FP: matched=false
        let fp_count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_entities
             WHERE label = 'FeedbackNode'
             AND properties->>'sovereign_id' = $1
             AND properties->>'predicted_anomaly_type' = $2
             AND (properties->>'matched')::boolean = false",
        )
        .bind(sovereign_id.to_string())
        .bind(&anomaly_type)
        .fetch_one(pool)
        .await?;

        let tp = tp_count.0;
        let fp = fp_count.0;

        // Count FN: anomalies with no matching feedback
        let fn_count: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM graph_entities ae
             WHERE ae.label = 'AnomalyEventNode'
             AND ae.properties->>'sovereign_id' = $1
             AND ae.properties->>'anomaly_type' = $2
             AND NOT EXISTS (
               SELECT 1 FROM graph_entities f
               WHERE f.label = 'FeedbackNode'
               AND f.properties->>'sovereign_id' = $1
               AND f.properties->>'predicted_anomaly_type' = $2
               AND (f.properties->>'matched')::boolean = true
             )",
        )
        .bind(sovereign_id.to_string())
        .bind(&anomaly_type)
        .fetch_one(pool)
        .await?;

        let fn_count = fn_count.0;

        // Compute precision and recall
        let precision = if tp + fp > 0 {
            Some(tp as f64 / (tp + fp) as f64)
        } else {
            None
        };

        let recall = if tp + fn_count > 0 {
            Some(tp as f64 / (tp + fn_count) as f64)
        } else {
            None
        };

        // Compute average risk scores
        let avg_risk_correct: (Option<f64>,) = sqlx::query_as(
            "SELECT AVG((properties->>'prediction_risk_score')::float) FROM graph_entities
             WHERE label = 'FeedbackNode'
             AND properties->>'sovereign_id' = $1
             AND properties->>'predicted_anomaly_type' = $2
             AND (properties->>'matched')::boolean = true",
        )
        .bind(sovereign_id.to_string())
        .bind(&anomaly_type)
        .fetch_one(pool)
        .await?;

        let avg_risk_incorrect: (Option<f64>,) = sqlx::query_as(
            "SELECT AVG((properties->>'prediction_risk_score')::float) FROM graph_entities
             WHERE label = 'FeedbackNode'
             AND properties->>'sovereign_id' = $1
             AND properties->>'predicted_anomaly_type' = $2
             AND (properties->>'matched')::boolean = false",
        )
        .bind(sovereign_id.to_string())
        .bind(&anomaly_type)
        .fetch_one(pool)
        .await?;

        // Create/update AccuracyMetricsNode
        let properties = serde_json::json!({
            "sovereign_id": sovereign_id.to_string(),
            "anomaly_type": anomaly_type,
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn_count,
            "precision": precision,
            "recall": recall,
            "avg_risk_score_correct": avg_risk_correct.0,
            "avg_risk_score_incorrect": avg_risk_incorrect.0,
            "sample_count": tp + fp,
            "last_updated_at": Utc::now().to_rfc3339(),
        });

        sqlx::query(
            "INSERT INTO graph_entities (label, properties, graph_id)
             VALUES ('AccuracyMetricsNode', $1, 0)
             ON CONFLICT (
                (properties->>'sovereign_id')::uuid,
                (properties->>'anomaly_type')
             ) WHERE label = 'AccuracyMetricsNode'
             DO UPDATE SET properties = EXCLUDED.properties, updated_at = NOW()",
        )
        .bind(properties)
        .execute(pool)
        .await?;

        count += 1;
    }

    Ok(count)
}
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cargo test --lib metrics_aggregator --` from `crates/siss-graph-db`
Expected: All 4 tests pass

- [ ] **Step 3: Commit implementation**

```bash
git add crates/siss-graph-db/src/metrics_aggregator.rs
git commit -m "feat(phase30): implement aggregate_metrics_once"
```

---

## Task 7: Wire up observability anomaly handler to call record_feedback_for_anomaly

**Files:**
- Modify: `crates/siss-graph-db/src/observability/anomaly_watcher.rs` (or equivalent)

- [ ] **Step 1: Locate anomaly watcher**

Run: `grep -r "AnomalyEventNode" crates/siss-graph-db/src --include="*.rs" | grep -v test | head -5`
Expected: Find where anomalies are recorded

- [ ] **Step 2: Add call to record_feedback_for_anomaly()**

In the anomaly event handler, after creating AnomalyEventNode, add:

```rust
use crate::repo::feedback_recorder::{AnomalyEvent, record_feedback_for_anomaly};

// ... when anomaly is detected ...
let anomaly = AnomalyEvent {
    sovereign_id,
    anomaly_type: event.anomaly_type.clone(),
    detected_at: event.detected_at,
};
let _ = record_feedback_for_anomaly(pool, &anomaly).await;
```

- [ ] **Step 3: Verify cargo check passes**

Run: `cargo check --lib` from `crates/siss-graph-db`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add <anomaly_watcher_file>
git commit -m "feat(phase30): wire anomaly handler to feedback recorder"
```

---

## Task 8: Run full test suite and verify all Phase 30 tests pass

**Files:**
- No modifications

- [ ] **Step 1: Run all Phase 30 tests**

Run: `cargo test --lib repo::feedback_recorder metrics_aggregator` from `crates/siss-graph-db`
Expected: All 8 tests pass (4 feedback + 4 metrics)

- [ ] **Step 2: Run full test suite**

Run: `cargo test --lib` from `crates/siss-graph-db`
Expected: No regressions, all tests pass

- [ ] **Step 3: Format and lint**

Run in sequence:
```bash
cargo fmt --check
cargo clippy --all-targets --all-features
```
Expected: No format violations, no clippy warnings

- [ ] **Step 4: Commit any lint fixes (if needed)**

```bash
git add .
git commit -m "style(phase30): format and lint cleanup" || echo "No changes needed"
```

---

## Task 9: Final verification and commit summary

**Files:**
- No modifications (verification only)

- [ ] **Step 1: Verify migration applied**

Run: `cargo test --lib migrations::tests` from `crates/siss-graph-db` (if applicable)
Expected: Migration 041 runs without error

- [ ] **Step 2: List commits for this phase**

Run: `git log --oneline -10 | head`
Expected: See Phase 30 commits

- [ ] **Step 3: Verify no untracked files**

Run: `git status`
Expected: Clean working tree (or only expected untracked files)

- [ ] **Step 4: Summary output**

Print summary:
```
Phase 30: Prediction Feedback Loop — COMPLETE

Commits:
  - Migration 041: feedback and metrics indexes
  - feedback_recorder.rs: record_feedback_for_anomaly() with 4 tests
  - feedback_query.rs: fetch_unprocessed_feedback()
  - metrics_aggregator.rs: aggregate_metrics_once() + background ticker, 4 tests
  - Module wiring in repo/mod.rs and lib.rs
  - Observability integration (anomaly handler)
  - Full test suite: 8 new tests, 0 regressions
  - Format & lint: clean

Ready for merge to main.
```