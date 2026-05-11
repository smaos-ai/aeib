-- Migration 032: SMAOS Intelligence Graph Layer (Phase S1)
-- Purpose: Initialize Apache AGE graph schema for entity/relationship tracking
-- Enables decision lineage, explainability, and blast-radius propagation
-- Every Phase 20 state transition writes to both DB tables AND this graph

-- Create AGE graph if not exists
SELECT create_graph('smaos_graph');

-- Node labels (entities in the intelligence graph)
-- These are not explicit tables but logical node types in the AGE graph

-- Create property indexes for efficient traversal
CREATE TABLE IF NOT EXISTS graph_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    graph_id BIGINT NOT NULL,
    label VARCHAR(32) NOT NULL,
    properties JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Edge/relationship log for audit trail
CREATE TABLE IF NOT EXISTS graph_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_entity_id UUID NOT NULL REFERENCES graph_entities(id),
    target_entity_id UUID NOT NULL REFERENCES graph_entities(id),
    relationship_type VARCHAR(32) NOT NULL,
    confidence NUMERIC(3,2) NOT NULL DEFAULT 1.0,
    evidence JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for fast traversal
CREATE INDEX idx_entities_label ON graph_entities(label, created_at DESC);
CREATE INDEX idx_relationships_source ON graph_relationships(source_entity_id);
CREATE INDEX idx_relationships_target ON graph_relationships(target_entity_id);
CREATE INDEX idx_relationships_type ON graph_relationships(relationship_type);

-- Node type constants (logical, not enforced by schema)
-- SovereignNode: identity of a sovereign in recovery/probation
-- RecoveryNode: a recovery lifecycle event
-- ViolationNode: a violation that triggered re-quarantine
-- ScoringNode: a score computation decision
-- TransitionNode: a state machine transition
-- SignalNode: a slash, anomaly, or settlement signal

-- Edge type constants (logical)
-- TRIGGERS: recovery_node TRIGGERS -> violation_node (recovery triggered a violation)
-- SCORES: recovery_node SCORES -> scoring_node (recovery produced a score)
-- EXPLAINS: scoring_node EXPLAINS -> signal_node (score explained by signals)
-- SUPERSEDES: new_entity SUPERSEDES -> old_entity (decision overrides prior)
-- DEPENDS_ON: recovery_node DEPENDS_ON -> sovereign_node (recovery belongs to sovereign)
