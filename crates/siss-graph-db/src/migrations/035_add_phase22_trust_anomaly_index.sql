-- Migration 035: Phase 22b Trust Anomaly Graph Indexes
-- Purpose: Enable idempotent upsert of TrustAnomalyPatternNode by source_id
--          Enable idempotent EXHIBITS edge by (source, target, type)
--          Fix graph_id column for non-AGE relational writes

-- Fix graph_id column to allow sentinel value for non-AGE writes
ALTER TABLE graph_entities ALTER COLUMN graph_id SET DEFAULT 0;

-- Partial unique index: one TrustAnomalyPatternNode per source sovereign
CREATE UNIQUE INDEX IF NOT EXISTS idx_trust_anomaly_pattern_source_id
    ON graph_entities ((properties->>'source_id'))
    WHERE label = 'TrustAnomalyPatternNode';

-- Unique index: prevent duplicate EXHIBITS edges
CREATE UNIQUE INDEX IF NOT EXISTS idx_graph_rel_src_tgt_type
    ON graph_relationships (source_entity_id, target_entity_id, relationship_type);
