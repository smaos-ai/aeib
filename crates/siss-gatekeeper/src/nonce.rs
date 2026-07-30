/// Phase 41: Nonce Burn Protocol — one-time-use mandate enforcement
/// Abstracted as trait for both in-memory (tests) and PostgreSQL (production) implementations
use std::collections::HashSet;
use std::sync::Mutex;
use thiserror::Error;
use uuid::Uuid;

/// Error returned by NonceLedger operations
#[derive(Debug, Error, Clone, PartialEq, Eq)]
pub enum NonceBurnError {
    #[error("nonce already burned")]
    AlreadyBurned,
    #[error("storage error: {0}")]
    StorageError(String),
}

/// Trait for nonce burn ledger (one-time-use enforcement)
pub trait NonceLedger: Send + Sync {
    /// Burn a nonce (consume it for one-time use). Returns Ok if first time, Err if already burned.
    fn burn(&self, nonce: &str, mandate_id: Uuid) -> Result<(), NonceBurnError>;
    /// Check if a nonce has been burned
    fn is_burned(&self, nonce: &str) -> bool;
}

/// In-memory nonce ledger (for testing)
pub struct InMemoryNonceLedger {
    burned: Mutex<HashSet<String>>,
}

impl InMemoryNonceLedger {
    pub fn new() -> Self {
        Self {
            burned: Mutex::new(HashSet::new()),
        }
    }
}

impl Default for InMemoryNonceLedger {
    fn default() -> Self {
        Self::new()
    }
}

impl NonceLedger for InMemoryNonceLedger {
    fn burn(&self, nonce: &str, _mandate_id: Uuid) -> Result<(), NonceBurnError> {
        let mut burned = self.burned.lock().unwrap();
        if burned.contains(nonce) {
            Err(NonceBurnError::AlreadyBurned)
        } else {
            burned.insert(nonce.to_string());
            Ok(())
        }
    }

    fn is_burned(&self, nonce: &str) -> bool {
        let burned = self.burned.lock().unwrap();
        burned.contains(nonce)
    }
}
