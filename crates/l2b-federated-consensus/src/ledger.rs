use anyhow::Result;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Sha256, Digest};
use std::collections::VecDeque;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum LedgerError {
    #[error("Invalid entry index")]
    InvalidIndex,

    #[error("Entry not found")]
    NotFound,

    #[error("Ledger divergence detected")]
    Divergence,

    #[error("Internal error: {0}")]
    Internal(String),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LedgerEntry {
    pub index: u64,
    pub proposal_id: String,
    pub decision: Value,
    pub merkle_root: String,
    pub region: String,
    pub timestamp: DateTime<Utc>,
}

pub struct LedgerSync {
    region: String,
    entries: VecDeque<LedgerEntry>,
    merkle_root: Option<String>,
}

impl LedgerSync {
    pub fn new(region: String) -> Self {
        Self {
            region,
            entries: VecDeque::new(),
            merkle_root: None,
        }
    }

    pub async fn append_entry(&mut self, entry: LedgerEntry) -> Result<(), LedgerError> {
        // Validate sequential indexing
        let expected_index = (self.entries.len() + 1) as u64;

        if entry.index != expected_index {
            return Err(LedgerError::InvalidIndex);
        }

        // Update Merkle root
        self.update_merkle_root(&entry);

        self.entries.push_back(entry);
        Ok(())
    }

    pub async fn sync_ledger(&mut self, other: &LedgerSync) -> Result<(), LedgerError> {
        // Replicate entries from other ledger
        for entry in other.entries.iter() {
            if !self.entries.iter().any(|e| e.index == entry.index) {
                let mut entry_copy = entry.clone();
                entry_copy.region = self.region.clone();

                self.append_entry(entry_copy).await
                    .map_err(|e| LedgerError::Internal(format!("{:?}", e)))?;
            }
        }

        Ok(())
    }

    pub async fn verify_merkle_roots(&self) -> Result<String, LedgerError> {
        if self.entries.is_empty() {
            return Err(LedgerError::NotFound);
        }

        let mut hasher = Sha256::new();

        for entry in self.entries.iter() {
            hasher.update(entry.merkle_root.as_bytes());
        }

        let root = hasher.finalize();
        Ok(format!("0x{}", hex::encode(root)))
    }

    pub async fn get_entries(&self, start_index: usize) -> Result<Vec<LedgerEntry>, LedgerError> {
        let entries: Vec<LedgerEntry> = self.entries
            .iter()
            .skip(start_index)
            .cloned()
            .collect();

        if entries.is_empty() && !self.entries.is_empty() {
            return Err(LedgerError::NotFound);
        }

        Ok(entries)
    }

    pub async fn get_root(&self) -> Result<String, LedgerError> {
        self.merkle_root
            .clone()
            .ok_or(LedgerError::NotFound)
    }

    fn update_merkle_root(&mut self, entry: &LedgerEntry) {
        let mut hasher = Sha256::new();

        // Hash all previous entries
        for prev_entry in self.entries.iter() {
            hasher.update(prev_entry.merkle_root.as_bytes());
        }

        // Hash current entry
        hasher.update(entry.merkle_root.as_bytes());

        let root = hasher.finalize();
        self.merkle_root = Some(format!("0x{}", hex::encode(root)));
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ledger_creation() {
        let ledger = LedgerSync::new("EU".to_string());
        assert_eq!(ledger.region, "EU");
    }
}
