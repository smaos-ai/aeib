use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use siss_graph_core::node::NodeId;

/// Represents a condition in a TrustPolicyNode capability override rule
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(tag = "type", content = "data")]
pub enum PolicyCondition {
    /// Attestation is present
    HasAttestationType(String), // "hardware_enclave", "model_integrity", etc.

    /// Attestation is missing
    MissingAttestationType(String),

    /// Attestation score in range
    AttestationScoreRange { min: u32, max: u32 },

    /// Jurisdiction matches
    JurisdictionIs(String),

    /// Tool's risk_class is specific value
    ToolRiskClassIs(String), // "low", "medium", "high"

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
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
#[serde(tag = "type")]
pub enum CapabilityAction {
    /// Grant a capability
    Grant { capability: CapabilityGrant },

    /// Deny a capability
    Deny { capability: CapabilityGrant },

    /// Grant with constraints
    Constrain {
        capability: CapabilityGrant,
        rate_limit_per_minute: Option<u32>,
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
    pub priority: u32, // Higher priority = evaluated first
}

/// TrustPolicyNode: defines trust requirements and capability grants for a Persona
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TrustPolicyNode {
    /// Unique identifier for this policy node
    pub id: NodeId,
    /// Reference to the Persona this policy is associated with
    pub persona_id: NodeId,
    /// Reference to the Tenant that owns this policy
    pub tenant_id: NodeId,
    /// Policy version for migration and compatibility tracking
    pub policy_version: u32,

    /// Allowed agent types (e.g., "ai_agent", "service") - agents not in this list are denied
    pub allowed_agent_types: Vec<String>,
    /// Agent IDs to explicitly blacklist, regardless of type
    pub denied_agents_by_id: Vec<String>,
    /// Allowed organizations (e.g., "anthropic", "openai") - agents from other orgs are denied
    pub allowed_organizations: Vec<String>,

    /// Whether hardware enclave attestation is required for all capability grants
    pub hardware_enclave_required: bool,
    /// Whether model integrity attestation is required for all capability grants
    pub model_integrity_required: bool,
    /// Maximum number of failed attestations before access is revoked
    pub max_failed_attestations: u32,

    /// Minimum attestation score (out of 100) required for unrestricted access at Tier 1 (highest trust)
    pub tier_1_score_threshold: u32,
    /// Minimum attestation score (out of 100) required for Tier 2 (elevated trust) capabilities
    pub tier_2_score_threshold: u32,
    /// Minimum attestation score (out of 100) required for Tier 3 (baseline trust) capabilities
    pub tier_3_score_threshold: u32,

    /// Decision tree rules for capability overrides - evaluated in priority order
    pub capability_overrides: Vec<CapabilityRule>,

    /// Session token expiry duration in seconds
    pub session_token_expiry_seconds: u64,
    /// Capability token expiry duration in seconds
    pub capability_token_expiry_seconds: u64,

    /// Policy enforcement level: "strict" blocks at first security issue, "permissive" allows more flexibility
    pub enforcement_mode: String,
    /// Whether audit logging is required for all capability exercises under this policy
    pub audit_required: bool,
    /// Timestamp when this policy was created
    pub created_at: DateTime<Utc>,
    /// Timestamp of the last modification to this policy
    pub last_modified: DateTime<Utc>,
    /// User ID or agent ID that last modified this policy
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
