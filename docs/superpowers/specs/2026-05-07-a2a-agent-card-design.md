# Phase 3 — A2A Agent Cards Design

**Date:** 2026-05-07
**Status:** Approved
**Crate:** `siss-agent-card`
**Depends on:** `siss-graph-core`, `siss-graph-db`

---

## Overview

Phase 3 introduces the `siss-agent-card` crate — the discovery layer of the SISS Three-Plane Architecture. It implements Google's A2A Agent Card standard, allowing SISS personas to be discovered by external agents via the `/.well-known/agent.json` endpoint, while preserving sovereign identity in the SISS Knowledge Graph.

Design choice: **Hybrid** — the authoritative Agent Card lives in the SISS Knowledge Graph as a typed node, and is serialized into a Google A2A-compatible JSON document on demand. The standard A2A fields are emitted by default; a `x-siss.*` extension block is available via `SerializeOptions { extended: true }`.

---

## Section 1: Crate Structure & Dependencies

```
crates/siss-agent-card/
  Cargo.toml
  src/
    lib.rs          # pub re-exports
    types.rs        # AgentCard, AgentCardNode, Skill, Capability, Authentication, SerializeOptions, AgentCardError
    builder.rs      # AgentCardBuilder — constructs AgentCard from graph data
    serializer.rs   # to_a2a_json(card, opts) — Google A2A JSON output
    repo.rs         # insert_agent_card_node / fetch_agent_card_node
    handler.rs      # (axum feature only) well_known_agent_handler + AgentCardState
```

### `Cargo.toml` features

```toml
[features]
default = []
axum = ["dep:axum"]

[dependencies]
siss-graph-core = { path = "../siss-graph-core" }
siss-graph-db   = { path = "../siss-graph-db" }
serde           = { version = "1", features = ["derive"] }
serde_json      = "1"
sqlx            = { version = "0.8", features = ["postgres", "uuid", "runtime-tokio-rustls"] }
uuid            = { version = "1", features = ["v4"] }
chrono          = { version = "0.4", features = ["serde"] }
thiserror       = "1"
axum            = { version = "0.7", optional = true }
```

### Workspace membership

Add to root `Cargo.toml`:
```toml
[workspace]
members = [
    # ... existing members ...
    "crates/siss-agent-card",
]
```

### `siss-graph-core` addition

Add `AgentCard` variant to `NodeKind` enum:
```rust
// crates/siss-graph-core/src/node.rs
pub enum NodeKind {
    // ... existing variants ...
    AgentCard,
}
```

---

## Section 2: AgentCardNode Schema & Rust Types

### `AgentCardNode` — the graph node

```rust
pub struct AgentCardNode {
    pub id: NodeId,
    pub persona_id: NodeId,
    pub tenant_id: NodeId,
    pub name: String,
    pub description: String,
    pub version: String,
    pub url: String,                    // base URL for the agent's endpoint
    pub hardware_affinity: HardwareTarget,
    pub budget_cap: i64,                // max tokens per session
    pub allowed_tools: Vec<NodeId>,     // tool node IDs from CAN_EXECUTE edges
    pub created_at: DateTime<Utc>,
}
```

Stored as a `nodes` row with `kind = 'agent_card'` plus a JSONB `metadata` column holding all fields. A `HAS_AGENT_CARD` edge connects the Persona node to the AgentCard node.

### `AgentCard` — the in-memory working type

```rust
pub struct AgentCard {
    pub node: AgentCardNode,
    pub skills: Vec<Skill>,
    pub capabilities: Capability,
    pub authentication: Authentication,
}
```

### Supporting types

```rust
pub struct Skill {
    pub id: String,           // snake_case identifier, e.g. "text_generation"
    pub name: String,
    pub description: String,
    pub tags: Vec<String>,
}

pub struct Capability {
    pub streaming: bool,            // true if agent emits AG-UI events
    pub push_notifications: bool,   // false for Phase 3
}

pub struct Authentication {
    pub schemes: Vec<String>,  // e.g. ["Bearer"], ["None"]
}

pub struct SerializeOptions {
    pub extended: bool,  // if true, include x-siss.* block in JSON output
}
```

### `AgentCardError`

```rust
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
```

---

## Section 3: Builder, Serializer, and HTTP Handler

### `AgentCardBuilder` — `builder.rs`

Constructs an `AgentCard` from the Knowledge Graph. No live session required; reads Persona node + `CAN_EXECUTE` edges to enumerate allowed tools (as skills).

```rust
pub struct AgentCardBuilder<'a> {
    pool: &'a PgPool,
}

impl<'a> AgentCardBuilder<'a> {
    pub fn new(pool: &'a PgPool) -> Self { Self { pool } }

    pub async fn build(
        &self,
        persona_id: NodeId,
        tenant_id: NodeId,
        base_url: &str,
    ) -> Result<AgentCard, AgentCardError>;
}
```

Build steps:
1. Fetch the Persona node; return `PersonaNotFound` if missing or frozen.
2. Fetch the existing `AgentCardNode` via `HAS_AGENT_CARD` edge; return `CardNotFound` if absent.
3. Fetch all `CAN_EXECUTE` edges from the persona to enumerate `allowed_tools`.
4. Map each tool node into a `Skill` (id = tool name snake_cased, tags = tool kind).
5. Set `Capability { streaming: true, push_notifications: false }`.
6. Set `Authentication { schemes: ["Bearer"] }` (configurable in Phase 4).
7. Return the assembled `AgentCard`.

### `to_a2a_json` — `serializer.rs`

Serializes an `AgentCard` into a Google A2A-compatible `serde_json::Value`.

```rust
pub fn to_a2a_json(card: &AgentCard, opts: &SerializeOptions) -> serde_json::Value;
```

Standard output shape (always emitted):
```json
{
  "name": "...",
  "description": "...",
  "version": "...",
  "url": "...",
  "skills": [{ "id": "...", "name": "...", "description": "...", "tags": [] }],
  "capabilities": { "streaming": true, "pushNotifications": false },
  "authentication": { "schemes": ["Bearer"] }
}
```

Extended output (when `opts.extended == true`), adds:
```json
{
  "x-siss": {
    "persona_id": "<uuid>",
    "tenant_id": "<uuid>",
    "hardware_affinity": "local_mlx",
    "budget_cap": 100000
  }
}
```

Field names follow Google A2A camelCase convention for standard fields; `x-siss.*` fields use snake_case to match SISS conventions.

### `repo.rs`

```rust
pub async fn insert_agent_card_node(
    pool: &PgPool,
    node: &AgentCardNode,
) -> Result<Uuid, AgentCardError>;

pub async fn fetch_agent_card_node(
    pool: &PgPool,
    persona_id: Uuid,
) -> Result<Option<AgentCardNode>, AgentCardError>;
```

`insert_agent_card_node` writes a `nodes` row (`kind = 'agent_card'`, metadata as JSONB) and a `HAS_AGENT_CARD` edge from persona to the new node, in a single transaction.

### HTTP Handler — `handler.rs` (axum feature only)

```rust
#[derive(Clone)]
pub struct AgentCardState {
    pub pool: PgPool,
    pub persona_id: NodeId,
    pub tenant_id: NodeId,
    pub base_url: String,
    pub extended: bool,
}

pub async fn well_known_agent_handler(
    State(state): State<AgentCardState>,
) -> impl IntoResponse;
```

Handler steps:
1. Call `AgentCardBuilder::new(&state.pool).build(...)`.
2. On `PersonaNotFound` or `CardNotFound`: return HTTP 404 with JSON error body.
3. On `DatabaseError`: return HTTP 500 with JSON error body.
4. On success: serialize with `to_a2a_json(&card, &SerializeOptions { extended: state.extended })`.
5. Return `(StatusCode::OK, Json(json_value))`.

Callers mount it in Axum:
```rust
let app = Router::new()
    .route("/.well-known/agent.json", get(well_known_agent_handler))
    .with_state(agent_card_state);
```

---

## Section 4: Testing Strategy

### Unit tests (no database)

**`serializer.rs`** — test `to_a2a_json`:
- Standard fields present and correctly named (camelCase).
- `x-siss` block absent when `extended: false`.
- `x-siss` block present with correct values when `extended: true`.
- Skills round-trip through serialization.

**`types.rs`** — test `AgentCardError` messages match expected strings.

### Integration tests (live PgPool via `sqlx::test`)

**`repo.rs`**:
- `insert_agent_card_node` creates a `nodes` row with `kind = 'agent_card'` and a `HAS_AGENT_CARD` edge.
- `fetch_agent_card_node` returns the correct node after insert.
- `fetch_agent_card_node` returns `None` for an unknown persona.

**`builder.rs`**:
- `build` returns `PersonaNotFound` for a non-existent persona UUID.
- `build` returns `CardNotFound` when persona exists but no agent card node is linked.
- `build` returns a correct `AgentCard` with skills matching the persona's `CAN_EXECUTE` edges.

### Handler tests (axum feature, `axum::test`)

- `GET /.well-known/agent.json` returns 200 and valid A2A JSON when card exists.
- Returns 404 with JSON error body when persona is not found.
- Returns 200 with `x-siss` block when `extended: true`.
- Response `Content-Type` is `application/json`.

---

## Data Flow

```
AoE (Axum)
    │ GET /.well-known/agent.json
    ▼
well_known_agent_handler(State<AgentCardState>)
    │
    ▼
AgentCardBuilder::build(persona_id, tenant_id, base_url)
    │ reads
    ▼
siss-graph-db (Persona node + HAS_AGENT_CARD edge + CAN_EXECUTE edges)
    │
    ▼
AgentCard (in-memory)
    │
    ▼
to_a2a_json(&card, &SerializeOptions)
    │
    ▼
serde_json::Value  →  HTTP 200 application/json
```

---

## Out of Scope (Phase 3)

- A2A handshake / authentication negotiation (Phase 4)
- Agent delegation / task forwarding (Phase 5 / MeshFlow)
- Dynamic card mutation at runtime
- Card versioning or diffing
- Push notification support (`push_notifications` is always `false`)
