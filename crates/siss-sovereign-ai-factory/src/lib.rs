//! Sovereign AI Factory: Air-gapped cluster orchestration for 3x Mac Studio M3 Max
//!
//! # Architecture
//!
//! - **Cluster Discovery**: Multicast DNS on local network only (zero internet)
//! - **LLM Load Balancing**: Round-robin + latency-aware routing across 3 nodes
//! - **Gossip Consensus**: Byzantine-tolerant model sync & version agreement
//! - **Air-gap Hardening**: Merkle-verified updates, no external requests
//!
//! # Crates
//!
//! - `cluster_discovery` — mDNS node registration and peer detection
//! - `llm_balancer` — Load balancer for inference requests
//! - `gossip_consensus` — Gossip protocol for model version sync
//! - `merkle_verifier` — Merkle tree validation for air-gap safety
//! - `node_registry` — Central node state and health tracking

pub mod cluster_discovery;
pub mod error;
pub mod gossip_consensus;
pub mod llm_balancer;
pub mod merkle_verifier;
pub mod node_registry;
pub mod types;

pub use error::{Error, Result};
pub use types::{ClusterConfig, NodeId, NodeInfo};

#[cfg(test)]
mod tests;
