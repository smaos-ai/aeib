pub mod a2a_protocol;
pub mod agent_metadata;
pub mod bounds;
pub mod conflict_resolver;
pub mod coordinator;
pub mod errors;

pub use a2a_protocol::A2AMessage;
pub use agent_metadata::AgentMetadata;
pub use bounds::MongeGapBound;
pub use conflict_resolver::{ConflictResolver, ConflictStrategy};
pub use coordinator::SwarmCoordinator;
pub use errors::SwarmCoordinatorError;
