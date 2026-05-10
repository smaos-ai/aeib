-- Phase 6: Delegation Chains — Delegation Edges Table
-- Stores explicit delegation relationships between personas (DELEGATES_TO edges)

CREATE TABLE delegation_edges (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_persona_id UUID NOT NULL REFERENCES personas(id),
    target_persona_id UUID NOT NULL REFERENCES personas(id),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    ceiling_delegations JSONB NOT NULL,
    ceiling_constraints JSONB NOT NULL,
    delegated_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for fast delegation graph traversal
CREATE INDEX idx_delegation_edges_source ON delegation_edges(source_persona_id);
CREATE INDEX idx_delegation_edges_target ON delegation_edges(target_persona_id);
CREATE INDEX idx_delegation_edges_tenant ON delegation_edges(tenant_id);

-- Constraint: Prevent self-delegation
ALTER TABLE delegation_edges
  ADD CONSTRAINT check_no_self_delegation CHECK (source_persona_id != target_persona_id);

-- NOTE: Tenant consistency is enforced at application layer, not via CHECK constraints
-- (PostgreSQL CHECK constraints cannot use subqueries)

-- Constraint: Prevent duplicate delegation edges (one active delegation per source-target pair)
CREATE UNIQUE INDEX idx_delegation_edges_unique ON delegation_edges(source_persona_id, target_persona_id) WHERE delegated_at IS NOT NULL;
