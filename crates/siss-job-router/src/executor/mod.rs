pub mod mock;

use std::future::Future;
use std::pin::Pin;

use serde::{Deserialize, Serialize};
use thiserror::Error;
use uuid::Uuid;

use siss_graph_core::node::execution::{ComplexityClass, HardwareTarget};

use crate::types::ExecutionResult;

/// Context provided to an executor for task execution.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskContext {
    pub task_id: Uuid,
    pub intent: String,
    pub complexity_class: ComplexityClass,
    pub hardware_target: HardwareTarget,
    pub tenant_id: Uuid,
    pub visible_field: Option<serde_json::Value>,
}

#[derive(Debug, Error)]
#[error("execution error: {message}")]
pub struct ExecutionError {
    pub message: String,
}

/// Trait for executing tasks on a hardware backend.
pub trait Executor: Send + Sync {
    fn execute(
        &self,
        context: TaskContext,
    ) -> Pin<Box<dyn Future<Output = Result<ExecutionResult, ExecutionError>> + Send + '_>>;
}
