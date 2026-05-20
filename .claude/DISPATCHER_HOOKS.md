# Dispatcher Hook Configuration — Phase 27

## Overview

This document describes the dispatcher orchestration hooks configured in `.claude/settings.json`. These hooks enable multi-agent dispatch with automatic task coordination, conflict detection, and state management.

## Quick Start

**Enable dispatcher:**
```bash
export DISPATCHER_ACTIVE=true
export AGENT_ID=agent-1
```

**Disable dispatcher:**
```bash
unset DISPATCHER_ACTIVE
unset AGENT_ID
```

The dispatcher is **disabled by default** (`"enabled": false` in settings.json). All hooks conditionally activate only when `DISPATCHER_ACTIVE=true`.

---

## Hook Execution Order

1. **PreToolUse hooks** (before tool execution)
   - `pre_tool_use_dispatcher_gate.js` — Checks dispatcher state, blocks conflicts
   - `pre_tool_use_gate.js` — Security gate (destructive commands, protected paths)
   - `pre_tool_use_verification_gate.sh` — Correctness gate

2. **Tool execution** (Bash, Write, Edit)

3. **PostToolUse hooks** (after tool execution)
   - `post_tool_use_logger.js` — Audit logging
   - `post_tool_use_dispatcher_report.js` — Progress tracking, task promotion

4. **Automatic merge check** (if all tasks complete)

---

## Hook Scripts

### 1. PreToolUse Dispatcher Gate (`pre_tool_use_dispatcher_gate.js`)

**Purpose:** Gate control — prevents conflicts during auto-dispatch.

**Checks:**
- ✓ If `merge_in_progress` is true, **block all writes** (exit code 2)
- ✓ If auto-dispatch running but no task assigned, **warn** (exit code 1)
- ✓ If file locked by another agent, **block write** (exit code 2)
- ✓ Otherwise, **allow** (exit code 0)

**Exit Codes:**
- `0` = Allowed
- `1` = Allowed with warning (dispatcher active but no task)
- `2` = Denied (merge conflict, file lock, merge in progress)

**Input:** `{ tool_name, tool_input }`

**Output:** `{ permissionDecision, reason?, warning?, advisory? }`

**State Files:**
- Reads: `.claude/dispatcher/dispatcher_state.json`
- Reads: `.claude/dispatcher/task_queue.json`

---

### 2. PostToolUse Dispatcher Report (`post_tool_use_dispatcher_report.js`)

**Purpose:** Report tool execution to dispatcher; track progress; promote next task.

**Actions:**
- ✓ Records tool execution in current task's `executions` array
- ✓ Checks if task is complete (by `completion_signal` or subtask status)
- ✓ If task complete:
  - Marks `status = 'completed'`, sets `completed_at`
  - Removes from `in_progress`
  - **Automatically promotes next task from queue**
  - If queue empty, sets `auto_dispatch_running = false`

**Idempotent:** Handles case where no active task exists (warns, proceeds).

**Exit Code:** Always 0 (never blocks tool flow).

**Input:** `{ tool_name, tool_use_id, output, execution_time_ms, error? }`

**Output:** `{ status, taskComplete?, nextTask?, allTasksComplete? }`

**State Files:**
- Reads/Writes: `.claude/dispatcher/task_queue.json`
- Reads/Writes: `.claude/dispatcher/dispatcher_state.json`

---

### 3. WorktreeCreate Dispatcher Metadata (`worktree_create_dispatcher_metadata.js`)

**Purpose:** Set up isolated environment metadata when worktree is created.

**Actions:**
- ✓ Creates agent context record with `agent_id`, `worktree_path`, `branch_name`
- ✓ Registers agent in `dispatcher_state.active_agents`
- ✓ Writes agent-specific context: `.claude/dispatcher/agent_context/{AGENT_ID}.json`
- ✓ Sets `isolation_level = 'worktree'` for safe merging

**Metadata:**
```json
{
  "agent_id": "agent-1",
  "worktree_path": "/path/to/worktree",
  "worktree_name": "phase-27-feature",
  "branch_name": "feat/phase-27",
  "created_at": "2025-05-20T12:00:00Z",
  "protected_files": [],
  "status": "active",
  "isolation_level": "worktree",
  "merge_strategy_compatible": true
}
```

**Exit Code:** Always 0 (never blocks worktree creation).

**Input:** `{ worktree_path, worktree_name, branch_name }`

**Output:** `{ status, agent_id, metadata_initialized, context }`

**State Files:**
- Writes: `.claude/dispatcher/dispatcher_state.json`
- Writes: `.claude/dispatcher/agent_context/{AGENT_ID}.json`

---

### 4. WorktreeRemove Dispatcher Cleanup (`worktree_remove_cleanup_context.js`)

**Purpose:** Clean up dispatcher metadata and release locks when worktree is removed.

**Actions:**
- ✓ Deregisters agent from `active_agents`
- ✓ Releases file locks in `protected_file_sets`
- ✓ Archives agent context to `.claude/dispatcher/agent_archive/{AGENT_ID}-{timestamp}.json`
- ✓ Archives task completion metadata
- ✓ Removes from `in_progress` queue
- ✓ Persists all state changes

**Exit Code:** Always 0 (cleanup is best-effort).

**Input:** `{ worktree_path, worktree_name, action }`

**Output:** `{ status, cleaned_items, context_archived, state_persisted }`

**State Files:**
- Reads/Writes: `.claude/dispatcher/dispatcher_state.json`
- Reads/Writes: `.claude/dispatcher/task_queue.json`
- Writes: `.claude/dispatcher/agent_archive/{AGENT_ID}-{timestamp}.json`

---

## Dispatcher Configuration

### Location: `.claude/settings.json` → `dispatcher`

```json
{
  "enabled": false,
  "taskQueueLocation": ".claude/dispatcher/task_queue.json",
  "agentContextLocation": ".claude/dispatcher/agent_context",
  "maxConcurrentAgents": 5,
  "mergeStrategy": "sequential",
  "conflictResolutionRules": {
    "fileConflict": "abort_and_alert",
    "symrefConflict": "manual_resolution",
    "metadataConflict": "merge_dispatcher_metadata",
    "lockTimeout": 30000
  },
  "stateFile": ".claude/dispatcher/dispatcher_state.json",
  "agentChannels": {
    "reportInterval": 1000,
    "queueCheckInterval": 500,
    "mergeCheckInterval": 5000
  }
}
```

### Key Settings

| Setting | Value | Purpose |
|---------|-------|---------|
| `enabled` | `false` | Dispatcher is opt-in; disabled by default |
| `maxConcurrentAgents` | `5` | Max parallel tasks (sequential mode = 1 at a time) |
| `mergeStrategy` | `"sequential"` | Run tasks one-by-one; merge after each completes |
| `fileConflict` | `"abort_and_alert"` | If file locked: abort operation, alert user |
| `lockTimeout` | `30000` | File locks expire after 30 seconds |

---

## State Files

### `.claude/dispatcher/dispatcher_state.json`

```json
{
  "auto_dispatch_running": true,
  "merge_in_progress": false,
  "active_agents": [
    {
      "agent_id": "agent-1",
      "worktree_name": "phase-27-feature",
      "registered_at": "2025-05-20T12:00:00Z"
    }
  ],
  "protected_file_sets": {
    "agent-1": [
      "crates/siss-graph-core/src/lib.rs",
      "crates/siss-graph-core/src/graph.rs"
    ]
  },
  "dispatch_started_at": "2025-05-20T12:00:00Z"
}
```

### `.claude/dispatcher/task_queue.json`

```json
{
  "tasks": [
    {
      "task_id": "task-2",
      "description": "Implement Phase 2 features",
      "priority": 1
    }
  ],
  "in_progress": [
    {
      "task_id": "task-1",
      "description": "Implement Phase 1 features",
      "agent_id": "agent-1",
      "started_at": "2025-05-20T12:00:00Z",
      "executions": [
        {
          "tool_name": "Bash",
          "tool_use_id": "uuid-123",
          "execution_time_ms": 1250,
          "has_error": false
        }
      ],
      "status": "in_progress"
    }
  ],
  "completed": []
}
```

### `.claude/dispatcher/agent_context/{AGENT_ID}.json`

```json
{
  "agent_id": "agent-1",
  "worktree_path": "/path/to/.claude/worktrees/phase-27-feature",
  "worktree_name": "phase-27-feature",
  "branch_name": "feat/phase-27",
  "created_at": "2025-05-20T12:00:00Z",
  "protected_files": [],
  "status": "active",
  "isolation_level": "worktree",
  "merge_strategy_compatible": true
}
```

---

## Conflict Resolution Strategy

### Sequential Merge (Default)

```
Task 1 (agent-1) → complete + merge ↓
Task 2 (agent-2) → complete + merge ↓
Task 3 (agent-3) → complete + merge ↓
All merged → dispatcher done
```

**Flow:**
1. PreToolUse blocks writes if merge is in progress
2. PostToolUse promotes next task when current completes
3. Task completion triggers merge phase (sequential)
4. Once merge finishes, next task starts

### File Conflict Detection

| Scenario | Behavior |
|----------|----------|
| Agent-1 locks `file.rs` | Stored in `protected_file_sets["agent-1"]` |
| Agent-2 tries to edit `file.rs` | PreToolUse gate returns exit code 2 (denied) |
| Agent-1 removes lock (exits worktree) | WorktreeRemove releases lock automatically |
| File available to Agent-2 | Next tool use succeeds |

### Merge Conflicts

If `merge_in_progress = true`:
- All writes blocked (PreToolUse exit code 2)
- All reads allowed
- Manual merge needed if conflict detected
- User must resolve, then re-enable dispatch

---

## Conditional Hook Execution

Hooks are wired with `condition: "DISPATCHER_ACTIVE=true"`. 

**When `DISPATCHER_ACTIVE` is not set or false:**
- Dispatcher hooks are skipped (no performance cost)
- Security gate & correctness gate run normally
- Task tracking disabled

**When `DISPATCHER_ACTIVE=true`:**
- All dispatcher hooks activate
- Task progress tracked automatically
- Conflicts detected and prevented

---

## Enabling the Dispatcher

### For Single Session

```bash
export DISPATCHER_ACTIVE=true
export AGENT_ID=agent-1
export SISS_API_URL=http://localhost:3000
```

Then use Claude Code as normal. Hooks will:
1. Create `.claude/dispatcher/` directory structure
2. Register agent on first worktree creation
3. Track all tool use in task context
4. Auto-promote tasks when complete

### For Multiple Agents (Parallel Dispatch)

Each agent in separate terminal:

```bash
# Terminal 1
export DISPATCHER_ACTIVE=true
export AGENT_ID=agent-1
claude-code

# Terminal 2
export DISPATCHER_ACTIVE=true
export AGENT_ID=agent-2
claude-code
```

Both agents pull from same `task_queue.json`. Dispatcher coordinates with:
- File locks in `protected_file_sets`
- Sequential merge (only one merge phase at a time)

---

## Disabling the Dispatcher

```bash
unset DISPATCHER_ACTIVE
unset AGENT_ID
```

All dispatcher hooks become no-ops. Security & correctness gates run normally.

---

## Hook Performance

All hooks are **ultra-lightweight** with conditional logic:

| Hook | Typical Latency | File I/O |
|------|-----------------|----------|
| PreToolUse dispatcher gate | ~5ms | 2 reads (state, queue) |
| PostToolUse dispatcher report | ~10ms | 2 writes (state, queue) |
| WorktreeCreate metadata | ~8ms | 1 write (context) |
| WorktreeRemove cleanup | ~15ms | 2 writes (state, queue) + archive |

**Optimization:** When dispatcher not active, hooks are completely skipped. Zero overhead.

---

## Troubleshooting

### "File is locked by agent X"

**Cause:** Another agent is currently editing that file.

**Solution:**
1. Check `protected_file_sets` in `dispatcher_state.json`
2. Wait for other agent's task to complete
3. Or: manually remove lock from `protected_file_sets`

### "Merge in progress; writes blocked"

**Cause:** Dispatcher is merging tasks from previous agents.

**Solution:**
1. Check `merge_in_progress` in `dispatcher_state.json`
2. Wait for merge to complete (watch logs)
3. Or: set `merge_in_progress = false` manually to unblock

### "No active task found"

**Cause:** Tool was executed but dispatcher has no task assigned to this agent.

**Behavior:** PostToolUse report logs warning but succeeds. Proceeds without task tracking.

**Solution:** Ensure task queue is populated and agent is registered before tool use.

### Hooks not activating

**Check:**
1. Is `DISPATCHER_ACTIVE=true`?
2. Does `.claude/dispatcher/` directory exist?
3. Are hook scripts executable? (`ls -la scripts/hooks/`)
4. Check logs: `cat ~/.claude/agent-shell/audit.log` (if available)

---

## Files Summary

| File | Purpose | Lines |
|------|---------|-------|
| `.claude/settings.json` | Hook registration & dispatcher config | ~180 |
| `scripts/hooks/pre_tool_use_dispatcher_gate.js` | Conflict gate | 249 |
| `scripts/hooks/post_tool_use_dispatcher_report.js` | Task tracking & promotion | 297 |
| `scripts/hooks/worktree_create_dispatcher_metadata.js` | Agent registration | 215 |
| `scripts/hooks/worktree_remove_cleanup_context.js` | Context cleanup & archival | 317 |

**Total:** ~1,178 lines of dispatch orchestration logic.

---

## Next Steps

1. **Enable dispatcher** with `export DISPATCHER_ACTIVE=true`
2. **Create task queue** at `.claude/dispatcher/task_queue.json` with task list
3. **Monitor dispatch** using `watch -n 1 cat .claude/dispatcher/dispatcher_state.json`
4. **Review logs** in `~/.claude/agent-shell/audit.log` (if configured)
5. **Adjust settings** (maxConcurrentAgents, mergeStrategy) as needed

---

## API Integration (Optional)

PostToolUse logger posts to `SISS_API_URL` if available:
- Endpoint: `/api/graph/projections/audit`
- Fallback: Local `~/.claude/agent-shell/audit.log`

Set environment variable:
```bash
export SISS_API_URL=http://localhost:3000
```

If API unavailable, logs to local audit trail automatically.
