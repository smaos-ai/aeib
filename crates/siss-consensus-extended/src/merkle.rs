use crate::error::{ConsensusError, Result};
use sha2::{Digest, Sha256};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Merkle tree node
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct MerkleNode {
    pub hash: Vec<u8>,
    pub left: Option<Box<MerkleNode>>,
    pub right: Option<Box<MerkleNode>>,
}

/// Merkle checkpoint (immutable, proof-friendly)
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct MerkleCheckpoint {
    /// Sequence number
    pub sequence: u64,
    /// Merkle root hash
    pub root_hash: Vec<u8>,
    /// Timestamp
    pub timestamp: i64,
    /// Nodes in this checkpoint
    pub nodes: Vec<Vec<u8>>,
    /// Tree structure (for proofs)
    pub tree: Option<MerkleNode>,
}

impl MerkleCheckpoint {
    /// Create checkpoint from data nodes
    pub fn new(sequence: u64, nodes: Vec<Vec<u8>>, timestamp: i64) -> Result<Self> {
        let tree = Self::build_tree(&nodes)?;
        let root_hash = tree.hash.clone();

        Ok(Self {
            sequence,
            root_hash,
            timestamp,
            nodes,
            tree: Some(tree),
        })
    }

    /// Build Merkle tree from nodes
    fn build_tree(nodes: &[Vec<u8>]) -> Result<MerkleNode> {
        if nodes.is_empty() {
            return Err(ConsensusError::MerkleError("Empty node list".into()));
        }

        // Leaf nodes
        let mut level: Vec<MerkleNode> = nodes
            .iter()
            .map(|n| {
                let hash = Self::hash_data(n);
                MerkleNode {
                    hash,
                    left: None,
                    right: None,
                }
            })
            .collect();

        // Build tree bottom-up
        while level.len() > 1 {
            let mut next_level = Vec::new();
            for i in (0..level.len()).step_by(2) {
                let left = level[i].clone();
                let right = if i + 1 < level.len() {
                    level[i + 1].clone()
                } else {
                    left.clone()
                };

                let mut hasher = Sha256::new();
                hasher.update(&left.hash);
                hasher.update(&right.hash);
                let hash = hasher.finalize().to_vec();

                next_level.push(MerkleNode {
                    hash,
                    left: Some(Box::new(left)),
                    right: Some(Box::new(right)),
                });
            }
            level = next_level;
        }

        Ok(level.pop().unwrap())
    }

    /// Hash single data node
    fn hash_data(data: &[u8]) -> Vec<u8> {
        let mut hasher = Sha256::new();
        hasher.update(data);
        hasher.finalize().to_vec()
    }

    /// Verify data membership in checkpoint
    pub fn verify_membership(&self, data: &[u8], leaf_index: usize) -> Result<bool> {
        if leaf_index >= self.nodes.len() {
            return Ok(false);
        }

        let data_hash = Self::hash_data(data);
        Ok(data_hash == Self::hash_data(&self.nodes[leaf_index]))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_merkle_checkpoint_single_node() {
        let nodes = vec![vec![1, 2, 3]];
        let checkpoint = MerkleCheckpoint::new(1, nodes, 0).unwrap();
        assert_eq!(checkpoint.sequence, 1);
        assert!(!checkpoint.root_hash.is_empty());
    }

    #[test]
    fn test_merkle_checkpoint_multiple_nodes() {
        let nodes = vec![
            vec![1, 2, 3],
            vec![4, 5, 6],
            vec![7, 8, 9],
            vec![10, 11, 12],
        ];
        let checkpoint = MerkleCheckpoint::new(1, nodes.clone(), 0).unwrap();
        assert_eq!(checkpoint.nodes.len(), 4);
        assert!(!checkpoint.root_hash.is_empty());
    }

    #[test]
    fn test_merkle_verify_membership() {
        let nodes = vec![vec![1, 2, 3], vec![4, 5, 6]];
        let checkpoint = MerkleCheckpoint::new(1, nodes, 0).unwrap();
        assert!(checkpoint.verify_membership(&vec![1, 2, 3], 0).unwrap());
        assert!(checkpoint.verify_membership(&vec![4, 5, 6], 1).unwrap());
        assert!(!checkpoint.verify_membership(&vec![99, 99], 0).unwrap());
    }

    #[test]
    fn test_merkle_empty_nodes_error() {
        let nodes: Vec<Vec<u8>> = vec![];
        let result = MerkleCheckpoint::new(1, nodes, 0);
        assert!(result.is_err());
    }

    #[test]
    fn test_merkle_deterministic() {
        let nodes = vec![vec![1, 2, 3], vec![4, 5, 6]];
        let cp1 = MerkleCheckpoint::new(1, nodes.clone(), 0).unwrap();
        let cp2 = MerkleCheckpoint::new(1, nodes, 0).unwrap();
        assert_eq!(cp1.root_hash, cp2.root_hash);
    }
}
