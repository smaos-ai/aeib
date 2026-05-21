// HTTP handlers — SSE stream and control endpoints

pub mod stream;
pub mod control;
pub mod form_submit;
pub mod dashboard;
// pub mod projections; // Phase 24: commented due to PgPool blocker
pub mod router_handler;
