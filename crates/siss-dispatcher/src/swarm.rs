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
        // Check: not already dispatched (fail-closed: reject duplicates)
        {
            let active = self.active_slots.lock().await;
            if active.contains_key(&job_id) {
                return Err(DispatchError::AssignmentFailed(format!(
                    "Job {} already dispatched",
                    job_id
                )));
            }
        }

        // Check: all dependencies completed (event-log query)
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

        // Insert into active slots
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
