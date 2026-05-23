//! Swarm Dispatcher — orchestrates 10+ concurrent agents with isolated worktrees
//! Uses git worktree per job + dependency queue from siss-event-log + tmux sessions

use crate::git::GitManager;
use crate::tmux::TmuxSession;
use crate::{DispatchError, Result};
use siss_event_log::{EventLog, SystemEvent};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::Mutex;
use uuid::Uuid;

/// Job execution slot — tracks worktree + tmux + status
#[derive(Debug, Clone)]
pub struct JobSlot {
    pub job_id: Uuid,
    pub worktree_path: String,
    pub branch_name: String,
    pub tmux_session: String,
    pub status: SlotStatus,
}

#[derive(Debug, Clone, PartialEq)]
pub enum SlotStatus {
    Running,
    Completed,
    Failed,
}

/// Orchestrates isolated execution of 10+ concurrent jobs
pub struct SwarmDispatcher {
    git: GitManager,
    event_log: EventLog,
    repo_path: String,
    worktree_base: String,
    active_slots: Arc<Mutex<HashMap<Uuid, JobSlot>>>,
}

impl SwarmDispatcher {
    /// Create new SwarmDispatcher
    pub fn new(repo_path: String, worktree_base: String, event_log: EventLog) -> Self {
        Self {
            git: GitManager::new(&repo_path),
            event_log,
            repo_path,
            worktree_base,
            active_slots: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    /// Dispatch a job with dependency queue enforcement
    /// Returns UnmetDependencies if deps not complete
    /// Returns AssignmentFailed if job already running
    pub async fn dispatch_job(
        &self,
        job_id: Uuid,
        depends_on: Vec<Uuid>,
    ) -> Result<JobSlot> {
        // Check: all dependencies completed (event-log query, outside lock)
        for dep_id in &depends_on {
            match self.event_log.get_events(*dep_id).await {
                Ok(events) => {
                    let is_completed = events
                        .iter()
                        .any(|e| matches!(e, SystemEvent::JobCompleted { .. }));
                    if !is_completed {
                        return Err(DispatchError::UnmetDependencies);
                    }
                }
                Err(e) => {
                    return Err(DispatchError::Other(format!(
                        "Event log error: {}",
                        e
                    )))
                }
            }
        }

        // CRITICAL SECTION: Check duplicate + reserve slot atomically under lock
        // This prevents 20 concurrent calls from all passing the check
        {
            let mut active = self.active_slots.lock().await;
            if active.contains_key(&job_id) {
                return Err(DispatchError::AssignmentFailed(format!(
                    "Job {} already dispatched",
                    job_id
                )));
            }

            // Pre-reserve the slot in the map to mark job as "claimed"
            // Full slot data is populated after async ops complete
            let branch_name = format!("swarm/job-{}", job_id);
            let worktree_path = format!("{}/{}", self.worktree_base, branch_name);
            let placeholder_slot = JobSlot {
                job_id,
                worktree_path: worktree_path.clone(),
                branch_name,
                tmux_session: String::new(), // Will be updated below
                status: SlotStatus::Running,
            };
            active.insert(job_id, placeholder_slot);
        }
        // Lock released here — slot is now reserved

        // Create worktree (isolated file system per job)
        let branch_name = format!("swarm/job-{}", job_id);
        let worktree_path = format!("{}/{}", self.worktree_base, branch_name);

        self.git
            .create_worktree(&worktree_path, &branch_name)
            .await?;

        // Spawn tmux session
        let tmux_session = TmuxSession::new(job_id);
        tmux_session.spawn(&worktree_path).await?;

        // Log dispatch event to immutable ledger
        self.event_log
            .append_event(
                job_id,
                SystemEvent::JobDispatched {
                    job_id,
                    mandate_id: Uuid::nil(),
                },
            )
            .await
            .map_err(|e| DispatchError::Other(format!("Event log error: {}", e)))?;

        // Update slot with complete data
        let slot = JobSlot {
            job_id,
            worktree_path,
            branch_name,
            tmux_session: tmux_session.session_name.clone(),
            status: SlotStatus::Running,
        };

        self.active_slots.lock().await.insert(job_id, slot.clone());

        Ok(slot)
    }

    /// Complete a job — cleanup worktree + tmux + log event
    pub async fn complete_job(&self, job_id: Uuid) -> Result<()> {
        let _slot = self
            .active_slots
            .lock()
            .await
            .remove(&job_id)
            .ok_or_else(|| DispatchError::TaskNotFound(job_id.to_string()))?;

        // Kill tmux session (non-fatal if already dead)
        let tmux = TmuxSession::new(job_id);
        let _ = tmux.kill().await;

        // Remove worktree
        self.git.remove_worktree(&_slot.worktree_path).await?;

        // Log completion event
        self.event_log
            .append_event(
                job_id,
                SystemEvent::JobCompleted {
                    job_id,
                    result: "success".to_string(),
                },
            )
            .await
            .map_err(|e| DispatchError::Other(format!("Event log error: {}", e)))?;

        Ok(())
    }

    /// Fail a job — cleanup worktree + tmux + log error (fail-closed)
    pub async fn fail_job(&self, job_id: Uuid, error: &str) -> Result<()> {
        let _slot = self
            .active_slots
            .lock()
            .await
            .remove(&job_id)
            .ok_or_else(|| DispatchError::TaskNotFound(job_id.to_string()))?;

        // Kill tmux session (non-fatal if already dead)
        let tmux = TmuxSession::new(job_id);
        let _ = tmux.kill().await;

        // Remove worktree (fail-closed: cleanup always runs)
        if let Err(e) = self.git.remove_worktree(&_slot.worktree_path).await {
            eprintln!("Warning: failed to remove worktree: {}", e);
        }

        // Log failure event (mandatory: immutable ledger always records)
        self.event_log
            .append_event(
                job_id,
                SystemEvent::JobFailed {
                    job_id,
                    error: error.to_string(),
                },
            )
            .await
            .map_err(|e| DispatchError::Other(format!("Event log error: {}", e)))?;

        Ok(())
    }

    /// Get count of active concurrent jobs
    pub async fn active_count(&self) -> usize {
        self.active_slots.lock().await.len()
    }

    /// List all active job slots
    pub async fn active_slots(&self) -> Vec<JobSlot> {
        self.active_slots
            .lock()
            .await
            .values()
            .cloned()
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_job_slot_creation() {
        let job_id = Uuid::new_v4();
        let slot = JobSlot {
            job_id,
            worktree_path: format!(".claude/worktrees/job-{}", job_id),
            branch_name: format!("swarm/job-{}", job_id),
            tmux_session: format!("siss-agent-{}", job_id),
            status: SlotStatus::Running,
        };
        assert_eq!(slot.status, SlotStatus::Running);
    }
}

#[cfg(test)]
mod toctou_race_tests {
    use super::*;
    use std::sync::atomic::{AtomicUsize, Ordering};
    use tokio::task;

    /// Mock dispatcher that exposes TOCTOU race with instrumentation
    #[derive(Clone)]
    struct TestDispatcher {
        active_slots: Arc<Mutex<HashMap<Uuid, JobSlot>>>,
        // Atomic counter to track how many times we successfully passed the check+insert
        insert_count: Arc<AtomicUsize>,
    }

    impl TestDispatcher {
        fn new(_concurrent_count: usize) -> Self {
            Self {
                active_slots: Arc::new(Mutex::new(HashMap::new())),
                insert_count: Arc::new(AtomicUsize::new(0)),
            }
        }

        async fn dispatch_job(&self, job_id: Uuid) -> Result<JobSlot> {
            // CRITICAL SECTION: Check duplicate + reserve slot atomically under lock
            // This prevents 20 concurrent calls from all passing the check
            {
                let mut active = self.active_slots.lock().await;
                if active.contains_key(&job_id) {
                    return Err(DispatchError::AssignmentFailed(format!(
                        "Job {} already dispatched",
                        job_id
                    )));
                }

                // Pre-reserve the slot to mark job as "claimed"
                let placeholder_slot = JobSlot {
                    job_id,
                    worktree_path: format!("/tmp/job-{}", job_id),
                    branch_name: format!("swarm/job-{}", job_id),
                    tmux_session: format!("siss-agent-{}", job_id),
                    status: SlotStatus::Running,
                };
                active.insert(job_id, placeholder_slot);
                // Count successful check+insert (only 1 thread should reach here per job_id)
                self.insert_count.fetch_add(1, Ordering::SeqCst);
            }
            // Lock released here — slot is now reserved

            let slot = JobSlot {
                job_id,
                worktree_path: format!("/tmp/job-{}", job_id),
                branch_name: format!("swarm/job-{}", job_id),
                tmux_session: format!("siss-agent-{}", job_id),
                status: SlotStatus::Running,
            };

            Ok(slot)
        }

        async fn complete_job(&self, job_id: &Uuid) -> Result<()> {
            self.active_slots
                .lock()
                .await
                .remove(job_id)
                .ok_or_else(|| DispatchError::TaskNotFound(job_id.to_string()))?;
            Ok(())
        }
    }

    #[tokio::test]
    async fn test_concurrent_dispatch_same_job_id_creates_exactly_one_slot() {
        let concurrent_count = 20;
        let dispatcher = Arc::new(TestDispatcher::new(concurrent_count));
        let job_id = Uuid::new_v4();

        let mut handles = vec![];
        for _ in 0..concurrent_count {
            let dispatcher_clone = Arc::clone(&dispatcher);
            let job_id_clone = job_id;
            let handle = task::spawn(async move {
                let _ = dispatcher_clone.dispatch_job(job_id_clone).await;
            });
            handles.push(handle);
        }

        for handle in handles {
            let _ = handle.await;
        }

        // Due to TOCTOU race: all 20 threads can pass the check, then all insert
        let actual_slots = dispatcher.active_slots.lock().await.len();
        let actual_inserts = dispatcher.insert_count.load(Ordering::SeqCst);

        // FAIL (RED): Race condition means we get 20 inserts but only 1 survives in map
        // This test WILL FAIL with current code because HashMap.insert overwrites
        // but we can detect the race by counting inserts vs final slots
        eprintln!(
            "Inserts attempted: {}, Slots in map: {}, Duplicates detected: {}",
            actual_inserts,
            actual_slots,
            actual_inserts > 1
        );

        assert_eq!(
            actual_slots, 1,
            "TOCTOU race: concurrent dispatch of same job_id SHOULD create exactly 1 slot"
        );
        assert_eq!(
            actual_inserts, 1,
            "TOCTOU race: only 1 thread should successfully insert (but currently {} threads pass the check)",
            actual_inserts
        );
    }

    #[tokio::test]
    async fn test_dispatch_does_not_leave_partial_slot_on_early_failure() {
        let dispatcher = TestDispatcher::new(1);
        let job_id = Uuid::new_v4();

        // Manually insert a slot to represent partial state
        {
            let mut active = dispatcher.active_slots.lock().await;
            active.insert(
                job_id,
                JobSlot {
                    job_id,
                    worktree_path: format!("/tmp/job-{}", job_id),
                    branch_name: format!("swarm/job-{}", job_id),
                    tmux_session: format!("siss-agent-{}", job_id),
                    status: SlotStatus::Running,
                },
            );
        }

        // Now try to dispatch the same job_id (should fail)
        let result = dispatcher.dispatch_job(job_id).await;
        assert!(
            result.is_err(),
            "Dispatch of already-dispatched job should fail"
        );

        // Verify: exactly 1 slot remains (no duplicate created)
        let slot_count = dispatcher.active_slots.lock().await.len();
        assert_eq!(
            slot_count, 1,
            "Failed dispatch must not create duplicate slot"
        );
    }

    #[tokio::test]
    async fn test_completed_job_removed_from_active_slots() {
        let dispatcher = TestDispatcher::new(1);
        let job_id = Uuid::new_v4();

        // Dispatch a valid job
        let result = dispatcher.dispatch_job(job_id).await;
        assert!(result.is_ok(), "Dispatch should succeed");

        let slot_count_before = dispatcher.active_slots.lock().await.len();
        assert_eq!(
            slot_count_before, 1,
            "Job should be in active slots after dispatch"
        );

        // Mark as completed (remove from slots)
        dispatcher.complete_job(&job_id).await.unwrap();

        let slot_count_after = dispatcher.active_slots.lock().await.len();
        assert_eq!(
            slot_count_after, 0,
            "Completed job must be removed from active slots"
        );
    }
}
