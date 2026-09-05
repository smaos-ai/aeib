-- Phase 7: Token Budget & Rate Limiting
-- Adds token budget tracking and rate limit constraints to sessions

-- Add budget fields to sessions table
ALTER TABLE sessions
  ADD COLUMN token_budget_initial BIGINT NOT NULL DEFAULT 1000000,
  ADD COLUMN token_budget_remaining BIGINT NOT NULL DEFAULT 1000000,
  ADD COLUMN token_budget_consumed BIGINT NOT NULL DEFAULT 0,
  ADD COLUMN token_budget_reset_at TIMESTAMPTZ DEFAULT NOW(),
  ADD COLUMN rate_limits JSONB,
  ADD COLUMN last_refresh_at TIMESTAMPTZ;

-- Create indexes for budget tracking and rate limiting
CREATE INDEX idx_sessions_budget_remaining ON sessions(id)
  WHERE token_budget_remaining > 0 AND status = 'active'::session_status;

CREATE INDEX idx_sessions_last_refresh ON sessions(last_refresh_at)
  WHERE status = 'active'::session_status;

-- Add constraint: budget conservation
-- Verify that initial = remaining + consumed always holds
ALTER TABLE sessions
  ADD CONSTRAINT budget_conservation CHECK (
    token_budget_initial = (token_budget_remaining + token_budget_consumed)
  );

-- Add constraint: budget fields non-negative
ALTER TABLE sessions
  ADD CONSTRAINT budget_non_negative CHECK (
    token_budget_initial >= 0 AND
    token_budget_remaining >= 0 AND
    token_budget_consumed >= 0
  );

-- Add constraint: rate_limits format validation (if present, must be valid JSON)
-- Note: Full validation done at application level
ALTER TABLE sessions
  ADD CONSTRAINT rate_limits_json CHECK (
    rate_limits IS NULL OR rate_limits ? 'rate_limit'
  );
