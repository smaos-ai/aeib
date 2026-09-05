use futures::future::join_all;
/// Phase 27 Load Testing Suite — Multi-Agent Concurrency Under Load
///
/// TDD Red Phase: All 6 tests define acceptance criteria for concurrent dispatch,
/// dependency gating, and fail-closed cleanup under genuine tokio concurrency.
use std::collections::{HashMap, HashSet};
use std::sync::Arc;
use tokio::sync::Mutex;
use uuid::Uuid;

// ============================================================================
// MOCK FIXTURES (copied from Phase 26, unchanged)
// ============================================================================

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
        events
            .iter()
            .any(|e| matches!(e, MockSystemEvent::JobCompleted { .. }))
    }
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

struct MockSwarmDispatcher {
    event_log: MockEventLog,
    active_slots: Arc<Mutex<HashMap<Uuid, MockJobSlot>>>,
}

impl MockSwarmDispatcher {
    fn new(event_log: MockEventLog) -> Self {
        Self {
            event_log,
            active_slots: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    async fn dispatch_job(
        &self,
        job_id: Uuid,
        depends_on: Vec<Uuid>,
    ) -> Result<MockJobSlot, String> {
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
            .append_event(
                job_id,
                MockSystemEvent::JobDispatched {
                    job_id,
                    mandate_id: Uuid::nil(),
                },
            )
            .await;

        // Insert into active slots
        let slot = MockJobSlot {
            job_id,
            worktree_path,
            branch_name,
            tmux_session,
            status: SlotStatus::Running,
        };

        self.active_slots.lock().await.insert(job_id, slot.clone());

        Ok(slot)
    }

    async fn complete_job(&self, job_id: Uuid) -> Result<(), String> {
        let _slot = self
            .active_slots
            .lock()
            .await
            .remove(&job_id)
            .ok_or_else(|| format!("JobNotFound: {}", job_id))?;

        // Log completion
        self.event_log
            .append_event(
                job_id,
                MockSystemEvent::JobCompleted {
                    job_id,
                    result: "success".to_string(),
                },
            )
            .await;

        Ok(())
    }

    async fn fail_job(&self, job_id: Uuid, error: &str) -> Result<(), String> {
        let _slot = self
            .active_slots
            .lock()
            .await
            .remove(&job_id)
            .ok_or_else(|| format!("JobNotFound: {}", job_id))?;

        // Log failure (fail-closed: cleanup always runs)
        self.event_log
            .append_event(
                job_id,
                MockSystemEvent::JobFailed {
                    job_id,
                    error: error.to_string(),
                },
            )
            .await;

        Ok(())
    }

    async fn active_count(&self) -> usize {
        self.active_slots.lock().await.len()
    }
}

// ============================================================================
// LOAD TEST ACCEPTANCE TESTS (RED PHASE)
// ============================================================================

#[tokio::test]
async fn test_10_concurrent_independent_jobs_all_dispatch() {
    let event_log = MockEventLog::new();
    let dispatcher = Arc::new(MockSwarmDispatcher::new(event_log));

    let mut handles = vec![];
    for _ in 0..10 {
        let dispatcher = dispatcher.clone();
        let handle = tokio::spawn(async move {
            let job_id = Uuid::new_v4();
            dispatcher.dispatch_job(job_id, vec![]).await
        });
        handles.push(handle);
    }

    let results = join_all(handles).await;

    // All 10 should succeed
    for result in &results {
        assert!(result.is_ok(), "tokio task should not panic");
        let dispatch_result = result.as_ref().unwrap();
        assert!(dispatch_result.is_ok(), "dispatch_job should succeed");
    }

    assert_eq!(dispatcher.active_count().await, 10);
}

#[tokio::test]
async fn test_10_concurrent_jobs_have_unique_worktree_paths() {
    let event_log = MockEventLog::new();
    let dispatcher = Arc::new(MockSwarmDispatcher::new(event_log));

    let mut handles = vec![];
    for _ in 0..10 {
        let dispatcher = dispatcher.clone();
        let handle = tokio::spawn(async move {
            let job_id = Uuid::new_v4();
            dispatcher.dispatch_job(job_id, vec![]).await
        });
        handles.push(handle);
    }

    let results = join_all(handles).await;

    let mut worktree_paths = HashSet::new();
    let mut branch_names = HashSet::new();

    for result in results {
        let dispatch_result = result.unwrap().unwrap();
        worktree_paths.insert(dispatch_result.worktree_path);
        branch_names.insert(dispatch_result.branch_name);
    }

    assert_eq!(
        worktree_paths.len(),
        10,
        "all worktree paths must be unique"
    );
    assert_eq!(branch_names.len(), 10, "all branch names must be unique");
}

#[tokio::test]
async fn test_duplicate_dispatch_exactly_one_succeeds_under_concurrent_load() {
    let event_log = MockEventLog::new();
    let dispatcher = Arc::new(MockSwarmDispatcher::new(event_log));

    let job_id = Uuid::new_v4();
    let mut handles = vec![];

    // Spawn 5 tasks all trying to dispatch the same job_id
    for _ in 0..5 {
        let dispatcher = dispatcher.clone();
        let handle = tokio::spawn(async move { dispatcher.dispatch_job(job_id, vec![]).await });
        handles.push(handle);
    }

    let results = join_all(handles).await;

    // Count successes and failures
    let mut success_count = 0;
    let mut already_dispatched_count = 0;

    for result in results {
        let dispatch_result = result.unwrap();
        if dispatch_result.is_ok() {
            success_count += 1;
        } else if let Err(e) = dispatch_result {
            if e.contains("AlreadyDispatched") {
                already_dispatched_count += 1;
            }
        }
    }

    assert_eq!(success_count, 1, "exactly one dispatch should succeed");
    assert_eq!(
        already_dispatched_count, 4,
        "exactly four should be rejected"
    );
    assert_eq!(dispatcher.active_count().await, 1);
}

#[tokio::test]
async fn test_fan_out_dependency_gate_blocks_then_unblocks() {
    let event_log = MockEventLog::new();
    let dispatcher = Arc::new(MockSwarmDispatcher::new(event_log));

    let gate_id = Uuid::new_v4();

    // Dispatch the gate job first
    dispatcher
        .dispatch_job(gate_id, vec![])
        .await
        .expect("dispatch gate");

    // Attempt to dispatch 9 fan-out jobs before gate completes
    let mut handles = vec![];
    for _ in 0..9 {
        let dispatcher = dispatcher.clone();
        let handle = tokio::spawn(async move {
            let fan_out_id = Uuid::new_v4();
            dispatcher.dispatch_job(fan_out_id, vec![gate_id]).await
        });
        handles.push(handle);
    }

    let results = join_all(handles).await;

    // All should fail with DependencyNotMet
    for result in &results {
        let dispatch_result = result.as_ref().unwrap();
        assert!(
            dispatch_result.is_err(),
            "should reject before gate completes"
        );
        assert!(
            dispatch_result
                .as_ref()
                .unwrap_err()
                .contains("DependencyNotMet")
        );
    }

    // Complete the gate
    dispatcher
        .complete_job(gate_id)
        .await
        .expect("complete gate");

    // Now dispatch all 9 fan-out jobs again
    let mut handles = vec![];
    for _ in 0..9 {
        let dispatcher = dispatcher.clone();
        let handle = tokio::spawn(async move {
            let fan_out_id = Uuid::new_v4();
            dispatcher.dispatch_job(fan_out_id, vec![gate_id]).await
        });
        handles.push(handle);
    }

    let results = join_all(handles).await;

    // All should succeed now
    for result in &results {
        let dispatch_result = result.as_ref().unwrap();
        assert!(dispatch_result.is_ok(), "should allow after gate completes");
    }

    assert_eq!(dispatcher.active_count().await, 9);
}

#[tokio::test]
async fn test_concurrent_completions_drain_active_slots() {
    let event_log = MockEventLog::new();
    let dispatcher = Arc::new(MockSwarmDispatcher::new(event_log.clone()));

    // Dispatch 10 jobs
    let mut job_ids = vec![];
    let mut handles = vec![];
    for _ in 0..10 {
        let dispatcher = dispatcher.clone();
        let handle = tokio::spawn(async move {
            let job_id = Uuid::new_v4();
            dispatcher.dispatch_job(job_id, vec![]).await
        });
        handles.push(handle);
    }

    // Collect job_ids from dispatch results
    for handle in handles {
        let result = handle.await.unwrap().unwrap();
        job_ids.push(result.job_id);
    }

    assert_eq!(dispatcher.active_count().await, 10);

    // Concurrently complete all 10 jobs
    let mut handles = vec![];
    for job_id in &job_ids {
        let dispatcher = dispatcher.clone();
        let job_id = *job_id;
        let handle = tokio::spawn(async move { dispatcher.complete_job(job_id).await });
        handles.push(handle);
    }

    let results = join_all(handles).await;

    // All completions should succeed
    for result in &results {
        let complete_result = result.as_ref().unwrap();
        assert!(complete_result.is_ok(), "complete_job should succeed");
    }

    assert_eq!(dispatcher.active_count().await, 0);

    // Verify JobCompleted events logged
    for job_id in &job_ids {
        let events = event_log.get_events(*job_id).await;
        assert!(
            events
                .iter()
                .any(|e| matches!(e, MockSystemEvent::JobCompleted { .. }))
        );
    }
}

#[tokio::test]
async fn test_fail_closed_under_concurrent_failures() {
    let event_log = MockEventLog::new();
    let dispatcher = Arc::new(MockSwarmDispatcher::new(event_log.clone()));

    // Dispatch 10 jobs
    let mut job_ids = vec![];
    let mut handles = vec![];
    for _ in 0..10 {
        let dispatcher = dispatcher.clone();
        let handle = tokio::spawn(async move {
            let job_id = Uuid::new_v4();
            dispatcher.dispatch_job(job_id, vec![]).await
        });
        handles.push(handle);
    }

    for handle in handles {
        let result = handle.await.unwrap().unwrap();
        job_ids.push(result.job_id);
    }

    assert_eq!(dispatcher.active_count().await, 10);

    // Concurrently fail all 10 jobs
    let mut handles = vec![];
    for job_id in &job_ids {
        let dispatcher = dispatcher.clone();
        let job_id = *job_id;
        let handle =
            tokio::spawn(async move { dispatcher.fail_job(job_id, "load test error").await });
        handles.push(handle);
    }

    let results = join_all(handles).await;

    // All failures should succeed (fail-closed: cleanup always runs)
    for result in &results {
        let fail_result = result.as_ref().unwrap();
        assert!(fail_result.is_ok(), "fail_job should succeed");
    }

    assert_eq!(dispatcher.active_count().await, 0);

    // Verify JobFailed events logged (fail-closed: every job logged)
    for job_id in &job_ids {
        let events = event_log.get_events(*job_id).await;
        assert!(
            events
                .iter()
                .any(|e| matches!(e, MockSystemEvent::JobFailed { .. }))
        );
    }
}
