use uuid::Uuid;
use std::collections::HashMap;
use std::time::{SystemTime, UNIX_EPOCH};
use super::prepare::{PrepareRequest, PrepareToken};

#[derive(Clone)]
pub struct CapsuleEntry {
    pub capsule_id: Uuid,
    pub reservation_id: Uuid,
    pub committed_at: u64,
}

pub struct CapsuleCommitActor {
    pending: HashMap<Uuid, PrepareToken>,
    committed: Vec<CapsuleEntry>,
}

impl CapsuleCommitActor {
    pub fn new() -> Self {
        Self {
            pending: HashMap::new(),
            committed: Vec::new(),
        }
    }

    pub fn submit_prepare(&mut self, req: PrepareRequest) -> Result<PrepareToken, String> {
        let token = req.validate()?;
        self.pending.insert(token.reservation_id, token.clone());
        Ok(token)
    }

    pub fn commit(&mut self, token: PrepareToken) -> Result<CapsuleEntry, String> {
        // Remove token from pending if it exists (may have been submitted or directly validated)
        self.pending.remove(&token.reservation_id);

        let committed_at = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_err(|e| format!("Failed to get current time: {}", e))?
            .as_secs();

        let entry = CapsuleEntry {
            capsule_id: token.capsule_id,
            reservation_id: token.reservation_id,
            committed_at,
        };

        self.committed.push(entry.clone());
        Ok(entry)
    }

    pub fn abort(&mut self, token: PrepareToken) -> Result<(), String> {
        // Remove token from pending if it exists (may have been submitted or directly validated)
        self.pending.remove(&token.reservation_id);
        Ok(())
    }

    pub fn committed_count(&self) -> usize {
        self.committed.len()
    }
}
