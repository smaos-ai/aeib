-- Phase 15 Task 74: Behavioral anomaly detection
-- Phase 15 Task 76: Threat intelligence crystallization

-- Anomaly detection audit trail
CREATE TABLE behavioral_anomalies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
    anomaly_type VARCHAR(32) NOT NULL
        CHECK (anomaly_type IN ('dispute_spam', 'timeout_spam', 'revocation_pattern')),
    severity VARCHAR(16) NOT NULL
        CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    evidence JSONB NOT NULL DEFAULT '{}',
    window_hours INT NOT NULL,
    event_count INT NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX idx_anomalies_sovereign ON behavioral_anomalies(sovereign_id, detected_at DESC);
CREATE INDEX idx_anomalies_active ON behavioral_anomalies(sovereign_id) WHERE is_active = TRUE;

-- Threat intelligence: auditable record of finalized quarantine decisions
CREATE TABLE threat_intelligence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
    anomaly_type VARCHAR(32) NOT NULL,
    evidence_summary TEXT NOT NULL,
    severity VARCHAR(16) NOT NULL,
    consensus_proposal_id UUID REFERENCES consensus_proposals(id),
    crystallized_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_threat_intel_sovereign ON threat_intelligence(sovereign_id, crystallized_at DESC);
