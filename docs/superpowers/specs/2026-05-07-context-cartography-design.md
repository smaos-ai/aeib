# Context Cartography Design — Step D

**Date:** 2026-05-07
**Status:** Approved
**Scope:** Step D — Visible Field assembly for the SISS value loop
**Depends on:** Step A (Knowledge Graph Schema), Step B (Governance Gatekeeper), Step C (Job Router)

---

## 1. Overview

Context Cartography is the "Orient & Preload" step of the SISS value loop. It assembles the **Visible Field** — a curated, token-budgeted context window containing the exact memories a Persona needs to execute a task. It creates and owns the Session node, retrieves memories by tier, filters them through ReBAC, enforces a token budget, and records what was loaded for auditability.

Context Cartography is called by the Job Router between the `route` and `execute` pipeline steps. The enriched context is passed to the Executor.

### Position in the Value Loop

```
1. [Sense & Authorize] ← Governance Gatekeeper (Step B) ✅
2. [Orient & Preload]  ← CONTEXT CARTOGRAPHY (this component)
3. [Decide & Execute]  ← Job Router (Step C) ✅
4. [Act & Guard]       ← Behavioral Firewall (Step E)
5. [Learn & Crystallize] ← Feedback Router (Step F)
```

---

## 2. Architecture

A new Rust library crate `siss-context-cartography` that depends on `siss-graph-core` and `siss-graph-db`. It exposes a single async entry point `build_context` and is called from within the Job Router's pipeline.

### Crate Dependencies

```
siss-context-cartography
  ├── siss-graph-core   (node types: Session, Memory tiers, ConsolidationTier)
  └── siss-graph-db     (PostgreSQL repositories for memory retrieval, session creation)
```

### Key Design Principles

1. **Session owner** — Cartography creates the Session node, links it to Persona and Task, and records all LOADED edges
2. **Tier-based retrieval** — deterministic, no ML dependencies: Procedural → Semantic → Episodic
3. **Token-budgeted** — memories are trimmed to fit the budget, prioritized by tier importance
4. **ReBAC-filtered** — a Persona only sees memories it has CAN_READ access to
5. **Cold-start safe** — empty Visible Field is valid, not an error

---

## 3. Request/Response Types

### CartographyRequest

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | `NodeId` | The Task being contextualized |
| `persona_id` | `NodeId` | The Persona executing the task |
| `tenant_id` | `NodeId` | Tenant isolation boundary |
| `token_budget` | `i64` | Maximum estimated tokens for the context window |

### VisibleField

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | `NodeId` | The created Session node |
| `procedural` | `Vec<MemoryEntry>` | Loaded procedural memories (workflows, how-to's) |
| `semantic` | `Vec<MemoryEntry>` | Loaded semantic memories (domain knowledge) |
| `episodic` | `Vec<MemoryEntry>` | Loaded episodic memories (recent events) |
| `total_tokens_estimated` | `i64` | Estimated total token usage of the loaded field |

### MemoryEntry

| Field | Type | Description |
|-------|------|-------------|
| `memory_id` | `Uuid` | Memory node ID |
| `content` | `String` | The memory content |
| `confidence_score` | `f64` | Current confidence (after decay) |
| `tier` | `ConsolidationTier` | Which memory tier this belongs to |

### CartographyError

| Variant | Description |
|---------|-------------|
| `TaskNotFound` | Task ID does not exist |
| `PersonaNotFound` | Persona ID does not exist |
| `TenantViolation` | Cross-tenant operation attempted |
| `NoMemoriesAvailable` | Advisory — Persona has no accessible memories (cold start). Not fatal. |
| `DatabaseError` | Database operation failed |

---

## 4. Retrieval Strategy

### Tier-Based Retrieval

Memories are loaded in tier order with configurable caps:

| Tier | Query | Sort Order | Default Cap |
|------|-------|-----------|-------------|
| Procedural | All procedural memories for this Persona's tenant | By confidence descending | 20 |
| Semantic | All semantic memories for this Persona's tenant | By confidence descending | 30 |
| Episodic | All episodic memories for this Persona's tenant | By created_at descending (most recent first) | 10 |

All queries are:
- Scoped to the Persona's `tenant_id`
- Filtered by ReBAC: only memories where the Persona has a `CAN_READ` edge (direct or via Team)
- Filtered by confidence: only memories above the GC threshold (0.1) are returned

Working Memory is excluded — it's session-scoped and belongs to the current session, not preloaded from previous ones.

### Retrieval Configuration

```rust
pub struct RetrievalConfig {
    pub max_procedural: usize,    // Default: 20
    pub max_semantic: usize,      // Default: 30
    pub max_episodic: usize,      // Default: 10
    pub tokens_per_char: f64,     // Default: 0.25 (4 chars ≈ 1 token)
}
```

---

## 5. Token Budget Enforcement

The Visible Field must fit within the Session's `token_budget`. Token count is estimated using a character-based heuristic: `tokens ≈ content.len() * tokens_per_char`.

**Algorithm:**

```
available = token_budget

1. Load procedural memories (up to max_procedural)
   estimate_tokens = sum of (content.len() * tokens_per_char) for each
   if estimate_tokens > available:
       trim from the bottom (lowest confidence) until fits
   available -= procedural_tokens

2. Load semantic memories (up to max_semantic, by confidence desc)
   estimate_tokens for each
   if cumulative > available:
       trim from the bottom until fits
   available -= semantic_tokens

3. Load episodic memories (up to max_episodic, by recency desc)
   estimate_tokens for each
   if cumulative > available:
       trim from the bottom until fits
```

**Priority:** Procedural > Semantic > Episodic. Procedural memories are never trimmed in favor of other tiers. If Procedural memories alone exceed the budget, they are trimmed by confidence (lowest removed first).

---

## 6. Pipeline Integration

### Build Context Pipeline

```
Step 1: VALIDATE
  - Verify Task exists and is in a valid state (authorized or routing)
  - Verify Persona exists and belongs to the correct tenant
  - Verify tenant isolation

Step 2: CREATE SESSION
  - Insert Session node (token_budget, active_persona_id, status=active)
  - Create SCOPED_TO edge (Session → Persona)
  - Create CONTAINS edge (Session → Task)

Step 3: RETRIEVE MEMORIES
  - Query procedural memories (tenant-scoped, ReBAC-filtered, confidence > 0.1)
  - Query semantic memories (same filters, sorted by confidence)
  - Query episodic memories (same filters, sorted by recency)

Step 4: APPLY TOKEN BUDGET
  - Estimate tokens for each tier
  - Trim by priority until total fits within budget
  - Build MemoryEntry list for each tier

Step 5: RECORD AND RETURN
  - Create LOADED edge (Session → Memory) for each loaded memory
  - Serialize the VisibleField into Session.visible_field_snapshot (JSON)
  - Update Session in DB
  - Return VisibleField
```

### Router Integration

The Job Router's pipeline changes from:

```
validate → route → execute
```

to:

```
validate → route → build_context → execute
```

The `TaskContext` struct in `siss-job-router` gains a new field:

```rust
pub visible_field: Option<VisibleField>,
```

The Executor receives the full context. `Option` because if Cartography fails with `NoMemoriesAvailable`, execution proceeds with an empty context.

---

## 7. DB Functions Needed

### New Memory Retrieval Queries

| Function | Description |
|----------|-------------|
| `fetch_memories_by_tier(pool, tier, tenant_id, limit)` | Fetch memories of a given tier, ordered appropriately, with limit |
| `fetch_accessible_memory_ids(pool, persona_id, tenant_id)` | Get all memory IDs this Persona can read (via ReBAC CAN_READ edges) |
| `insert_session(pool, token_budget, persona_id, tenant_id)` | Create a new Session node |
| `update_session_snapshot(pool, session_id, snapshot)` | Update visible_field_snapshot JSON |

### Existing Functions Used

- `edge_repo::insert_edge` — for SCOPED_TO, CONTAINS, LOADED edges
- `node_repo::fetch_task` — validate task exists
- `node_repo::fetch_persona` — validate persona exists

---

## 8. File Structure

```
crates/
  siss-context-cartography/
    Cargo.toml
    src/
      lib.rs              # Re-exports
      types.rs            # CartographyRequest, VisibleField, MemoryEntry, CartographyError
      config.rs           # RetrievalConfig with defaults
      retrieval/
        mod.rs            # Memory retrieval orchestrator
        procedural.rs     # Procedural tier query + ReBAC filter
        semantic.rs       # Semantic tier query + ReBAC filter
        episodic.rs       # Episodic tier query + ReBAC filter
      budget.rs           # Token budget enforcement / trimming
      pipeline/
        mod.rs            # build_context() orchestrator
        validate.rs       # Step 1: validation
        session.rs        # Step 2: create session + edges
        record.rs         # Step 5: LOADED edges + snapshot
  siss-job-router/
    src/
      executor/mod.rs     # MODIFY: add visible_field to TaskContext
      pipeline/mod.rs     # MODIFY: call build_context between route and execute
```

---

## 9. Success Criteria

Context Cartography is correct when:

1. A valid CartographyRequest creates a Session node linked to the Persona (SCOPED_TO) and Task (CONTAINS).
2. Procedural memories are loaded first, sorted by confidence, capped at `max_procedural`.
3. Semantic memories are loaded second, sorted by confidence, capped at `max_semantic`.
4. Episodic memories are loaded last, sorted by recency, capped at `max_episodic`.
5. All loaded memories are filtered by ReBAC — only memories the Persona has CAN_READ access to are included.
6. The total estimated tokens of the Visible Field do not exceed the Session's `token_budget`.
7. When budget is tight, Episodic memories are trimmed first, then Semantic, then Procedural.
8. A LOADED edge is created for every memory in the Visible Field.
9. The Session's `visible_field_snapshot` contains the serialized VisibleField.
10. A Persona with no accessible memories returns a valid VisibleField with empty lists (cold start).
11. A cross-tenant request returns TenantViolation.
