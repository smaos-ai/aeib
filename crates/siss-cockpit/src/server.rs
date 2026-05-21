use crate::handlers::{control, dashboard, form_submit, stream, projections};
use crate::state::CockpitState;
use axum::{
    routing::{get, post},
    Router,
};

pub fn create_router(state: CockpitState) -> Router {
    Router::new()
        .route("/", get(dashboard::dashboard))
        .route("/api/agents/stream", get(stream::stream_agent_events))
        .route("/api/agents/:id/pause", post(control::pause_agent))
        .route("/api/agents/:id/resume", post(control::resume_agent))
        .route("/api/agents/:id/abort", post(control::abort_agent))
        .route(
            "/api/agents/:id/form-submit",
            post(form_submit::form_submit),
        )
        .route("/api/graph/projections/agent-actions", get(projections::get_agent_actions))
        .route("/api/graph/projections/anomalies", get(projections::get_anomalies))
        .route("/api/graph/projections/recovery", get(projections::get_recovery))
        .with_state(state)
}
