-- Stream Q: Glass Factory CAD Safety Review Pilot Data Schema
-- Load 500 CAD design documents for Sep 1-15 testing
-- Safety-Critical: Annex I compliant tempered glass designs
-- Zero False-Negatives: Target <0.01% FNR on safety-critical failures

CREATE TABLE IF NOT EXISTS glass_pilot_designs (
    design_id SERIAL PRIMARY KEY,
    design_hash VARCHAR(64) NOT NULL UNIQUE, -- SHA256(CAD content)
    design_name VARCHAR(255),
    design_type VARCHAR(50), -- "automotive", "architectural", "appliance"
    material_grade VARCHAR(50), -- "tempered", "laminated", "annealed"
    thickness_mm FLOAT,
    stress_test_passed BOOLEAN,
    temperature_range VARCHAR(50), -- "-20C to 80C", etc.
    safety_spec_version VARCHAR(20), -- ISO 12150, EN 1288, etc.
    l1_policy_status VARCHAR(50), -- "compliant", "non_compliant", "unknown"
    l3_safety_gate_result VARCHAR(50), -- "PASS", "FAIL", "REVIEW"
    risk_level INT CHECK (risk_level >= 0 AND risk_level <= 100),
    auditor_id VARCHAR(50),
    auditor_approval BOOLEAN,
    design_comments TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP + INTERVAL '30 days'),
    test_run_id UUID NOT NULL
);

CREATE TABLE IF NOT EXISTS glass_pilot_reviews (
    review_id SERIAL PRIMARY KEY,
    design_id INT NOT NULL REFERENCES glass_pilot_designs(design_id),
    reviewer_agent_id VARCHAR(50),
    l1_policy_check VARCHAR(255),
    l2_knowledge_retrieval BOOLEAN,
    l3_gate_enforcement VARCHAR(50),
    l4_orchestration_trace TEXT,
    l5_communication_output TEXT,
    l6_freetoken_consumed INT,
    l8_proof_hash VARCHAR(64),
    l7_ragas_score FLOAT,
    review_latency_ms INT,
    safety_confidence FLOAT CHECK (safety_confidence >= 0 AND safety_confidence <= 1),
    escalated_to_human BOOLEAN DEFAULT FALSE,
    human_safety_engineer_id VARCHAR(50),
    human_review_time_minutes INT,
    final_decision VARCHAR(50), -- "APPROVED", "REJECTED", "REDESIGN_REQUIRED"
    false_negative_risk BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Track false negatives from production (post-deployment)
CREATE TABLE IF NOT EXISTS glass_pilot_production_failures (
    failure_id SERIAL PRIMARY KEY,
    design_id INT REFERENCES glass_pilot_designs(design_id),
    failure_date TIMESTAMP NOT NULL,
    failure_description TEXT,
    root_cause VARCHAR(255),
    ai_review_decision VARCHAR(50), -- What AI decided during review
    was_false_negative BOOLEAN, -- Did AI miss this defect?
    severity_level VARCHAR(20), -- "CRITICAL", "HIGH", "MEDIUM", "LOW"
    affected_units INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX idx_glass_designs_expires ON glass_pilot_designs(expires_at);
CREATE INDEX idx_glass_designs_risk ON glass_pilot_designs(risk_level);
CREATE INDEX idx_glass_reviews_design ON glass_pilot_reviews(design_id);
CREATE INDEX idx_glass_reviews_latency ON glass_pilot_reviews(review_latency_ms);
CREATE INDEX idx_glass_reviews_safety_confidence ON glass_pilot_reviews(safety_confidence);
CREATE INDEX idx_glass_failures_false_negative ON glass_pilot_production_failures(was_false_negative);

-- View for safety audit (false negative tracking)
CREATE VIEW glass_safety_audit AS
SELECT
    g.design_type,
    COUNT(DISTINCT g.design_id) as total_designs,
    COUNT(DISTINCT f.design_id) as designs_with_failures,
    SUM(CASE WHEN f.was_false_negative THEN 1 ELSE 0 END) as false_negatives,
    ROUND(100.0 * SUM(CASE WHEN f.was_false_negative THEN 1 ELSE 0 END)::FLOAT / NULLIF(COUNT(DISTINCT g.design_id), 0), 3) as fnr_percent,
    AVG(r.safety_confidence) as avg_safety_confidence,
    AVG(r.review_latency_ms) as avg_review_latency_ms
FROM glass_pilot_designs g
LEFT JOIN glass_pilot_reviews r ON g.design_id = r.design_id
LEFT JOIN glass_pilot_production_failures f ON g.design_id = f.design_id
GROUP BY g.design_type
ORDER BY fnr_percent DESC;

-- SLA view: Designs reviewed <500ms with >85% safety confidence
CREATE VIEW glass_sla_compliance AS
SELECT
    COUNT(*) as total_reviews,
    SUM(CASE WHEN review_latency_ms < 500 THEN 1 ELSE 0 END) as latency_compliant,
    SUM(CASE WHEN safety_confidence > 0.85 THEN 1 ELSE 0 END) as confidence_compliant,
    ROUND(100.0 * SUM(CASE WHEN review_latency_ms < 500 THEN 1 ELSE 0 END)::FLOAT / COUNT(*), 2) as latency_sla_percent,
    ROUND(100.0 * SUM(CASE WHEN safety_confidence > 0.85 THEN 1 ELSE 0 END)::FLOAT / COUNT(*), 2) as confidence_sla_percent
FROM glass_pilot_reviews;
