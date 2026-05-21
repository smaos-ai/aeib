use serde::{Deserialize, Serialize};
use std::fmt;
use uuid::Uuid;

pub type EventId = Uuid;
pub type JobId = Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum SystemEvent {
    JobDispatched {
        job_id: Uuid,
        mandate_id: Uuid,
    },
    JobCompleted {
        job_id: Uuid,
        result: String,
    },
    JobFailed {
        job_id: Uuid,
        error: String,
    },
    AccessDecision {
        actor: Uuid,
        decision: String,
    },
}

impl fmt::Display for SystemEvent {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            SystemEvent::JobDispatched { job_id, mandate_id } => {
                write!(f, "JobDispatched(job={}, mandate={})", job_id, mandate_id)
            }
            SystemEvent::JobCompleted { job_id, result } => {
                write!(f, "JobCompleted(job={}, result={})", job_id, result)
            }
            SystemEvent::JobFailed { job_id, error } => {
                write!(f, "JobFailed(job={}, error={})", job_id, error)
            }
            SystemEvent::AccessDecision { actor, decision } => {
                write!(f, "AccessDecision(actor={}, decision={})", actor, decision)
            }
        }
    }
}

#[derive(Debug, Clone)]
pub struct EventFilter {
    pub job_id: Option<Uuid>,
    pub event_type: Option<String>,
}

impl EventFilter {
    pub fn all() -> Self {
        Self {
            job_id: None,
            event_type: None,
        }
    }

    pub fn by_job(job_id: Uuid) -> Self {
        Self {
            job_id: Some(job_id),
            event_type: None,
        }
    }
}

#[derive(Debug, thiserror::Error)]
pub enum LogError {
    #[error("Database error: {0}")]
    DatabaseError(String),

    #[error("Immutable log violation: {0}")]
    ImmutableLogViolation(String),

    #[error("Not found: {0}")]
    NotFound(String),

    #[error("Invalid input: {0}")]
    InvalidInput(String),
}
