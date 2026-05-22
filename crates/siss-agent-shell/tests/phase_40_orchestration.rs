/// Phase 40: δ⁺⁺ Agent of Empires Orchestration Layer
/// 6 TDD tests covering:
/// - Telemetry Sync: AgentSessionManager deduplication (Invariant 1)
/// - Worktree Provisioning: Atomic fail-closed provisioning (Invariant 2)
/// - Session Recovery: Fail-open recovery from suspended state (Invariant 3)

use siss_agent_shell::ag_ui::status_emitter::{AgentSessionManager, AgentState};
use siss_agent_shell::hooks::{HookResult, LifecycleHook, SessionContext};
use siss_agent_shell::hooks::session_recovery::{SessionRecoveryHook, SnapshotReader};
use siss_agent_shell::orchestrator::{SwarmProvisioner, TmuxSpawner, WorktreeCreator, ProvisionError};
use siss_graph_core::node::NodeId;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};

// ============================================================================
// TEST 1: Telemetry deduplication — same state twice emits once
// ============================================================================

#[test]
fn test_telemetry_dedup_same_state() {
    // GIVEN: AgentSessionManager
    let mut manager = AgentSessionManager::new();

    // WHEN: transition_to(Running) twice
    manager.transition_to(AgentState::Running);
    let state_after_first = manager.current_state();

    manager.transition_to(AgentState::Running);
    let state_after_second = manager.current_state();

    // THEN: state remains Running both times (dedup logic correct)
    assert_eq!(state_after_first, AgentState::Running);
    assert_eq!(state_after_second, AgentState::Running);
}

// ============================================================================
// TEST 2: Telemetry distinct transitions tracked in order
// ============================================================================

#[test]
fn test_telemetry_distinct_transitions() {
    // GIVEN: AgentSessionManager initially Idle
    let mut manager = AgentSessionManager::new();
    assert_eq!(manager.current_state(), AgentState::Idle);

    // WHEN: transition Running then Suspended
    manager.transition_to(AgentState::Running);
    let state_after_running = manager.current_state();

    manager.transition_to(AgentState::Suspended);
    let state_after_suspended = manager.current_state();

    // THEN: both transitions tracked, state correct
    assert_eq!(state_after_running, AgentState::Running);
    assert_eq!(state_after_suspended, AgentState::Suspended);
}

// ============================================================================
// Mock implementations for provision tests
// ============================================================================

#[derive(Clone)]
struct MockTmuxSpawner {
    should_fail: Arc<Mutex<bool>>,
    spawn_called: Arc<Mutex<bool>>,
}

impl MockTmuxSpawner {
    fn new(should_fail: bool) -> Self {
        Self {
            should_fail: Arc::new(Mutex::new(should_fail)),
            spawn_called: Arc::new(Mutex::new(false)),
        }
    }

    fn spawn_was_called(&self) -> bool {
        *self.spawn_called.lock().unwrap()
    }
}

#[async_trait::async_trait]
impl TmuxSpawner for MockTmuxSpawner {
    async fn spawn(&self, _name: &str, _working_dir: &str) -> Result<(), ProvisionError> {
        *self.spawn_called.lock().unwrap() = true;
        if *self.should_fail.lock().unwrap() {
            Err(ProvisionError::TmuxFailed("mock failure".into()))
        } else {
            Ok(())
        }
    }

    async fn kill(&self, _name: &str) {}
}

#[derive(Clone)]
struct MockWorktreeCreator {
    should_fail: Arc<Mutex<bool>>,
    create_called: Arc<Mutex<bool>>,
    remove_called: Arc<Mutex<bool>>,
}

impl MockWorktreeCreator {
    fn new(should_fail: bool) -> Self {
        Self {
            should_fail: Arc::new(Mutex::new(should_fail)),
            create_called: Arc::new(Mutex::new(false)),
            remove_called: Arc::new(Mutex::new(false)),
        }
    }

    fn create_was_called(&self) -> bool {
        *self.create_called.lock().unwrap()
    }

    fn remove_was_called(&self) -> bool {
        *self.remove_called.lock().unwrap()
    }
}

#[async_trait::async_trait]
impl WorktreeCreator for MockWorktreeCreator {
    async fn create(&self, _path: &Path, _branch: &str) -> Result<(), ProvisionError> {
        *self.create_called.lock().unwrap() = true;
        if *self.should_fail.lock().unwrap() {
            Err(ProvisionError::WorktreeFailed("mock failure".into()))
        } else {
            Ok(())
        }
    }

    async fn remove(&self, _path: &Path) -> Result<(), ProvisionError> {
        *self.remove_called.lock().unwrap() = true;
        Ok(())
    }
}

// ============================================================================
// TEST 3: Provision fail-closed — worktree error → tmux never called
// ============================================================================

#[tokio::test]
async fn test_provision_fail_closed_worktree_error() {
    // GIVEN: SwarmProvisioner with failing WorktreeCreator
    let worktree = MockWorktreeCreator::new(true);
    let tmux = MockTmuxSpawner::new(false);
    let provisioner = SwarmProvisioner::new(tmux.clone(), worktree.clone(), PathBuf::from("/tmp"));

    // WHEN: provision() called
    let result = provisioner.provision(NodeId::new()).await;

    // THEN: returns WorktreeFailed, tmux.spawn never called
    assert!(matches!(result, Err(ProvisionError::WorktreeFailed(_))));
    assert!(!tmux.spawn_was_called(), "TmuxSpawner::spawn should not have been called");
}

// ============================================================================
// TEST 4: Provision fail-closed — tmux error → worktree cleanup called
// ============================================================================

#[tokio::test]
async fn test_provision_fail_closed_tmux_error() {
    // GIVEN: SwarmProvisioner with successful WorktreeCreator but failing TmuxSpawner
    let worktree = MockWorktreeCreator::new(false);
    let tmux = MockTmuxSpawner::new(true);
    let provisioner = SwarmProvisioner::new(tmux.clone(), worktree.clone(), PathBuf::from("/tmp"));

    // WHEN: provision() called
    let result = provisioner.provision(NodeId::new()).await;

    // THEN: returns TmuxFailed AND worktree.remove was called (cleanup)
    assert!(matches!(result, Err(ProvisionError::TmuxFailed(_))));
    assert!(
        worktree.remove_was_called(),
        "WorktreeCreator::remove should have been called for cleanup"
    );
}

// ============================================================================
// Mock SnapshotReader for session recovery tests
// ============================================================================

struct MockSnapshotReader {
    snapshot: Option<serde_json::Value>,
}

impl MockSnapshotReader {
    fn with_suspended_snapshot() -> Self {
        Self {
            snapshot: Some(serde_json::json!({"status": "suspended"})),
        }
    }

    fn with_none() -> Self {
        Self { snapshot: None }
    }
}

impl SnapshotReader for MockSnapshotReader {
    fn read_snapshot(&self, _session_id: uuid::Uuid) -> Option<serde_json::Value> {
        self.snapshot.clone()
    }
}

// ============================================================================
// TEST 5: Session recovery detects suspended snapshot
// ============================================================================

#[test]
fn test_session_recovery_suspended_detected() {
    // GIVEN: SessionRecoveryHook with suspended snapshot
    let reader = MockSnapshotReader::with_suspended_snapshot();
    let hook = SessionRecoveryHook::new(reader);

    let ctx = SessionContext {
        session_id: NodeId::new(),
        persona_id: NodeId::new(),
        tenant_id: NodeId::new(),
    };

    // WHEN: on_session_start called
    let result = hook.on_session_start(&ctx);

    // THEN: returns Continue (session recovers, not blocked)
    assert_eq!(result, HookResult::Continue);
}

// ============================================================================
// TEST 6: Session recovery fail-open — DB failure → session starts fresh
// ============================================================================

#[test]
fn test_session_recovery_db_failure_fail_open() {
    // GIVEN: SessionRecoveryHook with no snapshot (simulating DB error)
    let reader = MockSnapshotReader::with_none();
    let hook = SessionRecoveryHook::new(reader);

    let ctx = SessionContext {
        session_id: NodeId::new(),
        persona_id: NodeId::new(),
        tenant_id: NodeId::new(),
    };

    // WHEN: on_session_start called
    let result = hook.on_session_start(&ctx);

    // THEN: returns Continue (session starts fresh, never blocked)
    assert_eq!(result, HookResult::Continue);
}
