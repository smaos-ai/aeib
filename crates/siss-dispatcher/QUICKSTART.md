# Quick Start: siss-dispatcher

## Installation

```bash
cd /path/to/SovereignNexus
cargo build -p siss-dispatcher --release
```

Binary: `./target/release/siss-dispatcher`

## Basic Usage

### 1. Create agents (run once)
```bash
dispatcher spawn 5
# Spawned 5 agents:
#   Agent 0 [uuid]: idle
#   Agent 1 [uuid]: idle
#   Agent 2 [uuid]: idle
#   Agent 3 [uuid]: idle
#   Agent 4 [uuid]: idle
```

### 2. Queue tasks
```bash
# Task 1: Independent feature
dispatcher queue-add '{
  "name": "feature-auth",
  "description": "Implement authentication"
}'

# Task 2: Depends on task 1 (get the UUID from task 1)
TASK1_ID="<uuid-from-step-2>"
dispatcher queue-add '{
  "name": "feature-dashboard",
  "description": "Build dashboard with auth",
  "dependencies": [{
    "task_id": "'$TASK1_ID'",
    "dep_type": "blocked_by"
  }]
}'
```

### 3. Monitor status
```bash
dispatcher status
# Queue Status:
#   Pending: 1
#   In Progress: 1
#   Completed: 0
#
# Agent Status:
#   Agent 0 [uuid]: task_in_progress
#     Assigned task: <uuid>
#     Worktree: ./.claude/worktrees/agent-0-task-<uuid>
#   Agent 1 [uuid]: idle
```

### 4. Run dispatch loop
```bash
dispatcher run
# Starting dispatch loop...
# (assigns tasks, polls agents, merges on completion)
# Dispatch complete
```

### 5. Check merge results
```bash
dispatcher merge
# Merge Results:
#   Task <uuid>: SUCCESS
#   Task <uuid>: FAILED
#     Conflicts: ["src/auth.rs", "src/config.rs"]
```

### 6. Cleanup
```bash
dispatcher cleanup
# Cleanup complete
```

## Example: Parallel feature development

### Scenario: 3 features, 2 dependencies
```
Feature A (independent)
Feature B (depends on A)
Feature C (depends on A, B)
```

### Commands
```bash
# Setup
dispatcher spawn 5

# Queue independent feature A
TASK_A=$(dispatcher queue-add '{
  "name": "feature-a"
}' | grep -o '[a-f0-9\-]*$')

# Queue feature B (blocked by A)
TASK_B=$(dispatcher queue-add '{
  "name": "feature-b",
  "dependencies": [{
    "task_id": "'$TASK_A'",
    "dep_type": "blocked_by"
  }]
}' | grep -o '[a-f0-9\-]*$')

# Queue feature C (blocked by A and B)
dispatcher queue-add '{
  "name": "feature-c",
  "dependencies": [
    {"task_id": "'$TASK_A'", "dep_type": "blocked_by"},
    {"task_id": "'$TASK_B'", "dep_type": "blocked_by"}
  ]
}'

# Execute
dispatcher run

# View results
dispatcher status
dispatcher merge
```

## Configuration

Create `.dispatcher/config.json`:
```json
{
  "max_agents": 5,
  "repo_path": ".",
  "worktree_base": "./.claude/worktrees",
  "queue_file": "./.dispatcher/queue.json",
  "agents_file": "./.dispatcher/agents.json",
  "lock_timeout_secs": 30,
  "task_timeout_secs": 3600
}
```

Then use:
```bash
dispatcher --config .dispatcher/config.json status
```

## Troubleshooting

### Agents stuck in "WorktreeInitializing"
Worktree creation failed. Check:
- Git is installed
- Repository is clean (no uncommitted changes)
- Disk space available

### Lock timeout errors
Multiple processes accessing queue. Check:
- Only one dispatcher instance running
- Previous run cleaned up properly (`dispatcher cleanup`)
- No stale `.dispatcher/queue.json.lock` files

### Merge conflicts detected
When `dispatcher merge` shows conflicts:
1. Manually resolve in affected files
2. Stage changes: `git add <files>`
3. Complete merge: `git merge --continue`
4. Re-run dispatcher merge

### Task never completes
Check:
- Task execution logic (currently placeholder `true`)
- Agent logs in `.dispatcher/agent-<idx>-task-<id>/`
- Task specification in `.dispatcher/task.json`

## Key Files & Directories

After dispatch:
```
.dispatcher/
├── config.json              # Configuration
├── queue.json               # Task queue (persistent)
├── queue.json.lock          # Lock file (auto-cleanup)
└── agents.json              # Agent state (TODO)

.claude/worktrees/
├── agent-0-task-<uuid>/    # Agent 0's worktree
│   ├── .git/
│   ├── .dispatcher/
│   │   └── task.json       # Task specification
│   └── <modified files>    # Task output
├── agent-1-task-<uuid>/
└── ...
```

## Performance Tips

1. **Increase max_agents** for high-parallelism tasks
   ```json
   "max_agents": 10
   ```

2. **Check dependency graph** before running
   Circular dependencies are rejected immediately

3. **Monitor agent status** during execution
   ```bash
   while true; do dispatcher status; sleep 5; done
   ```

4. **Cleanup on error**
   ```bash
   dispatcher cleanup  # Always safe - removes worktrees
   ```

## Next: Implement Task Logic

Currently, task execution is a placeholder. To implement:

1. Create agent task handler in `src/agent.rs` (line ~95)
2. Read task spec from `.dispatcher/task.json`
3. Execute task logic (compile, test, deploy, etc.)
4. Write results back to worktree
5. Set agent status to TaskCompleted

Example:
```rust
// In AgentExecutor::execute_task()
let task_spec = fs::read_to_string(worktree/.dispatcher/task.json).await?;
let task: Task = serde_json::from_str(&task_spec)?;

match task.specification.get("command") {
    Some(cmd) => {
        let output = Command::new("bash")
            .arg("-c")
            .arg(cmd.as_str()?)
            .current_dir(worktree_path)
            .output()
            .await?;
        
        if !output.status.success() {
            self.agent.status = AgentStatus::Failed;
            return Err(...);
        }
    }
    None => { /* handle default */ }
}

self.agent.status = AgentStatus::TaskCompleted;
```

## For More Details

- **Architecture**: See `README.md`
- **Implementation details**: See `IMPLEMENTATION.md`
- **Source code**: `src/` directory
- **Tests**: `cargo test -p siss-dispatcher --lib`
