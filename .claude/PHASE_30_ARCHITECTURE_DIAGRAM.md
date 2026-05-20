# Phase 30: Dispatcher Architecture Diagram

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PHASE 30 ORCHESTRATION SYSTEM                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    ORCHESTRATOR (Main Process)                      │   │
│  ├──────────────────────────────────────────────────────────────────────┤   │
│  │                                                                      │   │
│  │  ┌─────────────────────┐        ┌──────────────────────────────┐    │   │
│  │  │   TaskQueue (RAM)   │        │  DependencyGraph (DAG)       │    │   │
│  │  ├─────────────────────┤        ├──────────────────────────────┤    │   │
│  │  │ • task-001: Pending │◄──────┤• Kahn's Algorithm            │    │   │
│  │  │ • task-002: Pending │        │• In-degree tracking         │    │   │
│  │  │ • task-003: Pending │        │• Cycle detection            │    │   │
│  │  │ • task-004: Pending │        │• Topological sort           │    │   │
│  │  │ • task-005: Pending │        └──────────────────────────────┘    │   │
│  │  │ • task-006: Pending │                  ▲                       │   │
│  │  └─────────────────────┘                  │                       │   │
│  │           ▲                                │                       │   │
│  │           │                                │                       │   │
│  │  ┌────────┴──────────────┐       ┌────────┴─────────────────────┐  │   │
│  │  │  HTTP Routes (Axum)   │       │  MergeCoordinator           │  │   │
│  │  ├───────────────────────┤       ├────────────────────────────┤  │   │
│  │  │ POST /fetch_task      │       │ • Merge plan generation    │  │   │
│  │  │ POST /progress        │       │ • Topological merge order  │  │   │
│  │  │ POST /complete_task   │       │ • Conflict detection       │  │   │
│  │  │ POST /conflict_detect │       │ • Rollback on failure      │  │   │
│  │  └───────────────────────┘       └─────────────────────────────┘  │   │
│  │                                                                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                ▲                    ▲                      ▲                  │
│                │                    │                      │                  │
│         ┌──────┴──────┬─────────────┴────────┬─────────────┴──────┐         │
│         │             │                      │                    │         │
│   ┌─────▼─────┐ ┌──────▼──────┐  ┌──────────▼───┐  ┌────────────▼──┐     │
│   │  Agent 1  │ │  Agent 2   │  │   Agent 3    │  │   Agent 4    │     │
│   │ (Worktree)│ │(Worktree) │  │  (Worktree)  │  │  (Worktree)  │     │
│   ├───────────┤ ├────────────┤  ├──────────────┤  ├─────────────┤     │
│   │ task-001  │ │  task-002  │  │   task-003   │  │  task-004   │     │
│   │ polling   │ │  polling   │  │   polling    │  │  polling    │     │
│   │ every 30s │ │  every 30s │  │  every 30s   │  │ every 30s   │     │
│   │           │ │            │  │              │  │             │     │
│   │ [polling] │ │ [polling]  │  │ [polling]    │  │[polling]    │     │
│   │ [working] │ │ [working]  │  │ [working]    │  │[working]    │     │
│   │ [done]    │ │ [done]     │  │ [done]       │  │[done]       │     │
│   │           │ │            │  │              │  │             │     │
│   └───────────┘ └────────────┘  └──────────────┘  └─────────────┘     │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Task Dependency Graph (DAG)

```
                        ┌─────────────────┐
                        │   task-001      │
                        │  Dispatcher     │
                        │  Core (1.5d)    │
                        └────────┬────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                        │
                    ▼                        ▼
            ┌──────────────┐        ┌─────────────────┐
            │  task-004    │        │   task-005      │
            │  Agent       │        │  Conflict       │
            │  Protocol    │        │  Detection      │
            │  (1.5d)      │        │  (1.5d)         │
            └──────┬───────┘        └────────┬────────┘
                   │                         │
                   └──────────────┬──────────┘
                                  │
                                  ▼
                          ┌───────────────┐
                          │  task-006     │
                          │  Verification│
                          │  (1.5d)       │
                          └───────────────┘
                   (all tasks must be Merged)

Also independent parallel tracks:

┌─────────────┐         ┌──────────────┐         ┌───────────────┐
│  task-002   │         │  task-003    │         │  task-002*    │
│  Task Pool  │         │  Merge       │         │  (parallel to │
│  (1.0d)     │         │  Coordinator │         │   task-001)   │
│             │         │  (1.5d)      │         │               │
└─────────────┘         └──────────────┘         └───────────────┘

Critical path: task-001 → task-004/005 → task-006 = 3.5 days
Parallelizable: task-001, task-002, task-003 can start simultaneously
```

---

## Task State Machine (Per Task)

```
   ┌────────────┐
   │  Pending   │  (awaiting all dependencies to complete)
   └─────┬──────┘
         │
         │ (dependencies satisfied + agent available)
         ▼
   ┌────────────┐
   │ Assigned   │  (orchestrator assigned to Agent1)
   └─────┬──────┘
         │
         │ (agent polls /fetch_task → receives task)
         ▼
   ┌────────────────┐
   │  InProgress    │  (agent sends /progress heartbeat every 5 min)
   └─────┬──────────┘
         │
         │ (agent sends /complete_task with test results)
         ├─────────────────────────────────────┐
         │                                     │
         │ (tests pass + linter clean)  (tests fail)
         ▼                                    ▼
   ┌──────────────┐                  ┌──────────────┐
   │  Completed   │                  │InProgress    │
   │              │◄─────────────────┤(ask to fix)  │
   └─────┬────────┘                  └──────────────┘
         │
         │ (scheduled in merge_order, execute merge)
         ▼
   ┌───────────────┐
   │    Merged     │  (commit on main branch)
   └───────────────┘

Timeout: If no heartbeat > 600s
  InProgress ──→ Reassigned to another agent → original agent gets 410 GONE
```

---

## Merge Execution Sequence

```
Starting state: main = HEAD@abcd1234

Task-001 (merge_order=1)
  git checkout main
  git pull origin main
  git merge --no-ff feature/dispatcher-core
  cargo test && cargo clippy
  git push origin main
  ✓ main = HEAD@def56789 (includes task-001 commits)

Task-002 (merge_order=2)
  git checkout main
  git pull origin main  (now at def56789)
  git merge --no-ff feature/task-pool
  cargo test && cargo clippy
  git push origin main
  ✓ main = HEAD@ghi90123 (includes task-001 + task-002 commits)

Task-003 (merge_order=3)
  git checkout main
  git pull origin main  (now at ghi90123)
  git merge --no-ff feature/merge-coordinator
  cargo test && cargo clippy
  git push origin main
  ✓ main = HEAD@jkl34567 (includes task-001 + task-002 + task-003 commits)

... (repeat for task-004, task-005)

Task-006 (merge_order=6)
  git checkout main
  git pull origin main  (now at mno01234 with all prior merges)
  git merge --no-ff feature/dispatcher-tests
  cargo test && cargo clippy
  git push origin main
  ✓ main = HEAD@pqr56789 (full Phase 30 delivery)

Final state: All commits on main, zero merge conflicts, all tests passing
```

**Key property:** Each merge builds on previous merge's base → zero conflicts (if file ownership enforced).

---

## Dispatch Protocol Flow

```
Agent1 starts:
  ├─ T=0s:   POST /fetch_task
  │          ↓ Response: 200 OK { task-001 }
  │
  ├─ T=10s:  git checkout feature/dispatcher-core
  │          git rebase origin/main
  │
  ├─ T=300s: POST /progress { status: "InProgress", tests: 10/18 }
  │          ↓ Response: 200 OK { ack: true }
  │
  ├─ T=600s: POST /progress { status: "InProgress", tests: 18/18 }
  │          ↓ Response: 200 OK { ack: true }
  │
  ├─ T=900s: cargo test (all pass)
  │          cargo clippy (clean)
  │          git push origin feature/dispatcher-core
  │
  ├─ T=910s: POST /complete_task { status: "completed", tests: 18 }
  │          ↓ Response: 200 OK { acknowledged: true, merge_order: 1 }
  │
  └─ T=920s: sleep 120 (wait for merge)
             POST /fetch_task (poll for next task)
             ↓ Response: 202 ACCEPTED (waiting for task-002, task-003)
             sleep 300
             POST /fetch_task (poll again)
             ↓ Response: 200 OK { task-004 } (task-001, task-002 merged)

Agent2 (parallel):
  ├─ T=0s:   POST /fetch_task
  │          ↓ Response: 200 OK { task-002 } (no dependencies)
  │
  ├─ T=200s: [similar polling + working pattern]
  │
  └─ T=850s: POST /complete_task { status: "completed", tests: 12 }
             ↓ Response: 200 OK { merge_order: 2 }

[Merge executor watches queue]
  ├─ When task-001.status = Merged
  ├─ When task-002.status = Merged
  ├─ When all dependencies of task-004 are Merged
  └─ Assign task-004 for merge
```

---

## Conflict Prevention Strategy

```
LAYER 1: File Ownership (prevents 95% of conflicts)
  ┌────────────────────────────────────────────────────┐
  │ queue.json declares files_touched per task:        │
  │ • task-001 owns: dispatcher.rs, queue.rs            │
  │ • task-002 owns: pool.rs, state.rs                 │
  │ • task-003 owns: merge.rs, graph.rs                │
  │ • task-004 owns: protocol.rs, rpc.rs               │
  │ • task-005 owns: conflict.rs, diff.rs              │
  │                                                     │
  │ ⇒ ZERO file overlap = ZERO merge conflicts         │
  └────────────────────────────────────────────────────┘

LAYER 2: AST-Level Conflict Detection (prevents remaining 5%)
  ┌────────────────────────────────────────────────────┐
  │ If overlap unavoidable (e.g., Cargo.toml):         │
  │                                                     │
  │ 1. Parse AST before merge                          │
  │ 2. Compare function/struct definitions             │
  │ 3. If no overlap in defs → safe to merge           │
  │ 4. If overlap → rebase + manual resolution         │
  └────────────────────────────────────────────────────┘

LAYER 3: Merge Rollback (last resort)
  ┌────────────────────────────────────────────────────┐
  │ If git merge detects conflict:                     │
  │                                                     │
  │ 1. git merge --abort (revert to main state)        │
  │ 2. Notify agent: task assigned to rebase           │
  │ 3. Agent: git rebase main, force-push              │
  │ 4. Retry merge (should pass now)                   │
  └────────────────────────────────────────────────────┘
```

---

## Orchestrator State Persistence

```
At startup, load from disk:
  queue.json
  ├─ task state (Pending/Assigned/InProgress/Completed/Merged)
  ├─ assigned_agent per task
  ├─ started_at, completed_at timestamps
  └─ merge_order sequence

At each state change, write back to queue.json:
  Agent1: /fetch_task
    → Orchestrator updates: task-001.assigned_agent = "Agent1"
    → Write queue.json
    → Respond with task

Agent1: /progress
    → Orchestrator updates: task-001.status = "InProgress"
    → Write queue.json
    → Respond with ack

Agent1: /complete_task
    → Orchestrator validates tests
    → Updates: task-001.status = "Completed"
    → Writes queue.json
    → Queues task-001 for merge
    → Responds with merge_order

This ensures:
  • Restart safety (can resume from queue.json)
  • Audit trail (timestamps recorded)
  • Agent visibility (agents can inspect queue.json in worktree)
```

---

## Summary: Why This Design Works

| Property | Mechanism |
|----------|-----------|
| **Zero merge conflicts** | File ownership declared upfront + AST conflict detection |
| **Deterministic merge order** | Topological sort (Kahn's) guarantees acyclic DAG |
| **No agent stalls** | Dependency tracking + task fetching on satisfied deps |
| **Fault tolerance** | Heartbeat detection + task reassignment on timeout |
| **Scalability** | Stateless RPC protocol → supports 5+ agents |
| **Observability** | queue.json + merge_plan.json persist to disk |
| **Simplicity** | Single source of truth (queue.json), stateless HTTP |

**Critical path: 3.5 days** (sequential: task-001 → task-004/005 → task-006)  
**Parallelizable: 5 agents** (task-001, task-002, task-003 can start immediately)  
**Merge chain: 6 commits** (deterministic, zero conflicts)

