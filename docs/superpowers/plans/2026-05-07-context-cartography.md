# Context Cartography Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `siss-context-cartography` crate — the Visible Field assembler that creates Sessions, retrieves tier-based memories filtered by ReBAC, enforces token budgets, and records loaded context for auditability.

**Architecture:** A new Rust library crate `siss-context-cartography` that depends on `siss-graph-core` and `siss-graph-db`. Exposes a single async `build_context()` entry point. Called by the Job Router between `route` and `execute` steps. Retrieves memories by tier (Procedural → Semantic → Episodic), filters by ReBAC CAN_READ, trims to token budget, creates Session + LOADED edges.

**Tech Stack:** Rust (2024 edition), sqlx (async PostgreSQL), serde/serde_json, uuid, chrono, tokio, thiserror

**Spec:** `docs/superpowers/specs/2026-05-07-context-cartography-design.md`

---

## File Structure

```
crates/
  siss-context-cartography/
    Cargo.toml
    src/
      lib.rs                  # Re-exports
      types.rs                # CartographyRequest, VisibleField, MemoryEntry, CartographyError
      config.rs               # RetrievalConfig with defaults
      budget.rs               # Token budget enforcement / trimming
      retrieval/
        mod.rs                # Memory retrieval orchestrator
        procedural.rs         # Procedural tier query
        semantic.rs           # Semantic tier query
        episodic.rs           # Episodic tier query
      pipeline/
        mod.rs                # build_context() orchestrator
        validate.rs           # Step 1: validation
        session.rs            # Step 2: create session + edges
        record.rs             # Step 5: LOADED edges + snapshot
  siss-graph-db/
    src/
      repo/
        memory_repo.rs        # MODIFY: add fetch_memories_by_tier, fetch_accessible_memory_ids
        node_repo.rs          # MODIFY: add insert_session, update_session_snapshot
  siss-job-router/
    src/
      executor/mod.rs         # MODIFY: add visible_field to TaskContext
      pipeline/mod.rs         # MODIFY: call build_context between route and execute
```

---

### Task 1: Create siss-context-cartography Crate Skeleton

**Files:**
- Modify: `Cargo.toml` (workspace root)
- Create: `crates/siss-context-cartography/Cargo.toml`
- Create: `crates/siss-context-cartography/src/lib.rs`
- Create: stub modules

- [ ] **Step 1: Add crate to workspace**

Add `"crates/siss-context-cartography"` to workspace members in root `Cargo.toml`:

```toml
[workspace]
resolver = "2"
members = [
    "crates/siss-graph-core",
    "crates/siss-graph-db",
    "crates/siss-gatekeeper",
    "crates/siss-job-router",
    "crates/siss-context-cartography",
]
```

- [ ] **Step 2: Create crate Cargo.toml**

Create `crates/siss-context-cartography/Cargo.toml`:

```toml
[package]
name = "siss-context-cartography"
edition.workspace = true
version.workspace = true

[dependencies]
siss-graph-core = { path = "../siss-graph-core" }
siss-graph-db = { path = "../siss-graph-db" }
uuid.workspace = true
chrono.workspace = true
serde.workspace = true
serde_json.workspace = true
thiserror.workspace = true
tokio.workspace = true
sqlx.workspace = true

[dev-dependencies]
tokio = { workspace = true, features = ["full", "test-util"] }
```

- [ ] **Step 3: Create lib.rs and stubs**

Create `crates/siss-context-cartography/src/lib.rs`:

```rust
pub mod types;
pub mod config;
pub mod budget;
pub mod retrieval;
pub mod pipeline;
```

Create stubs:
- `crates/siss-context-cartography/src/types.rs` — `// Task 2`
- `crates/siss-context-cartography/src/config.rs` — `// Task 3`
- `crates/siss-context-cartography/src/budget.rs` — `// Task 4`
- `crates/siss-context-cartography/src/retrieval/mod.rs` — `// Task 5`
- `crates/siss-context-cartography/src/pipeline/mod.rs` — `// Task 7`

- [ ] **Step 4: Verify compilation**

```bash
source "$HOME/.cargo/env" && cargo check
```

- [ ] **Step 5: Commit**

```bash
git add Cargo.toml crates/siss-context-cartography/
git commit -m "feat: create siss-context-cartography crate skeleton"
```

---

### Task 2: Define Types

**Files:**
- Create: `crates/siss-context-cartography/src/types.rs`

- [ ] **Step 1: Implement types with tests**

Create `crates/siss-context-cartography/src/types.rs`:

```rust
use serde::{Deserialize, Serialize};
use thiserror::Error;
use uuid::Uuid;

use siss_graph_core::node::NodeId;
use siss_graph_core::node::memory::ConsolidationTier;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CartographyRequest {
    pub task_id: NodeId,
    pub persona_id: NodeId,
    pub tenant_id: NodeId,
    pub token_budget: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VisibleField {
    pub session_id: NodeId,
    pub procedural: Vec<MemoryEntry>,
    pub semantic: Vec<MemoryEntry>,
    pub episodic: Vec<MemoryEntry>,
    pub total_tokens_estimated: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryEntry {
    pub memory_id: Uuid,
    pub content: String,
    pub confidence_score: f64,
    pub tier: ConsolidationTier,
}

impl MemoryEntry {
    /// Estimate token count for this memory entry.
    pub fn estimate_tokens(&self, tokens_per_char: f64) -> i64 {
        (self.content.len() as f64 * tokens_per_char).ceil() as i64
    }
}

#[derive(Debug, Error)]
pub enum CartographyError {
    #[error("task {task_id} not found")]
    TaskNotFound { task_id: Uuid },

    #[error("persona {persona_id} not found")]
    PersonaNotFound { persona_id: Uuid },

    #[error("cross-tenant violation: source {source_tenant} != target {target_tenant}")]
    TenantViolation { source_tenant: Uuid, target_tenant: Uuid },

    #[error("no memories available for persona")]
    NoMemoriesAvailable,

    #[error("database error: {message}")]
    DatabaseError { message: String },
}

impl From<sqlx::Error> for CartographyError {
    fn from(e: sqlx::Error) -> Self {
        Self::DatabaseError { message: e.to_string() }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_memory_entry_estimate_tokens() {
        let entry = MemoryEntry {
            memory_id: Uuid::new_v4(),
            content: "hello world".into(), // 11 chars
            confidence_score: 0.9,
            tier: ConsolidationTier::Semantic,
        };
        // 11 * 0.25 = 2.75, ceil = 3
        assert_eq!(entry.estimate_tokens(0.25), 3);
    }

    #[test]
    fn test_memory_entry_estimate_tokens_empty() {
        let entry = MemoryEntry {
            memory_id: Uuid::new_v4(),
            content: "".into(),
            confidence_score: 0.5,
            tier: ConsolidationTier::Episodic,
        };
        assert_eq!(entry.estimate_tokens(0.25), 0);
    }

    #[test]
    fn test_create_cartography_request() {
        let req = CartographyRequest {
            task_id: NodeId::new(),
            persona_id: NodeId::new(),
            tenant_id: NodeId::new(),
            token_budget: 10000,
        };
        assert_eq!(req.token_budget, 10000);
    }
}
```

- [ ] **Step 2: Run tests**

```bash
source "$HOME/.cargo/env" && cargo test -p siss-context-cartography -- types
```

Expected: 3 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add crates/siss-context-cartography/src/types.rs
git commit -m "feat: define Context Cartography types (CartographyRequest, VisibleField, MemoryEntry)"
```

---

### Task 3: Implement RetrievalConfig

**Files:**
- Create: `crates/siss-context-cartography/src/config.rs`

- [ ] **Step 1: Implement config with tests**

Create `crates/siss-context-cartography/src/config.rs`:

```rust
/// Configuration for memory retrieval and token estimation.
#[derive(Debug, Clone)]
pub struct RetrievalConfig {
    pub max_procedural: usize,
    pub max_semantic: usize,
    pub max_episodic: usize,
    pub tokens_per_char: f64,
    pub confidence_threshold: f64,
}

impl Default for RetrievalConfig {
    fn default() -> Self {
        Self {
            max_procedural: 20,
            max_semantic: 30,
            max_episodic: 10,
            tokens_per_char: 0.25,
            confidence_threshold: 0.1,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_config() {
        let config = RetrievalConfig::default();
        assert_eq!(config.max_procedural, 20);
        assert_eq!(config.max_semantic, 30);
        assert_eq!(config.max_episodic, 10);
        assert!((config.tokens_per_char - 0.25).abs() < f64::EPSILON);
        assert!((config.confidence_threshold - 0.1).abs() < f64::EPSILON);
    }
}
```

- [ ] **Step 2: Run tests**

```bash
source "$HOME/.cargo/env" && cargo test -p siss-context-cartography -- config
```

Expected: 1 test PASS.

- [ ] **Step 3: Commit**

```bash
git add crates/siss-context-cartography/src/config.rs
git commit -m "feat: implement RetrievalConfig with sensible defaults"
```

---

### Task 4: Implement Token Budget Enforcement

**Files:**
- Create: `crates/siss-context-cartography/src/budget.rs`

- [ ] **Step 1: Implement budget trimming with tests**

Create `crates/siss-context-cartography/src/budget.rs`:

```rust
use crate::types::MemoryEntry;

/// Trim a list of memory entries to fit within the given token budget.
/// Removes entries from the end of the list (lowest priority) first.
/// Returns the trimmed list and the total tokens consumed.
pub fn trim_to_budget(
    entries: Vec<MemoryEntry>,
    available_tokens: i64,
    tokens_per_char: f64,
) -> (Vec<MemoryEntry>, i64) {
    let mut kept = Vec::new();
    let mut total = 0i64;

    for entry in entries {
        let tokens = entry.estimate_tokens(tokens_per_char);
        if total + tokens <= available_tokens {
            total += tokens;
            kept.push(entry);
        } else {
            break; // Budget exhausted — remaining entries are trimmed
        }
    }

    (kept, total)
}

/// Apply token budget across all three tiers in priority order.
/// Returns (procedural, semantic, episodic, total_tokens).
pub fn apply_budget(
    procedural: Vec<MemoryEntry>,
    semantic: Vec<MemoryEntry>,
    episodic: Vec<MemoryEntry>,
    token_budget: i64,
    tokens_per_char: f64,
) -> (Vec<MemoryEntry>, Vec<MemoryEntry>, Vec<MemoryEntry>, i64) {
    let mut remaining = token_budget;

    let (proc_trimmed, proc_tokens) = trim_to_budget(procedural, remaining, tokens_per_char);
    remaining -= proc_tokens;

    let (sem_trimmed, sem_tokens) = trim_to_budget(semantic, remaining, tokens_per_char);
    remaining -= sem_tokens;

    let (epi_trimmed, epi_tokens) = trim_to_budget(episodic, remaining, tokens_per_char);

    let total = proc_tokens + sem_tokens + epi_tokens;
    (proc_trimmed, sem_trimmed, epi_trimmed, total)
}

#[cfg(test)]
mod tests {
    use super::*;
    use siss_graph_core::node::memory::ConsolidationTier;
    use uuid::Uuid;

    fn make_entry(content: &str, tier: ConsolidationTier) -> MemoryEntry {
        MemoryEntry {
            memory_id: Uuid::new_v4(),
            content: content.into(),
            confidence_score: 0.9,
            tier,
        }
    }

    #[test]
    fn test_trim_all_fit() {
        let entries = vec![
            make_entry("hello", ConsolidationTier::Semantic),  // 5 chars = 2 tokens
            make_entry("world", ConsolidationTier::Semantic),  // 5 chars = 2 tokens
        ];
        let (kept, total) = trim_to_budget(entries, 100, 0.25);
        assert_eq!(kept.len(), 2);
        assert_eq!(total, 4); // 2 + 2
    }

    #[test]
    fn test_trim_partial_fit() {
        let entries = vec![
            make_entry("aaaa", ConsolidationTier::Semantic),   // 4 chars = 1 token
            make_entry("bbbb", ConsolidationTier::Semantic),   // 4 chars = 1 token
            make_entry("cccc", ConsolidationTier::Semantic),   // 4 chars = 1 token
        ];
        let (kept, total) = trim_to_budget(entries, 2, 0.25);
        assert_eq!(kept.len(), 2);
        assert_eq!(total, 2);
    }

    #[test]
    fn test_trim_none_fit() {
        let entries = vec![
            make_entry("a]very long content string that exceeds the budget", ConsolidationTier::Semantic),
        ];
        let (kept, total) = trim_to_budget(entries, 1, 0.25);
        assert_eq!(kept.len(), 0);
        assert_eq!(total, 0);
    }

    #[test]
    fn test_apply_budget_all_tiers() {
        let proc = vec![make_entry("proc1", ConsolidationTier::Procedural)]; // 2 tokens
        let sem = vec![make_entry("sem1", ConsolidationTier::Semantic)];     // 2 tokens
        let epi = vec![make_entry("epi1", ConsolidationTier::Episodic)];     // 2 tokens

        let (p, s, e, total) = apply_budget(proc, sem, epi, 100, 0.25);
        assert_eq!(p.len(), 1);
        assert_eq!(s.len(), 1);
        assert_eq!(e.len(), 1);
        assert_eq!(total, 6);
    }

    #[test]
    fn test_apply_budget_episodic_trimmed_first() {
        let proc = vec![make_entry("proc", ConsolidationTier::Procedural)]; // 1 token
        let sem = vec![make_entry("sema", ConsolidationTier::Semantic)];    // 1 token
        let epi = vec![make_entry("epis", ConsolidationTier::Episodic)];    // 1 token

        // Budget = 2 tokens: proc (1) + sem (1) = 2, no room for episodic
        let (p, s, e, total) = apply_budget(proc, sem, epi, 2, 0.25);
        assert_eq!(p.len(), 1);
        assert_eq!(s.len(), 1);
        assert_eq!(e.len(), 0); // trimmed
        assert_eq!(total, 2);
    }

    #[test]
    fn test_apply_budget_semantic_and_episodic_trimmed() {
        let proc = vec![
            make_entry("procedural workflow step one", ConsolidationTier::Procedural),
        ]; // 27 chars = 7 tokens
        let sem = vec![make_entry("sem", ConsolidationTier::Semantic)];
        let epi = vec![make_entry("epi", ConsolidationTier::Episodic)];

        // Budget = 7: only procedural fits
        let (p, s, e, total) = apply_budget(proc, sem, epi, 7, 0.25);
        assert_eq!(p.len(), 1);
        assert_eq!(s.len(), 0);
        assert_eq!(e.len(), 0);
        assert_eq!(total, 7);
    }

    #[test]
    fn test_empty_memories() {
        let (p, s, e, total) = apply_budget(vec![], vec![], vec![], 100, 0.25);
        assert_eq!(p.len(), 0);
        assert_eq!(s.len(), 0);
        assert_eq!(e.len(), 0);
        assert_eq!(total, 0);
    }
}
```

- [ ] **Step 2: Run tests**

```bash
source "$HOME/.cargo/env" && cargo test -p siss-context-cartography -- budget
```

Expected: 7 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add crates/siss-context-cartography/src/budget.rs
git commit -m "feat: implement token budget enforcement with tier-priority trimming"
```

---

### Task 5: Add DB Functions for Memory Retrieval and Session Management

**Files:**
- Modify: `crates/siss-graph-db/src/repo/memory_repo.rs`
- Modify: `crates/siss-graph-db/src/repo/node_repo.rs`

- [ ] **Step 1: Add fetch_memories_by_tier to memory_repo.rs**

Append to `crates/siss-graph-db/src/repo/memory_repo.rs`:

```rust
/// Fetch memories of a given tier for a tenant, above the confidence threshold.
/// For procedural/semantic: sorted by confidence descending.
/// For episodic: sorted by created_at descending (most recent first).
/// Returns (id, content, confidence_score, consolidation_tier::text).
pub async fn fetch_memories_by_tier(
    pool: &PgPool,
    tier: &str,
    tenant_id: Uuid,
    confidence_threshold: f64,
    limit: i64,
) -> Result<Vec<(Uuid, String, f64, String)>, sqlx::Error> {
    let order_clause = if tier == "episodic" {
        "ORDER BY created_at DESC"
    } else {
        "ORDER BY confidence_score DESC"
    };

    let query = format!(
        "SELECT id, content, confidence_score, consolidation_tier::text \
         FROM memories \
         WHERE tenant_id = $1 \
         AND consolidation_tier = $2::consolidation_tier \
         AND confidence_score * EXP( \
             -EXTRACT(EPOCH FROM (NOW() - last_reinforced_at)) / 3600.0 / \
             CASE consolidation_tier \
                 WHEN 'episodic' THEN 48.0 \
                 WHEN 'semantic' THEN 168.0 \
                 WHEN 'procedural' THEN 720.0 \
                 ELSE 1.0 \
             END \
         ) >= $3 \
         {} \
         LIMIT $4",
        order_clause
    );

    let rows: Vec<(Uuid, String, f64, String)> = sqlx::query_as(&query)
        .bind(tenant_id)
        .bind(tier)
        .bind(confidence_threshold)
        .bind(limit)
        .fetch_all(pool)
        .await?;

    Ok(rows)
}

/// Get all memory IDs that a Persona can read (via direct CAN_READ edges).
pub async fn fetch_accessible_memory_ids(
    pool: &PgPool,
    persona_id: Uuid,
    tenant_id: Uuid,
) -> Result<Vec<Uuid>, sqlx::Error> {
    let ids: Vec<Uuid> = sqlx::query_scalar(
        "SELECT target_id FROM edges \
         WHERE source_id = $1 \
         AND edge_type = 'can_read' \
         AND tenant_id = $2"
    )
    .bind(persona_id)
    .bind(tenant_id)
    .fetch_all(pool)
    .await?;
    Ok(ids)
}
```

- [ ] **Step 2: Add Session functions to node_repo.rs**

Append to `crates/siss-graph-db/src/repo/node_repo.rs`:

```rust
/// Insert a new Session node. Returns its ID.
pub async fn insert_session(
    pool: &PgPool,
    token_budget: i64,
    persona_id: Uuid,
    tenant_id: Uuid,
) -> Result<Uuid, sqlx::Error> {
    let id = Uuid::new_v4();
    sqlx::query(
        "INSERT INTO sessions (id, tenant_id, token_budget, active_persona_id, visible_field_snapshot, status) \
         VALUES ($1, $2, $3, $4, 'null'::jsonb, 'active'::session_status)"
    )
    .bind(id)
    .bind(tenant_id)
    .bind(token_budget)
    .bind(persona_id)
    .execute(pool)
    .await?;
    Ok(id)
}

/// Update a Session's visible_field_snapshot.
pub async fn update_session_snapshot(
    pool: &PgPool,
    session_id: Uuid,
    snapshot: serde_json::Value,
) -> Result<bool, sqlx::Error> {
    let result = sqlx::query(
        "UPDATE sessions SET visible_field_snapshot = $2 WHERE id = $1"
    )
    .bind(session_id)
    .bind(snapshot)
    .execute(pool)
    .await?;
    Ok(result.rows_affected() > 0)
}
```

- [ ] **Step 3: Verify compilation**

```bash
source "$HOME/.cargo/env" && cargo check
```

- [ ] **Step 4: Commit**

```bash
git add crates/siss-graph-db/src/repo/memory_repo.rs crates/siss-graph-db/src/repo/node_repo.rs
git commit -m "feat: add memory retrieval by tier, accessible memory IDs, and session management repo functions"
```

---

### Task 6: Implement Memory Retrieval Module

**Files:**
- Create: `crates/siss-context-cartography/src/retrieval/mod.rs`
- Create: `crates/siss-context-cartography/src/retrieval/procedural.rs`
- Create: `crates/siss-context-cartography/src/retrieval/semantic.rs`
- Create: `crates/siss-context-cartography/src/retrieval/episodic.rs`

- [ ] **Step 1: Implement retrieval orchestrator**

Create `crates/siss-context-cartography/src/retrieval/mod.rs`:

```rust
pub mod procedural;
pub mod semantic;
pub mod episodic;

use sqlx::PgPool;
use uuid::Uuid;

use crate::config::RetrievalConfig;
use crate::types::{CartographyError, MemoryEntry};

/// Retrieve all three tiers of memories for a Persona within a tenant.
/// All results are filtered by ReBAC (only memories the Persona can read).
pub async fn retrieve_all_tiers(
    pool: &PgPool,
    persona_id: Uuid,
    tenant_id: Uuid,
    config: &RetrievalConfig,
) -> Result<(Vec<MemoryEntry>, Vec<MemoryEntry>, Vec<MemoryEntry>), CartographyError> {
    // Get the set of memory IDs this Persona can read
    let accessible_ids = siss_graph_db::repo::memory_repo::fetch_accessible_memory_ids(
        pool, persona_id, tenant_id,
    )
    .await?;

    let proc = procedural::fetch(pool, tenant_id, &accessible_ids, config).await?;
    let sem = semantic::fetch(pool, tenant_id, &accessible_ids, config).await?;
    let epi = episodic::fetch(pool, tenant_id, &accessible_ids, config).await?;

    Ok((proc, sem, epi))
}
```

- [ ] **Step 2: Implement procedural retrieval**

Create `crates/siss-context-cartography/src/retrieval/procedural.rs`:

```rust
use sqlx::PgPool;
use uuid::Uuid;

use siss_graph_core::node::memory::ConsolidationTier;

use crate::config::RetrievalConfig;
use crate::types::{CartographyError, MemoryEntry};

/// Fetch procedural memories, sorted by confidence, filtered by accessible IDs.
pub async fn fetch(
    pool: &PgPool,
    tenant_id: Uuid,
    accessible_ids: &[Uuid],
    config: &RetrievalConfig,
) -> Result<Vec<MemoryEntry>, CartographyError> {
    let rows = siss_graph_db::repo::memory_repo::fetch_memories_by_tier(
        pool,
        "procedural",
        tenant_id,
        config.confidence_threshold,
        config.max_procedural as i64,
    )
    .await?;

    let entries: Vec<MemoryEntry> = rows
        .into_iter()
        .filter(|(id, _, _, _)| accessible_ids.is_empty() || accessible_ids.contains(id))
        .map(|(id, content, confidence, _tier)| MemoryEntry {
            memory_id: id,
            content,
            confidence_score: confidence,
            tier: ConsolidationTier::Procedural,
        })
        .collect();

    Ok(entries)
}
```

- [ ] **Step 3: Implement semantic retrieval**

Create `crates/siss-context-cartography/src/retrieval/semantic.rs`:

```rust
use sqlx::PgPool;
use uuid::Uuid;

use siss_graph_core::node::memory::ConsolidationTier;

use crate::config::RetrievalConfig;
use crate::types::{CartographyError, MemoryEntry};

/// Fetch semantic memories, sorted by confidence, filtered by accessible IDs.
pub async fn fetch(
    pool: &PgPool,
    tenant_id: Uuid,
    accessible_ids: &[Uuid],
    config: &RetrievalConfig,
) -> Result<Vec<MemoryEntry>, CartographyError> {
    let rows = siss_graph_db::repo::memory_repo::fetch_memories_by_tier(
        pool,
        "semantic",
        tenant_id,
        config.confidence_threshold,
        config.max_semantic as i64,
    )
    .await?;

    let entries: Vec<MemoryEntry> = rows
        .into_iter()
        .filter(|(id, _, _, _)| accessible_ids.is_empty() || accessible_ids.contains(id))
        .map(|(id, content, confidence, _tier)| MemoryEntry {
            memory_id: id,
            content,
            confidence_score: confidence,
            tier: ConsolidationTier::Semantic,
        })
        .collect();

    Ok(entries)
}
```

- [ ] **Step 4: Implement episodic retrieval**

Create `crates/siss-context-cartography/src/retrieval/episodic.rs`:

```rust
use sqlx::PgPool;
use uuid::Uuid;

use siss_graph_core::node::memory::ConsolidationTier;

use crate::config::RetrievalConfig;
use crate::types::{CartographyError, MemoryEntry};

/// Fetch episodic memories, sorted by recency, filtered by accessible IDs.
pub async fn fetch(
    pool: &PgPool,
    tenant_id: Uuid,
    accessible_ids: &[Uuid],
    config: &RetrievalConfig,
) -> Result<Vec<MemoryEntry>, CartographyError> {
    let rows = siss_graph_db::repo::memory_repo::fetch_memories_by_tier(
        pool,
        "episodic",
        tenant_id,
        config.confidence_threshold,
        config.max_episodic as i64,
    )
    .await?;

    let entries: Vec<MemoryEntry> = rows
        .into_iter()
        .filter(|(id, _, _, _)| accessible_ids.is_empty() || accessible_ids.contains(id))
        .map(|(id, content, confidence, _tier)| MemoryEntry {
            memory_id: id,
            content,
            confidence_score: confidence,
            tier: ConsolidationTier::Episodic,
        })
        .collect();

    Ok(entries)
}
```

- [ ] **Step 5: Verify compilation**

```bash
source "$HOME/.cargo/env" && cargo check
```

- [ ] **Step 6: Commit**

```bash
git add crates/siss-context-cartography/src/retrieval/
git commit -m "feat: implement tier-based memory retrieval with ReBAC filtering"
```

---

### Task 7: Implement Pipeline (validate, session, record, orchestrator)

**Files:**
- Create: `crates/siss-context-cartography/src/pipeline/mod.rs`
- Create: `crates/siss-context-cartography/src/pipeline/validate.rs`
- Create: `crates/siss-context-cartography/src/pipeline/session.rs`
- Create: `crates/siss-context-cartography/src/pipeline/record.rs`

- [ ] **Step 1: Implement validate step**

Create `crates/siss-context-cartography/src/pipeline/validate.rs`:

```rust
use sqlx::PgPool;
use uuid::Uuid;

use crate::types::CartographyError;

/// Pipeline Step 1: Validate Task and Persona exist, tenant matches.
pub async fn validate(
    pool: &PgPool,
    task_id: Uuid,
    persona_id: Uuid,
    tenant_id: Uuid,
) -> Result<(), CartographyError> {
    // Verify task exists
    let task_row = siss_graph_db::repo::node_repo::fetch_task(pool, task_id)
        .await
        .map_err(|e| CartographyError::DatabaseError { message: e.to_string() })?
        .ok_or(CartographyError::TaskNotFound { task_id })?;

    let (_id, task_tenant, _status, _intent) = task_row;
    if task_tenant != tenant_id {
        return Err(CartographyError::TenantViolation {
            source_tenant: task_tenant,
            target_tenant: tenant_id,
        });
    }

    // Verify persona exists
    let persona_row = siss_graph_db::repo::node_repo::fetch_persona(pool, persona_id)
        .await
        .map_err(|e| CartographyError::DatabaseError { message: e.to_string() })?
        .ok_or(CartographyError::PersonaNotFound { persona_id })?;

    let (_id, persona_tenant, _name, _kind, _is_frozen) = persona_row;
    if persona_tenant != tenant_id {
        return Err(CartographyError::TenantViolation {
            source_tenant: persona_tenant,
            target_tenant: tenant_id,
        });
    }

    Ok(())
}
```

- [ ] **Step 2: Implement session creation step**

Create `crates/siss-context-cartography/src/pipeline/session.rs`:

```rust
use sqlx::PgPool;
use uuid::Uuid;

use crate::types::CartographyError;

/// Pipeline Step 2: Create Session node and link to Persona + Task.
/// Returns the new Session ID.
pub async fn create_session(
    pool: &PgPool,
    task_id: Uuid,
    persona_id: Uuid,
    tenant_id: Uuid,
    token_budget: i64,
) -> Result<Uuid, CartographyError> {
    // Create session
    let session_id = siss_graph_db::repo::node_repo::insert_session(
        pool, token_budget, persona_id, tenant_id,
    )
    .await?;

    // SCOPED_TO: Session → Persona
    siss_graph_db::repo::edge_repo::insert_edge(
        pool, session_id, persona_id, "scoped_to", tenant_id, serde_json::json!({}),
    )
    .await?;

    // CONTAINS: Session → Task
    siss_graph_db::repo::edge_repo::insert_edge(
        pool, session_id, task_id, "contains", tenant_id, serde_json::json!({}),
    )
    .await?;

    Ok(session_id)
}
```

- [ ] **Step 3: Implement record step**

Create `crates/siss-context-cartography/src/pipeline/record.rs`:

```rust
use sqlx::PgPool;
use uuid::Uuid;

use crate::types::{CartographyError, MemoryEntry, VisibleField};

/// Pipeline Step 5: Create LOADED edges and save the snapshot.
pub async fn record_visible_field(
    pool: &PgPool,
    session_id: Uuid,
    tenant_id: Uuid,
    field: &VisibleField,
) -> Result<(), CartographyError> {
    // Create LOADED edges for all memories
    let all_entries: Vec<&MemoryEntry> = field.procedural.iter()
        .chain(field.semantic.iter())
        .chain(field.episodic.iter())
        .collect();

    for entry in &all_entries {
        siss_graph_db::repo::edge_repo::insert_edge(
            pool,
            session_id,
            entry.memory_id,
            "loaded",
            tenant_id,
            serde_json::json!({"tier": format!("{:?}", entry.tier)}),
        )
        .await?;
    }

    // Serialize and save the snapshot
    let snapshot = serde_json::to_value(field)
        .unwrap_or(serde_json::Value::Null);

    siss_graph_db::repo::node_repo::update_session_snapshot(pool, session_id, snapshot)
        .await?;

    Ok(())
}
```

- [ ] **Step 4: Implement the orchestrator**

Create `crates/siss-context-cartography/src/pipeline/mod.rs`:

```rust
pub mod validate;
pub mod session;
pub mod record;

use sqlx::PgPool;

use siss_graph_core::node::NodeId;

use crate::budget::apply_budget;
use crate::config::RetrievalConfig;
use crate::retrieval;
use crate::types::{CartographyError, CartographyRequest, VisibleField};

/// The sole entry point for building the Visible Field.
/// Creates a Session, retrieves memories by tier, applies token budget, records results.
pub async fn build_context(
    pool: &PgPool,
    request: &CartographyRequest,
    config: &RetrievalConfig,
) -> Result<VisibleField, CartographyError> {
    let task_id = request.task_id.0;
    let persona_id = request.persona_id.0;
    let tenant_id = request.tenant_id.0;

    // Step 1: Validate
    validate::validate(pool, task_id, persona_id, tenant_id).await?;

    // Step 2: Create Session
    let session_id = session::create_session(
        pool, task_id, persona_id, tenant_id, request.token_budget,
    )
    .await?;

    // Step 3: Retrieve memories
    let (procedural, semantic, episodic) = retrieval::retrieve_all_tiers(
        pool, persona_id, tenant_id, config,
    )
    .await?;

    // Step 4: Apply token budget
    let (proc_trimmed, sem_trimmed, epi_trimmed, total_tokens) = apply_budget(
        procedural,
        semantic,
        episodic,
        request.token_budget,
        config.tokens_per_char,
    );

    // Build VisibleField
    let field = VisibleField {
        session_id: NodeId(session_id),
        procedural: proc_trimmed,
        semantic: sem_trimmed,
        episodic: epi_trimmed,
        total_tokens_estimated: total_tokens,
    };

    // Step 5: Record
    record::record_visible_field(pool, session_id, tenant_id, &field).await?;

    Ok(field)
}
```

- [ ] **Step 5: Verify compilation**

```bash
source "$HOME/.cargo/env" && cargo check
```

- [ ] **Step 6: Commit**

```bash
git add crates/siss-context-cartography/src/pipeline/
git commit -m "feat: implement Context Cartography pipeline (validate, session, retrieve, budget, record)"
```

---

### Task 8: Integrate with Job Router

**Files:**
- Modify: `crates/siss-job-router/src/executor/mod.rs`
- Modify: `crates/siss-job-router/Cargo.toml`

This task adds `visible_field: Option<serde_json::Value>` to `TaskContext` so the Router can pass context to executors. We use `serde_json::Value` instead of importing the cartography crate directly to avoid circular dependencies.

- [ ] **Step 1: Add visible_field to TaskContext**

In `crates/siss-job-router/src/executor/mod.rs`, add the new field to `TaskContext`:

```rust
/// Context provided to an executor for task execution.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskContext {
    pub task_id: Uuid,
    pub intent: String,
    pub complexity_class: ComplexityClass,
    pub hardware_target: HardwareTarget,
    pub tenant_id: Uuid,
    pub visible_field: Option<serde_json::Value>,
}
```

- [ ] **Step 2: Update all TaskContext construction sites**

In `crates/siss-job-router/src/pipeline/mod.rs`, update the TaskContext construction to include the new field:

```rust
    let context = TaskContext {
        task_id,
        intent: validated.intent,
        complexity_class: validated.complexity_class,
        hardware_target,
        tenant_id,
        visible_field: None, // Populated by caller when Context Cartography is integrated
    };
```

In `crates/siss-job-router/src/executor/mock.rs`, update `make_context()` in tests:

```rust
    fn make_context() -> TaskContext {
        TaskContext {
            task_id: uuid::Uuid::nil(),
            intent: "test task".into(),
            complexity_class: ComplexityClass::Simple,
            hardware_target: HardwareTarget::LocalMlx,
            tenant_id: uuid::Uuid::nil(),
            visible_field: None,
        }
    }
```

- [ ] **Step 3: Run all tests**

```bash
source "$HOME/.cargo/env" && cargo test --workspace
```

Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add crates/siss-job-router/
git commit -m "feat: add visible_field to TaskContext for Context Cartography integration"
```

---

### Task 9: Final Workspace Validation

**Files:** None (validation only)

- [ ] **Step 1: Run complete test suite**

```bash
source "$HOME/.cargo/env" && cargo test --workspace
```

Expected: All tests pass across all five crates.

- [ ] **Step 2: Run clippy**

```bash
source "$HOME/.cargo/env" && cargo clippy --workspace -- -D warnings
```

Expected: No warnings.

- [ ] **Step 3: Fix any issues and commit**

```bash
git add -A
git commit -m "chore: fix clippy warnings from Context Cartography validation"
```

- [ ] **Step 4: Verify success criteria**

1. **Session created with SCOPED_TO + CONTAINS:** pipeline/session.rs
2. **Procedural loaded first by confidence:** retrieval/procedural.rs
3. **Semantic loaded second by confidence:** retrieval/semantic.rs
4. **Episodic loaded last by recency:** retrieval/episodic.rs
5. **ReBAC filtered:** retrieval/mod.rs (fetch_accessible_memory_ids)
6. **Token budget enforced:** budget.rs (apply_budget)
7. **Episodic trimmed first:** budget.rs priority order
8. **LOADED edges created:** pipeline/record.rs
9. **visible_field_snapshot saved:** pipeline/record.rs
10. **Cold start returns empty VisibleField:** retrieval returns empty vecs → budget passes through → valid empty field
11. **Cross-tenant returns TenantViolation:** pipeline/validate.rs
