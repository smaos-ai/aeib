/// AG-UI (Agent-User Interaction) Protocol Module
///
/// Implements the middleware that translates raw framework events into
/// standardized Server-Sent Events (SSE) streams for consumption by the
/// agent shell membrane and AoE orchestrator.
pub mod aoe_spatial_stream;
pub mod sse_consumer;
pub mod status_emitter;

pub use aoe_spatial_stream::AoeSpatialStream;
pub use sse_consumer::{AoEEvent, AoESseConsumer, SseConfig};
pub use status_emitter::{AgentSessionManager, AgentState, emit_agent_status};
