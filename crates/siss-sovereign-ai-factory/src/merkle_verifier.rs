//! Merkle tree verification for air-gap safety

use crate::error::Result;
use crate::types::MerkleNode;
use sha2::{Digest, Sha256};

/// Merkle tree verifier for model update integrity
pub struct MerkleVerifier {
    enable_verification: bool,
}

impl MerkleVerifier {
    pub fn new(enable_verification: bool) -> Self {
        Self {
            enable_verification,
        }
    }

    /// Build a Merkle tree from data chunks
    pub fn build_tree(data_chunks: &[String]) -> MerkleNode {
        if data_chunks.is_empty() {
            let empty_hash = hex::encode(Sha256::digest(b""));
            return MerkleNode::leaf(empty_hash);
        }

        let mut leaves: Vec<MerkleNode> = data_chunks
            .iter()
            .map(|chunk| {
                let hash = hex::encode(Sha256::digest(chunk.as_bytes()));
                MerkleNode::leaf(hash)
            })
            .collect();

        while leaves.len() > 1 {
            let mut new_level = Vec::new();
            for _ in (0..leaves.len()).step_by(2) {
                let left = leaves.remove(0);
                let right = if !leaves.is_empty() {
                    leaves.remove(0)
                } else {
                    left.clone()
                };
                new_level.push(MerkleNode::branch(left, right));
            }
            leaves = new_level;
        }

        leaves.pop().unwrap_or_else(|| {
            let empty_hash = hex::encode(Sha256::digest(b""));
            MerkleNode::leaf(empty_hash)
        })
    }

    /// Verify that a data chunk is in the tree
    pub fn verify_membership(&self, tree: &MerkleNode, data: &str, merkle_path: &[String]) -> bool {
        if !self.enable_verification {
            return true;
        }

        let mut current_hash = hex::encode(Sha256::digest(data.as_bytes()));

        for path_hash in merkle_path {
            let combined = if current_hash < *path_hash {
                format!("{}{}", current_hash, path_hash)
            } else {
                format!("{}{}", path_hash, current_hash)
            };
            let mut hasher = Sha256::new();
            hasher.update(combined.as_bytes());
            current_hash = hex::encode(hasher.finalize());
        }

        current_hash == tree.hash
    }

    /// Verify entire tree integrity
    pub fn verify_tree(&self, tree: &MerkleNode) -> bool {
        if !self.enable_verification {
            return true;
        }

        self.verify_node_integrity(tree)
    }

    fn verify_node_integrity(&self, node: &MerkleNode) -> bool {
        if node.is_leaf {
            return true;
        }

        let left_hash = node
            .left
            .as_ref()
            .map(|n| n.hash.clone())
            .unwrap_or_default();
        let right_hash = node
            .right
            .as_ref()
            .map(|n| n.hash.clone())
            .unwrap_or_default();

        let combined = format!("{}{}", left_hash, right_hash);
        let mut hasher = Sha256::new();
        hasher.update(combined.as_bytes());
        let computed_hash = hex::encode(hasher.finalize());

        if computed_hash != node.hash {
            return false;
        }

        let left_ok = node
            .left
            .as_ref()
            .map(|n| self.verify_node_integrity(n))
            .unwrap_or(true);

        let right_ok = node
            .right
            .as_ref()
            .map(|n| self.verify_node_integrity(n))
            .unwrap_or(true);

        left_ok && right_ok
    }

    /// Calculate root hash of tree
    pub fn root_hash(&self, tree: &MerkleNode) -> String {
        tree.hash.clone()
    }

    /// Verify model version using root hash
    pub fn verify_model_version(&self, local_root: &str, cluster_root: &str) -> Result<()> {
        if !self.enable_verification {
            return Ok(());
        }

        if local_root == cluster_root {
            Ok(())
        } else {
            Err(crate::Error::MerkleVerificationFailed(
                format!("Root mismatch: local={}, cluster={}", local_root, cluster_root),
            ))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_build_single_chunk_tree() {
        let chunks = vec!["chunk1".to_string()];
        let tree = MerkleVerifier::build_tree(&chunks);

        assert!(tree.is_leaf);
        assert_eq!(tree.hash, hex::encode(Sha256::digest(b"chunk1")));
    }

    #[test]
    fn test_build_multi_chunk_tree() {
        let chunks = vec!["chunk1".to_string(), "chunk2".to_string(), "chunk3".to_string()];
        let tree = MerkleVerifier::build_tree(&chunks);

        assert!(!tree.is_leaf);
        assert!(!tree.hash.is_empty());
    }

    #[test]
    fn test_build_empty_tree() {
        let chunks: Vec<String> = vec![];
        let tree = MerkleVerifier::build_tree(&chunks);

        assert!(tree.is_leaf);
        assert_eq!(tree.hash, hex::encode(Sha256::digest(b"")));
    }

    #[test]
    fn test_verify_tree_integrity() {
        let chunks = vec!["chunk1".to_string(), "chunk2".to_string()];
        let tree = MerkleVerifier::build_tree(&chunks);
        let verifier = MerkleVerifier::new(true);

        assert!(verifier.verify_tree(&tree));
    }

    #[test]
    fn test_verify_tree_disabled() {
        let chunks = vec!["chunk1".to_string(), "chunk2".to_string()];
        let mut tree = MerkleVerifier::build_tree(&chunks);
        tree.hash = "corrupted".to_string(); // Corrupt the root

        let verifier = MerkleVerifier::new(false);
        assert!(verifier.verify_tree(&tree)); // Still passes when disabled
    }

    #[test]
    fn test_root_hash() {
        let chunks = vec!["chunk1".to_string(), "chunk2".to_string()];
        let tree = MerkleVerifier::build_tree(&chunks);
        let verifier = MerkleVerifier::new(true);

        let root = verifier.root_hash(&tree);
        assert!(!root.is_empty());
        assert!(root.len() > 0);
    }

    #[test]
    fn test_verify_model_version_match() {
        let verifier = MerkleVerifier::new(true);
        let root = "abc123".to_string();

        let result = verifier.verify_model_version(&root, &root);
        assert!(result.is_ok());
    }

    #[test]
    fn test_verify_model_version_mismatch() {
        let verifier = MerkleVerifier::new(true);

        let result = verifier.verify_model_version("abc123", "def456");
        assert!(result.is_err());
    }

    #[test]
    fn test_verify_model_version_disabled() {
        let verifier = MerkleVerifier::new(false);

        let result = verifier.verify_model_version("abc123", "def456");
        assert!(result.is_ok()); // Passes when verification disabled
    }

    #[test]
    fn test_deterministic_tree_hash() {
        let chunks = vec!["chunk1".to_string(), "chunk2".to_string()];
        let tree1 = MerkleVerifier::build_tree(&chunks);
        let tree2 = MerkleVerifier::build_tree(&chunks);

        assert_eq!(tree1.hash, tree2.hash); // Same data => same hash
    }

    #[test]
    fn test_tree_hash_changes_with_data() {
        let chunks1 = vec!["chunk1".to_string(), "chunk2".to_string()];
        let chunks2 = vec!["chunk1".to_string(), "chunk2modified".to_string()];

        let tree1 = MerkleVerifier::build_tree(&chunks1);
        let tree2 = MerkleVerifier::build_tree(&chunks2);

        assert_ne!(tree1.hash, tree2.hash); // Different data => different hash
    }
}
