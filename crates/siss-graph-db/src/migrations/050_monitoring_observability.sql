-- Phase 76: Real-Time Monitoring & Observability

CREATE TABLE IF NOT EXISTS agent_heartbeats (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id              VARCHAR(255) NOT NULL,
    sovereign_id          UUID NOT NULL REFERENCES sovereigns(id) ON DELETE CASCADE,
    heartbeat_ts          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    latency_ms            BIGINT NOT NULL,
    status                VARCHAR(32) NOT NULL DEFAULT 'healthy',
    merkle_proof_ref      VARCHAR(64),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_heartbeats_agent ON agent_heartbeats(agent_id);
CREATE INDEX IF NOT EXISTS idx_heartbeats_sovereign ON agent_heartbeats(sovereign_id);
CREATE INDEX IF NOT EXISTS idx_heartbeats_ts ON agent_heartbeats(heartbeat_ts);
CREATE INDEX IF NOT EXISTS idx_heartbeats_status ON agent_heartbeats(status);

CREATE TABLE IF NOT EXISTS observability_event_log (
    sequence              BIGSERIAL PRIMARY KEY,
    event_id              UUID NOT NULL DEFAULT gen_random_uuid(),
    sovereign_id          UUID NOT NULL REFERENCES sovereigns(id) ON DELETE CASCADE,
    event_type            VARCHAR(64) NOT NULL,
    agent_id              VARCHAR(255),
    event_payload         JSONB,
    prev_hash             VARCHAR(64),
    curr_hash             VARCHAR(64) NOT NULL,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    merkle_dag_ref        VARCHAR(64)
);

CREATE INDEX IF NOT EXISTS idx_event_log_sovereign ON observability_event_log(sovereign_id);
CREATE INDEX IF NOT EXISTS idx_event_log_event_id ON observability_event_log(event_id);
CREATE INDEX IF NOT EXISTS idx_event_log_agent ON observability_event_log(agent_id);
CREATE INDEX IF NOT EXISTS idx_event_log_created ON observability_event_log(created_at);

CREATE TABLE IF NOT EXISTS anomaly_detection_rules (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_type             VARCHAR(64) NOT NULL,
    sovereign_id          UUID NOT NULL REFERENCES sovereigns(id) ON DELETE CASCADE,
    threshold_latency_ms  BIGINT,
    threshold_loss_pct    DECIMAL(5, 2),
    enabled               BOOLEAN NOT NULL DEFAULT true,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_anomaly_rules_sovereign ON anomaly_detection_rules(sovereign_id);
CREATE INDEX IF NOT EXISTS idx_anomaly_rules_enabled ON anomaly_detection_rules(enabled);

CREATE TABLE IF NOT EXISTS distributed_traces (
    trace_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    root_sovereign_id     UUID NOT NULL REFERENCES sovereigns(id) ON DELETE CASCADE,
    participating_sovereigns UUID[] NOT NULL DEFAULT '{}',
    request_id            VARCHAR(255) NOT NULL,
    start_ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    end_ts                TIMESTAMPTZ,
    status                VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_distributed_traces_root ON distributed_traces(root_sovereign_id);
CREATE INDEX IF NOT EXISTS idx_distributed_traces_request ON distributed_traces(request_id);
CREATE INDEX IF NOT EXISTS idx_distributed_traces_status ON distributed_traces(status);

CREATE TABLE IF NOT EXISTS alert_rules (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_name             VARCHAR(255) NOT NULL,
    severity              VARCHAR(32) NOT NULL,
    channels              TEXT[] NOT NULL DEFAULT '{}',
    enabled               BOOLEAN NOT NULL DEFAULT true,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alert_rules_enabled ON alert_rules(enabled);
CREATE INDEX IF NOT EXISTS idx_alert_rules_severity ON alert_rules(severity);

CREATE TABLE IF NOT EXISTS agents_alerts (
    alert_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id               UUID NOT NULL REFERENCES alert_rules(id) ON DELETE CASCADE,
    sovereign_id          UUID NOT NULL REFERENCES sovereigns(id) ON DELETE CASCADE,
    agent_id              VARCHAR(255) NOT NULL,
    fired_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status                VARCHAR(32) NOT NULL DEFAULT 'open',
    acknowledged_at       TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agents_alerts_rule ON agents_alerts(rule_id);
CREATE INDEX IF NOT EXISTS idx_agents_alerts_sovereign ON agents_alerts(sovereign_id);
CREATE INDEX IF NOT EXISTS idx_agents_alerts_agent ON agents_alerts(agent_id);
CREATE INDEX IF NOT EXISTS idx_agents_alerts_status ON agents_alerts(status);
