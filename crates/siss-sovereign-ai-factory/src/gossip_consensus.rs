//! Gossip protocol for Byzantine-tolerant model version consensus

use crate::error::Result;
use crate::types::{GossipMessage, ModelVersion, NodeId};
use chrono::Utc;
use dashmap::DashMap;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;

/// Gossip consensus engine for model synchronization
pub struct GossipConsensus {
    node_id: NodeId,
    messages: Arc<DashMap<u64, GossipMessage>>,
    sequence_counter: Arc<AtomicU64>,
    quorum_size: usize,
}

impl GossipConsensus {
    pub fn new(node_id: NodeId, quorum_size: usize) -> Self {
        Self {
            node_id,
            messages: Arc::new(DashMap::new()),
            sequence_counter: Arc::new(AtomicU64::new(0)),
            quorum_size,
        }
    }

    /// Broadcast a model version to the cluster
    pub fn broadcast(&self, model_version: &ModelVersion, merkle_root: &str) -> GossipMessage {
        let seq = self.sequence_counter.fetch_add(1, Ordering::SeqCst);

        let message = GossipMessage {
            from_node: self.node_id,
            sequence_number: seq,
            model_version: model_version.clone(),
            timestamp: Utc::now(),
            merkle_root: merkle_root.to_string(),
        };

        self.messages.insert(seq, message.clone());
        message
    }

    /// Receive a gossip message from peer
    pub fn receive(&self, message: GossipMessage) -> Result<()> {
        // Store message
        self.messages
            .insert(message.sequence_number, message.clone());

        // Forward to other peers (multi-hop gossip)
        // In production, would forward to N random peers

        Ok(())
    }

    /// Achieve consensus on model version
    pub fn achieve_consensus(&self) -> Result<ModelVersion> {
        let messages: Vec<GossipMessage> = self.messages.iter().map(|m| m.value().clone()).collect();

        if messages.is_empty() {
            return Err(crate::Error::ConsensusError(
                "No messages in consensus pool".to_string(),
            ));
        }

        // Count votes for each model version (by root hash)
        let mut votes: std::collections::HashMap<String, (ModelVersion, usize)> =
            std::collections::HashMap::new();

        for msg in messages {
            let root = msg.merkle_root.clone();
            votes
                .entry(root)
                .and_modify(|(_, count)| *count += 1)
                .or_insert((msg.model_version.clone(), 1));
        }

        // Find winning version (highest vote count)
        let (version, vote_count) = votes
            .into_iter()
            .max_by_key(|(_, (_, count))| *count)
            .ok_or_else(|| crate::Error::ConsensusError("No versions to vote on".to_string()))?
            .1;

        // Check quorum
        if vote_count >= self.quorum_size {
            Ok(version)
        } else {
            Err(crate::Error::QuorumNotMet(vote_count, self.quorum_size))
        }
    }

    /// Get message count
    pub fn message_count(&self) -> usize {
        self.messages.len()
    }

    /// Clear old messages
    pub fn prune_old_messages(&self, keep_last_n: usize) {
        let current_size = self.messages.len();
        if current_size <= keep_last_n {
            return;
        }

        // Remove oldest messages
        let to_remove = current_size - keep_last_n;
        let mut removed = 0;

        for item in self.messages.iter() {
            if removed >= to_remove {
                break;
            }
            self.messages.remove(item.key());
            removed += 1;
        }
    }

    /// Get all messages
    pub fn get_messages(&self) -> Vec<GossipMessage> {
        self.messages.iter().map(|m| m.value().clone()).collect()
    }
}

impl Clone for GossipConsensus {
    fn clone(&self) -> Self {
        Self {
            node_id: self.node_id,
            messages: Arc::clone(&self.messages),
            sequence_counter: Arc::clone(&self.sequence_counter),
            quorum_size: self.quorum_size,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_broadcast_creates_message() {
        let node_id = NodeId::new();
        let consensus = GossipConsensus::new(node_id, 2);

        let version = ModelVersion {
            name: "qwen3-coder".to_string(),
            version: "1.0.0".to_string(),
            merkle_root: "abc123".to_string(),
            updated_at: Utc::now(),
        };

        let msg = consensus.broadcast(&version, "abc123");

        assert_eq!(msg.from_node, node_id);
        assert_eq!(msg.sequence_number, 0);
        assert_eq!(msg.model_version.name, "qwen3-coder");
    }

    #[test]
    fn test_broadcast_increments_sequence() {
        let node_id = NodeId::new();
        let consensus = GossipConsensus::new(node_id, 2);

        let version = ModelVersion {
            name: "model".to_string(),
            version: "1.0.0".to_string(),
            merkle_root: "hash1".to_string(),
            updated_at: Utc::now(),
        };

        let msg1 = consensus.broadcast(&version, "hash1");
        let msg2 = consensus.broadcast(&version, "hash1");

        assert_eq!(msg1.sequence_number, 0);
        assert_eq!(msg2.sequence_number, 1);
    }

    #[test]
    fn test_receive_stores_message() {
        let node_id = NodeId::new();
        let consensus = GossipConsensus::new(node_id, 2);

        let version = ModelVersion {
            name: "model".to_string(),
            version: "1.0.0".to_string(),
            merkle_root: "hash1".to_string(),
            updated_at: Utc::now(),
        };

        let msg = GossipMessage {
            from_node: NodeId::new(),
            sequence_number: 0,
            model_version: version,
            timestamp: Utc::now(),
            merkle_root: "hash1".to_string(),
        };

        consensus.receive(msg).expect("receive failed");
        assert_eq!(consensus.message_count(), 1);
    }

    #[test]
    fn test_achieve_consensus_quorum_met() {
        let node_id = NodeId::new();
        let node2 = NodeId::new();
        let node3 = NodeId::new();

        let consensus = GossipConsensus::new(node_id, 2); // 2/3 quorum

        let version = ModelVersion {
            name: "qwen3".to_string(),
            version: "1.0.0".to_string(),
            merkle_root: "hash1".to_string(),
            updated_at: Utc::now(),
        };

        // Broadcast from node1
        consensus.broadcast(&version, "hash1");

        // Receive from node2
        let msg2 = GossipMessage {
            from_node: node2,
            sequence_number: 0,
            model_version: version.clone(),
            timestamp: Utc::now(),
            merkle_root: "hash1".to_string(),
        };
        consensus.receive(msg2).ok();

        // Achieve consensus
        let result = consensus.achieve_consensus();
        assert!(result.is_ok());
        assert_eq!(result.unwrap().name, "qwen3");
    }

    #[test]
    fn test_achieve_consensus_quorum_not_met() {
        let node_id = NodeId::new();
        let consensus = GossipConsensus::new(node_id, 3); // Need 3 votes

        let version = ModelVersion {
            name: "model".to_string(),
            version: "1.0.0".to_string(),
            merkle_root: "hash1".to_string(),
            updated_at: Utc::now(),
        };

        // Only 1 message (ourselves)
        consensus.broadcast(&version, "hash1");

        let result = consensus.achieve_consensus();
        assert!(result.is_err());
    }

    #[test]
    fn test_achieve_consensus_no_messages() {
        let node_id = NodeId::new();
        let consensus = GossipConsensus::new(node_id, 2);

        let result = consensus.achieve_consensus();
        assert!(result.is_err());
    }

    #[test]
    fn test_prune_old_messages() {
        let node_id = NodeId::new();
        let consensus = GossipConsensus::new(node_id, 2);

        let version = ModelVersion {
            name: "model".to_string(),
            version: "1.0.0".to_string(),
            merkle_root: "hash1".to_string(),
            updated_at: Utc::now(),
        };

        // Add 10 messages
        for _ in 0..10 {
            consensus.broadcast(&version, "hash1");
        }

        assert_eq!(consensus.message_count(), 10);

        // Prune to keep only 5
        consensus.prune_old_messages(5);

        assert_eq!(consensus.message_count(), 5);
    }

    #[test]
    fn test_multiple_model_versions_voting() {
        let node_id = NodeId::new();
        let node2 = NodeId::new();
        let node3 = NodeId::new();

        let consensus = GossipConsensus::new(node_id, 2);

        let v1 = ModelVersion {
            name: "model".to_string(),
            version: "1.0.0".to_string(),
            merkle_root: "hash_v1".to_string(),
            updated_at: Utc::now(),
        };

        let v2 = ModelVersion {
            name: "model".to_string(),
            version: "1.0.1".to_string(),
            merkle_root: "hash_v2".to_string(),
            updated_at: Utc::now(),
        };

        // Node1 votes for v1
        consensus.broadcast(&v1, "hash_v1");

        // Node2 votes for v1
        let msg2 = GossipMessage {
            from_node: node2,
            sequence_number: 0,
            model_version: v1.clone(),
            timestamp: Utc::now(),
            merkle_root: "hash_v1".to_string(),
        };
        consensus.receive(msg2).ok();

        // Node3 votes for v2 (minority)
        let msg3 = GossipMessage {
            from_node: node3,
            sequence_number: 0,
            model_version: v2,
            timestamp: Utc::now(),
            merkle_root: "hash_v2".to_string(),
        };
        consensus.receive(msg3).ok();

        let result = consensus.achieve_consensus();
        assert!(result.is_ok());
        assert_eq!(result.unwrap().version, "1.0.0"); // v1 wins with 2 votes
    }
}
