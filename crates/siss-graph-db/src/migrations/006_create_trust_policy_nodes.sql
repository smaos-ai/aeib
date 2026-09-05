-- SISS Knowledge Graph: Trust Policy Nodes
-- Adds HasTrustPolicy edge type and trust_policy_nodes table.

-- NOTE: ALTER TYPE ... ADD VALUE cannot run inside a transaction block.
-- The migration runner must NOT wrap this file in BEGIN/COMMIT.
ALTER TYPE edge_type ADD VALUE IF NOT EXISTS 'has_trust_policy';

-- Trust Policy Nodes — one per persona, per tenant.
CREATE TABLE IF NOT EXISTS trust_policy_nodes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    persona_id UUID NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    policy_version INT NOT NULL DEFAULT 1,

    -- Agent classification
    allowed_agent_types TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    denied_agents_by_id TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    allowed_organizations TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],

    -- Attestation requirements (boolean flags)
    hardware_enclave_required BOOLEAN NOT NULL DEFAULT FALSE,
    model_integrity_required BOOLEAN NOT NULL DEFAULT FALSE,
    max_failed_attestations INT NOT NULL DEFAULT 0,

    -- Security tier thresholds
    tier_1_score_threshold INT NOT NULL DEFAULT 100,
    tier_2_score_threshold INT NOT NULL DEFAULT 70,
    tier_3_score_threshold INT NOT NULL DEFAULT 40,

    -- Capability override rules (JSONB for flexibility)
    capability_overrides JSONB NOT NULL DEFAULT '[]'::JSONB,

    -- Token expiry
    session_token_expiry_seconds BIGINT NOT NULL DEFAULT 3600,
    capability_token_expiry_seconds BIGINT NOT NULL DEFAULT 86400,

    -- Metadata
    enforcement_mode VARCHAR(50) NOT NULL DEFAULT 'strict',
    audit_required BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_modified TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_modified_by UUID NOT NULL,

    -- Constraints
    CONSTRAINT unique_trust_policy_per_persona_tenant UNIQUE (persona_id, tenant_id)
);

-- Indexes for queries by tenant/persona
CREATE INDEX IF NOT EXISTS idx_trust_policy_nodes_persona_id ON trust_policy_nodes(persona_id);
CREATE INDEX IF NOT EXISTS idx_trust_policy_nodes_tenant_id ON trust_policy_nodes(tenant_id);
