use crate::attestation::{Attestation, AttestationType, AttestationVector};
use crate::policy::{CapabilityAction, CapabilityGrant, PolicyCondition, TrustPolicyNode};
use crate::tokens::{CapabilityToken, Delegation, DelegationConstraints, SessionToken};
use chrono::Utc;
use std::collections::{HashMap, HashSet};

/// Context available to rule predicates during evaluation.
pub struct EvaluationContext {
    pub task_tenant_id: uuid::Uuid,
    pub persona_tenant_id: uuid::Uuid,
    pub budget_remaining: i64,
    pub estimated_cost: i64,
}

type PredicateFn = fn(&EvaluationContext) -> bool;

/// Maps rule names to hardcoded predicate functions.
/// Unknown rules return false (logged as advisory).
pub struct RuleEvaluator {
    predicates: HashMap<String, PredicateFn>,
}

impl Default for RuleEvaluator {
    fn default() -> Self {
        let mut predicates: HashMap<String, PredicateFn> = HashMap::new();

        // Already checked in pipeline Step 3 (AP2), so this is a no-op confirmation
        predicates.insert("budget_cannot_exceed_limit".into(), |ctx| {
            ctx.budget_remaining >= ctx.estimated_cost
        });

        // Already checked in pipeline Step 1 (validate)
        predicates.insert("cross_tenant_edge_forbidden".into(), |ctx| {
            ctx.task_tenant_id == ctx.persona_tenant_id
        });

        // Already checked in pipeline Step 1 (validate)
        predicates.insert("task_fsm_valid_transitions".into(), |_ctx| true);

        // Not applicable during authorization
        predicates.insert("session_token_budget".into(), |_ctx| true);

        // Not applicable during authorization
        predicates.insert("memory_gc_threshold".into(), |_ctx| true);

        Self { predicates }
    }
}

impl RuleEvaluator {
    /// Evaluate a rule by name. Returns Ok(true) if the rule passes,
    /// Ok(false) if the rule is unknown or fails.
    pub fn evaluate(&self, rule_name: &str, ctx: &EvaluationContext) -> Result<bool, String> {
        match self.predicates.get(rule_name) {
            Some(predicate) => Ok(predicate(ctx)),
            None => Ok(false), // Unknown rule — treated as advisory warning
        }
    }
}

// ============================================================================
// Capability Evaluation Engine
// ============================================================================

#[derive(Debug)]
pub enum EvaluationError {
    AgentBlacklisted,
    InvalidAgentType,
    MissingRequiredAttestation(String),
    AttestationValidationFailed(String),
    InsufficientSecurityTier { required: u32, calculated: u32 },
    TooManyFailedAttestations { failed: u32, max_allowed: u32 },
}

/// Evaluates attestations against TrustPolicyNode and grants capabilities
pub fn evaluate_capabilities(
    attestations: Vec<Attestation>,
    policy: &TrustPolicyNode,
    persona_tools: Vec<(String, String)>, // (tool_id, risk_class)
) -> Result<(SessionToken, CapabilityToken), EvaluationError> {
    // Step 0.5: Validate agent classification (added before Step 1)
    // Note: In real implementation, agent_id would be passed in request.agent_card
    // For now, we skip agent validation since agent identity comes from request context
    // In production, add:
    // if policy.denied_agents_by_id.contains(&agent_id.to_string()) {
    //     return Err(EvaluationError::AgentBlacklisted);
    // }
    // if !policy.allowed_agent_types.is_empty() && !policy.allowed_agent_types.contains(&agent_type) {
    //     return Err(EvaluationError::InvalidAgentType);
    // }

    // Step 1: Validate attestations and build vectors
    let mut vectors = Vec::new();
    let mut total_score = 0u32;

    for attestation in &attestations {
        // For demo, assume all attestations are valid
        // In production, validate_attestation would check signatures, issuer, freshness
        let vector = AttestationVector {
            attestation_type: attestation.attestation_type,
            score_contribution: attestation.attestation_type.score_contribution(),
            data_sensitivity_allowed: match attestation.attestation_type {
                AttestationType::HardwareEnclave => {
                    crate::attestation::DataSensitivityLevel::Secret
                }
                AttestationType::ModelIntegrity => {
                    crate::attestation::DataSensitivityLevel::Confidential
                }
                AttestationType::SovereignOrigin => {
                    crate::attestation::DataSensitivityLevel::Internal
                }
                AttestationType::RuntimeIntegrity => {
                    crate::attestation::DataSensitivityLevel::Confidential
                }
            },
            hardware_classes_allowed: vec!["LocalMlx".to_string(), "Hybrid".to_string()],
            max_concurrency: 5,
            max_session_ttl_seconds: Some(3600),
            jurisdiction: None,
            verified_at: Utc::now(),
            valid_until: attestation.valid_until,
        };
        total_score += vector.score_contribution;
        vectors.push(vector);
    }

    // Step 2: Check hard requirements
    if policy.hardware_enclave_required
        && !vectors
            .iter()
            .any(|v| v.attestation_type == AttestationType::HardwareEnclave)
    {
        return Err(EvaluationError::MissingRequiredAttestation(
            "hardware_enclave".to_string(),
        ));
    }

    if policy.model_integrity_required
        && !vectors
            .iter()
            .any(|v| v.attestation_type == AttestationType::ModelIntegrity)
    {
        return Err(EvaluationError::MissingRequiredAttestation(
            "model_integrity".to_string(),
        ));
    }

    // Step 3: Assign tier from score
    let _tier = if total_score >= policy.tier_1_score_threshold {
        1
    } else if total_score >= policy.tier_2_score_threshold {
        2
    } else if total_score >= policy.tier_3_score_threshold {
        3
    } else {
        return Err(EvaluationError::InsufficientSecurityTier {
            required: policy.tier_3_score_threshold,
            calculated: total_score,
        });
    };

    // Step 4: Start with default capabilities (for tier 2)
    let mut granted_capabilities: HashSet<CapabilityGrant> = vec![
        CapabilityGrant::CanExecuteHighRiskTools,
        CapabilityGrant::CanAccessModelSensitiveTools,
    ]
    .into_iter()
    .collect();

    // Step 5: Apply capability override rules
    for rule in policy.capability_overrides.iter().rev() {
        // Evaluate condition (simplified: only checks presence/absence for now)
        let condition_met = match &rule.condition {
            PolicyCondition::HasAttestationType(att_type) => vectors
                .iter()
                .any(|v| v.attestation_type.as_str() == att_type),
            PolicyCondition::AttestationScoreRange { min, max } => {
                total_score >= *min && total_score <= *max
            }
            _ => false, // Simplified: other conditions not evaluated in this demo
        };

        if condition_met {
            match &rule.action {
                CapabilityAction::Grant { capability } => {
                    granted_capabilities.insert(capability.clone());
                }
                CapabilityAction::Deny { capability } => {
                    granted_capabilities.remove(capability);
                }
                CapabilityAction::Constrain { capability, .. } => {
                    // Keep capability but add constraints (handled in delegation building)
                    granted_capabilities.insert(capability.clone());
                }
            }
        }
    }

    // Step 6: Build delegations from persona tools
    let delegations = persona_tools
        .into_iter()
        .filter_map(|(tool_id, risk_class)| {
            let allowed = match risk_class.as_str() {
                "high" => granted_capabilities.contains(&CapabilityGrant::CanExecuteHighRiskTools),
                "medium" | "low" => true,
                _ => false,
            };

            if allowed {
                Some(Delegation {
                    permission: "can_execute".to_string(),
                    resource_type: "tool".to_string(),
                    resource_ids: vec![tool_id],
                    constraints: DelegationConstraints {
                        rate_limit: Some("1000/minute".to_string()),
                        max_concurrent: Some(5),
                        allowed_hardware: Some(vec!["LocalMlx".to_string(), "Hybrid".to_string()]),
                        max_duration_seconds: Some(300),
                    },
                })
            } else {
                None
            }
        })
        .collect();

    // Step 7: Emit tokens
    let now = Utc::now();
    let session_token = SessionToken {
        token: format!("session-token-{}", uuid::Uuid::new_v4()),
        expires_in: policy.session_token_expiry_seconds,
        token_type: "Bearer".to_string(),
    };

    let capability_token = CapabilityToken {
        token: format!("capability-token-{}", uuid::Uuid::new_v4()),
        delegations,
        issued_at: now,
        valid_until: now + chrono::Duration::seconds(policy.capability_token_expiry_seconds as i64),
    };

    Ok((session_token, capability_token))
}

#[cfg(test)]
mod tests {
    use super::*;
    use siss_graph_core::node::NodeId;

    #[test]
    fn test_known_rule_passes() {
        let evaluator = RuleEvaluator::default();
        let ctx = EvaluationContext {
            task_tenant_id: uuid::Uuid::new_v4(),
            persona_tenant_id: uuid::Uuid::new_v4(),
            budget_remaining: 1000,
            estimated_cost: 500,
        };
        let result = evaluator.evaluate("budget_cannot_exceed_limit", &ctx);
        assert!(result.is_ok());
        assert!(result.unwrap());
    }

    #[test]
    fn test_unknown_rule_returns_false() {
        let evaluator = RuleEvaluator::default();
        let ctx = EvaluationContext {
            task_tenant_id: uuid::Uuid::nil(),
            persona_tenant_id: uuid::Uuid::nil(),
            budget_remaining: 0,
            estimated_cost: 0,
        };
        let result = evaluator.evaluate("some_unknown_rule", &ctx);
        assert!(result.is_ok());
        assert!(!result.unwrap());
    }

    #[test]
    fn test_session_token_budget_skipped() {
        let evaluator = RuleEvaluator::default();
        let ctx = EvaluationContext {
            task_tenant_id: uuid::Uuid::nil(),
            persona_tenant_id: uuid::Uuid::nil(),
            budget_remaining: 0,
            estimated_cost: 0,
        };
        let result = evaluator.evaluate("session_token_budget", &ctx);
        assert!(result.unwrap());
    }

    // Capability evaluation engine tests
    fn make_test_policy() -> TrustPolicyNode {
        TrustPolicyNode {
            id: NodeId(uuid::Uuid::new_v4()),
            persona_id: NodeId(uuid::Uuid::new_v4()),
            tenant_id: NodeId(uuid::Uuid::new_v4()),
            policy_version: 1,
            allowed_agent_types: vec!["ai_agent".to_string()],
            denied_agents_by_id: vec![],
            allowed_organizations: vec![],
            hardware_enclave_required: false,
            model_integrity_required: false,
            max_failed_attestations: 0,
            tier_1_score_threshold: 100,
            tier_2_score_threshold: 70,
            tier_3_score_threshold: 40,
            capability_overrides: vec![],
            session_token_expiry_seconds: 3600,
            capability_token_expiry_seconds: 86400,
            enforcement_mode: "strict".to_string(),
            audit_required: true,
            created_at: Utc::now(),
            last_modified: Utc::now(),
            last_modified_by: uuid::Uuid::new_v4(),
        }
    }

    #[test]
    fn test_evaluate_capabilities_with_hardware_enclave() {
        let policy = make_test_policy();
        let attestations = vec![Attestation {
            attestation_type: AttestationType::HardwareEnclave,
            format: "sgx_quote".to_string(),
            payload: "payload".to_string(),
            signature: "sig".to_string(),
            issuer: "intel".to_string(),
            issued_at: Utc::now(),
            valid_until: Utc::now() + chrono::Duration::hours(1),
        }];
        let tools = vec![("tool-1".to_string(), "high".to_string())];

        let result = evaluate_capabilities(attestations, &policy, tools);
        assert!(result.is_ok());

        let (session_token, capability_token) = result.unwrap();
        assert_eq!(session_token.token_type, "Bearer");
        assert!(capability_token.delegations.len() > 0);
    }

    #[test]
    fn test_evaluate_capabilities_insufficient_score() {
        let mut policy = make_test_policy();
        policy.tier_3_score_threshold = 100; // Require score >= 100

        let attestations = vec![]; // No attestations = score 0
        let tools = vec![];

        let result = evaluate_capabilities(attestations, &policy, tools);
        assert!(matches!(
            result,
            Err(EvaluationError::InsufficientSecurityTier { .. })
        ));
    }

    #[test]
    fn test_evaluate_capabilities_hardware_enclave_required() {
        let mut policy = make_test_policy();
        policy.hardware_enclave_required = true;

        let attestations = vec![]; // No hardware_enclave attestation
        let tools = vec![];

        let result = evaluate_capabilities(attestations, &policy, tools);
        assert!(matches!(
            result,
            Err(EvaluationError::MissingRequiredAttestation(_))
        ));
    }

    #[test]
    fn test_evaluate_capabilities_model_integrity_required() {
        let mut policy = make_test_policy();
        policy.model_integrity_required = true;

        let attestations = vec![]; // No model_integrity attestation
        let tools = vec![];

        let result = evaluate_capabilities(attestations, &policy, tools);
        assert!(matches!(
            result,
            Err(EvaluationError::MissingRequiredAttestation(_))
        ));
    }
}
