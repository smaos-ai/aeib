# Phase 30 Specification: Advanced Worktree Orchestration
**Date:** May 20, 2026  
**Status:** READY FOR IMPLEMENTATION  
**Duration:** 5 days (dispatcher → workers → merge → cleanup)  
**Agents:** 1 dispatcher + 5 worker agents (parallel execution)

---

## Executive Summary

Phase 30 enables **Advanced Worktree Orchestration** — a distributed task execution system where 1 dispatcher spawns up to 5 concurrent Claude Code agents, each running in an isolated git worktree. Workers fetch tasks from a queue, execute them independently, report progress via SSE, and merge results back to main with zero conflicts.

**Blocking dependencies:** None. Works alongside Phase 25-29.  
**New components:** Task queue (in-memory or Redis), dispatcher agent entry point, worker agent lifecycle hooks, merge orchestrator, conflict detection.  
**Estimated LOC:** 1,500-2,000 (dispatcher, workers, merge coordinator, tests)

---

## 1. THE "ONE THING"

> **Enable 3-5 concurrent Claude Code agents to work in parallel on independent tasks without git conflicts or race conditions.**

**Definition of done:**
- [ ] 5 worker agents spawn from single dispatcher command
- [ ] Each worker gets unique task + isolated worktree
- [ ] All 5 complete in <30 minutes without blocking each other
- [ ] Zero git merge conflicts on final integration
- [ ] Task dependencies enforced (task B waits for task A merge)
- [ ] Rollback/recovery if any worker fails

---

## 2. ARCHITECTURE OVERVIEW

### 2.1 Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    DISPATCHER AGENT (main)                      │
│  - Parse task manifest                                          │
│  - Create task queue                                            │
│  - Spawn 3-5 worker agents                                      │
│  - Monitor progress via SSE                                     │
│  - Orchestrate merge sequence                                   │
└────────────────────┬────────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┬────────────┐
        │            │            │            │
    ┌───▼────┐  ┌───▼────┐  ┌───▼────┐  ┌───▼────┐
    │Worker 1│  │Worker 2│  │Worker 3│  │Worker 4│  (+ Worker 5)
    │        │  │        │  │        │  │        │
    │ Task A │  │ Task B │  │ Task C │  │ Task D │
    │ WKT-1  │  │ WKT-2  │  │ WKT-3  │  │ WKT-4  │
    └────────┘  └────────┘  └────────┘  └────────┘
        │            │            │            │
        └────────────┼────────────┴────────────┘
                     │
                Task Queue & Status
                (Memory + SSE Broadcast)
                     │
        ┌────────────▼────────────┐
        │  Merge Orchestrator      │
        │ (Sequential, Ordered)    │
        │ Conflict Detection       │
        │ Rollback on Failure      │
        └──────────────────────────┘
                     │
                     ▼
            main branch (integrated)
```

### 2.2 Worktree Lifecycle

Each worker agent operates in its own git worktree:

```
Before:
  /SovereignNexus/.git (main)
  /SovereignNexus/main (checked out)

During (Worker 1):
  /SovereignNexus/.git (shared)
  /SovereignNexus/main (main branch)
  /SovereignNexus/.claude/worktrees/task-a-worker-1/
    ├── .git (independent worktree)
    ├── CLAUDE.md (phase-30 instructions)
    ├── src/ (task code)
    └── tests/ (task tests)

During (Worker 2):
  /SovereignNexus/.claude/worktrees/task-b-worker-2/
    ├── .git (independent worktree)
    └── ...

After all workers finish:
  All worktrees merged to main
  All worktrees cleaned up
  /SovereignNexus/main (contains all changes)
```

### 2.3 Task Dependencies & Ordering

Tasks may have sequential dependencies:

```yaml
tasks:
  - id: task-a
    title: "Create entity models"
    depends_on: []
    worker: worker-1
    
  - id: task-b
    title: "Implement entity repository"
    depends_on: [task-a]
    worker: worker-2
    
  - id: task-c
    title: "Build API layer"
    depends_on: [task-b]
    worker: worker-3
    
  - id: task-d
    title: "Write integration tests"
    depends_on: [task-a, task-b, task-c]
    worker: worker-4
```

**Merge order:** task-a → task-b → task-c → task-d (enforced by dependency DAG)

---

## 3. EXECUTION PROTOCOL

### 3.1 Phase 1: Task Submission & Queue Setup

**Dispatcher workflow:**

```
1. User invokes: `claude-code /orchestrate --manifest=tasks.yaml`
2. Dispatcher reads manifest (YAML/JSON with task list + dependencies)
3. Validate dependencies form a DAG (no cycles)
4. Create in-memory task queue:
   - status[task-a] = pending
   - status[task-b] = blocked (waiting for task-a)
   - status[task-c] = blocked
   - status[task-d] = blocked
5. Start SSE broadcast server on localhost:9999
   - Endpoint: /events (task status updates)
6. Publish: task-a ready, task-b,c,d waiting
7. Spawn worker agents (up to worker count)
```

**Task Queue Structure:**

```rust
pub struct Task {
    pub id: String,              // "task-a"
    pub title: String,           // "Create entity models"
    pub description: String,     // Full task description
    pub depends_on: Vec<String>, // ["task-1", "task-2"]
    pub status: TaskStatus,      // pending|assigned|running|completed|failed
    pub assigned_to: Option<String>, // "worker-1"
    pub created_at: DateTime,
    pub started_at: Option<DateTime>,
    pub completed_at: Option<DateTime>,
    pub error: Option<String>,
}

pub enum TaskStatus {
    Pending,      // In queue, ready to run
    Blocked,      // Waiting for dependencies
    Assigned,     // Assigned to a worker
    Running,      // Worker actively executing
    Completed,    // Done, ready to merge
    Failed,       // Error occurred (rollback pending)
}
```

### 3.2 Phase 2: Worker Agent Spawning & Task Fetch

**For each worker (1-5):**

```
1. Dispatcher invokes: 
   `claude-code /worker --id=worker-1 --task=task-a --queue-url=localhost:9999`

2. Worker agent starts in main session
   - Connects to task queue SSE stream
   - Subscribe to /events (listens for task assignments)
   
3. Worker polls queue:
   GET /queue/tasks?status=pending
   → Receives first unblocked task
   
4. Worker marks task as assigned:
   PATCH /queue/tasks/task-a {status: "assigned", assigned_to: "worker-1"}
   
5. Worker creates isolated worktree:
   git worktree add .claude/worktrees/task-a-worker-1 origin/main
   cd .claude/worktrees/task-a-worker-1
   
6. Worker fetches task manifest for detailed requirements:
   GET /queue/tasks/task-a/manifest
   → Returns CLAUDE.md, success criteria, test specs
   
7. Worker marks task as running:
   PATCH /queue/tasks/task-a {status: "running", started_at: now()}
   
8. Worker publishes to SSE: "task-a: running (worker-1)"
```

### 3.3 Phase 3: Isolated Task Execution

**Worker execution loop (in worktree):**

```
1. Read task manifest (success criteria, test requirements)
2. Create feature branch:
   git checkout -b task-a (from origin/main)
3. Write tests (TDD first):
   cargo test --test task_a_tests → RED
4. Implement feature:
   cargo build → GREEN
   cargo test → GREEN
5. Run linter:
   cargo clippy → 0 warnings
6. Commit locally:
   git commit -m "task-a: [description]"
7. Publish progress:
   POST /queue/tasks/task-a/progress {
     message: "tests passing",
     percent: 75
   }
8. Continue until done:
   git commit -m "task-a: complete + verified"
```

**Key constraint:** Worker operates ONLY within its worktree directory. No modifications to main branch until merge phase.

### 3.4 Phase 4: Status Reporting & Coordination

**Workers emit progress via SSE to dispatcher:**

```
Worker-1: task-a → {
  "task_id": "task-a",
  "status": "running",
  "progress_percent": 50,
  "message": "tests passing, starting implementation",
  "timestamp": "2026-05-20T14:30:00Z"
}

Worker-2: task-b (blocked) → {
  "task_id": "task-b",
  "status": "blocked",
  "blocked_by": ["task-a"],
  "message": "waiting for task-a to merge",
  "timestamp": "2026-05-20T14:30:05Z"
}
```

**Dispatcher monitor (SSE consumer):**
- Aggregates all worker events
- Tracks task completion order
- Detects failures early
- Logs to stdout + persistent event log

### 3.5 Phase 5: Dependency Resolution & Merge Sequence

**Once task-a completes locally:**

```
1. Worker-1 signals to dispatcher:
   POST /queue/tasks/task-a/complete {
     "status": "completed",
     "worktree": ".claude/worktrees/task-a-worker-1"
   }
   
2. Dispatcher checks if task-a can be merged:
   - All tests pass? YES
   - Depends on: [] (no dependencies)
   - Mark as "ready_to_merge"
   
3. Merge orchestrator pulls task-a:
   git fetch origin task-a:task-a-merge
   git checkout main
   git merge --no-ff task-a-merge
   - Conflict? NO (isolated worktree, no conflicts expected)
   
4. Delete worktree:
   git worktree remove .claude/worktrees/task-a-worker-1 --force
   
5. Mark main updated:
   git push origin main
   
6. Task-b is now unblocked:
   Publish SSE: task-b ready
   Worker-2 receives assignment signal
```

**Merge ordering enforced by dependency DAG:**

```
Merge sequence:
1. task-a (depends_on: [])         → Merge immediately
2. task-b (depends_on: [a])        → Merge after a merged + pull new main
3. task-c (depends_on: [b])        → Merge after b merged + pull new main
4. task-d (depends_on: [a,b,c])    → Merge after all upstream merged
```

### 3.6 Phase 6: Conflict Detection & Prevention

**Before each merge, orchestrator validates:**

```
1. Fetch latest main:
   git fetch origin main:main-latest
   
2. Check for file overlaps:
   git diff --name-only main-latest task-a-merge
   files_a = {src/models.rs, tests/models_test.rs}
   
   git diff --name-only main-latest task-b-merge
   files_b = {src/repo.rs, tests/repo_test.rs}
   
   overlap = files_a ∩ files_b = {} (no conflicts expected)
   
3. If overlap detected:
   - Task isolation violated
   - Fail merge + alert dispatcher
   - Prevent corruption
   
4. Merge dry-run:
   git merge --no-commit --no-ff task-a-merge
   → Detects merge conflicts before committing
   → If conflict: abort, rollback, alert
   → If clean: commit + push
```

### 3.7 Phase 7: Failure & Rollback

**If worker fails (tests don't pass):**

```
1. Worker reports:
   POST /queue/tasks/task-a/failure {
     "error": "Test assertion failed: expected 42, got 41",
     "log": "<full test output>"
   }
   
2. Task marked as failed:
   status[task-a] = failed
   
3. Dispatcher publishes:
   "task-a: FAILED — see error log"
   
4. Dependent tasks (b, d) remain blocked:
   status[task-b] = blocked (now blocked by task-a failure)
   
5. Dispatcher options:
   a) Halt orchestration (wait for manual fix)
   b) Retry worker on same task
   c) Skip task + continue (if allowed)
   
6. Worktree cleanup (even on failure):
   git worktree remove .claude/worktrees/task-a-worker-1 --force
```

**Rollback to main (cascade):**
```
If task-a failed → task-b, task-d blocked
User can:
1. Fix task-a in new worker session
2. Resubmit with --retry=task-a
3. Abort entire orchestration (all worktrees cleaned up)
```

---

## 4. SUCCESS CRITERIA (Verifiable)

All items must be GREEN for Phase 30 to pass:

- [ ] **5-agent concurrency:** All 5 workers accept tasks simultaneously, no blocking on queue
- [ ] **0 merge conflicts:** Implement 5 independent tasks (models, repo, API, tests, docs), merge all with 0 conflicts
- [ ] **Dependency enforcement:** Task B does NOT merge before Task A; merge order verified in git log
- [ ] **<30 min execution:** All 5 tasks complete (code + tests) in <30 minutes wall time
- [ ] **Correct final state:** `git log --oneline main | head -10` shows all 5 task commits in dependency order
- [ ] **Integration tests pass:** Run full test suite on merged main; all tests green
- [ ] **Worktree cleanup:** After all merges, `git worktree list` shows 0 worktrees; `.claude/worktrees/task-*` directories deleted
- [ ] **Failure recovery:** Intentionally fail 1 task (e.g., task-c), verify rollback mechanism works, retry task-c, re-merge successfully
- [ ] **SSE broadcast working:** Dispatcher receives all worker status updates in <500ms latency
- [ ] **No data loss:** All task commits, test results, and logs persisted in git history

---

## 5. DETAILED IMPLEMENTATION STEPS

### 5.1 Dispatcher Agent (Entry Point)

**File:** `.claude/skills/orchestration/dispatcher.md` (skill file)

```markdown
# Orchestration Dispatcher Skill

## Input
- manifest: YAML task list (see example below)
- worker_count: 1-5 (default 3)

## Workflow
1. Parse manifest → validate DAG
2. Start in-memory queue + SSE broadcast server
3. Log start: "Orchestrating 5 tasks with 3 workers"
4. Spawn worker agents (up to worker_count)
5. Monitor all workers via SSE
6. Coordinate merges in dependency order
7. Report final status + metrics

## Manifest Format
```yaml
tasks:
  - id: task-a
    title: "Create entity models"
    description: "Implement Entity + EntityID types with serde"
    depends_on: []
    success_criteria:
      - "cargo test passes"
      - "zero clippy warnings"
      - "benchmarks show <1ms latency"
  
  - id: task-b
    title: "Entity repository layer"
    depends_on: [task-a]
    success_criteria:
      - "CRUD ops tested"
      - "transactions working"
```

## Output
- .phase30/orchestration_report.md (summary)
- .phase30/merge_log.txt (all git commits)
- .phase30/worker_logs/*.log (per-worker execution logs)
- Final: "All tasks merged to main ✓"
```

### 5.2 Task Queue Service (In-Memory)

**File:** `crates/siss-orchestration/src/queue.rs`

```rust
use std::sync::{Arc, Mutex};
use std::collections::HashMap;
use chrono::{DateTime, Utc};

pub struct TaskQueue {
    tasks: Arc<Mutex<HashMap<String, Task>>>,
    event_log: Arc<Mutex<Vec<Event>>>,
}

impl TaskQueue {
    pub fn new() -> Self {
        TaskQueue {
            tasks: Arc::new(Mutex::new(HashMap::new())),
            event_log: Arc::new(Mutex::new(Vec::new())),
        }
    }

    pub async fn fetch_ready_task(&self) -> Option<Task> {
        // Return first task with status=pending and all dependencies completed
    }

    pub async fn mark_running(&self, task_id: String, worker_id: String) {
        // Update status → running
        // Log event to SSE
    }

    pub async fn mark_completed(&self, task_id: String) {
        // Update status → completed
        // Unblock dependent tasks → pending
        // Publish SSE event
    }

    pub async fn mark_failed(&self, task_id: String, error: String) {
        // Update status → failed
        // Block dependent tasks
        // Publish SSE event
    }

    pub async fn subscribe_events(&self) -> tokio::sync::mpsc::Receiver<Event> {
        // Return SSE stream for all task events
    }
}

pub struct Event {
    pub task_id: String,
    pub status: TaskStatus,
    pub message: String,
    pub timestamp: DateTime<Utc>,
}
```

### 5.3 Worker Agent Lifecycle

**File:** `.claude/skills/orchestration/worker.md` (skill file)

```markdown
# Worker Agent Skill

## Input
- worker_id: string (worker-1, worker-2, etc.)
- queue_url: string (localhost:9999)
- max_attempts: u32 (default 1)

## Workflow
1. Connect to queue SSE stream
2. Poll for available task
3. Create worktree: git worktree add .claude/worktrees/task-X-worker-N origin/main
4. cd into worktree
5. Fetch task manifest (success criteria)
6. TDD: Write tests first, implement, verify green
7. Report completion to queue
8. Wait for merge orchestration
9. On merge complete, exit cleanly

## Key Constraints
- ONLY modify files within worktree
- NEVER touch main branch directly
- Commit all changes locally
- Report progress via SSE every 5 minutes
- Exit with status code 0 on success, 1 on failure
```

### 5.4 Merge Orchestrator

**File:** `crates/siss-orchestration/src/merge.rs`

```rust
pub struct MergeOrchestrator {
    queue: Arc<TaskQueue>,
    repo_path: PathBuf,
}

impl MergeOrchestrator {
    pub async fn execute_merge_plan(&self) -> Result<()> {
        // 1. Topological sort tasks by dependency
        let merge_order = self.compute_merge_order();
        
        // 2. For each task in order:
        for task_id in merge_order {
            self.merge_task(&task_id).await?;
        }
        
        // 3. Cleanup worktrees
        self.cleanup_all_worktrees().await?;
        
        Ok(())
    }

    async fn merge_task(&self, task_id: &str) -> Result<()> {
        // 1. Fetch task details from queue
        let task = self.queue.get_task(task_id).await?;
        
        // 2. Pull latest main (in case other tasks merged)
        self.git_fetch_main()?;
        
        // 3. Detect conflicts
        let conflicts = self.detect_conflicts(&task)?;
        if !conflicts.is_empty() {
            return Err(format!("Merge conflicts detected: {:?}", conflicts));
        }
        
        // 4. Merge worktree into main
        self.git_merge(&task)?;
        
        // 5. Push to origin
        self.git_push()?;
        
        // 6. Mark task as merged in queue
        self.queue.mark_merged(task_id).await?;
        
        Ok(())
    }

    fn detect_conflicts(&self, task: &Task) -> Result<Vec<String>> {
        // git diff --name-only --merge
        // Return list of conflicting files (empty = no conflicts)
    }

    fn git_merge(&self, task: &Task) -> Result<()> {
        // git fetch origin task-branch:task-branch-merge
        // git checkout main
        // git merge --no-ff task-branch-merge
        // If conflict: git merge --abort, return error
        // If clean: commit + return
    }
}
```

### 5.5 Example Manifest (tasks.yaml)

```yaml
version: "1.0"
orchestration:
  worker_count: 5
  timeout_minutes: 30
  rollback_on_failure: true

tasks:
  - id: task-a
    title: "Implement core entity types"
    description: "Create Entity, EntityID, and associated traits"
    depends_on: []
    success_criteria:
      - "test_entity_construction: verifies Entity creation"
      - "test_entity_id_parsing: validates UUID parsing"
      - "cargo clippy: 0 warnings"
    
  - id: task-b
    title: "Build persistence layer"
    description: "Implement EntityRepository with SQLx"
    depends_on: [task-a]
    success_criteria:
      - "test_create_entity: INSERT verified"
      - "test_query_entity: SELECT working"
      - "test_update_entity: UPDATE correct"
    
  - id: task-c
    title: "Axum HTTP routes"
    description: "REST API for entity CRUD"
    depends_on: [task-b]
    success_criteria:
      - "test_get_entity_200: happy path"
      - "test_post_entity_400: validation"
    
  - id: task-d
    title: "Integration tests"
    description: "Full E2E test suite"
    depends_on: [task-a, task-b, task-c]
    success_criteria:
      - "test_e2e_create_read_update: full cycle"
      - "cargo test --all: all green"
    
  - id: task-e
    title: "Documentation"
    description: "API docs + architecture diagram"
    depends_on: [task-c, task-d]
    success_criteria:
      - "docs/API.md: complete"
      - "docs/ARCHITECTURE.md: complete"
```

---

## 6. RISK ASSESSMENT & MITIGATION

### Risk 1: Git Merge Conflicts
**Severity:** HIGH  
**Cause:** Workers modify overlapping files (e.g., both touch src/lib.rs)  
**Mitigation:**
- Manifest specifies file ownership per task (task-a owns src/models.rs)
- Pre-merge conflict detection (dry-run git merge)
- If conflict detected: abort merge, revert worker assignment, alert dispatcher
- Retry mechanism: worker redoes task in clean worktree

### Risk 2: Deadlocks in Task Dependencies
**Severity:** MEDIUM  
**Cause:** Circular dependency (task-a depends on task-b, task-b depends on task-a)  
**Mitigation:**
- Manifest validator checks for cycles (topological sort fails if cycle exists)
- Dispatcher rejects cyclic manifests before spawning workers
- Error message: "Circular dependency detected: task-a → task-b → task-a"

### Risk 3: Worker Agent Timeout/Hang
**Severity:** MEDIUM  
**Cause:** Worker gets stuck (test hangs, deployment stalls)  
**Mitigation:**
- Set timeout per task (manifest: `timeout_minutes: 30`)
- Dispatcher monitors task runtime via SSE heartbeat
- If no progress for 5 minutes: dispatcher sends timeout signal
- Worker receives signal, cleans up worktree, exits
- Task marked as failed, dependent tasks blocked

### Risk 4: Race Condition in Merge Orchestration
**Severity:** HIGH  
**Cause:** Two workers both try to merge simultaneously  
**Mitigation:**
- Merge orchestrator is single-threaded (sequential, not parallel)
- Only ONE task can merge at a time
- Queue ensures FIFO order within dependency constraints
- Atomic git push (fail if remote changed, retry)

### Risk 5: Insufficient Disk Space for Worktrees
**Severity:** LOW  
**Cause:** 5 worktrees = 5× codebase copy (500MB × 5 = 2.5GB)  
**Mitigation:**
- Check disk space before spawning workers
- Warn if <5GB free
- Clean up worktrees immediately after merge (no stale directories)

### Risk 6: SSE Connection Dropout
**Severity:** LOW  
**Cause:** Network hiccup, worker loses connection to queue  
**Mitigation:**
- Worker has local heartbeat (every 5 sec: "still running")
- Dispatcher waits for heartbeat timeout (30 sec) before marking task failed
- Worker auto-reconnects with exponential backoff
- Event log persisted (worker can recover state from disk)

### Risk 7: Partial Merge Success
**Severity:** MEDIUM  
**Cause:** Push to origin succeeds, but task status update fails  
**Mitigation:**
- Merge is atomic: merge locally, validate tests pass, then push
- If push fails: git revert locally, retry
- If status update fails: queue has eventual consistency (re-poll until consistent)
- Idempotent merge (if already merged, no-op)

---

## 7. EXECUTION CHECKLIST

### Pre-Launch
- [ ] Manifest format validated (no cycles, all deps resolvable)
- [ ] All workers available (check max agent sessions)
- [ ] Disk space >5GB free
- [ ] Git repo in clean state (no uncommitted changes on main)
- [ ] Backup main branch: git branch backup-phase-30-main

### During Execution
- [ ] Monitor SSE broadcast (worker status updates flowing)
- [ ] Check merge order matches dependency DAG
- [ ] Verify 0 git merge conflicts
- [ ] Track wall-clock time (target <30 min)
- [ ] Log all events to .phase30/events.log

### Post-Execution
- [ ] All worktrees cleaned up
- [ ] All tasks marked completed or failed
- [ ] Final `git log main` shows all commits in correct order
- [ ] Full test suite passes: `cargo test --all`
- [ ] Metrics captured: total_time, workers_used, conflicts_detected

---

## 8. METRICS & MONITORING

**Dispatcher tracks:**
```json
{
  "orchestration_id": "orch-2026-05-20-001",
  "start_time": "2026-05-20T14:00:00Z",
  "end_time": "2026-05-20T14:25:30Z",
  "total_duration_minutes": 25.5,
  "workers_spawned": 5,
  "tasks_submitted": 5,
  "tasks_completed": 5,
  "tasks_failed": 0,
  "merge_conflicts_detected": 0,
  "merge_conflicts_resolved": 0,
  "git_push_errors": 0,
  "worktrees_created": 5,
  "worktrees_cleaned": 5,
  "per_task_metrics": {
    "task-a": {
      "assigned_to": "worker-1",
      "start_time": "2026-05-20T14:00:15Z",
      "end_time": "2026-05-20T14:05:30Z",
      "duration_minutes": 5.25,
      "merge_time_seconds": 2,
      "status": "merged"
    },
    ...
  },
  "success": true
}
```

**Output:** `.phase30/metrics.json` (saved after completion)

---

## 9. CONSTRAINTS & NON-NEGOTIABLES

1. **Isolation:** Each worker operates in its own worktree; no cross-contamination
2. **Atomicity:** Merge is all-or-nothing (no partial commits to main)
3. **Ordering:** Dependent tasks CANNOT merge before dependencies
4. **Cleanup:** All worktrees must be deleted after merge or failure
5. **Idempotency:** Running same orchestration twice produces same result
6. **Fail-closed:** If any task fails, orchestration halts (configurable retry/skip)
7. **Git integrity:** Zero force pushes, zero rebase (only merge commits)

---

## 10. ACCEPTANCE TESTS

### Test 1: 5 Independent Tasks (No Dependencies)
**Manifest:** tasks.yaml with 5 unrelated tasks  
**Expected:**
- All 5 workers spawn simultaneously
- All 5 complete in parallel (wall time ≈ max(task_time))
- 5 commits merged to main in any order
- Zero conflicts

### Test 2: Linear Dependency Chain
**Manifest:** task-a → task-b → task-c → task-d → task-e  
**Expected:**
- Worker-1 starts task-a
- Worker-2 blocked (waiting for task-a)
- After task-a merges: Worker-2 starts task-b
- Merge order: a, b, c, d, e (strictly sequential)
- Total time ≈ sum(task_times), not parallel

### Test 3: Diamond Dependency
**Manifest:**
```
task-a
├─ task-b
│  └─ task-d
└─ task-c
   └─ task-d
```
**Expected:**
- task-a runs alone
- task-b and task-c run in parallel (after task-a merges)
- task-d blocked until both task-b AND task-c merge
- Total time ≈ a + max(b, c) + d

### Test 4: Failure & Rollback
**Manifest:** 5 independent tasks, task-c fails intentionally  
**Expected:**
- Workers 1, 2, 4, 5 complete normally
- Worker 3 reports: "test assertion failed"
- task-c marked as failed
- Worktree cleaned up
- Dispatcher halts (waiting for retry signal)
- User retries: task-c runs on new worker-3
- Final: 5 tasks merged + 1 retry noted in logs

### Test 5: Merge Conflict Detection
**Manifest:** task-a and task-b both modify src/lib.rs  
**Expected:**
- Both workers start
- Merge orchestrator detects conflict in dry-run
- Merge aborted before changing main
- Error logged: "Conflict in src/lib.rs"
- Worktrees preserved for manual debugging

---

## 11. DEPLOYMENT & LAUNCH

**To run orchestration:**

```bash
# 1. Create manifest
cat > tasks.yaml <<EOF
version: "1.0"
orchestration:
  worker_count: 5
  timeout_minutes: 30

tasks:
  - id: task-a
    title: "..."
    depends_on: []
    success_criteria: [...]
  # ... more tasks
EOF

# 2. Launch dispatcher
claude-code /orchestrate --manifest=tasks.yaml --workers=5 --output=.phase30/

# 3. Monitor live
tail -f .phase30/orchestration_report.md

# 4. On completion
cat .phase30/metrics.json
git log --oneline main | head -10
```

---

## 12. HANDOFF & NEXT PHASES

**Phase 30 → Phase 31 dependencies:**
- Distributed task scheduler (queue-based, not in-memory)
- Persistent worktree registry (SQLite)
- Web dashboard for orchestration monitoring
- Retry policies (exponential backoff, max retries)
- Cost tracking (how long each task took, compute budget)

**Files eligible for Phase 31 refactor:**
- Replace in-memory queue with Redis
- Persist events to PostgreSQL (siss-graph-db integration)
- Add authentication for worker agents
- Add task templating system (reusable manifests)

---

## 13. QUICK REFERENCE

| Component | Responsibility | Crate |
|-----------|----------------|-------|
| Dispatcher | Spawn workers, orchestrate merges, monitor | .claude/skills/orchestration |
| Task Queue | Store/track task state, dependency resolution | siss-orchestration |
| Merge Orchestrator | Git merge logic, conflict detection | siss-orchestration |
| Worker Agent | Execute task, report progress, commit locally | .claude/skills/orchestration |
| SSE Broadcast | Real-time event stream to all consumers | siss-orchestration |

---

**Prepared by:** Claude Haiku 4.5  
**For:** Fresh dispatcher + worker agents (Phase 30 implementation)  
**Status:** READY — Agents can start immediately on Day 1.
