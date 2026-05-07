# A2A Agent Card Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `siss-agent-card` crate — a Google A2A-compatible agent discovery layer that stores agent cards in the SISS Knowledge Graph and serves them at `/.well-known/agent.json`.

**Architecture:** A dedicated `agent_cards` table stores agent card data alongside the persona it belongs to. An `AgentCardBuilder` assembles a complete `AgentCard` from the graph (persona + `CAN_EXECUTE` edges → tools as skills). A serializer converts the in-memory `AgentCard` to Google A2A JSON, with an opt-in `x-siss` extension block. An optional axum feature provides the HTTP handler.

**Tech Stack:** Rust, SQLx 0.8 (Postgres), serde_json, axum 0.7 (optional), testcontainers 0.23 (dev), tower (dev for handler tests).

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `crates/siss-graph-core/src/edge/mod.rs` | Modify | Add `HasAgentCard` variant to `EdgeType` |
| `crates/siss-graph-db/src/migrations/005_create_agent_cards.sql` | Create | Add `has_agent_card` enum value + `agent_cards` table |
| `crates/siss-graph-db/src/migrations/mod.rs` | Modify | Register migration 005 |
| `Cargo.toml` (workspace root) | Modify | Add `siss-agent-card` to workspace members |
| `crates/siss-agent-card/Cargo.toml` | Create | Crate manifest with optional `axum` feature |
| `crates/siss-agent-card/src/lib.rs` | Create | Public re-exports |
| `crates/siss-agent-card/src/types.rs` | Create | All types + `AgentCardError` |
| `crates/siss-agent-card/src/repo.rs` | Create | `insert_agent_card` / `fetch_agent_card_node` |
| `crates/siss-agent-card/src/serializer.rs` | Create | `to_a2a_json` |
| `crates/siss-agent-card/src/builder.rs` | Create | `AgentCardBuilder` |
| `crates/siss-agent-card/src/handler.rs` | Create | `well_known_agent_handler` (axum feature only) |

---

## Task 1: DB Infrastructure — `has_agent_card` edge type and `agent_cards` table

**Files:**
- Modify: `crates/siss-graph-core/src/edge/mod.rs`
- Create: `crates/siss-graph-db/src/migrations/005_create_agent_cards.sql`
- Modify: `crates/siss-graph-db/src/migrations/mod.rs`

- [ ] **Step 1: Write the failing test for `EdgeType::HasAgentCard`**

In `crates/siss-graph-core/src/edge/mod.rs`, add the test at the bottom of the existing `#[cfg(test)]` block:

```rust
#[test]
fn test_has_agent_card_edge_type_exists() {
    let edge = EdgeRecord::new(
        NodeId::new(),
        NodeId::new(),
        EdgeType::HasAgentCard,
        NodeId::new(),
    );
    assert_eq!(edge.edge_type, EdgeType::HasAgentCard);
}
```

- [ ] **Step 2: Run test — expect compile error**

```bash
cd /Users/andriileukhin/Documents/SovereignNexus
cargo test -p siss-graph-core test_has_agent_card_edge_type_exists 2>&1 | tail -10
```

Expected: compile error `no variant or associated item named HasAgentCard found for enum EdgeType`.

- [ ] **Step 3: Add `HasAgentCard` to `EdgeType` in `siss-graph-core/src/edge/mod.rs`**

In the enum, after the `A2aDelegates` variant, add one line:

```rust
pub enum EdgeType {
    // Identity & Governance
    MemberOf,
    ActsAs,
    BelongsTo,
    // Access Control
    CanRead,
    CanWrite,
    CanExecute,
    DenyRead,
    DenyWrite,
    DenyExecute,
    // AP2
    AuthorizedBy,
    ReceiptedBy,
    // Execution
    InitiatedBy,
    GovernedBy,
    Produced,
    ScopedTo,
    Contains,
    Loaded,
    // Governance
    Enforces,
    ViolatedBy,
    AuthoredBy,
    // Cognitive
    DependsOn,
    Uses,
    Supports,
    Extends,
    Contradicts,
    Supersedes,
    // Swarm
    A2aDelegates,
    // A2A Discovery
    HasAgentCard,
}
```

- [ ] **Step 4: Run test — expect pass**

```bash
cargo test -p siss-graph-core test_has_agent_card_edge_type_exists
```

Expected: `test test_has_agent_card_edge_type_exists ... ok`

- [ ] **Step 5: Create migration `005_create_agent_cards.sql`**

Create file `crates/siss-graph-db/src/migrations/005_create_agent_cards.sql`:

```sql
-- SISS Knowledge Graph: Agent Cards (A2A Discovery)
-- Adds has_agent_card edge type and agent_cards table.

-- Add the new edge value. IF NOT EXISTS makes this idempotent.
ALTER TYPE edge_type ADD VALUE IF NOT EXISTS 'has_agent_card';

-- Agent Card nodes — one per persona, per tenant.
CREATE TABLE IF NOT EXISTS agent_cards (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    persona_id UUID NOT NULL REFERENCES personas(id),
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT '0.1.0',
    url TEXT NOT NULL,
    hardware_affinity hardware_target NOT NULL DEFAULT 'local_mlx',
    budget_cap BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT agent_cards_persona_tenant_unique UNIQUE (persona_id, tenant_id)
);
CREATE INDEX IF NOT EXISTS idx_agent_cards_tenant ON agent_cards(tenant_id);
CREATE INDEX IF NOT EXISTS idx_agent_cards_persona ON agent_cards(persona_id);
```

- [ ] **Step 6: Register migration 005 in `crates/siss-graph-db/src/migrations/mod.rs`**

```rust
use sqlx::PgPool;

const MIGRATIONS: &[(&str, &str)] = &[
    ("001_create_base_schema", include_str!("001_create_base_schema.sql")),
    ("002_create_edges", include_str!("002_create_edges.sql")),
    ("003_create_age_graph", include_str!("003_create_age_graph.sql")),
    ("004_seed_governance", include_str!("004_seed_governance.sql")),
    ("005_create_agent_cards", include_str!("005_create_agent_cards.sql")),
];

/// Run all migrations in order. Idempotent — tracks applied migrations in a metadata table.
pub async fn run_all(pool: &PgPool) -> Result<(), sqlx::Error> {
    sqlx::query(
        "CREATE TABLE IF NOT EXISTS _siss_migrations (
            name TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ DEFAULT NOW()
        )"
    )
    .execute(pool)
    .await?;

    for (name, sql) in MIGRATIONS {
        let already_applied: bool = sqlx::query_scalar(
            "SELECT EXISTS(SELECT 1 FROM _siss_migrations WHERE name = $1)"
        )
        .bind(name)
        .fetch_one(pool)
        .await?;

        if !already_applied {
            sqlx::raw_sql(sql).execute(pool).await?;
            sqlx::query("INSERT INTO _siss_migrations (name) VALUES ($1)")
                .bind(name)
                .execute(pool)
                .await?;
        }
    }

    Ok(())
}
```

- [ ] **Step 7: Verify graph-core and graph-db compile**

```bash
cargo check -p siss-graph-core -p siss-graph-db
```

Expected: no errors.

- [ ] **Step 8: Commit**

```bash
git add crates/siss-graph-core/src/edge/mod.rs \
        crates/siss-graph-db/src/migrations/005_create_agent_cards.sql \
        crates/siss-graph-db/src/migrations/mod.rs
git commit -m "feat(graph): add HasAgentCard edge type and agent_cards table"
```

---

## Task 2: Crate Scaffold

**Files:**
- Create: `crates/siss-agent-card/Cargo.toml`
- Create: `crates/siss-agent-card/src/lib.rs`
- Modify: `Cargo.toml` (workspace root)

- [ ] **Step 1: Create `crates/siss-agent-card/Cargo.toml`**

```toml
[package]
name = "siss-agent-card"
edition.workspace = true
version.workspace = true

[features]
default = []
axum = ["dep:axum", "dep:tower", "dep:http-body-util"]

[dependencies]
siss-graph-core = { path = "../siss-graph-core" }
siss-graph-db   = { path = "../siss-graph-db" }
uuid.workspace = true
chrono.workspace = true
serde.workspace = true
serde_json.workspace = true
thiserror.workspace = true
tokio.workspace = true
sqlx.workspace = true
axum            = { version = "0.7", optional = true }
tower           = { version = "0.4", optional = true }
http-body-util  = { version = "0.1", optional = true }

[dev-dependencies]
testcontainers  = { workspace = true }
tokio           = { workspace = true, features = ["full", "test-util"] }
tower           = "0.4"
http-body-util  = "0.1"
axum            = "0.7"
```

- [ ] **Step 2: Create `crates/siss-agent-card/src/lib.rs`**

```rust
pub mod types;
pub mod repo;
pub mod serializer;
pub mod builder;

#[cfg(feature = "axum")]
pub mod handler;
```

- [ ] **Step 3: Add crate to workspace `Cargo.toml`**

In the root `Cargo.toml`, update the `members` list:

```toml
[workspace]
resolver = "2"
members = [
    "crates/siss-graph-core",
    "crates/siss-graph-db",
    "crates/siss-gatekeeper",
    "crates/siss-job-router",
    "crates/siss-context-cartography",
    "crates/siss-behavioral-firewall",
    "crates/siss-feedback-router",
    "crates/siss-agent-shell",
    "crates/siss-agent-card",
]
```

- [ ] **Step 4: Create stub files so the crate compiles**

Create `crates/siss-agent-card/src/types.rs`:
```rust
// stubs — filled in Task 3
```

Create `crates/siss-agent-card/src/repo.rs`:
```rust
// stubs — filled in Task 4
```

Create `crates/siss-agent-card/src/serializer.rs`:
```rust
// stubs — filled in Task 5
```

Create `crates/siss-agent-card/src/builder.rs`:
```rust
// stubs — filled in Task 6
```

Create `crates/siss-agent-card/src/handler.rs`:
```rust
// stubs — filled in Task 7
```

- [ ] **Step 5: Verify crate compiles**

```bash
cargo check -p siss-agent-card
```

Expected: no errors (stub files are empty).

- [ ] **Step 6: Commit**

```bash
git add crates/siss-agent-card/ Cargo.toml
git commit -m "feat(agent-card): scaffold siss-agent-card crate"
```

---

## Task 3: Types

**Files:**
- Modify: `crates/siss-agent-card/src/types.rs`

- [ ] **Step 1: Write failing tests**

Replace `crates/siss-agent-card/src/types.rs` with:

```rust
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use siss_graph_core::node::NodeId;
use siss_graph_core::node::execution::HardwareTarget;

// ── AgentCardNode ──────────────────────────────────────────────────────────────

/// The authoritative record stored in the SISS Knowledge Graph.
/// `allowed_tools` is populated by the builder from CAN_EXECUTE edges —
/// `fetch_agent_card_node` returns it as an empty vec.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentCardNode {
    pub id: NodeId,
    pub persona_id: NodeId,
    pub tenant_id: NodeId,
    pub name: String,
    pub description: String,
    pub version: String,
    pub url: String,
    pub hardware_affinity: HardwareTarget,
    pub budget_cap: i64,
    pub allowed_tools: Vec<NodeId>,
    pub created_at: DateTime<Utc>,
}

// ── AgentCard (in-memory working type) ────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct AgentCard {
    pub node: AgentCardNode,
    pub skills: Vec<Skill>,
    pub capabilities: Capability,
    pub authentication: Authentication,
}

// ── Supporting types ──────────────────────────────────────────────────────────

/// A single A2A skill — corresponds to one tool the persona can execute.
#[derive(Debug, Clone)]
pub struct Skill {
    /// snake_case identifier, e.g. "mcp_filesystem"
    pub id: String,
    pub name: String,
    pub description: String,
    pub tags: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct Capability {
    /// true because siss-agent-shell emits AG-UI events
    pub streaming: bool,
    /// false in Phase 3
    pub push_notifications: bool,
}

#[derive(Debug, Clone)]
pub struct Authentication {
    /// e.g. ["Bearer"]
    pub schemes: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct SerializeOptions {
    /// When true, include the `x-siss` extension block in the JSON output.
    pub extended: bool,
}

// ── AgentCardError ────────────────────────────────────────────────────────────

#[derive(Debug, thiserror::Error)]
pub enum AgentCardError {
    #[error("persona not found: {persona_id}")]
    PersonaNotFound { persona_id: Uuid },
    #[error("agent card not found for persona: {persona_id}")]
    CardNotFound { persona_id: Uuid },
    #[error("database error: {message}")]
    DatabaseError { message: String },
}

impl From<sqlx::Error> for AgentCardError {
    fn from(e: sqlx::Error) -> Self {
        AgentCardError::DatabaseError { message: e.to_string() }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_persona_not_found_error_message() {
        let id = Uuid::nil();
        let err = AgentCardError::PersonaNotFound { persona_id: id };
        assert_eq!(
            err.to_string(),
            "persona not found: 00000000-0000-0000-0000-000000000000"
        );
    }

    #[test]
    fn test_card_not_found_error_message() {
        let id = Uuid::nil();
        let err = AgentCardError::CardNotFound { persona_id: id };
        assert_eq!(
            err.to_string(),
            "agent card not found for persona: 00000000-0000-0000-0000-000000000000"
        );
    }

    #[test]
    fn test_database_error_message() {
        let err = AgentCardError::DatabaseError { message: "conn refused".into() };
        assert_eq!(err.to_string(), "database error: conn refused");
    }

    #[test]
    fn test_from_sqlx_error() {
        let sqlx_err = sqlx::Error::RowNotFound;
        let err: AgentCardError = sqlx_err.into();
        assert!(matches!(err, AgentCardError::DatabaseError { .. }));
    }

    #[test]
    fn test_agent_card_node_fields() {
        let tenant_id = NodeId::new();
        let persona_id = NodeId::new();
        let node = AgentCardNode {
            id: NodeId::new(),
            persona_id,
            tenant_id,
            name: "TestAgent".into(),
            description: "A test agent".into(),
            version: "0.1.0".into(),
            url: "https://example.com".into(),
            hardware_affinity: HardwareTarget::LocalMlx,
            budget_cap: 50_000,
            allowed_tools: vec![],
            created_at: Utc::now(),
        };
        assert_eq!(node.name, "TestAgent");
        assert_eq!(node.budget_cap, 50_000);
        assert_eq!(node.hardware_affinity, HardwareTarget::LocalMlx);
    }

    #[test]
    fn test_serialize_options_default_not_extended() {
        let opts = SerializeOptions { extended: false };
        assert!(!opts.extended);
    }
}
```

- [ ] **Step 2: Run tests — expect compile error (thiserror, sqlx not in scope)**

```bash
cargo test -p siss-agent-card 2>&1 | tail -15
```

Expected: compile errors because `types.rs` now has real content but other modules are stubs.

- [ ] **Step 3: Clear stubs in other modules so they compile**

Replace `crates/siss-agent-card/src/repo.rs` with an empty module:

```rust
```

Replace `crates/siss-agent-card/src/serializer.rs` with:

```rust
```

Replace `crates/siss-agent-card/src/builder.rs` with:

```rust
```

Replace `crates/siss-agent-card/src/handler.rs` with:

```rust
```

- [ ] **Step 4: Run tests — expect pass**

```bash
cargo test -p siss-agent-card 2>&1 | tail -10
```

Expected: all 5 tests in `types` pass.

- [ ] **Step 5: Commit**

```bash
git add crates/siss-agent-card/src/types.rs crates/siss-agent-card/src/
git commit -m "feat(agent-card): add types — AgentCardNode, AgentCard, AgentCardError"
```

---

## Task 4: Repo

**Files:**
- Modify: `crates/siss-agent-card/src/repo.rs`

The repo has two functions:
- `insert_agent_card(pool, node) -> Result<Uuid, AgentCardError>` — inserts the row and a `has_agent_card` edge in a transaction.
- `fetch_agent_card_node(pool, persona_id) -> Result<Option<AgentCardNode>, AgentCardError>` — reads from `agent_cards` WHERE `persona_id = $1`. Returns `AgentCardNode` with `allowed_tools: vec![]`.

The `hardware_affinity` column uses the `hardware_target` DB enum. When inserting, cast with `::hardware_target`. When reading, cast with `::text` and parse with a helper.

- [ ] **Step 1: Write the failing tests**

Replace `crates/siss-agent-card/src/repo.rs` with:

```rust
use chrono::Utc;
use sqlx::PgPool;
use uuid::Uuid;

use siss_graph_core::node::NodeId;
use siss_graph_core::node::execution::HardwareTarget;

use crate::types::{AgentCardError, AgentCardNode};

// ── Helpers ───────────────────────────────────────────────────────────────────

fn hardware_target_str(h: HardwareTarget) -> &'static str {
    match h {
        HardwareTarget::LocalMlx => "local_mlx",
        HardwareTarget::RemoteFrontier => "remote_frontier",
        HardwareTarget::Hybrid => "hybrid",
    }
}

fn parse_hardware_target(s: &str) -> HardwareTarget {
    match s {
        "local_mlx" => HardwareTarget::LocalMlx,
        "remote_frontier" => HardwareTarget::RemoteFrontier,
        "hybrid" => HardwareTarget::Hybrid,
        _ => HardwareTarget::LocalMlx,
    }
}

// ── Public API ────────────────────────────────────────────────────────────────

/// Insert an AgentCardNode and a `has_agent_card` edge from persona → card,
/// in a single transaction. Returns the new card's UUID.
pub async fn insert_agent_card(
    pool: &PgPool,
    node: &AgentCardNode,
) -> Result<Uuid, AgentCardError> {
    let mut tx = pool.begin().await?;

    sqlx::query(
        "INSERT INTO agent_cards \
         (id, tenant_id, persona_id, name, description, version, url, hardware_affinity, budget_cap) \
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8::hardware_target, $9)"
    )
    .bind(node.id.0)
    .bind(node.tenant_id.0)
    .bind(node.persona_id.0)
    .bind(&node.name)
    .bind(&node.description)
    .bind(&node.version)
    .bind(&node.url)
    .bind(hardware_target_str(node.hardware_affinity))
    .bind(node.budget_cap)
    .execute(&mut *tx)
    .await?;

    let edge_id = Uuid::new_v4();
    sqlx::query(
        "INSERT INTO edges (id, source_id, target_id, edge_type, tenant_id, metadata) \
         VALUES ($1, $2, $3, 'has_agent_card'::edge_type, $4, '{}'::jsonb)"
    )
    .bind(edge_id)
    .bind(node.persona_id.0)
    .bind(node.id.0)
    .bind(node.tenant_id.0)
    .execute(&mut *tx)
    .await?;

    tx.commit().await?;
    Ok(node.id.0)
}

/// Fetch an AgentCardNode by persona_id.
/// Returns `allowed_tools: vec![]` — the builder populates tools from edges.
pub async fn fetch_agent_card_node(
    pool: &PgPool,
    persona_id: Uuid,
) -> Result<Option<AgentCardNode>, AgentCardError> {
    let row: Option<(Uuid, Uuid, Uuid, String, String, String, String, String, i64, chrono::DateTime<Utc>)> =
        sqlx::query_as(
            "SELECT id, tenant_id, persona_id, name, description, version, url, \
             hardware_affinity::text, budget_cap, created_at \
             FROM agent_cards WHERE persona_id = $1"
        )
        .bind(persona_id)
        .fetch_optional(pool)
        .await?;

    Ok(row.map(|(id, tenant_id, persona_id, name, description, version, url, hw, budget_cap, created_at)| {
        AgentCardNode {
            id: NodeId(id),
            tenant_id: NodeId(tenant_id),
            persona_id: NodeId(persona_id),
            name,
            description,
            version,
            url,
            hardware_affinity: parse_hardware_target(&hw),
            budget_cap,
            allowed_tools: vec![],
            created_at,
        }
    }))
}

#[cfg(test)]
mod tests {
    use super::*;
    use testcontainers::{
        core::{IntoContainerPort, WaitFor},
        runners::AsyncRunner,
        GenericImage, ImageExt,
    };

    async fn start_postgres() -> (testcontainers::ContainerAsync<GenericImage>, PgPool) {
        let container = GenericImage::new("postgres", "16")
            .with_wait_for(WaitFor::message_on_stderr(
                "database system is ready to accept connections",
            ))
            .with_env_var("POSTGRES_PASSWORD", "postgres")
            .with_env_var("POSTGRES_DB", "siss_test")
            .with_exposed_port(5432.tcp())
            .start()
            .await
            .expect("postgres started");

        let port = container.get_host_port_ipv4(5432).await.unwrap();
        let url = format!("postgres://postgres:postgres@127.0.0.1:{port}/siss_test");
        let pool = PgPool::connect(&url).await.expect("pool connect");
        siss_graph_db::migrations::run_all(&pool).await.expect("migrations");
        (container, pool)
    }

    async fn make_tenant_and_persona(pool: &PgPool) -> (Uuid, Uuid) {
        let tenant_id = siss_graph_db::repo::node_repo::insert_tenant(pool, "TestCorp")
            .await
            .expect("insert tenant");
        let persona_id = siss_graph_db::repo::node_repo::insert_persona(
            pool, "Aria", "ai_agent", tenant_id,
        )
        .await
        .expect("insert persona");
        (tenant_id, persona_id)
    }

    fn make_node(tenant_id: Uuid, persona_id: Uuid) -> AgentCardNode {
        AgentCardNode {
            id: NodeId::new(),
            tenant_id: NodeId(tenant_id),
            persona_id: NodeId(persona_id),
            name: "Aria Agent".into(),
            description: "Test agent".into(),
            version: "0.1.0".into(),
            url: "https://example.com/agent".into(),
            hardware_affinity: HardwareTarget::LocalMlx,
            budget_cap: 100_000,
            allowed_tools: vec![],
            created_at: Utc::now(),
        }
    }

    #[tokio::test]
    async fn test_insert_and_fetch_agent_card() {
        let (_container, pool) = start_postgres().await;
        let (tenant_id, persona_id) = make_tenant_and_persona(&pool).await;
        let node = make_node(tenant_id, persona_id);
        let card_id = node.id.0;

        insert_agent_card(&pool, &node).await.expect("insert");

        let fetched = fetch_agent_card_node(&pool, persona_id)
            .await
            .expect("fetch")
            .expect("card exists");

        assert_eq!(fetched.id.0, card_id);
        assert_eq!(fetched.name, "Aria Agent");
        assert_eq!(fetched.hardware_affinity, HardwareTarget::LocalMlx);
        assert_eq!(fetched.budget_cap, 100_000);
        assert_eq!(fetched.allowed_tools, vec![]);
    }

    #[tokio::test]
    async fn test_fetch_returns_none_for_unknown_persona() {
        let (_container, pool) = start_postgres().await;
        let result = fetch_agent_card_node(&pool, Uuid::new_v4())
            .await
            .expect("fetch");
        assert!(result.is_none());
    }

    #[tokio::test]
    async fn test_insert_creates_has_agent_card_edge() {
        let (_container, pool) = start_postgres().await;
        let (tenant_id, persona_id) = make_tenant_and_persona(&pool).await;
        let node = make_node(tenant_id, persona_id);
        let card_id = node.id.0;

        insert_agent_card(&pool, &node).await.expect("insert");

        let edges = siss_graph_db::repo::edge_repo::find_edges_from(
            &pool,
            persona_id,
            "has_agent_card",
            tenant_id,
        )
        .await
        .expect("find edges");

        assert_eq!(edges.len(), 1);
        assert_eq!(edges[0].2, card_id); // target_id
    }

    #[test]
    fn test_hardware_target_str_roundtrip() {
        for (variant, s) in [
            (HardwareTarget::LocalMlx, "local_mlx"),
            (HardwareTarget::RemoteFrontier, "remote_frontier"),
            (HardwareTarget::Hybrid, "hybrid"),
        ] {
            assert_eq!(hardware_target_str(variant), s);
            assert_eq!(parse_hardware_target(s), variant);
        }
    }
}
```

- [ ] **Step 2: Run tests — expect compile failure (testcontainers API not imported yet)**

```bash
cargo test -p siss-agent-card 2>&1 | tail -15
```

Expected: compile errors about `testcontainers`, `IntoContainerPort`, etc.

- [ ] **Step 3: Add `testcontainers` to `crates/siss-agent-card/Cargo.toml` dev-dependencies (already done in Task 2)**

Verify the `[dev-dependencies]` section in `crates/siss-agent-card/Cargo.toml` includes:
```toml
testcontainers  = { workspace = true }
tokio           = { workspace = true, features = ["full", "test-util"] }
```

If the testcontainers features for `GenericImage` require a specific feature flag, add to the workspace Cargo.toml:
```toml
testcontainers = { version = "0.23", features = ["blocking"] }
```

> Note: The async runner in testcontainers 0.23 is in the `testcontainers::runners` module — no additional feature flag is needed for the async API.

- [ ] **Step 4: Run tests — expect the 3 DB tests to be skipped (no Docker) or pass (if Docker is available), unit test passes**

```bash
cargo test -p siss-agent-card repo 2>&1 | tail -15
```

Expected: `test_hardware_target_str_roundtrip ... ok`. DB tests pass if Docker is running.

- [ ] **Step 5: Commit**

```bash
git add crates/siss-agent-card/src/repo.rs
git commit -m "feat(agent-card): implement repo — insert_agent_card and fetch_agent_card_node"
```

---

## Task 5: Serializer

**Files:**
- Modify: `crates/siss-agent-card/src/serializer.rs`

- [ ] **Step 1: Write failing tests**

Replace `crates/siss-agent-card/src/serializer.rs` with:

```rust
use serde_json::{json, Value};

use crate::types::{AgentCard, AgentCardNode, Authentication, Capability, SerializeOptions, Skill};

/// Serialize an `AgentCard` to a Google A2A-compatible JSON value.
///
/// Standard fields are always emitted. When `opts.extended` is true, an
/// `x-siss` block is added with SISS-native fields.
pub fn to_a2a_json(card: &AgentCard, opts: &SerializeOptions) -> Value {
    let skills: Vec<Value> = card.skills.iter().map(|s| {
        json!({
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "tags": s.tags,
        })
    }).collect();

    let mut obj = json!({
        "name": card.node.name,
        "description": card.node.description,
        "version": card.node.version,
        "url": card.node.url,
        "skills": skills,
        "capabilities": {
            "streaming": card.capabilities.streaming,
            "pushNotifications": card.capabilities.push_notifications,
        },
        "authentication": {
            "schemes": card.authentication.schemes,
        },
    });

    if opts.extended {
        let hw_str = match card.node.hardware_affinity {
            siss_graph_core::node::execution::HardwareTarget::LocalMlx => "local_mlx",
            siss_graph_core::node::execution::HardwareTarget::RemoteFrontier => "remote_frontier",
            siss_graph_core::node::execution::HardwareTarget::Hybrid => "hybrid",
        };
        obj["x-siss"] = json!({
            "persona_id": card.node.persona_id.0.to_string(),
            "tenant_id": card.node.tenant_id.0.to_string(),
            "hardware_affinity": hw_str,
            "budget_cap": card.node.budget_cap,
        });
    }

    obj
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;
    use siss_graph_core::node::NodeId;
    use siss_graph_core::node::execution::HardwareTarget;
    use uuid::Uuid;

    fn make_card() -> AgentCard {
        let node = AgentCardNode {
            id: NodeId(Uuid::nil()),
            persona_id: NodeId(Uuid::nil()),
            tenant_id: NodeId(Uuid::nil()),
            name: "Aria".into(),
            description: "Test agent".into(),
            version: "0.2.0".into(),
            url: "https://example.com/agent".into(),
            hardware_affinity: HardwareTarget::RemoteFrontier,
            budget_cap: 200_000,
            allowed_tools: vec![],
            created_at: Utc::now(),
        };
        AgentCard {
            node,
            skills: vec![
                Skill {
                    id: "mcp_filesystem".into(),
                    name: "MCP Filesystem".into(),
                    description: "Read and write files".into(),
                    tags: vec!["filesystem".into()],
                },
            ],
            capabilities: Capability { streaming: true, push_notifications: false },
            authentication: Authentication { schemes: vec!["Bearer".into()] },
        }
    }

    #[test]
    fn test_standard_fields_present() {
        let card = make_card();
        let json = to_a2a_json(&card, &SerializeOptions { extended: false });

        assert_eq!(json["name"], "Aria");
        assert_eq!(json["description"], "Test agent");
        assert_eq!(json["version"], "0.2.0");
        assert_eq!(json["url"], "https://example.com/agent");
    }

    #[test]
    fn test_capabilities_camel_case() {
        let card = make_card();
        let json = to_a2a_json(&card, &SerializeOptions { extended: false });

        assert_eq!(json["capabilities"]["streaming"], true);
        assert_eq!(json["capabilities"]["pushNotifications"], false);
        // pushNotifications must be camelCase, not snake_case
        assert!(json["capabilities"].get("push_notifications").is_none());
    }

    #[test]
    fn test_authentication_schemes() {
        let card = make_card();
        let json = to_a2a_json(&card, &SerializeOptions { extended: false });

        let schemes = &json["authentication"]["schemes"];
        assert_eq!(schemes[0], "Bearer");
    }

    #[test]
    fn test_skills_serialized() {
        let card = make_card();
        let json = to_a2a_json(&card, &SerializeOptions { extended: false });

        let skills = &json["skills"];
        assert_eq!(skills[0]["id"], "mcp_filesystem");
        assert_eq!(skills[0]["name"], "MCP Filesystem");
        assert_eq!(skills[0]["tags"][0], "filesystem");
    }

    #[test]
    fn test_x_siss_block_absent_when_not_extended() {
        let card = make_card();
        let json = to_a2a_json(&card, &SerializeOptions { extended: false });
        assert!(json.get("x-siss").is_none());
    }

    #[test]
    fn test_x_siss_block_present_when_extended() {
        let card = make_card();
        let json = to_a2a_json(&card, &SerializeOptions { extended: true });

        let x_siss = &json["x-siss"];
        assert_eq!(x_siss["persona_id"], "00000000-0000-0000-0000-000000000000");
        assert_eq!(x_siss["tenant_id"], "00000000-0000-0000-0000-000000000000");
        assert_eq!(x_siss["hardware_affinity"], "remote_frontier");
        assert_eq!(x_siss["budget_cap"], 200_000i64);
    }

    #[test]
    fn test_empty_skills_list() {
        let mut card = make_card();
        card.skills.clear();
        let json = to_a2a_json(&card, &SerializeOptions { extended: false });
        assert_eq!(json["skills"], json!([]));
    }
}
```

- [ ] **Step 2: Run tests — expect compile error (types not exported yet)**

```bash
cargo test -p siss-agent-card serializer 2>&1 | tail -15
```

Expected: compile errors because `AgentCard`, `Skill`, etc. are not re-exported from `lib.rs`.

- [ ] **Step 3: Update `lib.rs` to export types**

Replace `crates/siss-agent-card/src/lib.rs` with:

```rust
pub mod types;
pub mod repo;
pub mod serializer;
pub mod builder;

#[cfg(feature = "axum")]
pub mod handler;

pub use types::{
    AgentCard, AgentCardError, AgentCardNode,
    Authentication, Capability, SerializeOptions, Skill,
};
```

- [ ] **Step 4: Run serializer tests — expect all pass**

```bash
cargo test -p siss-agent-card serializer
```

Expected: 7 tests, all pass.

- [ ] **Step 5: Commit**

```bash
git add crates/siss-agent-card/src/serializer.rs crates/siss-agent-card/src/lib.rs
git commit -m "feat(agent-card): implement to_a2a_json serializer with x-siss extension"
```

---

## Task 6: Builder

**Files:**
- Modify: `crates/siss-agent-card/src/builder.rs`

The builder reads from the DB:
1. Fetch the Persona row — return `PersonaNotFound` if absent or frozen.
2. Fetch the `AgentCardNode` via `fetch_agent_card_node` — return `CardNotFound` if absent.
3. Fetch all `CAN_EXECUTE` edges from the persona to enumerate tools.
4. For each tool, fetch the tool row and build a `Skill`.
5. Assemble and return `AgentCard`.

- [ ] **Step 1: Write failing tests**

Replace `crates/siss-agent-card/src/builder.rs` with:

```rust
use sqlx::PgPool;
use uuid::Uuid;

use siss_graph_core::node::NodeId;

use crate::repo::{fetch_agent_card_node, insert_agent_card};
use crate::types::{AgentCard, AgentCardError, Authentication, Capability, Skill};

pub struct AgentCardBuilder<'a> {
    pool: &'a PgPool,
}

impl<'a> AgentCardBuilder<'a> {
    pub fn new(pool: &'a PgPool) -> Self {
        Self { pool }
    }

    /// Build a complete `AgentCard` from the Knowledge Graph.
    ///
    /// 1. Validates the persona exists and is not frozen.
    /// 2. Fetches the AgentCardNode (must be pre-inserted via `insert_agent_card`).
    /// 3. Enumerates tools via `can_execute` edges → builds skills.
    pub async fn build(
        &self,
        persona_id: NodeId,
        tenant_id: NodeId,
        _base_url: &str,
    ) -> Result<AgentCard, AgentCardError> {
        // 1. Validate persona
        let persona_row = siss_graph_db::repo::node_repo::fetch_persona(self.pool, persona_id.0)
            .await?
            .ok_or(AgentCardError::PersonaNotFound { persona_id: persona_id.0 })?;

        let (_id, _tenant, _name, _kind, is_frozen) = persona_row;
        if is_frozen {
            return Err(AgentCardError::PersonaNotFound { persona_id: persona_id.0 });
        }

        // 2. Fetch AgentCardNode
        let mut node = fetch_agent_card_node(self.pool, persona_id.0)
            .await?
            .ok_or(AgentCardError::CardNotFound { persona_id: persona_id.0 })?;

        // 3. Enumerate tools from CAN_EXECUTE edges (persona → tool)
        let edges = siss_graph_db::repo::edge_repo::find_edges_from(
            self.pool,
            persona_id.0,
            "can_execute",
            tenant_id.0,
        )
        .await?;

        let tool_ids: Vec<Uuid> = edges.iter().map(|(_, _, target)| *target).collect();
        node.allowed_tools = tool_ids.iter().map(|&u| NodeId(u)).collect();

        // 4. Build skills from tool rows
        let mut skills = Vec::new();
        for tool_id in &tool_ids {
            // Fetch tool name via a direct query (tool rows live in the `tools` table)
            let row: Option<(String, String)> = sqlx::query_as(
                "SELECT name, tool_uri FROM tools WHERE id = $1"
            )
            .bind(tool_id)
            .fetch_optional(self.pool)
            .await?;

            if let Some((name, uri)) = row {
                let id = name.to_lowercase().replace(['-', ' '], "_");
                skills.push(Skill {
                    id,
                    name: name.clone(),
                    description: uri,
                    tags: vec![],
                });
            }
        }

        Ok(AgentCard {
            node,
            skills,
            capabilities: Capability { streaming: true, push_notifications: false },
            authentication: Authentication { schemes: vec!["Bearer".into()] },
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;
    use testcontainers::{
        core::{IntoContainerPort, WaitFor},
        runners::AsyncRunner,
        GenericImage, ImageExt,
    };

    use crate::types::AgentCardNode;
    use siss_graph_core::node::execution::HardwareTarget;

    async fn start_postgres() -> (testcontainers::ContainerAsync<GenericImage>, PgPool) {
        let container = GenericImage::new("postgres", "16")
            .with_wait_for(WaitFor::message_on_stderr(
                "database system is ready to accept connections",
            ))
            .with_env_var("POSTGRES_PASSWORD", "postgres")
            .with_env_var("POSTGRES_DB", "siss_test")
            .with_exposed_port(5432.tcp())
            .start()
            .await
            .expect("postgres started");

        let port = container.get_host_port_ipv4(5432).await.unwrap();
        let url = format!("postgres://postgres:postgres@127.0.0.1:{port}/siss_test");
        let pool = PgPool::connect(&url).await.expect("pool connect");
        siss_graph_db::migrations::run_all(&pool).await.expect("migrations");
        (container, pool)
    }

    async fn make_tenant_and_persona(pool: &PgPool) -> (Uuid, Uuid) {
        let tenant_id = siss_graph_db::repo::node_repo::insert_tenant(pool, "BuilderCorp")
            .await
            .expect("insert tenant");
        let persona_id = siss_graph_db::repo::node_repo::insert_persona(
            pool, "Aria", "ai_agent", tenant_id,
        )
        .await
        .expect("insert persona");
        (tenant_id, persona_id)
    }

    fn make_card_node(tenant_id: Uuid, persona_id: Uuid) -> AgentCardNode {
        AgentCardNode {
            id: NodeId::new(),
            tenant_id: NodeId(tenant_id),
            persona_id: NodeId(persona_id),
            name: "Aria".into(),
            description: "A sovereign agent".into(),
            version: "0.1.0".into(),
            url: "https://example.com/agent".into(),
            hardware_affinity: HardwareTarget::LocalMlx,
            budget_cap: 100_000,
            allowed_tools: vec![],
            created_at: Utc::now(),
        }
    }

    #[tokio::test]
    async fn test_build_returns_card_with_no_tools() {
        let (_container, pool) = start_postgres().await;
        let (tenant_id, persona_id) = make_tenant_and_persona(&pool).await;
        let node = make_card_node(tenant_id, persona_id);
        insert_agent_card(&pool, &node).await.expect("insert card");

        let builder = AgentCardBuilder::new(&pool);
        let card = builder
            .build(NodeId(persona_id), NodeId(tenant_id), "https://example.com")
            .await
            .expect("build");

        assert_eq!(card.node.name, "Aria");
        assert!(card.skills.is_empty());
        assert!(card.capabilities.streaming);
        assert!(!card.capabilities.push_notifications);
        assert_eq!(card.authentication.schemes, vec!["Bearer"]);
    }

    #[tokio::test]
    async fn test_build_returns_persona_not_found() {
        let (_container, pool) = start_postgres().await;
        let builder = AgentCardBuilder::new(&pool);
        let err = builder
            .build(NodeId(Uuid::new_v4()), NodeId(Uuid::new_v4()), "https://example.com")
            .await
            .unwrap_err();
        assert!(matches!(err, AgentCardError::PersonaNotFound { .. }));
    }

    #[tokio::test]
    async fn test_build_returns_card_not_found_when_no_card_inserted() {
        let (_container, pool) = start_postgres().await;
        let (tenant_id, persona_id) = make_tenant_and_persona(&pool).await;
        let builder = AgentCardBuilder::new(&pool);
        let err = builder
            .build(NodeId(persona_id), NodeId(tenant_id), "https://example.com")
            .await
            .unwrap_err();
        assert!(matches!(err, AgentCardError::CardNotFound { .. }));
    }

    #[tokio::test]
    async fn test_build_populates_skills_from_can_execute_edges() {
        let (_container, pool) = start_postgres().await;
        let (tenant_id, persona_id) = make_tenant_and_persona(&pool).await;

        // Insert a tool and a CAN_EXECUTE edge from persona to tool
        let tool_id = siss_graph_db::repo::node_repo::insert_tool(
            &pool, "mcp-filesystem", "mcp://localhost:3000/fs", "medium", tenant_id,
        )
        .await
        .expect("insert tool");

        siss_graph_db::repo::edge_repo::insert_edge(
            &pool,
            persona_id,
            tool_id,
            "can_execute",
            tenant_id,
            serde_json::Value::Null,
        )
        .await
        .expect("insert edge");

        let node = make_card_node(tenant_id, persona_id);
        insert_agent_card(&pool, &node).await.expect("insert card");

        let builder = AgentCardBuilder::new(&pool);
        let card = builder
            .build(NodeId(persona_id), NodeId(tenant_id), "https://example.com")
            .await
            .expect("build");

        assert_eq!(card.skills.len(), 1);
        assert_eq!(card.skills[0].id, "mcp_filesystem");
        assert_eq!(card.skills[0].name, "mcp-filesystem");
        assert_eq!(card.node.allowed_tools.len(), 1);
        assert_eq!(card.node.allowed_tools[0].0, tool_id);
    }
}
```

- [ ] **Step 2: Run tests — expect compile errors (builder imports types)**

```bash
cargo test -p siss-agent-card builder 2>&1 | tail -15
```

Expected: compile errors if any imports are missing. Fix any issues.

- [ ] **Step 3: Run tests — expect pass (requires Docker)**

```bash
cargo test -p siss-agent-card builder
```

Expected: 4 tests pass.

- [ ] **Step 4: Commit**

```bash
git add crates/siss-agent-card/src/builder.rs
git commit -m "feat(agent-card): implement AgentCardBuilder"
```

---

## Task 7: Axum Handler

**Files:**
- Modify: `crates/siss-agent-card/src/handler.rs`

The handler is only compiled with `--features axum`. It uses `axum::extract::State` and `axum::response::IntoResponse`.

- [ ] **Step 1: Write failing tests**

Replace `crates/siss-agent-card/src/handler.rs` with:

```rust
use axum::{
    extract::State,
    http::StatusCode,
    response::{IntoResponse, Json},
};
use sqlx::PgPool;

use siss_graph_core::node::NodeId;

use crate::builder::AgentCardBuilder;
use crate::serializer::to_a2a_json;
use crate::types::{AgentCardError, SerializeOptions};

/// Axum state for the `/.well-known/agent.json` endpoint.
#[derive(Clone)]
pub struct AgentCardState {
    pub pool: PgPool,
    pub persona_id: NodeId,
    pub tenant_id: NodeId,
    pub base_url: String,
    pub extended: bool,
}

/// GET `/.well-known/agent.json`
///
/// Returns the Google A2A Agent Card JSON for the configured persona.
/// 200 on success, 404 when persona or card is not found, 500 on DB error.
pub async fn well_known_agent_handler(
    State(state): State<AgentCardState>,
) -> impl IntoResponse {
    let builder = AgentCardBuilder::new(&state.pool);
    match builder.build(state.persona_id, state.tenant_id, &state.base_url).await {
        Ok(card) => {
            let opts = SerializeOptions { extended: state.extended };
            let json = to_a2a_json(&card, &opts);
            (StatusCode::OK, Json(json)).into_response()
        }
        Err(AgentCardError::PersonaNotFound { persona_id }) => (
            StatusCode::NOT_FOUND,
            Json(serde_json::json!({ "error": format!("persona not found: {persona_id}") })),
        )
            .into_response(),
        Err(AgentCardError::CardNotFound { persona_id }) => (
            StatusCode::NOT_FOUND,
            Json(serde_json::json!({ "error": format!("agent card not found for persona: {persona_id}") })),
        )
            .into_response(),
        Err(AgentCardError::DatabaseError { message }) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(serde_json::json!({ "error": message })),
        )
            .into_response(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::{body::Body, routing::get, Router};
    use chrono::Utc;
    use http::{Request, StatusCode};
    use tower::ServiceExt; // for .oneshot()
    use testcontainers::{
        core::{IntoContainerPort, WaitFor},
        runners::AsyncRunner,
        GenericImage, ImageExt,
    };
    use uuid::Uuid;

    use crate::repo::insert_agent_card;
    use crate::types::AgentCardNode;
    use siss_graph_core::node::execution::HardwareTarget;

    async fn start_postgres() -> (testcontainers::ContainerAsync<GenericImage>, PgPool) {
        let container = GenericImage::new("postgres", "16")
            .with_wait_for(WaitFor::message_on_stderr(
                "database system is ready to accept connections",
            ))
            .with_env_var("POSTGRES_PASSWORD", "postgres")
            .with_env_var("POSTGRES_DB", "siss_test")
            .with_exposed_port(5432.tcp())
            .start()
            .await
            .expect("postgres started");

        let port = container.get_host_port_ipv4(5432).await.unwrap();
        let url = format!("postgres://postgres:postgres@127.0.0.1:{port}/siss_test");
        let pool = PgPool::connect(&url).await.expect("pool connect");
        siss_graph_db::migrations::run_all(&pool).await.expect("migrations");
        (container, pool)
    }

    fn make_router(state: AgentCardState) -> Router {
        Router::new()
            .route("/.well-known/agent.json", get(well_known_agent_handler))
            .with_state(state)
    }

    async fn body_json(body: Body) -> serde_json::Value {
        use http_body_util::BodyExt;
        let bytes = body.collect().await.unwrap().to_bytes();
        serde_json::from_slice(&bytes).unwrap()
    }

    #[tokio::test]
    async fn test_handler_returns_200_for_valid_persona() {
        let (_container, pool) = start_postgres().await;

        let tenant_id = siss_graph_db::repo::node_repo::insert_tenant(&pool, "HandlerCorp")
            .await.unwrap();
        let persona_id = siss_graph_db::repo::node_repo::insert_persona(
            &pool, "HandlerAgent", "ai_agent", tenant_id,
        ).await.unwrap();

        let node = AgentCardNode {
            id: NodeId::new(),
            tenant_id: NodeId(tenant_id),
            persona_id: NodeId(persona_id),
            name: "HandlerAgent".into(),
            description: "test".into(),
            version: "0.1.0".into(),
            url: "https://example.com/handler".into(),
            hardware_affinity: HardwareTarget::LocalMlx,
            budget_cap: 50_000,
            allowed_tools: vec![],
            created_at: Utc::now(),
        };
        insert_agent_card(&pool, &node).await.unwrap();

        let state = AgentCardState {
            pool,
            persona_id: NodeId(persona_id),
            tenant_id: NodeId(tenant_id),
            base_url: "https://example.com".into(),
            extended: false,
        };
        let app = make_router(state);

        let response = app
            .oneshot(
                Request::builder()
                    .uri("/.well-known/agent.json")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_eq!(response.status(), StatusCode::OK);
        let json = body_json(response.into_body()).await;
        assert_eq!(json["name"], "HandlerAgent");
        assert!(json.get("x-siss").is_none());
    }

    #[tokio::test]
    async fn test_handler_returns_200_with_x_siss_when_extended() {
        let (_container, pool) = start_postgres().await;

        let tenant_id = siss_graph_db::repo::node_repo::insert_tenant(&pool, "ExtendedCorp")
            .await.unwrap();
        let persona_id = siss_graph_db::repo::node_repo::insert_persona(
            &pool, "ExtendedAgent", "ai_agent", tenant_id,
        ).await.unwrap();

        let node = AgentCardNode {
            id: NodeId::new(),
            tenant_id: NodeId(tenant_id),
            persona_id: NodeId(persona_id),
            name: "ExtendedAgent".into(),
            description: "ext test".into(),
            version: "0.1.0".into(),
            url: "https://example.com/ext".into(),
            hardware_affinity: HardwareTarget::Hybrid,
            budget_cap: 99_000,
            allowed_tools: vec![],
            created_at: Utc::now(),
        };
        insert_agent_card(&pool, &node).await.unwrap();

        let state = AgentCardState {
            pool,
            persona_id: NodeId(persona_id),
            tenant_id: NodeId(tenant_id),
            base_url: "https://example.com".into(),
            extended: true,
        };
        let app = make_router(state);

        let response = app
            .oneshot(
                Request::builder()
                    .uri("/.well-known/agent.json")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_eq!(response.status(), StatusCode::OK);
        let json = body_json(response.into_body()).await;
        assert!(json.get("x-siss").is_some());
        assert_eq!(json["x-siss"]["hardware_affinity"], "hybrid");
        assert_eq!(json["x-siss"]["budget_cap"], 99_000i64);
    }

    #[tokio::test]
    async fn test_handler_returns_404_for_unknown_persona() {
        let (_container, pool) = start_postgres().await;

        let state = AgentCardState {
            pool,
            persona_id: NodeId(Uuid::new_v4()),
            tenant_id: NodeId(Uuid::new_v4()),
            base_url: "https://example.com".into(),
            extended: false,
        };
        let app = make_router(state);

        let response = app
            .oneshot(
                Request::builder()
                    .uri("/.well-known/agent.json")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_eq!(response.status(), StatusCode::NOT_FOUND);
    }

    #[tokio::test]
    async fn test_handler_response_content_type_is_json() {
        let (_container, pool) = start_postgres().await;

        let tenant_id = siss_graph_db::repo::node_repo::insert_tenant(&pool, "ContentCorp")
            .await.unwrap();
        let persona_id = siss_graph_db::repo::node_repo::insert_persona(
            &pool, "ContentAgent", "ai_agent", tenant_id,
        ).await.unwrap();

        let node = AgentCardNode {
            id: NodeId::new(),
            tenant_id: NodeId(tenant_id),
            persona_id: NodeId(persona_id),
            name: "ContentAgent".into(),
            description: "content type test".into(),
            version: "0.1.0".into(),
            url: "https://example.com/content".into(),
            hardware_affinity: HardwareTarget::LocalMlx,
            budget_cap: 10_000,
            allowed_tools: vec![],
            created_at: Utc::now(),
        };
        insert_agent_card(&pool, &node).await.unwrap();

        let state = AgentCardState {
            pool,
            persona_id: NodeId(persona_id),
            tenant_id: NodeId(tenant_id),
            base_url: "https://example.com".into(),
            extended: false,
        };
        let app = make_router(state);

        let response = app
            .oneshot(
                Request::builder()
                    .uri("/.well-known/agent.json")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();

        let content_type = response.headers()
            .get("content-type")
            .and_then(|v| v.to_str().ok())
            .unwrap_or("");
        assert!(content_type.contains("application/json"), "got: {content_type}");
    }
}
```

- [ ] **Step 2: Run tests (axum feature) — expect compile errors**

```bash
cargo test -p siss-agent-card --features axum handler 2>&1 | tail -15
```

Expected: compile errors because `handler.rs` now has real content.

- [ ] **Step 3: Fix any import issues and run again**

```bash
cargo test -p siss-agent-card --features axum handler
```

Expected: 4 tests pass (requires Docker).

- [ ] **Step 4: Run all tests together**

```bash
cargo test -p siss-agent-card --features axum
```

Expected: all tests pass.

- [ ] **Step 5: Run clippy on the whole workspace**

```bash
cargo clippy --workspace --features axum -- -D warnings 2>&1 | tail -20
```

Expected: no warnings.

- [ ] **Step 6: Commit**

```bash
git add crates/siss-agent-card/src/handler.rs
git commit -m "feat(agent-card): implement well_known_agent_handler (axum feature)"
```

---

## Task 8: Final verification

- [ ] **Step 1: Run all workspace tests**

```bash
cargo test --workspace
```

Expected: all tests pass. Count should be ≥ 153 (existing) + new tests from this crate.

- [ ] **Step 2: Run workspace clippy**

```bash
cargo clippy --workspace -- -D warnings
```

Expected: 0 warnings.

- [ ] **Step 3: Final commit**

```bash
git add -u
git commit -m "feat: Phase 3 complete — siss-agent-card A2A discovery layer"
```
