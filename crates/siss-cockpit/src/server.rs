use crate::handlers::{control, dashboard, form_submit, stream, router_handler, ag_ui_streaming}; // projections removed due to Phase 24 pool blocker
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
        .route("/api/router/route", post(router_handler::post_route))
        .route("/api/rce/stream", get(ag_ui_streaming::get_rce_stream))
        // Phase 24 projections routes — handlers need PgPool from state (currently commented)
        // TODO: Wire PgPool into CockpitState and uncomment these routes
        // .route("/api/graph/projections/agent-actions", get(projections::get_agent_actions))
        // .route("/api/graph/projections/anomalies", get(projections::get_anomalies))
        // .route("/api/graph/projections/recovery", get(projections::get_recovery))
        .with_state(state)
}
