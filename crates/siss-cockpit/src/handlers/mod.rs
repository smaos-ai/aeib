// HTTP handlers — SSE stream and control endpoints

pub mod stream;
pub mod control;
pub mod form_submit;
pub mod dashboard;
// pub mod projections; // Phase 24: commented due to PgPool blocker
pub mod router_handler;
pub mod router_integration_tests;
pub mod ag_ui_streaming;
pub mod ag_ui_streaming_integration;
pub mod rate_limiting;
pub mod rate_limiting_integration;
pub mod rate_limiting_middleware;
pub mod skills_verification;
pub mod skills_verification_integration;
pub mod a2ui_payload_generator;
pub mod a2ui_payload_integration;
pub mod aoe_cockpit;
pub mod aoe_cockpit_integration;
pub mod swarm_sync;
pub mod swarm_sync_integration;
pub mod crabbox_security;
pub mod mcp_governance;
