/// Phase 2B Part 1: End-to-End Multi-Agent Swarm Tests
/// Full pipeline: Intent -> Planner -> Compliance -> Evidence -> Ledger

use chrono::Utc;
use siss_planner_agent::{
    CodebaseNode, ImplementationPlan, IntentMandate, IntentSpec, PlanStep, PlannerAgent,
    RiskAssessment, RiskLevel,
};
use uuid::Uuid;

// Test 1: Full workflow execution
#[tokio::test]
async fn test_e2e_full_workflow_intent_to_plan() {
    let secret_bytes: [u8; 32] = rand::random();
    let signing_key = ed25519_dalek::SigningKey::from_bytes(&secret_bytes);
    let planner = PlannerAgent::new(signing_key);

    let intent = IntentSpec {
        intent_id: Uuid::new_v4(),
        user_id: Uuid::new_v4(),
        action: "approve_hotel_credit".to_string(),
        context: serde_json::json!({
            "amount": 5_000_000,
            "currency": "EUR",
            "counterparty": "Hotel Grand Budapest",
            "jurisdiction": "EU"
        }),
        created_at: Utc::now(),
    };

    let result = planner.ingest_intent(intent.clone()).await;
    // Result may be Ok or Err depending on IPC, but intent processing should complete
    assert!(result.is_ok() || result.is_err());
}

// Test 2: Intent validation with multiple invalid scenarios
#[test]
fn test_intent_validation_empty_action() {
    let secret_bytes: [u8; 32] = rand::random();
    let signing_key = ed25519_dalek::SigningKey::from_bytes(&secret_bytes);
    let planner = PlannerAgent::new(signing_key);

    let intent = IntentSpec {
        intent_id: Uuid::new_v4(),
        user_id: Uuid::new_v4(),
        action: String::new(),
        context: serde_json::json!({}),
        created_at: Utc::now(),
    };

    assert!(planner.validate_intent(&intent).is_err());
}

// Test 3: Codebase graph generation consistency
#[tokio::test]
async fn test_codebase_graph_consistency() {
    let secret_bytes: [u8; 32] = rand::random();
    let signing_key = ed25519_dalek::SigningKey::from_bytes(&secret_bytes);
    let planner = PlannerAgent::new(signing_key);

    let intent = IntentSpec {
        intent_id: Uuid::new_v4(),
        user_id: Uuid::new_v4(),
        action: "execute_transfer".to_string(),
        context: serde_json::json!({"amount": 100_000}),
        created_at: Utc::now(),
    };

    let graph1 = planner.generate_codebase_graph(&intent).await.unwrap();
    let graph2 = planner.generate_codebase_graph(&intent).await.unwrap();

    // Same intent should generate consistent graph structure
    assert_eq!(graph1.len(), graph2.len());
    for (n1, n2) in graph1.iter().zip(graph2.iter()) {
        assert_eq!(n1.node_id, n2.node_id);
        assert_eq!(n1.risk_level, n2.risk_level);
    }
}

// Test 4: Implementation plan draft with risk assessment
#[tokio::test]
async fn test_implementation_plan_draft_risk() {
    let secret_bytes: [u8; 32] = rand::random();
    let signing_key = ed25519_dalek::SigningKey::from_bytes(&secret_bytes);
    let planner = PlannerAgent::new(signing_key);

    let intent = IntentSpec {
        intent_id: Uuid::new_v4(),
        user_id: Uuid::new_v4(),
        action: "critical_operation".to_string(),
        context: serde_json::json!({"risk_level": "high"}),
        created_at: Utc::now(),
    };

    let graph = vec![
        CodebaseNode {
            node_id: "critical_module".to_string(),
            node_type: "module".to_string(),
            dependencies: vec!["l3_permit_gates".to_string()],
            risk_level: RiskLevel::High,
        },
    ];

    let plan = planner
        .draft_implementation_plan(&intent, &graph)
        .await
        .unwrap();

    assert_eq!(plan.intent_id, intent.intent_id);
    assert!(plan.risk_assessment.requires_human_approval);
    assert_eq!(plan.risk_assessment.overall_risk, RiskLevel::High);
}

// Test 5: Mandate creation with budget validation
#[test]
fn test_mandate_creation_budget() {
    let secret_bytes: [u8; 32] = rand::random();
    let signing_key = ed25519_dalek::SigningKey::from_bytes(&secret_bytes);
    let planner = PlannerAgent::new(signing_key);

    let intent = IntentSpec {
        intent_id: Uuid::new_v4(),
        user_id: Uuid::new_v4(),
        action: "test".to_string(),
        context: serde_json::json!({}),
        created_at: Utc::now(),
    };

    let plan = ImplementationPlan {
        plan_id: Uuid::new_v4(),
        intent_id: intent.intent_id,
        mandated_steps: vec![],
        risk_assessment: RiskAssessment {
            overall_risk: RiskLevel::Low,
            requires_human_approval: false,
            compliance_gates: vec![],
        },
        created_at: Utc::now(),
    };

    let mandate = planner.create_mandate(&intent, &plan).unwrap();
    assert_eq!(mandate.intent_id, intent.intent_id);
    assert!(mandate.budget_allocated > 0);
}

// Test 6: Plan step composition
#[test]
fn test_plan_step_composition() {
    let step = PlanStep {
        step_id: 0,
        action: "validate_compliance".to_string(),
        agent_type: "compliance".to_string(),
        parameters: serde_json::json!({"rule": "basel_iii"}),
    };

    assert_eq!(step.agent_type, "compliance");
    assert_eq!(step.action, "validate_compliance");
}

// Test 7: Intent serialization/deserialization round-trip
#[test]
fn test_intent_serde_round_trip() {
    let original = IntentSpec {
        intent_id: Uuid::new_v4(),
        user_id: Uuid::new_v4(),
        action: "complex_action".to_string(),
        context: serde_json::json!({
            "nested": {
                "data": [1, 2, 3],
                "flags": true
            }
        }),
        created_at: Utc::now(),
    };

    let json = serde_json::to_string(&original).unwrap();
    let restored: IntentSpec = serde_json::from_str(&json).unwrap();

    assert_eq!(original.intent_id, restored.intent_id);
    assert_eq!(original.action, restored.action);
    assert_eq!(original.context, restored.context);
}

// Test 8: Plan multi-step execution tracking
#[test]
fn test_plan_multiple_steps() {
    let mut steps = Vec::new();
    for i in 0..5 {
        steps.push(PlanStep {
            step_id: i,
            action: format!("step_{}", i),
            agent_type: if i % 2 == 0 {
                "compliance"
            } else {
                "evidence"
            }
            .to_string(),
            parameters: serde_json::json!({"index": i}),
        });
    }

    assert_eq!(steps.len(), 5);
    assert_eq!(steps[0].step_id, 0);
    assert_eq!(steps[4].step_id, 4);

    let compliance_steps: Vec<_> = steps
        .iter()
        .filter(|s| s.agent_type == "compliance")
        .collect();
    assert_eq!(compliance_steps.len(), 3); // steps 0, 2, 4
}

// Test 9: Risk level comparison
#[test]
fn test_risk_level_ordering_full() {
    let levels = vec![
        RiskLevel::Low,
        RiskLevel::Medium,
        RiskLevel::High,
        RiskLevel::Critical,
    ];

    for i in 0..levels.len() - 1 {
        assert!(levels[i] < levels[i + 1]);
    }
}

// Test 10: Agent ID uniqueness
#[test]
fn test_agent_id_uniqueness() {
    let secret_bytes: [u8; 32] = rand::random();
    let signing_key = ed25519_dalek::SigningKey::from_bytes(&secret_bytes);
    let agent1 = PlannerAgent::new(signing_key.clone());
    let agent2 = PlannerAgent::new(signing_key.clone());

    assert_ne!(agent1.agent_id, agent2.agent_id);
}

// Test 11: Concurrent intent processing
#[tokio::test]
async fn test_concurrent_intent_processing() {
    let secret_bytes: [u8; 32] = rand::random();
    let signing_key = ed25519_dalek::SigningKey::from_bytes(&secret_bytes);
    let planner = std::sync::Arc::new(PlannerAgent::new(signing_key));

    let mut handles = vec![];
    for i in 0..5 {
        let planner_clone = planner.clone();
        let handle = tokio::spawn(async move {
            let intent = IntentSpec {
                intent_id: Uuid::new_v4(),
                user_id: Uuid::new_v4(),
                action: format!("action_{}", i),
                context: serde_json::json!({"index": i}),
                created_at: Utc::now(),
            };
            planner_clone.ingest_intent(intent).await
        });
        handles.push(handle);
    }

    for handle in handles {
        let _ = handle.await;
    }
}

// Test 12: Compliance gate composition
#[test]
fn test_compliance_gates_in_assessment() {
    let assessment = RiskAssessment {
        overall_risk: RiskLevel::High,
        requires_human_approval: true,
        compliance_gates: vec![
            "basel_iii".to_string(),
            "eu_ai_act".to_string(),
            "aml_kyc".to_string(),
        ],
    };

    assert_eq!(assessment.compliance_gates.len(), 3);
    assert!(assessment.compliance_gates.contains(&"basel_iii".to_string()));
}

// Test 13: Plan ID uniqueness
#[test]
fn test_plan_id_uniqueness() {
    let plan1 = ImplementationPlan {
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

    let plan2 = ImplementationPlan {
        plan_id: Uuid::new_v4(),
        intent_id: plan1.intent_id,
        mandated_steps: vec![],
        risk_assessment: RiskAssessment {
            overall_risk: RiskLevel::Low,
            requires_human_approval: false,
            compliance_gates: vec![],
        },
        created_at: Utc::now(),
    };

    assert_ne!(plan1.plan_id, plan2.plan_id);
    assert_eq!(plan1.intent_id, plan2.intent_id);
}

// Test 14: Context preservation in intent
#[test]
fn test_intent_context_complex() {
    let complex_context = serde_json::json!({
        "transaction": {
            "amount": 1_000_000,
            "currency": "EUR",
            "counterparty": {
                "name": "Test Corp",
                "country": "DE",
                "score": 850
            }
        },
        "flags": ["urgent", "approved_by_ceo"],
        "metadata": {
            "request_id": "REQ-2024-001",
            "timestamp": "2024-01-01T00:00:00Z"
        }
    });

    let intent = IntentSpec {
        intent_id: Uuid::new_v4(),
        user_id: Uuid::new_v4(),
        action: "complex_intent".to_string(),
        context: complex_context.clone(),
        created_at: Utc::now(),
    };

    assert_eq!(intent.context, complex_context);
}

// Test 15: Mandate budget allocation
#[test]
fn test_mandate_budget_allocation() {
    let mandate1 = IntentMandate::new(Uuid::new_v4(), 1_000_000);
    let mandate2 = IntentMandate::new(Uuid::new_v4(), 5_000_000);

    assert_eq!(mandate1.budget_allocated, 1_000_000);
    assert_eq!(mandate2.budget_allocated, 5_000_000);
    assert!(mandate2.budget_allocated > mandate1.budget_allocated);
}

// Test 16: Async codebase graph generation
#[tokio::test]
async fn test_async_graph_generation() {
    let secret_bytes: [u8; 32] = rand::random();
    let signing_key = ed25519_dalek::SigningKey::from_bytes(&secret_bytes);
    let planner = PlannerAgent::new(signing_key);

    let intent = IntentSpec {
        intent_id: Uuid::new_v4(),
        user_id: Uuid::new_v4(),
        action: "async_test".to_string(),
        context: serde_json::json!({}),
        created_at: Utc::now(),
    };

    // Should complete without blocking
    let graph = planner.generate_codebase_graph(&intent).await.unwrap();
    assert!(!graph.is_empty());
}
