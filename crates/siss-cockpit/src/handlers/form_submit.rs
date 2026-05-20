use crate::a2ui::form_handler::FormHandler;
use crate::state::CockpitEvent;
use crate::state::CockpitState;
use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::Json;
use chrono::Utc;
use siss_agent_shell::a2ui::FormSubmission;
use uuid::Uuid;

#[derive(serde::Serialize)]
pub struct FormResponseBody {
    pub submission_id: String,
    pub status: String,
}

pub async fn form_submit(
    Path(agent_id): Path<Uuid>,
    State(state): State<CockpitState>,
    Json(submission): Json<FormSubmission>,
) -> (StatusCode, Json<FormResponseBody>) {
    let handler = FormHandler::new();

    match handler.process(&submission) {
        Ok(response) => {
            let event = CockpitEvent {
                event_type: "form_submitted".to_string(),
                agent_id: Some(agent_id.to_string()),
                payload: serde_json::json!({
                    "submission_id": response.submission_id,
                    "form_id": submission.form_id,
                    "task_id": submission.task_id,
                    "values": submission.values,
                }),
                timestamp: Utc::now(),
            };
            state.emit(event);

            (
                StatusCode::ACCEPTED,
                Json(FormResponseBody {
                    submission_id: response.submission_id,
                    status: response.status,
                }),
            )
        }
        Err(err) => (
            StatusCode::BAD_REQUEST,
            Json(FormResponseBody {
                submission_id: String::new(),
                status: format!("error: {}", err),
            }),
        ),
    }
}
