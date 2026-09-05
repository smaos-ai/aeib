use crate::attestation::sha256;
use chrono::{DateTime, Utc};
use std::sync::Mutex;
use thiserror::Error;
use uuid::Uuid;

#[derive(Debug, Clone, Error)]
pub enum ExecLogError {
    #[error("Log is empty")]
    Empty,
    #[error("Entry not found")]
    NotFound,
    #[error("Merkle chain verification failed")]
    VerificationFailed,
}

#[derive(Debug, Clone)]
pub struct ExecLogEntry {
    pub id: i64,
    pub mandate_id: Uuid,
    pub action: String,
    pub tool_name: String,
    pub result_hash: [u8; 32],
    pub merkle_hash: [u8; 32],
    pub parent_merkle_hash: [u8; 32],
    pub created_at: DateTime<Utc>,
}

pub struct InMemoryAuditLog {
    entries: Mutex<Vec<ExecLogEntry>>,
}

impl InMemoryAuditLog {
    pub fn new() -> Self {
        Self {
            entries: Mutex::new(Vec::new()),
        }
    }

    pub fn append(
        &self,
        mandate_id: Uuid,
        action: &str,
        tool_name: &str,
        result_hash: [u8; 32],
    ) -> Result<ExecLogEntry, ExecLogError> {
        let mut entries = self.entries.lock().unwrap();

        let parent_merkle_hash = if entries.is_empty() {
            [0u8; 32]
        } else {
            entries.last().unwrap().merkle_hash
        };

        let merkle_input = [
            &parent_merkle_hash[..],
            &mandate_id.as_bytes()[..],
            action.as_bytes(),
            tool_name.as_bytes(),
            &result_hash[..],
        ]
        .concat();
        let merkle_hash = sha256(&merkle_input);

        let entry = ExecLogEntry {
            id: entries.len() as i64,
            mandate_id,
            action: action.to_string(),
            tool_name: tool_name.to_string(),
            result_hash,
            merkle_hash,
            parent_merkle_hash,
            created_at: Utc::now(),
        };

        entries.push(entry.clone());
        Ok(entry)
    }

    pub fn verify_chain(&self) -> Result<bool, ExecLogError> {
        let entries = self.entries.lock().unwrap();
        if entries.is_empty() {
            return Ok(true);
        }

        for (i, entry) in entries.iter().enumerate() {
            let expected_parent = if i == 0 {
                [0u8; 32]
            } else {
                entries[i - 1].merkle_hash
            };

            if entry.parent_merkle_hash != expected_parent {
                return Ok(false);
            }

            // Verify merkle hash computation
            let merkle_input = [
                &entry.parent_merkle_hash[..],
                &entry.mandate_id.as_bytes()[..],
                entry.action.as_bytes(),
                entry.tool_name.as_bytes(),
                &entry.result_hash[..],
            ]
            .concat();
            let computed_hash = sha256(&merkle_input);
            if computed_hash != entry.merkle_hash {
                return Ok(false);
            }
        }

        Ok(true)
    }

    pub fn merkle_root(&self) -> Result<[u8; 32], ExecLogError> {
        let entries = self.entries.lock().unwrap();
        if entries.is_empty() {
            return Ok([0u8; 32]);
        }
        Ok(entries.last().unwrap().merkle_hash)
    }

    pub fn get_entry(&self, id: i64) -> Result<ExecLogEntry, ExecLogError> {
        let entries = self.entries.lock().unwrap();
        entries
            .get(id as usize)
            .cloned()
            .ok_or(ExecLogError::NotFound)
    }

    pub fn entry_count(&self) -> usize {
        self.entries.lock().unwrap().len()
    }
}

impl Default for InMemoryAuditLog {
    fn default() -> Self {
        Self::new()
    }
}
