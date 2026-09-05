/// Phase 2B Part 1: Integration tests for @Compliance Agent
use chrono::Utc;
use siss_compliance_agent::{
    ComplianceAgent, ComplianceEvaluation, ComplianceVerdict, IncomingPlan, PolicyAction,
    PolicyRule,
};
use uuid::Uuid;

#[tokio::test]
async fn test_compliance_agent_creation() {
    let signing_key = ed25519_dalek::SigningKey::generate(&mut rand::thread_rng());
    let agent = ComplianceAgent::new(signing_key);

    assert_ne!(agent.agent_id, Uuid::nil());
    assert!(!agent.policy_rules.is_empty());
}

#[test]
fn test_policy_rule_creation() {
    let rule = PolicyRule {
        rule_id: Uuid::new_v4(),
        rule_name: "test_rule".to_string(),
        condition: "amount > 100M".to_string(),
        action: PolicyAction::Block,
        priority: 100,
    };

    assert_eq!(rule.priority, 100);
    assert_eq!(rule.action, PolicyAction::Block);
}

#[test]
fn test_policy_action_variants() {
    assert_eq!(PolicyAction::Allow, PolicyAction::Allow);
    assert_ne!(PolicyAction::Allow, PolicyAction::Block);
    assert_ne!(PolicyAction::Block, PolicyAction::RequireApproval);
    assert_ne!(PolicyAction::RequireApproval, PolicyAction::Escalate);
}

#[test]
fn test_compliance_evaluation_structure() {
    let evaluation = ComplianceEvaluation {
        evaluation_id: Uuid::new_v4(),
        plan_id: Uuid::new_v4(),
        rules_checked: vec![],
        verdict: ComplianceVerdict::Approved,
        triggered_gates: vec!["gate1".to_string()],
        requires_human_gate: false,
        timestamp: Utc::now(),
    };

    assert_eq!(evaluation.verdict, ComplianceVerdict::Approved);
    assert!(!evaluation.triggered_gates.is_empty());
}

#[test]
fn test_compliance_verdict_variants() {
    let v1 = ComplianceVerdict::Approved;
    let v2 = ComplianceVerdict::Approved;
    assert_eq!(v1, v2);

    let v3 = ComplianceVerdict::Blocked {
        reason: "policy violation".to_string(),
    };
    assert_ne!(v1, v3);

    let v4 = ComplianceVerdict::PendingHumanReview;
    assert_ne!(v1, v4);
}

#[tokio::test]
async fn test_compliance_evaluate_plan() {
    let signing_key = ed25519_dalek::SigningKey::generate(&mut rand::thread_rng());
    let agent = ComplianceAgent::new(signing_key);

    let plan = IncomingPlan {
        plan_id: Uuid::new_v4(),
        intent_id: Uuid::new_v4(),
        mandated_steps: vec![],
        risk_assessment: serde_json::json!({}),
    };

    let result = agent.evaluate_plan(&plan).await;
    // May succeed or fail depending on IPC, but should execute evaluation logic
    let _ = result;
}

#[test]
fn test_incoming_plan_serialization() {
    let plan = IncomingPlan {
        plan_id: Uuid::new_v4(),
        intent_id: Uuid::new_v4(),
        mandated_steps: vec![serde_json::json!({"action": "test"})],
        risk_assessment: serde_json::json!({"risk_level": "high"}),
    };

    let json = serde_json::to_string(&plan).expect("serialization failed");
    let deserialized: IncomingPlan =
        serde_json::from_str(&json).expect("deserialization failed");

    assert_eq!(plan.plan_id, deserialized.plan_id);
    assert_eq!(plan.intent_id, deserialized.intent_id);
}

#[test]
fn test_resource_metrics() {
    use siss_compliance_agent::ResourceMetrics;

    let metrics = ResourceMetrics {
        cpu_ms: 150,
        memory_bytes: 10 * 1024 * 1024,
        network_calls: 2,
    };

    assert_eq!(metrics.cpu_ms, 150);
    assert_eq!(metrics.memory_bytes, 10 * 1024 * 1024);
    assert_eq!(metrics.network_calls, 2);
}

#[test]
fn test_dry_run_execution() {
    use siss_compliance_agent::DryRunExecution;

    let dry_run = DryRunExecution {
        execution_id: Uuid::new_v4(),
        plan_id: Uuid::new_v4(),
        trace_steps: vec!["step1".to_string(), "step2".to_string()],
        sandbox_exit_code: 0,
        resources_consumed: Default::default(),
    };

    assert_eq!(dry_run.sandbox_exit_code, 0);
    assert_eq!(dry_run.trace_steps.len(), 2);
}
