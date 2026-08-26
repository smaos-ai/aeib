-- L2 Knowledge Layer Schema
-- EU AI Act compliance, evidence tracking, policy management
-- Uses pgvector for semantic search + BM25 for keyword search + RRF for reranking

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 1. Compliance Timeline (regulatory deadlines)
CREATE TABLE compliance_timeline (
    id SERIAL PRIMARY KEY,
    deadline DATE NOT NULL,
    regulation TEXT NOT NULL,
    article_number TEXT,
    description TEXT,
    annex_level VARCHAR(10),
    implementation_status VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Governance Risks (identified threats)
CREATE TABLE governance_risks (
    id SERIAL PRIMARY KEY,
    risk_name VARCHAR(255) NOT NULL,
    description TEXT,
    severity VARCHAR(20),
    mitigation_strategy TEXT,
    owner VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Tech Stack (layer to tool mapping)
CREATE TABLE tech_stack (
    id SERIAL PRIMARY KEY,
    layer VARCHAR(20) NOT NULL,
    tool_name VARCHAR(255) NOT NULL,
    tool_version VARCHAR(50),
    purpose TEXT,
    audit_evidence TEXT,
    critical_for_compliance BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Evidence by Process (audit trail)
CREATE TABLE evidence_by_process (
    id SERIAL PRIMARY KEY,
    request_id UUID NOT NULL,
    request_type VARCHAR(100),
    model_used VARCHAR(255),
    data_touched TEXT,
    approved_by VARCHAR(255),
    human_oversight_required BOOLEAN,
    human_oversight_completed BOOLEAN,
    digest_git_sha256 VARCHAR(64),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_request_id (request_id),
    INDEX idx_timestamp (timestamp)
);

-- 5. Policy Documents (EU AI Act text + interpretations)
CREATE TABLE policy_documents (
    id SERIAL PRIMARY KEY,
    article_id VARCHAR(50),
    article_text TEXT,
    embedding vector(1536),
    interpretation TEXT,
    annex_reference VARCHAR(100),
    keywords TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(article_id)
);

-- 6. Permit Gates (authorization decisions)
CREATE TABLE permit_gates (
    id SERIAL PRIMARY KEY,
    gate_name VARCHAR(255) NOT NULL,
    required_approvals INT,
    current_approvals INT,
    status VARCHAR(50),
    escalation_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_policy_embedding ON policy_documents USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_policy_keywords ON policy_documents USING gin(keywords gin_trgm_ops);
CREATE INDEX idx_compliance_deadline ON compliance_timeline(deadline);
CREATE INDEX idx_governance_severity ON governance_risks(severity);

-- Views for common queries
CREATE VIEW compliance_alerts AS
SELECT
    deadline,
    regulation,
    article_number,
    description,
    EXTRACT(DAY FROM deadline - CURRENT_DATE) as days_until_deadline
FROM compliance_timeline
WHERE deadline > CURRENT_DATE
ORDER BY deadline ASC;

CREATE VIEW active_risks AS
SELECT
    risk_name,
    severity,
    mitigation_strategy,
    owner
FROM governance_risks
WHERE severity IN ('HIGH', 'CRITICAL')
ORDER BY severity DESC;
