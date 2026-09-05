use crate::error::SettlementError;
use crate::settlement::{Settlement, SettlementSignature};
use std::collections::HashMap;
use uuid::Uuid;

pub struct AtomicSwap {
    commitments: HashMap<Uuid, String>,
    signatures: HashMap<Uuid, Vec<SettlementSignature>>,
}

impl AtomicSwap {
    pub fn new() -> Self {
        Self {
            commitments: HashMap::new(),
            signatures: HashMap::new(),
        }
    }

    pub fn create_commitment(
        &mut self,
        settlement: &Settlement,
    ) -> Result<String, SettlementError> {
        if self.commitments.contains_key(&settlement.id) {
            return Err(SettlementError::InvalidCommitment(
                "Commitment already exists".to_string(),
            ));
        }

        let commitment = settlement.compute_commitment_hash();
        self.commitments.insert(settlement.id, commitment.clone());
        Ok(commitment)
    }

    pub fn verify_commitment(
        &self,
        settlement_id: Uuid,
        commitment: &str,
    ) -> Result<bool, SettlementError> {
        match self.commitments.get(&settlement_id) {
            Some(stored) => Ok(stored == commitment),
            None => Err(SettlementError::NotFound("Settlement not found".to_string())),
        }
    }

    pub fn add_signature(
        &mut self,
        settlement_id: Uuid,
        signature: SettlementSignature,
    ) -> Result<(), SettlementError> {
        if !self.commitments.contains_key(&settlement_id) {
            return Err(SettlementError::NotFound("Settlement not found".to_string()));
        }

        self.signatures
            .entry(settlement_id)
            .or_insert_with(Vec::new)
            .push(signature);

        Ok(())
    }

    pub fn get_signatures(
        &self,
        settlement_id: Uuid,
    ) -> Result<Vec<SettlementSignature>, SettlementError> {
        self.signatures
            .get(&settlement_id)
            .cloned()
            .ok_or_else(|| SettlementError::NotFound("No signatures found".to_string()))
    }

    pub fn verify_signature_count(
        &self,
        settlement_id: Uuid,
        required_count: usize,
    ) -> Result<bool, SettlementError> {
        match self.signatures.get(&settlement_id) {
            Some(sigs) => Ok(sigs.len() >= required_count),
            None => Err(SettlementError::NotFound("Signatures not found".to_string())),
        }
    }

    pub fn can_commit_settlement(
        &self,
        settlement_id: Uuid,
    ) -> Result<bool, SettlementError> {
        let has_commitment = self.commitments.contains_key(&settlement_id);
        let sigs = self.get_signatures(settlement_id)?;
        Ok(has_commitment && sigs.len() >= 2)
    }

    pub fn clear_settlement(&mut self, settlement_id: Uuid) {
        self.commitments.remove(&settlement_id);
        self.signatures.remove(&settlement_id);
    }
}

impl Default for AtomicSwap {
    fn default() -> Self {
        Self::new()
    }
}
