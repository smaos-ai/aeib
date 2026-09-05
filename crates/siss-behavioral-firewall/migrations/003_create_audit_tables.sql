-- audit_log: Append-only decision audit trail with Merkle chaining
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    actor UUID NOT NULL,
    decision_type TEXT NOT NULL,
    mandate_id UUID NOT NULL,
    request_hash BYTEA NOT NULL,
    prev_hash BYTEA NOT NULL,
    decision_hash BYTEA NOT NULL,
    decision_json JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL DEFAULT (NOW() + INTERVAL '90 days'),
    CONSTRAINT immutable_log CHECK (id IS NOT NULL)
);

CREATE INDEX idx_audit_log_actor ON audit_log(actor);
CREATE INDEX idx_audit_log_timestamp ON audit_log(created_at);
CREATE INDEX idx_audit_log_expires ON audit_log(expires_at);

-- config_evolution_ledger: Track all policy mutations
CREATE TABLE IF NOT EXISTS config_evolution_ledger (
    id SERIAL PRIMARY KEY,
    rule_id UUID NOT NULL,
    rule_name TEXT NOT NULL,
    old_config JSONB,
    new_config JSONB,
    author UUID NOT NULL,
    author_signature BYTEA NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT immutable_evolution CHECK (id IS NOT NULL)
);

CREATE INDEX idx_config_evolution_rule ON config_evolution_ledger(rule_id);
