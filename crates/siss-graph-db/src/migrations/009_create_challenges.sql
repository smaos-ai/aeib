-- Phase 5.5 Task 14: Create challenges table for pull-based refresh flow
-- Stores single-use nonces issued by SISS for agents to prove freshness

CREATE TABLE refresh_challenges (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL,
    nonce TEXT NOT NULL,
    required_attestations TEXT[] NOT NULL,
    issued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    consumed BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_challenges_session
  ON refresh_challenges(session_id) WHERE NOT consumed;

CREATE INDEX IF NOT EXISTS idx_challenges_expiry
  ON refresh_challenges(expires_at) WHERE NOT consumed;
