-- Migration 037: Phase 25 Causal Pattern Extraction Engine
-- Purpose: Enable idempotent upsert of CorrelationPatternNode
--          Support causal pattern detection and aggregation

-- Idempotency index: unique per (sovereign_id, pattern_type) pair
CREATE UNIQUE INDEX IF NOT EXISTS idx_correlation_pattern_sovereign_type
    ON graph_entities ((properties->>'sovereign_id'), (properties->>'pattern_type'))
    WHERE label = 'CorrelationPatternNode';

-- Query index: find patterns for a sovereign ordered by recency
CREATE INDEX IF NOT EXISTS idx_correlation_pattern_sovereign
    ON graph_entities ((properties->>'sovereign_id'), created_at DESC)
    WHERE label = 'CorrelationPatternNode';
