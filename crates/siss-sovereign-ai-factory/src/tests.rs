//! Integration tests for Sovereign AI Factory

use crate::{
    cluster_discovery::ClusterDiscovery, gossip_consensus::GossipConsensus,
    llm_balancer::LlmBalancer, merkle_verifier::MerkleVerifier, node_registry::NodeRegistry,
    types::{ClusterConfig, ModelVersion, NodeId},
};
use chrono::Utc;
use std::net::IpAddr;
use std::str::FromStr;

#[test]
fn test_full_cluster_setup() {
    let registry = NodeRegistry::new();
    let ip = IpAddr::from_str("192.168.1.10").unwrap();

    // Register 3 nodes
    let id1 = NodeId::new();
    let id2 = NodeId::new();
    let id3 = NodeId::new();
    let _ = id3;

    registry.register(id1, "mac-studio-1".to_string(), ip, 8080);
    registry.register(id2, "mac-studio-2".to_string(), ip, 8081);
    registry.register(id3, "mac-studio-3".to_string(), ip, 8082);

    assert_eq!(registry.count(), 3);
    assert!(registry.has_quorum(2));
}

#[test]
fn test_cluster_config_three_node() {
    let config = ClusterConfig::three_node_mac_studio();

    assert_eq!(config.node_count, 3);
    assert_eq!(config.quorum_size, 2);
    assert!(config.local_network_only);
    assert!(config.merkle_verification_enabled);
}

#[tokio::test]
async fn test_air_gap_validation() {
    let discovery = ClusterDiscovery::new("sovereign-ai.local".to_string(), true);

    let result = discovery.validate_air_gap();
    assert!(result.is_ok());

    // Invalid domain fails
    let bad_discovery = ClusterDiscovery::new("example.com".to_string(), true);
    assert!(bad_discovery.validate_air_gap().is_err());
}

#[test]
fn test_merkle_tree_chain() {
    let data = vec![
        "model_chunk_1".to_string(),
        "model_chunk_2".to_string(),
        "model_chunk_3".to_string(),
    ];

    let tree = MerkleVerifier::build_tree(&data);
    let verifier = MerkleVerifier::new(true);

    assert!(verifier.verify_tree(&tree));

    let root = verifier.root_hash(&tree);
    assert!(!root.is_empty());
}

#[test]
fn test_load_balancer_with_registry() {
    let registry = NodeRegistry::new();
    let ip = IpAddr::from_str("192.168.1.10").unwrap();

    let id1 = NodeId::new();
    let id2 = NodeId::new();
    let id3 = NodeId::new();

    registry.register(id1, "node1".to_string(), ip, 8080);
    registry.register(id2, "node2".to_string(), ip, 8081);
    registry.register(id3, "node3".to_string(), ip, 8082);

    let balancer = LlmBalancer::new(registry);

    // Record requests
    let registry = balancer.registry.clone();
    registry.record_request(&id1, 40.0).ok();
    registry.record_request(&id2, 45.0).ok();
    registry.record_request(&id3, 50.0).ok();

    let dist = balancer.load_distribution();
    assert_eq!(dist.len(), 3);
}

#[test]
fn test_gossip_with_consensus() {
    let node1 = NodeId::new();
    let node2 = NodeId::new();
    let node3 = NodeId::new();

    let consensus = GossipConsensus::new(node1, 2); // 2/3 quorum

    let version = ModelVersion {
        name: "qwen3-coder".to_string(),
        version: "1.2.0".to_string(),
        merkle_root: "hash_abc123".to_string(),
        updated_at: Utc::now(),
    };

    // Node1 broadcasts
    consensus.broadcast(&version, "hash_abc123");

    // Node2 agrees
    let msg2 = crate::types::GossipMessage {
        from_node: node2,
        sequence_number: 0,
        model_version: version.clone(),
        timestamp: Utc::now(),
        merkle_root: "hash_abc123".to_string(),
    };
    consensus.receive(msg2).ok();

    // Consensus achieved
    let result = consensus.achieve_consensus();
    assert!(result.is_ok());
    assert_eq!(result.unwrap().version, "1.2.0");
}

#[test]
fn test_air_gap_no_external_ips() {
    // Validate local IP ranges for air-gap safety
    let discovery = ClusterDiscovery::new("sovereign-ai.local".to_string(), true);

    // Test via the discovery validation (private IP checking)
    assert!(discovery.validate_air_gap().is_ok());
}

#[test]
fn test_node_health_tracking() {
    let registry = NodeRegistry::new();
    let node_id = NodeId::new();
    let ip = IpAddr::from_str("192.168.1.10").unwrap();

    registry.register(node_id, "test-node".to_string(), ip, 8080);

    // Initially healthy
    let node = registry.get(&node_id).unwrap();
    assert!(node.is_healthy());

    // Mark degraded
    registry
        .set_health(&node_id, crate::types::NodeHealth::Degraded)
        .ok();

    let node = registry.get(&node_id).unwrap();
    assert_eq!(node.health, crate::types::NodeHealth::Degraded);
}

#[test]
fn test_merkle_update_detection() {
    let verifier = MerkleVerifier::new(true);

    let old_chunks = vec!["v1_chunk1".to_string(), "v1_chunk2".to_string()];
    let new_chunks = vec!["v2_chunk1".to_string(), "v2_chunk2".to_string()];

    let old_tree = MerkleVerifier::build_tree(&old_chunks);
    let new_tree = MerkleVerifier::build_tree(&new_chunks);

    let old_root = verifier.root_hash(&old_tree);
    let new_root = verifier.root_hash(&new_tree);

    // Different data => different roots
    assert_ne!(old_root, new_root);

    // Can detect version mismatch
    let mismatch = verifier.verify_model_version(&old_root, &new_root);
    assert!(mismatch.is_err());
}

#[test]
fn test_quorum_enforcement() {
    let registry = NodeRegistry::new();
    let ip = IpAddr::from_str("192.168.1.10").unwrap();

    let id1 = NodeId::new();
    let id2 = NodeId::new();
    let id3 = NodeId::new();

    registry.register(id1, "node1".to_string(), ip, 8080);
    registry.register(id2, "node2".to_string(), ip, 8081);
    registry.register(id3, "node3".to_string(), ip, 8082);

    // 3 healthy >= 2 quorum
    assert!(registry.has_quorum(2));

    // Take one down
    registry
        .set_health(&id3, crate::types::NodeHealth::Offline)
        .ok();

    // 2 healthy >= 2 quorum still works
    assert!(registry.has_quorum(2));

    // Take another down
    registry
        .set_health(&id2, crate::types::NodeHealth::Offline)
        .ok();

    // 1 healthy < 2 quorum fails
    assert!(!registry.has_quorum(2));
}

#[test]
fn test_node_id_deterministic_from_mac() {
    let mac1 = b"aa:bb:cc:dd:ee:ff";
    let mac2 = b"aa:bb:cc:dd:ee:ff";
    let mac3 = b"11:22:33:44:55:66";

    let id1 = NodeId::from_mac_hash(mac1);
    let id2 = NodeId::from_mac_hash(mac2);
    let id3 = NodeId::from_mac_hash(mac3);

    // Same MAC => same ID
    assert_eq!(id1, id2);

    // Different MAC => different ID
    assert_ne!(id1, id3);
}

#[test]
fn test_load_balancer_failover_chain() {
    let registry = NodeRegistry::new();
    let ip = IpAddr::from_str("192.168.1.10").unwrap();

    let id1 = NodeId::new();
    let id2 = NodeId::new();
    let id3 = NodeId::new();

    registry.register(id1, "primary".to_string(), ip, 8080);
    registry.register(id2, "secondary".to_string(), ip, 8081);
    registry.register(id3, "tertiary".to_string(), ip, 8082);

    let balancer = LlmBalancer::new(registry.clone());

    // Primary fails
    registry
        .set_health(&id1, crate::types::NodeHealth::Unhealthy)
        .ok();

    let failover1 = balancer.failover(&id1).expect("failover failed");
    assert!(failover1.selected_node == id2 || failover1.selected_node == id3);

    // Second node fails too
    registry
        .set_health(&id2, crate::types::NodeHealth::Unhealthy)
        .ok();

    let failover2 = balancer.failover(&id1).expect("failover failed");
    assert_eq!(failover2.selected_node, id3);
}

#[test]
fn test_gossip_message_ordering() {
    let node1 = NodeId::new();
    let consensus = GossipConsensus::new(node1, 1);

    let v1 = ModelVersion {
        name: "model".to_string(),
        version: "1.0.0".to_string(),
        merkle_root: "hash1".to_string(),
        updated_at: Utc::now(),
    };

    let msg1 = consensus.broadcast(&v1, "hash1");
    let msg2 = consensus.broadcast(&v1, "hash1");
    let msg3 = consensus.broadcast(&v1, "hash1");

    // Sequence numbers must increase
    assert!(msg1.sequence_number < msg2.sequence_number);
    assert!(msg2.sequence_number < msg3.sequence_number);

    let messages = consensus.get_messages();
    assert_eq!(messages.len(), 3);
}

#[test]
fn test_quorum_size_for_three_nodes() {
    let registry = NodeRegistry::new();
    let ip = IpAddr::from_str("192.168.1.10").unwrap();

    let id1 = NodeId::new();
    let id2 = NodeId::new();
    let id3 = NodeId::new();

    registry.register(id1, "node1".to_string(), ip, 8080);
    registry.register(id2, "node2".to_string(), ip, 8081);
    registry.register(id3, "node3".to_string(), ip, 8082);

    // For 3-node cluster, quorum should be 2 (majority)
    let config = ClusterConfig::three_node_mac_studio();
    assert_eq!(config.quorum_size, 2);
    assert!(registry.has_quorum(config.quorum_size));
}

#[test]
fn test_model_version_equality() {
    let v1 = ModelVersion {
        name: "qwen3".to_string(),
        version: "1.0.0".to_string(),
        merkle_root: "abc".to_string(),
        updated_at: Utc::now(),
    };

    let v2 = ModelVersion {
        name: "qwen3".to_string(),
        version: "1.0.0".to_string(),
        merkle_root: "abc".to_string(),
        updated_at: v1.updated_at,
    };

    assert_eq!(v1.name, v2.name);
    assert_eq!(v1.version, v2.version);
    assert_eq!(v1.merkle_root, v2.merkle_root);
}
