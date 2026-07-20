-- Phase 25: ReBAC Foundation — Relationship persistence
-- Migration 001: Create relationships and audit tables

CREATE TABLE IF NOT EXISTS relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_sovereign UUID NOT NULL,
    to_resource_type TEXT NOT NULL,
    to_resource_id UUID NOT NULL,
    relationship_type TEXT NOT NULL
        CHECK (relationship_type IN ('Owner', 'Operator', 'Observer', 'Delegate', 'Participant', 'Initiator')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    CONSTRAINT valid_expiry CHECK (expires_at IS NULL OR expires_at > created_at),
    CONSTRAINT not_revoked_and_expired CHECK (revoked_at IS NULL OR expires_at IS NULL OR revoked_at <= expires_at)
);

CREATE INDEX idx_relationships_from ON relationships(from_sovereign);
CREATE INDEX idx_relationships_expires ON relationships(expires_at);
CREATE INDEX idx_relationships_revoked ON relationships(revoked_at);
CREATE INDEX idx_relationships_resource ON relationships(to_resource_type, to_resource_id);

-- Audit log for relationship changes
CREATE TABLE IF NOT EXISTS relationship_audit (
    id BIGSERIAL PRIMARY KEY,
    relationship_id UUID REFERENCES relationships(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL CHECK (event_type IN ('created', 'revoked', 'expired')),
    event_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_relationship ON relationship_audit(relationship_id);
CREATE INDEX idx_audit_event ON relationship_audit(event_at);

-- Trigger to auto-log relationship creation
CREATE OR REPLACE FUNCTION log_relationship_event()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO relationship_audit (relationship_id, event_type)
    VALUES (NEW.id, 'created');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER rel_audit_insert
AFTER INSERT ON relationships
FOR EACH ROW
EXECUTE FUNCTION log_relationship_event();

-- Trigger to auto-log relationship revocation
CREATE OR REPLACE FUNCTION log_revocation()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.revoked_at IS NOT NULL AND OLD.revoked_at IS NULL THEN
        INSERT INTO relationship_audit (relationship_id, event_type)
        VALUES (NEW.id, 'revoked');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER rel_audit_revoke
AFTER UPDATE ON relationships
FOR EACH ROW
EXECUTE FUNCTION log_revocation();
