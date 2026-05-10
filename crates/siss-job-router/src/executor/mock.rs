use std::future::Future;
use std::pin::Pin;

use super::{ExecutionError, Executor, TaskContext};
use crate::types::ExecutionResult;

/// A deterministic mock executor for tests.
pub struct MockExecutor;

impl Executor for MockExecutor {
    fn execute(
        &self,
        context: TaskContext,
    ) -> Pin<Box<dyn Future<Output = Result<ExecutionResult, ExecutionError>> + Send + '_>> {
        Box::pin(async move {
            Ok(ExecutionResult {
                output: serde_json::json!({
                    "status": "mock_completed",
                    "task_id": context.task_id.to_string(),
                }),
                token_cost: 100,
                duration_ms: 10,
            })
        })
    }
}

/// A mock executor that always fails, for testing error paths.
pub struct FailingExecutor {
    pub error_message: String,
}

impl Executor for FailingExecutor {
    fn execute(
        &self,
        _context: TaskContext,
    ) -> Pin<Box<dyn Future<Output = Result<ExecutionResult, ExecutionError>> + Send + '_>> {
        Box::pin(async move {
            Err(ExecutionError {
                message: self.error_message.clone(),
            })
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use siss_graph_core::node::execution::{ComplexityClass, HardwareTarget};

    fn make_context() -> TaskContext {
        TaskContext {
            task_id: uuid::Uuid::nil(),
            intent: "test task".into(),
            complexity_class: ComplexityClass::Simple,
            hardware_target: HardwareTarget::LocalMlx,
            tenant_id: uuid::Uuid::nil(),
            visible_field: None,
        }
    }

    #[tokio::test]
    async fn test_mock_executor_returns_deterministic_output() {
        let executor = MockExecutor;
        let result = executor.execute(make_context()).await.unwrap();
        assert_eq!(result.token_cost, 100);
        assert_eq!(result.duration_ms, 10);
        assert_eq!(result.output["status"], "mock_completed");
    }

    #[tokio::test]
    async fn test_mock_executor_includes_task_id() {
        let mut ctx = make_context();
        ctx.task_id = uuid::Uuid::new_v4();
        let executor = MockExecutor;
        let result = executor.execute(ctx.clone()).await.unwrap();
        assert_eq!(result.output["task_id"], ctx.task_id.to_string());
    }

    #[tokio::test]
    async fn test_failing_executor_returns_error() {
        let executor = FailingExecutor {
            error_message: "GPU unavailable".into(),
        };
        let result = executor.execute(make_context()).await;
        assert!(result.is_err());
        assert_eq!(result.unwrap_err().message, "GPU unavailable");
    }
}
