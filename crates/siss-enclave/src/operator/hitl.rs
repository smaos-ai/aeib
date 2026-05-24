use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::{oneshot, RwLock};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CryptoApproval {
    pub task_id: Uuid,
    pub operator_id: String,
    pub signature: String,
    pub approved: bool,
    pub rejection_reason: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum HitlVerdict {
    Approved,
    Rejected { reason: String },
    Quarantined,
    RequireApproval,
    Suspended,
}

#[derive(Debug, Clone, thiserror::Error)]
pub enum HitlError {
    #[error("invalid signature for task {task_id}")]
    InvalidSignature { task_id: Uuid },
    #[error("no pending approval for task {task_id}")]
    NoPendingApproval { task_id: Uuid },
}

pub struct HitlGate {
    pending: Arc<RwLock<HashMap<Uuid, oneshot::Sender<HitlVerdict>>>>,
    lower_bound: f32,
    upper_bound: f32,
}

impl HitlGate {
    pub fn new() -> Self {
        Self {
            pending: Arc::new(RwLock::new(HashMap::new())),
            lower_bound: 0.50,
            upper_bound: 0.80,
        }
    }

    pub fn with_bounds(lower: f32, upper: f32) -> Self {
        Self {
            pending: Arc::new(RwLock::new(HashMap::new())),
            lower_bound: lower,
            upper_bound: upper,
        }
    }

    pub fn requires_approval(&self, trust_score: f32) -> bool {
        trust_score >= self.lower_bound && trust_score <= self.upper_bound
    }

    pub async fn wait_for_approval(&self, task_id: Uuid) -> Result<HitlVerdict, HitlError> {
        let (tx, rx) = oneshot::channel::<HitlVerdict>();
        {
            let mut pending = self.pending.write().await;
            pending.insert(task_id, tx);
        }

        rx.await
            .map_err(|_| HitlError::NoPendingApproval { task_id })
    }

    pub async fn issue_approval(&self, approval: CryptoApproval) -> Result<(), HitlError> {
        // Validate signature: hex(sha256(task_id || operator_id))
        use sha2::{Digest, Sha256};
        let mut hasher = Sha256::new();
        hasher.update(approval.task_id.as_bytes());
        hasher.update(approval.operator_id.as_bytes());
        let sig_bytes = hasher.finalize();
        let expected_signature = hex::encode(sig_bytes);

        let mut pending = self.pending.write().await;

        // Eager validation: reject invalid signatures and notify any waiting task
        if approval.signature != expected_signature {
            // If there's a pending task waiting for approval, send it a Quarantined verdict to unblock it
            if let Some(tx) = pending.remove(&approval.task_id) {
                let _ = tx.send(HitlVerdict::Quarantined);
            }
            return Err(HitlError::InvalidSignature {
                task_id: approval.task_id,
            });
        }

        let verdict = if approval.approved {
            HitlVerdict::Approved
        } else {
            HitlVerdict::Rejected {
                reason: approval
                    .rejection_reason
                    .clone()
                    .unwrap_or_else(|| "unknown".to_string()),
            }
        };

        if let Some(tx) = pending.remove(&approval.task_id) {
            let _ = tx.send(verdict);
            Ok(())
        } else {
            Err(HitlError::NoPendingApproval {
                task_id: approval.task_id,
            })
        }
    }
}

impl Default for HitlGate {
    fn default() -> Self {
        Self::new()
    }
}
