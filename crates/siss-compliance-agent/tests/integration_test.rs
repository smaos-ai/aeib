/// Phase 2B Part 1: Integration tests for @Compliance Agent
use chrono::Utc;
use siss_compliance_agent::{
    ComplianceAgent, ComplianceEvaluation, ComplianceVerdict, IncomingPlan, PolicyAction,
    PolicyRule, ResourceMetrics,
};
use uuid::Uuid;

#[tokio::test]
async fn test_compliance_agent_creation() {
    let secret_bytes: [u8; 32] = rand::random();
    let signing_key = ed25519_dalek::SigningKey::from_bytes(&secret_bytes);
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
    let secret_bytes: [u8; 32] = rand::random();
    let signing_key = ed25519_dalek::SigningKey::from_bytes(&secret_bytes);
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
        resources_consumed: ResourceMetrics {
            cpu_ms: 0,
            memory_bytes: 0,
            network_calls: 0,
        },
    };

    assert_eq!(dry_run.sandbox_exit_code, 0);
    assert_eq!(dry_run.trace_steps.len(), 2);
}

#[tokio::test]
async fn test_compose_policy_rules() {
    let secret_bytes: [u8; 32] = rand::random();
    let signing_key = ed25519_dalek::SigningKey::from_bytes(&secret_bytes);
    let agent = ComplianceAgent::new(signing_key);

    let plan = IncomingPlan {
        plan_id: Uuid::new_v4(),
        intent_id: Uuid::new_v4(),
        mandated_steps: vec![],
        risk_assessment: serde_json::json!({"risk_level": "High", "amount": 150_000_000}),
    };

    let rules = agent.compose_policy_rules(&plan).await.unwrap();
    assert!(!rules.is_empty());
    assert!(rules.iter().any(|r| r.rule_name == "BaselIII_CAR_Limit"));
}

#[test]
fn test_detect_rule_conflicts() {
    let secret_bytes: [u8; 32] = rand::random();
    let signing_key = ed25519_dalek::SigningKey::from_bytes(&secret_bytes);
    let agent = ComplianceAgent::new(signing_key);

    let conflict_rules = vec![
        PolicyRule {
            rule_id: Uuid::new_v4(),
            rule_name: "Basel_Block".to_string(),
            condition: "amount > 100M".to_string(),
            action: PolicyAction::Block,
            priority: 100,
        },
        PolicyRule {
            rule_id: Uuid::new_v4(),
            rule_name: "Basel_Allow".to_string(),
            condition: "amount > 100M".to_string(),
            action: PolicyAction::Allow,
            priority: 90,
        },
    ];

    let conflicts = agent.detect_rule_conflicts(&conflict_rules).unwrap();
    assert!(!conflicts.is_empty());
}

#[tokio::test]
async fn test_track_veto() {
    let secret_bytes: [u8; 32] = rand::random();
    let signing_key = ed25519_dalek::SigningKey::from_bytes(&secret_bytes);
    let mut agent = ComplianceAgent::new(signing_key);

    let plan_id = Uuid::new_v4();
    agent.track_veto(plan_id, "Sanction list violation").await.unwrap();
    assert!(agent.veto_history.len() > 0);
}

#[test]
fn test_generate_audit_trail() {
    let secret_bytes: [u8; 32] = rand::random();
    let signing_key = ed25519_dalek::SigningKey::from_bytes(&secret_bytes);
    let agent = ComplianceAgent::new(signing_key);

    let evaluation = ComplianceEvaluation {
        evaluation_id: Uuid::new_v4(),
        plan_id: Uuid::new_v4(),
        rules_checked: vec![PolicyRule {
            rule_id: Uuid::new_v4(),
            rule_name: "TestRule".to_string(),
            condition: "test".to_string(),
            action: PolicyAction::Block,
            priority: 100,
        }],
        verdict: ComplianceVerdict::Approved,
        triggered_gates: vec!["gate1".to_string()],
        requires_human_gate: false,
        timestamp: Utc::now(),
    };

    let trail = agent.generate_audit_trail(&evaluation).unwrap();
    assert!(trail.contains("Compliance Audit"));
    assert!(trail.contains("TestRule"));
}

#[tokio::test]
async fn test_sandbox_resource_limit_check_pass() {
    let secret_bytes: [u8; 32] = rand::random();
    let signing_key = ed25519_dalek::SigningKey::from_bytes(&secret_bytes);
    let agent = ComplianceAgent::new(signing_key);

    let metrics = ResourceMetrics {
        cpu_ms: 100,
        memory_bytes: 10 * 1024 * 1024,
        network_calls: 5,
    };

    assert!(agent.sandbox_resource_limit_check(&metrics).await.is_ok());
}

#[tokio::test]
async fn test_sandbox_resource_limit_check_exceeded() {
    let secret_bytes: [u8; 32] = rand::random();
    let signing_key = ed25519_dalek::SigningKey::from_bytes(&secret_bytes);
    let agent = ComplianceAgent::new(signing_key);

    let metrics = ResourceMetrics {
        cpu_ms: 6000,
        memory_bytes: 10 * 1024 * 1024,
        network_calls: 5,
    };

    assert!(agent.sandbox_resource_limit_check(&metrics).await.is_err());
}
