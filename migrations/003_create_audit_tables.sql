-- Phase 25 Wave 3: Audit Logging + S3 Archive Export
-- PostgreSQL schema for immutable audit logging with 90-day TTL

-- Main audit log table
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    audit_id UUID UNIQUE NOT NULL,
    requester UUID NOT NULL,
    action TEXT NOT NULL,
    decision TEXT NOT NULL,  -- 'Allow' or 'Deny'
    reasons JSONB NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '90 days',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Archive metadata table for S3 exports
CREATE TABLE IF NOT EXISTS audit_archive (
    id BIGSERIAL PRIMARY KEY,
    exported_at TIMESTAMPTZ DEFAULT NOW(),
    s3_bucket TEXT NOT NULL,
    s3_key TEXT NOT NULL,
    record_count BIGINT NOT NULL,
    checksum TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_audit_expires ON audit_log(expires_at);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_requester ON audit_log(requester);
CREATE INDEX IF NOT EXISTS idx_audit_decision ON audit_log(decision);
CREATE INDEX IF NOT EXISTS idx_archive_exported ON audit_archive(exported_at DESC);
