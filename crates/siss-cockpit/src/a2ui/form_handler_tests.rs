use crate::a2ui::form_handler::FormHandler;
use serde_json::json;
use siss_agent_shell::a2ui::FormSubmission;
use uuid::Uuid;

#[test]
fn test_form_handler_exists() {
    // Simple test to verify compilation
    assert_eq!(1, 1);
}

#[test]
fn test_rejects_submission_with_missing_task_id() {
    let submission = FormSubmission {
        task_id: Uuid::nil(),
        form_id: "approval_form".to_string(),
        values: json!({}),
    };

    let handler = FormHandler::new();
    let result = handler.process(&submission);

    assert!(result.is_err());
    assert!(result.unwrap_err().contains("task_id"));
}

#[test]
fn test_rejects_submission_with_empty_form_id() {
    let submission = FormSubmission {
        task_id: Uuid::new_v4(),
        form_id: "".to_string(),
        values: json!({}),
    };

    let handler = FormHandler::new();
    let result = handler.process(&submission);

    assert!(result.is_err());
    assert!(result.unwrap_err().contains("form_id"));
}

#[test]
fn test_processes_form_with_complex_values() {
    let submission = FormSubmission {
        task_id: Uuid::new_v4(),
        form_id: "complex_form".to_string(),
        values: json!({
            "email": "test@example.com",
            "selections": ["a", "b", "c"],
            "nested": {
                "field1": "value1"
            }
        }),
    };

    let handler = FormHandler::new();
    let result = handler.process(&submission);

    assert!(result.is_ok());
}

#[test]
fn test_returns_submission_id_on_success() {
    let submission = FormSubmission {
        task_id: Uuid::new_v4(),
        form_id: "test_form".to_string(),
        values: json!({}),
    };

    let handler = FormHandler::new();
    let result = handler.process(&submission).unwrap();

    assert!(!result.submission_id.is_empty());
    assert_eq!(result.status, "accepted");
}
