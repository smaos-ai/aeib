use crate::types::ClaimStatus;
use chrono::Utc;
use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use thiserror::Error;
use uuid::Uuid;

#[derive(Debug, Clone, Error)]
pub enum LedgerError {
    #[error("Claim not found: {0}")]
    ClaimNotFound(Uuid),
    #[error("Invalid status transition")]
    InvalidStatusTransition,
    #[error("Ledger operation failed")]
    OperationFailed,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClaimEntry {
    pub claim_id: Uuid,
    pub policy_id: Uuid,
    pub claimant_id: Uuid,
    pub amount_cents: u64,
    pub status: ClaimStatus,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub settlement_amount: Option<u64>,
    pub settled_at: Option<chrono::DateTime<chrono::Utc>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClaimHistory {
    pub claim_id: Uuid,
    pub status: ClaimStatus,
    pub updated_at: chrono::DateTime<chrono::Utc>,
}

/// PostgreSQL-backed claim ledger (in-memory simulation)
pub struct ClaimLedger {
    claims: DashMap<Uuid, ClaimEntry>,
    history: DashMap<Uuid, Vec<ClaimHistory>>,
}

impl ClaimLedger {
    pub fn new() -> Self {
        Self {
            claims: DashMap::new(),
            history: DashMap::new(),
        }
    }

    /// Record a new claim in the ledger
    pub fn record_claim(
        &self,
        claim_id: Uuid,
        policy_id: Uuid,
        claimant_id: Uuid,
        amount_cents: u64,
    ) -> Result<ClaimEntry, LedgerError> {
        let entry = ClaimEntry {
            claim_id,
            policy_id,
            claimant_id,
            amount_cents,
            status: ClaimStatus::Submitted,
            created_at: Utc::now(),
            settlement_amount: None,
            settled_at: None,
        };

        self.claims.insert(claim_id, entry.clone());

        // Initialize history with submission
        let mut hist = vec![];
        hist.push(ClaimHistory {
            claim_id,
            status: ClaimStatus::Submitted,
            updated_at: Utc::now(),
        });
        self.history.insert(claim_id, hist);

        Ok(entry)
    }

    /// Retrieve a claim from the ledger
    pub fn get_claim(&self, claim_id: &Uuid) -> Result<ClaimEntry, LedgerError> {
        self.claims
            .get(claim_id)
            .map(|entry| entry.clone())
            .ok_or(LedgerError::ClaimNotFound(*claim_id))
    }

    /// Update claim status with audit trail
    pub fn update_claim_status(
        &self,
        claim_id: &Uuid,
        new_status: ClaimStatus,
    ) -> Result<ClaimEntry, LedgerError> {
        let mut entry = self
            .claims
            .get_mut(claim_id)
            .ok_or(LedgerError::ClaimNotFound(*claim_id))?;

        entry.status = new_status;

        // Add to history
        if let Some(mut hist) = self.history.get_mut(claim_id) {
            hist.push(ClaimHistory {
                claim_id: *claim_id,
                status: new_status,
                updated_at: Utc::now(),
            });
        }

        Ok(entry.clone())
    }

    /// Settle a claim (mark as paid)
    pub fn settle_claim(
        &self,
        claim_id: &Uuid,
        settlement_amount: u64,
    ) -> Result<ClaimEntry, LedgerError> {
        let mut entry = self
            .claims
            .get_mut(claim_id)
            .ok_or(LedgerError::ClaimNotFound(*claim_id))?;

        entry.status = ClaimStatus::Paid;
        entry.settlement_amount = Some(settlement_amount);
        entry.settled_at = Some(Utc::now());

        // Add to history
        if let Some(mut hist) = self.history.get_mut(claim_id) {
            hist.push(ClaimHistory {
                claim_id: *claim_id,
                status: ClaimStatus::Paid,
                updated_at: Utc::now(),
            });
        }

        Ok(entry.clone())
    }

    /// Get all claims for a policy
    pub fn get_claims_by_policy(&self, policy_id: &Uuid) -> Result<Vec<ClaimEntry>, LedgerError> {
        let claims: Vec<_> = self
            .claims
            .iter()
            .filter(|entry| entry.policy_id == *policy_id)
            .map(|entry| entry.clone())
            .collect();

        Ok(claims)
    }

    /// Get claim status history
    pub fn get_claim_history(&self, claim_id: &Uuid) -> Result<Vec<ClaimHistory>, LedgerError> {
        self.history
            .get(claim_id)
            .map(|hist| hist.clone())
            .ok_or(LedgerError::ClaimNotFound(*claim_id))
    }

    /// Get all claims (for audit)
    pub fn get_all_claims(&self) -> Result<Vec<ClaimEntry>, LedgerError> {
        let claims: Vec<_> = self.claims.iter().map(|entry| entry.clone()).collect();
        Ok(claims)
    }
}

impl Default for ClaimLedger {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ledger_operations() {
        let ledger = ClaimLedger::new();
        let claim_id = Uuid::new_v4();
        let policy_id = Uuid::new_v4();
        let claimant_id = Uuid::new_v4();

        let entry = ledger
            .record_claim(claim_id, policy_id, claimant_id, 100_000_00)
            .unwrap();
        assert_eq!(entry.status, ClaimStatus::Submitted);

        let retrieved = ledger.get_claim(&claim_id).unwrap();
        assert_eq!(retrieved.claim_id, claim_id);
    }
}
