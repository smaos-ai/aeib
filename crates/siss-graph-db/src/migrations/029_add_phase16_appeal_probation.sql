-- Phase 16 Task 77: Appeal Protocol
-- Tracks consensus-gated appeal requests from quarantined sovereigns
CREATE TABLE appeal_proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
    consensus_proposal_id UUID NOT NULL REFERENCES consensus_proposals(id),
    improvement_evidence JSONB NOT NULL DEFAULT '{}',
    appeal_initiated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    appeal_resolved_at TIMESTAMPTZ,
    is_approved BOOLEAN
);
CREATE INDEX idx_appeals_sovereign ON appeal_proposals(sovereign_id, appeal_initiated_at DESC);
CREATE INDEX idx_appeals_pending ON appeal_proposals(sovereign_id) WHERE is_approved IS NULL;

-- Phase 16 Task 78: Behavioral Improvement Tracking
-- 7-day behavioral metrics for determining appeal readiness
CREATE TABLE behavioral_improvements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
    disputes_7d INT NOT NULL,
    timeouts_7d INT NOT NULL,
    revocations_7d INT NOT NULL,
    is_ready_for_appeal BOOLEAN NOT NULL DEFAULT FALSE,
    measured_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_improvements_sovereign ON behavioral_improvements(sovereign_id, measured_at DESC);

-- Phase 16 Task 79: Probation State & Enforcement
-- Audit trail of all probation events for compliance and monitoring
CREATE TABLE probation_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
    probation_started_at TIMESTAMPTZ NOT NULL,
    event_type VARCHAR(32) NOT NULL
        CHECK (event_type IN ('activity_logged', 'threshold_approaching', 'anomaly_detected', 'clean_exit')),
    event_details JSONB NOT NULL DEFAULT '{}',
    logged_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_probation_log_sovereign ON probation_audit_log(sovereign_id, logged_at DESC);
