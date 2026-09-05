pub mod errors;
pub mod routes;

use axum::{Router, routing::get};
use sqlx::PgPool;

use routes::{get_agent_actions, get_anomalies, get_correlations, get_recovery};

/// Create the Axum router with all routes
pub fn create_router(pool: PgPool) -> Router {
    Router::new()
        .route(
            "/api/graph/projections/agent_actions",
            get(get_agent_actions),
        )
        .route("/api/graph/projections/anomalies", get(get_anomalies))
        .route("/api/graph/projections/recovery", get(get_recovery))
        .route("/api/graph/correlations", get(get_correlations))
        .with_state(pool)
}
