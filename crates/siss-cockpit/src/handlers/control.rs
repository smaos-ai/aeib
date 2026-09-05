use crate::state::CockpitEvent;
use crate::state::CockpitState;
use axum::extract::{Path, State};
use axum::http::StatusCode;
use chrono::Utc;
use uuid::Uuid;

pub async fn pause_agent(Path(id): Path<Uuid>, State(state): State<CockpitState>) -> StatusCode {
    let event = CockpitEvent {
        event_type: "agent_paused".to_string(),
        agent_id: Some(id.to_string()),
        payload: serde_json::json!({}),
        timestamp: Utc::now(),
    };
    state.emit(event);
    StatusCode::ACCEPTED
}

pub async fn resume_agent(Path(id): Path<Uuid>, State(state): State<CockpitState>) -> StatusCode {
    let event = CockpitEvent {
        event_type: "agent_resumed".to_string(),
        agent_id: Some(id.to_string()),
        payload: serde_json::json!({}),
        timestamp: Utc::now(),
    };
    state.emit(event);
    StatusCode::ACCEPTED
}

pub async fn abort_agent(Path(id): Path<Uuid>, State(state): State<CockpitState>) -> StatusCode {
    let event = CockpitEvent {
        event_type: "agent_aborted".to_string(),
        agent_id: Some(id.to_string()),
        payload: serde_json::json!({}),
        timestamp: Utc::now(),
    };
    state.emit(event);
    StatusCode::ACCEPTED
}
