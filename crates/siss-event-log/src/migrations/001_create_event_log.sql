-- Create event_log table for append-only event persistence
CREATE TABLE IF NOT EXISTS event_log (
    id UUID PRIMARY KEY,
    job_id UUID NOT NULL,
    event_type VARCHAR(32) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index for fast lookups by job_id
CREATE INDEX IF NOT EXISTS idx_event_log_job_id ON event_log(job_id);

-- Index for ordering by creation time
CREATE INDEX IF NOT EXISTS idx_event_log_created_at ON event_log(created_at DESC);

-- Composite index for efficient filtering
CREATE INDEX IF NOT EXISTS idx_event_log_job_created ON event_log(job_id, created_at DESC);
