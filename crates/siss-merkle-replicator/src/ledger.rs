use chrono::{DateTime, Utc};
use sha2::{Digest, Sha256};
use std::sync::{Arc, Mutex};

#[derive(Debug, Clone)]
pub struct MerkleRootEntry {
    pub parent_hash: [u8; 32],
    pub merkle_hash: [u8; 32],
    pub data_hash: [u8; 32],
    pub seq: u64,
    pub timestamp: DateTime<Utc>,
}

pub struct MerkleRootLedger {
    entries: Arc<Mutex<Vec<MerkleRootEntry>>>,
    last_merkle_hash: Arc<Mutex<[u8; 32]>>,
}

impl MerkleRootLedger {
    pub fn new() -> Self {
        Self {
            entries: Arc::new(Mutex::new(Vec::new())),
            last_merkle_hash: Arc::new(Mutex::new([0u8; 32])),
        }
    }

    pub fn append(&self, data_hash: [u8; 32]) -> Result<MerkleRootEntry, String> {
        let mut entries = self.entries.lock().unwrap();
        let seq = entries.len() as u64;

        // Get parent hash (previous merkle hash or 0)
        let parent_hash = if seq > 0 {
            entries[seq as usize - 1].merkle_hash
        } else {
            [0u8; 32]
        };

        // Compute merkle hash = sha256(parent || data || seq)
        let mut hasher = Sha256::new();
        hasher.update(parent_hash);
        hasher.update(data_hash);
        hasher.update(seq.to_le_bytes());
        let merkle_hash_result = hasher.finalize();

        let mut merkle_hash = [0u8; 32];
        merkle_hash.copy_from_slice(&merkle_hash_result[..]);

        let entry = MerkleRootEntry {
            parent_hash,
            merkle_hash,
            data_hash,
            seq,
            timestamp: Utc::now(),
        };

        entries.push(entry.clone());

        // Update last merkle hash
        *self.last_merkle_hash.lock().unwrap() = merkle_hash;

        Ok(entry)
    }

    pub fn verify_chain(&self) -> bool {
        let entries = self.entries.lock().unwrap();

        for (i, entry) in entries.iter().enumerate() {
            let expected_parent = if i > 0 {
                entries[i - 1].merkle_hash
            } else {
                [0u8; 32]
            };

            if entry.parent_hash != expected_parent {
                return false;
            }

            // Recompute merkle hash
            let mut hasher = Sha256::new();
            hasher.update(entry.parent_hash);
            hasher.update(entry.data_hash);
            hasher.update(entry.seq.to_le_bytes());
            let computed = hasher.finalize();

            let mut computed_hash = [0u8; 32];
            computed_hash.copy_from_slice(&computed[..]);

            if entry.merkle_hash != computed_hash {
                return false;
            }
        }

        true
    }

    pub fn get_root(&self) -> [u8; 32] {
        *self.last_merkle_hash.lock().unwrap()
    }

    pub fn len(&self) -> usize {
        self.entries.lock().unwrap().len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.lock().unwrap().is_empty()
    }
}

impl Default for MerkleRootLedger {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_merkle_root_deterministic() {
        let ledger = MerkleRootLedger::new();

        // Append 3 items
        let h1 = [1u8; 32];
        let h2 = [2u8; 32];
        let h3 = [3u8; 32];

        let _e1 = ledger.append(h1).unwrap();
        let _e2 = ledger.append(h2).unwrap();
        let e3 = ledger.append(h3).unwrap();

        let root1 = ledger.get_root();

        // Verify the root is consistent
        assert_eq!(root1, e3.merkle_hash);

        // Create another ledger and append the same items
        let ledger2 = MerkleRootLedger::new();
        ledger2.append(h1).unwrap();
        ledger2.append(h2).unwrap();
        ledger2.append(h3).unwrap();

        let root2 = ledger2.get_root();

        // Roots should be identical (deterministic)
        assert_eq!(root1, root2);
    }

    #[test]
    fn test_merkle_chain_integrity() {
        let ledger = MerkleRootLedger::new();

        ledger.append([1u8; 32]).unwrap();
        ledger.append([2u8; 32]).unwrap();
        ledger.append([3u8; 32]).unwrap();

        // Chain should be valid
        assert!(ledger.verify_chain());

        // Mutate an entry and verify detection
        {
            let mut entries = ledger.entries.lock().unwrap();
            if let Some(entry) = entries.get_mut(1) {
                entry.data_hash[0] ^= 0xFF; // Flip bits
            }
        }

        // Verification should fail
        assert!(!ledger.verify_chain());
    }

    #[test]
    fn test_sequence_number_monotonic() {
        let ledger = MerkleRootLedger::new();

        let mut last_seq: i64 = -1;
        for i in 0..5 {
            let entry = ledger.append([i as u8; 32]).unwrap();
            assert_eq!(entry.seq, i as u64);
            assert!(entry.seq as i64 > last_seq);
            last_seq = entry.seq as i64;
        }

        // Verify all sequences 0-4
        assert_eq!(ledger.len(), 5);
        let entries = ledger.entries.lock().unwrap();
        for (i, entry) in entries.iter().enumerate() {
            assert_eq!(entry.seq, i as u64);
        }
    }
}
