# Phase 22: AutoResearch Memory Hooks — Specification

**Date:** 2026-05-11  
**Status:** Design  
**Authors:** Claude Haiku 4.5  

---

## 1. Executive Summary

Phase 22 crystallizes trust anomalies into structured knowledge. A background AutoResearch loop subscribes to Phase 21 trust events, detects severe penalties (score < 25, decay > -50 days, 3+ active slashes), and appends them to the LLM Wiki v2. When patterns recur ≥ 3 times per source sovereign, they're synthesized into semantic entries. A linting script periodically prunes stale entries and reports contradictions.

**Core formula:**
```
trust_anomaly_detected() ⟹ append_episodic_event()
anomaly_count(source_id) ≥ 3 ⟹ synthesize_pattern()
daily_lint() ⟹ prune_stale + detect_contradictions + report()
```

---

## 2. Architectural Constraints & Safety Invariants

### LOCKED Design Decisions

1. **AutoResearch reads, never writes to DB** — Wiki only; `trust_network_edges` is read-only
2. **Broadcaster lives in siss-graph-db, not siss-agent-shell** — Avoids circular dependency
3. **Async non-blocking file I/O** — Uses `tokio::fs`, never blocks the event loop
4. **Fire-and-forget emission** — No backpressure; if no subscribers, signals drop silently
5. **Backward compatibility** — `TrustEventBroadcaster` is optional; None = Phase 21 unchanged

### Blast Radius Analysis

| System | Risk | Mitigation |
|--------|------|-----------|
| `trust_topology_repo.rs` | Emitting new signal type | `Option<Arc<...>>` param; default None preserves all existing tests |
| `siss-graph-db/lib.rs` | Module registration | Three new modules; no impact on existing repos |
| `tokio runtime` | File I/O contention | Async `tokio::fs`; dedicated background task |
| Wiki directory | Concurrent writes | One watcher task only; sequential appends |
| `lint_trust_wiki.sh` | File mutation | `--dry-run` by default; `--prune` explicit flag |

**Structural safety guarantee:** Wiki writes are append-only (JSONL episodic) or append-to-end (Markdown semantic). No in-place mutation; no locking required.

---

## 3. Data Model — Trust Anomaly Signal

### TrustUpdateSignal

Defined in `crates/siss-graph-db/src/trust_event_broadcaster.rs`:

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TrustUpdateSignal {
    pub source_id: Uuid,                      // Trust source (one who trusts)
    pub target_id: Uuid,                      // Trust target (recipient)
    pub new_score: i16,                       // Final hybrid_trust_score [0..100]
    pub explicit_component: i16,              // Explicit endorsement contribution
    pub implicit_component: i16,              // Behavioral signals (slash, anomaly, settle)
    pub decay_component: i16,                 // Time decay contribution (negative)
    pub transitive_component: Option<i16>,    // Transitive grant boost (capped ≤ 15)
    pub timestamp: DateTime<Utc>,             // Event UTC time
}
```

**Emitted from:** `trust_topology_repo::compute_and_upsert_trust_score()` after every score computation.

**Broadcast channel:** `TrustEventBroadcaster` with 256-capacity broadcast queue (async, non-blocking).

---

## 4. Severity Detection Rules

```rust
pub fn is_severe_penalty(signal: &TrustUpdateSignal) -> bool {
    signal.new_score < 25            // Critical trust collapse
    || signal.decay_component < -50  // >15 days zero interaction (linear decay)
    || signal.implicit_component < -30 // 3+ active slashes (min penalty = 30)
}
```

**Severity classification (for wiki):**
- `critical`: Any condition above (score < 25 OR decay < -50 OR implicit < -30)
- `high`: score ∈ [25, 50)
- `medium`: score ∈ [50, 75)

---

## 5. AutoResearch Watcher Loop

**Function:** `start_autoresearch_watcher(rx: broadcast::Receiver<TrustUpdateSignal>, wiki_dir: PathBuf) → tokio::task::JoinHandle<()>`

**Pattern:** Canonical tokio spawn loop (mirrors `recovery_sweep_scheduler.rs`):
```rust
tokio::spawn(async move {
    loop {
        match rx.recv().await {
            Ok(signal) => {
                if is_severe_penalty(&signal) {
                    wiki_writer::append_episodic_event(wiki_dir.clone(), signal.clone()).await;
                    occurrence_count[signal.source_id] += 1;
                    
                    if occurrence_count[signal.source_id] >= 3 {
                        wiki_writer::synthesize_pattern(wiki_dir.clone(), signal.source_id).await;
                    }
                }
            }
            Err(broadcast::error::RecvError::Lagged(_)) => continue,
            Err(broadcast::error::RecvError::Closed) => break,
        }
    }
})
```

**Constraints:**
- One watcher task per instance (no parallelism)
- In-memory occurrence counter (HashMap<Uuid, usize>); not persisted
- Pattern synthesis happens once per source_id reaching threshold

---

## 6. Wiki Writer — Episodic Layer

**File:** `crates/siss-graph-db/src/wiki_writer.rs`

**Function:** `append_episodic_event(wiki_dir: PathBuf, signal: TrustUpdateSignal) → Result<(), io::Error>`

**Format:** JSONL (one JSON object per line), appended to `docs/wiki/episodic/trust-events.md`

**JSON schema:**
```json
{
  "event_id": "uuid",
  "event_type": "trust_anomaly",
  "source_id": "uuid-string",
  "target_id": "uuid-string",
  "score": 12,
  "explicit_component": 80,
  "implicit_component": -41,
  "decay_component": -50,
  "transitive_component": null,
  "severity": "critical",
  "timestamp": "2026-05-11T14:30:45Z"
}
```

**File guarantees:**
- Append-only; no in-place mutation
- Line-buffered; each event is one line
- UTF-8 encoded
- No concurrent writers (single watcher task enforces this)

**Implementation notes:**
- Use `tokio::fs::OpenOptions::append()` for async append
- Create file if missing (first event)
- Panic/error if append fails (critical condition)

---

## 7. Wiki Writer — Semantic Layer

**Function:** `synthesize_pattern(wiki_dir: PathBuf, source_id: Uuid) → Result<(), io::Error>`

**Trigger:** When `occurrence_count[source_id] >= 3` (at 3rd, 4th, 5th event...)

**Format:** Markdown section appended to `docs/wiki/semantic/trust-anomalies.md`

**Template:**
```markdown
## Anomaly Pattern: <source_id_prefix_8_chars>

| Field | Value |
|-------|-------|
| Source Sovereign | <source_id> |
| Total Occurrences | N |
| Latest Score | I16 |
| Dominant Cause | (categorized) |
| First Detected | ISO 8601 date |
| Latest Event | ISO 8601 date |
| Recommended Action | (prescriptive) |

---
```

**Dominant Cause Categories:**
- `decay_collapse`: decay_component < -50 (flagged as "Persistent zero-interaction")
- `slash_accumulation`: implicit_component < -30 (flagged as "Repeated slashing penalties")
- `mixed_decay_slash`: Both conditions (flagged as "Combined decay + slash")
- `transitive_loss`: transitive_component was non-zero, now 0 (flagged as "Transitive grant revocation")

**Recommended Actions (prescriptive):**
- "Revoke explicit trust edges; notify governance layer"
- "Sweep eligibility check; re-establish tenure requirements"
- "Query behavioral anomalies for source; investigate root cause"
- "Monitor recovery trajectory post-interaction; allow grace period"

**Implementation notes:**
- Check if pattern already exists; only append if new (prevent duplicates)
- Extract oldest and latest timestamps from episodic entries for same source_id
- Idempotent: running twice for same source_id produces same output

---

## 8. Linting Script — Health Check

**File:** `scripts/lint_trust_wiki.sh`

**Usage:** `./lint_trust_wiki.sh [--dry-run] [--prune] [--report]`

**Flags:**
- `--dry-run` (default): Print findings, do not modify wiki
- `--prune`: Execute deletions/corrections
- `--report`: Write summary to `docs/wiki/working/autoresearch-status.md`

**Three checks:**

### 8.1 Prune Stale Entries

**Condition:** JSONL episodic lines with `timestamp` older than 30 days

**Action:** Delete line from `docs/wiki/episodic/trust-events.md`

**Rationale:** Keep episodic log bounded; old anomalies are synthesized into semantic patterns

### 8.2 Detect Contradictions

**Condition:** Same `(source_id, target_id)` pair with score swing > 50 within 24 hours

**Example:** 
```
14:00 - score: 80
14:30 - score: 15  // swing of 65 → contradiction
```

**Action:** Mark as "potential flip-flopping"; report to `autoresearch-status.md`

**Rationale:** Trust reversals this sudden suggest data anomalies or governance events that warrant investigation

### 8.3 Detect Orphaned Patterns

**Condition:** Semantic entry for source_id appears 0 times in recent episodic log (last 30 days)

**Action:** Mark as "stale pattern"; candidate for archival

**Rationale:** If pattern hasn't re-occurred in 30 days, it's resolved or decayed

### 8.4 Health Report

**Output file:** `docs/wiki/working/autoresearch-status.md`

**Content:**
```markdown
# AutoResearch Health Check — 2026-05-11 14:45 UTC

## Summary
- Episodic entries: 127 (last 30 days: 43)
- Semantic patterns: 12
- Contradictions detected: 3
- Stale patterns: 1

## Contradictions
- source: uuid-1, target: uuid-2, swing: 65 points in 30 min
- source: uuid-3, target: uuid-4, swing: 48 points in 2 hours

## Stale Patterns (≥30 days, no recent events)
- source: uuid-5 (last event: 2026-04-01)

## Recommendations
- Investigate source uuid-1: potential data anomaly or governance action
- Archive pattern for uuid-5 if genuinely resolved

**Next lint:** 2026-05-12 14:45 UTC
```

---

## 9. Integration — Trust Topology Repo

**File:** `crates/siss-graph-db/src/repo/trust_topology_repo.rs`

**Function signature (modified):**
```rust
pub async fn compute_and_upsert_trust_score(
    pool: &PgPool,
    source_id: Uuid,
    target_id: Uuid,
    broadcaster: Option<Arc<TrustEventBroadcaster>>,  // NEW param
) -> Result<i16, sqlx::Error>
```

**Change:** After computing `hybrid_score` and upserting, emit signal:
```rust
if let Some(bc) = broadcaster {
    bc.emit(TrustUpdateSignal {
        source_id,
        target_id,
        new_score: hybrid_score,
        explicit_component: explicit_base,
        implicit_component: implicit_adj,
        decay_component: decay_penalty,
        transitive_component: transitive_boost,
        timestamp: Utc::now(),
    });
}
```

**Backward compatibility:** Default `None` = Phase 21 behavior unchanged; all existing tests pass.

---

## 10. Module Registration

**File:** `crates/siss-graph-db/src/lib.rs`

**Add:**
```rust
pub mod trust_event_broadcaster;
pub mod wiki_writer;
pub mod autoresearch_scheduler;
```

---

## 11. TDD — 10 Failing Tests (Write Before Implementation)

### wiki_writer.rs (6 tests)

```rust
#[tokio::test]
async fn test_append_episodic_event_creates_file_if_missing() {
    // Setup: temp dir, no file
    // Action: append one event
    // Assert: file created, contains valid JSON line, can be parsed
}

#[tokio::test]
async fn test_append_episodic_event_appends_valid_jsonl() {
    // Setup: existing file with 1 line
    // Action: append second event
    // Assert: file has 2 lines, both valid JSON, no corruption
}

#[tokio::test]
async fn test_append_multiple_events_no_overwrite() {
    // Setup: temp dir
    // Action: append 10 events in rapid succession
    // Assert: file has 10 lines, all intact, sequential order preserved
}

#[tokio::test]
async fn test_synthesize_pattern_appends_markdown_section() {
    // Setup: temp dir, episodic file with 3 events for same source_id
    // Action: synthesize_pattern(source_id)
    // Assert: semantic file created, contains "## Anomaly Pattern: <prefix>", proper Markdown table
}

#[tokio::test]
async fn test_synthesize_pattern_idempotent_on_same_source() {
    // Setup: semantic file with one pattern
    // Action: synthesize_pattern(source_id) again
    // Assert: file unchanged (no duplicate pattern)
}

#[tokio::test]
fn test_wiki_entry_contains_all_required_fields() {
    // Setup: TrustUpdateSignal with all fields
    // Action: serialize to JSON string
    // Assert: JSON contains event_id, source_id, target_id, score, severity, timestamp
}
```

### autoresearch_scheduler.rs (4 tests)

```rust
#[test]
fn test_is_severe_score_below_25() {
    let signal = TrustUpdateSignal {
        new_score: 12,
        decay_component: 0,
        implicit_component: 0,
        ..default()
    };
    assert!(is_severe_penalty(&signal));
}

#[test]
fn test_is_severe_decay_below_50() {
    let signal = TrustUpdateSignal {
        new_score: 50,
        decay_component: -51,
        implicit_component: 0,
        ..default()
    };
    assert!(is_severe_penalty(&signal));
}

#[test]
fn test_is_severe_slash_implicit_below_30() {
    let signal = TrustUpdateSignal {
        new_score: 50,
        decay_component: 0,
        implicit_component: -31,
        ..default()
    };
    assert!(is_severe_penalty(&signal));
}

#[test]
fn test_not_severe_above_all_thresholds() {
    let signal = TrustUpdateSignal {
        new_score: 30,
        decay_component: -10,
        implicit_component: -10,
        ..default()
    };
    assert!(!is_severe_penalty(&signal));
}
```

---

## 12. Build Sequence (TDD)

| Phase | Action | Verification |
|-------|--------|-------------|
| **A** | Create wiki skeleton + broadcaster stubs | `cargo check -p siss-graph-db` ✓ |
| **B** | Implement wiki_writer.rs + 6 tests | `cargo test wiki_writer` → 6 PASS |
| **C** | Implement autoresearch_scheduler.rs + 4 tests | `cargo test autoresearch` → 4 PASS |
| **D** | Wire broadcaster into trust_topology_repo.rs | All existing tests pass |
| **E** | Register modules in lib.rs | `cargo build -p siss-graph-db` clean |
| **F** | Create lint_trust_wiki.sh + integration test | Script executes, report written |
| **G** | Final verification | `cargo test`, `cargo clippy`, `cargo fmt` |

---

## 13. Success Criteria

✓ AutoResearch watcher spawns and subscribes to broadcaster  
✓ Severe penalties (score < 25, decay < -50, implicit < -30) trigger wiki writes  
✓ Episodic JSONL entries are append-only and valid JSON  
✓ Patterns recur ≥ 3 times before semantic synthesis  
✓ Linting script prunes stale entries, detects contradictions, generates report  
✓ Backward compat: Phase 21 tests pass with broadcaster = None  
✓ No DB mutations; wiki writes only  
✓ Async file I/O (tokio::fs); non-blocking  
✓ 10 unit tests pass; coverage ≥ 80%  
✓ All code formatted, no clippy warnings  

---

## 14. Future Extensions

1. **Governance integration:** `autoresearch-status.md` triggers automated governance proposals for patterns
2. **Graph dual-write:** Anomaly patterns written to intelligence graph as `TrustAnomalyNode`
3. **Streaming export:** Wiki feed exposed as SSE to cockpit for real-time anomaly dashboard
4. **Decentralized archive:** Synthesized patterns archived to distributed ledger for immutable log
5. **Cross-agent learning:** Multiple agent instances share wiki via Git sync or MCP

---

## 15. References & Related Phases

- **Phase 20:** Reputation Recovery (graduation curve, scoring signals)
- **Phase 21:** Hybrid Trust Topology (directional edges, decay model, intelligence graph)
- **LLM Wiki v2:** `docs/wiki/` (episodic, semantic, working layers)
- **Recovery Sweep Scheduler:** `crates/siss-graph-db/src/recovery_sweep_scheduler.rs` (tokio loop pattern)
- **Behavioral Anomalies:** migration `028_add_phase15_behavioral_anomalies.sql` (severity enum)

---

**Spec Complete:** 2026-05-11 15:45 UTC  
**Ready for:** Implementation Phase B (wiki_writer.rs TDD)
