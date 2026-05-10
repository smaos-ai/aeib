use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use thiserror::Error;

use crate::node::NodeId;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ComplexityClass {
    Trivial,
    Simple,
    Moderate,
    Complex,
    Heavy,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum TaskStatus {
    Pending,
    Authorized,
    Routing,
    Executing,
    Guarding,
    Crystallizing,
    Completed,
    Failed,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum HardwareTarget {
    LocalMlx,
    RemoteFrontier,
    Hybrid,
}

#[derive(Debug, Error)]
#[error("invalid task transition from {from:?} to {to:?}")]
pub struct InvalidTransition {
    pub from: TaskStatus,
    pub to: TaskStatus,
}

impl TaskStatus {
    /// Returns the set of valid next states from this state.
    fn valid_next(&self) -> &'static [TaskStatus] {
        match self {
            Self::Pending => &[Self::Authorized, Self::Failed],
            Self::Authorized => &[Self::Routing, Self::Failed],
            Self::Routing => &[Self::Executing, Self::Failed],
            Self::Executing => &[Self::Guarding, Self::Failed],
            Self::Guarding => &[Self::Crystallizing, Self::Failed],
            Self::Crystallizing => &[Self::Completed, Self::Failed],
            Self::Completed => &[],
            Self::Failed => &[],
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Task {
    pub id: NodeId,
    pub tenant_id: NodeId,
    pub intent: String,
    pub complexity_class: ComplexityClass,
    pub status: TaskStatus,
    pub hardware_target: HardwareTarget,
    pub token_cost: i64,
    pub created_at: DateTime<Utc>,
    pub completed_at: Option<DateTime<Utc>>,
}

impl Task {
    pub fn new(intent: String, complexity_class: ComplexityClass, tenant_id: NodeId) -> Self {
        Self {
            id: NodeId::new(),
            tenant_id,
            intent,
            complexity_class,
            status: TaskStatus::Pending,
            hardware_target: HardwareTarget::LocalMlx,
            token_cost: 0,
            created_at: Utc::now(),
            completed_at: None,
        }
    }

    /// Attempt to transition to a new status. Returns an error if the transition is invalid.
    pub fn transition_to(&mut self, new_status: TaskStatus) -> Result<(), InvalidTransition> {
        if self.status.valid_next().contains(&new_status) {
            self.status = new_status;
            if matches!(new_status, TaskStatus::Completed | TaskStatus::Failed) {
                self.completed_at = Some(Utc::now());
            }
            Ok(())
        } else {
            Err(InvalidTransition {
                from: self.status,
                to: new_status,
            })
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum SessionStatus {
    Active,
    Suspended,
    Completed,
    Evicted,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Session {
    pub id: NodeId,
    pub tenant_id: NodeId,
    pub started_at: DateTime<Utc>,
    pub token_budget: i64,
    pub tokens_consumed: i64,
    pub active_persona_id: NodeId,
    pub visible_field_snapshot: serde_json::Value,
    pub status: SessionStatus,
}

impl Session {
    pub fn new(token_budget: i64, active_persona_id: NodeId, tenant_id: NodeId) -> Self {
        Self {
            id: NodeId::new(),
            tenant_id,
            started_at: Utc::now(),
            token_budget,
            tokens_consumed: 0,
            active_persona_id,
            visible_field_snapshot: serde_json::Value::Null,
            status: SessionStatus::Active,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_task() {
        let tenant_id = NodeId::new();
        let task = Task::new(
            "Summarize this document".into(),
            ComplexityClass::Simple,
            tenant_id,
        );
        assert_eq!(task.intent, "Summarize this document");
        assert_eq!(task.complexity_class, ComplexityClass::Simple);
        assert_eq!(task.status, TaskStatus::Pending);
        assert_eq!(task.hardware_target, HardwareTarget::LocalMlx);
        assert_eq!(task.token_cost, 0);
    }

    #[test]
    fn test_task_transition_valid() {
        let tenant_id = NodeId::new();
        let mut task = Task::new("test".into(), ComplexityClass::Trivial, tenant_id);
        assert!(task.transition_to(TaskStatus::Authorized).is_ok());
        assert_eq!(task.status, TaskStatus::Authorized);
        assert!(task.transition_to(TaskStatus::Routing).is_ok());
        assert!(task.transition_to(TaskStatus::Executing).is_ok());
        assert!(task.transition_to(TaskStatus::Guarding).is_ok());
        assert!(task.transition_to(TaskStatus::Crystallizing).is_ok());
        assert!(task.transition_to(TaskStatus::Completed).is_ok());
        assert!(task.completed_at.is_some());
    }

    #[test]
    fn test_task_transition_invalid() {
        let tenant_id = NodeId::new();
        let mut task = Task::new("test".into(), ComplexityClass::Trivial, tenant_id);
        let result = task.transition_to(TaskStatus::Executing);
        assert!(result.is_err());
        assert_eq!(task.status, TaskStatus::Pending);
    }

    #[test]
    fn test_task_transition_to_failed_from_any() {
        let tenant_id = NodeId::new();
        let mut task = Task::new("test".into(), ComplexityClass::Trivial, tenant_id);
        assert!(task.transition_to(TaskStatus::Authorized).is_ok());
        assert!(task.transition_to(TaskStatus::Failed).is_ok());
        assert_eq!(task.status, TaskStatus::Failed);
        assert!(task.completed_at.is_some());
    }

    #[test]
    fn test_create_session() {
        let tenant_id = NodeId::new();
        let persona_id = NodeId::new();
        let session = Session::new(100_000, persona_id, tenant_id);
        assert_eq!(session.token_budget, 100_000);
        assert_eq!(session.tokens_consumed, 0);
        assert_eq!(session.active_persona_id, persona_id);
        assert_eq!(session.status, SessionStatus::Active);
    }
}
