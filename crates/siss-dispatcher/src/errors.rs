use thiserror::Error;

/// Dispatcher operation result type
pub type Result<T> = std::result::Result<T, DispatchError>;

#[derive(Error, Debug)]
pub enum DispatchError {
    #[error("Task not found: {0}")]
    TaskNotFound(String),

    #[error("Agent not found: {0}")]
    AgentNotFound(String),

    #[error("No available agents")]
    NoAvailableAgents,

    #[error("Task has unmet dependencies")]
    UnmetDependencies,

    #[error("Cannot assign task: agent already has task assigned")]
    AgentAlreadyAssigned,

    #[error("Task assignment failed: {0}")]
    AssignmentFailed(String),

    #[error("Worktree operation failed: {0}")]
    WorktreeError(String),

    #[error("Git operation failed: {0}")]
    GitError(String),

    #[error("Merge conflict detected: {files:?}")]
    MergeConflict { files: Vec<String> },

    #[error("Merge failed: {0}")]
    MergeFailed(String),

    #[error("File lock error: {0}")]
    LockError(String),

    #[error("Lock timeout")]
    LockTimeout,

    #[error("Task timeout")]
    TaskTimeout,

    #[error("JSON serialization error: {0}")]
    JsonError(#[from] serde_json::Error),

    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),

    #[error("Failed to spawn process: {0}")]
    ProcessError(String),

    #[error("Invalid configuration: {0}")]
    InvalidConfig(String),

    #[error("Queue error: {0}")]
    QueueError(String),

    #[error("Merge order violation: circular dependency detected")]
    CircularDependency,

    #[error("Rollback failed: {0}")]
    RollbackFailed(String),

    #[error("Unknown error: {0}")]
    Other(String),
}
