// Task FSM validation is implemented directly on Task::transition_to() in node/execution.rs.
// This module re-exports the relevant types for convenience.
pub use crate::node::execution::{InvalidTransition, Task, TaskStatus};

#[cfg(test)]
mod tests {
    use super::*;
    use crate::node::NodeId;
    use crate::node::execution::ComplexityClass;

    #[test]
    fn test_full_happy_path() {
        let mut task = Task::new("test".into(), ComplexityClass::Moderate, NodeId::new());
        assert!(task.transition_to(TaskStatus::Authorized).is_ok());
        assert!(task.transition_to(TaskStatus::Routing).is_ok());
        assert!(task.transition_to(TaskStatus::Executing).is_ok());
        assert!(task.transition_to(TaskStatus::Guarding).is_ok());
        assert!(task.transition_to(TaskStatus::Crystallizing).is_ok());
        assert!(task.transition_to(TaskStatus::Completed).is_ok());
    }

    #[test]
    fn test_cannot_transition_from_completed() {
        let mut task = Task::new("test".into(), ComplexityClass::Trivial, NodeId::new());
        task.transition_to(TaskStatus::Authorized).unwrap();
        task.transition_to(TaskStatus::Routing).unwrap();
        task.transition_to(TaskStatus::Executing).unwrap();
        task.transition_to(TaskStatus::Guarding).unwrap();
        task.transition_to(TaskStatus::Crystallizing).unwrap();
        task.transition_to(TaskStatus::Completed).unwrap();
        assert!(task.transition_to(TaskStatus::Pending).is_err());
    }

    #[test]
    fn test_cannot_transition_from_failed() {
        let mut task = Task::new("test".into(), ComplexityClass::Trivial, NodeId::new());
        task.transition_to(TaskStatus::Failed).unwrap();
        assert!(task.transition_to(TaskStatus::Pending).is_err());
    }
}
