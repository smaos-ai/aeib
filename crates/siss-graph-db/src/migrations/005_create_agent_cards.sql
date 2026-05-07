-- SISS Knowledge Graph: Agent Cards (A2A Discovery)
-- Adds has_agent_card edge type and agent_cards table.

-- Add the new edge value. IF NOT EXISTS makes this idempotent.
ALTER TYPE edge_type ADD VALUE IF NOT EXISTS 'has_agent_card';

-- Agent Card nodes — one per persona, per tenant.
CREATE TABLE IF NOT EXISTS agent_cards (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    persona_id UUID NOT NULL REFERENCES personas(id),
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT '0.1.0',
    url TEXT NOT NULL,
    hardware_affinity hardware_target NOT NULL DEFAULT 'local_mlx',
    budget_cap BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT agent_cards_persona_tenant_unique UNIQUE (persona_id, tenant_id)
);
CREATE INDEX IF NOT EXISTS idx_agent_cards_tenant ON agent_cards(tenant_id);
CREATE INDEX IF NOT EXISTS idx_agent_cards_persona ON agent_cards(persona_id);
