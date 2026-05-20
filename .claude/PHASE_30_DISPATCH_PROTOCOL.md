# Phase 30: Dispatch Protocol Quick Reference

**Purpose:** Stateless polling interface between orchestrator and up to 5 worktree agents.

---

## 1. AGENT INITIALIZATION (one-time)

**Agent spawns with:**
```bash
# Agent1 in worktree /path/to/agent1
cd /path/to/agent1
export ORCHESTRATOR_URL="http://localhost:9999"
export AGENT_ID="Agent1"
./agent-poll.sh
```

**Agent polls every 30 seconds:**
```bash
curl -X POST $ORCHESTRATOR_URL/dispatch/fetch_task \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "Agent1",
    "version": "phase-30-v1",
    "status_report": {
      "current_task_id": null,
      "git_worktree": "/path/to/agent1",
      "last_heartbeat_at": "2026-05-20T19:05:00Z"
    }
  }'
```

---

## 2. FETCH_TASK RESPONSE CASES

### Case A: Task Assigned (200 OK)
Agent receives task with full metadata and starts work:
```json
{
  "task": {
    "id": "task-001",
    "name": "Phase 30 Feature 1: Dispatcher Core",
    "description": "...",
    "priority": 1,
    "dependencies": [],
    "blocks": ["task-004", "task-005"],
    "worktree_branch": "feature/dispatcher-core",
    "files_touched": [
      "crates/siss-dispatcher/src/dispatcher.rs",
      "crates/siss-dispatcher/src/queue.rs"
    ]
  },
  "checkpoint": {
    "commit_sha": "abc123def456",
    "timestamp": "2026-05-20T19:05:30Z"
  }
}
```

**Agent action:**
```bash
git fetch origin
git checkout feature/dispatcher-core
git rebase origin/main  # Ensure fresh
# ... write code, test, commit ...
```

### Case B: No Tasks Available (202 Accepted)
Agent waits or picks up test/doc work:
```json
{
  "message": "No available tasks. Waiting on: task-002 (pending), task-003 (pending)",
  "estimated_wait_seconds": 300,
  "suggested_action": "POLL_AGAIN_IN_300_SECONDS"
}
```

**Agent action:**
```bash
sleep 300
curl -X POST $ORCHESTRATOR_URL/dispatch/fetch_task ...
```

### Case C: Agent Reassigned (410 Gone)
Task was cancelled or reassigned during timeout:
```json
{
  "reason": "Task reassigned to Agent3 due to agent timeout (>600s no heartbeat)",
  "action": "ABORT_LOCAL_CHANGES"
}
```

**Agent action:**
```bash
git checkout main
git reset --hard origin/main
# Restart polling for new task
```

---

## 3. PROGRESS REPORTING (every 5 minutes during work)

**Agent sends heartbeat + status:**
```bash
curl -X POST $ORCHESTRATOR_URL/dispatch/progress \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "Agent1",
    "task_id": "task-001",
    "status": "in_progress",
    "checkpoint": {
      "commit_sha": "abc123...",
      "files_staged": 3,
      "tests_passing": 18,
      "tests_failing": 0,
      "lines_of_code": 342
    },
    "eta_seconds": 1800
  }'
```

**Orchestrator response:**
```json
{
  "ack": true,
  "heartbeat_interval_seconds": 300,
  "orchestrator_status": "running"
}
```

**If no heartbeat > 600 seconds:**
- Orchestrator reassigns task to another agent
- Original agent receives 410 GONE on next poll
- Agent stops work on that task

---

## 4. TASK COMPLETION (when tests pass + linter clean)

**Agent signals done:**
```bash
curl -X POST $ORCHESTRATOR_URL/dispatch/complete_task \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "Agent1",
    "task_id": "task-001",
    "status": "completed",
    "result": {
      "tests_passed": 18,
      "linter_clean": true,
      "lines_of_code": 342,
      "commit_sha": "def456ghi789",
      "branch": "feature/dispatcher-core"
    },
    "git_push_url": "origin feature/dispatcher-core"
  }'
```

### Case A: Completion Accepted (200 OK)
```json
{
  "acknowledged": true,
  "next_task_available_in_seconds": 120,
  "merge_order": 1,
  "merge_priority": "IMMEDIATE"
}
```

**Agent action:**
```bash
git push origin feature/dispatcher-core
sleep 120
# Poll for next task
```

### Case B: Tests Failing (422 Unprocessable Entity)
```json
{
  "reason": "Task completion rejected: 2 tests failing",
  "tests_failing": [
    "test_dispatcher_timeout",
    "test_queue_underflow"
  ],
  "action": "RERUN_FAILED_TESTS"
}
```

**Agent action:**
```bash
cargo test
# Fix failures, commit, re-signal completion
```

---

## 5. DISPATCH STATE MACHINE (Orchestrator perspective)

```
Pending
  ↓
  (dependencies satisfied? yes → assign to available agent)
  ↓
Assigned
  ↓
  (agent sends /progress heartbeat? yes → next poll)
  ↓
InProgress
  ↓
  (agent sends /complete_task? yes → verify tests)
  ↓
Completed (tests pass)
  ↓
  (schedule for merge in topological order)
  ↓
Merged
  ↓
  (agent freed to fetch next task)

TIMEOUT branch:
  InProgress → (600s no heartbeat) → Reassign to another agent
```

---

## 6. MERGE EXECUTION (Orchestrator, after all tasks completed)

**Orchestrator generates merge plan:**
```json
{
  "merge_order": [
    {
      "rank": 1,
      "task_id": "task-001",
      "branch": "feature/dispatcher-core",
      "merge_base": "main"
    },
    {
      "rank": 2,
      "task_id": "task-002",
      "branch": "feature/task-pool",
      "merge_base": "main"
    },
    ...
  ]
}
```

**For each step in merge_order (sequentially on main):**

```bash
# Step 1: Merge task-001
git checkout main
git pull origin main
git merge --no-ff feature/dispatcher-core

# Detect conflicts
if [ $? -ne 0 ]; then
  # Conflict detected → rollback
  git merge --abort
  
  # Notify agent
  curl -X POST $ORCHESTRATOR_URL/dispatch/conflict_detected \
    -d '{"task_id": "task-001", "branch": "feature/dispatcher-core"}'
  
  # Agent rebases locally
  # Agent force-pushes branch
  # Retry merge
else
  cargo test
  cargo clippy
  
  # If all pass: commit
  git push origin main
  
  # Move to Step 2
fi
```

---

## 7. DEPENDENCY RESOLUTION (prevents circular waits)

**At queue creation, validate:**
```bash
./validate-dependencies.sh phase-30-queue.json

# Checks:
# 1. No cycles in dependency graph
# 2. Topological sort succeeds (Kahn's algorithm)
# 3. File ownership non-overlapping
# 4. All merge_order values unique
```

**Example: Task A depends on Task B**
```
Queue says: task-001.dependencies = ["task-002"]
            task-002.blocks = ["task-001"]

Orchestrator logic:
  - task-001 status = Pending
  - task-002 status = Pending
  - Agent asks for task → gets task-002 (no dependencies)
  - task-002 completes → orchestrator marks task-002.status = Merged
  - task-001 dependency list updated: task-001.dependencies.remove("task-002")
  - Agent asks for task → gets task-001 (dependencies now empty)
  - task-001 completes → orchestrator queues task-001 for merge
```

---

## 8. CONFLICT PREVENTION CHECKLIST

Before dispatch starts, orchestrator verifies:

```
[✓] All task files_touched are non-overlapping
    task-001: crates/siss-dispatcher/src/dispatcher.rs ✓
    task-002: crates/siss-dispatcher/src/pool.rs ✓
    (no duplicates)

[✓] Dependency graph is acyclic
    run topological_sort() → succeeds

[✓] Merge order is deterministic
    merge_order values = [1, 2, 3, 4, 5, 6] (sequential)

[✓] Each task has at most 2 blockers
    task-001 blocks 2 tasks ✓
    (prevents exponential fanout)

[✓] Critical path ≤ available_agents × parallelizable_tasks
    critical_path_days = 3.5
    parallelizable_tasks = 5
    3.5 / 5 = 0.7 days per agent ✓
```

---

## 9. FAULT TOLERANCE

| Scenario | Recovery |
|----------|----------|
| **Agent crashes mid-task** | Orchestrator detects missing heartbeat (600s) → reassigns to Agent2 |
| **Merge conflict detected** | Rollback merge, notify agent, agent rebases locally, retry |
| **Agent reports failed tests** | Reject completion, ask agent to fix tests |
| **Orchestrator crash** | Queue state persisted in queue.json → restart from checkpoint |
| **Network timeout** | Agent retries /fetch_task on 5-second loop |

---

## 10. SUMMARY TABLE

| Endpoint | Method | Agent Role | Orchestrator Role |
|----------|--------|------------|-------------------|
| `/fetch_task` | POST | Poll for next task | Assign based on dependencies |
| `/progress` | POST | Send heartbeat + status | Detect timeouts, track progress |
| `/complete_task` | POST | Signal done + test results | Verify, queue for merge |
| `/conflict_detected` | POST | Notify rebase needed | Trigger conflict resolution |

**Polling cadence:**
- Fetch task: every 30 seconds (on idle)
- Progress heartbeat: every 5 minutes (during work)
- Merge check: every 10 seconds (after all tasks completed)

