// Stub implementation for state_log module
use crate::signing::SignedMutation;
use thiserror::Error;

#[derive(Debug, Clone, Error)]
pub enum StateLogError {
    #[error("Verification failed")]
    VerificationFailed,
    #[error("IO error")]
    IoError,
}

#[derive(Debug)]
pub struct SignedStateLog {
    _entries: Vec<Vec<u8>>,
}

impl SignedStateLog {
    pub fn new() -> Self {
        Self {
            _entries: Vec::new(),
        }
    }

    pub fn append(&self, _mutation: SignedMutation) -> Result<(), StateLogError> {
        Ok(())
    }
}

impl Default for SignedStateLog {
    fn default() -> Self {
        Self::new()
    }
}
