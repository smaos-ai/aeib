-- Phase 11: Gap Fixes
-- Fix Phase 10 gaps identified during Phase 11 planning

-- Fix Gap 2: cumulative foreign agent budget tracking
ALTER TABLE federation_peers
    ADD COLUMN foreign_agent_budget_consumed BIGINT NOT NULL DEFAULT 0
        CHECK (foreign_agent_budget_consumed >= 0);

-- Fix Gap 3: bidirectional peer lookup index
CREATE INDEX idx_federation_peers_inbound ON federation_peers(sovereign_b_id, sovereign_a_id)
    WHERE status = 'active';
