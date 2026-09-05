-- Phase 5: Attestation Refresh Session Persistence
-- Extends sessions table with token and trust evaluation tracking

ALTER TABLE sessions
  ADD COLUMN session_token TEXT,
  ADD COLUMN capability_token TEXT,
  ADD COLUMN attestation_score INT NOT NULL DEFAULT 0,
  ADD COLUMN attestation_tier INT,
  ADD COLUMN last_refreshed_at TIMESTAMPTZ,
  ADD COLUMN session_expires_at TIMESTAMPTZ;

-- Index for fast session token lookup during refresh validation
CREATE INDEX idx_sessions_token ON sessions(session_token) WHERE session_token IS NOT NULL;

-- Index for session expiry enforcement
CREATE INDEX idx_sessions_expiry ON sessions(session_expires_at) WHERE status = 'active'::session_status;
