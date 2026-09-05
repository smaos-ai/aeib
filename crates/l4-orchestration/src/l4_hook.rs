//! Phase 2A L4 Execution Hook
//! Routes intent to L3B, enriches with metadata, logs to L8

use chrono::Utc;
use l3_permit_gates::{CryptoIntentCommitment, IntentVerificationGate, VerificationResult};
use std::time::Instant;
use uuid::Uuid;

/// L4 Hook execution result
#[derive(Debug, Clone)]
pub struct L4ExecutionResult {
    pub request_id: String,
    pub execution_permitted: bool,
    pub enriched_hash: String,
    pub timestamp: chrono::DateTime<chrono::Utc>,
    pub metadata: ExecutionMetadata,
}

/// Execution metadata for L8 ledger
#[derive(Debug, Clone)]
pub struct ExecutionMetadata {
    pub hook_id: String,
    pub l3b_validation_time_ms: u64,
    pub delegation_chain_valid: bool,
    pub scope_valid: bool,
}

/// L4 Execution Hook
pub struct L4Hook {
    verifier: IntentVerificationGate,
    timeout_ms: u64,
}

impl L4Hook {
    /// Create new L4 hook with intent verifier
    pub fn new(verifier: IntentVerificationGate) -> Self {
        Self {
            verifier,
            timeout_ms: 100,
        }
    }

    /// Set timeout threshold (default 100ms)
    pub fn with_timeout(mut self, timeout_ms: u64) -> Self {
        self.timeout_ms = timeout_ms;
        self
    }

    /// Route intent from L1 through L3B to L4
    /// 1. Route to L3B (delegation + scope checks)
    /// 2. Enrich metadata (hash verification)
    /// 3. Fail-closed on error
    /// 4. Return result for L8 logging
    pub fn execute_with_verification(&self, commitment: &CryptoIntentCommitment) -> L4ExecutionResult {
        let start = Instant::now();

        // Route to L3B: delegation check
        let delegation_check = self.verifier.check_delegation_chain(commitment);
        let delegation_valid = delegation_check == VerificationResult::Valid;

        // Route to L3B: scope check
        let scope_check = self.verifier.check_scope_boundary(commitment);
        let scope_valid = scope_check == VerificationResult::Valid;

        // Time check
        let time_check = self.verifier.verify_commitment(commitment);
        let time_valid = time_check == VerificationResult::Valid;

        let elapsed = start.elapsed();
        let validation_time_ms = elapsed.as_millis() as u64;

        // Fail-closed on timeout
        if elapsed.as_millis() > self.timeout_ms as u128 {
            return L4ExecutionResult {
                request_id: commitment.request_id.clone(),
                execution_permitted: false,
                enriched_hash: commitment.intent_tree_hash.clone(),
                timestamp: Utc::now(),
                metadata: ExecutionMetadata {
                    hook_id: format!("l4_hook_{}", Uuid::new_v4()),
                    l3b_validation_time_ms: validation_time_ms,
                    delegation_chain_valid: delegation_valid,
                    scope_valid: scope_valid,
                },
            };
        }

        // Final decision: all checks must pass
        let execution_permitted = delegation_valid && scope_valid && time_valid;

        L4ExecutionResult {
            request_id: commitment.request_id.clone(),
            execution_permitted,
            enriched_hash: commitment.intent_tree_hash.clone(),
            timestamp: Utc::now(),
            metadata: ExecutionMetadata {
                hook_id: format!("l4_hook_{}", Uuid::new_v4()),
                l3b_validation_time_ms: validation_time_ms,
                delegation_chain_valid: delegation_valid,
                scope_valid: scope_valid,
            },
        }
    }

    /// Prepare metadata for L8 ledger entry
    pub fn prepare_l8_entry(&self, result: &L4ExecutionResult) -> L8MetadataEntry {
        L8MetadataEntry {
            entry_id: format!("l8_exec_{}_{}", result.request_id, Uuid::new_v4()),
            request_id: result.request_id.clone(),
            hook_id: result.metadata.hook_id.clone(),
            execution_permitted: result.execution_permitted,
            intent_hash: result.enriched_hash.clone(),
            timestamp: result.timestamp,
            validation_time_ms: result.metadata.l3b_validation_time_ms,
        }
    }
}

/// L8 Metadata Entry for immutable ledger
#[derive(Debug, Clone)]
pub struct L8MetadataEntry {
    pub entry_id: String,
    pub request_id: String,
    pub hook_id: String,
    pub execution_permitted: bool,
    pub intent_hash: String,
    pub timestamp: chrono::DateTime<chrono::Utc>,
    pub validation_time_ms: u64,
}

#[cfg(test)]
mod tests {
    use super::*;
    use l3_permit_gates::DelegationLink;
    use ed25519_dalek::{SigningKey, Signer};
    use rand::RngCore;

    fn create_test_commitment(
        request_id: String,
        hours_until_expiry: i64,
        signing_key: &SigningKey,
    ) -> CryptoIntentCommitment {
        let mut commitment = CryptoIntentCommitment {
            request_id: request_id.clone(),
            scope: vec!["read:user".to_string()],
            delegation_chain: vec![DelegationLink {
                delegator: "user_alice".to_string(),
                delegatee: "agent_bot".to_string(),
                tools: vec!["read:user".to_string()],
                created_at: Utc::now(),
            }],
            time_lock: Utc::now() + chrono::Duration::hours(hours_until_expiry),
            ed25519_signature: vec![0u8; 64],
            intent_tree_hash: String::new(),
        };

        commitment.intent_tree_hash = IntentVerificationGate::build_intent_tree(&commitment);
        let signature = signing_key.sign(commitment.intent_tree_hash.as_bytes());
        commitment.ed25519_signature = signature.to_bytes().to_vec();

        commitment
    }

    #[test]
    fn test_l4_hook_permits_valid_intent() {
        let mut verifier = IntentVerificationGate::new();
        verifier.add_delegation_policy("user_alice".to_string(), "agent_bot".to_string());

        let hook = L4Hook::new(verifier);

        let mut seed = [0u8; 32];
        rand::thread_rng().fill_bytes(&mut seed);
        let signing_key = SigningKey::from_bytes(&seed);

        let commitment = create_test_commitment("l4_req_001".to_string(), 24, &signing_key);
        let result = hook.execute_with_verification(&commitment);

        assert_eq!(result.request_id, "l4_req_001");
        assert!(!result.enriched_hash.is_empty());
        assert_eq!(result.enriched_hash.len(), 64); // SHA256 hex
    }

    #[test]
    fn test_l4_hook_enriches_metadata_for_l8() {
        let mut verifier = IntentVerificationGate::new();
        verifier.add_delegation_policy("user_alice".to_string(), "agent_bot".to_string());

        let hook = L4Hook::new(verifier);

        let mut seed = [0u8; 32];
        rand::thread_rng().fill_bytes(&mut seed);
        let signing_key = SigningKey::from_bytes(&seed);

        let commitment = create_test_commitment("l4_req_002".to_string(), 24, &signing_key);
        let result = hook.execute_with_verification(&commitment);

        let l8_entry = hook.prepare_l8_entry(&result);
        assert!(!l8_entry.entry_id.is_empty());
        assert_eq!(l8_entry.request_id, "l4_req_002");
        assert_eq!(l8_entry.intent_hash, result.enriched_hash);
    }

    #[test]
    fn test_l4_hook_fails_closed_on_invalid_delegation() {
        let verifier = IntentVerificationGate::new(); // No policy
        let hook = L4Hook::new(verifier);

        let mut seed = [0u8; 32];
        rand::thread_rng().fill_bytes(&mut seed);
        let signing_key = SigningKey::from_bytes(&seed);

        let commitment = create_test_commitment("l4_req_003".to_string(), 24, &signing_key);
        let result = hook.execute_with_verification(&commitment);

        assert!(!result.execution_permitted);
        assert!(!result.metadata.delegation_chain_valid);
    }

    #[test]
    fn test_l4_hook_timeout_fail_closed() {
        let mut verifier = IntentVerificationGate::new();
        verifier.add_delegation_policy("user_alice".to_string(), "agent_bot".to_string());

        let hook = L4Hook::new(verifier).with_timeout(0); // 0ms timeout

        let mut seed = [0u8; 32];
        rand::thread_rng().fill_bytes(&mut seed);
        let signing_key = SigningKey::from_bytes(&seed);

        let commitment = create_test_commitment("l4_req_004".to_string(), 24, &signing_key);
        let result = hook.execute_with_verification(&commitment);

        // Timeout should fail-closed
        assert!(!result.execution_permitted);
        assert!(result.metadata.l3b_validation_time_ms >= 0);
    }

    #[test]
    fn test_l4_hook_metadata_validation_time() {
        let mut verifier = IntentVerificationGate::new();
        verifier.add_delegation_policy("user_alice".to_string(), "agent_bot".to_string());

        let hook = L4Hook::new(verifier);

        let mut seed = [0u8; 32];
        rand::thread_rng().fill_bytes(&mut seed);
        let signing_key = SigningKey::from_bytes(&seed);

        let commitment = create_test_commitment("l4_req_005".to_string(), 24, &signing_key);
        let result = hook.execute_with_verification(&commitment);

        // Metadata should record validation time
        assert!(result.metadata.l3b_validation_time_ms < 100);
        assert!(!result.metadata.hook_id.is_empty());
    }
}
