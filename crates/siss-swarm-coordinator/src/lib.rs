pub mod coordinator;
pub mod bounds;
pub mod agent_metadata;
pub mod errors;
pub mod a2a_protocol;
pub mod conflict_resolver;

pub use coordinator::SwarmCoordinator;
pub use bounds::MongeGapBound;
pub use agent_metadata::AgentMetadata;
pub use errors::SwarmCoordinatorError;
pub use a2a_protocol::A2AMessage;
pub use conflict_resolver::{ConflictResolver, ConflictStrategy};
