-- Phase 5.5 Task 13: Add session revocation capability
-- Extends sessions table with revocation status and timestamp

ALTER TYPE session_status ADD VALUE IF NOT EXISTS 'revoked';

ALTER TABLE sessions
  ADD COLUMN IF NOT EXISTS revoked_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_sessions_revoked
  ON sessions(id) WHERE status = 'revoked'::session_status;
