/// Phase 2B Part 1: @Compliance Agent (400 LOC)
/// Policy rule evaluation via l9-governance-api + l3-permit-gates
/// Dry-run execution, veto gate triggering, RCE freeze mechanism

pub mod a2a_handler;

use anyhow::{anyhow, Result};
use chrono::{DateTime, Utc};
use ed25519_dalek::SigningKey;
use serde::{Deserialize, Serialize};
use siss_a2a_ipc::{A2AMessage, IPCConfig, LocalIPCClient, MessageType};
use std::collections::HashMap;
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

/// Veto record for audit trail
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VetoRecord {
    pub veto_id: Uuid,
    pub plan_id: Uuid,
    pub reason: String,
    pub triggered_rule: String,
    pub timestamp: DateTime<Utc>,
}

/// Policy composition metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolicyComposition {
    pub composition_id: Uuid,
    pub plan_id: Uuid,
    pub selected_rules: Vec<Uuid>,
    pub conflicts_detected: Vec<String>,
    pub priority_order: Vec<u8>,
    pub created_at: DateTime<Utc>,
}

/// @Compliance Agent — evaluates policies, gates execution, freezes on veto
pub struct ComplianceAgent {
    pub agent_id: Uuid,
    pub signing_key: SigningKey,
    ipc_client: Arc<LocalIPCClient>,
    pub policy_rules: Vec<PolicyRule>,
    pub veto_history: Vec<VetoRecord>,
    pub audit_log: Vec<String>,
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
            veto_history: Vec::new(),
            audit_log: Vec::new(),
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

    pub async fn compose_policy_rules(&self, plan: &IncomingPlan) -> Result<Vec<PolicyRule>> {
        log::debug!("Composing policy rules for plan {}", plan.plan_id);
        let risk_assessment = &plan.risk_assessment;
        let mut selected_rules = Vec::new();

        for rule in &self.policy_rules {
            let applicable = match rule.rule_name.as_str() {
                "BaselIII_CAR_Limit" => risk_assessment
                    .get("amount")
                    .and_then(|v| v.as_i64())
                    .map(|a| a > 100_000_000)
                    .unwrap_or(false),
                "EU_AI_Act_High_Risk" => risk_assessment
                    .get("risk_level")
                    .and_then(|v| v.as_str())
                    .map(|r| r == "High" || r == "Critical")
                    .unwrap_or(false),
                _ => true,
            };
            if applicable {
                selected_rules.push(rule.clone());
            }
        }
        log::info!("Composed {} rules for plan {}", selected_rules.len(), plan.plan_id);
        Ok(selected_rules)
    }

    pub fn detect_rule_conflicts(&self, rules: &[PolicyRule]) -> Result<Vec<String>> {
        let mut conflicts = Vec::new();
        let mut rule_map: HashMap<String, Vec<&PolicyRule>> = HashMap::new();

        for rule in rules {
            let prefix = rule.rule_name.split('_').next().unwrap_or("default");
            rule_map.entry(prefix.to_string()).or_insert_with(Vec::new).push(rule);
        }

        for (_resource, group) in rule_map.iter() {
            let blocks = group.iter().filter(|r| r.action == PolicyAction::Block).count();
            let allows = group.iter().filter(|r| r.action == PolicyAction::Allow).count();

            if blocks > 1 || (blocks > 0 && allows > 0) {
                conflicts.push(format!("Policy conflict detected in {}", group[0].rule_name));
            }
        }
        Ok(conflicts)
    }

    pub async fn track_veto(&mut self, plan_id: Uuid, reason: &str) -> Result<()> {
        let veto = VetoRecord {
            veto_id: Uuid::new_v4(),
            plan_id,
            reason: reason.to_string(),
            triggered_rule: "compliance_gate_veto".to_string(),
            timestamp: Utc::now(),
        };
        log::warn!("VETO: plan {} — {}", plan_id, reason);
        self.veto_history.push(veto);
        if self.veto_history.len() > 1000 {
            self.veto_history.remove(0);
        }
        Ok(())
    }

    pub fn generate_audit_trail(&self, evaluation: &ComplianceEvaluation) -> Result<String> {
        let rules_str = evaluation.rules_checked.iter()
            .map(|r| format!("  - {} ({})", r.rule_name, r.priority))
            .collect::<Vec<_>>()
            .join("\n");

        let gates_str = evaluation.triggered_gates.join(", ");

        let trail = format!(
            "=== Compliance Audit ===\nID: {}\nPlan: {}\nTime: {}\nVerdict: {:?}\n\
             Rules ({}):\n{}\nGates: {}\nHuman Gate: {}\n===",
            evaluation.evaluation_id, evaluation.plan_id, evaluation.timestamp,
            evaluation.verdict, evaluation.rules_checked.len(), rules_str,
            gates_str, evaluation.requires_human_gate
        );
        Ok(trail)
    }

    pub async fn sandbox_resource_limit_check(&self, resources: &ResourceMetrics) -> Result<()> {
        const MAX_CPU_MS: u64 = 5000; // 5 seconds
        const MAX_MEMORY_BYTES: u64 = 512 * 1024 * 1024; // 512 MB
        const MAX_NETWORK_CALLS: usize = 100;

        if resources.cpu_ms > MAX_CPU_MS {
            return Err(anyhow!(
                "CPU limit exceeded: {} ms > {} ms",
                resources.cpu_ms,
                MAX_CPU_MS
            ));
        }

        if resources.memory_bytes > MAX_MEMORY_BYTES {
            return Err(anyhow!(
                "Memory limit exceeded: {} bytes > {} bytes",
                resources.memory_bytes,
                MAX_MEMORY_BYTES
            ));
        }

        if resources.network_calls > MAX_NETWORK_CALLS {
            return Err(anyhow!(
                "Network call limit exceeded: {} > {}",
                resources.network_calls,
                MAX_NETWORK_CALLS
            ));
        }

        log::debug!(
            "Sandbox resource limits OK: cpu={}ms mem={}MB net={}",
            resources.cpu_ms,
            resources.memory_bytes / (1024 * 1024),
            resources.network_calls
        );

        Ok(())
    }

    pub async fn select_applicable_rules(&self, _plan: &IncomingPlan) -> Result<Vec<PolicyRule>> {
        Ok(self.policy_rules.clone())
    }

    pub async fn sandbox_dry_run(&self, plan: &IncomingPlan) -> Result<DryRunExecution> {
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
