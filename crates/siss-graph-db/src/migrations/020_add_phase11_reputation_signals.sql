-- Phase 11: Reputation Signals
-- Constitutional invariant: REPUTATION_ISOLATION

ALTER TABLE federation_peers
    ADD COLUMN reputation_blend_weight FLOAT NOT NULL DEFAULT 0.0
        CHECK (reputation_blend_weight BETWEEN 0.0 AND 1.0);

CREATE TABLE federated_reputation_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
    subject_agent_id VARCHAR(255) NOT NULL,
    signal_type VARCHAR(32) NOT NULL CHECK (signal_type IN ('positive', 'negative', 'neutral')),
    signal_strength SMALLINT NOT NULL CHECK (signal_strength BETWEEN -10 AND 10),
    source_gossip_message_id UUID REFERENCES gossip_messages(id),
    observed_at TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    signal_signature TEXT NOT NULL,
    lineage_safe BOOLEAN NOT NULL DEFAULT FALSE CHECK (lineage_safe = FALSE)
);

CREATE INDEX idx_rep_signals_source ON federated_reputation_signals(source_sovereign_id, subject_agent_id);
CREATE INDEX idx_rep_signals_agent ON federated_reputation_signals(subject_agent_id, observed_at DESC);
