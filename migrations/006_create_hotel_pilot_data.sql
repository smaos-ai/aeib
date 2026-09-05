-- Stream Q: Hotel Credit Scoring Pilot Data Schema
-- Load 1,000 real guest records for Sep 1-15 testing
-- PII Masking: All names/emails SHA256-hashed
-- GDPR Compliance: 30-day retention policy + automatic purge

CREATE TABLE IF NOT EXISTS hotel_pilot_guests (
    guest_id SERIAL PRIMARY KEY,
    guest_hash VARCHAR(64) NOT NULL UNIQUE, -- SHA256(name + email)
    age_bracket VARCHAR(20) NOT NULL, -- "18-24", "25-34", "35-44", "45-54", "55-64", "65+"
    eu_resident BOOLEAN NOT NULL,
    location_country VARCHAR(2), -- ISO 3166-1 alpha-2
    credit_score INT CHECK (credit_score >= 300 AND credit_score <= 850),
    previous_bookings INT DEFAULT 0,
    previous_cancellations INT DEFAULT 0,
    average_stay_nights INT,
    total_spending_usd DECIMAL(10, 2),
    approval_decision VARCHAR(50), -- "APPROVED", "DENIED", "ESCALATED"
    risk_score FLOAT CHECK (risk_score >= 0 AND risk_score <= 1),
    fairness_group VARCHAR(50), -- "elderly", "non_eu", "low_credit", "new_guest", "baseline"
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP + INTERVAL '30 days'),
    test_run_id UUID NOT NULL
);

CREATE TABLE IF NOT EXISTS hotel_pilot_decisions (
    decision_id SERIAL PRIMARY KEY,
    guest_id INT NOT NULL REFERENCES hotel_pilot_guests(guest_id),
    request_timestamp TIMESTAMP NOT NULL,
    l1_policy_check VARCHAR(255),
    l2_knowledge_retrieval BOOLEAN,
    l3_gate_enforcement VARCHAR(50),
    l4_orchestration_trace TEXT,
    l6_freetoken_consumed INT,
    l8_proof_hash VARCHAR(64),
    l7_ragas_score FLOAT,
    decision_latency_ms INT,
    escalated_to_human BOOLEAN DEFAULT FALSE,
    human_reviewer_id VARCHAR(50),
    appeal_filed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX idx_hotel_guests_expires ON hotel_pilot_guests(expires_at);
CREATE INDEX idx_hotel_guests_fairness ON hotel_pilot_guests(fairness_group);
CREATE INDEX idx_hotel_decisions_guest ON hotel_pilot_decisions(guest_id);
CREATE INDEX idx_hotel_decisions_latency ON hotel_pilot_decisions(decision_latency_ms);
CREATE INDEX idx_hotel_decisions_timestamp ON hotel_pilot_decisions(request_timestamp);

-- View for fairness audit
CREATE VIEW hotel_fairness_audit AS
SELECT
    fairness_group,
    COUNT(*) as total_decisions,
    SUM(CASE WHEN approval_decision = 'APPROVED' THEN 1 ELSE 0 END) as approved,
    ROUND(100.0 * SUM(CASE WHEN approval_decision = 'APPROVED' THEN 1 ELSE 0 END) / COUNT(*), 2) as approval_rate,
    AVG(risk_score) as avg_risk_score,
    AVG(COALESCE(d.decision_latency_ms, 0)) as avg_latency_ms
FROM hotel_pilot_guests g
LEFT JOIN hotel_pilot_decisions d ON g.guest_id = d.guest_id
GROUP BY fairness_group
ORDER BY approval_rate DESC;

-- Automatic cleanup job (30-day retention)
-- Run via cron: psql -U smaos_user -d smaos -c "DELETE FROM hotel_pilot_guests WHERE expires_at < CURRENT_TIMESTAMP;"
