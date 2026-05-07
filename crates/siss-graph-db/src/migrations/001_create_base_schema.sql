-- SISS Knowledge Graph: Base Schema
-- All tables partitioned by tenant_id for isolation.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enums
CREATE TYPE risk_class AS ENUM ('low', 'medium', 'high', 'critical');
CREATE TYPE persona_kind AS ENUM ('human_role', 'ai_agent', 'system_daemon');
CREATE TYPE consolidation_tier AS ENUM ('working', 'episodic', 'semantic', 'procedural');
CREATE TYPE mandate_status AS ENUM ('pending', 'approved', 'rejected', 'expired');
CREATE TYPE task_status AS ENUM ('pending', 'authorized', 'routing', 'executing', 'guarding', 'crystallizing', 'completed', 'failed');
CREATE TYPE hardware_target AS ENUM ('local_mlx', 'remote_frontier', 'hybrid');
CREATE TYPE complexity_class AS ENUM ('trivial', 'simple', 'moderate', 'complex', 'heavy');
CREATE TYPE session_status AS ENUM ('active', 'suspended', 'completed', 'evicted');
CREATE TYPE rule_type AS ENUM ('rebac', 'ap2', 'memory_lifecycle', 'task_fsm', 'context', 'custom');
CREATE TYPE severity AS ENUM ('advisory', 'enforced', 'critical');

-- Identity Nodes
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT tenants_self_ref CHECK (id = tenant_id)
);

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    email TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_users_tenant ON users(tenant_id);

CREATE TABLE teams (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_teams_tenant ON teams(tenant_id);

CREATE TABLE personas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    name TEXT NOT NULL,
    kind persona_kind NOT NULL,
    is_frozen BOOLEAN NOT NULL DEFAULT FALSE,
    spawned_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_personas_tenant ON personas(tenant_id);

-- Resource Nodes
CREATE TABLE tools (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    name TEXT NOT NULL,
    tool_uri TEXT NOT NULL,
    risk_class risk_class NOT NULL,
    version TEXT NOT NULL DEFAULT '0.1.0',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_tools_tenant ON tools(tenant_id);

CREATE TABLE skills (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    name TEXT NOT NULL,
    definition TEXT NOT NULL,
    required_tools UUID[] NOT NULL DEFAULT '{}',
    version TEXT NOT NULL DEFAULT '0.1.0',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_skills_tenant ON skills(tenant_id);

CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    name TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    source_uri TEXT,
    content_hash BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_documents_tenant ON documents(tenant_id);

-- Memory Nodes (unified table with tier discrimination)
CREATE TABLE memories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    session_id UUID,
    content TEXT NOT NULL,
    confidence_score DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    quality_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    last_reinforced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    consolidation_tier consolidation_tier NOT NULL,
    content_hash BYTEA NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_memories_tenant ON memories(tenant_id);
CREATE INDEX idx_memories_tier ON memories(consolidation_tier);
CREATE INDEX idx_memories_confidence ON memories(confidence_score);

-- AP2 Transaction Nodes
CREATE TABLE intent_mandates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    budget_limit BIGINT NOT NULL,
    budget_spent BIGINT NOT NULL DEFAULT 0,
    risk_class risk_class NOT NULL,
    allowed_tools UUID[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT budget_not_exceeded CHECK (budget_spent <= budget_limit)
);
CREATE INDEX idx_intent_mandates_tenant ON intent_mandates(tenant_id);

CREATE TABLE payment_mandates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    intent_mandate_id UUID NOT NULL REFERENCES intent_mandates(id),
    amount BIGINT NOT NULL,
    risk_class risk_class NOT NULL,
    status mandate_status NOT NULL DEFAULT 'pending',
    cryptographic_signature BYTEA NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_payment_mandates_tenant ON payment_mandates(tenant_id);

CREATE TABLE payment_receipts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    payment_mandate_id UUID NOT NULL REFERENCES payment_mandates(id),
    amount BIGINT NOT NULL,
    cryptographic_signature BYTEA NOT NULL,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_payment_receipts_tenant ON payment_receipts(tenant_id);

-- Governance Nodes
CREATE TABLE governance_rules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    name TEXT NOT NULL,
    rule_type rule_type NOT NULL,
    expression TEXT NOT NULL,
    severity severity NOT NULL,
    applies_to TEXT[] NOT NULL DEFAULT '{}',
    version INT NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_governance_rules_tenant ON governance_rules(tenant_id);
CREATE INDEX idx_governance_rules_active ON governance_rules(is_active) WHERE is_active = TRUE;

-- Execution Nodes
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    intent TEXT NOT NULL,
    complexity_class complexity_class NOT NULL,
    status task_status NOT NULL DEFAULT 'pending',
    hardware_target hardware_target NOT NULL DEFAULT 'local_mlx',
    token_cost BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);
CREATE INDEX idx_tasks_tenant ON tasks(tenant_id);
CREATE INDEX idx_tasks_status ON tasks(status);

CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    token_budget BIGINT NOT NULL,
    tokens_consumed BIGINT NOT NULL DEFAULT 0,
    active_persona_id UUID NOT NULL REFERENCES personas(id),
    visible_field_snapshot JSONB NOT NULL DEFAULT 'null',
    status session_status NOT NULL DEFAULT 'active'
);
CREATE INDEX idx_sessions_tenant ON sessions(tenant_id);
CREATE INDEX idx_sessions_persona ON sessions(active_persona_id);
