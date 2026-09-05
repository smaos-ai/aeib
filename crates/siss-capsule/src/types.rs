use crate::signing::StateMutationSigner;
use crate::state_log::{SignedStateLog, StateLogError};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use uuid::Uuid;

/// Policy verification result from ReBAC + AP2
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum PolicyVerificationResult {
    Allowed(String),
    Denied(String),
}

impl PolicyVerificationResult {
    pub fn is_allowed(&self) -> bool {
        matches!(self, PolicyVerificationResult::Allowed(_))
    }
}

/// Tool call authorization proof with hash + signature
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolAuthProof {
    pub tool_name: String,
    pub hash: Vec<u8>,
    pub signature: Vec<u8>,
    pub timestamp: DateTime<Utc>,
    pub nonce: String,
}

/// Verification result for tool authorization
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolAuthVerification {
    pub is_valid: bool,
    pub reason: String,
}

/// Execution context with isolation guarantees
#[derive(Debug, Clone)]
pub struct ExecutionContext {
    pub context_id: Uuid,
    pub sovereign_identity: String,
    pub isolation_level: ContextIsolation,
    pub created_at: DateTime<Utc>,
    pub state_mutations: std::sync::Arc<parking_lot::Mutex<Vec<(String, String)>>>,
    pub snapshot_data: std::sync::Arc<parking_lot::Mutex<Option<Vec<u8>>>>,
    pub rolled_back: std::sync::Arc<parking_lot::Mutex<bool>>,
    pub signed_log: Arc<SignedStateLog>,
    pub signer: Arc<StateMutationSigner>,
}

impl ExecutionContext {
    pub fn new(sovereign_id: String, isolation: ContextIsolation) -> Self {
        ExecutionContext {
            context_id: Uuid::new_v4(),
            sovereign_identity: sovereign_id,
            isolation_level: isolation,
            created_at: Utc::now(),
            state_mutations: std::sync::Arc::new(parking_lot::Mutex::new(Vec::new())),
            snapshot_data: std::sync::Arc::new(parking_lot::Mutex::new(None)),
            rolled_back: std::sync::Arc::new(parking_lot::Mutex::new(false)),
            signed_log: Arc::new(SignedStateLog::new()),
            signer: Arc::new(StateMutationSigner::generate()),
        }
    }

    pub async fn snapshot(&self) -> Vec<u8> {
        // Serialize current state
        let mutations = self.state_mutations.lock();
        serde_json::to_vec(&*mutations).unwrap_or_default()
    }

    pub async fn record_mutation(&self, key: &str, value: &str) {
        let mut mutations = self.state_mutations.lock();
        mutations.push((key.to_string(), value.to_string()));
    }

    /// Record a signed state mutation
    pub fn record_state_mutation(&self, key: String, value: String) -> Result<(), StateLogError> {
        // Sign the mutation
        let mutation = self
            .signer
            .sign_mutation(&key, &value, self.context_id)
            .map_err(|_| StateLogError::VerificationFailed)?;

        // Append to signed log
        self.signed_log.append(mutation)?;

        // Also push to state_mutations Vec for backward compatibility
        let mut mutations = self.state_mutations.lock();
        mutations.push((key, value));

        Ok(())
    }

    pub fn was_rolled_back(&self) -> bool {
        *self.rolled_back.lock()
    }

    pub fn mark_rolled_back(&self) {
        *self.rolled_back.lock() = true;
    }
}

/// Context isolation strategies
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ContextIsolation {
    SovereignIsolation,
    ProcessIsolation,
    HardwareEnclaveIsolation,
}

/// Audit trace entry immutable
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditTraceEntry {
    pub trace_id: Uuid,
    pub sovereign_id: String,
    pub action: String,
    pub resource: String,
    pub is_decision_allowed: bool,
    pub reason: String,
    pub timestamp: DateTime<Utc>,
    pub merkle_proof: Option<Vec<u8>>,
}

/// Merkle proof verification result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MerkleProofVerification {
    pub is_valid: bool,
    pub root_hash: Vec<u8>,
    pub proof_path: Vec<Vec<u8>>,
}

/// Covenant enforcement for 1:99 split
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CovenantEnforcement {
    pub sovereign_quota_percent: u32,
    pub delegated_quota_percent: u32,
    pub context_id: Uuid,
}

/// Harness configuration for adapters
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HarnessConfig {
    pub ollama_endpoint: String,
    pub enable_gpu: bool,
    pub timeout_ms: u64,
    pub max_concurrent_requests: usize,
    pub policy_check_enabled: bool,
}

impl Default for HarnessConfig {
    fn default() -> Self {
        HarnessConfig {
            ollama_endpoint: "http://localhost:11434".to_string(),
            enable_gpu: false,
            timeout_ms: 500,
            max_concurrent_requests: 10,
            policy_check_enabled: true,
        }
    }
}
