use crate::handlers::{control, form_submit, stream};
use crate::state::CockpitState;
use axum::{
    routing::{get, post},
    Router,
};

pub fn create_router(state: CockpitState) -> Router {
    Router::new()
        .route("/api/agents/stream", get(stream::stream_agent_events))
        .route("/api/agents/:id/pause", post(control::pause_agent))
        .route("/api/agents/:id/resume", post(control::resume_agent))
        .route("/api/agents/:id/abort", post(control::abort_agent))
        .route(
            "/api/agents/:id/form-submit",
            post(form_submit::form_submit),
        )
        .with_state(state)
}
