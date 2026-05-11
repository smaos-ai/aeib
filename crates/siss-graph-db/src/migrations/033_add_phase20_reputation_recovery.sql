-- Migration 033: Phase 20 — Graduated Reputation Recovery
-- Purpose: Track recovery lifecycle with graduated score progression (8 weeks, week 1=85 → week 8=100)
-- Every recovery_log record integrates with:
-- - Phase 19 enriched scoring (signals apply continuously)
-- - SMAOS intelligence graph (dual-write decision lineage)
-- - AG-UI event streaming (recovery transitions emit RecoveryEvent)

CREATE TABLE reputation_recovery_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Entry Conditions (lifecycle transition anchor)
    sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
    recovery_started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    score_at_entry INT NOT NULL,
    probation_exit_reason VARCHAR(32) NOT NULL
        CHECK (probation_exit_reason IN ('clean_30_days', 'manual_override', 'appeal_success')),

    -- Recovery Progress (8-week graduated window)
    recovery_window_weeks INT NOT NULL DEFAULT 8,
    recovery_progress_weeks INT NOT NULL DEFAULT 0,
    last_progress_update_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Signals During Recovery (Phase 19 integration)
    slashes_during_recovery INT NOT NULL DEFAULT 0,
    anomalies_during_recovery INT NOT NULL DEFAULT 0,
    settlement_bonus_during_recovery INT NOT NULL DEFAULT 0,
    score_adjustments_applied INT NOT NULL DEFAULT 0,

    -- Exit Conditions (success or failure)
    recovery_completed_at TIMESTAMPTZ,
    recovery_exit_status VARCHAR(32)
        CHECK (recovery_exit_status IS NULL OR recovery_exit_status IN ('success', 'failure')),
    score_at_exit INT,

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_recovery_sovereign ON reputation_recovery_log(sovereign_id, recovery_started_at DESC);
CREATE INDEX idx_recovery_active ON reputation_recovery_log(sovereign_id)
    WHERE recovery_exit_status IS NULL;
CREATE INDEX idx_recovery_completed ON reputation_recovery_log(sovereign_id, recovery_completed_at DESC)
    WHERE recovery_exit_status IS NOT NULL;
