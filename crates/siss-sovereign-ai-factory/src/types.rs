//! Core types for Sovereign AI Factory

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::net::IpAddr;
use std::time::Duration;
use uuid::Uuid;

/// Unique identifier for a cluster node (MAC address hash for air-gap safety)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct NodeId(pub Uuid);

impl NodeId {
    pub fn new() -> Self {
        NodeId(Uuid::new_v4())
    }

    pub fn from_mac_hash(mac_bytes: &[u8]) -> Self {
        // Hash MAC address for deterministic node IDs
        let hash = sha2::Sha256::digest(mac_bytes);
        let bytes = &hash[0..16];
        let uuid_bytes = <[u8; 16]>::try_from(bytes).unwrap();
        NodeId(Uuid::from_bytes(uuid_bytes))
    }
}

impl Default for NodeId {
    fn default() -> Self {
        Self::new()
    }
}

/// Health status of a node
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum NodeHealth {
    Healthy,
    Degraded,
    Unhealthy,
    Offline,
}

/// Model version agreement state
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelVersion {
    pub name: String,
    pub version: String,
    pub merkle_root: String, // Merkle tree root hash
    pub updated_at: DateTime<Utc>,
}

/// Node information and state
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NodeInfo {
    pub node_id: NodeId,
    pub hostname: String,
    pub local_ip: IpAddr,
    pub port: u16,
    pub health: NodeHealth,
    pub model_version: Option<ModelVersion>,
    pub inference_latency_ms: Option<f64>, // Latest p99 latency
    pub request_count: u64,
    pub last_heartbeat: DateTime<Utc>,
    pub joined_at: DateTime<Utc>,
}

impl NodeInfo {
    pub fn new(node_id: NodeId, hostname: String, local_ip: IpAddr, port: u16) -> Self {
        Self {
            node_id,
            hostname,
            local_ip,
            port,
            health: NodeHealth::Healthy,
            model_version: None,
            inference_latency_ms: None,
            request_count: 0,
            last_heartbeat: Utc::now(),
            joined_at: Utc::now(),
        }
    }

    pub fn is_healthy(&self) -> bool {
        self.health == NodeHealth::Healthy
    }

    pub fn endpoint(&self) -> String {
        format!("http://{}:{}", self.local_ip, self.port)
    }
}

/// Cluster configuration (air-gap hardened)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClusterConfig {
    pub cluster_id: Uuid,
    pub node_count: usize,
    pub quorum_size: usize,
    pub gossip_interval: Duration,
    pub heartbeat_timeout: Duration,
    pub mdns_domain: String, // e.g., "sovereign-ai.local"
    pub local_network_only: bool,
    pub merkle_verification_enabled: bool,
}

impl ClusterConfig {
    /// Standard 3-node Mac Studio configuration
    pub fn three_node_mac_studio() -> Self {
        Self {
            cluster_id: Uuid::new_v4(),
            node_count: 3,
            quorum_size: 2,
            gossip_interval: Duration::from_millis(500),
            heartbeat_timeout: Duration::from_secs(5),
            mdns_domain: "sovereign-ai.local".to_string(),
            local_network_only: true,
            merkle_verification_enabled: true,
        }
    }
}

/// Gossip message for consensus
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GossipMessage {
    pub from_node: NodeId,
    pub sequence_number: u64,
    pub model_version: ModelVersion,
    pub timestamp: DateTime<Utc>,
    pub merkle_root: String,
}

/// Load balancing request
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BalanceRequest {
    pub request_id: Uuid,
    pub model_name: String,
    pub priority: i32,
    pub max_wait_ms: u64,
}

/// Load balancing response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BalanceResponse {
    pub request_id: Uuid,
    pub selected_node: NodeId,
    pub endpoint: String,
    pub estimated_latency_ms: f64,
}

/// Merkle tree node for verification
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MerkleNode {
    pub hash: String,
    pub is_leaf: bool,
    pub left: Option<Box<MerkleNode>>,
    pub right: Option<Box<MerkleNode>>,
}

impl MerkleNode {
    pub fn leaf(hash: String) -> Self {
        Self {
            hash,
            is_leaf: true,
            left: None,
            right: None,
        }
    }

    pub fn branch(left: MerkleNode, right: MerkleNode) -> Self {
        let combined = format!("{}{}", left.hash, right.hash);
        let mut hasher = Sha256::new();
        hasher.update(combined.as_bytes());
        let hash = hex::encode(hasher.finalize());
        Self {
            hash,
            is_leaf: false,
            left: Some(Box::new(left)),
            right: Some(Box::new(right)),
        }
    }
}
