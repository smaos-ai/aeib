// Merkle tree archive for historical state snapshots

use super::events::AuditEvent;
use sha2::{Sha256, Digest};
use std::sync::RwLock;
use std::sync::Arc;

pub struct MerkleArchive {
    snapshots: Arc<RwLock<Vec<Vec<u8>>>>,     // List of snapshot roots
    snapshot_hashes: Arc<RwLock<Vec<Vec<u8>>>>, // Individual event hashes per snapshot
}

impl MerkleArchive {
    pub fn new() -> Self {
        MerkleArchive {
            snapshots: Arc::new(RwLock::new(Vec::new())),
            snapshot_hashes: Arc::new(RwLock::new(Vec::new())),
        }
    }

    /// Add a snapshot of events and return the merkle root hash
    pub fn add_snapshot(&self, events: Vec<AuditEvent>) -> Vec<u8> {
        let root = Self::compute_merkle_root(&events);

        if let Ok(mut snapshots) = self.snapshots.write() {
            snapshots.push(root.clone());
        }

        root
    }

    /// Compute merkle root from event list
    fn compute_merkle_root(events: &[AuditEvent]) -> Vec<u8> {
        if events.is_empty() {
            return Self::hash_empty();
        }

        let event_hashes: Vec<Vec<u8>> = events.iter().map(Self::hash_event).collect();
        Self::merkle_tree_root(&event_hashes)
    }

    /// Hash a single event
    fn hash_event(event: &AuditEvent) -> Vec<u8> {
        let mut hasher = Sha256::new();
        hasher.update(event.to_bytes());
        hasher.finalize().to_vec()
    }

    /// Hash empty data
    fn hash_empty() -> Vec<u8> {
        let mut hasher = Sha256::new();
        hasher.update(b"");
        hasher.finalize().to_vec()
    }

    /// Hash two byte slices
    fn hash_pair(left: &[u8], right: &[u8]) -> Vec<u8> {
        let mut hasher = Sha256::new();
        hasher.update(left);
        hasher.update(right);
        hasher.finalize().to_vec()
    }

    /// Build merkle tree from leaf hashes
    fn merkle_tree_root(leaf_hashes: &[Vec<u8>]) -> Vec<u8> {
        if leaf_hashes.is_empty() {
            return Self::hash_empty();
        }

        if leaf_hashes.len() == 1 {
            return leaf_hashes[0].clone();
        }

        let mut current_level = leaf_hashes.to_vec();

        while current_level.len() > 1 {
            let mut next_level = Vec::new();
            for i in (0..current_level.len()).step_by(2) {
                if i + 1 < current_level.len() {
                    let combined = Self::hash_pair(&current_level[i], &current_level[i + 1]);
                    next_level.push(combined);
                } else {
                    // Odd number of nodes: combine with itself
                    let combined = Self::hash_pair(&current_level[i], &current_level[i]);
                    next_level.push(combined);
                }
            }
            current_level = next_level;
        }

        current_level[0].clone()
    }

    pub fn snapshot_count(&self) -> usize {
        self.snapshots.read().map(|s| s.len()).unwrap_or(0)
    }

    pub fn root_hash(&self) -> Vec<u8> {
        self.snapshots
            .read()
            .map(|s| {
                if s.is_empty() {
                    Self::hash_empty()
                } else {
                    Self::merkle_tree_root(&s)
                }
            })
            .unwrap_or_default()
    }

    pub fn get_snapshot_root(&self, index: usize) -> Option<Vec<u8>> {
        self.snapshots
            .read()
            .ok()
            .and_then(|s| s.get(index).cloned())
    }

    pub fn verify_snapshot(&self, index: usize, expected_root: &[u8]) -> Result<bool, String> {
        match self.get_snapshot_root(index) {
            Some(actual_root) => Ok(actual_root == expected_root),
            None => Err(format!("Snapshot {} not found", index)),
        }
    }

    pub fn get_proof(&self, _index: usize) -> Option<Vec<u8>> {
        // Simplified: return snapshot root as proof
        // Full merkle proof would include sibling hashes
        self.snapshots
            .read()
            .ok()
            .and_then(|s| {
                if _index < s.len() {
                    Some(s[_index].clone())
                } else {
                    None
                }
            })
    }
}

impl Default for MerkleArchive {
    fn default() -> Self {
        Self::new()
    }
}

impl Clone for MerkleArchive {
    fn clone(&self) -> Self {
        MerkleArchive {
            snapshots: Arc::clone(&self.snapshots),
            snapshot_hashes: Arc::clone(&self.snapshot_hashes),
        }
    }
}
