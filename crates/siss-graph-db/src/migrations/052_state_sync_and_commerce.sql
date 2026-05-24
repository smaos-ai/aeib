-- Phase 77: Cross-Sovereign Capability Negotiation & State Synchronization

-- Capability requests table: tracks requests for capabilities across sovereign boundaries
CREATE TABLE IF NOT EXISTS capability_requests (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requester_id          UUID NOT NULL,
    requester_sovereign   UUID NOT NULL REFERENCES sovereigns(id) ON DELETE CASCADE,
    target_resource       VARCHAR(255) NOT NULL,
    requested_capability  VARCHAR(64) NOT NULL,
    ceiling_tier_limit    VARCHAR(32) NOT NULL,
    status                VARCHAR(32) NOT NULL DEFAULT 'pending',
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_capability_requests_requester_id ON capability_requests(requester_id);
CREATE INDEX IF NOT EXISTS idx_capability_requests_requester_sovereign ON capability_requests(requester_sovereign);
CREATE INDEX IF NOT EXISTS idx_capability_requests_status ON capability_requests(status);
CREATE INDEX IF NOT EXISTS idx_capability_requests_created_at ON capability_requests(created_at);

-- Capability grants table: immutable record of granted capabilities
CREATE TABLE IF NOT EXISTS capability_grants (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id            UUID NOT NULL REFERENCES capability_requests(id) ON DELETE CASCADE,
    granted_capability    VARCHAR(64) NOT NULL,
    ceiling_tier          VARCHAR(32) NOT NULL,
    expires_at            TIMESTAMPTZ NOT NULL,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_capability_grants_request_id ON capability_grants(request_id);
CREATE INDEX IF NOT EXISTS idx_capability_grants_ceiling_tier ON capability_grants(ceiling_tier);
CREATE INDEX IF NOT EXISTS idx_capability_grants_expires_at ON capability_grants(expires_at);

-- Grant ledger: transactional record of all grants with consensus proofs
CREATE TABLE IF NOT EXISTS grant_ledger (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    grant_id              UUID NOT NULL,
    request_id            UUID NOT NULL REFERENCES capability_requests(id) ON DELETE CASCADE,
    granted_capability    VARCHAR(64) NOT NULL,
    ceiling_tier          VARCHAR(32) NOT NULL,
    expires_at            TIMESTAMPTZ NOT NULL,
    recorded_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status                VARCHAR(32) NOT NULL DEFAULT 'active',
    consensus_proof       VARCHAR(255)
);

CREATE INDEX IF NOT EXISTS idx_grant_ledger_grant_id ON grant_ledger(grant_id);
CREATE INDEX IF NOT EXISTS idx_grant_ledger_request_id ON grant_ledger(request_id);
CREATE INDEX IF NOT EXISTS idx_grant_ledger_status ON grant_ledger(status);
CREATE INDEX IF NOT EXISTS idx_grant_ledger_recorded_at ON grant_ledger(recorded_at);

-- Delegation relationships: track delegation chains between sovereigns
CREATE TABLE IF NOT EXISTS delegation_relationships (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    delegator             UUID NOT NULL REFERENCES sovereigns(id) ON DELETE CASCADE,
    delegatee             UUID NOT NULL REFERENCES sovereigns(id) ON DELETE CASCADE,
    ceiling_tier          VARCHAR(32) NOT NULL,
    delegated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at            TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_delegation_relationships_delegator ON delegation_relationships(delegator);
CREATE INDEX IF NOT EXISTS idx_delegation_relationships_delegatee ON delegation_relationships(delegatee);
CREATE INDEX IF NOT EXISTS idx_delegation_relationships_ceiling_tier ON delegation_relationships(ceiling_tier);
CREATE UNIQUE INDEX IF NOT EXISTS idx_delegation_relationships_unique ON delegation_relationships(delegator, delegatee) WHERE revoked_at IS NULL;

-- Commerce state table: tracks cross-sovereign transaction state and settlements
CREATE TABLE IF NOT EXISTS commerce_state (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sovereign_id          UUID NOT NULL REFERENCES sovereigns(id) ON DELETE CASCADE,
    transaction_id        UUID NOT NULL,
    state_type            VARCHAR(64) NOT NULL,
    state_data            JSONB NOT NULL,
    merkle_root           VARCHAR(255),
    consensus_round       BIGINT,
    finalized_at          TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_commerce_state_sovereign_id ON commerce_state(sovereign_id);
CREATE INDEX IF NOT EXISTS idx_commerce_state_transaction_id ON commerce_state(transaction_id);
CREATE INDEX IF NOT EXISTS idx_commerce_state_state_type ON commerce_state(state_type);
CREATE INDEX IF NOT EXISTS idx_commerce_state_consensus_round ON commerce_state(consensus_round);
CREATE INDEX IF NOT EXISTS idx_commerce_state_finalized_at ON commerce_state(finalized_at);

-- State synchronization ledger: tracks state replication across sovereigns
CREATE TABLE IF NOT EXISTS state_sync_ledger (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_sovereign      UUID NOT NULL REFERENCES sovereigns(id) ON DELETE CASCADE,
    target_sovereign      UUID NOT NULL REFERENCES sovereigns(id) ON DELETE CASCADE,
    state_hash            VARCHAR(255) NOT NULL,
    sync_round            BIGINT NOT NULL,
    acknowledged_at       TIMESTAMPTZ,
    synced_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_state_sync_ledger_source ON state_sync_ledger(source_sovereign);
CREATE INDEX IF NOT EXISTS idx_state_sync_ledger_target ON state_sync_ledger(target_sovereign);
CREATE INDEX IF NOT EXISTS idx_state_sync_ledger_sync_round ON state_sync_ledger(sync_round);
CREATE INDEX IF NOT EXISTS idx_state_sync_ledger_synced_at ON state_sync_ledger(synced_at);
