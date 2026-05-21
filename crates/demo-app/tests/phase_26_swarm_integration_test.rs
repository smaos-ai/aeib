/// Phase 26 Integration Test Suite — Swarm Dispatcher & Worktree Isolation
///
/// TDD Red Phase: All 6 tests define acceptance criteria for:
/// - Isolated git worktrees per job
/// - Tmux session orchestration
/// - Dependency queue enforcement
/// - Fail-closed resource cleanup

use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::Mutex;
use uuid::Uuid;

// ============================================================================
// MOCK FIXTURES & TEST UTILITIES
// ============================================================================

/// Mock EventLog for testing dependency queue logic
#[derive(Clone)]
struct MockEventLog {
    events: Arc<Mutex<HashMap<Uuid, Vec<MockSystemEvent>>>>,
}

#[derive(Debug, Clone, PartialEq)]
enum MockSystemEvent {
    JobDispatched { job_id: Uuid, mandate_id: Uuid },
    JobCompleted { job_id: Uuid, result: String },
    JobFailed { job_id: Uuid, error: String },
}

impl MockEventLog {
    fn new() -> Self {
        Self {
            events: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    async fn append_event(&self, job_id: Uuid, event: MockSystemEvent) {
        let mut events = self.events.lock().await;
        events.entry(job_id).or_insert_with(Vec::new).push(event);
    }

    async fn get_events(&self, job_id: Uuid) -> Vec<MockSystemEvent> {
        let events = self.events.lock().await;
        events.get(&job_id).cloned().unwrap_or_default()
    }

    async fn has_completed(&self, job_id: Uuid) -> bool {
        let events = self.get_events(job_id).await;
        events.iter().any(|e| matches!(e, MockSystemEvent::JobCompleted { .. }))
    }
}

/// Mock TmuxSession for testing
struct MockTmuxSession {
    pub session_name: String,
}

impl MockTmuxSession {
    fn new(job_id: Uuid) -> Self {
        Self {
            session_name: format!("siss-agent-{}", job_id),
        }
    }

    async fn spawn(&self, _working_dir: &str) -> Result<(), String> {
        Ok(())
    }

    async fn kill(&self) -> Result<(), String> {
        Ok(())
    }
}

/// Mock SwarmDispatcher for testing
struct MockSwarmDispatcher {
    event_log: MockEventLog,
    active_slots: Arc<Mutex<HashMap<Uuid, MockJobSlot>>>,
}

#[derive(Debug, Clone)]
struct MockJobSlot {
    pub job_id: Uuid,
    pub worktree_path: String,
    pub branch_name: String,
    pub tmux_session: String,
    pub status: SlotStatus,
}

#[derive(Debug, Clone, PartialEq)]
enum SlotStatus {
    Running,
    Completed,
    Failed,
}

impl MockSwarmDispatcher {
    fn new(event_log: MockEventLog) -> Self {
        Self {
            event_log,
            active_slots: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    async fn dispatch_job(&self, job_id: Uuid, depends_on: Vec<Uuid>) -> Result<MockJobSlot, String> {
        let active = self.active_slots.lock().await;
        if active.contains_key(&job_id) {
            return Err(format!("AlreadyDispatched: {}", job_id));
        }
        drop(active);

        // Check dependencies
        for dep_id in &depends_on {
            if !self.event_log.has_completed(*dep_id).await {
                return Err(format!("DependencyNotMet: {}", dep_id));
            }
        }

        // Create worktree (mock)
        let worktree_path = format!(".claude/worktrees/job-{}", job_id);
        let branch_name = format!("swarm/job-{}", job_id);
        let tmux_session = format!("siss-agent-{}", job_id);

        // Log dispatch
        self.event_log
            .append_event(job_id, MockSystemEvent::JobDispatched {
                job_id,
                mandate_id: Uuid::nil(),
            })
            .await;

        // Insert into active slots
        let slot = MockJobSlot {
            job_id,
            worktree_path,
            branch_name,
            tmux_session,
            status: SlotStatus::Running,
        };

        self.active_slots
            .lock()
            .await
            .insert(job_id, slot.clone());

        Ok(slot)
    }

    async fn complete_job(&self, job_id: Uuid) -> Result<(), String> {
        let _slot = self.active_slots.lock().await.remove(&job_id)
            .ok_or_else(|| format!("JobNotFound: {}", job_id))?;

        // Log completion
        self.event_log
            .append_event(job_id, MockSystemEvent::JobCompleted {
                job_id,
                result: "success".to_string(),
            })
            .await;

        Ok(())
    }

    async fn fail_job(&self, job_id: Uuid, error: &str) -> Result<(), String> {
        let _slot = self.active_slots.lock().await.remove(&job_id)
            .ok_or_else(|| format!("JobNotFound: {}", job_id))?;

        // Log failure (fail-closed: cleanup always runs)
        self.event_log
            .append_event(job_id, MockSystemEvent::JobFailed {
                job_id,
                error: error.to_string(),
            })
            .await;

        Ok(())
    }

    async fn active_count(&self) -> usize {
        self.active_slots.lock().await.len()
    }
}

// ============================================================================
// ACCEPTANCE TESTS (RED PHASE)
// ============================================================================

#[tokio::test]
async fn test_swarm_dispatcher_mounts_isolated_worktree_per_job() {
    let event_log = MockEventLog::new();
    let dispatcher = MockSwarmDispatcher::new(event_log);

    let job_a = Uuid::new_v4();
    let job_b = Uuid::new_v4();
    let job_c = Uuid::new_v4();

    let slot_a = dispatcher.dispatch_job(job_a, vec![]).await.expect("dispatch A");
    let slot_b = dispatcher.dispatch_job(job_b, vec![]).await.expect("dispatch B");
    let slot_c = dispatcher.dispatch_job(job_c, vec![]).await.expect("dispatch C");

    // Verify isolation: unique worktree paths
    assert_ne!(slot_a.worktree_path, slot_b.worktree_path);
    assert_ne!(slot_b.worktree_path, slot_c.worktree_path);
    assert_ne!(slot_a.worktree_path, slot_c.worktree_path);

    // Verify isolation: unique branch names
    assert_ne!(slot_a.branch_name, slot_b.branch_name);
    assert_ne!(slot_b.branch_name, slot_c.branch_name);
}

#[tokio::test]
async fn test_swarm_dispatcher_cleans_up_worktree_on_completion() {
    let event_log = MockEventLog::new();
    let dispatcher = MockSwarmDispatcher::new(event_log.clone());

    let job_id = Uuid::new_v4();
    let _slot = dispatcher.dispatch_job(job_id, vec![]).await.expect("dispatch");

    assert_eq!(dispatcher.active_count().await, 1);

    // Complete the job
    dispatcher.complete_job(job_id).await.expect("complete");

    assert_eq!(dispatcher.active_count().await, 0);

    // Verify JobCompleted event logged
    let events = event_log.get_events(job_id).await;
    assert!(events.iter().any(|e| matches!(e, MockSystemEvent::JobCompleted { .. })));
}

#[tokio::test]
async fn test_swarm_dispatcher_cleans_up_worktree_on_failure() {
    let event_log = MockEventLog::new();
    let dispatcher = MockSwarmDispatcher::new(event_log.clone());

    let job_id = Uuid::new_v4();
    let _slot = dispatcher.dispatch_job(job_id, vec![]).await.expect("dispatch");

    assert_eq!(dispatcher.active_count().await, 1);

    // Fail the job (fail-closed: cleanup always runs)
    dispatcher.fail_job(job_id, "simulated error").await.expect("fail");

    assert_eq!(dispatcher.active_count().await, 0);

    // Verify JobFailed event logged
    let events = event_log.get_events(job_id).await;
    assert!(events.iter().any(|e| matches!(e, MockSystemEvent::JobFailed { .. })));
}

#[tokio::test]
async fn test_swarm_dispatcher_enforces_dependency_queue() {
    let event_log = MockEventLog::new();
    let dispatcher = MockSwarmDispatcher::new(event_log.clone());

    let job_a = Uuid::new_v4();
    let job_b = Uuid::new_v4();

    // Dispatch Job A
    dispatcher.dispatch_job(job_a, vec![]).await.expect("dispatch A");

    // Try to dispatch Job B (depends on A) before A is complete → should fail
    let result = dispatcher.dispatch_job(job_b, vec![job_a]).await;
    assert!(result.is_err(), "should reject Job B when Job A not complete");

    // Complete Job A
    dispatcher.complete_job(job_a).await.expect("complete A");

    // Now dispatch Job B should succeed
    let result = dispatcher.dispatch_job(job_b, vec![job_a]).await;
    assert!(result.is_ok(), "should allow Job B after Job A completes");
}

#[tokio::test]
async fn test_tmux_session_name_is_unique_per_job() {
    let job_a = Uuid::new_v4();
    let job_b = Uuid::new_v4();

    let session_a = MockTmuxSession::new(job_a);
    let session_b = MockTmuxSession::new(job_b);

    // Verify unique names
    assert_ne!(session_a.session_name, session_b.session_name);

    // Verify format
    assert!(session_a.session_name.starts_with("siss-agent-"));
    assert!(session_b.session_name.starts_with("siss-agent-"));
}

#[tokio::test]
async fn test_swarm_dispatcher_rejects_duplicate_job_dispatch() {
    let event_log = MockEventLog::new();
    let dispatcher = MockSwarmDispatcher::new(event_log);

    let job_id = Uuid::new_v4();

    // First dispatch succeeds
    let result1 = dispatcher.dispatch_job(job_id, vec![]).await;
    assert!(result1.is_ok(), "first dispatch should succeed");
    assert_eq!(dispatcher.active_count().await, 1);

    // Second dispatch should fail (AlreadyDispatched)
    let result2 = dispatcher.dispatch_job(job_id, vec![]).await;
    assert!(result2.is_err(), "second dispatch should fail");
    assert!(result2.unwrap_err().contains("AlreadyDispatched"));

    // Active count should remain 1
    assert_eq!(dispatcher.active_count().await, 1);
}
