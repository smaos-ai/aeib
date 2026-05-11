-- Migration 036: Phase 23 Unified Observability Layer
-- Purpose: Enable idempotent upsert of AgentActionNode, AnomalyEventNode, SystemMetricNode
--          Support dual-write ingestion of behavior_events and behavioral_anomalies

-- Idempotency indexes (unique, partial on label)

CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_action_behavior_event_id
    ON graph_entities ((properties->>'behavior_event_id'))
    WHERE label = 'AgentActionNode';

CREATE UNIQUE INDEX IF NOT EXISTS idx_anomaly_event_db_id
    ON graph_entities ((properties->>'anomaly_db_id'))
    WHERE label = 'AnomalyEventNode';

CREATE UNIQUE INDEX IF NOT EXISTS idx_system_metric_session_snapshot
    ON graph_entities ((properties->>'session_id'), (properties->>'snapshot_at'))
    WHERE label = 'SystemMetricNode';

-- Query indexes

CREATE INDEX IF NOT EXISTS idx_agent_action_session_id
    ON graph_entities ((properties->>'session_id'))
    WHERE label = 'AgentActionNode';

CREATE INDEX IF NOT EXISTS idx_anomaly_event_sovereign_detected
    ON graph_entities ((properties->>'sovereign_id'), created_at DESC)
    WHERE label = 'AnomalyEventNode';

CREATE INDEX IF NOT EXISTS idx_system_metric_session_time
    ON graph_entities ((properties->>'session_id'), created_at DESC)
    WHERE label = 'SystemMetricNode';
