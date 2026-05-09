use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use siss_graph_core::node::NodeId;

/// Represents a condition in a TrustPolicyNode capability override rule
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(tag = "type", content = "data")]
pub enum PolicyCondition {
    /// Attestation is present
    HasAttestationType(String),  // "hardware_enclave", "model_integrity", etc.

    /// Attestation is missing
    MissingAttestationType(String),

    /// Attestation score in range
    AttestationScoreRange { min: u32, max: u32 },

    /// Jurisdiction matches
    JurisdictionIs(String),

    /// Tool's risk_class is specific value
    ToolRiskClassIs(String),  // "low", "medium", "high"

    /// Tool requires a specific capability
    ToolRequiresCapability(String),

    /// Composite: all conditions must be true
    And(Vec<PolicyCondition>),

    /// Composite: any condition must be true
    Or(Vec<PolicyCondition>),

    /// Negation
    Not(Box<PolicyCondition>),
}

/// Represents a capability that can be granted or denied
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum CapabilityGrant {
    CanExecuteHighRiskTools,
    CanAccessModelSensitiveTools,
    CanAccessEuOnlyData,
    CanRunLongLivedSessions,
    CanAccessExportControlledData,
    CanSpawnChildProcesses,
}

/// Action to take on a capability
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type")]
pub enum CapabilityAction {
    /// Grant a capability
    Grant { capability: CapabilityGrant },

    /// Deny a capability
    Deny { capability: CapabilityGrant },

    /// Grant with constraints
    Constrain {
        capability: CapabilityGrant,
        rate_limit_rpm: Option<u32>,
        max_duration_seconds: Option<u64>,
        allowed_resources: Option<Vec<String>>,
    },
}

/// A single rule in TrustPolicyNode.capability_overrides
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CapabilityRule {
    pub id: Uuid,
    pub condition: PolicyCondition,
    pub action: CapabilityAction,
    pub priority: u32,  // Higher priority = evaluated first
}

/// TrustPolicyNode: defines trust requirements and capability grants for a Persona
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TrustPolicyNode {
    pub id: NodeId,
    pub persona_id: NodeId,
    pub tenant_id: NodeId,
    pub policy_version: u32,

    // Agent classification rules
    pub allowed_agent_types: Vec<String>,       // ["ai_agent", "service"]
    pub denied_agents_by_id: Vec<String>,       // agent UUIDs to blacklist
    pub allowed_organizations: Vec<String>,     // ["anthropic", "openai"]

    // Attestation requirements
    pub hardware_enclave_required: bool,
    pub model_integrity_required: bool,
    pub max_failed_attestations: u32,

    // Security tier thresholds
    pub tier_1_score_threshold: u32,
    pub tier_2_score_threshold: u32,
    pub tier_3_score_threshold: u32,

    // Capability override rules (decision tree)
    pub capability_overrides: Vec<CapabilityRule>,

    // Token expiry
    pub session_token_expiry_seconds: u64,
    pub capability_token_expiry_seconds: u64,

    // Metadata
    pub enforcement_mode: String,  // "strict" or "permissive"
    pub audit_required: bool,
    pub created_at: DateTime<Utc>,
    pub last_modified: DateTime<Utc>,
    pub last_modified_by: Uuid,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_policy_condition_and_action_types_exist() {
        let condition = PolicyCondition::HasAttestationType("hardware_enclave".to_string());
        assert!(matches!(condition, PolicyCondition::HasAttestationType(_)));

        let action = CapabilityAction::Grant {
            capability: CapabilityGrant::CanExecuteHighRiskTools,
        };
        assert!(matches!(action, CapabilityAction::Grant { .. }));
    }

    #[test]
    fn test_capability_rule_can_be_constructed() {
        let rule = CapabilityRule {
            id: Uuid::new_v4(),
            condition: PolicyCondition::AttestationScoreRange { min: 70, max: 100 },
            action: CapabilityAction::Grant {
                capability: CapabilityGrant::CanExecuteHighRiskTools,
            },
            priority: 1,
        };
        assert_eq!(rule.priority, 1);
    }
}
