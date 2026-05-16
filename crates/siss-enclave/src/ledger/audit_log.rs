use crate::operator::HitlVerdict;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OperatorAuditLog {
    pub task_id: Uuid,
    pub operator_id: String,
    pub decision: HitlVerdict,
    pub timestamp_unix_ms: u64,
    pub approval_signature: String,
    pub merkle_root: String,
}
