use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Insurance claim state machine
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ClaimStatus {
    Submitted,
    UnderReview,
    Approved,
    Denied,
    Paid,
    Disputed,
    Resolved,
}

/// Parametric trigger conditions
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ParametricTrigger {
    EventThreshold { event_type: String, threshold: i32 },
    TimeWindow { start_day: u32, end_day: u32 }, // Days 1-365
    DataFeed { source: String, min_value: f64 },
}

/// Insurance claim (immutable, Merkle-rooted)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Claim {
    pub id: Uuid,
    pub policy_id: Uuid,
    pub claimant_sovereign_id: Uuid,
    pub claim_amount: u64, // in cents
    pub status: ClaimStatus,
    pub submitted_at: DateTime<Utc>,
    pub settlement_amount: Option<u64>,
    pub settled_at: Option<DateTime<Utc>>,
    pub merkle_proof: Option<Vec<String>>, // Merkle path (hex-encoded hashes)
}

/// Insurance policy (defines relationships, triggers, payouts)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Policy {
    pub id: Uuid,
    pub policy_holder_id: Uuid,
    pub policy_type: String, // e.g., "parametric", "indemnity"
    pub coverage_limit: u64, // in cents
    pub deductible: u64,     // in cents
    pub premium_paid: u64,   // in cents
    pub active: bool,
    pub issued_at: DateTime<Utc>,
    pub expires_at: DateTime<Utc>,
}

/// Parametric payout (automated trigger + settlement)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ParametricPayout {
    pub id: Uuid,
    pub claim_id: Uuid,
    pub trigger: ParametricTrigger,
    pub payout_amount: u64, // in cents
    pub executed_at: Option<DateTime<Utc>>,
}

/// Merkle ledger node (claim history chain)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MerkleNode {
    pub hash: String, // Hex-encoded SHA-256
    pub claim_id: Uuid,
    pub claim_hash: String,          // Hash of claim data
    pub parent_hash: Option<String>, // Previous node hash (chain)
    pub position: u64,
    pub created_at: DateTime<Utc>,
}

/// Zero-knowledge fraud proof
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FraudProof {
    pub id: Uuid,
    pub claim_id: Uuid,
    pub proof_data: Vec<u8>, // Serialized proof (implementation-specific)
    pub verified: bool,
    pub created_at: DateTime<Utc>,
}

// Re-export for convenience
pub use serde_json::json;
