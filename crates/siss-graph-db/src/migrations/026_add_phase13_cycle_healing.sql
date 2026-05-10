-- Phase 13 Task 69: Cycle Healing Audit Log
-- Blackboard pattern: shared audit trail for automatic and consensus-gated cycle healing

CREATE TABLE cycle_healing_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cycle_nodes UUID[] NOT NULL,
    severity VARCHAR(16) NOT NULL,
    weakest_link_sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
    weakest_link_ceiling INT NOT NULL,
    grant_id_revoked UUID REFERENCES cross_sovereign_delegation_grants(id),
    action_taken VARCHAR(32) NOT NULL,   -- "auto_revoked" | "consensus_initiated"
    proposal_id UUID REFERENCES consensus_proposals(id),
    healed_by_sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
    healed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cascade_count INT NOT NULL DEFAULT 0,
    CONSTRAINT check_action_valid CHECK (action_taken IN ('auto_revoked', 'consensus_initiated')),
    CONSTRAINT check_weakest_ceiling_positive CHECK (weakest_link_ceiling > 0),
    CONSTRAINT check_cascade_count_nonnegative CHECK (cascade_count >= 0)
);

CREATE INDEX idx_healing_log_sovereign ON cycle_healing_log(healed_by_sovereign_id);
CREATE INDEX idx_healing_log_grant ON cycle_healing_log(grant_id_revoked) WHERE grant_id_revoked IS NOT NULL;
CREATE INDEX idx_healing_log_severity ON cycle_healing_log(severity);
