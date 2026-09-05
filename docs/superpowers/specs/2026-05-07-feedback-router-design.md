# Feedback Router Design — Step F

**Date:** 2026-05-07
**Status:** Approved
**Scope:** Step F — Task completion, quality scoring, and memory crystallization for the SISS value loop
**Depends on:** Step A (Knowledge Graph Schema), Step E (Behavioral Firewall — Verdict type)

---

## 1. Overview

The Feedback Router is the "Learn & Crystallize" step — the final component of the SISS value loop. It receives a Task that has been cleared by the Behavioral Firewall (status = `guarding`), scores its execution quality, crystallizes the output into a permanent memory node, and transitions the Task to `completed`.

The byproduct of every successful execution is a new memory node that makes the system smarter for the next task.

### Position in the Value Loop

```
1. [Sense & Authorize] ← Governance Gatekeeper (Step B) ✅
2. [Orient & Preload]  ← Context Cartography (Step D) ✅
3. [Decide & Execute]  ← Job Router (Step C) ✅
4. [Act & Guard]       ← Behavioral Firewall (Step E) ✅
5. [Learn & Crystallize] ← FEEDBACK ROUTER (this component)
```

---

## 2. Architecture

A new Rust library crate `siss-feedback-router` that depends on `siss-graph-core` and `siss-graph-db`. Exposes a single async entry point `complete_task`. Uses two pluggable traits: `Scorer` (evaluates quality) and `Crystallizer` (produces memory nodes).

### Key Design Principles

1. **Trait-based** — `Scorer` and `Crystallizer` are swappable
2. **Score + Crystallize + Complete** — no AP2 refund or memory reinforcement at launch
3. **One memory per task** — default Crystallizer produces one Episodic memory
4. **Quality score seeds confidence** — the new memory's confidence_score starts at the quality score

---

## 3. Types

### CompletionRequest

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | `NodeId` | The Task to complete |
| `persona_id` | `NodeId` | The Persona that executed it |
| `intent_mandate_id` | `NodeId` | The IntentMandate that funded it |
| `tenant_id` | `NodeId` | Tenant isolation boundary |
| `verdict` | `Verdict` | From the Behavioral Firewall (Clear/Blocked/CriticalBlocked) |
| `execution_output` | `serde_json::Value` | The execution result output |
| `token_cost` | `i64` | Actual tokens consumed |
| `estimated_cost` | `i64` | Originally estimated cost |

### CompletionResult

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | `NodeId` | The completed Task |
| `quality_score` | `f64` | Computed quality score [0.0, 1.0] |
| `crystallized_memories` | `Vec<CrystallizedMemory>` | Memories produced |

### CrystallizedMemory

| Field | Type | Description |
|-------|------|-------------|
| `memory_id` | `Uuid` | The new memory node's ID |
| `tier` | `ConsolidationTier` | Which tier the memory was created in |
| `content` | `String` | The memory content |

### FeedbackError

| Variant | Description |
|---------|-------------|
| `TaskNotFound` | Task ID does not exist |
| `InvalidTaskStatus` | Task is not in `guarding` status |
| `TenantViolation` | Cross-tenant operation attempted |
| `DatabaseError` | Database operation failed |

---

## 4. Scorer Trait

```rust
pub trait Scorer: Send + Sync {
    fn score(&self, context: &ScoringContext) -> f64;
}
```

### ScoringContext

| Field | Type | Description |
|-------|------|-------------|
| `verdict` | `Verdict` | Firewall verdict |
| `token_cost` | `i64` | Actual cost |
| `estimated_cost` | `i64` | Estimated cost |

### Default: HeuristicScorer

- Verdict component: Clear=1.0, Blocked=0.5, CriticalBlocked=0.0
- Efficiency component: `1.0 - (token_cost as f64 / estimated_cost as f64)` clamped to [0.0, 1.0]. If estimated_cost is 0, efficiency = 1.0.
- Final score: `(verdict_score + efficiency_score) / 2.0`

---

## 5. Crystallizer Trait

```rust
pub trait Crystallizer: Send + Sync {
    fn crystallize(&self, context: &CrystallizationContext) -> Vec<CrystallizedMemory>;
}
```

### CrystallizationContext

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | `Uuid` | Task identifier |
| `intent` | `String` | The original task intent |
| `execution_output` | `serde_json::Value` | The execution output |
| `quality_score` | `f64` | The computed quality score |

### Default: EpisodicCrystallizer

Produces one `Episodic_Memory` with:
- `content`: `"Task: {intent}\nOutput: {output_summary}\nQuality: {score:.2}"`
- `confidence_score`: set to the quality score
- `quality_score`: set to the quality score
- Output summary: first 500 characters of the JSON-serialized output

---

## 6. Pipeline

### Step 1: VALIDATE
- Fetch Task; verify `status == guarding`
- Verify tenant isolation
- Fetch task intent for crystallization context

### Step 2: TRANSITION TO CRYSTALLIZING
- Task status → `crystallizing`

### Step 3: SCORE
- Build `ScoringContext` from request
- Call `scorer.score(context)` → `quality_score`

### Step 4: CRYSTALLIZE
- Build `CrystallizationContext` with intent, output, and quality_score
- Call `crystallizer.crystallize(context)` → `Vec<CrystallizedMemory>`

### Step 5: PERSIST
- For each CrystallizedMemory: insert Memory node in DB
- Create `PRODUCED` edge (Task → Memory) for each
- Update Task's quality metadata if needed

### Step 6: COMPLETE
- Task status → `completed`
- Return `CompletionResult`

---

## 7. DB Functions Needed

| Function | Description |
|----------|-------------|
| `insert_memory(pool, content, tier, confidence, quality, tenant_id)` | Create a new memory node |

Existing functions used: `fetch_task`, `update_task_status`, `edge_repo::insert_edge`.

---

## 8. File Structure

```
crates/
  siss-feedback-router/
    Cargo.toml
    src/
      lib.rs              # Re-exports
      types.rs            # CompletionRequest, CompletionResult, CrystallizedMemory, FeedbackError
      scorer/
        mod.rs            # Scorer trait + ScoringContext
        heuristic.rs      # HeuristicScorer
      crystallizer/
        mod.rs            # Crystallizer trait + CrystallizationContext
        episodic.rs       # EpisodicCrystallizer
      pipeline/
        mod.rs            # complete_task() orchestrator
        validate.rs       # Validation + transition to crystallizing
        persist.rs        # Insert memories + PRODUCED edges + complete
```

---

## 9. Success Criteria

1. A cleared Task (verdict=Clear, cost=50, estimated=100) produces quality_score=1.0 (verdict) + 0.5 (efficiency) / 2 = 0.75.
2. A blocked Task (verdict=Blocked) produces quality_score with verdict component = 0.5.
3. Crystallization produces exactly one Episodic memory containing the task intent and output summary.
4. The PRODUCED edge (Task → Memory) is created.
5. The memory's confidence_score equals the quality_score.
6. Task transitions: `guarding` → `crystallizing` → `completed`.
7. A Task not in `guarding` status returns `InvalidTaskStatus`.
8. Cross-tenant returns `TenantViolation`.
9. The Scorer trait can be swapped without changing the pipeline.
10. The Crystallizer trait can be swapped without changing the pipeline.
