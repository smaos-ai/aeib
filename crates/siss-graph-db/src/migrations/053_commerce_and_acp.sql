-- Phase 78: Commerce & State Synchronization with ACP Routing

-- Commerce Agent Cards: Identity cards with Ed25519 public keys and capability registry
-- Distinct from the existing agent_cards table (migration 005) used for persona management
CREATE TABLE IF NOT EXISTS commerce_agent_cards (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id              VARCHAR(255) NOT NULL UNIQUE,
    endpoint_url          VARCHAR(255) NOT NULL,
    public_key_ed25519    VARCHAR(255) NOT NULL,
    capabilities          JSONB NOT NULL DEFAULT '{}',
    signature             VARCHAR(255) NOT NULL,
    issued_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at            TIMESTAMPTZ NOT NULL,
    verified_at           TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_commerce_agent_cards_agent_id ON commerce_agent_cards(agent_id);
CREATE INDEX IF NOT EXISTS idx_commerce_agent_cards_endpoint_url ON commerce_agent_cards(endpoint_url);
CREATE INDEX IF NOT EXISTS idx_commerce_agent_cards_expires_at ON commerce_agent_cards(expires_at);

-- UCP Checkout Requests: Universal Commerce Protocol checkout with buyer/seller
CREATE TABLE IF NOT EXISTS ucp_checkout_requests (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    buyer_agent_id        VARCHAR(255) NOT NULL,
    seller_agent_id       VARCHAR(255) NOT NULL,
    items                 JSONB NOT NULL,
    amount_cents          BIGINT NOT NULL,
    currency              VARCHAR(3) NOT NULL DEFAULT 'USD',
    signature             VARCHAR(255) NOT NULL,
    status                VARCHAR(32) NOT NULL DEFAULT 'pending',
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    verified_at           TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_ucp_checkout_requests_buyer ON ucp_checkout_requests(buyer_agent_id);
CREATE INDEX IF NOT EXISTS idx_ucp_checkout_requests_seller ON ucp_checkout_requests(seller_agent_id);
CREATE INDEX IF NOT EXISTS idx_ucp_checkout_requests_status ON ucp_checkout_requests(status);
CREATE INDEX IF NOT EXISTS idx_ucp_checkout_requests_created_at ON ucp_checkout_requests(created_at);

-- AP2 Intent Mandates: Authorization proofs with ceiling tiers for settlement
CREATE TABLE IF NOT EXISTS ap2_intent_mandates (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    checkout_id           UUID NOT NULL REFERENCES ucp_checkout_requests(id) ON DELETE CASCADE,
    buyer_proof           VARCHAR(255) NOT NULL,
    ceiling_tier          VARCHAR(32) NOT NULL,
    authorization_sig     VARCHAR(255) NOT NULL,
    status                VARCHAR(32) NOT NULL DEFAULT 'pending',
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    authorized_at         TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_ap2_intent_mandates_checkout_id ON ap2_intent_mandates(checkout_id);
CREATE INDEX IF NOT EXISTS idx_ap2_intent_mandates_ceiling_tier ON ap2_intent_mandates(ceiling_tier);
CREATE INDEX IF NOT EXISTS idx_ap2_intent_mandates_status ON ap2_intent_mandates(status);

-- AP2 Settlements: Atomic lock-verify-release settlement records
CREATE TABLE IF NOT EXISTS ap2_settlements (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mandate_id            UUID NOT NULL REFERENCES ap2_intent_mandates(id) ON DELETE CASCADE,
    consensus_proof       VARCHAR(255) NOT NULL,
    lock_acquired_at      TIMESTAMPTZ,
    verified_at           TIMESTAMPTZ,
    released_at           TIMESTAMPTZ,
    status                VARCHAR(32) NOT NULL DEFAULT 'pending',
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ap2_settlements_mandate_id ON ap2_settlements(mandate_id);
CREATE INDEX IF NOT EXISTS idx_ap2_settlements_status ON ap2_settlements(status);
CREATE INDEX IF NOT EXISTS idx_ap2_settlements_created_at ON ap2_settlements(created_at);

-- ACP Message Log: Agent Communication Platform with stateful routing and context preservation
CREATE TABLE IF NOT EXISTS acp_message_log (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id            VARCHAR(255) NOT NULL UNIQUE,
    source_agent_id       VARCHAR(255) NOT NULL,
    target_agent_id       VARCHAR(255) NOT NULL,
    message_type          VARCHAR(64) NOT NULL,
    payload               JSONB NOT NULL,
    context_state         JSONB NOT NULL DEFAULT '{}',
    route_hops            INTEGER NOT NULL DEFAULT 1,
    routed_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delivered_at          TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_acp_message_log_source ON acp_message_log(source_agent_id);
CREATE INDEX IF NOT EXISTS idx_acp_message_log_target ON acp_message_log(target_agent_id);
CREATE INDEX IF NOT EXISTS idx_acp_message_log_message_id ON acp_message_log(message_id);
CREATE INDEX IF NOT EXISTS idx_acp_message_log_routed_at ON acp_message_log(routed_at);
