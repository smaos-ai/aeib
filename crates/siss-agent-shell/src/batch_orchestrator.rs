/// Phase 57: Batch Orchestrator — Collision-Free 50–100 Parallel Agent Fan-Out
/// INVARIANT: InMemoryClaimLedger enforces first-wins file ownership via Mutex atomicity.

use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::Mutex;
use uuid::Uuid;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ClaimError {
    AlreadyClaimed { owner_id: Uuid },
    InvalidWorkItem,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FileClaim {
    pub file_path: String,
    pub owner_id: Uuid,
    pub claimed_at: chrono::DateTime<chrono::Utc>,
}

pub struct InMemoryClaimLedger {
    claims: Arc<Mutex<HashMap<String, FileClaim>>>,
}

impl InMemoryClaimLedger {
    /// Create new ledger.
    pub fn new() -> Self {
        InMemoryClaimLedger {
            claims: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    /// Attempt to claim a file for exclusive access.
    /// RULE 1: file_path must not be empty → Err(InvalidWorkItem) if empty
    /// RULE 2: Acquire Mutex lock on claims map
    /// RULE 3: Check if file_path already claimed
    /// RULE 4: If claimed by different owner → Err(AlreadyClaimed { owner_id })
    /// RULE 5: If unclaimed or claimed by same owner → insert/update claim, return Ok(FileClaim)
    pub async fn claim_file(&self, file_path: &str, owner_id: Uuid) -> Result<FileClaim, ClaimError> {
        if file_path.is_empty() {
            return Err(ClaimError::InvalidWorkItem);
        }

        let mut claims = self.claims.lock().await;

        if let Some(existing) = claims.get(file_path) {
            if existing.owner_id != owner_id {
                return Err(ClaimError::AlreadyClaimed {
                    owner_id: existing.owner_id,
                });
            }
        }

        let claim = FileClaim {
            file_path: file_path.to_string(),
            owner_id,
            claimed_at: chrono::Utc::now(),
        };
        claims.insert(file_path.to_string(), claim.clone());
        Ok(claim)
    }

    /// Release a file claim.
    /// RULE 6: Only the owner can release
    /// RULE 7: Err(AlreadyClaimed) if different owner tries to release
    pub async fn release_file(&self, file_path: &str, owner_id: Uuid) -> Result<(), ClaimError> {
        let mut claims = self.claims.lock().await;

        if let Some(existing) = claims.get(file_path) {
            if existing.owner_id != owner_id {
                return Err(ClaimError::AlreadyClaimed {
                    owner_id: existing.owner_id,
                });
            }
        }

        claims.remove(file_path);
        Ok(())
    }

    /// Get current state of a claim.
    pub async fn get_claim(&self, file_path: &str) -> Option<FileClaim> {
        let claims = self.claims.lock().await;
        claims.get(file_path).cloned()
    }
}

impl Default for InMemoryClaimLedger {
    fn default() -> Self {
        InMemoryClaimLedger::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_claim_file_succeeds() {
        let ledger = InMemoryClaimLedger::new();
        let agent_id = Uuid::new_v4();
        let result = ledger.claim_file("test.txt", agent_id).await;
        assert!(result.is_ok());
        let claim = result.unwrap();
        assert_eq!(claim.file_path, "test.txt");
        assert_eq!(claim.owner_id, agent_id);
    }

    #[tokio::test]
    async fn test_claim_collision_rejects_second_owner() {
        let ledger = InMemoryClaimLedger::new();
        let agent1 = Uuid::new_v4();
        let agent2 = Uuid::new_v4();

        let _ = ledger.claim_file("exclusive.txt", agent1).await;
        let result = ledger.claim_file("exclusive.txt", agent2).await;
        assert_eq!(result, Err(ClaimError::AlreadyClaimed { owner_id: agent1 }));
    }

    #[tokio::test]
    async fn test_release_file_only_by_owner() {
        let ledger = InMemoryClaimLedger::new();
        let owner = Uuid::new_v4();
        let other = Uuid::new_v4();

        let _ = ledger.claim_file("owned.txt", owner).await;
        let result = ledger.release_file("owned.txt", other).await;
        assert_eq!(result, Err(ClaimError::AlreadyClaimed { owner_id: owner }));

        let result = ledger.release_file("owned.txt", owner).await;
        assert!(result.is_ok());
    }
}
