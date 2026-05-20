use siss_agent_shell::a2ui::FormSubmission;

pub struct FormHandler;

#[derive(Debug)]
pub struct FormResponse {
    pub submission_id: String,
    pub status: String,
}

impl FormHandler {
    pub fn new() -> Self {
        FormHandler
    }

    pub fn process(&self, submission: &FormSubmission) -> Result<FormResponse, String> {
        if submission.task_id == uuid::Uuid::nil() {
            return Err("task_id must not be nil".to_string());
        }

        if submission.form_id.is_empty() {
            return Err("form_id must not be empty".to_string());
        }

        Ok(FormResponse {
            submission_id: uuid::Uuid::new_v4().to_string(),
            status: "accepted".to_string(),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use uuid::Uuid;

    #[test]
    fn test_accepts_valid_form_submission() {
        let submission = FormSubmission {
            task_id: Uuid::new_v4(),
            form_id: "approval_form".to_string(),
            values: json!({
                "approved": true,
                "reason": "test"
            }),
        };

        let handler = FormHandler::new();
        let result = handler.process(&submission);

        assert!(result.is_ok());
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
}
