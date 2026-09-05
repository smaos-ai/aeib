# Phase 23: Unified Observability Layer — Data Contracts

**Status:** COMPLETE (2026-05-11)  
**Tests:** 11/11 passing  
**Schema Lock:** ✅ Intelligence graph schemas finalized

---

## Overview

Phase 23 closes the observability gap in SMAOS by dual-writing behavioral telemetry (behavior_events, behavioral_anomalies) into the intelligence graph. This enables:

- **Real-time behavior tracking:** Agent actions queryable as graph entities (AgentActionNode)
- **Anomaly visibility:** Detected anomalies discoverable via DETECTED_IN edges to sovereigns
- **Budget monitoring:** System metrics (SystemMetricNode) track token consumption during recovery
- **Projection readiness:** All three entity types support /api/graph/projections/* views

---

## Intelligence Graph Schema (Relational Fallback)

### Node Labels

#### **AgentActionNode** (behavior_events → graph)

| Property | Type | SQL Type | Idempotency |
|----------|------|----------|-------------|
| behavior_event_id | UUID | UUID | **PRIMARY** |
| session_id | UUID | UUID | Indexed |
| persona_id | UUID | UUID | - |
| sovereign_id | UUID | UUID | FK edge target |
| event_type | String | VARCHAR(32) | - |
| tier_before | i16 | SMALLINT | - |
| tier_after | i16 | SMALLINT | - |
| cost_incurred | i64 | BIGINT | - |
| lineage_safe | bool | BOOLEAN | - |
| scored_at | DateTime<Utc> | TIMESTAMPTZ | Checkpoint |

**Idempotency Index:**
```sql
CREATE UNIQUE INDEX idx_agent_action_behavior_event_id
    ON graph_entities ((properties->>'behavior_event_id'))
    WHERE label = 'AgentActionNode';
```

**Query Index:**
```sql
CREATE INDEX idx_agent_action_session_id
    ON graph_entities ((properties->>'session_id'))
    WHERE label = 'AgentActionNode';
```

---

#### **AnomalyEventNode** (behavioral_anomalies → graph)

| Property | Type | SQL Type | Notes |
|----------|------|----------|-------|
| anomaly_db_id | UUID | UUID | **PRIMARY** (idempotency key) |
| sovereign_id | UUID | UUID | FK edge target |
| anomaly_type | String | VARCHAR(32) | dispute_spam / timeout_spam / revocation_pattern |
| severity | String | VARCHAR(16) | low / medium / high / critical |
| event_count | i64 | BIGINT | Events in window |
| window_hours | i64 | BIGINT | Observation window |
| evidence | serde_json::Value | JSONB | Raw anomaly data |
| detected_at | DateTime<Utc> | TIMESTAMPTZ | Checkpoint |

**Idempotency Index:**
```sql
CREATE UNIQUE INDEX idx_anomaly_event_db_id
    ON graph_entities ((properties->>'anomaly_db_id'))
    WHERE label = 'AnomalyEventNode';
```

**Query Index:**
```sql
CREATE INDEX idx_anomaly_event_sovereign_detected
    ON graph_entities ((properties->>'sovereign_id'), created_at DESC)
    WHERE label = 'AnomalyEventNode';
```

---

#### **SystemMetricNode** (token budget snapshots)

| Property | Type | SQL Type | Notes |
|----------|------|----------|-------|
| session_id | UUID | UUID | Part of **composite idempotency key** |
| sovereign_id | UUID | UUID | FK edge target |
| token_budget_remaining | i64 | BIGINT | Remaining tokens |
| token_budget_consumed | i64 | BIGINT | Consumed in session |
| budget_utilization_pct | f64 | FLOAT | consumed / (remaining + consumed) × 100 |
| snapshot_at | DateTime<Utc> | TIMESTAMPTZ | Part of **composite idempotency key** |

**Idempotency Index (composite key):**
```sql
CREATE UNIQUE INDEX idx_system_metric_session_snapshot
    ON graph_entities ((properties->>'session_id'), (properties->>'snapshot_at'))
    WHERE label = 'SystemMetricNode';
```

**Query Index:**
```sql
CREATE INDEX idx_system_metric_session_time
    ON graph_entities ((properties->>'session_id'), created_at DESC)
    WHERE label = 'SystemMetricNode';
```

---

### Relationship Types

| Type | Source → Target | Semantics | Cardinality |
|------|-----------------|-----------|-------------|
| **EMITTED_BY** | AgentActionNode → SovereignNode | Action performed by sovereign | 1→1 |
| **EMITTED_BY** | SystemMetricNode → SovereignNode | Metric belongs to sovereign | 1→1 |
| **DETECTED_IN** | AnomalyEventNode → SovereignNode | Anomaly detected for sovereign | 1→1 |

**Edge Constraint:**
```sql
CREATE UNIQUE INDEX idx_graph_rel_src_tgt_type
    ON graph_relationships (source_entity_id, target_entity_id, relationship_type);
```

---

## Rust Data Model

**File:** `crates/siss-graph-db/src/repo/observability_repo.rs`

### Records

```rust
#[derive(Debug, Clone)]
pub struct AgentActionIngestionRecord {
    pub behavior_event_id: Uuid,
    pub session_id: Uuid,
    pub persona_id: Uuid,
    pub sovereign_id: Uuid,
    pub event_type: String,           // VARCHAR(32): refresh_success, delegation_created, …
    pub tier_before: i16,
    pub tier_after: i16,
    pub cost_incurred: i64,
    pub lineage_safe: bool,
    pub scored_at: DateTime<Utc>,
}

#[derive(Debug, Clone)]
pub struct AnomalyIngestionRecord {
    pub anomaly_db_id: Uuid,
    pub sovereign_id: Uuid,
    pub anomaly_type: String,         // "dispute_spam" | "timeout_spam" | "revocation_pattern"
    pub severity: String,             // "low" | "medium" | "high" | "critical"
    pub event_count: i64,
    pub window_hours: i64,
    pub evidence: serde_json::Value,  // Raw anomaly JSON
    pub detected_at: DateTime<Utc>,
}

#[derive(Debug, Clone)]
pub struct SystemMetricIngestionRecord {
    pub session_id: Uuid,
    pub sovereign_id: Uuid,
    pub token_budget_remaining: i64,
    pub token_budget_consumed: i64,
    pub budget_utilization_pct: f64,
    pub snapshot_at: DateTime<Utc>,
}
```

### Ingestion Functions

```rust
/// Returns node ID on success or repeat; idempotent via behavior_event_id
pub async fn ingest_agent_action(
    pool: &PgPool,
    record: &AgentActionIngestionRecord,
) -> Result<Uuid, sqlx::Error>

/// Returns node ID on success or repeat; idempotent via anomaly_db_id
pub async fn ingest_anomaly_event(
    pool: &PgPool,
    record: &AnomalyIngestionRecord,
) -> Result<Uuid, sqlx::Error>

/// Returns node ID on success or repeat; idempotent via (session_id, snapshot_at)
pub async fn ingest_system_metric(
    pool: &PgPool,
    record: &SystemMetricIngestionRecord,
) -> Result<Uuid, sqlx::Error>
```

---

## Polling Watcher (observability_watcher.rs)

### Configuration

```rust
pub const DEFAULT_POLL_INTERVAL: Duration = Duration::from_secs(30);
pub const BOOT_LOOKBACK: Duration = Duration::from_secs(300);  // 5 minutes on boot
```

### Poll Queries

**behavior_events:**
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

**behavioral_anomalies:**
```sql
SELECT ba.id, ba.sovereign_id, ba.anomaly_type, ba.severity,
       ba.event_count, ba.window_hours, ba.evidence, ba.detected_at
FROM behavioral_anomalies ba
WHERE ba.detected_at > $1
ORDER BY ba.detected_at ASC
LIMIT 500
```

### Checkpoint Strategy

| Rule | Behavior |
|------|----------|
| **Advance on rows** | Update checkpoint to max(scored_at / detected_at) when poll returns rows |
| **Freeze on empty** | Leave checkpoint unchanged if poll returns no rows (prevents skipping fresh inserts) |
| **Boot backfill** | On startup: checkpoint = NOW() - 5min; ingests last 5min of events |

---

## SSE Event Broadcaster

**Moved:** `siss-agent-card/src/events.rs` → `siss-graph-db/src/recovery_event_broadcaster.rs`

**Reason:** Resolve circular dependency (recovery_sweep_scheduler needs to emit)

### Event Enum

```rust
#[derive(Debug, Clone, serde::Serialize)]
pub enum RecoveryEvent {
    RecoveryEntered {
        sovereign_id: String,
        score_at_entry: i16,
        timestamp: String,
    },
    RecoveryProgressed {
        sovereign_id: String,
        weeks_elapsed: u32,
        current_score: i16,
        timestamp: String,
    },
    RecoveryCompleted {
        sovereign_id: String,
        exit_status: String,       // "success" | "failure"
        score_at_exit: i16,
        timestamp: String,
    },
    RecoveryViolation {
        sovereign_id: String,
        reason: String,
        new_status: String,        // "quarantined"
        timestamp: String,
    },
    ScoringDecision {
        sovereign_id: String,
        score: i16,
        weeks_elapsed: u32,
        slash_penalty: i16,
        anomaly_penalty: i16,
        settlement_bonus: i16,
        timestamp: String,
    },
}
```

### Broadcaster

```rust
#[derive(Clone)]
pub struct RecoveryEventBroadcaster {
    tx: broadcast::Sender<RecoveryEvent>,
}

impl RecoveryEventBroadcaster {
    pub fn new() -> Self
    pub fn emit(&self, event: RecoveryEvent)
    pub fn subscribe(&self) -> broadcast::Receiver<RecoveryEvent>
}
```

---

## Integration Points

### recovery_sweep_scheduler

```rust
pub fn start_recovery_sweep(
    pool: PgPool,
    interval: Duration,
    broadcaster: Option<Arc<RecoveryEventBroadcaster>>,  // NEW
) -> JoinHandle<()>
```

Emits `ScoringDecision` event when sovereigns advance or complete recovery.

### intelligence_graph_repo

```rust
pub(crate) async fn get_or_create_sovereign_node(  // Changed from private to pub(crate)
    pool: &PgPool,
    sovereign_id: Uuid,
) -> Result<Uuid, sqlx::Error>
```

Used by all three ingestion functions to create/link sovereigns.

---

## Test Coverage

**Location:** `crates/siss-graph-db/src/repo/observability_repo.rs` + `observability_watcher.rs`

| Test | Purpose | Status |
|------|---------|--------|
| test_ingest_agent_action_creates_graph_entity | Verify AgentActionNode creation | ✅ |
| test_ingest_agent_action_creates_emitted_by_edge | Verify EMITTED_BY edge | ✅ |
| test_ingest_agent_action_is_idempotent | Duplicate insert → 1 row | ✅ |
| test_ingest_agent_action_returns_same_uuid_on_repeat | Same ID both calls | ✅ |
| test_ingest_anomaly_event_creates_graph_entity | Verify AnomalyEventNode creation | ✅ |
| test_ingest_anomaly_event_creates_detected_in_edge | Verify DETECTED_IN edge | ✅ |
| test_ingest_anomaly_event_is_idempotent | Duplicate insert → 1 row | ✅ |
| test_ingest_system_metric_creates_entity_and_edge | Verify SystemMetricNode + EMITTED_BY | ✅ |
| test_ingest_system_metric_idempotent_on_same_snapshot | Same (session_id, snapshot_at) → 1 row | ✅ |
| test_poll_behavior_events_once_ingests_new_row | Poll workflow end-to-end | ✅ |
| test_poll_skips_sessions_without_sovereign_id | Null guard in SQL | ✅ |

---

## Phase 24 Dependencies

**These data contracts are locked and available for Phase 24:**

✅ GraphQL schema for AgentActionNode, AnomalyEventNode, SystemMetricNode  
✅ REST projection endpoints: `/api/graph/projections/agent-actions`, `/api/graph/projections/anomalies`  
✅ Cockpit dashboard widgets: action timeline, anomaly heatmap, budget gauge  
✅ Advanced queries: "Which sovereigns had timeout_spam in last 24h?" (DETECTED_IN traversal)  
✅ Recovery lifecycle: Correlate SystemMetricNode budget drops with RecoveryProgressed events  

---

**Last Updated:** 2026-05-11 | **By:** Claude Haiku 4.5
