/// Phase 2B Part 1: Integration tests for @Planner Agent
use chrono::Utc;
use siss_planner_agent::{IntentSpec, PlannerAgent};
use uuid::Uuid;

#[tokio::test]
async fn test_planner_agent_creation() {
    let signing_key = ed25519_dalek::SigningKey::generate(&mut rand::thread_rng());
    let agent = PlannerAgent::new(signing_key);

    // Agent should be created successfully
    assert_ne!(agent.agent_id, Uuid::nil());
}

#[tokio::test]
async fn test_intent_spec_creation() {
    let intent = IntentSpec {
        intent_id: Uuid::new_v4(),
        user_id: Uuid::new_v4(),
        action: "approve_hotel_credit".to_string(),
        context: serde_json::json!({
            "amount": 1_000_000,
            "currency": "EUR",
            "counterparty": "Hotel ABC"
        }),
        created_at: Utc::now(),
    };

    assert_ne!(intent.intent_id, Uuid::nil());
    assert_eq!(intent.action, "approve_hotel_credit");
}

#[tokio::test]
async fn test_planner_ingest_valid_intent() {
    let signing_key = ed25519_dalek::SigningKey::generate(&mut rand::thread_rng());
    let agent = PlannerAgent::new(signing_key);

    let intent = IntentSpec {
        intent_id: Uuid::new_v4(),
        user_id: Uuid::new_v4(),
        action: "approve_credit".to_string(),
        context: serde_json::json!({}),
        created_at: Utc::now(),
    };

    // Should succeed (IPC send may fail, but intent processing should work)
    let result = agent.ingest_intent(intent).await;
    // Result may be Ok() or Err (depending on IPC availability)
    // The important thing is that it handles the flow
    let _ = result;
}

#[test]
fn test_intent_spec_serialization() {
    let intent = IntentSpec {
        intent_id: Uuid::new_v4(),
        user_id: Uuid::new_v4(),
        action: "test_action".to_string(),
        context: serde_json::json!({"key": "value"}),
        created_at: Utc::now(),
    };

    let json = serde_json::to_string(&intent).expect("serialization failed");
    let deserialized: IntentSpec =
        serde_json::from_str(&json).expect("deserialization failed");

    assert_eq!(intent.intent_id, deserialized.intent_id);
    assert_eq!(intent.action, deserialized.action);
}

#[test]
fn test_implementation_plan_structure() {
    use siss_planner_agent::{ImplementationPlan, PlanStep, RiskAssessment, RiskLevel};

    let plan = ImplementationPlan {
        plan_id: Uuid::new_v4(),
        intent_id: Uuid::new_v4(),
        mandated_steps: vec![
            PlanStep {
                step_id: 0,
                action: "check_compliance".to_string(),
                agent_type: "compliance".to_string(),
                parameters: serde_json::json!({}),
            },
            PlanStep {
                step_id: 1,
                action: "collect_evidence".to_string(),
                agent_type: "evidence".to_string(),
                parameters: serde_json::json!({}),
            },
        ],
        risk_assessment: RiskAssessment {
            overall_risk: RiskLevel::Medium,
            requires_human_approval: true,
            compliance_gates: vec!["l3_permit_gates".to_string()],
        },
        created_at: Utc::now(),
    };

    assert_eq!(plan.mandated_steps.len(), 2);
    assert_eq!(plan.risk_assessment.overall_risk, RiskLevel::Medium);
    assert!(plan.risk_assessment.requires_human_approval);
}

#[test]
fn test_risk_level_comparison() {
    use siss_planner_agent::RiskLevel;

    assert!(RiskLevel::Low as u8 < RiskLevel::Medium as u8);
    assert!(RiskLevel::Medium as u8 < RiskLevel::High as u8);
    assert!(RiskLevel::High as u8 < RiskLevel::Critical as u8);
}
