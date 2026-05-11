# Phase 26: Anomaly Chain Detection — Data Contracts

**Status:** DESIGN (2026-05-11)  
**Tests:** 0/8 pending  
**Implementation:** Ready for build sequence

---

## Overview

Phase 26 detects **temporal anomaly chains**—recurring sequences where one anomaly type consistently precedes another within a time window. When a sovereign experiences `dispute_spam` followed by `timeout_spam` within 4 hours, that is not a coincidence; it is a behavioral pattern that reflects deeper systemic issues (escalating behavioral problems under resource or delegation pressure).

The engine runs as a background task, periodically scanning the graph for anomaly pairs where:
- Both events belong to the same sovereign
- Events are different anomaly types (not repeated identical anomalies)
- Second event occurs within configurable window (4 hours default) after first
- No existing LEADS_TO edge between the pair

For each detected pair, Phase 26:
1. Creates a LEADS_TO edge: `AnomalyEventNode → AnomalyEventNode` (instance-level)
2. Upserts an `AnomalyChainNode` aggregate tracking occurrence count and confidence

**Key insight:** Individual anomalies are signals; chained anomalies are stories. "This sovereign triggered timeout spam" is a fact. "This sovereign consistently goes from dispute spam to timeout spam" is a causal narrative.

---

## Intelligence Graph Schema

### New Entity Label: `AnomalyChainNode`

Represents a detected recurring two-step anomaly sequence for a specific sovereign.

| Property | Type | SQL Type | Phase 26 Notes |
|----------|------|----------|---|
| `sovereign_id` | UUID | UUID | Sovereign this chain was detected for |
| `chain_type` | String | VARCHAR(64) | Ordered string: "dispute_spam→timeout_spam" |
| `chain_length` | i64 | BIGINT | Always 2 (Phase 26 scope: only 2-hop chains) |
| `start_anomaly_type` | String | VARCHAR(32) | "dispute_spam" \| "timeout_spam" \| "revocation_pattern" |
| `end_anomaly_type` | String | VARCHAR(32) | (same enum) |
| `occurrence_count` | i64 | BIGINT | Times this chain pattern has been observed |
| `avg_elapsed_hours` | f64 | FLOAT | Average elapsed time from start → end across occurrences |
| `confidence` | f64 | FLOAT | 0.0–1.0, scales with occurrence_count (formula: min(1.0, count * 0.2)) |
| `last_seen_at` | String | TIMESTAMPTZ | ISO 8601, most recent chain occurrence timestamp |
| `evidence` | JSONB | JSONB | Sample pair: `{"first_id": "...", "second_id": "..."}` |

**Idempotency index (migration 038):**
```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_anomaly_chain_sovereign_type
    ON graph_entities ((properties->>'sovereign_id'), (properties->>'chain_type'))
    WHERE label = 'AnomalyChainNode';
```

One AnomalyChainNode per (sovereign_id, chain_type) pair. Upserts via `ON CONFLICT` update `occurrence_count`, `avg_elapsed_hours`, `confidence`, `last_seen_at`, and `evidence`.

**Query index:**
```sql
CREATE INDEX IF NOT EXISTS idx_anomaly_chain_sovereign
    ON graph_entities ((properties->>'sovereign_id'), created_at DESC)
    WHERE label = 'AnomalyChainNode';
```

---

### New Relationship Types

| Type | Source → Target | Semantics | Cardinality |
|------|-----------------|-----------|-------------|
| `LEADS_TO` | AnomalyEventNode → AnomalyEventNode | First anomaly was followed by second anomaly (instance-level temporal link) | 1→many |
| `CHAINS_FOR` | AnomalyChainNode → SovereignNode | Aggregate chain belongs to this sovereign | 1→1 |

Both use existing `idx_graph_rel_src_tgt_type` UNIQUE index for idempotency.

---

## Rust Data Model

### `AnomalyChainRecord`

```rust
pub struct AnomalyChainRecord {
    pub sovereign_id: Uuid,
    pub chain_type: String,           // "dispute_spam→timeout_spam"
    pub chain_length: i64,            // Always 2 in Phase 26
    pub start_anomaly_type: String,
    pub end_anomaly_type: String,
    pub occurrence_count: i64,
    pub avg_elapsed_hours: f64,
    pub confidence: f64,              // min(1.0, occurrence_count * 0.2)
    pub last_seen_at: DateTime<Utc>,
    pub evidence: serde_json::Value,  // {"first_id": "...", "second_id": "..."}
}
```

### Query Structure

```rust
pub(crate) struct AnomalyChainPair {
    pub first_anomaly_id: Uuid,
    pub second_anomaly_id: Uuid,
    pub sovereign_id: Uuid,
    pub first_type: String,
    pub second_type: String,
    pub elapsed_hours: f64,
}

pub(crate) async fn fetch_anomaly_chain_pairs(
    pool: &PgPool,
    since: DateTime<Utc>,
    window_hours: i64,        // default: 4
) -> Result<Vec<AnomalyChainPair>, sqlx::Error>
```

---

## Chain Detection Algorithm

### Trigger Conditions (4-hour window)

For each sovereign:
1. Find AnomalyEventNode A with `detected_at > since`
2. Find AnomalyEventNode B for same sovereign with:
   - `anomaly_type` ≠ A.anomaly_type (different types only)
   - `detected_at` between A.detected_at and A.detected_at + 4 hours
   - No existing LEADS_TO edge from A to B
3. Create LEADS_TO edge: A → B
4. Upsert AnomalyChainNode: pattern_type = "A_type→B_type"

### SQL Query (simplified)

```sql
SELECT
    a1.id,                                     -- first_anomaly_id
    a2.id,                                     -- second_anomaly_id
    (a1.properties->>'sovereign_id')::uuid,    -- sovereign_id
    a1.properties->>'anomaly_type',            -- first_type
    a2.properties->>'anomaly_type',            -- second_type
    EXTRACT(EPOCH FROM (
        (a2.properties->>'detected_at')::timestamptz -
        (a1.properties->>'detected_at')::timestamptz
    ))::float / 3600.0                         -- elapsed_hours
FROM graph_entities a1
JOIN graph_entities a2 ON a2.label = 'AnomalyEventNode'
    AND (a2.properties->>'sovereign_id') = (a1.properties->>'sovereign_id')
    AND a2.properties->>'anomaly_type' != a1.properties->>'anomaly_type'
WHERE a1.label = 'AnomalyEventNode'
  AND (a1.properties->>'detected_at')::timestamptz > $1  -- since
  AND (a2.properties->>'detected_at')::timestamptz BETWEEN
      (a1.properties->>'detected_at')::timestamptz
      AND (a1.properties->>'detected_at')::timestamptz + (4 * INTERVAL '1 hour')
  AND NOT EXISTS (
      SELECT 1 FROM graph_relationships r
      WHERE r.source_entity_id = a1.id
        AND r.target_entity_id = a2.id
        AND r.relationship_type = 'LEADS_TO'
  )
ORDER BY a1.created_at ASC
LIMIT 200
```

Chain type derived in Rust: `format!("{}→{}", first_type, second_type)`

---

## Background Extractor

### Function Signature

```rust
pub async fn extract_anomaly_chains_once(
    pool: &PgPool,
    since: DateTime<Utc>,
) -> Result<usize, sqlx::Error>
```

Returns count of LEADS_TO edges created in this run.

### Ticker Loop

```rust
pub fn start_chain_extractor(pool: Arc<PgPool>, interval: Duration) -> JoinHandle<()>
```

- Boot checkpoint: `NOW() - 5 minutes` (lookback on startup)
- Default poll interval: 60 seconds (configurable)
- Checkpoint always advances to `NOW()` after each run
- Error handling: fire-and-forget (errors logged but don't crash loop)

**Integration pattern:** Same as Phase 25 causal_extractor.rs

---

## Test Coverage

**Location:** `crates/siss-graph-db/src/chain_extractor.rs` (tests module)

| # | Test | Coverage |
|---|------|----------|
| 1 | `test_detect_anomaly_leads_to_anomaly_creates_edge` | Core detection: different types, within 4h → LEADS_TO edge |
| 2 | `test_no_edge_when_gap_exceeds_window` | Temporal boundary: gap > 4h → no edge |
| 3 | `test_no_edge_for_same_anomaly_type` | Type constraint: two dispute_spam → no LEADS_TO |
| 4 | `test_no_edge_for_different_sovereign` | Isolation: anomalies from different sovereigns → no edge |
| 5 | `test_extract_chains_once_creates_chain_node` | Chain node creation: AnomalyChainNode appears in graph |
| 6 | `test_extract_chains_idempotent` | Re-extraction → same edge count, no duplicates |

**Additional tests** (anomaly_chain_repo.rs):

| # | Test | Coverage |
|---|------|----------|
| 7 | `test_ingest_anomaly_chain_creates_node` | AnomalyChainNode upsert creates correct JSONB properties |
| 8 | `test_ingest_anomaly_chain_upsert_increments_count` | Same (sovereign_id, chain_type) → occurrence_count++, same UUID |

**All 8 tests:** Passing (TBD)

---

## Migration 038

**File:** `crates/siss-graph-db/src/migrations/038_add_phase26_chain_indexes.sql`

Creates UNIQUE and query indexes for idempotent AnomalyChainNode upserts:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_anomaly_chain_sovereign_type
    ON graph_entities ((properties->>'sovereign_id'), (properties->>'chain_type'))
    WHERE label = 'AnomalyChainNode';

CREATE INDEX IF NOT EXISTS idx_anomaly_chain_sovereign
    ON graph_entities ((properties->>'sovereign_id'), created_at DESC)
    WHERE label = 'AnomalyChainNode';
```

---

## Integration with Phase 23-25

### Reads from Phase 25

Phase 26 **reads** from AnomalyEventNode (Phase 23 entity, ingested by Phase 24):
- Source for LEADS_TO pair detection
- Properties used: `sovereign_id`, `anomaly_type`, `detected_at`
- Timestamps compared: Phase 25 causal extraction uses Phase 23 anomaly detected_at

### Writes to Graph

- **LEADS_TO edges**: Between existing AnomalyEventNode pairs (no new entity types created at instance level)
- **AnomalyChainNode**: New aggregate entity tracking chains per sovereign
- **CHAINS_FOR edges**: From AnomalyChainNode to SovereignNode

### Query Patterns

Example: "List all chain patterns for sovereign X":
```sql
SELECT properties FROM graph_entities
WHERE label = 'AnomalyChainNode'
  AND properties->>'sovereign_id' = '<sovereign_uuid>'
ORDER BY created_at DESC;
```

Example: "Show the causal chain leading to a recovery":
```sql
-- Phase 27 extends this with anomaly→recovery traversal
SELECT a1.properties->>'anomaly_type',
       a2.properties->>'anomaly_type',
       (a2.properties->>'detected_at')::timestamptz - (a1.properties->>'detected_at')::timestamptz
FROM graph_entities a1
JOIN graph_relationships r ON r.source_entity_id = a1.id AND r.relationship_type = 'LEADS_TO'
JOIN graph_entities a2 ON a2.id = r.target_entity_id
WHERE a1.properties->>'sovereign_id' = '<sovereign_uuid>';
```

---

## Non-Goals (Phase 26)

- **No anomaly → RecoveryNode detection** — RecoveryNode does not store sovereign_id in properties; requires cross-entity graph join; deferred to Phase 27
- **No 3-hop chains or chain-of-chains** — Phase 26 limited to 2-hop (AnomalyEventNode → AnomalyEventNode); Phase 27 will enable cascading chains
- **No AMPLIFIES / SUPPRESSES edges** — Pure sequential LEADS_TO relationships only
- **No REST/GraphQL projections** — Chain queries via existing `/api/graph/projections/*` infrastructure
- **No real-time SSE push** — Batch extraction only
- **No historical backfill** — Extractor runs from NOW()-5min on boot
- **No configurable thresholds via API** — Window size (4h) and type constraints are code constants; requires recompile to adjust

---

## Phase 27+ Vision

**Anomaly → Recovery Correlation:**
- Detect PRECEDED_RECOVERY edges: AnomalyEventNode → RecoveryNode
- Requires graph join through SovereignNode (RecoveryNode lacks sovereign_id)
- Enables: "Which anomalies triggered this sovereign's recovery?"

**Chain Extension:**
- 3-hop chains: AnomalyEventNode → AnomalyEventNode → AnomalyEventNode
- Recursive chain detection: track chains of chains
- Enable longer causal narratives

**Risk Scoring Integration:**
- AnomalyChainNode confidence → input to recovery risk calculation
- Sovereigns with high-confidence chains → elevated monitoring
- Anomaly patterns feed into Phase 20 scoring system

**Cockpit Enhancements:**
- Timeline view: LEADS_TO edges visualized as arrows between anomalies
- Chain browser: "Show all chains for this sovereign"
- Risk trajectory: time-series of chain occurrence frequency

---

**Last Updated:** 2026-05-11 | **By:** Claude Haiku 4.5
