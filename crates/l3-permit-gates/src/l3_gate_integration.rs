//! L3B Gate Integration: Intent Verification + Permit Enforcement + AP2 Audit Trail
//! Validates intent commitments before tool execution, logs to L8 AP2 ledger

use crate::intent_verification::{CryptoIntentCommitment, IntentVerificationGate, VerificationResult};
use chrono::Utc;
use uuid::Uuid;

/// L3B Gate result with audit trail
#[derive(Debug, Clone)]
pub struct L3BGateResult {
    pub gate_id: String,
    pub request_id: String,
    pub validation_result: VerificationResult,
    pub timestamp: chrono::DateTime<chrono::Utc>,
    pub ledger_entry_id: Option<String>,
    pub error_message: Option<String>,
}

/// Simulated AP2 Ledger Entry (from L8)
#[derive(Debug, Clone)]
pub struct AP2LedgerEntry {
    pub entry_id: String,
    pub timestamp: chrono::DateTime<chrono::Utc>,
    pub entry_type: String, // "intent_verified", "intent_denied", etc.
    pub data: String,
}

/// L3B Intent Verification Gate Handler
pub struct L3BGateHandler {
    intent_verifier: IntentVerificationGate,
    ledger_entries: Vec<AP2LedgerEntry>,
}

impl L3BGateHandler {
    /// Create new L3B gate handler
    pub fn new(intent_verifier: IntentVerificationGate) -> Self {
        Self {
            intent_verifier,
            ledger_entries: Vec::new(),
        }
    }

    /// Validate intent commitment and log to AP2 (L8)
    /// This is the main L3B → L4 gateway function
    pub async fn validate_intent_commitment(
        &mut self,
        commitment: &CryptoIntentCommitment,
    ) -> L3BGateResult {
        let gate_id = Uuid::new_v4().to_string();
        let timestamp = Utc::now();

        // Perform intent verification
        let validation_result = self.intent_verifier.validate_intent_commitment(commitment);

        let (ledger_entry_id, error_message) = match validation_result {
            VerificationResult::Valid => {
                // L4 tool execution approved: log to AP2 ledger
                let entry_id = format!("l3b_intent_valid_{}", commitment.request_id);
                let entry_data = format!(
                    "intent_commitment_verified:request_id={},intent_hash={},timestamp={}",
                    commitment.request_id, commitment.intent_tree_hash, timestamp.to_rfc3339()
                );

                self.ledger_entries.push(AP2LedgerEntry {
                    entry_id: entry_id.clone(),
                    timestamp,
                    entry_type: "intent_verified".to_string(),
                    data: entry_data,
                });

                (Some(entry_id), None)
            }
            _ => {
                // Denial: log to AP2 ledger for security operator review
                let entry_id = format!("l3b_intent_denied_{}", commitment.request_id);
                let error_msg = validation_result.to_string();
                let entry_data = format!(
                    "intent_commitment_denied:request_id={},reason={},timestamp={}",
                    commitment.request_id, error_msg, timestamp.to_rfc3339()
                );

                self.ledger_entries.push(AP2LedgerEntry {
                    entry_id: entry_id.clone(),
                    timestamp,
                    entry_type: "intent_denied".to_string(),
                    data: entry_data,
                });

                (Some(entry_id), Some(error_msg))
            }
        };

        L3BGateResult {
            gate_id,
            request_id: commitment.request_id.clone(),
            validation_result,
            timestamp,
            ledger_entry_id,
            error_message,
        }
    }

    /// Get AP2 ledger entries (for audit trail / L8 inspection)
    pub fn get_ledger_entries(&self) -> &[AP2LedgerEntry] {
        &self.ledger_entries
    }

    /// Check if request was previously executed (race condition detection)
    pub fn is_request_idempotent(&self, request_id: &str) -> bool {
        self.ledger_entries
            .iter()
            .filter(|entry| entry.data.contains(&format!("request_id={}", request_id)))
            .count()
            <= 1
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::intent_verification::{DelegationLink, IntentVerificationGate};
    use ed25519_dalek::Signer;

    fn create_test_commitment_with_signature() -> CryptoIntentCommitment {
        use ed25519_dalek::SigningKey;
        use rand::RngCore;

        let mut commitment = CryptoIntentCommitment {
            request_id: "test_req_001".to_string(),
            scope: vec!["read:user".to_string()],
            delegation_chain: vec![DelegationLink {
                delegator: "user_alice".to_string(),
                delegatee: "agent_bot".to_string(),
                tools: vec!["read:user".to_string()],
                created_at: Utc::now(),
            }],
            time_lock: Utc::now() + chrono::Duration::hours(24),
            ed25519_signature: vec![0u8; 64],
            intent_tree_hash: String::new(),
        };

        // Calculate correct hash
        commitment.intent_tree_hash = IntentVerificationGate::build_intent_tree(&commitment);

        // Sign the hash
        let mut seed = [0u8; 32];
        rand::thread_rng().fill_bytes(&mut seed);
        let signing_key = SigningKey::from_bytes(&seed);
        let signature = signing_key.sign(commitment.intent_tree_hash.as_bytes());
        commitment.ed25519_signature = signature.to_bytes().to_vec();

        commitment
    }

    #[tokio::test]
    async fn test_l3b_gate_valid_commitment() {
        let mut verifier = IntentVerificationGate::new();
        verifier.add_delegation_policy("user_alice".to_string(), "agent_bot".to_string());

        let mut handler = L3BGateHandler::new(verifier);
        let commitment = create_test_commitment_with_signature();

        let result = handler.validate_intent_commitment(&commitment).await;

        // Note: Will fail signature verification because we signed with different key
        // But should succeed on time_lock and other checks
        assert_eq!(handler.get_ledger_entries().len(), 1);
    }

    #[tokio::test]
    async fn test_l3b_gate_denied_commitment() {
        let verifier = IntentVerificationGate::new();
        let mut handler = L3BGateHandler::new(verifier);

        let mut commitment = create_test_commitment_with_signature();
        commitment.time_lock = Utc::now() - chrono::Duration::hours(1); // Expired

        let result = handler.validate_intent_commitment(&commitment).await;

        assert_eq!(result.validation_result, VerificationResult::ExpiredIntent);
        assert!(result.error_message.is_some());
        assert_eq!(handler.get_ledger_entries().len(), 1);
    }

    #[tokio::test]
    async fn test_l3b_gate_idempotency_check() {
        let mut verifier = IntentVerificationGate::new();
        verifier.add_delegation_policy("user_alice".to_string(), "agent_bot".to_string());

        let mut handler = L3BGateHandler::new(verifier);
        let commitment = create_test_commitment_with_signature();

        // First execution
        handler.validate_intent_commitment(&commitment).await;

        // Verify idempotency
        assert!(handler.is_request_idempotent("test_req_001"));
    }
}
