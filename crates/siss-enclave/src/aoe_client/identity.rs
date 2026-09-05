use uuid::Uuid;

/// Operator identity and cryptographic credentials for AoE client
#[derive(Clone, Debug)]
pub struct OperatorIdentity {
    pub operator_id: String,
}

impl OperatorIdentity {
    pub fn new(operator_id: &str) -> Self {
        Self {
            operator_id: operator_id.to_string(),
        }
    }

    /// Generate SHA-256 signature for a task decision
    /// Signature = hex(sha256(task_id || operator_id))
    pub fn sign_decision_payload(&self, task_id: &Uuid) -> String {
        use sha2::{Digest, Sha256};

        let mut hasher = Sha256::new();
        hasher.update(task_id.as_bytes());
        hasher.update(self.operator_id.as_bytes());
        let sig_bytes = hasher.finalize();

        hex::encode(sig_bytes)
    }
}
