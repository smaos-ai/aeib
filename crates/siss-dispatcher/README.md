# siss-dispatcher: Multi-Worktree Execution Framework

A concurrent task dispatcher that manages parallel agent execution using isolated git worktrees. Supports task dependencies, automatic conflict detection, and distributed coordination via file-based locking.

## Architecture Overview

```
┌─────────────────────────────────────────────────┐
│         Task Queue (persistent JSON)             │
│  - Pending, Assigned, InProgress, Completed     │
│  - Dependency tracking (BlockedBy/Blocks)       │
└────────────┬────────────────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────────────┐
│         Executor (Main Dispatcher)               │
│  - Agent spawn/polling                          │
│  - Task assignment (round-robin)                │
│  - Merge orchestration                          │
│  - State persistence                            │
└──────┬──────────────────────┬──────┬────────────┘
       │                      │      │
    ┌──┴──┐              ┌──┬─┴──┐  │
    │ Git │              │  V    │  │
    └──┬──┘              │ ... Agents (N)
       │                 │  Worktrees
       ▼                 │  + Task Execution
  Create/Remove          │
  Worktree              │
  Merge/Commit          └────────────┘
  Conflict Check
```

## Core Components

### 1. Task Queue (`queue.rs`)
- **In-memory VecDeque** with file persistence
- **Dependency tracking**: BlockedBy/Blocks relationships
- **Circular dependency detection**: DFS-based cycle detection
- **Lock-guarded save/load**: File-based locking for concurrent access
- **Next-task selection**: Returns only unassigned tasks with met dependencies

### 2. File-Based Locking (`lock.rs`)
- **Non-blocking atomic lock acquisition**: Uses `create_new()` for atomicity
- **Timeout support**: Respects configurable timeout durations
- **Automatic release**: Drop-based cleanup (TODO: async-aware)
- **Stale lock detection**: TODO - implement age-based cleanup

### 3. Agent Lifecycle Management (`agent.rs`)
- **AgentExecutor**: Manages one agent's worktree lifecycle
- **Status tracking**: Idle → WorktreeInit → TaskInProgress → MergingChanges → Cleanup
- **Worktree isolation**: Independent branch per agent (`agent-{idx}-task-{id}`)
- **Task specification**: Passed via `.dispatcher/task.json` in worktree
- **Change extraction**: Queries git for modified files

### 4. Git Operations (`git.rs`)
- **Worktree management**: Create/remove isolated worktrees
- **Merge coordination**: Merge branch into target with conflict detection
- **Conflict handling**: Checks before merge, aborts on failure
- **Change tracking**: Lists modified files after task execution
- **Commit orchestration**: Stages and commits worktree changes

### 5. Main Executor (`executor.rs`)
- **Agent spawning**: Creates up to `max_agents` (default 5) concurrent agents
- **Task assignment loop**: Assigns next unassigned task to idle agent
- **Agent polling**: Checks all agents for completion
- **Merge orchestration**: Topological sort (TODO) + conflict resolution
- **Cleanup coordination**: Removes worktrees when agents finish

## CLI Usage

### Spawn N agents
```bash
dispatcher spawn 5
# Output:
# Spawned 5 agents:
#   Agent 0 [uuid]: idle
#   Agent 1 [uuid]: idle
#   ...
```

### Queue a task
```bash
dispatcher queue-add '{"name": "feature-x", "description": "Implement feature X"}'
# Output: Added task [uuid] to queue
```

### Show status
```bash
dispatcher status
# Output:
# Queue Status:
#   Pending: 2
#   In Progress: 1
#   Completed: 3
#
# Agent Status:
#   Agent 0 [uuid]: idle
#   Agent 1 [uuid]: task_in_progress
```

### Orchestrate merge
```bash
dispatcher merge
# Topologically sorts tasks by dependencies, auto-merges when safe,
# flags conflicts for manual resolution
```

### Run dispatch loop
```bash
dispatcher run
# Continuously assigns tasks, polls for completion, and merges
# Exits when all tasks are completed
```

### Cleanup worktrees
```bash
dispatcher cleanup
# Removes all agent worktrees and resets agents to idle
```

## Task Specification

Tasks are represented as JSON:

```json
{
  "id": "uuid",
  "name": "task-name",
  "description": "optional description",
  "specification": {
    "custom_key": "custom_value"
  },
  "status": "pending",
  "assigned_to": null,
  "retry_count": 0,
  "dependencies": [
    {
      "task_id": "uuid-of-blocker",
      "dep_type": "blocked_by"
    }
  ]
}
```

## Task Dependencies

Two dependency types:
- **BlockedBy**: Task cannot start until dependency completes
- **Blocks**: Task must start before dependent task completes

Example:
```
Task A (no deps)
Task B (BlockedBy: A) 
Task C (BlockedBy: B)
```

Circular dependencies are detected on queue load and rejected.

## Concurrency Model

### File-Based Locking
- Queue file protected by `.dispatcher/queue.json.lock`
- Lock acquisition is **atomic** (uses `create_new()`)
- Timeout prevents indefinite blocking
- TODO: Implement stale lock detection

### Agent-Level Isolation
- Each agent gets independent git worktree
- Worktree isolation prevents merge conflicts between agents
- Agent state stored in-memory (fast polling)

### Merge Coordination (TODO)
- Topological sort of task DAG by dependency order
- Dry-run merge to detect conflicts before committing
- Auto-merge if no conflicts; flag conflicts for review

## Configuration

Default config (ExecutorConfig):
```rust
ExecutorConfig {
    max_agents: 5,                              // Up to 5 concurrent agents
    repo_path: ".",                             // Git repo root
    worktree_base: "./.claude/worktrees",       // Worktree parent
    queue_file: "./.dispatcher/queue.json",     // Queue persistence
    agents_file: "./.dispatcher/agents.json",   // Agents state (TODO)
    lock_timeout_secs: 30,                      // Lock acquisition timeout
    task_timeout_secs: 3600,                    // Task execution timeout (TODO)
}
```

## Implementation TODOs

### High Priority
- [ ] Topological sort for merge ordering (prevent dependency violations)
- [ ] Dry-run merge with conflict file extraction
- [ ] Task execution timeout enforcement
- [ ] Retry logic (3x retries on failure)
- [ ] Persistent agent state (agents.json)

### Medium Priority
- [ ] Stale lock detection and cleanup
- [ ] Async-aware drop for file locks
- [ ] Command execution in agent worktree (currently placeholder)
- [ ] Merge conflict resolution strategies
- [ ] Rollback on merge failure

### Low Priority
- [ ] Web UI for status monitoring
- [ ] Webhook notifications on task completion
- [ ] Performance metrics (throughput, latency)
- [ ] Support for >5 agents with process pooling

## Testing

All core modules have tests:

```bash
cargo test -p siss-dispatcher --lib
# Output: 11 passed (lock, queue, executor, agent, git, config)
```

Key test coverage:
- Lock acquire/release and timeout
- Queue enqueue/dequeue with dependencies
- Circular dependency detection
- Agent spawn/status
- Executor initialization and polling

## Example Workflow

```rust
// Create executor
let mut executor = Executor::new(config).await?;

// Spawn 5 agents
let agents = executor.spawn_agents(5).await?;

// Queue tasks
executor.queue_task(task1).await?;
executor.queue_task(task2).await?; // BlockedBy: task1

// Run dispatch loop until completion
executor.run_loop(None).await?;

// Merge results
let merge_results = executor.merge_completed_tasks().await?;
```

## Files Structure

```
crates/siss-dispatcher/
├── src/
│   ├── main.rs              # CLI dispatcher tool
│   ├── lib.rs               # Public API
│   ├── types.rs             # Core types (Task, Agent, etc.)
│   ├── errors.rs            # Error types
│   ├── config.rs            # Configuration loading
│   ├── queue.rs             # Task queue + persistence
│   ├── lock.rs              # File-based locking
│   ├── agent.rs             # Agent lifecycle
│   ├── git.rs               # Git operations
│   └── executor.rs          # Main dispatcher
├── Cargo.toml               # Dependencies
└── README.md                # This file
```

## Performance Characteristics

- **Agent spawn**: O(1) per agent
- **Task assignment**: O(N) where N = tasks (linear search for next unassigned)
- **Polling**: O(A) where A = active agents
- **Lock contention**: Low (30s timeout, 100ms retry loop)
- **Memory**: O(T + A) where T = tasks, A = agents

## Next Steps

1. Implement task execution engine (replace placeholder)
2. Add topological sort for merge ordering
3. Implement dry-run merge with conflict extraction
4. Add retry logic with backoff
5. Persist agent state to `.dispatcher/agents.json`
