CREATE TABLE IF NOT EXISTS cross_sovereign_agent_registry (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id              VARCHAR(255) NOT NULL,
    sovereign_id          UUID NOT NULL REFERENCES sovereigns(id) ON DELETE CASCADE,
    agent_type            VARCHAR(64) NOT NULL,
    capabilities          TEXT[] NOT NULL DEFAULT '{}',
    endpoint_url          VARCHAR(512),
    registered_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status                VARCHAR(32) NOT NULL DEFAULT 'active',
    UNIQUE (agent_id, sovereign_id)
);

CREATE INDEX IF NOT EXISTS idx_csar_sovereign ON cross_sovereign_agent_registry(sovereign_id);
CREATE INDEX IF NOT EXISTS idx_csar_capabilities ON cross_sovereign_agent_registry USING gin(capabilities);
CREATE INDEX IF NOT EXISTS idx_csar_status ON cross_sovereign_agent_registry(status);

-- Phase 74: Multi-Sovereign Consensus Proposal Tracking
CREATE TABLE IF NOT EXISTS multi_sovereign_proposals (
    proposal_id           UUID PRIMARY KEY,
    initiator_sovereign_id UUID NOT NULL REFERENCES sovereigns(id) ON DELETE CASCADE,
    sovereign_participants UUID[] NOT NULL DEFAULT '{}',
    proposal_type         VARCHAR(64) NOT NULL,
    required_quorum       BIGINT NOT NULL,
    expires_at            TIMESTAMPTZ NOT NULL,
    status                VARCHAR(32) NOT NULL DEFAULT 'pending',
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decided_at            TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_msp_initiator ON multi_sovereign_proposals(initiator_sovereign_id);
CREATE INDEX IF NOT EXISTS idx_msp_status ON multi_sovereign_proposals(status);
CREATE INDEX IF NOT EXISTS idx_msp_expires_at ON multi_sovereign_proposals(expires_at);

-- Phase 74: Distributed Consensus Votes
CREATE TABLE IF NOT EXISTS distributed_consensus_votes (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id           UUID NOT NULL REFERENCES multi_sovereign_proposals(proposal_id) ON DELETE CASCADE,
    voter_sovereign_id    UUID NOT NULL REFERENCES sovereigns(id) ON DELETE CASCADE,
    vote                  VARCHAR(32) NOT NULL,
    voted_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    signature             TEXT,
    UNIQUE (proposal_id, voter_sovereign_id)
);

CREATE INDEX IF NOT EXISTS idx_dcv_proposal ON distributed_consensus_votes(proposal_id);
CREATE INDEX IF NOT EXISTS idx_dcv_voter ON distributed_consensus_votes(voter_sovereign_id);
