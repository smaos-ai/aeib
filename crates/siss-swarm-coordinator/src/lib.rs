mod coordinator;
mod bounds;
mod agent_metadata;
mod errors;
mod a2a_protocol;
mod conflict_resolver;

pub use coordinator::SwarmCoordinator;
pub use bounds::MongeGapBound;
pub use agent_metadata::AgentMetadata;
pub use errors::SwarmCoordinatorError;
pub use a2a_protocol::A2AMessage;
pub use conflict_resolver::{ConflictResolver, ConflictStrategy};
