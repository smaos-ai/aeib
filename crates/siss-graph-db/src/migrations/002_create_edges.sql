-- SISS Knowledge Graph: Unified Edges Table

CREATE TYPE edge_type AS ENUM (
    -- Identity & Governance
    'member_of', 'acts_as', 'belongs_to',
    -- Access Control
    'can_read', 'can_write', 'can_execute',
    'deny_read', 'deny_write', 'deny_execute',
    -- AP2
    'authorized_by', 'receipted_by',
    -- Execution
    'initiated_by', 'governed_by', 'produced',
    'scoped_to', 'contains', 'loaded',
    -- Governance
    'enforces', 'violated_by', 'authored_by',
    -- Cognitive
    'depends_on', 'uses', 'supports', 'extends',
    'contradicts', 'supersedes',
    -- Swarm
    'a2a_delegates'
);

CREATE TABLE edges (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID NOT NULL,
    target_id UUID NOT NULL,
    edge_type edge_type NOT NULL,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_edges_source ON edges(source_id);
CREATE INDEX idx_edges_target ON edges(target_id);
CREATE INDEX idx_edges_type ON edges(edge_type);
CREATE INDEX idx_edges_tenant ON edges(tenant_id);
CREATE INDEX idx_edges_source_type ON edges(source_id, edge_type);
CREATE INDEX idx_edges_target_type ON edges(target_id, edge_type);
