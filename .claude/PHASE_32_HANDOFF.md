# Phase 32: Event Log Integration Handoff

**Status:** PHASE 31 COMPLETE. PHASE 32 READY FOR EXECUTION.  
**Date:** 2026-05-21  
**Branch:** `phase-32-event-log-integration`

---

## 🎯 PHASE 32 Mission

Wire the event log (`siss-event-log`) through the authorization pipeline and extend async job routing with explicit dependency queues. This phase creates the observability backbone for all future control flow (SSE streaming, distributed decision tracking, audit compliance).

**Success Criteria:**
- ✅ `authorize_task()` emits AccessDecision events post-commit
- ✅ `siss-job-router` has explicit `depends_on: Vec<JobId>` field
- ✅ Dependency validation and queue logic operational
- ✅ Event log appends on task lifecycle
- ✅ `siss-cockpit` SSE endpoint consumes event stream
- ✅ `cargo test --all` → 30/30 passing (24 Phase 32 + 6 Phase 25 regressions)

---

## 📋 INFRASTRUCTURE STATE

### Event Log Crate (`siss-event-log`)
**Status:** Ready. Core types + repo layer complete.

**Location:** `crates/siss-event-log/`
**Key Files:**
- `src/lib.rs` — Public API (EventLog, SystemEvent, EventFilter, EventId, JobId)
- `src/repo.rs` — EventLog trait + SQL persistence layer
- `src/types.rs` — Event enums (AccessDecision, TaskAssigned, etc.)
- `src/migrations/` — Schema definitions

**Public API:**
```rust
pub struct EventLog;
impl EventLog {
    pub async fn append_event(pool: &PgPool, event: SystemEvent) -> Result<EventId, LogError>;
    pub async fn fetch_events(pool: &PgPool, filter: EventFilter) -> Result<Vec<SystemEvent>, LogError>;
}

pub enum SystemEvent {
    AccessDecision { task_id, decision, risk_class, persona_id, ... },
    TaskAssigned { job_id, assigned_at, payload, ... },
    JobCompleted { job_id, result, metrics, ... },
    DependencyResolved { parent_job_id, resolved_deps, ... },
    // ... more variants
}
```

### Gatekeeper Pipeline (`siss-gatekeeper`)
**Status:** 5-stage authorization complete. Missing: event log append post-commit.

**Location:** `crates/siss-gatekeeper/src/pipeline/`

**Current Entry Point:**
```rust
// authorize_task() — lines 18-66 in pipeline/mod.rs
// Stages: validate → ReBAC → AP2 → governance → sign+commit
// Each stage modifies state but NO event emissions yet
```

**Issue:** `commit::sign_and_commit()` creates AccessDecision in database but does NOT emit to event log.

### Job Router (`siss-job-router`)
**Status:** Basic routing working. Missing: dependency queue logic.

**Location:** `crates/siss-job-router/src/`
**Key Files:**
- `pipeline/mod.rs` — Main dispatcher
- `pipeline/validate.rs` — Validation rules
- `pipeline/execute.rs` — Task execution
- `types.rs` — RoutingRequest, RoutingDecision

**Current RoutingRequest Structure:**
```rust
pub struct RoutingRequest {
    pub job_id: JobId,
    pub intent_id: IntentId,
    pub agent_id: AgentId,
    pub complexity_score: i32,
    // ... missing: depends_on field
}
```

### Cockpit UI (`siss-cockpit`)
**Status:** SSE infrastructure wired (Phase 31). Missing: event log stream binding.

**Location:** `crates/siss-cockpit/src/`
**Key Files:**
- `src/api/handlers.rs` — SSE endpoint (/api/agents/stream)
- `src/ui/dashboard.js` — EventSource listener
- `src/state.rs` — Event buffer (max 1000 events)

---

## 🔧 PHASE 32 TASKS (Sequential Execution)

### Task 2: Wire Event Log into Gatekeeper (2-3 files)

**Scope:** Modify `siss-gatekeeper` to emit AccessDecision events after authorization succeeds.

**Files to Modify:**
1. `crates/siss-gatekeeper/src/pipeline/mod.rs` — authorize_task()
   - Import: `use siss_event_log::{EventLog, SystemEvent};`
   - After `commit::sign_and_commit()` succeeds, call:
     ```rust
     let event = SystemEvent::AccessDecision { ... };
     EventLog::append_event(pool, event).await?;
     ```

2. `crates/siss-gatekeeper/src/pipeline/commit.rs` — Return more data
   - Modify `sign_and_commit()` return type to include decision details
   - Caller (authorize_task) uses returned data to construct SystemEvent

3. `Cargo.toml` — Workspace dependency
   - Add `siss-event-log` to `siss-gatekeeper` dependencies (if not present)

**Test Pattern:**
- Create test in `crates/siss-gatekeeper/src/tests/event_emission.rs`
- Mock EventLog append
- Verify AccessDecision event created post-authorization
- Verify error propagation if event log fails

**Success Criteria:**
- ✅ Authorization still returns AuthorizationResult (no signature change)
- ✅ Event emitted with correct task_id, decision, risk_class, persona_id
- ✅ If event append fails, authorization fails (transactional)
- ✅ All existing gatekeeper tests pass (zero regressions)

---

### Task 3: Extend Job Router with Dependency Queues (3-4 files, Wave B)

**Scope:** Add explicit dependency tracking to job routing. Enqueue jobs that depend on other jobs; resolve dependencies when parent completes.

**Files to Modify:**

1. `crates/siss-job-router/src/types.rs`
   - Add field to RoutingRequest:
     ```rust
     pub struct RoutingRequest {
         // ... existing fields ...
         pub depends_on: Vec<JobId>,  // NEW
     }
     ```

2. `crates/siss-job-router/src/pipeline/validate.rs`
   - New validation rule: `validate_dependencies()`
   - Check: all JobIds in depends_on exist in database
   - Check: no circular dependencies (BFS/DFS scan)
   - Check: depends_on jobs are in QUEUED or COMPLETED status

3. `crates/siss-job-router/src/pipeline/execute.rs`
   - When job status = COMPLETED, trigger dependency resolution:
     ```rust
     // Find all jobs that depend_on this job
     let dependent_jobs = find_dependents(job_id).await?;
     
     // Update their status: WAITING → QUEUED
     for dep_job_id in dependent_jobs {
         update_job_status(dep_job_id, JobStatus::QUEUED).await?;
         EventLog::append_event(pool, SystemEvent::DependencyResolved { ... }).await?;
     }
     ```

4. `crates/siss-job-router/src/pipeline/mod.rs`
   - Add dependency queue dispatcher:
     ```rust
     pub async fn process_dependency_queue(pool: &PgPool) -> Result<(), RouterError> {
         // Periodically scan for QUEUED jobs with satisfied dependencies
         // Move them to RUNNING
     }
     ```

**Test Pattern:**
- Create test suite in `crates/siss-job-router/src/tests/dependency_queue_tests.rs`
- Test 1: validate_dependencies rejects circular deps
- Test 2: validate_dependencies rejects missing parent jobs
- Test 3: Parent job completion triggers dependent job activation
- Test 4: Event emitted when dependency resolves
- Test 5: Multiple dependent jobs queued, all activated together

**Success Criteria:**
- ✅ RoutingRequest accepts depends_on field
- ✅ Circular dependencies rejected
- ✅ Missing parent jobs rejected
- ✅ Job completion triggers dependent job activation
- ✅ DependencyResolved event emitted
- ✅ All existing job router tests pass

---

### Task 4: Wire Cockpit SSE to Event Log Stream (2-3 files, Wave C)

**Scope:** Connect the SSE endpoint to the event log stream. Dashboard receives AccessDecision, DependencyResolved, JobCompleted events in real-time.

**Files to Modify:**

1. `crates/siss-cockpit/src/api/handlers.rs` — /api/agents/stream endpoint
   - Current: broadcasts AgEvent (agent-shell events)
   - New: also subscribe to event log stream
   ```rust
   // Pseudo-code
   pub async fn stream_events(State(state): State<CockpitState>) -> Sse<impl Stream<Item = Event>> {
       let agent_events = subscribe_to_agent_events();
       let system_events = EventLog::subscribe(pool).await?;  // NEW
       
       // Merge both streams
       let merged = futures::stream::select(agent_events, system_events)
           .map(|e| serde_json::json!(e))
           .map(Event::default);
       
       Sse::new(merged)
   }
   ```

2. `crates/siss-cockpit/src/state.rs` — Event buffering
   - Current: buffers AgEvent (max 1000)
   - New: unify buffer to handle both AgEvent and SystemEvent
   ```rust
   pub enum BufferedEvent {
       Agent(AgEvent),
       System(SystemEvent),
   }
   ```

3. `crates/siss-cockpit/ui/dashboard.js` — EventSource listener
   - Current: renders AgEvent (agent cards, status, output)
   - New: also render SystemEvent (AccessDecision → risk badge, DependencyResolved → job tree)

**Integration Pattern:**
```rust
// In CockpitState::new()
let event_log = EventLog::new(pool.clone());
let event_subscription = event_log.subscribe().await?;
```

**Test Pattern:**
- E2E test: Create task → authorize → check SSE receives AccessDecision event
- E2E test: Create job with dependency → parent completes → verify DependencyResolved on SSE stream
- Buffering test: Disconnect/reconnect → receive last 50 system events

**Success Criteria:**
- ✅ SSE endpoint streams both AgEvent and SystemEvent
- ✅ Dashboard displays AccessDecision with risk class badge
- ✅ Dashboard displays job dependency tree
- ✅ Event buffer (max 1000) handles mixed types
- ✅ Reconnect delivers event history (last 50 events)

---

## 🏗️ EXECUTION PLAN

### Phase 32 Wave Structure
```
Phase 32A: Gatekeeper + Event Log (Task 2) — Linear execution
├─ Modify authorize_task() to append events
├─ Write event_emission_tests.rs
├─ Verify: cargo test -p siss-gatekeeper

Phase 32B: Job Router Dependencies (Task 3) — Linear execution
├─ Add depends_on to RoutingRequest
├─ Write validate_dependencies()
├─ Wire dependency resolution in execute.rs
├─ Write dependency_queue_tests.rs
├─ Verify: cargo test -p siss-job-router

Phase 32C: Cockpit SSE Integration (Task 4) — Linear execution
├─ Unify event buffering in cockpit state
├─ Modify /api/agents/stream to subscribe to event log
├─ Update dashboard.js to render SystemEvent
├─ Write SSE integration tests
├─ Verify: cargo test -p siss-cockpit

Final Verification
├─ cargo test --all
├─ Expected: 30/30 passing (24 Phase 32 + 6 Phase 25)
└─ Deploy to main
```

---

## 📊 VERIFICATION CHECKLIST

Before marking Phase 32 COMPLETE:

- [ ] **Gatekeeper (Task 2)**
  - [ ] authorize_task() appends AccessDecision event
  - [ ] Event contains correct task_id, decision, risk_class, persona_id, signed_at
  - [ ] Existing gatekeeper tests pass (0 regressions)
  - [ ] Event emission tests created (min 3 tests)

- [ ] **Job Router (Task 3)**
  - [ ] RoutingRequest.depends_on field added
  - [ ] validate_dependencies() rejects circular deps
  - [ ] Job completion triggers dependent job activation
  - [ ] DependencyResolved event emitted correctly
  - [ ] Existing job router tests pass (0 regressions)
  - [ ] Dependency queue tests created (min 5 tests)

- [ ] **Cockpit SSE (Task 4)**
  - [ ] /api/agents/stream broadcasts SystemEvent
  - [ ] Dashboard renders AccessDecision (risk badge)
  - [ ] Dashboard renders job dependency tree
  - [ ] Event buffer handles mixed AgEvent/SystemEvent
  - [ ] Reconnect delivers event history
  - [ ] Existing cockpit tests pass (0 regressions)
  - [ ] SSE integration tests created (min 3 tests)

- [ ] **Compilation & Testing**
  - [ ] `cargo check --all` passes
  - [ ] `cargo clippy --all` clean (0 warnings)
  - [ ] `cargo test --all` → **30/30 passing**
  - [ ] No new warnings in test output

- [ ] **Git & Handoff**
  - [ ] All changes committed atomically
  - [ ] No merge conflicts (Golden Rule enforced)
  - [ ] Branch merges cleanly to main
  - [ ] Next phase's HANDOFF.md written

---

## 🔗 REFERENCE FILES

| File | Purpose |
|------|---------|
| `MEMORY.md` | Phase 31 crystallized patterns (GitNexus, file-orthogonal design) |
| `PHASE_31_HANDOFF.md` | Phase 31 completion state |
| `WAVE_ORCHESTRATOR.md` | Locked interface contracts (use if modifying cockpit APIs) |
| `.claude/CLAUDE.md` | Core operations doctrine + Golden Rule |
| `Cargo.toml` (root) | Workspace dependencies |

---

## ⚡ CRITICAL RULES FOR NEXT AGENT

1. **Always use GitNexus before editing:** Run `gitnexus_impact({target: "authorize_task", direction: "upstream"})` before modifying gatekeeper
2. **Test-First:** Write tests before implementation (TDD)
3. **No Drive-by Cleanup:** Stick to Task 2/3/4 scope only
4. **Golden Rule:** Each task modifies disjoint files; no merge conflicts
5. **Event Log Pattern:** All events must include `created_at`, `task_id` or `job_id`, human-readable description

---

## 🎬 NEXT SESSION STARTUP

**Step 1:** Load this handoff:
```bash
cat .claude/PHASE_32_HANDOFF.md
```

**Step 2:** Verify git state:
```bash
git status
git log --oneline -5  # Should show Phase 31 commits
```

**Step 3:** Verify compilation:
```bash
cargo check --all
cargo test --lib --no-run  # Compile but don't run (faster)
```

**Step 4:** Start Task 2:
```bash
# Read current authorize_task() implementation
read crates/siss-gatekeeper/src/pipeline/mod.rs

# Check event log API
read crates/siss-event-log/src/lib.rs

# Start modifying authorize_task()
edit crates/siss-gatekeeper/src/pipeline/mod.rs
```

---

**Handoff Complete. Phase 32 Ready for Execution. ✅**

