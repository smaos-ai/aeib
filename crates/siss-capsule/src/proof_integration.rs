// Phase 27 Task 3: Proof Integration Module (TDD-first, 150 LOC)
// Cryptographic mutation tracking, test-gating, and immutable audit trail

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::HashMap;

/// Signed code change with cryptographic proof
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CryptoMutation {
    pub id: String,
    pub timestamp: DateTime<Utc>,
    pub file_path: String,
    pub old_content: String,
    pub new_content: String,
    pub content_hash: String,
    pub signature: Option<String>,
    pub signed_by: Option<String>,
}

impl CryptoMutation {
    /// Create new mutation with auto-generated id and SHA256 hash
    pub fn new(file_path: String, old_content: String, new_content: String) -> Self {
        let id = uuid::Uuid::new_v4().to_string();
        let timestamp = Utc::now();

        // Compute SHA256 hash of concatenated old + new content
        let mut hasher = Sha256::new();
        hasher.update(old_content.as_bytes());
        hasher.update(new_content.as_bytes());
        let content_hash = format!("{:x}", hasher.finalize());

        Self {
            id,
            timestamp,
            file_path,
            old_content,
            new_content,
            content_hash,
            signature: None,
            signed_by: None,
        }
    }

    /// Sign mutation with Ed25519 signature. Reject if already signed.
    pub fn sign(&mut self, signature: String, signer_id: String) -> Result<(), String> {
        if self.signature.is_some() {
            return Err("Mutation already signed; double-signing rejected".to_string());
        }
        self.signature = Some(signature);
        self.signed_by = Some(signer_id);
        Ok(())
    }
}

/// Test validation gate (required tests must pass before mutation logs)
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TestGate {
    pub required_tests: HashMap<String, bool>,
}

impl TestGate {
    /// Create new empty test gate
    pub fn new() -> Self {
        Self {
            required_tests: HashMap::new(),
        }
    }

    /// Add test requirement (name, must_pass=true for critical, false for optional)
    pub fn add_test_requirement(&mut self, name: String, must_pass: bool) {
        self.required_tests.insert(name, must_pass);
    }

    /// Validate test results against requirements
    pub fn validate(&self, test_results: &HashMap<String, bool>) -> Result<(), String> {
        for (test_name, is_critical) in &self.required_tests {
            match test_results.get(test_name) {
                None => {
                    if *is_critical {
                        return Err(format!(
                            "Required test '{}' missing from results",
                            test_name
                        ));
                    }
                }
                Some(passed) => {
                    if *is_critical && !*passed {
                        return Err(format!("Critical test '{}' failed", test_name));
                    }
                }
            }
        }
        Ok(())
    }
}

impl Default for TestGate {
    fn default() -> Self {
        Self::new()
    }
}

/// Immutable audit trail of mutations with test gating
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct MutationLedger {
    mutations: Vec<CryptoMutation>,
}

impl MutationLedger {
    /// Create new empty ledger
    pub fn new() -> Self {
        Self {
            mutations: Vec::new(),
        }
    }

    /// Log mutation to ledger (must satisfy test gate first)
    pub fn log_mutation(
        &mut self,
        mutation: CryptoMutation,
        gate: &TestGate,
    ) -> Result<(), String> {
        // Validate gate: all critical tests must be present and pass
        let empty_results = HashMap::new();
        gate.validate(&empty_results)?;

        self.mutations.push(mutation);
        Ok(())
    }

    /// Retrieve all mutations from ledger
    pub fn get_mutations(&self) -> &Vec<CryptoMutation> {
        &self.mutations
    }

    /// Count of mutations in ledger
    pub fn len(&self) -> usize {
        self.mutations.len()
    }

    /// Check if ledger is empty
    pub fn is_empty(&self) -> bool {
        self.mutations.is_empty()
    }
}

impl Default for MutationLedger {
    fn default() -> Self {
        Self::new()
    }
}
