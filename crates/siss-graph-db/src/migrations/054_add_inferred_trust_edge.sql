-- Migration 054: INFERRED_TRUST Edge Type and Bilateral Renegotiation
-- Purpose: Add INFERRED_TRUST relationship type to graph_relationships for transitive trust inference
--          Enables bilateral upgrade trigger when inferred confidence meets threshold

-- Create index on INFERRED_TRUST relationships for efficient lookup
CREATE INDEX IF NOT EXISTS idx_graph_rel_inferred_trust
    ON graph_relationships (source_entity_id, target_entity_id)
    WHERE relationship_type = 'INFERRED_TRUST';

-- Create composite index for bilateral upgrade queries
CREATE INDEX IF NOT EXISTS idx_graph_rel_inferred_confidence
    ON graph_relationships (source_entity_id, target_entity_id, confidence DESC)
    WHERE relationship_type = 'INFERRED_TRUST';
