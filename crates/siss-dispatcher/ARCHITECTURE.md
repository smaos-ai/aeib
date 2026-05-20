# siss-dispatcher: Architecture & Design

## System Overview

```
┌───────────────────────────────────────────────────────────┐
│                  CLI Interface                             │
│  dispatcher spawn|queue-add|status|merge|run|cleanup      │
└─────────────────┬─────────────────────────────────────────┘
                  │
┌─────────────────▼─────────────────────────────────────────┐
│              Main Executor                                 │
│  - spawn_agents(N)          [creates N agents]            │
│  - assign_next_task()       [round-robin dispatch]        │
│  - poll_agents()            [check completion]            │
│  - merge_completed_tasks()  [orchestrate merge]           │
│  - run_loop()               [main dispatch loop]          │
└────┬────────────────────────────────────────────────────┬─┘
     │                                                      │
     ▼                                                      ▼
┌──────────────────────────┐                    ┌──────────────────────┐
│   Task Queue             │                    │   Git Manager        │
│  - VecDeque<Task>        │                    │  - create_worktree() │
│  - HashMap<Id, idx>      │                    │  - remove_worktree() │
│  - Circular dep detect   │                    │  - get_modified()    │
│  - Dependency checking   │                    │  - merge_branch()    │
│  - File persistence      │                    │  - commit_changes()  │
│    (queue.json)          │                    │  - abort_merge()     │
└──────────────────────────┘                    └──────────────────────┘
         │                                              │
         ▼                                              ▼
┌──────────────────────────┐      ┌──────────────────────────────┐
│   File Lock              │      │    Agent Executor (x5)       │
│  - Atomic acquire        │      │  - Agent state machine       │
│  - Timeout support       │      │  - Worktree lifecycle        │
│  - create_new() syscall  │      │  - Task execution            │
│  - 100ms retry loop      │      │  - Completion polling        │
└──────────────────────────┘      │  - Change extraction         │
                                  │  - Cleanup                   │
                                  └──────────────────────────────┘
                                             │
                                             ▼
                                  ┌──────────────────────────┐
                                  │  Git Worktree            │
                                  │  .claude/worktrees/      │
                                  │  └─ agent-0-task-uuid/  │
                                  │  └─ agent-1-task-uuid/  │
                                  │  └─ ...                 │
                                  └──────────────────────────┘
```

## Component Responsibility Matrix

| Component | Responsibility | Key Methods |
|-----------|-----------------|------------|
| **Executor** | Central dispatcher, orchestration | spawn_agents, assign_next_task, poll_agents, run_loop |
| **Queue** | Task persistence & dependency mgmt | enqueue, next_unassigned, check_circular_deps |
| **Agent** | Worktree lifecycle & execution | initialize_worktree, execute_task, prepare_merge, cleanup |
| **Git** | Git operations wrapper | create_worktree, merge_branch, commit_changes |
| **Lock** | Distributed coordination | acquire, release |
| **Config** | Configuration mgmt | load_config, save_config |

## Data Flow

### Task Assignment Flow
```
1. Executor.assign_next_task()
   ├─ Find idle agent
   ├─ Find next unassigned task with met dependencies
   ├─ Agent.initialize_worktree(task)
   │  └─ Git.create_worktree()
   ├─ Agent.write_task_specification()
   ├─ Agent.execute_task()
   └─ Queue.update_status(task, Assigned)
       └─ Queue.save() [lock-protected]

2. Executor.poll_agents()
   ├─ Agent.check_completion()
   ├─ [if complete] finalize_tasks()
   │  └─ Agent.prepare_merge()
   │     ├─ Git.commit_changes()
   │     └─ Queue.update_status(task, Completed)
   └─ [if failed] mark task as Failed

3. Executor.merge_completed_tasks()
   ├─ Get all Completed tasks
   ├─ For each task:
   │  ├─ Git.check_merge_conflicts()
   │  ├─ [if no conflicts] Git.merge_branch()
   │  └─ [if conflicts] Flag for manual resolution
   └─ Return merge results
```

### Dependency Checking Flow
```
Queue.next_unassigned()
├─ For each Pending task:
│  ├─ For each dependency:
│  │  ├─ Look up dependency task
│  │  ├─ Check status == Completed
│  │  └─ [if not] skip task
│  └─ [if all deps met] return task
└─ [if none found] return None
```

### Lock Coordination Flow
```
Queue.load()
├─ Lock.acquire(.dispatcher/queue.json.lock, 30s)
│  ├─ Check file exists [if yes, wait]
│  ├─ Try create_new() [atomic]
│  └─ [if timeout] return LockTimeout
├─ fs::read_to_string(queue.json)
├─ Parse JSON
└─ Lock.release()

Queue.save()
├─ Lock.acquire()
├─ Create .dispatcher directory
├─ fs::write(queue.json)
└─ Lock.release()
```

## State Machines

### Agent Status Machine
```
Idle
  ↓ [initialize_worktree]
WorktreeInitializing
  ├─ [create_worktree] → TaskInProgress
  └─ [error] → Failed

TaskInProgress
  ├─ [execute_task success] → TaskCompleted
  └─ [error] → Failed

TaskCompleted
  ├─ [prepare_merge] → MergingChanges
  └─ [error] → Failed

MergingChanges
  ├─ [merge success] → Cleanup
  └─ [merge error] → Failed

Cleanup
  └─ [remove_worktree] → Idle

Failed
  └─ [cleanup] → Idle
```

### Task Status Machine
```
Pending
  ├─ [assigned to agent] → Assigned
  └─ [dependency unmet] → wait

Assigned
  ├─ [agent starts] → InProgress
  └─ [timeout] → Failed

InProgress
  ├─ [agent completes] → Completed
  └─ [agent fails] → Failed

Completed
  ├─ [merged] → [finalized]
  └─ [conflict] → [manual resolution]

Failed
  └─ [retry] → Pending
```

## Concurrency Safety

### Shared State Protection
```
Task Queue (VecDeque + HashMap)
├─ In-memory index (HashMap<Id, idx>)
│  └─ Fast O(1) lookups
├─ Persistent JSON (queue.json)
│  └─ Lock-protected save/load
└─ File lock (.dispatcher/queue.json.lock)
   └─ Atomic create_new() syscall

Agent State (HashMap<Uuid, AgentExecutor>)
├─ In-memory only
├─ Single-threaded access
└─ No lock needed (main loop sequential)
```

### Lock Safety
```
FileLock::acquire(path, timeout)
├─ Check path.exists() [non-blocking]
├─ If exists, sleep 100ms and retry
├─ If timeout > elapsed, return LockTimeout
├─ Try OpenOptions::new().create_new(true)
│  └─ [atomic] Only one process succeeds
└─ Return Self { path }

FileLock::release()
└─ fs::remove_file(path)
```

## Configuration

```rust
pub struct ExecutorConfig {
    pub max_agents: u32,              // 5
    pub repo_path: String,            // "."
    pub worktree_base: String,        // "./.claude/worktrees"
    pub queue_file: String,           // "./.dispatcher/queue.json"
    pub agents_file: String,          // "./.dispatcher/agents.json" (TODO)
    pub lock_timeout_secs: u64,       // 30
    pub task_timeout_secs: u64,       // 3600 (TODO: enforce)
}
```

## Task Specification Schema

```json
{
  "id": "uuid-v4",
  "name": "string",
  "description": "optional string",
  "specification": {
    "custom": "fields vary by task type"
  },
  "status": "pending|assigned|in_progress|completed|failed|rolled_back",
  "assigned_to": "uuid-v4 or null",
  "retry_count": 0,
  "created_at": "2026-05-20T...",
  "started_at": "2026-05-20T... or null",
  "completed_at": "2026-05-20T... or null",
  "dependencies": [
    {
      "task_id": "uuid-v4",
      "dep_type": "blocked_by|blocks"
    }
  ]
}
```

## Error Handling Strategy

### Task-Level Errors
- **AssignmentFailed**: Agent unavailable, try next loop
- **WorktreeError**: Retry initialization up to 3x
- **UnmetDependencies**: Skip task, try next loop
- **TaskTimeout**: Mark failed, retry (TODO)

### Merge-Level Errors
- **MergeConflict**: Flag for manual resolution
- **MergeFailed**: Abort merge, mark task failed
- **RollbackFailed**: Log error, manual intervention

### System-Level Errors
- **LockTimeout**: Retry with exponential backoff
- **NoAvailableAgents**: Wait for agent to become idle
- **CircularDependency**: Reject task immediately

## Performance Analysis

### Time Complexity
| Operation | Complexity | Notes |
|-----------|-----------|-------|
| Agent spawn | O(1) | Create struct, insert into HashMap |
| Task enqueue | O(1) | Push to VecDeque, update HashMap |
| Next task | O(N) | Linear search through all tasks |
| Task assignment | O(A) | Find idle agent in HashMap |
| Agent polling | O(A) | Check each agent's status |
| Lock acquire | O(timeout/retry) | Wait loop at 100ms intervals |

### Space Complexity
| Structure | Space | Notes |
|-----------|-------|-------|
| Agents | O(A) | HashMap with A agents |
| Tasks | O(T) | VecDeque with T tasks |
| Lock file | O(1) | Single "locked" string |
| Worktree | O(W) | Git repo clone size |

### Bottlenecks
1. **Next task** - O(N) linear search (could optimize with index)
2. **Lock contention** - 100ms retry loop (could use condition variables)
3. **Worktree creation** - Git subprocess (slow for large repos)
4. **Merge orchestration** - Sequential (could parallelize safe merges)

## Testing Strategy

### Unit Tests (11 tests)
- Lock: acquire, release, conflict, timeout
- Queue: enqueue, circular dependency, next task
- Executor: spawn, status, queue operations
- Agent: creation, unique IDs
- Git: initialization
- Config: defaults

### Integration Tests (TODO)
- Multi-agent dispatch flow
- Task dependency enforcement
- Merge with conflicts
- Rollback scenario
- Stale lock cleanup

### Load Tests (TODO)
- 5 agents × 100 tasks
- Throughput measurement
- Memory profiling
- Lock contention measurement

## Deployment Considerations

### Single Machine
- ✓ Works on single machine (5 concurrent agents)
- ✓ File-based locking sufficient
- ✓ No network required

### Multiple Machines (Future)
- Need: Distributed lock service (etcd, Consul)
- Need: Central state store (shared filesystem or DB)
- Need: Agent discovery (DNS or registry)

### Production Hardening (TODO)
- [ ] Structured logging (tracing)
- [ ] Metrics collection (prometheus)
- [ ] Health checks per agent
- [ ] Graceful shutdown
- [ ] Recovery from crash
- [ ] Config reloading

## Extensibility Points

1. **Task Execution**: Replace placeholder in agent.rs
2. **Merge Strategy**: Customize merge_completed_tasks()
3. **Conflict Resolution**: Add interactive flow
4. **Lock Implementation**: Swap for distributed lock
5. **State Persistence**: Add agents.json support
6. **Metrics**: Add prometheus counters/histograms

## Design Principles

1. **Simplicity**: ~1600 LOC, no async overhead except tokio
2. **Isolation**: Independent worktrees prevent interference
3. **Persistence**: JSON queue survives process restart
4. **Atomicity**: OS-level locks (create_new syscall)
5. **Safety**: Circular dependency detection upfront
6. **Clarity**: Clear state machines, explicit status tracking
