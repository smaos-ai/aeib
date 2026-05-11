-- Migration 038: Phase 26 Anomaly Chain Detection
-- Purpose: Enable idempotent upsert of AnomalyChainNode
--          Support detection of temporal anomaly sequences (dispute_spam → timeout_spam, etc.)

-- Idempotency index: unique per (sovereign_id, chain_type) pair
CREATE UNIQUE INDEX IF NOT EXISTS idx_anomaly_chain_sovereign_type
    ON graph_entities ((properties->>'sovereign_id'), (properties->>'chain_type'))
    WHERE label = 'AnomalyChainNode';

-- Query index: find chains for a sovereign ordered by recency
CREATE INDEX IF NOT EXISTS idx_anomaly_chain_sovereign
    ON graph_entities ((properties->>'sovereign_id'), created_at DESC)
    WHERE label = 'AnomalyChainNode';
