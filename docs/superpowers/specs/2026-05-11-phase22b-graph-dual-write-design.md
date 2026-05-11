# Phase 22b: Intelligence Graph Dual-Write — Specification

**Date:** 2026-05-11  
**Status:** Design  
**Authors:** Claude Haiku 4.5  

---

## 1. Executive Summary

When `synthesize_pattern()` fires (≥3 anomaly occurrences for a source sovereign), it currently writes only to a Markdown wiki file. This spec extends that write to **simultaneously insert a structured `TrustAnomalyPatternNode`** into the intelligence graph (`graph_entities` + `graph_relationships` tables). The graph node is linked to the source sovereign's `SovereignNode` via an `EXHIBITS` edge.

**Core formula:**
```
synthesize_pattern() ⟹ wiki_write() + graph_write()
pool = None  ⟹  wiki_write() only (backward compat)
pool = Some  ⟹  wiki_write() + graph_upsert()
```

No DB is read by the AutoResearch watcher; all writes are append/upsert only.

---

## 2. Architectural Constraints & Safety Invariants

### LOCKED Design Decisions

1. **Graph write is fire-and-forget** — failures print to stderr, never propagate to `std::io::Result<()>`
2. **Pool is `Option<Arc<PgPool>>`** — `None` = Phase 22 behavior unchanged; all existing tests pass
3. **Idempotent upsert** — same `source_id` → update, not duplicate
4. **No new crate dependencies** — `write_trust_anomaly_pattern()` lives in `siss-graph-db` alongside existing intel graph functions
5. **No circular dependency** — `wiki_writer.rs` imports from same crate `repo::intelligence_graph_repo`

### Blast Radius

| Component | Change | Risk |
|-----------|--------|------|
| `wiki_writer::synthesize_pattern` | +2 params (pool, first_detected) | Low — all call sites in tests updated |
| `autoresearch_scheduler::start_autoresearch_watcher` | +1 param (pool) | Low — callers pass None |
| `intelligence_graph_repo.rs` | +1 new function | Zero risk to existing functions |
| Migration 035 | +2 partial unique indexes | Additive, no drops |

---

## 3. New Migration: `035_add_phase22_trust_anomaly_index.sql`

**File:** `crates/siss-graph-db/src/migrations/035_add_phase22_trust_anomaly_index.sql`

```sql
-- Migration 035: Phase 22b Trust Anomaly Graph Indexes
-- Enables idempotent upsert of TrustAnomalyPatternNode by source_id
-- Enables idempotent EXHIBITS edge by (source, target, type)

-- Fix graph_id column to allow sentinel value for non-AGE writes
ALTER TABLE graph_entities ALTER COLUMN graph_id SET DEFAULT 0;

-- Partial unique index: one TrustAnomalyPatternNode per source sovereign
CREATE UNIQUE INDEX IF NOT EXISTS idx_trust_anomaly_pattern_source_id
    ON graph_entities ((properties->>'source_id'))
    WHERE label = 'TrustAnomalyPatternNode';

-- Unique index: prevent duplicate EXHIBITS edges
CREATE UNIQUE INDEX IF NOT EXISTS idx_graph_rel_src_tgt_type
    ON graph_relationships (source_entity_id, target_entity_id, relationship_type);
```

**Note on `graph_id`:** Migration 032 defines `graph_id BIGINT NOT NULL` with no default. Existing inserts omit this column (lines 45, 96, 126, 174, 277 of `intelligence_graph_repo.rs`). Migration 035 adds `DEFAULT 0` as a sentinel for non-AGE relational usage, fixing the latent schema issue without touching existing code.

---

## 4. New Function: `write_trust_anomaly_pattern`

**File:** `crates/siss-graph-db/src/repo/intelligence_graph_repo.rs`

```rust
pub async fn write_trust_anomaly_pattern(
    pool: &PgPool,
    source_id: Uuid,
    target_id: Uuid,
    latest_score: i16,
    dominant_cause: &str,
    occurrence_count: usize,
    first_detected: DateTime<Utc>,
    last_detected: DateTime<Utc>,
) -> Result<Uuid, sqlx::Error>
```

**Implementation:**

```rust
let properties = json!({
    "source_id": source_id.to_string(),
    "target_id": target_id.to_string(),
    "occurrence_count": occurrence_count,
    "latest_score": latest_score,
    "dominant_cause": dominant_cause,
    "first_detected": first_detected.to_rfc3339(),
    "last_detected": last_detected.to_rfc3339(),
});

// 1. Upsert TrustAnomalyPatternNode
let pattern_id: Uuid = sqlx::query_scalar(
    "INSERT INTO graph_entities (id, label, properties) \
     VALUES ($1, 'TrustAnomalyPatternNode', $2) \
     ON CONFLICT ((properties->>'source_id')) \
     WHERE label = 'TrustAnomalyPatternNode' \
     DO UPDATE SET properties = EXCLUDED.properties, updated_at = NOW() \
     RETURNING id",
)
.bind(Uuid::new_v4())
.bind(&properties)
.fetch_one(pool)
.await?;

// 2. Get/create SovereignNode for source
let sovereign_node_id = get_or_create_sovereign_node(pool, source_id).await?;

// 3. Insert EXHIBITS edge (idempotent)
sqlx::query(
    "INSERT INTO graph_relationships \
     (source_entity_id, target_entity_id, relationship_type, confidence) \
     VALUES ($1, $2, 'EXHIBITS', 1.0) \
     ON CONFLICT (source_entity_id, target_entity_id, relationship_type) \
     DO NOTHING",
)
.bind(sovereign_node_id)
.bind(pattern_id)
.execute(pool)
.await?;

Ok(pattern_id)
```

---

## 5. Modified Signatures

### `wiki_writer.rs` — `synthesize_pattern`

```rust
pub async fn synthesize_pattern(
    wiki_dir: PathBuf,
    source_id: Uuid,
    occurrence_count: usize,
    signal: TrustUpdateSignal,
    pool: Option<std::sync::Arc<sqlx::PgPool>>,
    first_detected: chrono::DateTime<chrono::Utc>,
) -> std::io::Result<()>
```

**After Markdown write succeeds**, fire-and-forget graph call:
```rust
if let Some(pool) = pool {
    if let Err(e) = crate::repo::intelligence_graph_repo::write_trust_anomaly_pattern(
        &pool,
        source_id,
        signal.target_id,
        signal.new_score,
        dominant_cause,
        occurrence_count,
        first_detected,
        signal.timestamp,
    ).await {
        eprintln!("[graph-dual-write] write_trust_anomaly_pattern failed: {e}");
    }
}
```

`dominant_cause` is already computed earlier in the function body (lines 64–74 of current impl), so no duplication.

### `autoresearch_scheduler.rs` — `start_autoresearch_watcher`

```rust
pub fn start_autoresearch_watcher(
    mut rx: broadcast::Receiver<TrustUpdateSignal>,
    wiki_dir: PathBuf,
    pool: Option<std::sync::Arc<sqlx::PgPool>>,
) -> tokio::task::JoinHandle<()>
```

**State tracking upgrade** (replaces bare `HashMap<Uuid, usize>`):

```rust
struct AnomalyState {
    count: usize,
    first_detected: chrono::DateTime<chrono::Utc>,
}
let mut occurrence_state: HashMap<Uuid, AnomalyState> = HashMap::new();
```

On each severe signal:
```rust
let state = occurrence_state.entry(signal.source_id).or_insert(AnomalyState {
    count: 0,
    first_detected: signal.timestamp,
});
state.count += 1;

if state.count >= 3 {
    wiki_writer::synthesize_pattern(
        (*wiki_dir).clone(),
        signal.source_id,
        state.count,
        signal,
        pool.clone(),
        state.first_detected,
    ).await;
}
```

---

## 6. TDD Sequence — 4 Failing Tests (Write Before Implementation)

### Tests 1–3: `intelligence_graph_repo.rs` (require testcontainers DB)

```rust
#[tokio::test]
async fn test_write_trust_anomaly_pattern_creates_entity()
// Setup: testcontainers postgres, run all migrations including 035
// Action: write_trust_anomaly_pattern(&pool, src, tgt, 42, "decay_collapse", 3, now, now)
// Assert: graph_entities WHERE label='TrustAnomalyPatternNode' AND properties->>'source_id'=... COUNT=1

#[tokio::test]
async fn test_write_trust_anomaly_pattern_idempotent()
// Action: call twice with same source_id, occurrence_count 3 then 5
// Assert: count still 1; properties->>'occurrence_count' = '5'

#[tokio::test]
async fn test_write_trust_anomaly_pattern_creates_exhibits_edge()
// Action: call once
// Assert: graph_relationships WHERE relationship_type='EXHIBITS' COUNT=1
//         source_entity_id = sovereign node for source_id
```

### Test 4: `wiki_writer.rs` (unit test, no DB)

```rust
#[tokio::test]
async fn test_synthesize_pattern_with_pool_none_writes_markdown_only()
// Action: synthesize_pattern(wiki_dir, source_id, 3, signal, None, Utc::now())
// Assert: semantic markdown file written correctly; Ok(()) returned
// (confirms backward compat signature change doesn't break existing behavior)
```

---

## 7. Build Sequence (TDD)

| Phase | Action | Verification |
|-------|--------|-------------|
| **A** | Write migration 035 + register in migrations/mod.rs | `cargo check` ✓ |
| **A** | Write 4 failing tests (3 in intel_graph_repo, 1 in wiki_writer) | `cargo test` → exactly 4 new failures |
| **B** | Implement `write_trust_anomaly_pattern()` | Tests 1–3 pass |
| **C** | Update `synthesize_pattern()` signature + graph call | Test 4 passes; all 6 wiki_writer tests pass |
| **D** | Update `start_autoresearch_watcher()` + `AnomalyState` struct | All 10 Phase 22 tests pass |
| **E** | Update existing wiki_writer test call sites (add `None, signal.timestamp`) | Zero compile errors |
| **F** | Final: `cargo test`, `cargo clippy`, `cargo fmt` | All green |

---

## 8. Files to Create

| File | Purpose |
|------|---------|
| `crates/siss-graph-db/src/migrations/035_add_phase22_trust_anomaly_index.sql` | Indexes for upsert + graph_id default fix |

## Files to Modify

| File | Change |
|------|--------|
| `crates/siss-graph-db/src/migrations/mod.rs` | Register migration 035 |
| `crates/siss-graph-db/src/repo/intelligence_graph_repo.rs` | Add `write_trust_anomaly_pattern()` + 3 tests |
| `crates/siss-graph-db/src/wiki_writer.rs` | Add `pool` + `first_detected` params; call graph write; update test call sites |
| `crates/siss-graph-db/src/autoresearch_scheduler.rs` | Add `pool` param; `AnomalyState` struct; pass through |

---

## 9. Success Criteria

✓ `write_trust_anomaly_pattern()` creates TrustAnomalyPatternNode on first call  
✓ Second call with same source_id updates, not duplicates  
✓ EXHIBITS edge connects SovereignNode → TrustAnomalyPatternNode  
✓ `synthesize_pattern(pool=None)` writes Markdown only (backward compat)  
✓ `synthesize_pattern(pool=Some)` writes Markdown + graph atomically  
✓ Graph write failure is non-fatal (fire-and-forget, eprintln)  
✓ All 10 Phase 22 unit tests pass  
✓ 4 new TDD tests pass  
✓ `cargo clippy` clean; `cargo fmt` clean  

---

## 10. Future Extensions

1. **Episodic dual-write:** Also write individual `AnomalyNode` entries per event (not just patterns)
2. **Graph query in cockpit:** Expose `TrustAnomalyPatternNode` via `/api/graph/anomalies` SSE endpoint
3. **Cross-agent reasoning:** Query graph for patterns when scoring trust in new sessions
4. **Governance trigger:** Create `GovernanceProposalNode` linked from `TrustAnomalyPatternNode` when occurrence_count > 10

---

## 11. References

- **Phase 22 SPEC:** `docs/superpowers/specs/2026-05-11-phase22-autoresearch-memory-hooks-design.md`
- **Intel Graph Repo:** `crates/siss-graph-db/src/repo/intelligence_graph_repo.rs`
- **Wiki Writer:** `crates/siss-graph-db/src/wiki_writer.rs`
- **AutoResearch Scheduler:** `crates/siss-graph-db/src/autoresearch_scheduler.rs`
- **Migration 032:** `crates/siss-graph-db/src/migrations/032_add_smaos_intelligence_graph.sql`
- **Recovery Sweep Pattern:** `crates/siss-graph-db/src/recovery_sweep_scheduler.rs`

---

**Spec Complete:** 2026-05-11  
**Ready for:** TDD Phase A (write failing tests, then implement)
