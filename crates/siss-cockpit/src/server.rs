use crate::handlers::{
    ag_ui_streaming, anomaly_stream, control, dashboard, form_submit, projections, rce_decision,
    rce_projection, router_handler, stream,
};
use crate::state::CockpitState;
use axum::{
    Router,
    routing::{get, post},
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
        .route("/api/rce/decision", post(rce_decision::post_rce_decision))
        .route(
            "/api/rce/:workflow_id/projection",
            get(rce_projection::get_rce_projection),
        )
        // Phase 24 projections routes — PgPool now wired into CockpitState
        .route(
            "/api/graph/projections/agent-actions",
            get(projections::get_agent_actions),
        )
        .route(
            "/api/graph/projections/anomalies",
            get(projections::get_anomalies),
        )
        .route(
            "/api/graph/projections/recovery",
            get(projections::get_recovery),
        )
        // Phase 38 anomaly stream SSE endpoint
        .route(
            "/api/anomalies/stream",
            get(anomaly_stream::get_anomaly_stream),
        )
        .with_state(state)
}
