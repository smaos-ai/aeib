-- Stream Q: School Access Control Pilot Data Schema
-- Load 2,000 student records with biometric + attendance tracking
-- Temporal Durability: 48-hour network outage resilience
-- GDPR + Biometric: Full compliance with Art. 9 (sensitive data)

CREATE TABLE IF NOT EXISTS school_pilot_students (
    student_id SERIAL PRIMARY KEY,
    student_hash VARCHAR(64) NOT NULL UNIQUE, -- SHA256(name + student_id_number)
    age_group VARCHAR(20), -- "5-9", "10-14", "15-18"
    enrollment_status VARCHAR(50), -- "active", "on_campus", "off_campus", "transferred", "graduated"
    enrollment_date DATE,
    last_campus_visit DATE,
    attendance_rate FLOAT CHECK (attendance_rate >= 0 AND attendance_rate <= 1), -- 0.0 to 1.0
    days_since_attendance INT,
    biometric_template_hash VARCHAR(64), -- SHA256(fingerprint/iris data)
    biometric_enrollment_date DATE,
    teacher_notes TEXT,
    guardian_contact_hash VARCHAR(64), -- SHA256(parent email)
    special_accommodations VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP + INTERVAL '30 days'),
    test_run_id UUID NOT NULL
);

CREATE TABLE IF NOT EXISTS school_pilot_access_attempts (
    access_id SERIAL PRIMARY KEY,
    student_id INT NOT NULL REFERENCES school_pilot_students(student_id),
    attempt_timestamp TIMESTAMP NOT NULL,
    biometric_confidence FLOAT CHECK (biometric_confidence >= 0 AND biometric_confidence <= 1),
    l1_policy_check VARCHAR(255), -- Enrollment, attendance policy
    l2_knowledge_retrieval BOOLEAN,
    l3_gate_enforcement VARCHAR(50), -- "ALLOW", "DENY", "ESCALATE"
    l4_orchestration_trace TEXT,
    l5_communication_output TEXT,
    l6_freetoken_consumed INT,
    l8_proof_hash VARCHAR(64),
    l7_ragas_score FLOAT,
    access_decision VARCHAR(50), -- "GRANTED", "DENIED", "PENDING_REVIEW"
    decision_latency_ms INT,
    escalated_to_admin BOOLEAN DEFAULT FALSE,
    admin_reviewer_id VARCHAR(50),
    admin_decision VARCHAR(50),
    admin_review_time_seconds INT,
    reason_denied VARCHAR(255), -- "low_attendance", "off_campus", "biometric_mismatch", "invalid_enrollment"
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Temporal cache for network outage resilience (48-hour durability)
CREATE TABLE IF NOT EXISTS school_pilot_temporal_cache (
    cache_id SERIAL PRIMARY KEY,
    student_id INT NOT NULL REFERENCES school_pilot_students(student_id),
    cached_access_decision VARCHAR(50),
    cached_timestamp TIMESTAMP NOT NULL,
    cache_valid_until TIMESTAMP NOT NULL,
    last_synced TIMESTAMP,
    is_network_offline BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Impersonation/security test scenarios
CREATE TABLE IF NOT EXISTS school_pilot_security_tests (
    test_id SERIAL PRIMARY KEY,
    test_type VARCHAR(50), -- "spoofed_biometric", "valid_student_on_vacation", "off_campus_access", "transferred_student"
    target_student_id INT REFERENCES school_pilot_students(student_id),
    test_biometric_hash VARCHAR(64), -- Different biometric (for spoofing tests)
    expected_outcome VARCHAR(50), -- "DENIED", "ESCALATED", "ALLOWED"
    actual_outcome VARCHAR(50),
    ai_decision VARCHAR(50),
    test_passed BOOLEAN,
    confidence_score FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance (<5s latency SLA)
CREATE INDEX idx_school_students_expires ON school_pilot_students(expires_at);
CREATE INDEX idx_school_students_enrollment ON school_pilot_students(enrollment_status);
CREATE INDEX idx_school_students_attendance ON school_pilot_students(attendance_rate);
CREATE INDEX idx_school_access_student ON school_pilot_access_attempts(student_id);
CREATE INDEX idx_school_access_timestamp ON school_pilot_access_attempts(attempt_timestamp);
CREATE INDEX idx_school_access_latency ON school_pilot_access_attempts(decision_latency_ms);
CREATE INDEX idx_school_access_decision ON school_pilot_access_attempts(access_decision);
CREATE INDEX idx_school_cache_valid_until ON school_pilot_temporal_cache(cache_valid_until);
CREATE INDEX idx_school_cache_network_offline ON school_pilot_temporal_cache(is_network_offline);
CREATE INDEX idx_school_security_test_outcome ON school_pilot_security_tests(test_passed);

-- View for biometric accuracy audit
CREATE VIEW school_biometric_audit AS
SELECT
    s.age_group,
    COUNT(DISTINCT s.student_id) as total_students,
    COUNT(DISTINCT a.access_id) as total_access_attempts,
    SUM(CASE WHEN a.biometric_confidence > 0.95 THEN 1 ELSE 0 END) as high_confidence_matches,
    SUM(CASE WHEN a.access_decision = 'GRANTED' THEN 1 ELSE 0 END) as granted_access,
    SUM(CASE WHEN a.access_decision = 'DENIED' THEN 1 ELSE 0 END) as denied_access,
    SUM(CASE WHEN a.escalated_to_admin THEN 1 ELSE 0 END) as escalated_count,
    ROUND(100.0 * SUM(CASE WHEN a.biometric_confidence > 0.95 THEN 1 ELSE 0 END)::FLOAT / NULLIF(COUNT(DISTINCT a.access_id), 0), 2) as high_confidence_percent,
    ROUND(100.0 * SUM(CASE WHEN a.access_decision = 'GRANTED' THEN 1 ELSE 0 END)::FLOAT / NULLIF(COUNT(DISTINCT a.access_id), 0), 2) as grant_rate,
    AVG(a.decision_latency_ms) as avg_latency_ms
FROM school_pilot_students s
LEFT JOIN school_pilot_access_attempts a ON s.student_id = a.student_id
GROUP BY s.age_group
ORDER BY avg_latency_ms ASC;

-- View for security test performance
CREATE VIEW school_security_test_summary AS
SELECT
    test_type,
    COUNT(*) as total_tests,
    SUM(CASE WHEN test_passed THEN 1 ELSE 0 END) as passed,
    SUM(CASE WHEN actual_outcome = expected_outcome THEN 1 ELSE 0 END) as correct_decisions,
    ROUND(100.0 * SUM(CASE WHEN test_passed THEN 1 ELSE 0 END)::FLOAT / COUNT(*), 2) as pass_rate,
    ROUND(100.0 * SUM(CASE WHEN actual_outcome = expected_outcome THEN 1 ELSE 0 END)::FLOAT / COUNT(*), 2) as accuracy_percent,
    AVG(confidence_score) as avg_confidence
FROM school_pilot_security_tests
GROUP BY test_type
ORDER BY accuracy_percent DESC;

-- View for temporal cache effectiveness (network resilience)
CREATE VIEW school_temporal_resilience AS
SELECT
    COUNT(DISTINCT student_id) as cached_students,
    COUNT(*) as total_cache_entries,
    SUM(CASE WHEN cache_valid_until > CURRENT_TIMESTAMP THEN 1 ELSE 0 END) as valid_entries,
    SUM(CASE WHEN is_network_offline THEN 1 ELSE 0 END) as offline_decisions,
    MAX(cache_valid_until - cached_timestamp) as max_cache_duration,
    INTERVAL '48 hours' as target_duration,
    ROUND(100.0 * SUM(CASE WHEN cache_valid_until > CURRENT_TIMESTAMP THEN 1 ELSE 0 END)::FLOAT / NULLIF(COUNT(*), 0), 2) as cache_validity_percent
FROM school_pilot_temporal_cache;
