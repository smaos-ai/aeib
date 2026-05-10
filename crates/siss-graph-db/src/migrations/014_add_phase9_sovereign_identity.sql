-- Phase 9: Federated Identity Foundation
-- Introduces sovereigns table + shadow persona support for cross-sovereign operations

CREATE TABLE sovereigns (
  id UUID PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  public_key_pem TEXT NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  established_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Tenants now have a sovereign_id (organizational anchor)
ALTER TABLE tenants
  ADD COLUMN sovereign_id UUID REFERENCES sovereigns(id);

-- Personas can have origin_sovereign_id (NULL = local, non-NULL = shadow/foreign)
ALTER TABLE personas
  ADD COLUMN origin_sovereign_id UUID REFERENCES sovereigns(id);

-- Sessions track whether they are federated cross-sovereign operations
ALTER TABLE sessions
  ADD COLUMN is_federated_session BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN origin_sovereign_id UUID REFERENCES sovereigns(id);

-- Indexes for shadow persona lookups and federated session filtering
CREATE INDEX idx_personas_origin_sovereign ON personas(origin_sovereign_id)
  WHERE origin_sovereign_id IS NOT NULL;

CREATE INDEX idx_sessions_federated ON sessions(origin_sovereign_id)
  WHERE is_federated_session = TRUE;
