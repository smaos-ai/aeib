-- Migration 041: Phase 30 Feedback and Accuracy Metrics Nodes
-- Purpose: Enable FeedbackNode idempotency and efficient queries
--          Support AccuracyMetricsNode per-sovereign upsert and aggregation

-- UNIQUE index for FeedbackNode idempotency (one feedback per prediction)
CREATE UNIQUE INDEX IF NOT EXISTS idx_feedback_prediction_node_id
    ON graph_entities ((properties->>'prediction_node_id'))
    WHERE label = 'FeedbackNode';

-- Query index for feedback by sovereign and creation time
CREATE INDEX IF NOT EXISTS idx_feedback_sovereign_created
    ON graph_entities (
        (properties->>'sovereign_id') ASC,
        (created_at) DESC
    )
    WHERE label = 'FeedbackNode';

-- UNIQUE index for AccuracyMetricsNode per (sovereign, anomaly_type)
CREATE UNIQUE INDEX IF NOT EXISTS idx_metrics_sovereign_anomaly_type
    ON graph_entities (
        (properties->>'sovereign_id'),
        (properties->>'anomaly_type')
    )
    WHERE label = 'AccuracyMetricsNode';

-- Query index for metrics by sovereign and update time
CREATE INDEX IF NOT EXISTS idx_metrics_sovereign_updated
    ON graph_entities (
        (properties->>'sovereign_id') ASC,
        (created_at) DESC
    )
    WHERE label = 'AccuracyMetricsNode';
