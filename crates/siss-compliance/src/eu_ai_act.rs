use chrono::{DateTime, Duration, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Risk level classification for EU AI Act compliance
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum RiskLevel {
    High,
    Medium,
    Low,
}

/// Article 9: Risk Management System - tracks identified risks and mitigation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RiskManagementRecord {
    pub system_id: Uuid,
    pub risk_level: RiskLevel,
    pub identified_risks: Vec<String>,
    pub mitigation_steps: Vec<String>,
    pub last_assessment: DateTime<Utc>,
}

/// Article 12: Automatic Logging & Record Keeping (6-month minimum retention)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditLogEntry {
    pub id: Uuid,
    pub actor: Uuid,    // persona_id or system_id
    pub action: String, // "decision", "training", "deployment"
    pub decision_json: serde_json::Value,
    pub created_at: DateTime<Utc>,
    pub expires_at: DateTime<Utc>, // Must be >= created_at + 180 days
}

impl AuditLogEntry {
    /// Creates a new audit log entry with 180-day retention floor
    pub fn new(actor: Uuid, action: String, decision: serde_json::Value) -> Self {
        let created_at = Utc::now();
        let expires_at = created_at + Duration::days(180);

        Self {
            id: Uuid::new_v4(),
            actor,
            action,
            decision_json: decision,
            created_at,
            expires_at,
        }
    }

    /// Checks if the audit log entry has exceeded its retention period
    pub fn is_expired(&self) -> bool {
        Utc::now() > self.expires_at
    }
}

/// Article 14: Human Oversight Gate - ensures human approval for high-risk decisions
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HumanOversightGate {
    pub system_id: Uuid,
    pub requires_human_approval: bool,
    pub approval_timeout_seconds: u32, // Default 900 (15 min)
    pub approved_at: Option<DateTime<Utc>>,
    pub approved_by: Option<Uuid>, // Human operator
}

impl HumanOversightGate {
    /// Resets approval state when a new decision needs approval
    pub fn request_approval(&mut self) {
        self.approved_at = None;
        self.approved_by = None;
    }

    /// Records human approval for the decision
    pub fn grant_approval(&mut self, operator_id: Uuid) {
        self.approved_at = Some(Utc::now());
        self.approved_by = Some(operator_id);
    }

    /// Checks if approval is still valid (granted and within timeout)
    pub fn is_approved(&self) -> bool {
        if let Some(approved_time) = self.approved_at {
            let elapsed = (Utc::now() - approved_time).num_seconds() as u32;
            elapsed <= self.approval_timeout_seconds
        } else {
            false
        }
    }
}

/// Article 15: Transparency & Information - system capabilities, limitations, and data sources
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransparencyRecord {
    pub system_id: Uuid,
    pub capabilities: Vec<String>,
    pub limitations: Vec<String>,
    pub data_sources: Vec<String>,
    pub human_oversight_mechanism: String,
}
