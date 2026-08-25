use crate::types::Claim;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use thiserror::Error;
use uuid::Uuid;

#[derive(Debug, Clone, Error)]
pub enum MerkleError {
    #[error("Claim not found in tree")]
    ClaimNotFound,
    #[error("Invalid proof")]
    InvalidProof,
    #[error("Tree operation failed")]
    OperationFailed,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MerkleLeaf {
    pub claim_id: Uuid,
    pub hash: String, // Hex-encoded SHA-256
    pub claim_hash: String,
}

impl MerkleLeaf {
    pub fn from_claim(claim: &Claim) -> Self {
        let claim_json = serde_json::to_string(claim).unwrap_or_default();
        let claim_hash = Self::hash_string(&claim_json);
        let leaf_hash = Self::hash_string(&claim_hash);

        Self {
            claim_id: claim.id,
            hash: leaf_hash,
            claim_hash,
        }
    }

    fn hash_string(s: &str) -> String {
        let mut hasher = Sha256::new();
        hasher.update(s.as_bytes());
        hex::encode(hasher.finalize())
    }
}

#[derive(Debug, Clone)]
pub struct MerkleNode {
    pub hash: String,
    pub left: Option<Box<MerkleNode>>,
    pub right: Option<Box<MerkleNode>>,
    pub claim_id: Option<Uuid>,
}

impl MerkleNode {
    fn new_leaf(leaf: &MerkleLeaf) -> Self {
        Self {
            hash: leaf.hash.clone(),
            left: None,
            right: None,
            claim_id: Some(leaf.claim_id),
        }
    }

    fn new_parent(left: MerkleNode, right: MerkleNode) -> Self {
        let combined = format!("{}{}", left.hash, right.hash);
        let mut hasher = Sha256::new();
        hasher.update(combined.as_bytes());
        let hash = hex::encode(hasher.finalize());

        Self {
            hash,
            left: Some(Box::new(left)),
            right: Some(Box::new(right)),
            claim_id: None,
        }
    }
}

pub struct MerkleTree {
    root: Option<MerkleNode>,
    leaves: Vec<MerkleLeaf>,
}

impl MerkleTree {
    pub fn new() -> Self {
        Self {
            root: None,
            leaves: Vec::new(),
        }
    }

    /// Insert a claim into the tree
    pub fn insert(&mut self, claim: Claim) -> Result<(), MerkleError> {
        let leaf = MerkleLeaf::from_claim(&claim);
        self.leaves.push(leaf);
        self.rebuild_tree();
        Ok(())
    }

    /// Rebuild the tree from leaves
    fn rebuild_tree(&mut self) {
        if self.leaves.is_empty() {
            self.root = None;
            return;
        }

        let mut nodes: Vec<MerkleNode> = self.leaves.iter().map(MerkleNode::new_leaf).collect();

        while nodes.len() > 1 {
            let mut next_level = Vec::new();

            for i in (0..nodes.len()).step_by(2) {
                let left = nodes.remove(0);
                let right = if i + 1 < nodes.len() {
                    nodes.remove(0)
                } else {
                    left.clone()
                };

                next_level.push(MerkleNode::new_parent(left, right));
            }

            nodes = next_level;
        }

        self.root = nodes.pop();
    }

    /// Get the root hash of the tree
    pub fn root_hash(&self) -> String {
        self.root
            .as_ref()
            .map(|n| n.hash.clone())
            .unwrap_or_default()
    }

    /// Generate a Merkle proof for a claim
    pub fn generate_proof(&self, claim_id: &Uuid) -> Result<Vec<String>, MerkleError> {
        if let Some(root) = &self.root {
            // If this is a leaf node (contains the claim), return empty proof
            if root.claim_id == Some(*claim_id) {
                return Ok(vec![]);
            }

            // Otherwise, find the path
            let mut proof = Vec::new();
            if Self::collect_proof(root, claim_id, &mut proof) {
                Ok(proof)
            } else {
                Err(MerkleError::ClaimNotFound)
            }
        } else {
            Err(MerkleError::ClaimNotFound)
        }
    }

    fn collect_proof(node: &MerkleNode, claim_id: &Uuid, proof: &mut Vec<String>) -> bool {
        // If this is a leaf and it matches our claim, we found it
        if node.claim_id == Some(*claim_id) {
            return true;
        }

        // If this is a leaf but doesn't match, it's not here
        if node.left.is_none() && node.right.is_none() {
            return false;
        }

        // Check left subtree
        if let Some(left) = &node.left {
            if Self::collect_proof(left, claim_id, proof) {
                // Found in left, add right sibling as proof
                if let Some(right) = &node.right {
                    proof.push(right.hash.clone());
                }
                return true;
            }
        }

        // Check right subtree
        if let Some(right) = &node.right {
            if Self::collect_proof(right, claim_id, proof) {
                // Found in right, add left sibling as proof
                if let Some(left) = &node.left {
                    proof.push(left.hash.clone());
                }
                return true;
            }
        }

        false
    }

    /// Verify a Merkle proof
    pub fn verify_proof(
        leaf_hash: &str,
        proof: &[String],
        root_hash: &str,
    ) -> Result<bool, MerkleError> {
        let mut current_hash = leaf_hash.to_string();

        for sibling_hash in proof {
            let combined = format!("{}{}", current_hash, sibling_hash);
            let mut hasher = Sha256::new();
            hasher.update(combined.as_bytes());
            current_hash = hex::encode(hasher.finalize());
        }

        Ok(current_hash == root_hash)
    }
}

impl Default for MerkleTree {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::ClaimStatus;
    use chrono::Utc;

    #[test]
    fn test_merkle_leaf_creation() {
        let claim = Claim {
            id: Uuid::new_v4(),
            policy_id: Uuid::new_v4(),
            claimant_sovereign_id: Uuid::new_v4(),
            claim_amount: 100_000_00,
            status: ClaimStatus::Submitted,
            submitted_at: Utc::now(),
            settlement_amount: None,
            settled_at: None,
            merkle_proof: None,
        };

        let leaf = MerkleLeaf::from_claim(&claim);
        assert_eq!(leaf.claim_id, claim.id);
        assert_eq!(leaf.hash.len(), 64);
    }

    #[test]
    fn test_merkle_tree_single_claim() {
        let mut tree = MerkleTree::new();
        let claim = Claim {
            id: Uuid::new_v4(),
            policy_id: Uuid::new_v4(),
            claimant_sovereign_id: Uuid::new_v4(),
            claim_amount: 50_000_00,
            status: ClaimStatus::Submitted,
            submitted_at: Utc::now(),
            settlement_amount: None,
            settled_at: None,
            merkle_proof: None,
        };

        tree.insert(claim).unwrap();
        assert!(!tree.root_hash().is_empty());
    }
}
