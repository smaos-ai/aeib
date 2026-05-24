-- Phase 75: Distributed Consensus Finalization
-- Tables for BFT (Byzantine Fault Tolerant) quorum management

CREATE TABLE IF NOT EXISTS bft_quorum_rounds (
    quorum_id UUID PRIMARY KEY,
    initiator_sovereign_id UUID NOT NULL REFERENCES sovereigns(id) ON DELETE RESTRICT,
    participant_sovereigns UUID[] NOT NULL,
    required_quorum BIGINT NOT NULL,
    yes_votes BIGINT NOT NULL DEFAULT 0,
    no_votes BIGINT NOT NULL DEFAULT 0,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    merkle_root VARCHAR(64),
    merkle_proof_ref VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finalized_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS bft_quorum_signatures (
    id UUID PRIMARY KEY,
    quorum_id UUID NOT NULL REFERENCES bft_quorum_rounds(quorum_id) ON DELETE CASCADE,
    voter_sovereign_id UUID NOT NULL REFERENCES sovereigns(id) ON DELETE RESTRICT,
    vote VARCHAR(32) NOT NULL,
    signature VARCHAR(256) NOT NULL,
    voted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(quorum_id, voter_sovereign_id)
);

CREATE INDEX IF NOT EXISTS idx_bft_quorum_rounds_initiator ON bft_quorum_rounds(initiator_sovereign_id);
CREATE INDEX IF NOT EXISTS idx_bft_quorum_rounds_status ON bft_quorum_rounds(status);
CREATE INDEX IF NOT EXISTS idx_bft_quorum_signatures_quorum ON bft_quorum_signatures(quorum_id);
CREATE INDEX IF NOT EXISTS idx_bft_quorum_signatures_voter ON bft_quorum_signatures(voter_sovereign_id);
