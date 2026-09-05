//! siss-a2a-protocol: Agent-to-Agent Protocol Layer
//!
//! Phase 2B Part 2 deliverable. Provides:
//! - CBOR message envelope with Ed25519 signatures
//! - Peer discovery via /.well-known/agent.json
//! - Cryptographic handoff of task state
//! - Stateful task resumption with atomic ledger commits
//! - Joint ledger anchoring via git digests
//!
//! Timeline: Oct 22 - Nov 4, 2026 (2 weeks after Phase 2B Part 1)
//! Depends on: Phase 2B Part 1 (multi-agent swarm)

pub mod protocol;
pub mod discovery;
pub mod handoff;
pub mod ledger;
pub mod error;
pub mod integration;
pub mod ipc_router;

pub use protocol::{A2AMessage, A2AEnvelope, MessageStatus, MessageType};
pub use discovery::{PeerDiscovery, PeerCapability, PeerManifest};
pub use handoff::{CryptographicHandoff, TaskState, HandoffResult};
pub use ledger::{JointLedger, LedgerAnchor};
pub use error::{A2AError, Result};
pub use integration::{AgentRegistry, RegisteredAgent, ipc_to_a2a, a2a_to_ipc};
pub use ipc_router::{A2ARouter, A2AHandlerTrait};

#[cfg(test)]
mod tests;

#[cfg(test)]
mod protocol_tests;

#[cfg(test)]
mod discovery_tests;

#[cfg(test)]
mod handoff_tests;
