-- Phase 8: Behavioral Governance
-- Creates behavior_events table to track trust tier adjustments over time
-- and enable deterministic behavior scoring with exponential decay

CREATE TABLE behavior_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  event_type VARCHAR(32) NOT NULL,
  tier_before SMALLINT NOT NULL,
  tier_after SMALLINT NOT NULL,
  tier_delta SMALLINT NOT NULL,
  cost_incurred BIGINT NOT NULL DEFAULT 0,
  attestation_count SMALLINT NOT NULL DEFAULT 0,
  lineage_safe BOOLEAN NOT NULL DEFAULT TRUE,
  scored_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_behavior_events_session_id ON behavior_events(session_id);
CREATE INDEX idx_behavior_events_scored_at ON behavior_events(session_id, scored_at DESC);
