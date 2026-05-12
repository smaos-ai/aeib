# Phase 25: Causal Pattern Extraction Engine — Data Contracts

**Status:** COMPLETE (2026-05-11)  
**Tests:** 8/8 passing  
**Implementation:** ✅ Temporal correlation detection, idempotent pattern nodes, instance-level edges

---

## Overview

Phase 25 closes the temporal intelligence gap in the SMAOS graph by detecting and representing **causal patterns**—recurring temporal relationships between observed events (AgentActionNode, AnomalyEventNode, SystemMetricNode). The engine runs as a background task, periodically scanning the graph for event pairs within configurable time windows, creating direct instance-level edges (PRECEDES, COINCIDES_WITH) between correlated entities, and aggregating pattern observations into CorrelationPatternNode entities that track occurrence frequency and confidence scores.

**Key insight:** Individual events alone are isolated facts; temporal patterns reveal systemic behavior. A single expensive action followed by a timeout is noise. Ten expensive actions followed by timeouts within 2 hours is a causal signal.

---

## Intelligence Graph Schema (Relational Foundation)

### New Entity Label: `CorrelationPatternNode`

Represents a detected recurring temporal relationship between two event types for a specific sovereign.

| Property | Type | SQL Type | Notes |
|----------|------|----------|-------|
| `sovereign_id` | UUID | UUID | Sovereign this pattern was detected for |
| `pattern_type` | String | VARCHAR(32) | "action_precedes_anomaly" \| "metric_spike_anomaly" |
| `occurrence_count` | i64 | BIGINT | Times this pattern has been observed |
| `avg_gap_seconds` | f64 | FLOAT | Average temporal gap between source and target |
| `confidence` | f64 | FLOAT | 0.0–1.0, scales with occurrence_count |
| `last_seen_at` | String | TIMESTAMPTZ | ISO 8601, most recent observation |
| `evidence` | serde_json::Value | JSONB | Sample entity pair IDs (source_id, target_id) |

**Confidence formula:**
```
confidence = min(1.0, occurrence_count * 0.2)
```
- 1 observation → 0.2 (weak signal)
- 5 observations → 1.0 (strong signal, saturated)

**Idempotency index (migration 037):**
```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_correlation_pattern_sovereign_type
    ON graph_entities ((properties->>'sovereign_id'), (properties->>'pattern_type'))
    WHERE label = 'CorrelationPatternNode';
```

This composite index ensures one pattern node per (sovereign, pattern_type) pair. Upserts via `ON CONFLICT` update `occurrence_count`, `confidence`, `last_seen_at`, and `evidence` sample.

**Query indices:**
```sql
CREATE INDEX IF NOT EXISTS idx_correlation_pattern_sovereign
    ON graph_entities ((properties->>'sovereign_id'), created_at DESC)
    WHERE label = 'CorrelationPatternNode';
```

---

### New Relationship Types

| Type | Source → Target | Window | Threshold | Cardinality |
|------|-----------------|--------|-----------|-------------|
| `PRECEDES` | AgentActionNode → AnomalyEventNode | 2 hours | cost > 1000 | 1→many (instance-level) |
| `COINCIDES_WITH` | SystemMetricNode → AnomalyEventNode | 1 hour | utilization > 80% | 1→many (instance-level) |

All edges use the existing `idx_graph_rel_src_tgt_type` UNIQUE index for idempotency:
```sql
ON CONFLICT (source_entity_id, target_entity_id, relationship_type) DO NOTHING
```

---

## Rust Data Model

### `CorrelationPatternRecord`

```rust
pub struct CorrelationPatternRecord {
    pub sovereign_id: Uuid,
    pub pattern_type: String,        // "action_precedes_anomaly" | "metric_spike_anomaly"
    pub occurrence_count: i64,
    pub avg_gap_seconds: f64,
    pub confidence: f64,             // min(1.0, occurrence_count * 0.2)
    pub last_seen_at: DateTime<Utc>,
    pub evidence: serde_json::Value, // {"source_id": "...", "target_id": "..."}
}
```

### Query Structures

**ActionAnomalyPair:**
```rust
pub struct ActionAnomalyPair {
    pub action_entity_id: Uuid,
    pub anomaly_entity_id: Uuid,
    pub sovereign_id: Uuid,
    pub gap_seconds: f64,
    pub action_cost: i64,
    pub action_event_type: String,
}
```

**MetricAnomalyPair:**
```rust
pub struct MetricAnomalyPair {
    pub metric_entity_id: Uuid,
    pub anomaly_entity_id: Uuid,
    pub sovereign_id: Uuid,
    pub gap_seconds: f64,
    pub utilization_pct: f64,
}
```

---

## Extraction Algorithms

### Algorithm 1: Action-Precedes-Anomaly (2h window, cost > 1000)

**Trigger condition:**
- AgentActionNode with `cost_incurred > 1000`
- AnomalyEventNode for same `sovereign_id`
- Anomaly detected within 2 hours after action
- No existing PRECEDES edge between the pair

**Action:**
1. Create PRECEDES edge: AgentActionNode → AnomalyEventNode
2. Upsert CorrelationPatternNode: pattern_type="action_precedes_anomaly"
3. Increment occurrence_count, update confidence and last_seen_at

**SQL (simplified):**
```sql
SELECT a.id, an.id, a.properties->>'sovereign_id', gap_seconds, cost, event_type
FROM graph_entities a
JOIN graph_entities an ON an.label = 'AnomalyEventNode'
    AND a.properties->>'sovereign_id' = an.properties->>'sovereign_id'
WHERE a.label = 'AgentActionNode'
  AND a.properties->>'cost_incurred'::bigint > 1000
  AND an.properties->>'detected_at'::timestamptz 
      BETWEEN a.properties->>'scored_at'::timestamptz
      AND a.properties->>'scored_at'::timestamptz + INTERVAL '2 hours'
  AND NOT EXISTS (
      SELECT 1 FROM graph_relationships WHERE source_entity_id = a.id
        AND target_entity_id = an.id AND relationship_type = 'PRECEDES'
  )
```

### Algorithm 2: Metric-Spike-Anomaly (1h window, utilization > 80%)

**Trigger condition:**
- SystemMetricNode with `budget_utilization_pct > 80%`
- AnomalyEventNode for same `sovereign_id`
- Anomaly detected within 1 hour after metric snapshot
- No existing COINCIDES_WITH edge between the pair

**Action:**
1. Create COINCIDES_WITH edge: SystemMetricNode → AnomalyEventNode
2. Upsert CorrelationPatternNode: pattern_type="metric_spike_anomaly"
3. Record sample utilization_pct in evidence

**Semantics:**
Budget pressure (high utilization) correlates with behavioral anomalies. This signal informs recovery scoring: sovereigns under resource constraint are more likely to exhibit timeout spam or revocation patterns.

---

## Background Task

### Function Signature

```rust
pub async fn extract_causal_patterns_once(
    pool: &PgPool,
    since: DateTime<Utc>,
) -> Result<usize, sqlx::Error>
```

**Returns:** Count of edges created in this run.

**Semantics:**
- Queries all event pairs matching detection windows and cost/utilization thresholds since `since` checkpoint
- Skips pairs that already have edges (idempotency)
- Creates edges and upserts pattern nodes
- No errors on duplicate inserts (ON CONFLICT DO NOTHING)

### Ticker Loop

```rust
pub fn start_causal_extractor(pool: Arc<PgPool>, interval: Duration) -> JoinHandle<()>
```

- Boot checkpoint: `NOW() - 5 minutes` (lookback on startup)
- Poll interval: 60 seconds (configurable via parameter)
- Checkpoint advances to `NOW()` after each run (always moves forward, never backfills)
- Fire-and-forget error handling (errors logged but don't crash loop)

**Integration example:**
```rust
let pool = Arc::new(pool);
let extractor = siss_graph_db::causal_extractor::start_causal_extractor(
    pool.clone(),
    Duration::from_secs(60),
);
// Runs in background indefinitely; join handle can be dropped or awaited for shutdown
```

---

## Test Coverage

**Location:** `crates/siss-graph-db/src/causal_extractor.rs` (tests module)

| # | Test | Coverage |
|---|------|----------|
| 1 | `test_detect_action_precedes_anomaly_creates_edge` | Core detection: cost > 1000 + gap < 2h → PRECEDES edge |
| 2 | `test_no_edge_when_gap_exceeds_window` | Temporal boundary: gap > 2h → no edge |
| 3 | `test_no_edge_for_different_sovereign` | Isolation: events from different sovereigns don't correlate |
| 4 | `test_detect_metric_coincides_anomaly_creates_edge` | Metric variant: utilization > 80% + gap < 1h → COINCIDES_WITH |
| 5 | `test_extract_once_creates_correlation_pattern_node` | Pattern node creation and occurrence tracking |
| 6 | `test_extract_once_idempotent` | Re-extraction doesn't duplicate edges or nodes |

**Additional tests** (correlation_pattern_repo.rs):

| # | Test | Coverage |
|---|------|----------|
| 7 | `test_ingest_correlation_pattern_creates_node` | CorrelationPatternNode upsert creates correct JSONB properties |
| 8 | `test_ingest_correlation_pattern_upsert_increments_count` | Idempotent upsert: same (sovereign_id, pattern_type) → occurrence_count++ |

**All 8 tests pass with:**
- PostgreSQL 16 testcontainer
- Full migration suite (037 indexes included)
- Docker-based test isolation

---

## Migration 037

**File:** `crates/siss-graph-db/src/migrations/037_add_phase25_correlation_indexes.sql`

Creates UNIQUE and query indexes for idempotent CorrelationPatternNode upserts:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_correlation_pattern_sovereign_type
    ON graph_entities ((properties->>'sovereign_id'), (properties->>'pattern_type'))
    WHERE label = 'CorrelationPatternNode';

CREATE INDEX IF NOT EXISTS idx_correlation_pattern_sovereign
    ON graph_entities ((properties->>'sovereign_id'), created_at DESC)
    WHERE label = 'CorrelationPatternNode';
```

**Registration:** Added to `migrations/mod.rs` MIGRATIONS array as entry 037.

---

## Integration Points

### With Phase 23-24 Entities

Phase 25 **reads** from three Phase 23-24 entity types (no writes back):

- **AgentActionNode** (Phase 24)
  - Source for PRECEDES edges
  - Filtered by cost_incurred > 1000
  - Temporal anchor: scored_at timestamp
  
- **AnomalyEventNode** (Phase 23)
  - Target for PRECEDES and COINCIDES_WITH edges
  - Filtered by temporal proximity to source
  
- **SystemMetricNode** (Phase 23)
  - Source for COINCIDES_WITH edges
  - Filtered by budget_utilization_pct > 80%
  - Temporal anchor: snapshot_at timestamp

### With Recovery Lifecycle

CorrelationPatternNode can be queried to inform recovery scoring decisions:
- High occurrence_count of action_precedes_anomaly → elevated risk signal
- Metric_spike_anomaly → resource constraint context for Phase 20 scoring

**Example query:**
```sql
SELECT COUNT(*) FROM graph_entities
WHERE label = 'CorrelationPatternNode'
  AND properties->>'sovereign_id' = $1
  AND properties->>'pattern_type' = 'action_precedes_anomaly'
  AND (properties->>'confidence')::float > 0.8
```

---

## Non-Goals (Phase 25)

- **No AMPLIFIES / SUPPRESSES edges** — Deferred to Phase 25.5 for multi-signal correlations
- **No anomaly chain detection** — AnomalyEventNode → RecoveryNode patterns reserved for Phase 26
- **No external anomaly detection** — Uses only Phase 23-24 behavioral anomalies (not third-party signals)
- **No REST/GraphQL projections** — Query via existing `/api/graph/projections/*` endpoints
- **No real-time SSE push** — Batch extraction only; no event stream updates on pattern creation
- **No historical backfill** — Extractor runs from NOW()-5min on boot; past patterns not replayed
- **No tuning UI** — Window size (2h, 1h) and cost thresholds (1000, 80%) are code constants

---

## Phase 26+ Vision

**Anomaly Chain Detection:**
- Detect sequences: AnomalyEventNode → AnomalyEventNode → RecoveryNode
- Example: dispute_spam → timeout_spam → recovery_entered (3-event chain)
- Create LEADS_TO edges: AnomalyEventNode → AnomalyEventNode

**Advanced Signals (AMPLIFIES / SUPPRESSES):**
- Detect signal magnitude relationships
- Example: High slashing → amplifies recovery difficulty; settlement → suppresses anomaly detection
- Create edges: SignalNode → CorrelationPatternNode

**Cockpit Integration:**
- Timeline view: correlated events linked with arrows
- Pattern heatmap: (sovereign, pattern_type) matrix with confidence scores
- Risk dashboard: sovereigns with > 3 high-confidence patterns flagged

---

**Last Updated:** 2026-05-11 | **By:** Claude Haiku 4.5
