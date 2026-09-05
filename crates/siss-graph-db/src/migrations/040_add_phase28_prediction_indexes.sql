-- Migration 040: Phase 28 Predictive Anomaly Modeling
-- Purpose: Enable idempotent upsert of PredictionNode
--          Support risk-based queries for high-risk sovereigns

-- Idempotency index: unique per sovereign (one active prediction per sovereign)
CREATE UNIQUE INDEX IF NOT EXISTS idx_prediction_sovereign
    ON graph_entities ((properties->>'sovereign_id'))
    WHERE label = 'PredictionNode';

-- Query index: find sovereigns ordered by risk score (descending)
CREATE INDEX IF NOT EXISTS idx_prediction_risk_score
    ON graph_entities (((properties->>'risk_score')::float) DESC)
    WHERE label = 'PredictionNode';
