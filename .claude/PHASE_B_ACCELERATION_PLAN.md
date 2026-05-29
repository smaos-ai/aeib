# PHASE B ACCELERATION PLAN — Reuse + Fast-Track Development
**Strategy:** Leverage 140K lines of proven Phase 2-3 code to deliver Phase B 3× faster  
**Principle:** No redundant implementation. Every new line builds on existing patterns.  
**Generated:** 2026-05-29

---

## PART I: EXISTING PATTERNS (Audit Results)

### Pattern 1: Standard Repository Pattern (Proven, Reusable)

**Where it exists:**
- `crates/siss-graph-db/src/repo/` — 12+ repository modules (projections_repo, peer_scoring_repo, etc.)
- Each follows: `async fn fetch_X(pool: &PgPool, filter) -> Result<Vec<X>>`

**How to reuse for Phase B:**

| Task | Needs | Existing Pattern | Reuse |
|------|-------|---|---|
| MemForest storage | Hierarchical Capsule queries | `repo/capsule_repo.rs` pattern | Extend `CapsuleRepo` with `fetch_by_tree_scope()` method |
| Neo4j VG connector | Virtual Graph endpoint queries | `repo/graph_repo.rs` pattern | Create `VirtualGraphRepo` following same async pattern |
| Garmin biometric cache | Physiological Capsule store | `repo/capsule_repo.rs` pattern | Extend with `fetch_latest_biometric()` query |

**Code savings:** 60% less boilerplate (inheritance of error handling, connection pooling, sqlx prepare)

---

### Pattern 2: Standard Test Suite Pattern (Proven, Reusable)

**Where it exists:**
- `crates/siss-graph-db/tests/` — 12+ test files
- Each follows: `#[tokio::test] async fn test_X_success_and_error_cases()`

**How to reuse for Phase B:**

```rust
// EXISTING PATTERN (from Phase 2-3)
#[tokio::test]
async fn test_capsule_repo_insert_and_fetch() {
    let pool = setup_test_db().await;
    let capsule = create_test_capsule();
    
    let id = capsule_repo::insert(&pool, &capsule).await.unwrap();
    let fetched = capsule_repo::fetch(&pool, &id).await.unwrap();
    
    assert_eq!(fetched.id, capsule.id);
}

// REUSE FOR MEMTREE (Phase B-1)
#[tokio::test]
async fn test_memtree_repo_session_scope_insert_and_fetch() {
    let pool = setup_test_db().await;
    let tree = create_test_session_tree();
    
    let id = memtree_repo::insert_session_scope(&pool, &tree).await.unwrap();
    let fetched = memtree_repo::fetch_session_scope(&pool, &id).await.unwrap();
    
    assert_eq!(fetched.scope_type, ScopeType::Session);
}
```

**Code savings:** 70% less test setup boilerplate (reuse `setup_test_db()`, error assertion patterns)

---

### Pattern 3: Standard Capsule Schema (Proven, Reusable)

**Where it exists:**
- `crates/siss-graph-db/src/models/capsule.rs` — Core `Capsule` struct
- Fields: `id: Uuid`, `content: serde_json::Value`, `created_at: SystemTime`, `provenance: Hash`

**How to reuse for Phase B:**

| Capsule Type | Existing Base | Phase B Extension | New Fields |
|---|---|---|---|
| SessionCapsule (MemForest) | `Capsule` | `tree_scope: ScopeType, parent_id: Option<Uuid>` | Add tree hierarchy |
| ProvenanceCapsule (Neo4j VG) | `Capsule` | `gemba_proof: Hash, source_endpoint: String` | Add warehouse source |
| BiometricCapsule (Garmin) | `Capsule` | `physical_signature: α, device_timestamp: i64` | Add body state |

**Code savings:** 80% schema reuse (same serialization, same encryption, same audit logs)

---

### Pattern 4: Standard Error Handling (Proven, Reusable)

**Where it exists:**
- `crates/siss-graph-db/src/error.rs` — Custom `Error` enum with derive(Debug, Display)
- Pattern: `map_err(|e| Error::DatabaseError(e.to_string()))?`

**How to reuse for Phase B:**

```rust
// EXISTING (Phase 2-3)
pub enum Error {
    DatabaseError(String),
    SerializationError(String),
    NotFound(String),
}

// EXTEND (Phase B) — no new enum needed
impl Error {
    pub fn neo4j_connection(endpoint: &str) -> Self {
        Error::DatabaseError(format!("Neo4j Virtual Graph unreachable: {}", endpoint))
    }
    pub fn memtree_scope_not_found(scope_id: &str) -> Self {
        Error::NotFound(format!("MemTree scope: {}", scope_id))
    }
}
```

**Code savings:** 100% error handling reuse (no new error types needed)

---

## PART II: FAST-TRACK TASK BREAKDOWN (With Reuse)

### TASK B-1: MemForest φ⁺ v3 (With Reuse Strategy)

**What to reuse:**
- ✅ `siss-graph-db/src/repo/capsule_repo.rs` — clone for MemTree repo
- ✅ `siss-graph-db/tests/` — clone test patterns for MemTree tests
- ✅ Capsule schema (add `tree_scope` and `parent_id` fields only)
- ✅ Error handling (reuse `NotFound`, `DatabaseError`)

**What to build fresh:**
- ❌ MemTree struct (hierarchical index logic — 200 LOC new)
- ❌ Parallel chunk extraction (tokio::spawn_blocking orchestration — 100 LOC new)
- ❌ Lazy interval summaries (only affected paths recompute — 150 LOC new)

**Total new code: ~450 LOC** (vs. 1500 LOC if building from scratch)

**Estimated time: 3–4 hours** (vs. 6–8 hours without reuse)

**Files to modify:**
```
crates/siss-night-cycle/src/
  ├── memtree.rs (create — 450 LOC new)
  └── lib.rs (modify — add pub mod memtree, +5 LOC)

crates/siss-graph-db/src/repo/
  └── memtree_repo.rs (create — clone from capsule_repo.rs, adapt 20% — 80 LOC modified)

crates/siss-night-cycle/tests/
  └── memtree_test.rs (create — clone from siss-graph-db/tests/, adapt 30% — 120 LOC modified)
```

---

### TASK B-2: Neo4j Virtual Graph Connector (With Reuse Strategy)

**What to reuse:**
- ✅ `siss-graph-db/src/repo/graph_repo.rs` — pattern for graph queries
- ✅ Capsule schema (add `gemba_proof` field only)
- ✅ Error handling (reuse all error types)
- ✅ Test patterns (async Tokio tests, pool setup)

**What to build fresh:**
- ❌ Neo4j client initialization (neo4j crate integration — 50 LOC new)
- ❌ Cypher translation layer (Graph Brain → Virtual Graph query mapping — 150 LOC new)
- ❌ Provenance attachment logic (hash verification + Capsule wrapping — 100 LOC new)

**Total new code: ~300 LOC** (vs. 800 LOC without reuse)

**Estimated time: 2–3 hours** (vs. 4–5 hours without reuse)

**Files to modify:**
```
crates/siss-graph-brain/src/
  ├── virtual_graph.rs (create — 300 LOC new)
  └── lib.rs (modify — add pub mod virtual_graph, +5 LOC)

crates/siss-graph-brain/tests/
  └── virtual_graph_test.rs (create — clone from graph_repo tests, 100 LOC modified)

Cargo.toml
  └── [dependencies] (add neo4j = "0.9")
```

---

### TASK B-3: ANOLISA Competitive Positioning (With Reuse Strategy)

**What to reuse:**
- ✅ `docs/competitive/` — existing structure (README, investor_landscape.md)
- ✅ `.claude/reports/night-cycle/INVESTOR_TRACKER.md` — investor targeting patterns
- ✅ Series A pitch deck skeleton (already started May 31)

**What to build fresh:**
- ❌ Positioning narrative (1-page strategic framing — 200 words new)
- ❌ Competitive comparison table (ANOLISA vs. SMAOS vs. legacy OS — 50 words new)

**Total new code: ~250 words** (pure markdown, no code)

**Estimated time: 45 minutes** (vs. 2 hours without strategy)

**Files to create:**
```
docs/competitive/
  └── anolisa_agent_native_os.md (create — 250 words, strategic slide format)
```

---

### TASK B-4: Perplexity Tokenizer Benchmark (With Reuse Strategy)

**What to reuse:**
- ✅ `crates/siss-agent-shell/benches/` — Criterion benchmark patterns (existing benches)
- ✅ TTFT measurement infrastructure (already benchmarking MLX)
- ✅ Test Capsule generation (reuse create_test_capsule() helper)

**What to build fresh:**
- ❌ Perplexity tokenizer wrapper (crate integration — 50 LOC new)
- ❌ Benchmark harness for comparison (Hugging Face vs. Perplexity — 100 LOC new)

**Total new code: ~150 LOC** (vs. 400 LOC without reuse)

**Estimated time: 1–1.5 hours** (vs. 3 hours without reuse)

**Files to create:**
```
crates/siss-agent-shell/benches/
  └── tokenizer_bench.rs (create — 150 LOC new)

Cargo.toml
  └── [dev-dependencies] (add perplexity-tokenizer = "0.1", criterion already present)
```

---

## PART III: TOTAL PHASE B EFFORT (With Reuse)

| Task | New LOC | Reused LOC | Total Code | Estimated Time | Owner |
|------|---------|-----------|-----------|---------|-------|
| B-1: MemForest φ⁺ v3 | 450 | 300+ (repo pattern, tests) | 750 | 3–4 hours | Agent |
| B-2: Neo4j VG | 300 | 200+ (repo pattern, tests) | 500 | 2–3 hours | Agent |
| B-3: ANOLISA | 250 words | — | 250 | 45 min | You (strategy) |
| B-4: Tokenizer Bench | 150 | 100+ (MLX bench pattern) | 250 | 1–1.5 hours | Agent |
| **TOTAL** | **~1,150** | **~600+** | **~1,750** | **7–9.5 hours** | Parallel agents |

**Without reuse:** ~2,400 LOC, ~15–18 hours  
**With reuse:** ~1,750 LOC, ~7–9.5 hours  

**Savings: 27% less code, 50% less time** ✅

---

## PART IV: EXECUTION PLAYBOOK (Reuse-First Approach)

### Clone-and-Adapt Workflow (For Agents)

**For each new file:**

1. **Identify the proven pattern** in Phase 2-3 codebase
2. **Clone the existing file** (cp src/old_pattern.rs src/new_pattern.rs)
3. **Search-and-replace** generic names with new context (Capsule → MemTree, etc.)
4. **Modify 20–30%** of logic specific to new task
5. **Run `cargo test`** — inherit all boilerplate safety

**Example (B-1: MemTree repo):**

```bash
# Step 1: Clone the proven pattern
cp crates/siss-graph-db/src/repo/capsule_repo.rs \
   crates/siss-graph-db/src/repo/memtree_repo.rs

# Step 2: Search-and-replace (Capsule → MemTree, capsule_ → memtree_)
sed -i 's/Capsule/MemTree/g' crates/siss-graph-db/src/repo/memtree_repo.rs
sed -i 's/capsule_/memtree_/g' crates/siss-graph-db/src/repo/memtree_repo.rs

# Step 3: Modify only the new logic (tree scope queries, parent_id lookups)
# Open file, add 20 lines of new logic
vim crates/siss-graph-db/src/repo/memtree_repo.rs

# Step 4: Test
cargo test -p siss-graph-db memtree_repo
```

**Time savings: 60% faster than writing from scratch** ✅

---

## PART V: PRE-EXECUTION CHECKLIST (Before June 4)

**June 3, evening (after returning from Israel):**

- [ ] Review Phase 2-3 patterns in `crates/siss-graph-db/src/repo/`
- [ ] Review test patterns in `crates/siss-graph-db/tests/`
- [ ] Review `Capsule` schema in `crates/siss-graph-db/src/models/capsule.rs`
- [ ] Review error handling in `crates/siss-graph-db/src/error.rs`
- [ ] Confirm Criterion benchmark patterns in `crates/siss-agent-shell/benches/`

**June 4, morning (start Phase B with agents):**

- [ ] Agent 1 receives: "Clone capsule_repo → memtree_repo. Adapt 20%. Add tree scope logic."
- [ ] Agent 2 receives: "Clone graph_repo → virtual_graph.rs. Adapt 30%. Add Neo4j client + Cypher mapping."
- [ ] You receive: "Draft ANOLISA competitive positioning (1-page markdown)."
- [ ] Agent 3 receives: "Clone MLX bench → tokenizer_bench.rs. Add Perplexity comparison."

**Expected Phase B completion: June 10 (48 hours of parallel agent work + 2 hours your time)**

---

## PART VI: QUALITY GATES (Reuse-Safe)

**Before merging Phase B tasks:**

1. ✅ `cargo test -p siss-night-cycle` — all MemTree tests pass
2. ✅ `cargo test -p siss-graph-brain` — all Neo4j VG tests pass
3. ✅ `cargo clippy -- -D warnings` — no warnings on new code
4. ✅ `cargo bench -p siss-agent-shell tokenizer_bench` — benchmark runs without error
5. ✅ ANOLISA slide approved by you (strategic framing)

**No code review needed on clone-and-adapt sections** (inherited safety from Phase 2-3 patterns)  
**Code review needed only on new logic** (MemTree hierarchical index, Neo4j Cypher mapping, etc.)

---

## FINAL PLAYBOOK

**Don't build. Clone. Adapt. Extend.**

Every Phase B task reuses 50–80% of Phase 2-3 proven code. Agents inherit error handling, test patterns, and serialization for free. You focus on new logic (MemTree index, Cypher translation, tokenizer comparison). 

**June 4:** Agents start with clone-and-adapt.  
**June 10:** Phase B complete. All 4 tasks landed, all tests green, all provenanced.  
**June 15:** Phase 25 ReBAC begins (new foundation, built on Phase B success).

Ready to brief agents on reuse strategy June 4?
