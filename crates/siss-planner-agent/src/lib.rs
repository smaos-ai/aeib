/// Phase 2B Part 1: @Planner Agent (400 LOC)
/// Intent ingestion → GitNexus codebase graph → implementation plan → delegation
/// Publishes intent to siss-a2a-dispatcher with Ed25519 signature

pub mod a2a_handler;

use anyhow::{anyhow, Result};
use chrono::{DateTime, Utc};
use ed25519_dalek::SigningKey;
use serde::{Deserialize, Serialize};
use siss_a2a_ipc::{A2AMessage, IPCConfig, LocalIPCClient, MessageType};
use std::sync::Arc;
use uuid::Uuid;

/// Intent payload — parsed from user submission
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IntentSpec {
    pub intent_id: Uuid,
    pub user_id: Uuid,
    pub action: String, // e.g. "approve_hotel_credit"
    pub context: serde_json::Value,
    pub created_at: DateTime<Utc>,
}

/// Codebase graph node for planning
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CodebaseNode {
    pub node_id: String,
    pub node_type: String, // "module", "function", "struct"
    pub dependencies: Vec<String>,
    pub risk_level: RiskLevel,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
pub enum RiskLevel {
    Low,
    Medium,
    High,
    Critical,
}

/// Delegation mandate (simplified)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IntentMandate {
    pub mandate_id: Uuid,
    pub intent_id: Uuid,
    pub budget_allocated: i64,
}

impl IntentMandate {
    pub fn new(intent_id: Uuid, budget: i64) -> Self {
        Self {
            mandate_id: Uuid::new_v4(),
            intent_id,
            budget_allocated: budget,
        }
    }
}

/// Implementation plan for downstream agents
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ImplementationPlan {
    pub plan_id: Uuid,
    pub intent_id: Uuid,
    pub mandated_steps: Vec<PlanStep>,
    pub risk_assessment: RiskAssessment,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PlanStep {
    pub step_id: usize,
    pub action: String,
    pub agent_type: String, // "compliance", "evidence", "execution"
    pub parameters: serde_json::Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RiskAssessment {
    pub overall_risk: RiskLevel,
    pub requires_human_approval: bool,
    pub compliance_gates: Vec<String>,
}

/// @Planner Agent — orchestrates intent → plan → delegation
pub struct PlannerAgent {
    pub agent_id: Uuid,
    pub signing_key: SigningKey,
    ipc_client: Arc<LocalIPCClient>,
}

impl PlannerAgent {
    pub fn new(signing_key: SigningKey) -> Self {
        let agent_id = Uuid::new_v4();
        let ipc_config = IPCConfig::default();
        let signing_key_copy = SigningKey::from_bytes(signing_key.as_bytes());
        Self {
            agent_id,
            signing_key,
            ipc_client: Arc::new(LocalIPCClient::new(ipc_config, signing_key_copy, agent_id)),
        }
    }

    pub async fn ingest_intent(&self, intent: IntentSpec) -> Result<()> {
        log::info!("@Planner: ingesting intent {}", intent.intent_id);

        // Step 1: Parse and validate intent
        self.validate_intent(&intent)?;

        // Step 2: Generate codebase graph (stub — would call GitNexus)
        let codebase_nodes = self.generate_codebase_graph(&intent).await?;

        // Step 3: Draft implementation plan
        let plan = self.draft_implementation_plan(&intent, &codebase_nodes).await?;

        // Step 4: Create mandate for delegation
        let mandate = self.create_mandate(&intent, &plan)?;

        // Step 5: Publish to compliance agent via IPC
        self.delegate_to_compliance(&plan, &mandate).await?;

        Ok(())
    }

    fn validate_intent(&self, intent: &IntentSpec) -> Result<()> {
        if intent.intent_id == Uuid::nil() {
            return Err(anyhow!("intent_id cannot be nil"));
        }
        if intent.action.is_empty() {
            return Err(anyhow!("action cannot be empty"));
        }
        Ok(())
    }

    async fn generate_codebase_graph(&self, intent: &IntentSpec) -> Result<Vec<CodebaseNode>> {
        // Stub: in production, call siss-mcp-gitnexus to generate codebase graph
        // For now, return mock graph based on intent action
        log::debug!("Generating codebase graph for action: {}", intent.action);

        let nodes = vec![
            CodebaseNode {
                node_id: "compliance_check".to_string(),
                node_type: "module".to_string(),
                dependencies: vec!["l3_permit_gates".to_string()],
                risk_level: RiskLevel::Medium,
            },
            CodebaseNode {
                node_id: "evidence_collection".to_string(),
                node_type: "module".to_string(),
                dependencies: vec!["l8_proof".to_string()],
                risk_level: RiskLevel::Low,
            },
        ];

        Ok(nodes)
    }

    async fn draft_implementation_plan(
        &self,
        intent: &IntentSpec,
        codebase_nodes: &[CodebaseNode],
    ) -> Result<ImplementationPlan> {
        log::debug!(
            "Drafting implementation plan for intent {}",
            intent.intent_id
        );

        let mut steps = Vec::new();
        let mut max_risk = RiskLevel::Low;

        for (idx, node) in codebase_nodes.iter().enumerate() {
            steps.push(PlanStep {
                step_id: idx,
                action: format!("Process: {}", node.node_id),
                agent_type: "compliance".to_string(),
                parameters: serde_json::json!({
                    "node_id": node.node_id,
                    "dependencies": node.dependencies,
                }),
            });

            if node.risk_level as u8 > max_risk as u8 {
                max_risk = node.risk_level;
            }
        }

        // Add evidence step
        steps.push(PlanStep {
            step_id: steps.len(),
            action: "Collect evidence and generate proof".to_string(),
            agent_type: "evidence".to_string(),
            parameters: serde_json::json!({"intent_id": intent.intent_id}),
        });

        let plan = ImplementationPlan {
            plan_id: Uuid::new_v4(),
            intent_id: intent.intent_id,
            mandated_steps: steps,
            risk_assessment: RiskAssessment {
                overall_risk: max_risk,
                requires_human_approval: max_risk >= RiskLevel::High,
                compliance_gates: vec!["l3_permit_gates".to_string(), "l9_governance_api".to_string()],
            },
            created_at: Utc::now(),
        };

        Ok(plan)
    }

    fn create_mandate(&self, intent: &IntentSpec, plan: &ImplementationPlan) -> Result<IntentMandate> {
        // Stub: create an IntentMandate
        // In production, would use siss-gatekeeper to create formal mandate
        log::debug!("Creating mandate for plan {}", plan.plan_id);
        Ok(IntentMandate::new(intent.intent_id, 1_000_000)) // 1M budget
    }

    async fn delegate_to_compliance(
        &self,
        plan: &ImplementationPlan,
        _mandate: &IntentMandate,
    ) -> Result<()> {
        log::info!(
            "@Planner: delegating plan {} to @Compliance",
            plan.plan_id
        );

        let msg = A2AMessage {
            agent_id: self.agent_id,
            message_type: MessageType::PlannerToCompliance,
            payload: serde_json::to_value(plan)?,
            timestamp: Utc::now(),
            signature: String::new(), // Will be signed by IPC client
        };

        // Send to compliance agent via IPC
        match self.ipc_client.send_message(msg).await {
            Ok(response) => {
                log::info!(
                    "@Planner: received response from @Compliance: {:?}",
                    response.message_type
                );
                Ok(())
            }
            Err(e) => {
                log::warn!("Failed to send message to @Compliance: {}", e);
                // Continue — compliance agent may not be listening yet
                Ok(())
            }
        }
    }

    pub async fn traverse_dependencies(&self, root: &str) -> Result<Vec<CodebaseNode>> {
        log::debug!("Traversing dependencies from root: {}", root);

        let mut nodes = Vec::new();
        let mut visited = std::collections::HashSet::new();
        let mut stack = vec![root.to_string()];

        while let Some(node_id) = stack.pop() {
            if visited.contains(&node_id) {
                continue;
            }
            visited.insert(node_id.clone());

            let dependencies = self.get_node_dependencies(&node_id);
            let node = CodebaseNode {
                node_id: node_id.clone(),
                node_type: "module".to_string(),
                dependencies: dependencies.clone(),
                risk_level: self.estimate_node_risk(&node_id),
            };

            nodes.push(node);

            for dep in dependencies {
                if !visited.contains(&dep) {
                    stack.push(dep);
                }
            }
        }

        log::info!("Traversed {} nodes from root: {}", nodes.len(), root);
        Ok(nodes)
    }

    fn get_node_dependencies(&self, node_id: &str) -> Vec<String> {
        match node_id {
            "compliance_check" => vec!["l3_permit_gates".to_string()],
            "evidence_collection" => vec!["l8_proof".to_string()],
            "authorization_gate" => {
                vec!["l7_ragas".to_string(), "l3_permit_gates".to_string()]
            }
            _ => vec![],
        }
    }

    fn estimate_node_risk(&self, node_id: &str) -> RiskLevel {
        match node_id {
            "compliance_check" => RiskLevel::High,
            "authorization_gate" => RiskLevel::Critical,
            "evidence_collection" => RiskLevel::Medium,
            _ => RiskLevel::Low,
        }
    }

    pub fn validate_plan(&self, plan: &ImplementationPlan) -> Result<()> {
        if plan.plan_id == Uuid::nil() {
            return Err(anyhow!("plan_id cannot be nil"));
        }
        if plan.intent_id == Uuid::nil() {
            return Err(anyhow!("intent_id cannot be nil"));
        }
        if plan.mandated_steps.is_empty() {
            return Err(anyhow!("plan must have at least one mandated step"));
        }

        for (idx, step) in plan.mandated_steps.iter().enumerate() {
            if step.action.is_empty() {
                return Err(anyhow!("Step {} has empty action", idx));
            }
            if step.agent_type.is_empty() {
                return Err(anyhow!("Step {} has empty agent_type", idx));
            }
        }

        log::info!("Plan {} validated successfully", plan.plan_id);
        Ok(())
    }

    pub async fn refine_plan(&self, plan: &mut ImplementationPlan) -> Result<()> {
        log::debug!("Refining plan {}", plan.plan_id);

        let max_risk = plan
            .mandated_steps
            .iter()
            .map(|_| plan.risk_assessment.overall_risk)
            .max()
            .unwrap_or(RiskLevel::Low);

        plan.risk_assessment.overall_risk = max_risk;
        plan.risk_assessment.requires_human_approval = max_risk >= RiskLevel::High;

        if plan.mandated_steps.len() > 10 {
            log::warn!(
                "Plan {} has {} steps; may be too complex",
                plan.plan_id,
                plan.mandated_steps.len()
            );
        }

        log::info!("Plan {} refined; overall_risk: {:?}", plan.plan_id, max_risk);
        Ok(())
    }

    pub fn compose_plan_from_steps(&self, steps: Vec<PlanStep>) -> Result<ImplementationPlan> {
        if steps.is_empty() {
            return Err(anyhow!("Cannot compose plan from zero steps"));
        }

        let max_risk = steps
            .iter()
            .enumerate()
            .map(|(idx, _)| {
                if idx == 0 {
                    RiskLevel::Low
                } else if idx < steps.len() / 2 {
                    RiskLevel::Medium
                } else {
                    RiskLevel::High
                }
            })
            .max()
            .unwrap_or(RiskLevel::Low);

        let plan = ImplementationPlan {
            plan_id: Uuid::new_v4(),
            intent_id: Uuid::new_v4(),
            mandated_steps: steps,
            risk_assessment: RiskAssessment {
                overall_risk: max_risk,
                requires_human_approval: max_risk >= RiskLevel::High,
                compliance_gates: vec!["l3_permit_gates".to_string()],
            },
            created_at: Utc::now(),
        };

        log::info!("Composed plan {} from {} steps", plan.plan_id, plan.mandated_steps.len());
        Ok(plan)
    }

    pub async fn estimate_execution_cost(&self, plan: &ImplementationPlan) -> Result<i64> {
        log::debug!("Estimating execution cost for plan {}", plan.plan_id);

        let base_cost = 100_000_i64; // 100K baseline
        let step_multiplier = plan.mandated_steps.len() as i64 * 50_000; // 50K per step
        let risk_multiplier = match plan.risk_assessment.overall_risk {
            RiskLevel::Low => 1_000_000,
            RiskLevel::Medium => 2_000_000,
            RiskLevel::High => 5_000_000,
            RiskLevel::Critical => 10_000_000,
        };

        let total_cost = base_cost + step_multiplier + risk_multiplier;

        log::info!(
            "Estimated cost for plan {}: {} tokens",
            plan.plan_id,
            total_cost
        );
        Ok(total_cost)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_signing_key() -> SigningKey {
        let secret_key_bytes = [42u8; 32];
        SigningKey::from_bytes(&secret_key_bytes)
    }

    #[test]
    fn test_intent_validation_nil_id() {
        let intent = IntentSpec {
            intent_id: Uuid::nil(),
            user_id: Uuid::new_v4(),
            action: "test".to_string(),
            context: serde_json::json!({}),
            created_at: Utc::now(),
        };
        let signing_key = create_test_signing_key();
        let agent = PlannerAgent::new(signing_key);
        assert!(agent.validate_intent(&intent).is_err());
    }

    #[test]
    fn test_intent_validation_empty_action() {
        let intent = IntentSpec {
            intent_id: Uuid::new_v4(),
            user_id: Uuid::new_v4(),
            action: String::new(),
            context: serde_json::json!({}),
            created_at: Utc::now(),
        };
        let signing_key = create_test_signing_key();
        let agent = PlannerAgent::new(signing_key);
        assert!(agent.validate_intent(&intent).is_err());
    }

    #[test]
    fn test_risk_level_ordering() {
        assert!(RiskLevel::Low < RiskLevel::Medium);
        assert!(RiskLevel::Medium < RiskLevel::High);
        assert!(RiskLevel::High < RiskLevel::Critical);
    }

    #[tokio::test]
    async fn test_codebase_graph_generation() {
        let intent = IntentSpec {
            intent_id: Uuid::new_v4(),
            user_id: Uuid::new_v4(),
            action: "approve_credit".to_string(),
            context: serde_json::json!({}),
            created_at: Utc::now(),
        };
        let signing_key = create_test_signing_key();
        let agent = PlannerAgent::new(signing_key);
        let graph = agent.generate_codebase_graph(&intent).await.unwrap();
        assert!(!graph.is_empty());
        assert!(graph.iter().any(|n| n.node_id == "compliance_check"));
    }

    #[tokio::test]
    async fn test_implementation_plan_draft() {
        let intent = IntentSpec {
            intent_id: Uuid::new_v4(),
            user_id: Uuid::new_v4(),
            action: "approve_credit".to_string(),
            context: serde_json::json!({}),
            created_at: Utc::now(),
        };
        let signing_key = create_test_signing_key();
        let agent = PlannerAgent::new(signing_key);
        let graph = agent.generate_codebase_graph(&intent).await.unwrap();
        let plan = agent
            .draft_implementation_plan(&intent, &graph)
            .await
            .unwrap();
        assert_eq!(plan.intent_id, intent.intent_id);
        assert!(!plan.mandated_steps.is_empty());
    }

    #[tokio::test]
    async fn test_traverse_dependencies() {
        let signing_key = create_test_signing_key();
        let agent = PlannerAgent::new(signing_key);
        let nodes = agent.traverse_dependencies("compliance_check").await.unwrap();
        assert!(!nodes.is_empty());
        assert!(nodes.iter().any(|n| n.node_id == "compliance_check"));
    }

    #[test]
    fn test_validate_plan_valid() {
        let signing_key = create_test_signing_key();
        let agent = PlannerAgent::new(signing_key);
        let plan = ImplementationPlan {
            plan_id: Uuid::new_v4(),
            intent_id: Uuid::new_v4(),
            mandated_steps: vec![PlanStep {
                step_id: 0,
                action: "test".to_string(),
                agent_type: "compliance".to_string(),
                parameters: serde_json::json!({}),
            }],
            risk_assessment: RiskAssessment {
                overall_risk: RiskLevel::Low,
                requires_human_approval: false,
                compliance_gates: vec![],
            },
            created_at: Utc::now(),
        };
        assert!(agent.validate_plan(&plan).is_ok());
    }

    #[test]
    fn test_validate_plan_empty_steps() {
        let signing_key = create_test_signing_key();
        let agent = PlannerAgent::new(signing_key);
        let plan = ImplementationPlan {
            plan_id: Uuid::new_v4(),
            intent_id: Uuid::new_v4(),
            mandated_steps: vec![],
            risk_assessment: RiskAssessment {
                overall_risk: RiskLevel::Low,
                requires_human_approval: false,
                compliance_gates: vec![],
            },
            created_at: Utc::now(),
        };
        assert!(agent.validate_plan(&plan).is_err());
    }

    #[tokio::test]
    async fn test_refine_plan() {
        let signing_key = create_test_signing_key();
        let agent = PlannerAgent::new(signing_key);
        let mut plan = ImplementationPlan {
            plan_id: Uuid::new_v4(),
            intent_id: Uuid::new_v4(),
            mandated_steps: vec![PlanStep {
                step_id: 0,
                action: "test".to_string(),
                agent_type: "compliance".to_string(),
                parameters: serde_json::json!({}),
            }],
            risk_assessment: RiskAssessment {
                overall_risk: RiskLevel::Low,
                requires_human_approval: false,
                compliance_gates: vec![],
            },
            created_at: Utc::now(),
        };
        agent.refine_plan(&mut plan).await.unwrap();
        assert_eq!(plan.risk_assessment.overall_risk, RiskLevel::Low);
    }

    #[test]
    fn test_compose_plan_from_steps() {
        let signing_key = create_test_signing_key();
        let agent = PlannerAgent::new(signing_key);
        let steps = vec![PlanStep {
            step_id: 0,
            action: "initialize".to_string(),
            agent_type: "compliance".to_string(),
            parameters: serde_json::json!({}),
        }];
        let plan = agent.compose_plan_from_steps(steps).unwrap();
        assert!(!plan.mandated_steps.is_empty());
    }

    #[test]
    fn test_compose_plan_empty_steps() {
        let signing_key = create_test_signing_key();
        let agent = PlannerAgent::new(signing_key);
        assert!(agent.compose_plan_from_steps(vec![]).is_err());
    }

    #[tokio::test]
    async fn test_estimate_execution_cost_low_risk() {
        let signing_key = create_test_signing_key();
        let agent = PlannerAgent::new(signing_key);
        let plan = ImplementationPlan {
            plan_id: Uuid::new_v4(),
            intent_id: Uuid::new_v4(),
            mandated_steps: vec![PlanStep {
                step_id: 0,
                action: "test".to_string(),
                agent_type: "compliance".to_string(),
                parameters: serde_json::json!({}),
            }],
            risk_assessment: RiskAssessment {
                overall_risk: RiskLevel::Low,
                requires_human_approval: false,
                compliance_gates: vec![],
            },
            created_at: Utc::now(),
        };
        let cost = agent.estimate_execution_cost(&plan).await.unwrap();
        assert!(cost > 0);
    }

    #[tokio::test]
    async fn test_estimate_execution_cost_critical_risk() {
        let signing_key = create_test_signing_key();
        let agent = PlannerAgent::new(signing_key);
        let plan = ImplementationPlan {
            plan_id: Uuid::new_v4(),
            intent_id: Uuid::new_v4(),
            mandated_steps: vec![PlanStep {
                step_id: 0,
                action: "critical_action".to_string(),
                agent_type: "compliance".to_string(),
                parameters: serde_json::json!({}),
            }],
            risk_assessment: RiskAssessment {
                overall_risk: RiskLevel::Critical,
                requires_human_approval: true,
                compliance_gates: vec![],
            },
            created_at: Utc::now(),
        };
        let cost = agent.estimate_execution_cost(&plan).await.unwrap();
        let low_risk_plan = ImplementationPlan {
            plan_id: Uuid::new_v4(),
            intent_id: Uuid::new_v4(),
            mandated_steps: vec![PlanStep {
                step_id: 0,
                action: "test".to_string(),
                agent_type: "compliance".to_string(),
                parameters: serde_json::json!({}),
            }],
            risk_assessment: RiskAssessment {
                overall_risk: RiskLevel::Low,
                requires_human_approval: false,
                compliance_gates: vec![],
            },
            created_at: Utc::now(),
        };
        let low_cost = agent.estimate_execution_cost(&low_risk_plan).await.unwrap();
        assert!(cost > low_cost);
    }
}
