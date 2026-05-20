# Phase 30: Master Dispatcher Architecture Design
**Date:** May 20, 2026  
**Purpose:** Multi-agent orchestration framework for 3-5 parallel worktree agents  
**Status:** DESIGN DOCUMENT (no implementation)

---

## I. OVERVIEW

Phase 30 establishes the **dispatch protocol** and **task queue infrastructure** enabling 5 independent agents to work on isolated features concurrently without merge conflicts. The design prevents:
- Concurrent writes to the same file
- Merge commit conflicts
- Agent stalls due to blocked tasks
- Data corruption from incomplete commits

**Key principle:** Topology-sorted task dependencies + topologically-sorted merge order = zero conflicts.

---

## II. TASK QUEUE SCHEMA (queue.json)

```json
{
  "version": 1,
  "phase": 30,
  "created_at": "2026-05-20T19:00:00Z",
  "tasks": [
    {
      "id": "task-001",
      "phase": 30,
      "name": "Phase 30 Feature 1: Dispatcher Core",
      "description": "Implement dispatcher.rs with queue management and agent assignment",
      "priority": 1,
      "assigned_agent": "Agent1",
      "status": "pending",
      "dependencies": [],
      "blocks": ["task-004", "task-005"],
      "worktree_branch": "feature/dispatcher-core",
      "files_touched": [
        "crates/siss-dispatcher/src/dispatcher.rs",
        "crates/siss-dispatcher/src/queue.rs",
        "crates/siss-dispatcher/Cargo.toml"
      ],
      "estimated_days": 1.5,
      "merge_order": 1,
      "created_at": "2026-05-20T19:00:00Z",
      "started_at": null,
      "completed_at": null
    },
    {
      "id": "task-002",
      "phase": 30,
      "name": "Phase 30 Feature 2: Task Pool & State Machine",
      "description": "Implement task state transitions and pool management",
      "priority": 2,
      "assigned_agent": "Agent2",
      "status": "pending",
      "dependencies": [],
      "blocks": ["task-004"],
      "worktree_branch": "feature/task-pool",
      "files_touched": [
        "crates/siss-dispatcher/src/pool.rs",
        "crates/siss-dispatcher/src/state.rs"
      ],
      "estimated_days": 1.0,
      "merge_order": 2,
      "created_at": "2026-05-20T19:00:00Z",
      "started_at": null,
      "completed_at": null
    },
    {
      "id": "task-003",
      "phase": 30,
      "name": "Phase 30 Feature 3: Merge Coordinator",
      "description": "Topological sort and merge sequencing logic",
      "priority": 3,
      "assigned_agent": "Agent3",
      "status": "pending",
      "dependencies": [],
      "blocks": ["task-006"],
      "worktree_branch": "feature/merge-coordinator",
      "files_touched": [
        "crates/siss-dispatcher/src/merge.rs",
        "crates/siss-dispatcher/src/graph.rs"
      ],
      "estimated_days": 1.5,
      "merge_order": 3,
      "created_at": "2026-05-20T19:00:00Z",
      "started_at": null,
      "completed_at": null
    },
    {
      "id": "task-004",
      "phase": 30,
      "name": "Phase 30 Feature 4: Agent Protocol & Progress Reporting",
      "description": "RPC/polling interface for agents to fetch tasks and report progress",
      "priority": 2,
      "assigned_agent": "Agent4",
      "status": "pending",
      "dependencies": ["task-001", "task-002"],
      "blocks": ["task-006"],
      "worktree_branch": "feature/agent-protocol",
      "files_touched": [
        "crates/siss-dispatcher/src/protocol.rs",
        "crates/siss-dispatcher/src/rpc.rs"
      ],
      "estimated_days": 1.5,
      "merge_order": 4,
      "created_at": "2026-05-20T19:00:00Z",
      "started_at": null,
      "completed_at": null
    },
    {
      "id": "task-005",
      "phase": 30,
      "name": "Phase 30 Feature 5: Conflict Detection & Resolution",
      "description": "AST-based file diff analysis and conflict resolution strategy",
      "priority": 2,
      "assigned_agent": "Agent5",
      "status": "pending",
      "dependencies": ["task-001"],
      "blocks": ["task-006"],
      "worktree_branch": "feature/conflict-detection",
      "files_touched": [
        "crates/siss-dispatcher/src/conflict.rs",
        "crates/siss-dispatcher/src/diff.rs"
      ],
      "estimated_days": 1.5,
      "merge_order": 5,
      "created_at": "2026-05-20T19:00:00Z",
      "started_at": null,
      "completed_at": null
    },
    {
      "id": "task-006",
      "phase": 30,
      "name": "Phase 30 Verification: Integration Tests & Load Test",
      "description": "Test suite: 5 agents parallel dispatch, state coherency, merge sequencing",
      "priority": 3,
      "assigned_agent": null,
      "status": "pending",
      "dependencies": ["task-003", "task-004", "task-005"],
      "blocks": [],
      "worktree_branch": "feature/dispatcher-tests",
      "files_touched": [
        "crates/siss-dispatcher/tests/dispatcher_test.rs",
        "crates/siss-dispatcher/tests/load_test.rs"
      ],
      "estimated_days": 1.5,
      "merge_order": 6,
      "created_at": "2026-05-20T19:00:00Z",
      "started_at": null,
      "completed_at": null
    }
  ],
  "metadata": {
    "total_tasks": 6,
    "critical_path_days": 3.5,
    "parallelizable_tasks": 5,
    "merge_chain_length": 6
  }
}
```

**Schema rationale:**
- `merge_order`: Explicitly orders branches by dependency graph (no topological errors)
- `dependencies`: List of task IDs that must complete before this task can start
- `blocks`: List of tasks waiting on this one (inverse index for fast lookup)
- `worktree_branch`: Agent-local branch name for easy git tracking
- `files_touched`: Declare file ownership upfront → no concurrent writes

---

## III. DISPATCH PROTOCOL (Agent ↔ Orchestrator)

### Phase 1: Task Fetch (Agent polls)

**Request (Agent → Orchestrator):**
```
POST /dispatch/fetch_task
{
  "agent_id": "Agent1",
  "version": "phase-30-v1",
  "status_report": {
    "current_task_id": null,
    "git_worktree": "/path/to/worktree",
    "last_heartbeat_at": "2026-05-20T19:05:00Z"
  }
}
```

**Response (Orchestrator → Agent):**
```
200 OK
{
  "task": {
    "id": "task-001",
    "name": "Dispatcher Core",
    "description": "...",
    "worktree_branch": "feature/dispatcher-core",
    "files_touched": ["crates/siss-dispatcher/src/dispatcher.rs"],
    "blockedBy": [],
    "blocks": ["task-004", "task-005"]
  },
  "checkpoint": {
    "commit_sha": "abc123...",
    "timestamp": "2026-05-20T19:05:30Z"
  }
}

OR (if no tasks available)

202 ACCEPTED
{
  "message": "No available tasks. Waiting on: task-002 (pending → in_progress), task-003 (pending → in_progress)",
  "estimated_wait_seconds": 300
}
```

### Phase 2: Progress Report (Agent polls every 5 min)

**Request (Agent → Orchestrator):**
```
POST /dispatch/progress
{
  "agent_id": "Agent1",
  "task_id": "task-001",
  "status": "in_progress",
  "checkpoint": {
    "commit_sha": "abc123...",
    "files_staged": 3,
    "tests_passing": 15,
    "tests_failing": 0
  },
  "eta_seconds": 1800
}
```

**Response (Orchestrator → Agent):**
```
200 OK
{
  "ack": true,
  "heartbeat_interval_seconds": 300,
  "orchestrator_status": "running"
}

OR (if agent task was cancelled)

410 GONE
{
  "reason": "Task reassigned to Agent2 due to timeout",
  "action": "ABORT_LOCAL_CHANGES"
}
```

### Phase 3: Task Completion (Agent signals done)

**Request (Agent → Orchestrator):**
```
POST /dispatch/complete_task
{
  "agent_id": "Agent1",
  "task_id": "task-001",
  "status": "completed",
  "result": {
    "tests_passed": 18,
    "linter_clean": true,
    "lines_of_code": 342,
    "commit_sha": "def456...",
    "branch": "feature/dispatcher-core"
  },
  "git_push_url": "origin feature/dispatcher-core"
}
```

**Response (Orchestrator → Agent):**
```
200 OK
{
  "acknowledged": true,
  "next_task_available_in_seconds": 120,
  "merge_order": 1,
  "merge_priority": "IMMEDIATE"
}

OR (on test failure)

422 UNPROCESSABLE_ENTITY
{
  "reason": "Task completion rejected: 2 tests failing",
  "tests_failing": ["test_dispatcher_timeout", "test_queue_underflow"],
  "action": "RERUN_FAILED_TESTS"
}
```

---

## IV. MERGE COORDINATION ALGORITHM

### Algorithm: Topological Merge Sequencing

```
INPUT: queue.json with tasks
OUTPUT: merge_plan.json with ordered commits

1. BUILD DEPENDENCY GRAPH:
   For each task:
     nodes[task.id] = { status, merge_order, dependencies }
     For each dep in task.dependencies:
       add edge(dep → task.id)

2. TOPOLOGICAL SORT:
   sorted_tasks = kahn_algorithm(nodes, edges)
   
   Function kahn_algorithm(nodes, edges):
     in_degree = { task: count_incoming_edges(task) for task in nodes }
     queue = [task for task in nodes if in_degree[task] == 0]
     result = []
     
     while queue not empty:
       task = queue.pop(0)
       result.append(task)
       
       for dependent in task.blocks:
         in_degree[dependent] -= 1
         if in_degree[dependent] == 0:
           queue.append(dependent)
     
     if len(result) != len(nodes):
       RAISE("Cycle detected in task graph!")
     
     return result

3. BUILD MERGE PLAN:
   merge_plan = []
   for i, task in enumerate(sorted_tasks):
     merge_plan.append({
       "rank": i + 1,
       "task_id": task.id,
       "branch": task.worktree_branch,
       "merge_base": sorted_tasks[i-1].branch if i > 0 else "main",
       "strategy": "merge --no-ff" or "rebase --interactive",
       "conflict_resolution": task.conflict_strategy
     })

4. EXECUTE MERGES IN ORDER:
   last_merged_commit = HEAD(main)
   
   for merge_step in merge_plan:
     git checkout main
     git pull origin main  # Ensure fresh
     
     try:
       git merge --no-ff merge_step.branch
       commit = get_current_commit_sha()
       
       run_tests()  # CRITICAL: catch conflicts early
       
       merge_plan[merge_step.rank].committed_at = now()
       merge_plan[merge_step.rank].commit_sha = commit
     
     catch MERGE_CONFLICT:
       invoke_conflict_resolution(merge_step)
       # See Section V below
```

**Merge order in queue.json:**
- `task-001` (merge_order: 1) → merged first
- `task-002` (merge_order: 2) → merged second
- ... continues in sequence

**Key property:** No task can reach `merge_order` ≤ until all tasks it depends on have `merge_order` < and are merged.

---

## V. CONFLICT DETECTION & RESOLUTION

### File-Level Conflict Prevention

**Strategy 1: Ownership (first defense)**
```
task-001 owns: crates/siss-dispatcher/src/dispatcher.rs
task-002 owns: crates/siss-dispatcher/src/pool.rs
task-003 owns: crates/siss-dispatcher/src/merge.rs
task-004 owns: crates/siss-dispatcher/src/protocol.rs
task-005 owns: crates/siss-dispatcher/src/conflict.rs

⇒ ZERO file overlap = ZERO merge conflicts
```

**If overlap is unavoidable:**

**Strategy 2: AST-level conflict detection**
```rust
// In conflict.rs
fn detect_ast_conflicts(branch_a: &str, branch_b: &str, file: &Path) -> ConflictReport {
  let ast_a = parse_rust_file(branch_a, file)?;
  let ast_b = parse_rust_file(branch_b, file)?;
  
  let changes_a = ast_diff(base_ast, ast_a);
  let changes_b = ast_diff(base_ast, ast_b);
  
  // Check: do changes touch the same functions/structs?
  let conflicts = find_overlapping_changes(changes_a, changes_b);
  
  if conflicts.is_empty() {
    return Ok(NoConflict)
  } else {
    return Err(ConflictReport {
      functions_in_conflict: conflicts.keys(),
      severity: "SEMANTIC" | "SYNTACTIC",
      resolution_hint: suggest_resolution(conflicts)
    })
  }
}
```

**Strategy 3: Merge conflict resolution (last resort)**
```
If conflict detected at merge time:
  1. Abort merge (git merge --abort)
  2. Revert to last stable main
  3. Ask task owner to rebase their branch onto latest main
  4. Re-request merge
  
  Agent receives: 410 CONFLICT_DETECTED
  Agent action: git rebase main, resolve conflicts locally, force-push
```

---

## VI. DISPATCHER IMPLEMENTATION PSEUDOCODE

### dispatcher.rs (Core Orchestrator)

```rust
use std::sync::{Arc, Mutex};
use std::collections::HashMap;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TaskStatus {
    Pending,
    Assigned,
    InProgress,
    Completed,
    Failed,
    Merged,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Task {
    pub id: String,
    pub phase: u32,
    pub name: String,
    pub priority: u32,
    pub assigned_agent: Option<String>,
    pub status: TaskStatus,
    pub dependencies: Vec<String>,
    pub blocks: Vec<String>,
    pub merge_order: u32,
    pub files_touched: Vec<String>,
    pub worktree_branch: String,
}

#[derive(Debug, Clone)]
pub struct TaskQueue {
    tasks: Arc<Mutex<HashMap<String, Task>>>,
    dependency_graph: Arc<Mutex<DependencyGraph>>,
}

impl TaskQueue {
    pub fn new(queue_json: &str) -> Result<Self, Box<dyn std::error::Error>> {
        let json: QueueJson = serde_json::from_str(queue_json)?;
        
        let mut tasks = HashMap::new();
        for task in json.tasks {
            tasks.insert(task.id.clone(), task);
        }
        
        let graph = DependencyGraph::build(&tasks)?;
        
        Ok(Self {
            tasks: Arc::new(Mutex::new(tasks)),
            dependency_graph: Arc::new(Mutex::new(graph)),
        })
    }
    
    /// Fetch next available task for agent
    pub fn fetch_task(&self, agent_id: &str) -> Result<Option<Task>, Box<dyn std::error::Error>> {
        let tasks = self.tasks.lock().unwrap();
        let graph = self.dependency_graph.lock().unwrap();
        
        // Find pending task with all dependencies satisfied
        for task in tasks.values() {
            if task.status == TaskStatus::Pending && task.dependencies.is_empty() {
                // All dependencies completed
                return Ok(Some(task.clone()));
            }
        }
        
        Ok(None)
    }
    
    /// Update task status and refresh dependency graph
    pub fn update_task_status(
        &self,
        task_id: &str,
        new_status: TaskStatus,
        agent_id: &str,
    ) -> Result<(), Box<dyn std::error::Error>> {
        let mut tasks = self.tasks.lock().unwrap();
        
        if let Some(task) = tasks.get_mut(task_id) {
            task.status = new_status.clone();
            task.assigned_agent = Some(agent_id.to_string());
            
            // If completed, unblock dependent tasks
            if matches!(new_status, TaskStatus::Completed | TaskStatus::Merged) {
                for blocked_task_id in &task.blocks {
                    if let Some(blocked_task) = tasks.get_mut(blocked_task_id) {
                        // Remove this task from dependencies
                        blocked_task.dependencies.retain(|dep| dep != task_id);
                    }
                }
            }
        }
        
        Ok(())
    }
    
    /// Build topologically sorted merge order
    pub fn compute_merge_order(&self) -> Result<Vec<String>, Box<dyn std::error::Error>> {
        let tasks = self.tasks.lock().unwrap();
        let graph = self.dependency_graph.lock().unwrap();
        
        let sorted = graph.topological_sort()?;
        
        Ok(sorted.into_iter().map(|t| t.id).collect())
    }
}

#[derive(Debug)]
pub struct DependencyGraph {
    adjacency: HashMap<String, Vec<String>>,
    in_degree: HashMap<String, usize>,
}

impl DependencyGraph {
    pub fn build(tasks: &HashMap<String, Task>) -> Result<Self, Box<dyn std::error::Error>> {
        let mut adjacency: HashMap<String, Vec<String>> = HashMap::new();
        let mut in_degree: HashMap<String, usize> = HashMap::new();
        
        // Initialize
        for task_id in tasks.keys() {
            adjacency.insert(task_id.clone(), Vec::new());
            in_degree.insert(task_id.clone(), tasks[task_id].dependencies.len());
        }
        
        // Build edges
        for task in tasks.values() {
            for dep in &task.dependencies {
                adjacency.get_mut(dep).unwrap().push(task.id.clone());
            }
        }
        
        Ok(Self { adjacency, in_degree })
    }
    
    /// Kahn's algorithm for topological sort
    pub fn topological_sort(&self) -> Result<Vec<Task>, Box<dyn std::error::Error>> {
        let mut queue: Vec<String> = self.in_degree
            .iter()
            .filter(|(_, degree)| **degree == 0)
            .map(|(id, _)| id.clone())
            .collect();
        
        let mut result = Vec::new();
        let mut in_degree_copy = self.in_degree.clone();
        
        while !queue.is_empty() {
            let node = queue.remove(0);
            result.push(node.clone());
            
            for neighbor in &self.adjacency[&node] {
                in_degree_copy.insert(neighbor.clone(), in_degree_copy[neighbor] - 1);
                if in_degree_copy[neighbor] == 0 {
                    queue.push(neighbor.clone());
                }
            }
        }
        
        if result.len() != self.in_degree.len() {
            return Err("Cycle detected in task dependency graph!".into());
        }
        
        // Convert to Task objects (stub)
        Ok(result.into_iter().map(|id| Task {
            id,
            phase: 30,
            name: "".to_string(),
            priority: 0,
            assigned_agent: None,
            status: TaskStatus::Pending,
            dependencies: vec![],
            blocks: vec![],
            merge_order: 0,
            files_touched: vec![],
            worktree_branch: "".to_string(),
        }).collect())
    }
}

#[derive(Debug)]
pub struct MergeCoordinator {
    queue: Arc<TaskQueue>,
}

impl MergeCoordinator {
    pub fn new(queue: Arc<TaskQueue>) -> Self {
        Self { queue }
    }
    
    /// Generate merge plan from task dependencies
    pub fn generate_merge_plan(&self) -> Result<MergePlan, Box<dyn std::error::Error>> {
        let merge_order = self.queue.compute_merge_order()?;
        
        let mut plan = MergePlan {
            steps: Vec::new(),
            estimated_duration_seconds: 0,
        };
        
        for (rank, task_id) in merge_order.into_iter().enumerate() {
            plan.steps.push(MergeStep {
                rank: rank + 1,
                task_id,
                merge_base: if rank == 0 { "main".to_string() } else { "prev_merge".to_string() },
                strategy: "merge --no-ff",
                conflict_resolution: "rebase_on_conflict",
            });
        }
        
        Ok(plan)
    }
    
    /// Execute merge with conflict detection
    pub async fn execute_merge(&self, step: &MergeStep) -> Result<MergeResult, Box<dyn std::error::Error>> {
        // Pseudocode: invoke git commands via Command/Process
        // 1. git checkout main
        // 2. git pull origin main
        // 3. git merge --no-ff <branch>
        // 4. run tests + linter
        // 5. if conflict: trigger conflict_resolution(step)
        // 6. git push origin main
        
        Ok(MergeResult {
            commit_sha: "abc123".to_string(),
            merged_at: chrono::Utc::now(),
            tests_passed: true,
            conflicts_resolved: false,
        })
    }
}

#[derive(Debug)]
pub struct MergePlan {
    pub steps: Vec<MergeStep>,
    pub estimated_duration_seconds: u32,
}

#[derive(Debug)]
pub struct MergeStep {
    pub rank: usize,
    pub task_id: String,
    pub merge_base: String,
    pub strategy: &'static str,
    pub conflict_resolution: &'static str,
}

#[derive(Debug)]
pub struct MergeResult {
    pub commit_sha: String,
    pub merged_at: chrono::DateTime<chrono::Utc>,
    pub tests_passed: bool,
    pub conflicts_resolved: bool,
}
```

### protocol.rs (Agent ↔ Orchestrator RPC)

```rust
use axum::{
    extract::{State, Json},
    http::StatusCode,
    Router,
};
use tokio::sync::RwLock;

#[derive(Serialize, Deserialize)]
pub struct FetchTaskRequest {
    pub agent_id: String,
    pub version: String,
    pub status_report: StatusReport,
}

#[derive(Serialize, Deserialize)]
pub struct StatusReport {
    pub current_task_id: Option<String>,
    pub git_worktree: String,
    pub last_heartbeat_at: chrono::DateTime<chrono::Utc>,
}

#[derive(Serialize, Deserialize)]
pub struct FetchTaskResponse {
    pub task: Option<Task>,
    pub checkpoint: Checkpoint,
}

pub async fn fetch_task_handler(
    State(queue): State<Arc<RwLock<TaskQueue>>>,
    Json(req): Json<FetchTaskRequest>,
) -> Result<(StatusCode, Json<FetchTaskResponse>), String> {
    let queue = queue.read().await;
    
    match queue.fetch_task(&req.agent_id) {
        Ok(Some(task)) => {
            Ok((StatusCode::OK, Json(FetchTaskResponse {
                task: Some(task),
                checkpoint: Checkpoint {
                    commit_sha: "abc123".to_string(),
                    timestamp: chrono::Utc::now(),
                },
            })))
        }
        Ok(None) => {
            Ok((StatusCode::ACCEPTED, Json(FetchTaskResponse {
                task: None,
                checkpoint: Checkpoint::default(),
            })))
        }
        Err(e) => Err(e.to_string()),
    }
}

pub async fn progress_handler(
    State(queue): State<Arc<RwLock<TaskQueue>>>,
    Json(req): Json<ProgressRequest>,
) -> Result<StatusCode, String> {
    let mut queue = queue.write().await;
    queue.update_task_status(&req.task_id, TaskStatus::InProgress, &req.agent_id)?;
    
    Ok(StatusCode::OK)
}

pub fn router(queue: Arc<RwLock<TaskQueue>>) -> Router {
    Router::new()
        .route("/fetch_task", axum::routing::post(fetch_task_handler))
        .route("/progress", axum::routing::post(progress_handler))
        .with_state(queue)
}
```

---

## VII. SUMMARY

| Component | Responsibility |
|-----------|-----------------|
| **queue.json** | Single source of truth: task state, dependencies, ownership, merge order |
| **Dispatch Protocol** | Stateless polling interface (agent ↔ orchestrator) |
| **Dependency Graph** | Kahn's algorithm ensures zero cycles, correct merge ordering |
| **File Ownership** | Prevents concurrent writes by explicit file declarations |
| **Conflict Detection** | AST-level analysis before merge attempt |
| **Merge Coordinator** | Executes merges in dependency order with rollback on failure |

**Critical invariants:**
1. **Acyclic:** Task dependencies form a DAG (checked at queue creation)
2. **Deterministic:** Same queue always produces same merge order
3. **Conflict-free:** Non-overlapping file ownership = zero merge conflicts
4. **Recoverable:** Failed merge triggers rebase, no data loss

This design supports 5 concurrent agents with sub-second task assignment and deterministic merge sequencing.

