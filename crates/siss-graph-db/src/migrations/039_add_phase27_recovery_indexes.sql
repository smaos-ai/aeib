-- Migration 039: Phase 27 Anomaly → Recovery Correlation
-- Purpose: Enable idempotent upsert of RecoveryCorrelationNode
--          Support detection of anomalies that preceded recovery entries

-- Idempotency index: unique per (sovereign_id, anomaly_type) pair
CREATE UNIQUE INDEX IF NOT EXISTS idx_recovery_correlation_sovereign_anomaly_type
    ON graph_entities ((properties->>'sovereign_id'), (properties->>'anomaly_type'))
    WHERE label = 'RecoveryCorrelationNode';

-- Query index: find correlations for a sovereign ordered by recency
CREATE INDEX IF NOT EXISTS idx_recovery_correlation_sovereign
    ON graph_entities ((properties->>'sovereign_id'), created_at DESC)
    WHERE label = 'RecoveryCorrelationNode';
