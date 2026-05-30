-- Phase 25 Wave 1: ReBAC Foundation
-- PostgreSQL schema for relationship-based access control (ReBAC)

-- Core relationships table
CREATE TABLE relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_sovereign UUID NOT NULL,
    to_resource_type TEXT NOT NULL,
    to_resource_id UUID NOT NULL,
    relationship_type TEXT NOT NULL CHECK (relationship_type IN ('Owner', 'Operator', 'Observer', 'Delegate', 'Participant', 'Initiator')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    UNIQUE (from_sovereign, to_resource_type, to_resource_id, relationship_type)
);

-- Audit log for relationship lifecycle events
CREATE TABLE relationship_audit (
    id BIGSERIAL PRIMARY KEY,
    relationship_id UUID REFERENCES relationships(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL CHECK (event_type IN ('created', 'revoked', 'expired')),
    event_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    audit_metadata JSONB
);

-- Indexes for performance
CREATE INDEX idx_relationships_from ON relationships(from_sovereign);
CREATE INDEX idx_relationships_expires ON relationships(expires_at);
CREATE INDEX idx_relationships_revoked ON relationships(revoked_at);
CREATE INDEX idx_relationships_resource ON relationships(to_resource_type, to_resource_id);
CREATE INDEX idx_relationship_audit_rel ON relationship_audit(relationship_id);
CREATE INDEX idx_relationship_audit_event_at ON relationship_audit(event_at);
