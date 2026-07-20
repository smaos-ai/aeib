use serde::{Deserialize, Serialize};
use uuid::Uuid;
use chrono::{DateTime, Utc};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct OAuth2Token {
    pub access_token: String,
    pub refresh_token: Option<String>,
    pub platform: String,
    pub expires_at: Option<DateTime<Utc>>,
    pub scope: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PlatformAuth {
    pub platform: String,
    pub user_id: String,
    pub access_token: String,
    pub refresh_token: Option<String>,
    pub scope: Vec<String>,
    pub expires_at: Option<DateTime<Utc>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreatorPolicy {
    pub creator_id: Uuid,
    pub rules: Vec<PolicyRule>,
    pub version: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolicyRule {
    pub id: String,
    pub description: String,
    pub condition: PolicyCondition,
    pub effect: PolicyEffect,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum PolicyCondition {
    Always,
    Action { platform: String, action: String },
    Attribute {
        attribute: String,
        operator: String,
        value: serde_json::Value,
    },
    And(Vec<PolicyCondition>),
    Or(Vec<PolicyCondition>),
    Not(Box<PolicyCondition>),
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub enum PolicyEffect {
    Allow,
    Deny,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum DecisionGate {
    Approved {
        capsule_result: CapsuleResult,
        merkle_proof: String,
    },
    NeedsApproval {
        reason: String,
        alternatives: Vec<String>,
        expires_at: DateTime<Utc>,
    },
    Denied {
        reason: String,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CapsuleResult {
    pub decision_id: Uuid,
    pub approved: bool,
    pub latency_ms: f64,
    pub merkle_proof: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DecisionContext {
    pub subscriber_tier: String,
    pub blast_radius: f64,
    pub estimated_value: Option<f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditEntry {
    pub id: Uuid,
    pub creator_id: Uuid,
    pub platform: String,
    pub action: String,
    pub timestamp: DateTime<Utc>,
    pub approved: bool,
    pub blast_radius: f64,
    pub value_detected: Option<f64>,
    pub revenue_split: Option<RevenueSplit>,
    pub merkle_proof: String,
    pub context: serde_json::Value,
}

impl AuditEntry {
    pub fn to_json_ld(&self) -> serde_json::Value {
        serde_json::json!({
            "@context": "https://axiom.local/ctx/vision-api/v1",
            "type": "CreatorDecision",
            "id": self.id.to_string(),
            "creator_id": self.creator_id.to_string(),
            "platform": self.platform,
            "action": self.action,
            "timestamp": self.timestamp.to_rfc3339(),
            "approved": self.approved,
            "blast_radius": self.blast_radius,
            "value_detected": self.value_detected,
            "revenue_split": self.revenue_split,
            "merkle_proof": self.merkle_proof,
            "verifiable": true,
        })
    }
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct RevenueSplit {
    pub value: f64,
    pub creator_payout: f64,
    pub platform_fee: f64,
}

#[derive(Debug, Clone, Copy)]
pub struct SplitRatio {
    pub creator_percentage: f64,
    pub platform_percentage: f64,
}

impl Default for SplitRatio {
    fn default() -> Self {
        Self {
            creator_percentage: 99.0,
            platform_percentage: 1.0,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ActionDefinition {
    pub name: String,
    pub description: String,
    pub required_params: Vec<String>,
    pub optional_params: Vec<String>,
    pub requires_approval: bool,
    pub estimated_blast_radius: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ActionResult {
    pub action: String,
    pub status: ActionStatus,
    pub response: serde_json::Value,
    pub latency_ms: f64,
}

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub enum ActionStatus {
    Success,
    Failed,
    Pending,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Settlement {
    pub decision_id: Uuid,
    pub creator_id: Uuid,
    pub value_detected: f64,
    pub creator_payout: f64,
    pub platform_fee: f64,
    pub timestamp: DateTime<Utc>,
    pub merkle_proof: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EarningsSummary {
    pub creator_id: Uuid,
    pub total_detected: f64,
    pub creator_total: f64,
    pub platform_total: f64,
    pub by_platform: HashMap<String, f64>,
    pub period_start: DateTime<Utc>,
    pub period_end: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionContext {
    pub creator_id: Uuid,
    pub platform: String,
    pub action: String,
    pub isolated: bool,
    pub timestamp: DateTime<Utc>,
}

impl ExecutionContext {
    pub fn new(creator_id: Uuid, platform: &str, action: &str) -> Self {
        Self {
            creator_id,
            platform: platform.to_string(),
            action: action.to_string(),
            isolated: true,
            timestamp: Utc::now(),
        }
    }
}
