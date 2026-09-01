//! Phase 2A Intent Verification Protocol
//! Validates cryptographic commitments before tool execution (L1→L3B→L4→L8 flow)
//! Threat models: ASI01 (intent hijacking), privilege escalation, Byzantine delegation, TOCTOU

use chrono::{DateTime, Utc};
use ed25519_dalek::{Signature, SigningKey, Verifier, VerifyingKey};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

/// Signed intent commitment with delegation chain and time lock
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CryptoIntentCommitment {
    pub request_id: String,
    pub scope: Vec<String>, // e.g., ["read:user", "write:email"]
    pub delegation_chain: Vec<DelegationLink>,
    pub time_lock: DateTime<Utc>, // Expiry timestamp
    pub ed25519_signature: Vec<u8>, // Ed25519 signature over intent tree
    pub intent_tree_hash: String, // Merkle hash of (requestor, scope, delegated_tools, expiry)
}

/// Single delegation link in authorization chain
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DelegationLink {
    pub delegator: String,   // Who gave permission
    pub delegatee: String,   // Who received permission
    pub tools: Vec<String>,  // Tools allowed in delegation
    pub created_at: DateTime<Utc>,
}

/// Result of intent commitment verification
#[derive(Debug, Clone, PartialEq)]
pub enum VerificationResult {
    Valid,
    ExpiredIntent,
    InvalidSignature,
    TamperedIntentTree,
    UnauthorizedDelegation,
    ScopeViolation,
    InvalidDelegationChain,
}

impl std::fmt::Display for VerificationResult {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            VerificationResult::Valid => write!(f, "valid"),
            VerificationResult::ExpiredIntent => write!(f, "expired_intent"),
            VerificationResult::InvalidSignature => write!(f, "invalid_signature"),
            VerificationResult::TamperedIntentTree => write!(f, "tampered_intent_tree"),
            VerificationResult::UnauthorizedDelegation => write!(f, "unauthorized_delegation"),
            VerificationResult::ScopeViolation => write!(f, "scope_violation"),
            VerificationResult::InvalidDelegationChain => write!(f, "invalid_delegation_chain"),
        }
    }
}

/// L3B Intent Verification Gate
pub struct IntentVerificationGate {
    signing_key: SigningKey,
    verifying_key: VerifyingKey,
    authorized_delegators: Vec<(String, String)>, // (delegator, delegatee) pairs
}

impl IntentVerificationGate {
    /// Create new intent verification gate with Ed25519 keypair
    pub fn new() -> Self {
        let mut seed = [0u8; 32];
        use rand::RngCore;
        rand::thread_rng().fill_bytes(&mut seed);
        let signing_key = SigningKey::from_bytes(&seed);
        let verifying_key = signing_key.verifying_key();

        Self {
            signing_key,
            verifying_key,
            authorized_delegators: Vec::new(),
        }
    }

    /// Add authorized delegation policy
    pub fn add_delegation_policy(&mut self, delegator: String, delegatee: String) {
        self.authorized_delegators.push((delegator, delegatee));
    }

    /// Build Merkle hash of intent tree from commitment
    pub fn build_intent_tree(commitment: &CryptoIntentCommitment) -> String {
        let mut hasher = Sha256::new();

        // Hash request_id
        hasher.update(commitment.request_id.as_bytes());

        // Hash scope (sorted for determinism)
        let mut scope_sorted = commitment.scope.clone();
        scope_sorted.sort();
        for scope_item in &scope_sorted {
            hasher.update(scope_item.as_bytes());
        }

        // Hash delegation chain
        for link in &commitment.delegation_chain {
            hasher.update(link.delegator.as_bytes());
            hasher.update(link.delegatee.as_bytes());
            let mut tools_sorted = link.tools.clone();
            tools_sorted.sort();
            for tool in &tools_sorted {
                hasher.update(tool.as_bytes());
            }
        }

        // Hash time lock
        hasher.update(commitment.time_lock.to_rfc3339().as_bytes());

        format!("{:x}", hasher.finalize())
    }

    /// Verify Ed25519 signature over intent tree hash
    pub fn verify_commitment(
        &self,
        commitment: &CryptoIntentCommitment,
    ) -> VerificationResult {
        // 1. Check time lock (not expired)
        if commitment.time_lock <= Utc::now() {
            return VerificationResult::ExpiredIntent;
        }

        // 2. Verify intent tree hash consistency
        let expected_hash = Self::build_intent_tree(commitment);
        if commitment.intent_tree_hash != expected_hash {
            return VerificationResult::TamperedIntentTree;
        }

        // 3. Verify Ed25519 signature
        if commitment.ed25519_signature.len() != 64 {
            return VerificationResult::InvalidSignature;
        }

        let sig = Signature::from_bytes(
            &(commitment.ed25519_signature[..])
                .try_into()
                .unwrap_or([0u8; 64]),
        );

        if self
            .verifying_key
            .verify(expected_hash.as_bytes(), &sig)
            .is_err()
        {
            return VerificationResult::InvalidSignature;
        }

        VerificationResult::Valid
    }

    /// Validate delegation chain (all links must be authorized)
    pub fn check_delegation_chain(&self, commitment: &CryptoIntentCommitment) -> VerificationResult {
        for link in &commitment.delegation_chain {
            let policy_exists = self
                .authorized_delegators
                .iter()
                .any(|(delegator, delegatee)| {
                    delegator == &link.delegator && delegatee == &link.delegatee
                });

            if !policy_exists {
                return VerificationResult::UnauthorizedDelegation;
            }
        }

        VerificationResult::Valid
    }

    /// Check scope boundary (all requested tools must be in delegation chain)
    pub fn check_scope_boundary(&self, commitment: &CryptoIntentCommitment) -> VerificationResult {
        let allowed_tools: Vec<String> = commitment
            .delegation_chain
            .iter()
            .flat_map(|link| link.tools.iter().cloned())
            .collect();

        for scope_item in &commitment.scope {
            if !allowed_tools.contains(scope_item) {
                return VerificationResult::ScopeViolation;
            }
        }

        VerificationResult::Valid
    }

    /// Validate complete commitment (all checks)
    pub fn validate_intent_commitment(
        &self,
        commitment: &CryptoIntentCommitment,
    ) -> VerificationResult {
        // Check 1: Signature and intent tree
        let result = self.verify_commitment(commitment);
        if result != VerificationResult::Valid {
            return result;
        }

        // Check 2: Delegation chain authorization
        let result = self.check_delegation_chain(commitment);
        if result != VerificationResult::Valid {
            return result;
        }

        // Check 3: Scope boundary
        self.check_scope_boundary(commitment)
    }
}

impl Default for IntentVerificationGate {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_valid_commitment(hours_until_expiry: i64) -> CryptoIntentCommitment {
        CryptoIntentCommitment {
            request_id: "req_001".to_string(),
            scope: vec!["read:user".to_string(), "write:email".to_string()],
            delegation_chain: vec![DelegationLink {
                delegator: "user_alice".to_string(),
                delegatee: "agent_bot".to_string(),
                tools: vec!["read:user".to_string(), "write:email".to_string()],
                created_at: Utc::now(),
            }],
            time_lock: Utc::now() + chrono::Duration::hours(hours_until_expiry),
            ed25519_signature: vec![0u8; 64], // Placeholder
            intent_tree_hash: String::new(),
        }
    }

    #[test]
    fn test_build_intent_tree_deterministic() {
        let commitment = create_valid_commitment(24);
        let hash1 = IntentVerificationGate::build_intent_tree(&commitment);
        let hash2 = IntentVerificationGate::build_intent_tree(&commitment);
        assert_eq!(hash1, hash2); // Same input = same hash
    }

    #[test]
    fn test_build_intent_tree_tamper_detection() {
        let commitment1 = create_valid_commitment(24);
        let mut commitment2 = create_valid_commitment(24);

        let hash1 = IntentVerificationGate::build_intent_tree(&commitment1);

        // Tamper with scope
        commitment2.scope.push("write:admin".to_string());
        let hash2 = IntentVerificationGate::build_intent_tree(&commitment2);

        assert_ne!(hash1, hash2); // Different inputs = different hash
    }

    #[test]
    fn test_expired_intent_detection() {
        let gate = IntentVerificationGate::new();
        let commitment = create_valid_commitment(-1); // -1 hours = expired
        let result = gate.verify_commitment(&commitment);
        assert_eq!(result, VerificationResult::ExpiredIntent);
    }

    #[test]
    fn test_scope_boundary_violation() {
        let gate = IntentVerificationGate::new();
        let mut commitment = create_valid_commitment(24);
        // Add tool to scope that's not in delegation chain
        commitment.scope.push("write:admin".to_string());
        let result = gate.check_scope_boundary(&commitment);
        assert_eq!(result, VerificationResult::ScopeViolation);
    }

    #[test]
    fn test_delegation_chain_validation() {
        let mut gate = IntentVerificationGate::new();
        gate.add_delegation_policy("user_alice".to_string(), "agent_bot".to_string());

        let commitment = create_valid_commitment(24);
        let result = gate.check_delegation_chain(&commitment);
        assert_eq!(result, VerificationResult::Valid);
    }

    #[test]
    fn test_unauthorized_delegation() {
        let gate = IntentVerificationGate::new();
        // No policy added, so any delegation should be unauthorized
        let commitment = create_valid_commitment(24);
        let result = gate.check_delegation_chain(&commitment);
        assert_eq!(result, VerificationResult::UnauthorizedDelegation);
    }
}
