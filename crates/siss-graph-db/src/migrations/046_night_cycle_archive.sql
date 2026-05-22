-- Phase 43: Night Cycle Archive Table
-- Supports atomic move-before-delete pattern for metabolic decay

CREATE TABLE IF NOT EXISTS crystallized_archive (
    idempotency_key TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    phase TEXT NOT NULL,
    status TEXT NOT NULL,
    payload_json TEXT,
    crystallized_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    archived_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_crystallized_agent_phase
ON crystallized_archive(agent_id, phase);
