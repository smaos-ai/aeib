-- Phase 25: AP2 Policy Engine — Sovereign attribute persistence
-- Migration 002: Create sovereign attributes and AP2 policy tables

CREATE TABLE IF NOT EXISTS sovereign_attributes (
    sovereign_id UUID PRIMARY KEY,
    trust_level SMALLINT NOT NULL CHECK (trust_level >= 0 AND trust_level <= 100),
    reputation_score INT NOT NULL,
    joined_at TIMESTAMPTZ NOT NULL,
    blacklisted BOOLEAN NOT NULL DEFAULT FALSE,
    certifications TEXT[] DEFAULT '{}',
    organization TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_attributes_blacklist ON sovereign_attributes(blacklisted) WHERE blacklisted = true;
CREATE INDEX idx_attributes_trust ON sovereign_attributes(trust_level);
CREATE INDEX idx_attributes_joined ON sovereign_attributes(joined_at);
CREATE INDEX idx_attributes_updated ON sovereign_attributes(updated_at);

-- Audit log for attribute changes
CREATE TABLE IF NOT EXISTS attribute_audit (
    id BIGSERIAL PRIMARY KEY,
    sovereign_id UUID NOT NULL REFERENCES sovereign_attributes(sovereign_id) ON DELETE CASCADE,
    event_type TEXT NOT NULL CHECK (event_type IN ('created', 'updated', 'blacklisted', 'cleared')),
    old_trust_level SMALLINT,
    new_trust_level SMALLINT,
    old_reputation INT,
    new_reputation INT,
    old_blacklisted BOOLEAN,
    new_blacklisted BOOLEAN,
    event_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_attribute_audit_sovereign ON attribute_audit(sovereign_id);
CREATE INDEX idx_attribute_audit_event ON attribute_audit(event_at);
CREATE INDEX idx_attribute_audit_type ON attribute_audit(event_type);

-- Trigger to auto-log attribute creation
CREATE OR REPLACE FUNCTION log_attribute_event()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO attribute_audit (
        sovereign_id,
        event_type,
        new_trust_level,
        new_reputation,
        new_blacklisted
    ) VALUES (
        NEW.sovereign_id,
        'created',
        NEW.trust_level,
        NEW.reputation_score,
        NEW.blacklisted
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER attr_audit_insert
AFTER INSERT ON sovereign_attributes
FOR EACH ROW
EXECUTE FUNCTION log_attribute_event();

-- Trigger to auto-log attribute updates
CREATE OR REPLACE FUNCTION log_attribute_update()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO attribute_audit (
        sovereign_id,
        event_type,
        old_trust_level,
        new_trust_level,
        old_reputation,
        new_reputation,
        old_blacklisted,
        new_blacklisted
    ) VALUES (
        NEW.sovereign_id,
        CASE
            WHEN NEW.blacklisted AND NOT OLD.blacklisted THEN 'blacklisted'
            WHEN NOT NEW.blacklisted AND OLD.blacklisted THEN 'cleared'
            ELSE 'updated'
        END,
        OLD.trust_level,
        NEW.trust_level,
        OLD.reputation_score,
        NEW.reputation_score,
        OLD.blacklisted,
        NEW.blacklisted
    );
    UPDATE sovereign_attributes SET updated_at = NOW() WHERE sovereign_id = NEW.sovereign_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER attr_audit_update
AFTER UPDATE ON sovereign_attributes
FOR EACH ROW
EXECUTE FUNCTION log_attribute_update();
