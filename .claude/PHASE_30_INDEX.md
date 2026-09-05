# Phase 30: Master Dispatcher Design — Complete Index

**Status:** DESIGN COMPLETE (1,987 lines across 5 documents)  
**Date:** May 20, 2026  
**Ready for:** Implementation (task-001 → task-006)

---

## Document Navigation

### Quick Start (5 min read)
→ **PHASE_30_DESIGN_SUMMARY.md** — Executive overview, key design decisions, implementation roadmap

### Full Architecture (20 min read)
→ **PHASE_30_DISPATCHER_DESIGN.md** — Comprehensive specification with pseudocode

### API Implementation (15 min read)
→ **PHASE_30_DISPATCH_PROTOCOL.md** — HTTP endpoints, request/response formats, state machine

### Visual Understanding (10 min read)
→ **PHASE_30_ARCHITECTURE_DIAGRAM.md** — ASCII diagrams, DAG, merge sequence, conflict prevention

### Configuration (load into orchestrator)
→ **phase-30-queue.json** — Concrete task queue template for Phase 30

---

## What Each Document Covers

| Document | Length | Purpose | Key Content |
|----------|--------|---------|------------|
| **PHASE_30_DESIGN_SUMMARY.md** | 359 lines | Executive overview | Problems solved, design decisions, validation checklist |
| **PHASE_30_DISPATCHER_DESIGN.md** | 785 lines | Full architectural spec | Task queue schema, dispatch protocol, merge algorithm, pseudocode |
| **PHASE_30_DISPATCH_PROTOCOL.md** | 366 lines | HTTP API reference | Endpoint signatures, state machine, fault scenarios, polling cadence |
| **PHASE_30_ARCHITECTURE_DIAGRAM.md** | 327 lines | Visual system design | ASCII diagrams, DAG, state machine, merge sequence, conflict layers |
| **phase-30-queue.json** | 150 lines | Concrete configuration | 6 tasks, dependencies, file ownership, merge order |

**Total: 1,987 lines of design documentation**

---

## How to Use These Documents

### If you're implementing the orchestrator:
1. Read **PHASE_30_DESIGN_SUMMARY.md** (understand the problem)
2. Study **PHASE_30_DISPATCHER_DESIGN.md** Section VII (dispatcher.rs pseudocode)
3. Implement TaskQueue struct with Arc<Mutex<>> synchronization
4. Implement DependencyGraph with Kahn's algorithm
5. Implement MergeCoordinator with topological merge

### If you're implementing an agent:
1. Read **PHASE_30_DISPATCH_PROTOCOL.md** (understand the protocol)
2. Implement HTTP polling loop:
   - POST /fetch_task every 30s (idle)
   - POST /progress every 5 min (working)
   - POST /complete_task (when tests pass)
3. Handle 410 GONE (task reassigned) and 422 UNPROCESSABLE_ENTITY (tests fail)

### If you're setting up the dispatcher:
1. Load **phase-30-queue.json** into orchestrator
2. Run validation:
   - Topological sort succeeds (no cycles)
   - File ownership non-overlapping
   - All tasks have unique merge_order
3. Start orchestrator on port 9999
4. Spawn 5 agents in separate worktrees

### If you're debugging conflicts:
1. Consult **PHASE_30_ARCHITECTURE_DIAGRAM.md** Section "Conflict Prevention Strategy"
2. Layer 1: File ownership (check phase-30-queue.json files_touched)
3. Layer 2: AST-level conflict detection (see PHASE_30_DISPATCHER_DESIGN.md Section V)
4. Layer 3: Merge rollback + rebase (see PHASE_30_DISPATCH_PROTOCOL.md Section 6)

---

## Critical Design Invariants

**These are guaranteed by design:**

1. **Acyclic task graph:** Kahn's algorithm validates at queue creation
2. **Deterministic merge order:** Same queue → same topological sort result
3. **Zero file conflicts:** Non-overlapping files_touched declared upfront
4. **No agent stalls:** Dependencies tracked, tasks assigned when ready
5. **Fault tolerant:** Heartbeat detection + automatic task reassignment

---

## Key Metrics at a Glance

```
Phase 30 Composition:
  - Total tasks: 6
  - Parallel startup: 3 tasks (task-001, 002, 003)
  - Critical path: 3.5 days
  - Max agents supported: 5
  - Merge chain length: 6 commits (topologically ordered)
  - File conflict probability: 0% (by design)

Task breakdown:
  - task-001: Dispatcher Core (1.5d)
  - task-002: Task Pool & State (1.0d)
  - task-003: Merge Coordinator (1.5d)
  - task-004: Agent Protocol (1.5d) [blocks on 001, 002]
  - task-005: Conflict Detection (1.5d) [blocks on 001]
  - task-006: Verification Tests (1.5d) [blocks on 003, 004, 005]

Timeline:
  Parallel window: Days 1-1.5 (task-001, 002, 003 simultaneous)
  Sequential path: Days 1-3.5 (task-001 → 004 → 006)
```

---

## Files Touched by Each Task

```
task-001 (Dispatcher Core):
  • crates/siss-dispatcher/src/lib.rs
  • crates/siss-dispatcher/src/dispatcher.rs
  • crates/siss-dispatcher/src/queue.rs
  • crates/siss-dispatcher/Cargo.toml

task-002 (Task Pool & State):
  • crates/siss-dispatcher/src/pool.rs
  • crates/siss-dispatcher/src/state.rs
  • crates/siss-dispatcher/tests/state_machine_test.rs

task-003 (Merge Coordinator):
  • crates/siss-dispatcher/src/merge.rs
  • crates/siss-dispatcher/src/graph.rs
  • crates/siss-dispatcher/tests/merge_coordinator_test.rs

task-004 (Agent Protocol):
  • crates/siss-dispatcher/src/protocol.rs
  • crates/siss-dispatcher/src/rpc.rs
  • crates/siss-dispatcher/src/heartbeat.rs
  • crates/siss-dispatcher/tests/protocol_test.rs

task-005 (Conflict Detection):
  • crates/siss-dispatcher/src/conflict.rs
  • crates/siss-dispatcher/src/diff.rs
  • crates/siss-dispatcher/tests/conflict_detection_test.rs

task-006 (Verification Tests):
  • crates/siss-dispatcher/tests/dispatcher_integration_test.rs
  • crates/siss-dispatcher/tests/load_test.rs
  • crates/siss-dispatcher/tests/merge_plan_test.rs

ZERO FILE OVERLAP ✓
```

---

## Dispatch Protocol at a Glance

```
Agent Polling Loop:

  Idle → POST /fetch_task
         ↓ Response: 200 OK { task } or 202 ACCEPTED { wait }
         
  Working (every 5 min) → POST /progress
                         ↓ Response: 200 OK { ack }
                         
  Tests pass → POST /complete_task
              ↓ Response: 200 OK { merge_order: 1 }
              
  Tests fail → POST /complete_task { tests: FAIL }
              ↓ Response: 422 UNPROCESSABLE_ENTITY { rerun }
              
  Timeout (>600s) → GET /fetch_task
                    ↓ Response: 410 GONE { reassigned }

Merge Execution (orchestrator, sequential):
  task-001 → merge --no-ff → tests pass → push main
  task-002 → merge --no-ff → tests pass → push main
  task-003 → merge --no-ff → tests pass → push main
  ... (repeat for 004, 005, 006)
```

---

## Validation Checklist Before First Agent Starts

- [ ] Crate created: `cargo new --lib crates/siss-dispatcher`
- [ ] phase-30-queue.json loaded into orchestrator
- [ ] Topological sort validates (no cycles)
- [ ] File ownership non-overlapping
- [ ] Merge order [1, 2, 3, 4, 5, 6] matches queue.json
- [ ] Orchestrator HTTP server running on :9999
- [ ] Agent 1 can POST /fetch_task
- [ ] Agent 1 receives task-001 (Dispatcher Core)
- [ ] Merge coordinator generates merge_plan.json
- [ ] All dependencies in graph are satisfied

---

## Design Guarantees

**What you get from this design:**

| Property | How it's guaranteed |
|----------|-------------------|
| **Zero merge conflicts** | File ownership declared, no overlap |
| **Deterministic merge order** | Topological sort (Kahn's algorithm) |
| **No agent stalls** | Task assignment waits for dependencies only |
| **Fault recovery** | Heartbeat timeout → reassign to another agent |
| **Restart safety** | queue.json persists all state to disk |
| **Scale to 5 agents** | Stateless HTTP protocol, no shared state |

---

## Troubleshooting Reference

**"Topological sort failed — cycle detected"**
→ Check phase-30-queue.json for circular dependencies
→ See PHASE_30_DISPATCHER_DESIGN.md Section IV (algorithm)

**"Merge conflict on main"**
→ File ownership violation (check files_touched)
→ Or commit overlap despite ownership (rebase agent, retry merge)
→ See PHASE_30_ARCHITECTURE_DIAGRAM.md "Conflict Prevention"

**"Agent not receiving task"**
→ Check dependencies in queue.json (blocking on other tasks?)
→ Run topological sort to find which tasks unblock this one
→ See PHASE_30_DISPATCH_PROTOCOL.md Section 7 (dependency resolution)

**"Agent timeout — task reassigned"**
→ Agent didn't send /progress heartbeat for 600+ seconds
→ Check agent logs for crashes or network issues
→ Task automatically reassigned to another agent
→ See PHASE_30_DISPATCH_PROTOCOL.md Section 3 (heartbeat)

---

## Quick Reference: Endpoints

| Endpoint | Method | Agent → Orchestrator | Success Response |
|----------|--------|-------------------|-----------------|
| `/fetch_task` | POST | agent_id, version | 200 OK { task } |
| `/progress` | POST | task_id, tests_passing | 200 OK { ack } |
| `/complete_task` | POST | task_id, tests_passed | 200 OK { merge_order } |
| `/conflict_detected` | POST | task_id, branch | 200 OK { rebase } |

---

## Implementation Timeline (Estimated)

```
task-001 (1.5d)  → Dispatcher Core + Queue struct
task-002 (1.0d)  → Task Pool & State machine
task-003 (1.5d)  → Merge Coordinator + Topological sort
↓ (both 001 + 002 must complete)
task-004 (1.5d)  → Agent Protocol + Axum routes
↓ (001 must complete)
task-005 (1.5d)  → Conflict Detection + AST analysis
↓ (all prior must complete)
task-006 (1.5d)  → Integration Tests + Load test

Critical path: 001 (1.5d) → 004 (1.5d) → 006 (1.5d) = 4.5 days
Parallelizable: 001, 002, 003 start immediately = saves 1 day
Actual: ~3.5 days (bottleneck is 006 waiting for three dependencies)
```

---

## Design Philosophy

This design follows these principles:

1. **Simplicity:** Single source of truth (queue.json), stateless HTTP
2. **Correctness:** Topological sort ensures zero cycles, zero conflicts
3. **Fault tolerance:** Automatic agent reassignment, persist to disk
4. **Scalability:** Support 5+ agents without coordination overhead
5. **Observability:** All state in queue.json, easily auditable

**No complex coordination logic.** Just dependency graphs + HTTP polling.

---

## Next Steps

1. **Read PHASE_30_DESIGN_SUMMARY.md** (15 min)
2. **Review PHASE_30_DISPATCHER_DESIGN.md** (30 min)
3. **Create crates/siss-dispatcher crate**
4. **Implement task-001** (Dispatcher Core) following pseudocode
5. **Spawn Agent1 in worktree** (fetch task-001)
6. **Continue with task-002, task-003** (parallel)
7. **When task-001 completes:** task-004, task-005 unblock
8. **When all complete:** Orchestrator executes merge plan

---

## Contact & References

All design documents are in `.claude/`:
```
/Users/andriileukhin/Documents/SovereignNexus/.claude/
├── PHASE_30_DESIGN_SUMMARY.md
├── PHASE_30_DISPATCHER_DESIGN.md
├── PHASE_30_DISPATCH_PROTOCOL.md
├── PHASE_30_ARCHITECTURE_DIAGRAM.md
├── phase-30-queue.json
└── PHASE_30_INDEX.md (this file)
```

Start here: **PHASE_30_DESIGN_SUMMARY.md** (5 min)  
Deep dive: **PHASE_30_DISPATCHER_DESIGN.md** (30 min)  
Implementation: **PHASE_30_DISPATCH_PROTOCOL.md** + pseudocode

---

**Design Status: READY FOR IMPLEMENTATION**

All architectural decisions finalized. No design changes needed.  
Proceed with task-001 (Dispatcher Core).

