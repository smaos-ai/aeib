use crate::api::ag_ui::{
    get_state_projection, health_check, stream_lora_swap_events, submit_operator_decision,
    AgUiState,
};
use crate::operator::OperatorCockpit;
use axum::routing::{get, post};
use axum::Router;
use std::sync::Arc;

pub fn create_ag_ui_router(cockpit: Arc<OperatorCockpit>) -> Router {
    let state = AgUiState { cockpit };

    Router::new()
        .route("/api/rce/stream", get(stream_lora_swap_events))
        .route("/api/rce/decision", post(submit_operator_decision))
        .route("/api/rce/:task_id/projection", get(get_state_projection))
        .route("/health", get(health_check))
        .with_state(state)
}
