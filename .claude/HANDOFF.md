# HANDOFF.md — Phase 23 Unified Observability Layer

**Date:** 2026-05-11  
**Status:** Phase 23 COMPLETE — 11/11 tests passing, merged to main  
**Next Phase:** Phase 24 (TBD)

---

## Phase 23 Deliverables

### 1. Intelligence Graph Schemas (Apache AGE / Relational Fallback)

**New Node Labels:**
```
AgentActionNode
├── Key property: behavior_event_id (UUID) — idempotency
├── Properties: {
│   ├── behavior_event_id: UUID
│   ├── session_id: UUID
│   ├── persona_id: UUID
│   ├── sovereign_id: UUID
│   ├── event_type: VARCHAR(32) [refresh_success, delegation_created, ...]
│   ├── tier_before: SMALLINT
│   ├── tier_after: SMALLINT
│   ├── cost_incurred: BIGINT
│   ├── lineage_safe: BOOLEAN
│   └── scored_at: TIMESTAMPTZ
│   }
└── Idempotency: UNIQUE INDEX on (properties->>'behavior_event_id') WHERE label='AgentActionNode'

AnomalyEventNode
├── Key property: anomaly_db_id (UUID) — idempotency
├── Properties: {
│   ├── anomaly_db_id: UUID
│   ├── sovereign_id: UUID
│   ├── anomaly_type: VARCHAR [dispute_spam, timeout_spam, revocation_pattern]
│   ├── severity: VARCHAR [low, medium, high, critical]
│   ├── event_count: BIGINT
│   ├── window_hours: BIGINT
│   ├── evidence: JSONB
│   └── detected_at: TIMESTAMPTZ
│   }
└── Idempotency: UNIQUE INDEX on (properties->>'anomaly_db_id') WHERE label='AnomalyEventNode'

SystemMetricNode
├── Key properties: (session_id, snapshot_at) — idempotency
├── Properties: {
│   ├── session_id: UUID
│   ├── sovereign_id: UUID
│   ├── token_budget_remaining: BIGINT
│   ├── token_budget_consumed: BIGINT
│   ├── budget_utilization_pct: FLOAT
│   └── snapshot_at: TIMESTAMPTZ
│   }
└── Idempotency: UNIQUE INDEX on (properties->>'session_id', properties->>'snapshot_at') WHERE label='SystemMetricNode'
```

**New Relationship Types:**
```
EMITTED_BY: AgentActionNode → SovereignNode | SystemMetricNode → SovereignNode
DETECTED_IN: AnomalyEventNode → SovereignNode
```

**Indexes (Migration 036):**
```sql
-- Idempotency (unique, partial)
CREATE UNIQUE INDEX idx_agent_action_behavior_event_id 
  ON graph_entities ((properties->>'behavior_event_id')) 
  WHERE label = 'AgentActionNode';

CREATE UNIQUE INDEX idx_anomaly_event_db_id 
  ON graph_entities ((properties->>'anomaly_db_id')) 
  WHERE label = 'AnomalyEventNode';

CREATE UNIQUE INDEX idx_system_metric_session_snapshot 
  ON graph_entities ((properties->>'session_id'), (properties->>'snapshot_at')) 
  WHERE label = 'SystemMetricNode';

-- Query (for projection views)
CREATE INDEX idx_agent_action_session_id 
  ON graph_entities ((properties->>'session_id')) 
  WHERE label = 'AgentActionNode';

CREATE INDEX idx_anomaly_event_sovereign_detected 
  ON graph_entities ((properties->>'sovereign_id'), created_at DESC) 
  WHERE label = 'AnomalyEventNode';

CREATE INDEX idx_system_metric_session_time 
  ON graph_entities ((properties->>'session_id'), created_at DESC) 
  WHERE label = 'SystemMetricNode';
```

---

### 2. Rust Data Contracts (siss-graph-db)

**Location:** `crates/siss-graph-db/src/repo/observability_repo.rs`

```rust
pub struct AgentActionIngestionRecord {
    pub behavior_event_id: Uuid,
    pub session_id: Uuid,
    pub persona_id: Uuid,
    pub sovereign_id: Uuid,
    pub event_type: String,
    pub tier_before: i16,
    pub tier_after: i16,
    pub cost_incurred: i64,
    pub lineage_safe: bool,
    pub scored_at: DateTime<Utc>,
}

pub struct AnomalyIngestionRecord {
    pub anomaly_db_id: Uuid,
    pub sovereign_id: Uuid,
    pub anomaly_type: String,
    pub severity: String,
    pub event_count: i64,
    pub window_hours: i64,
    pub evidence: serde_json::Value,
    pub detected_at: DateTime<Utc>,
}

pub struct SystemMetricIngestionRecord {
    pub session_id: Uuid,
    pub sovereign_id: Uuid,
    pub token_budget_remaining: i64,
    pub token_budget_consumed: i64,
    pub budget_utilization_pct: f64,
    pub snapshot_at: DateTime<Utc>,
}
```

**Public Functions:**
```rust
pub async fn ingest_agent_action(pool: &PgPool, record: &AgentActionIngestionRecord) -> Result<Uuid, sqlx::Error>
pub async fn ingest_anomaly_event(pool: &PgPool, record: &AnomalyIngestionRecord) -> Result<Uuid, sqlx::Error>
pub async fn ingest_system_metric(pool: &PgPool, record: &SystemMetricIngestionRecord) -> Result<Uuid, sqlx::Error>
```

---

### 3. Polling Watcher (observability_watcher.rs)

**Constants:**
```rust
pub const DEFAULT_POLL_INTERVAL: Duration = Duration::from_secs(30);
pub const BOOT_LOOKBACK: Duration = Duration::from_secs(300);  // 5 minutes
```

**Polling SQL (behavior_events):**
```sql
SELECT be.id, be.session_id, s.active_persona_id, s.origin_sovereign_id,
       be.event_type, be.tier_before, be.tier_after, be.cost_incurred,
       be.lineage_safe, be.scored_at
FROM behavior_events be
JOIN sessions s ON s.id = be.session_id
WHERE be.scored_at > $1
  AND s.origin_sovereign_id IS NOT NULL
ORDER BY be.scored_at ASC
LIMIT 500
```

**Polling SQL (behavioral_anomalies):**
```sql
SELECT ba.id, ba.sovereign_id, ba.anomaly_type, ba.severity,
       ba.event_count, ba.window_hours, ba.evidence, ba.detected_at
FROM behavioral_anomalies ba
WHERE ba.detected_at > $1
ORDER BY ba.detected_at ASC
LIMIT 500
```

**Watcher Signature:**
```rust
pub fn start_observability_watcher(
    pool: Arc<PgPool>,
    poll_interval: Duration,
) -> JoinHandle<()>
```

---

### 4. SSE Event Broadcaster (recovery_event_broadcaster.rs)

**Moved from:** `siss-agent-card/src/events.rs` → `siss-graph-db/src/recovery_event_broadcaster.rs`

**Reason:** Resolve circular dependency (recovery_sweep_scheduler in siss-graph-db needs to emit events)

**Event Schema:**
```rust
#[derive(Debug, Clone, serde::Serialize)]
pub enum RecoveryEvent {
    RecoveryEntered { sovereign_id: String, score_at_entry: i16, timestamp: String },
    RecoveryProgressed { sovereign_id: String, weeks_elapsed: u32, current_score: i16, timestamp: String },
    RecoveryCompleted { sovereign_id: String, exit_status: String, score_at_exit: i16, timestamp: String },
    RecoveryViolation { sovereign_id: String, reason: String, new_status: String, timestamp: String },
    ScoringDecision { sovereign_id: String, score: i16, weeks_elapsed: u32, slash_penalty: i16, anomaly_penalty: i16, settlement_bonus: i16, timestamp: String },
}

pub struct RecoveryEventBroadcaster {
    tx: broadcast::Sender<RecoveryEvent>,
}
```

**Re-export in siss-agent-card:**
```rust
pub use siss_graph_db::recovery_event_broadcaster::{RecoveryEvent, RecoveryEventBroadcaster};
pub type EventBroadcaster = RecoveryEventBroadcaster;  // Backward compat
```

---

### 5. Modified Modules

**crates/siss-graph-db/src/repo/intelligence_graph_repo.rs:**
- Changed `get_or_create_sovereign_node` from `async fn` to `pub(crate) async fn`
- Allows observability_repo to reuse sovereign node creation

**crates/siss-graph-db/src/recovery_sweep_scheduler.rs:**
- Updated signature: `pub fn start_recovery_sweep(pool: PgPool, interval: Duration, broadcaster: Option<Arc<RecoveryEventBroadcaster>>) -> JoinHandle<()>`
- Now emits aggregate sweep events when sovereigns advance/complete recovery

---

## Test Coverage (Phase 23)

**File:** `crates/siss-graph-db/src/repo/observability_repo.rs`  
**Count:** 9 tests, all passing

```
✓ test_ingest_agent_action_creates_graph_entity
✓ test_ingest_agent_action_creates_emitted_by_edge
✓ test_ingest_agent_action_is_idempotent
✓ test_ingest_agent_action_returns_same_uuid_on_repeat
✓ test_ingest_anomaly_event_creates_graph_entity
✓ test_ingest_anomaly_event_creates_detected_in_edge
✓ test_ingest_anomaly_event_is_idempotent
✓ test_ingest_system_metric_creates_entity_and_edge
✓ test_ingest_system_metric_idempotent_on_same_snapshot
```

**File:** `crates/siss-graph-db/src/observability_watcher.rs`  
**Count:** 2 tests, all passing

```
✓ test_poll_behavior_events_once_ingests_new_row
✓ test_poll_skips_sessions_without_sovereign_id
```

---

## Phase 24 Prerequisites

### Data Contracts Locked In:
✅ Graph entity schemas (AgentActionNode, AnomalyEventNode, SystemMetricNode)  
✅ Polling SQL queries (behavior_events, behavioral_anomalies)  
✅ Idempotency strategy (partial unique indexes on JSONB properties)  
✅ Ingestion function signatures (3 async fn, standard Result<Uuid, sqlx::Error>)  
✅ Watcher constants (30s poll, 5min boot lookback, 500-row limit)  

### Ready for Phase 24:
- **Real-time projection views** — Query AgentActionNode + AnomalyEventNode + SystemMetricNode via existing `/api/graph/projections/*` endpoints
- **Cockpit dashboard updates** — Display observability metrics in intelligence cockpit
- **Advanced anomaly correlation** — Cross-reference anomalies with agent actions to detect patterns
- **Recovery lifecycle tracking** — Leverage SystemMetricNode for token budget monitoring during recovery
- **Performance optimization** — Tune polling interval, batch ingestion, add query plan indexes

---

## Critical Notes for Next Agent

1. **Idempotency is strict:** Each ingestion function returns the SAME Uuid on repeat calls with identical behavior_event_id / anomaly_db_id / (session_id, snapshot_at)
2. **Checkpoint logic:** Watcher only advances checkpoint when rows are returned; empty poll leaves checkpoint unchanged to avoid skipping fresh inserts
3. **Sovereign null guard:** Poll SQL filters at database level (WHERE origin_sovereign_id IS NOT NULL) to prevent orphaned nodes
4. **Broadcaster is optional:** recovery_sweep_scheduler accepts `Option<Arc<RecoveryEventBroadcaster>>` — gracefully handles when no SSE listener is configured
5. **No historical back-fill:** Watcher boots with 5min lookback; older events are ignored (intentional design)

---

## Git State

**Commit:** f90f393 — Phase 23: Unified Observability Layer — Complete Implementation  
**Branch:** main (merged, not pushed to remote)  
**Test Status:** 11/11 passing on main  
**Build Status:** ✅ cargo check clean, ✅ cargo fmt clean, ✅ no clippy warnings on new code

---

**Prepared by:** Claude Haiku 4.5  
**For:** Next agent session (Phase 24 and beyond)
