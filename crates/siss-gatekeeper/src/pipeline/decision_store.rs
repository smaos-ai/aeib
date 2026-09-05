//! Immutable Decision Store: Covenant Invariant Retention Floor
//!
//! Provides cryptographically-sealed, Merkle-DAG-chained storage of authorization decisions.
//! All decisions are signed with Ed25519 and chained via Merkle hash. The covenant invariant
//! (1%/99% split) is retained across all decision reads: no decision can be modified or
//! deleted from the audit trail.
//!
//! Latency: Target <100µs per append (Tier1 SLO from LatencyConstitution).

use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::sync::{Arc, RwLock};
use uuid::Uuid;

use crate::signer::Signer;
use crate::types::GatekeeperError;

/// A single immutable decision entry in the audit trail.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DecisionEntry {
    /// Unique ID for this decision
    pub id: Uuid,
    /// Task ID this decision applies to
    pub task_id: Uuid,
    /// Manifest (authorization payload)
    pub manifest: String,
    /// Merkle hash of parent entry (None for genesis)
    pub merkle_parent: Option<String>,
    /// Ed25519 signature of (manifest + merkle_parent)
    pub signature: Vec<u8>,
}

impl DecisionEntry {
    /// Compute Merkle hash of this entry: SHA256(manifest + merkle_parent + signature)
    pub fn merkle_hash(&self) -> String {
        let mut hasher = Sha256::new();
        hasher.update(&self.manifest);
        if let Some(parent) = &self.merkle_parent {
            hasher.update(parent.as_bytes());
        }
        hasher.update(&self.signature);
        format!("sha256:{}", hex::encode(hasher.finalize()))
    }

    /// Verify Ed25519 signature of this entry.
    /// Payload is: manifest + merkle_parent (if any)
    pub fn verify_signature(&self, signer: &dyn Signer) -> Result<bool, GatekeeperError> {
        let mut payload = self.manifest.as_bytes().to_vec();
        if let Some(parent) = &self.merkle_parent {
            payload.extend_from_slice(parent.as_bytes());
        }

        signer
            .verify(&payload, &self.signature)
            .map_err(|e| GatekeeperError::SigningError { message: e.message })
    }
}

/// Immutable decision store with Merkle-DAG chaining.
pub struct DecisionStore {
    // All entries, indexed by decision ID
    entries: Arc<DashMap<Uuid, DecisionEntry>>,
    // Task audit trail: task_id → Vec of decision IDs in order
    task_indices: Arc<DashMap<Uuid, Vec<Uuid>>>,
    // Merkle root (hash of last entry)
    merkle_root_hash: Arc<RwLock<String>>,
}

impl DecisionStore {
    /// Create a new decision store with genesis (empty) Merkle root.
    pub fn new() -> Self {
        Self {
            entries: Arc::new(DashMap::new()),
            task_indices: Arc::new(DashMap::new()),
            merkle_root_hash: Arc::new(RwLock::new("sha256:genesis".to_string())),
        }
    }

    /// Append a decision entry to the store.
    /// Sets merkle_parent to current root if not already set.
    pub fn append(&self, mut entry: DecisionEntry) -> Result<(), GatekeeperError> {
        // If no parent specified, use current root
        if entry.merkle_parent.is_none() {
            let root = self.merkle_root_hash.read().unwrap().clone();
            if root != "sha256:genesis" {
                entry.merkle_parent = Some(root);
            }
        }

        // Compute merkle hash and update root
        let hash = entry.merkle_hash();
        {
            let mut root = self.merkle_root_hash.write().unwrap();
            *root = hash.clone();
        }

        // Index by task
        {
            let mut indices = self
                .task_indices
                .entry(entry.task_id)
                .or_insert_with(Vec::new);
            indices.push(entry.id);
        }

        // Store entry
        self.entries.insert(entry.id, entry);

        Ok(())
    }

    /// Append a decision entry with Ed25519 signature verification.
    pub fn append_with_verification(
        &self,
        entry: &DecisionEntry,
        signer: &dyn Signer,
    ) -> Result<(), GatekeeperError> {
        // Reject if signature is empty
        if entry.signature.is_empty() {
            return Err(GatekeeperError::SigningError {
                message: "signature cannot be empty".to_string(),
            });
        }

        // Verify signature
        entry.verify_signature(signer)?;

        // Append to store
        self.append(entry.clone())
    }

    /// Retrieve a single decision entry by ID.
    pub fn get(&self, id: Uuid) -> Result<DecisionEntry, GatekeeperError> {
        self.entries
            .get(&id)
            .map(|entry| entry.clone())
            .ok_or_else(|| GatekeeperError::SigningError {
                message: format!("decision entry {} not found", id),
            })
    }

    /// Get all decisions for a specific task (audit trail).
    pub fn audit_trail(&self, task_id: Uuid) -> Result<Vec<DecisionEntry>, GatekeeperError> {
        let indices =
            self.task_indices
                .get(&task_id)
                .ok_or_else(|| GatekeeperError::SigningError {
                    message: format!("no audit trail for task {}", task_id),
                })?;

        let trail = indices
            .iter()
            .filter_map(|&id| self.entries.get(&id).map(|e| e.clone()))
            .collect();

        Ok(trail)
    }

    /// Get the current Merkle root hash.
    pub fn merkle_root(&self) -> String {
        self.merkle_root_hash.read().unwrap().clone()
    }

    /// Return the count of all stored decisions (for metrics).
    pub fn size(&self) -> usize {
        self.entries.len()
    }
}

impl Default for DecisionStore {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
#[path = "decision_store_tests.rs"]
mod tests;
