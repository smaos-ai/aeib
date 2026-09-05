// Phase 26 Task 1: SignedStateLog + Merkle-DAG chain verification
// Mirrors InMemoryAuditLog pattern from siss-layer00/exec_log.rs

use crate::signing::SignedMutation;
use siss_layer00::attestation::sha256;
use std::sync::Mutex;
use thiserror::Error;

#[derive(Debug, Clone, Error)]
pub enum StateLogError {
    #[error("Log is empty")]
    Empty,
    #[error("Merkle chain verification failed")]
    VerificationFailed,
}

/// Entry in the signed state log with Merkle linkage
#[derive(Debug, Clone)]
pub struct SignedStateEntry {
    pub mutation: SignedMutation,
    pub merkle_hash: [u8; 32],
    pub parent_hash: [u8; 32],
    pub seq: u64,
}

/// Immutable audit log for signed state mutations
#[derive(Debug)]
pub struct SignedStateLog {
    entries: Mutex<Vec<SignedStateEntry>>,
    last_hash: Mutex<[u8; 32]>,
}

impl SignedStateLog {
    /// Create new log
    pub fn new() -> Self {
        Self {
            entries: Mutex::new(Vec::new()),
            last_hash: Mutex::new([0u8; 32]),
        }
    }

    /// Append a signed mutation to the log
    pub fn append(&self, mutation: SignedMutation) -> Result<SignedStateEntry, StateLogError> {
        let mut entries = self.entries.lock().unwrap();
        let mut last_hash = self.last_hash.lock().unwrap();

        let parent_hash = *last_hash;

        // Compute merkle_hash: sha256(parent_hash || signature || context_id || timestamp_bytes)
        let timestamp_bytes = mutation.timestamp.timestamp().to_le_bytes();
        let merkle_input = [
            &parent_hash[..],
            &mutation.signature[..],
            mutation.context_id.as_bytes(),
            &timestamp_bytes[..],
        ]
        .concat();
        let merkle_hash = sha256(&merkle_input);

        let seq = entries.len() as u64;

        let entry = SignedStateEntry {
            mutation,
            merkle_hash,
            parent_hash,
            seq,
        };

        entries.push(entry.clone());
        *last_hash = merkle_hash;

        Ok(entry)
    }

    /// Verify chain integrity (replay all hashes)
    pub fn verify_chain(&self) -> bool {
        let entries = self.entries.lock().unwrap();

        if entries.is_empty() {
            return true;
        }

        let mut expected_parent = [0u8; 32];

        for entry in entries.iter() {
            // Check parent linkage
            if entry.parent_hash != expected_parent {
                return false;
            }

            // Verify merkle hash computation
            let timestamp_bytes = entry.mutation.timestamp.timestamp().to_le_bytes();
            let merkle_input = [
                &entry.parent_hash[..],
                &entry.mutation.signature[..],
                entry.mutation.context_id.as_bytes(),
                &timestamp_bytes[..],
            ]
            .concat();
            let computed_hash = sha256(&merkle_input);

            if computed_hash != entry.merkle_hash {
                return false;
            }

            expected_parent = entry.merkle_hash;
        }

        true
    }

    /// Get Merkle root (last hash)
    pub fn merkle_root(&self) -> [u8; 32] {
        *self.last_hash.lock().unwrap()
    }

    /// Get all entries
    pub fn entries(&self) -> Vec<SignedStateEntry> {
        self.entries.lock().unwrap().clone()
    }

    /// Get number of entries
    pub fn len(&self) -> usize {
        self.entries.lock().unwrap().len()
    }

    /// Check if log is empty
    pub fn is_empty(&self) -> bool {
        self.entries.lock().unwrap().is_empty()
    }
}

impl Default for SignedStateLog {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_log_basic_operations() {
        let log = SignedStateLog::new();
        assert!(log.is_empty());
        assert_eq!(log.len(), 0);
        assert_eq!(log.merkle_root(), [0u8; 32]);
    }
}
