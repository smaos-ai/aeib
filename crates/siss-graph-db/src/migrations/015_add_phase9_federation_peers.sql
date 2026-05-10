-- Phase 9: Bilateral Federation Agreements + Revocation Certificates
-- federation_peers: explicit bilateral trust grants between sovereigns
-- revocation_certificates: signed revocation notices (not DB cascade)

CREATE TABLE federation_peers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sovereign_a_id UUID NOT NULL REFERENCES sovereigns(id),
  sovereign_b_id UUID NOT NULL REFERENCES sovereigns(id),
  max_admitted_tier SMALLINT NOT NULL,
  granted_attestation_types TEXT[] NOT NULL,
  foreign_agent_budget_cap BIGINT NOT NULL DEFAULT 1000000,
  granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ,
  status VARCHAR(32) NOT NULL DEFAULT 'active'
);

CREATE UNIQUE INDEX idx_federation_peers_bilateral ON federation_peers(sovereign_a_id, sovereign_b_id, granted_at);
CREATE INDEX idx_federation_peers_active ON federation_peers(sovereign_a_id, sovereign_b_id)
  WHERE status = 'active'
  ORDER BY granted_at DESC;

CREATE TABLE revocation_certificates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id VARCHAR(255) NOT NULL,
  source_sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
  revoked_at TIMESTAMPTZ NOT NULL,
  signature TEXT NOT NULL,
  received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_revocation_certificates_agent ON revocation_certificates(agent_id, source_sovereign_id);
CREATE INDEX idx_revocation_certificates_time ON revocation_certificates(received_at);
