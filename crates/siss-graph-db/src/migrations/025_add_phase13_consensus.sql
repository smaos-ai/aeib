-- Phase 13 Task 68: 2-Phase Consensus Protocol
-- Blackboard pattern: shared tables for multi-agent consensus coordination
-- Constitutional invariant: CONSENSUS_QUORUM_REQUIRED (majority of active peers must approve)

CREATE TABLE consensus_proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    initiator_sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
    escrow_id UUID REFERENCES escrow_ledger(id),     -- nullable: cycle_break has no escrow
    proposal_type VARCHAR(32) NOT NULL,               -- "release_escrow" | "cycle_break" | "arbitration"
    payload JSONB NOT NULL DEFAULT '{}',              -- context data: grant_ids, cycle info, etc.
    status VARCHAR(32) NOT NULL DEFAULT 'pending',    -- "pending" | "approved" | "rejected" | "expired" | "finalized"
    required_quorum INT NOT NULL,                     -- ceil((peer_count + 1) / 2) at creation time
    peer_count INT NOT NULL,                          -- number of active peers at creation time
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '24 hours'),
    decided_at TIMESTAMPTZ,
    finalized_at TIMESTAMPTZ,

    -- Status machine constraints
    CONSTRAINT check_proposal_type CHECK (
        proposal_type IN ('release_escrow', 'cycle_break', 'arbitration')
    ),
    CONSTRAINT check_status_valid CHECK (
        status IN ('pending', 'approved', 'rejected', 'expired', 'finalized')
    ),
    CONSTRAINT check_quorum_positive CHECK (required_quorum > 0),
    CONSTRAINT check_peer_count_nonnegative CHECK (peer_count >= 0),
    CONSTRAINT check_expires_after_created CHECK (expires_at > created_at)
);

CREATE TABLE consensus_votes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID NOT NULL REFERENCES consensus_proposals(id),
    voter_sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
    vote VARCHAR(16) NOT NULL,               -- "yes" | "no" | "abstain"
    signature TEXT NOT NULL,                 -- Ed25519(voter.private_key, "{proposal_id}:{vote}")
    voted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Ensure each voter votes once per proposal (idempotent: second vote ignored)
    CONSTRAINT check_vote_valid CHECK (vote IN ('yes', 'no', 'abstain')),
    CONSTRAINT uq_one_vote_per_voter UNIQUE (proposal_id, voter_sovereign_id)
);

-- Index for finding pending proposals by escrow (quick lookup during finalization)
CREATE INDEX idx_proposals_escrow ON consensus_proposals(escrow_id)
    WHERE status = 'pending';

-- Index for timeout sweep: find proposals past their expiration
CREATE INDEX idx_proposals_pending_timeout ON consensus_proposals(expires_at)
    WHERE status = 'pending';

-- Index for vote counting by proposal
CREATE INDEX idx_votes_proposal ON consensus_votes(proposal_id, vote);

-- Index for finding votes by voter (query: "has this sovereign voted on proposal X?")
CREATE INDEX idx_votes_voter_proposal ON consensus_votes(voter_sovereign_id, proposal_id);
