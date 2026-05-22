-- Phase 11: Cross-Sovereign Delegation Grants
-- Constitutional invariant: TRANSITIVITY_DEPTH_MAX = 3

CREATE TABLE cross_sovereign_delegation_grants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    grantor_agent_id VARCHAR(255) NOT NULL,
    grantor_sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
    grantee_agent_id VARCHAR(255) NOT NULL,
    grantee_sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
    federation_peer_id UUID NOT NULL REFERENCES federation_peers(id),
    ceiling_tier SMALLINT NOT NULL,
    ceiling_attestation_types TEXT[] NOT NULL,
    transitivity_depth SMALLINT NOT NULL CHECK (transitivity_depth BETWEEN 1 AND 4),
    parent_grant_id UUID REFERENCES cross_sovereign_delegation_grants(id),
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    grant_signature TEXT NOT NULL,
    CONSTRAINT check_not_same_sovereign CHECK (grantor_sovereign_id != grantee_sovereign_id),
    CONSTRAINT check_no_self_delegation CHECK (
        grantor_agent_id != grantee_agent_id OR grantor_sovereign_id != grantee_sovereign_id
    )
);

CREATE INDEX idx_csdg_grantor ON cross_sovereign_delegation_grants(grantor_sovereign_id, grantor_agent_id) WHERE status = 'active';
CREATE INDEX idx_csdg_grantee ON cross_sovereign_delegation_grants(grantee_sovereign_id, grantee_agent_id) WHERE status = 'active';
CREATE UNIQUE INDEX idx_csdg_unique_active ON cross_sovereign_delegation_grants(
    grantor_agent_id, grantor_sovereign_id, grantee_agent_id, grantee_sovereign_id
) WHERE status = 'active';
