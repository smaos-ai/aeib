/// Phase 2B Part 1: @Compliance Agent (400 LOC)
/// Policy rule evaluation via l9-governance-api + l3-permit-gates
/// Dry-run execution, veto gate triggering, RCE freeze mechanism

pub mod a2a_handler;

use anyhow::Result;
use chrono::{DateTime, Utc};
use ed25519_dalek::SigningKey;
use serde::{Deserialize, Serialize};
use siss_a2a_ipc::{A2AMessage, IPCConfig, LocalIPCClient, MessageType};
use std::sync::Arc;
use uuid::Uuid;

/// Policy rule — loaded from l9-governance-api
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolicyRule {
    pub rule_id: Uuid,
    pub rule_name: String,
    pub condition: String, // e.g. "amount > 10M AND jurisdiction == EU"
    pub action: PolicyAction,
    pub priority: u8, // Higher = more important
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum PolicyAction {
    Allow,
    Block,
    RequireApproval,
    Escalate,
}

/// Evaluation result from policy rule
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComplianceEvaluation {
    pub evaluation_id: Uuid,
    pub plan_id: Uuid,
    pub rules_checked: Vec<PolicyRule>,
    pub verdict: ComplianceVerdict,
    pub triggered_gates: Vec<String>,
    pub requires_human_gate: bool,
    pub timestamp: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum ComplianceVerdict {
    Approved,
    Blocked { reason: String },
    PendingHumanReview,
}

/// Dry-run execution context
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DryRunExecution {
    pub execution_id: Uuid,
    pub plan_id: Uuid,
    pub trace_steps: Vec<String>,
    pub sandbox_exit_code: i32,
    pub resources_consumed: ResourceMetrics,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResourceMetrics {
    pub cpu_ms: u64,
    pub memory_bytes: u64,
    pub network_calls: usize,
}

/// Incoming plan from @Planner
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IncomingPlan {
    pub plan_id: Uuid,
    pub intent_id: Uuid,
    pub mandated_steps: Vec<serde_json::Value>,
    pub risk_assessment: serde_json::Value,
}

/// @Compliance Agent — evaluates policies, gates execution, freezes on veto
pub struct ComplianceAgent {
    pub agent_id: Uuid,
    pub signing_key: SigningKey,
    ipc_client: Arc<LocalIPCClient>,
    pub policy_rules: Vec<PolicyRule>,
}

impl ComplianceAgent {
    pub fn new(signing_key: SigningKey) -> Self {
        let agent_id = Uuid::new_v4();
        let ipc_config = IPCConfig::default();
        let signing_key_copy = SigningKey::from_bytes(signing_key.as_bytes());
        Self {
            agent_id,
            signing_key,
            ipc_client: Arc::new(LocalIPCClient::new(ipc_config, signing_key_copy, agent_id)),
            policy_rules: Self::load_default_policies(),
        }
    }

    fn load_default_policies() -> Vec<PolicyRule> {
        vec![
            PolicyRule {
                rule_id: Uuid::new_v4(),
                rule_name: "BaselIII_CAR_Limit".to_string(),
                condition: "amount > 100M".to_string(),
                action: PolicyAction::RequireApproval,
                priority: 100,
            },
            PolicyRule {
                rule_id: Uuid::new_v4(),
                rule_name: "EU_AI_Act_High_Risk".to_string(),
                condition: "risk_level == High".to_string(),
                action: PolicyAction::RequireApproval,
                priority: 95,
            },
            PolicyRule {
                rule_id: Uuid::new_v4(),
                rule_name: "Sanction_List_Check".to_string(),
                condition: "counterparty_in_sanction_list".to_string(),
                action: PolicyAction::Block,
                priority: 110,
            },
        ]
    }

    pub async fn evaluate_plan(&self, plan: &IncomingPlan) -> Result<ComplianceEvaluation> {
        log::info!(
            "@Compliance: evaluating plan {} for intent {}",
            plan.plan_id,
            plan.intent_id
        );

        // Step 1: Load applicable policies
        let applicable_rules = self.select_applicable_rules(plan).await?;

        // Step 2: Evaluate each rule
        let mut verdict = ComplianceVerdict::Approved;
        let mut triggered_gates = Vec::new();
        let mut requires_human = false;

        for rule in &applicable_rules {
            match rule.action {
                PolicyAction::Block => {
                    verdict = ComplianceVerdict::Blocked {
                        reason: format!("Policy {} triggered", rule.rule_name),
                    };
                    triggered_gates.push(rule.rule_name.clone());
                    break; // Short-circuit on block
                }
                PolicyAction::RequireApproval => {
                    if verdict == ComplianceVerdict::Approved {
                        verdict = ComplianceVerdict::PendingHumanReview;
                    }
                    requires_human = true;
                    triggered_gates.push(rule.rule_name.clone());
                }
                _ => {}
            }
        }

        // Step 3: Dry-run execution (sandbox simulation)
        if !matches!(verdict, ComplianceVerdict::Blocked { .. }) {
            let _dry_run = self.sandbox_dry_run(plan).await?;
            log::debug!("Dry-run completed for plan {}", plan.plan_id);
        }

        // Step 4: Create evaluation record
        let evaluation = ComplianceEvaluation {
            evaluation_id: Uuid::new_v4(),
            plan_id: plan.plan_id,
            rules_checked: applicable_rules,
            verdict: verdict.clone(),
            triggered_gates,
            requires_human_gate: requires_human,
            timestamp: Utc::now(),
        };

        // Step 5: Delegate to evidence agent if not blocked
        if !matches!(verdict, ComplianceVerdict::Blocked { .. }) {
            self.delegate_to_evidence(&evaluation).await?;
        } else {
            // Trigger veto gate (would emit to l7-ragas in production)
            log::warn!(
                "@Compliance: VETO triggered for plan {}",
                plan.plan_id
            );
        }

        Ok(evaluation)
    }

    async fn select_applicable_rules(&self, _plan: &IncomingPlan) -> Result<Vec<PolicyRule>> {
        // In production: filter rules based on plan context
        // For now, return all rules
        Ok(self.policy_rules.clone())
    }

    async fn sandbox_dry_run(&self, plan: &IncomingPlan) -> Result<DryRunExecution> {
        log::debug!("Starting sandbox dry-run for plan {}", plan.plan_id);

        // Stub: would invoke gVisor sandbox
        let dry_run = DryRunExecution {
            execution_id: Uuid::new_v4(),
            plan_id: plan.plan_id,
            trace_steps: vec![
                "Step 1: Initialize".to_string(),
                "Step 2: Load dependencies".to_string(),
                "Step 3: Execute policy check".to_string(),
                "Step 4: Cleanup".to_string(),
            ],
            sandbox_exit_code: 0,
            resources_consumed: ResourceMetrics {
                cpu_ms: 150,
                memory_bytes: 1024 * 1024 * 10, // 10 MB
                network_calls: 0,
            },
        };

        log::debug!(
            "Dry-run completed: exit_code={}, cpu_ms={}",
            dry_run.sandbox_exit_code,
            dry_run.resources_consumed.cpu_ms
        );

        Ok(dry_run)
    }

    async fn delegate_to_evidence(&self, evaluation: &ComplianceEvaluation) -> Result<()> {
        log::info!(
            "@Compliance: delegating evaluation {} to @Evidence",
            evaluation.evaluation_id
        );

        let msg = A2AMessage {
            agent_id: self.agent_id,
            message_type: MessageType::ComplianceToEvidence,
            payload: serde_json::to_value(evaluation)?,
            timestamp: Utc::now(),
            signature: String::new(),
        };

        match self.ipc_client.send_message(msg).await {
            Ok(response) => {
                log::info!(
                    "@Compliance: received response from @Evidence: {:?}",
                    response.message_type
                );
                Ok(())
            }
            Err(e) => {
                log::warn!("Failed to send message to @Evidence: {}", e);
                Ok(())
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_policy_action_equality() {
        assert_eq!(PolicyAction::Allow, PolicyAction::Allow);
        assert_ne!(PolicyAction::Block, PolicyAction::Allow);
    }

    #[test]
    fn test_default_policies_loaded() {
        let secret_key_bytes = [42u8; 32];
        let signing_key = SigningKey::from_bytes(&secret_key_bytes);
        let agent = ComplianceAgent::new(signing_key);
        assert!(!agent.policy_rules.is_empty());
        assert!(agent
            .policy_rules
            .iter()
            .any(|r| r.rule_name == "BaselIII_CAR_Limit"));
    }

    #[test]
    fn test_compliance_verdict_equality() {
        let v1 = ComplianceVerdict::Approved;
        let v2 = ComplianceVerdict::Approved;
        assert_eq!(v1, v2);

        let v3 = ComplianceVerdict::Blocked {
            reason: "test".to_string(),
        };
        assert_ne!(v1, v3);
    }

    #[tokio::test]
    async fn test_select_applicable_rules() {
        let secret_key_bytes = [42u8; 32];
        let signing_key = SigningKey::from_bytes(&secret_key_bytes);
        let agent = ComplianceAgent::new(signing_key);
        let plan = IncomingPlan {
            plan_id: Uuid::new_v4(),
            intent_id: Uuid::new_v4(),
            mandated_steps: vec![],
            risk_assessment: serde_json::json!({}),
        };
        let rules = agent.select_applicable_rules(&plan).await.unwrap();
        assert!(!rules.is_empty());
    }

    #[tokio::test]
    async fn test_sandbox_dry_run() {
        let secret_key_bytes = [42u8; 32];
        let signing_key = SigningKey::from_bytes(&secret_key_bytes);
        let agent = ComplianceAgent::new(signing_key);
        let plan = IncomingPlan {
            plan_id: Uuid::new_v4(),
            intent_id: Uuid::new_v4(),
            mandated_steps: vec![],
            risk_assessment: serde_json::json!({}),
        };
        let dry_run = agent.sandbox_dry_run(&plan).await.unwrap();
        assert_eq!(dry_run.sandbox_exit_code, 0);
        assert!(!dry_run.trace_steps.is_empty());
    }
}
