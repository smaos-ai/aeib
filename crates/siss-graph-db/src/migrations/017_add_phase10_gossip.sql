-- Phase 10: Gossip Protocol for Dynamic Federation
-- Implements peer-to-peer message bus for revocation, renegotiation, and heartbeat propagation

-- Gossip messages: Idempotent message delivery via (source_sovereign_id, gossip_seq) uniqueness
CREATE TABLE gossip_messages (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
    gossip_seq          BIGINT NOT NULL,                    -- Monotonically increasing per source sovereign
    message_type        VARCHAR(64) NOT NULL,               -- 'revocation', 'renegotiation', 'heartbeat'
    payload             JSONB NOT NULL,
    payload_signature   TEXT NOT NULL,                      -- Ed25519 hex over canonical JSON payload
    received_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at        TIMESTAMPTZ,                        -- NULL until handler processes message
    CONSTRAINT uq_gossip_seq UNIQUE (source_sovereign_id, gossip_seq)
);

CREATE INDEX idx_gossip_messages_source ON gossip_messages(source_sovereign_id, gossip_seq);
CREATE INDEX idx_gossip_messages_unprocessed ON gossip_messages(message_type)
    WHERE processed_at IS NULL;

-- Extend federation_peers: Track gossip sequence and store agreement signature
ALTER TABLE federation_peers
    ADD COLUMN gossip_seq          BIGINT,                  -- Last gossip_seq seen from bilateral peer
    ADD COLUMN agreement_signature TEXT;                    -- Ed25519 hex over canonical agreement payload

-- Extend sovereign_credit_entries: Link to invoices and identify foreign agent
ALTER TABLE sovereign_credit_entries
    ADD COLUMN foreign_agent_id VARCHAR(255),               -- agent_id string from cross-sovereign session
    ADD COLUMN invoice_id       UUID;                       -- FK to settlement_invoices (added in Phase 10 Migration 018)

-- Extend sovereigns: Add endpoint URL for gossip delivery
ALTER TABLE sovereigns ADD COLUMN endpoint_url VARCHAR(512);  -- HTTP endpoint for receiving gossip messages
