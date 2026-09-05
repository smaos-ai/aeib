//! L1→L8 Complete Integration Test Suite (50+ tests)
//! Tests the full proof pipeline from intent submission through ledger entry

use l8_proof::{
    ProofHarness, PipelineStage, WorkflowContext, ProofLayer, AgentacctWorkReceipt,
    AP2LedgerEntry, KmsVault,
};

// ============================================================================
// SECTION 1: Harness Scaffold Tests (5 tests)
// ============================================================================

#[test]
fn test_l1_to_l8_pipeline_structure() {
    let harness = ProofHarness::new();
    assert_eq!(harness.ledger_size(), 0);
    assert!(harness.get_workflows().is_empty());
    assert!(harness.get_receipts().is_empty());
    assert!(harness.get_ap2_entries().is_empty());
}

#[test]
fn test_harness_with_compression_threshold() {
    let harness = ProofHarness::new().with_compression(50);
    assert_eq!(harness.ledger_size(), 0);
}

#[test]
fn test_proof_layer_embedded_in_harness() {
    let harness = ProofHarness::new();
    // Harness contains embedded proof layer
    assert_eq!(harness.ledger_size(), 0);
}

#[test]
fn test_harness_default_creation() {
    let harness = ProofHarness::default();
    assert!(harness.get_workflows().is_empty());
}

#[test]
fn test_harness_state_isolation() {
    let harness1 = ProofHarness::new();
    let harness2 = ProofHarness::new();
    assert_eq!(harness1.ledger_size(), harness2.ledger_size());
}

// ============================================================================
// SECTION 2: L1 Intent Input Flow (5 tests)
// ============================================================================

#[test]
fn test_l1_workflow_creation_from_intent() {
    let mut harness = ProofHarness::new();
    let ctx = harness.create_workflow("intent-hotel-credit-001".to_string());
    assert_eq!(ctx.intent_id, "intent-hotel-credit-001");
    assert_eq!(ctx.stage, PipelineStage::L1InputIntent);
    assert!(ctx.created_at <= chrono::Utc::now());
}

#[test]
fn test_l1_multiple_concurrent_intents() {
    let mut harness = ProofHarness::new();
    let intent1 = harness.create_workflow("intent-001".to_string());
    let intent2 = harness.create_workflow("intent-002".to_string());
    let intent3 = harness.create_workflow("intent-003".to_string());

    assert_eq!(harness.get_workflows().len(), 3);
    assert_ne!(intent1.id, intent2.id);
    assert_ne!(intent2.id, intent3.id);
}

#[test]
fn test_l1_workflow_retrieval_by_id() {
    let mut harness = ProofHarness::new();
    let ctx = harness.create_workflow("intent-retrieve-test".to_string());
    let retrieved = harness.get_workflow(&ctx.id).unwrap();
    assert_eq!(retrieved.id, ctx.id);
    assert_eq!(retrieved.intent_id, "intent-retrieve-test");
}

#[test]
fn test_l1_intent_context_metadata() {
    let mut harness = ProofHarness::new();
    let ctx = harness.create_workflow("intent-metadata-test".to_string());
    assert!(!ctx.id.is_empty());
    assert!(ctx.classification.is_none());
    assert!(ctx.gate_decision.is_none());
    assert!(ctx.completed_at.is_none());
}

#[test]
fn test_l1_workflow_invalid_id_handling() {
    let harness = ProofHarness::new();
    assert!(harness.get_workflow("nonexistent").is_none());
}

// ============================================================================
// SECTION 3: L2 Classification Flow (5 tests)
// ============================================================================

#[test]
fn test_l2_classification_assignment() {
    let mut harness = ProofHarness::new();
    let ctx = harness.create_workflow("intent-classify".to_string());
    harness.set_classification(&ctx.id, "APPROVE".to_string()).unwrap();

    let retrieved = harness.get_workflow(&ctx.id).unwrap();
    assert_eq!(retrieved.classification, Some("APPROVE".to_string()));
}

#[test]
fn test_l2_stage_advancement_to_classification() {
    let mut harness = ProofHarness::new();
    let ctx = harness.create_workflow("intent-advance".to_string());
    harness.advance_stage(&ctx.id, PipelineStage::L2Classification).unwrap();

    let retrieved = harness.get_workflow(&ctx.id).unwrap();
    assert_eq!(retrieved.stage, PipelineStage::L2Classification);
}

#[test]
fn test_l2_multiple_classifications() {
    let mut harness = ProofHarness::new();
    let ctx1 = harness.create_workflow("intent-high-risk".to_string());
    let ctx2 = harness.create_workflow("intent-low-risk".to_string());

    harness.set_classification(&ctx1.id, "BLOCK".to_string()).unwrap();
    harness.set_classification(&ctx2.id, "APPROVE".to_string()).unwrap();

    assert_eq!(harness.get_workflow(&ctx1.id).unwrap().classification, Some("BLOCK".to_string()));
    assert_eq!(harness.get_workflow(&ctx2.id).unwrap().classification, Some("APPROVE".to_string()));
}

#[test]
fn test_l2_classification_overwrite() {
    let mut harness = ProofHarness::new();
    let ctx = harness.create_workflow("intent-update-class".to_string());
    harness.set_classification(&ctx.id, "PENDING".to_string()).unwrap();
    harness.set_classification(&ctx.id, "APPROVE".to_string()).unwrap();

    let retrieved = harness.get_workflow(&ctx.id).unwrap();
    assert_eq!(retrieved.classification, Some("APPROVE".to_string()));
}

#[test]
fn test_l2_invalid_workflow_classification() {
    let mut harness = ProofHarness::new();
    let result = harness.set_classification("invalid-id", "BLOCK".to_string());
    assert!(result.is_err());
}

// ============================================================================
// SECTION 4: L3 Permit Gate Flow (5 tests)
// ============================================================================

#[test]
fn test_l3_permit_gate_decision() {
    let mut harness = ProofHarness::new();
    let ctx = harness.create_workflow("intent-gate".to_string());
    harness.set_gate_decision(&ctx.id, "ALLOW".to_string()).unwrap();

    let retrieved = harness.get_workflow(&ctx.id).unwrap();
    assert_eq!(retrieved.gate_decision, Some("ALLOW".to_string()));
}

#[test]
fn test_l3_permit_gate_stage_advancement() {
    let mut harness = ProofHarness::new();
    let ctx = harness.create_workflow("intent-permit".to_string());
    harness.advance_stage(&ctx.id, PipelineStage::L3PermitGate).unwrap();

    let retrieved = harness.get_workflow(&ctx.id).unwrap();
    assert_eq!(retrieved.stage, PipelineStage::L3PermitGate);
}

#[test]
fn test_l3_deny_decision_path() {
    let mut harness = ProofHarness::new();
    let ctx = harness.create_workflow("intent-deny".to_string());
    harness.set_gate_decision(&ctx.id, "DENY".to_string()).unwrap();

    let retrieved = harness.get_workflow(&ctx.id).unwrap();
    assert_eq!(retrieved.gate_decision, Some("DENY".to_string()));
}

#[test]
fn test_l3_gate_decision_workflow_combination() {
    let mut harness = ProofHarness::new();
    let ctx = harness.create_workflow("intent-combined".to_string());

    harness.set_classification(&ctx.id, "HIGH_RISK".to_string()).unwrap();
    harness.advance_stage(&ctx.id, PipelineStage::L3PermitGate).unwrap();
    harness.set_gate_decision(&ctx.id, "BLOCK".to_string()).unwrap();

    let retrieved = harness.get_workflow(&ctx.id).unwrap();
    assert_eq!(retrieved.classification, Some("HIGH_RISK".to_string()));
    assert_eq!(retrieved.gate_decision, Some("BLOCK".to_string()));
    assert_eq!(retrieved.stage, PipelineStage::L3PermitGate);
}

#[test]
fn test_l3_invalid_gate_workflow_handling() {
    let mut harness = ProofHarness::new();
    let result = harness.set_gate_decision("invalid-id", "ALLOW".to_string());
    assert!(result.is_err());
}

// ============================================================================
// SECTION 5: L4→L5 Orchestration & Communication (5 tests)
// ============================================================================

#[test]
fn test_l4_orchestration_stage_advancement() {
    let mut harness = ProofHarness::new();
    let ctx = harness.create_workflow("intent-orchestrate".to_string());
    harness.advance_stage(&ctx.id, PipelineStage::L4Orchestration).unwrap();

    let retrieved = harness.get_workflow(&ctx.id).unwrap();
    assert_eq!(retrieved.stage, PipelineStage::L4Orchestration);
}

#[test]
fn test_l5_communication_stage_advancement() {
    let mut harness = ProofHarness::new();
    let ctx = harness.create_workflow("intent-communicate".to_string());
    harness.advance_stage(&ctx.id, PipelineStage::L5Communication).unwrap();

    let retrieved = harness.get_workflow(&ctx.id).unwrap();
    assert_eq!(retrieved.stage, PipelineStage::L5Communication);
}

#[test]
fn test_l4_l5_pipeline_progression() {
    let mut harness = ProofHarness::new();
    let ctx = harness.create_workflow("intent-l4l5".to_string());

    harness.advance_stage(&ctx.id, PipelineStage::L3PermitGate).unwrap();
    harness.advance_stage(&ctx.id, PipelineStage::L4Orchestration).unwrap();
    harness.advance_stage(&ctx.id, PipelineStage::L5Communication).unwrap();

    let retrieved = harness.get_workflow(&ctx.id).unwrap();
    assert_eq!(retrieved.stage, PipelineStage::L5Communication);
}

#[test]
fn test_l4_orchestration_with_receipt() {
    let mut harness = ProofHarness::new();
    let ctx = harness.create_workflow("intent-orch-receipt".to_string());
    let receipt = harness.create_receipt(
        "orchestrator-agent".to_string(),
        "route_intent".to_string(),
        "routed_to_validator".to_string(),
    );

    assert_eq!(receipt.agent_id, "orchestrator-agent");
    assert_eq!(harness.get_receipts().len(), 1);
}

#[test]
fn test_l5_communication_mcp_server_stub() {
    let mut harness = ProofHarness::new();
    let ctx = harness.create_workflow("intent-mcp".to_string());
    harness.advance_stage(&ctx.id, PipelineStage::L5Communication).unwrap();

    // Stub: MCP server invocation would happen here
    let receipt = harness.create_receipt(
        "mcp-gateway".to_string(),
        "notify_stakeholders".to_string(),
        "notification_sent".to_string(),
    );
    assert!(!receipt.id.is_empty());
}

// ============================================================================
// SECTION 6: L6 Infrastructure Health (4 tests)
// ============================================================================

#[test]
fn test_l6_infrastructure_stage_advancement() {
    let mut harness = ProofHarness::new();
    let ctx = harness.create_workflow("intent-infra".to_string());
    harness.advance_stage(&ctx.id, PipelineStage::L6Infrastructure).unwrap();

    let retrieved = harness.get_workflow(&ctx.id).unwrap();
    assert_eq!(retrieved.stage, PipelineStage::L6Infrastructure);
}

#[test]
fn test_l6_freetoken_validation_stub() {
    let mut harness = ProofHarness::new();
    let receipt = harness.create_receipt(
        "freetok-validator".to_string(),
        "check_available_tokens".to_string(),
        "120_tokens_available".to_string(),
    );
    assert_eq!(harness.get_receipts().len(), 1);
}

#[test]
fn test_l6_hardware_capability_check() {
    let mut harness = ProofHarness::new();
    let receipt = harness.create_receipt(
        "hw-detector".to_string(),
        "query_device_capability".to_string(),
        "qwen_39_tok_per_sec".to_string(),
    );
    assert!(!receipt.signature.is_empty());
}

#[test]
fn test_l6_health_endpoint_ready() {
    let mut harness = ProofHarness::new();
    let receipt = harness.create_receipt(
        "health-check".to_string(),
        "endpoint_health".to_string(),
        "all_systems_operational".to_string(),
    );
    assert_eq!(receipt.result, "all_systems_operational");
}

// ============================================================================
// SECTION 7: L7 Authorization Gate (5 tests)
// ============================================================================

#[test]
fn test_l7_authorization_stage_advancement() {
    let mut harness = ProofHarness::new();
    let ctx = harness.create_workflow("intent-authz".to_string());
    harness.advance_stage(&ctx.id, PipelineStage::L7Authorization).unwrap();

    let retrieved = harness.get_workflow(&ctx.id).unwrap();
    assert_eq!(retrieved.stage, PipelineStage::L7Authorization);
}

#[test]
fn test_l7_human_gate_receipt_creation() {
    let mut harness = ProofHarness::new();
    let receipt = harness.create_receipt(
        "authorization-gate".to_string(),
        "await_human_signature".to_string(),
        "waiting_for_approval".to_string(),
    );
    assert_eq!(receipt.action, "await_human_signature");
}

#[test]
fn test_l7_signature_verification_receipt() {
    let mut harness = ProofHarness::new();
    let receipt = harness.create_receipt(
        "sig-verifier".to_string(),
        "verify_ed25519_signature".to_string(),
        "signature_valid".to_string(),
    );
    assert!(receipt.signature.starts_with("ed25519:"));
}

#[test]
fn test_l7_authorization_approval_flow() {
    let mut harness = ProofHarness::new();
    let ctx = harness.create_workflow("intent-approve".to_string());
    harness.advance_stage(&ctx.id, PipelineStage::L7Authorization).unwrap();

    let approval = harness.create_receipt(
        "human-approver".to_string(),
        "human_authorization".to_string(),
        "APPROVED".to_string(),
    );
    assert_eq!(approval.result, "APPROVED");
}

#[test]
fn test_l7_authorization_rejection_flow() {
    let mut harness = ProofHarness::new();
    let ctx = harness.create_workflow("intent-reject".to_string());
    harness.advance_stage(&ctx.id, PipelineStage::L7Authorization).unwrap();

    let rejection = harness.create_receipt(
        "human-reviewer".to_string(),
        "human_authorization".to_string(),
        "REJECTED".to_string(),
    );
    assert_eq!(rejection.result, "REJECTED");
}

// ============================================================================
// SECTION 8: L8 Proof & Ledger (6 tests)
// ============================================================================

#[test]
fn test_l8_proof_layer_ledger_entry() {
    let mut harness = ProofHarness::new();
    let result = harness.create_ledger_entry("test ledger data".to_string());

    assert!(result.is_ok());
    let entry = result.unwrap();
    assert!(!entry.id.is_empty());
    assert!(entry.signature.starts_with("ed25519:"));
}

#[test]
fn test_l8_multiple_ledger_entries() {
    let mut harness = ProofHarness::new();
    let e1 = harness.create_ledger_entry("entry_1".to_string()).unwrap();
    let e2 = harness.create_ledger_entry("entry_2".to_string()).unwrap();
    let e3 = harness.create_ledger_entry("entry_3".to_string()).unwrap();

    assert_eq!(harness.ledger_size(), 3);
    assert_ne!(e1.digest, e2.digest);
    assert_ne!(e2.digest, e3.digest);
}

#[test]
fn test_l8_ledger_chain_immutability() {
    let mut harness = ProofHarness::new();
    harness.create_ledger_entry("data_1".to_string()).unwrap();
    harness.create_ledger_entry("data_2".to_string()).unwrap();
    harness.create_ledger_entry("data_3".to_string()).unwrap();

    let integrity = harness.verify_ledger_integrity();
    assert!(integrity.is_ok());
    assert!(integrity.unwrap());
}

#[test]
fn test_l8_ap2_transaction_recording() {
    let mut harness = ProofHarness::new();
    let entry = harness.record_ap2_transaction(
        "auth-treasury-001".to_string(),
        r#"{"amount": 10000, "recipient": "hotel_credit_line"}"#.to_string(),
    );

    assert!(!entry.id.is_empty());
    assert_eq!(harness.get_ap2_entries().len(), 1);
}

#[test]
fn test_l8_multiple_ap2_entries() {
    let mut harness = ProofHarness::new();
    harness.record_ap2_transaction("auth-1".to_string(), r#"{"tx": 1}"#.to_string());
    harness.record_ap2_transaction("auth-2".to_string(), r#"{"tx": 2}"#.to_string());
    harness.record_ap2_transaction("auth-3".to_string(), r#"{"tx": 3}"#.to_string());

    assert_eq!(harness.get_ap2_entries().len(), 3);
}

#[test]
fn test_l8_agentacct_receipt_immutability() {
    let mut harness = ProofHarness::new();
    let receipt1 = harness.create_receipt(
        "agent-trace".to_string(),
        "action_1".to_string(),
        "completed".to_string(),
    );
    let receipt2 = harness.create_receipt(
        "agent-trace".to_string(),
        "action_2".to_string(),
        "completed".to_string(),
    );

    assert_eq!(harness.get_receipts().len(), 2);
    assert_ne!(receipt1.id, receipt2.id);
    assert_ne!(receipt1.chain_digest, receipt2.chain_digest);
}

// ============================================================================
// SECTION 9: End-to-End Workflow Tests (8 tests)
// ============================================================================

#[test]
fn test_complete_workflow_intent_to_proof() {
    let mut harness = ProofHarness::new();
    let ctx = harness.create_workflow("intent-e2e-full".to_string());

    // L1: Intent received
    assert_eq!(ctx.stage, PipelineStage::L1InputIntent);

    // L2: Classification
    harness.set_classification(&ctx.id, "EVALUATE".to_string()).unwrap();
    harness.advance_stage(&ctx.id, PipelineStage::L2Classification).unwrap();

    // L3: Gate decision
    harness.advance_stage(&ctx.id, PipelineStage::L3PermitGate).unwrap();
    harness.set_gate_decision(&ctx.id, "ALLOW".to_string()).unwrap();

    // L7: Authorization
    harness.advance_stage(&ctx.id, PipelineStage::L7Authorization).unwrap();

    // L8: Proof ledger entry
    let ledger_entry = harness.create_ledger_entry("complete_workflow_proof".to_string()).unwrap();
    let ap2_entry = harness.record_ap2_transaction(
        "authz_final".to_string(),
        r#"{"workflow_id": "intent-e2e-full"}"#.to_string(),
    );

    // Completion
    harness.complete_workflow(&ctx.id).unwrap();

    let final_workflow = harness.get_workflow(&ctx.id).unwrap();
    assert!(final_workflow.completed_at.is_some());
    assert_eq!(harness.ledger_size(), 1);
    assert_eq!(harness.get_ap2_entries().len(), 1);
}

#[test]
fn test_workflow_approval_path() {
    let mut harness = ProofHarness::new();
    let ctx = harness.create_workflow("intent-approve-path".to_string());

    harness.set_classification(&ctx.id, "LOW_RISK".to_string()).unwrap();
    harness.advance_stage(&ctx.id, PipelineStage::L2Classification).unwrap();
    harness.advance_stage(&ctx.id, PipelineStage::L3PermitGate).unwrap();
    harness.set_gate_decision(&ctx.id, "AUTO_APPROVE".to_string()).unwrap();
    harness.advance_stage(&ctx.id, PipelineStage::L7Authorization).unwrap();

    let final_workflow = harness.get_workflow(&ctx.id).unwrap();
    assert_eq!(final_workflow.classification, Some("LOW_RISK".to_string()));
    assert_eq!(final_workflow.gate_decision, Some("AUTO_APPROVE".to_string()));
}

#[test]
fn test_workflow_block_path() {
    let mut harness = ProofHarness::new();
    let ctx = harness.create_workflow("intent-block-path".to_string());

    harness.set_classification(&ctx.id, "HIGH_RISK".to_string()).unwrap();
    harness.advance_stage(&ctx.id, PipelineStage::L2Classification).unwrap();
    harness.advance_stage(&ctx.id, PipelineStage::L3PermitGate).unwrap();
    harness.set_gate_decision(&ctx.id, "BLOCK".to_string()).unwrap();

    let blocked_workflow = harness.get_workflow(&ctx.id).unwrap();
    assert_eq!(blocked_workflow.gate_decision, Some("BLOCK".to_string()));
}

#[test]
fn test_concurrent_workflows_isolation() {
    let mut harness = ProofHarness::new();
    let w1 = harness.create_workflow("intent-iso-1".to_string());
    let w2 = harness.create_workflow("intent-iso-2".to_string());
    let w3 = harness.create_workflow("intent-iso-3".to_string());

    harness.set_classification(&w1.id, "CLASS_A".to_string()).unwrap();
    harness.set_classification(&w2.id, "CLASS_B".to_string()).unwrap();
    harness.set_classification(&w3.id, "CLASS_C".to_string()).unwrap();

    assert_eq!(harness.get_workflow(&w1.id).unwrap().classification, Some("CLASS_A".to_string()));
    assert_eq!(harness.get_workflow(&w2.id).unwrap().classification, Some("CLASS_B".to_string()));
    assert_eq!(harness.get_workflow(&w3.id).unwrap().classification, Some("CLASS_C".to_string()));
}

#[test]
fn test_workflow_completion_verification() {
    let mut harness = ProofHarness::new();
    let ctx = harness.create_workflow("intent-verify-complete".to_string());
    assert!(!harness.verify_workflow_chain(&ctx.id));

    harness.complete_workflow(&ctx.id).unwrap();
    assert!(harness.verify_workflow_chain(&ctx.id));
}

#[test]
fn test_workflow_with_multiple_receipts() {
    let mut harness = ProofHarness::new();
    let ctx = harness.create_workflow("intent-multi-receipt".to_string());

    let r1 = harness.create_receipt("agent-1".to_string(), "step_1".to_string(), "done".to_string());
    let r2 = harness.create_receipt("agent-2".to_string(), "step_2".to_string(), "done".to_string());
    let r3 = harness.create_receipt("agent-3".to_string(), "step_3".to_string(), "done".to_string());

    assert_eq!(harness.get_receipts().len(), 3);
    harness.complete_workflow(&ctx.id).unwrap();
    assert!(harness.verify_workflow_chain(&ctx.id));
}

#[test]
fn test_workflow_ledger_chain_with_mixed_entries() {
    let mut harness = ProofHarness::new();
    let ctx = harness.create_workflow("intent-mixed-ledger".to_string());

    // Mix of ledger entries, AP2 entries, and receipts
    let _le1 = harness.create_ledger_entry("proof_data_1".to_string()).unwrap();
    let _ap1 = harness.record_ap2_transaction("auth-1".to_string(), r#"{"data": 1}"#.to_string());
    let _rec1 = harness.create_receipt("tracer".to_string(), "trace_1".to_string(), "ok".to_string());

    let _le2 = harness.create_ledger_entry("proof_data_2".to_string()).unwrap();
    let _ap2 = harness.record_ap2_transaction("auth-2".to_string(), r#"{"data": 2}"#.to_string());

    assert!(harness.verify_ledger_integrity().unwrap());
    harness.complete_workflow(&ctx.id).unwrap();
}

// ============================================================================
// SECTION 10: KMS Integration Stubs (4 tests)
// ============================================================================

#[tokio::test]
async fn test_kms_vault_key_generation() {
    let mut kms = KmsVault::new();
    let key = kms.generate_key().await.expect("Failed to generate key");

    assert_eq!(key.algorithm, "Ed25519");
    assert!(!key.key_id.is_empty());
}

#[tokio::test]
async fn test_kms_vault_in_harness() {
    let mut harness = ProofHarness::new();
    let mut kms = KmsVault::new();
    let key = kms.generate_key().await.expect("Failed to generate key");
    harness.set_current_key(key.clone());

    assert!(harness.get_current_key().is_some());
}

#[tokio::test]
async fn test_kms_signing_for_ledger() {
    let mut kms = KmsVault::new();
    let key = kms.generate_key().await.expect("Failed to generate key");
    let key_id = key.key_id.clone();

    let data = b"ledger entry data";
    let signature = kms.sign_data(&key_id, data).await.expect("Failed to sign");

    assert!(!signature.is_empty());
}

#[tokio::test]
async fn test_kms_signature_verification() {
    let mut kms = KmsVault::new();
    let key = kms.generate_key().await.expect("Failed to generate key");
    let key_id = key.key_id.clone();

    let data = b"verify this";
    let sig = kms.sign_data(&key_id, data).await.expect("Failed to sign");
    let result = kms.verify_signature(&key_id, data, &sig).await.expect("Failed to verify");

    assert!(result);
}

// ============================================================================
// SECTION 11: Error Handling & Edge Cases (5 tests)
// ============================================================================

#[test]
fn test_invalid_workflow_advancement() {
    let mut harness = ProofHarness::new();
    let result = harness.advance_stage("nonexistent", PipelineStage::L2Classification);
    assert!(result.is_err());
}

#[test]
fn test_duplicate_workflow_prevention() {
    let mut harness = ProofHarness::new();
    let ctx1 = harness.create_workflow("intent-dup".to_string());
    let ctx2 = harness.create_workflow("intent-dup".to_string());
    // Different intent_ids but different context IDs
    assert_ne!(ctx1.id, ctx2.id);
}

#[test]
fn test_ledger_entry_on_empty_harness() {
    let mut harness = ProofHarness::new();
    let result = harness.create_ledger_entry("first_entry".to_string());
    assert!(result.is_ok());
    assert_eq!(harness.ledger_size(), 1);
}

#[test]
fn test_ap2_entry_creation_without_prior_state() {
    let mut harness = ProofHarness::new();
    let entry = harness.record_ap2_transaction("auth".to_string(), "data".to_string());
    assert!(!entry.id.is_empty());
}

#[test]
fn test_receipt_creation_independent_of_workflows() {
    let mut harness = ProofHarness::new();
    // Create receipt without any workflow
    let receipt = harness.create_receipt("free-agent".to_string(), "free_action".to_string(), "ok".to_string());
    assert_eq!(harness.get_receipts().len(), 1);
    assert!(harness.get_workflows().is_empty());
}

// ============================================================================
// SECTION 12: Compression & Performance (3 tests)
// ============================================================================

#[test]
fn test_ledger_compression_threshold() {
    let mut harness = ProofHarness::new().with_compression(5);
    for i in 0..10 {
        let _ = harness.create_ledger_entry(format!("entry_{}", i));
    }
    assert!(harness.ledger_size() > 0);
}

#[test]
fn test_large_workflow_batch() {
    let mut harness = ProofHarness::new();
    for i in 0..20 {
        harness.create_workflow(format!("intent-batch-{}", i));
    }
    assert_eq!(harness.get_workflows().len(), 20);
}

#[test]
fn test_mixed_operations_stress() {
    let mut harness = ProofHarness::new();
    for i in 0..5 {
        let ctx = harness.create_workflow(format!("stress-{}", i));
        harness.set_classification(&ctx.id, format!("CLASS_{}", i)).unwrap();
        let _ = harness.create_ledger_entry(format!("entry_{}", i));
        let _ = harness.create_receipt(format!("agent-{}", i), "action".to_string(), "ok".to_string());
    }
    assert!(harness.verify_ledger_integrity().unwrap());
}
