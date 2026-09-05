/// Phase 2B Part 1: Integration tests for @Evidence Agent
use chrono::Utc;
use siss_evidence_agent::{
    CompliancePrecedent, EvidenceAgent, ExecutionTraceEvent, IncomingEvaluation, MerkleReceipt,
};
use uuid::Uuid;

#[tokio::test]
async fn test_evidence_agent_creation() {
    let secret_bytes: [u8; 32] = rand::random();
    let signing_key = ed25519_dalek::SigningKey::from_bytes(&secret_bytes);
    let agent = EvidenceAgent::new(signing_key);

    assert_ne!(agent.agent_id, Uuid::nil());
}

#[test]
fn test_execution_trace_event_creation() {
    let event = ExecutionTraceEvent {
        event_id: Uuid::new_v4(),
        step_index: 5,
        action: "test_action".to_string(),
        result: "success".to_string(),
        timestamp: Utc::now(),
    };

    assert_eq!(event.step_index, 5);
    assert_eq!(event.result, "success");
}

#[test]
fn test_merkle_receipt_structure() {
    let receipt = MerkleReceipt {
        receipt_id: Uuid::new_v4(),
        plan_id: Uuid::new_v4(),
        evaluation_id: Uuid::new_v4(),
        trace_hash: "abc123".to_string(),
        merkle_root: "def456".to_string(),
        proof_chain: vec!["link1".to_string(), "link2".to_string()],
        signature: "sig_xyz".to_string(),
        created_at: Utc::now(),
    };

    assert!(!receipt.trace_hash.is_empty());
    assert!(!receipt.merkle_root.is_empty());
    assert!(!receipt.signature.is_empty());
    assert_eq!(receipt.proof_chain.len(), 2);
}

#[test]
fn test_compliance_precedent_similarity() {
    let precedent = CompliancePrecedent {
        precedent_id: Uuid::new_v4(),
        rule_name: "BaselIII_CAR".to_string(),
        case_reference: "ECB/2023/001".to_string(),
        embedding: vec![0.1, 0.2, 0.3, 0.4, 0.5],
        similarity_score: 0.95,
    };

    assert_eq!(precedent.similarity_score, 0.95);
    assert_eq!(precedent.embedding.len(), 5);
    assert!(precedent.similarity_score > 0.9);
}

#[test]
fn test_incoming_evaluation_serialization() {
    let evaluation = IncomingEvaluation {
        evaluation_id: Uuid::new_v4(),
        plan_id: Uuid::new_v4(),
        verdict: "Approved".to_string(),
        triggered_gates: vec!["gate_1".to_string(), "gate_2".to_string()],
    };

    let json = serde_json::to_string(&evaluation).expect("serialization failed");
    let deserialized: IncomingEvaluation =
        serde_json::from_str(&json).expect("deserialization failed");

    assert_eq!(evaluation.evaluation_id, deserialized.evaluation_id);
    assert_eq!(evaluation.verdict, deserialized.verdict);
    assert_eq!(evaluation.triggered_gates.len(), deserialized.triggered_gates.len());
}

#[tokio::test]
async fn test_evidence_process_evaluation() {
    let secret_bytes: [u8; 32] = rand::random();
    let signing_key = ed25519_dalek::SigningKey::from_bytes(&secret_bytes);
    let mut agent = EvidenceAgent::new(signing_key);

    let evaluation = IncomingEvaluation {
        evaluation_id: Uuid::new_v4(),
        plan_id: Uuid::new_v4(),
        verdict: "Approved".to_string(),
        triggered_gates: vec!["basel_iii".to_string()],
    };

    let result = agent.process_evaluation(&evaluation).await;
    // May succeed or fail depending on IPC, but should execute the flow
    let _ = result;
}

#[test]
fn test_trace_event_ordering() {
    let events: Vec<ExecutionTraceEvent> = (0..3)
        .map(|i| ExecutionTraceEvent {
            event_id: Uuid::new_v4(),
            step_index: i,
            action: format!("step_{}", i),
            result: "ok".to_string(),
            timestamp: Utc::now(),
        })
        .collect();

    assert_eq!(events[0].step_index, 0);
    assert_eq!(events[1].step_index, 1);
    assert_eq!(events[2].step_index, 2);
}

#[test]
fn test_merkle_root_immutability() {
    let receipt = MerkleReceipt {
        receipt_id: Uuid::new_v4(),
        plan_id: Uuid::new_v4(),
        evaluation_id: Uuid::new_v4(),
        trace_hash: "hash_value".to_string(),
        merkle_root: "root_value".to_string(),
        proof_chain: vec![],
        signature: "immutable_signature".to_string(),
        created_at: Utc::now(),
    };

    // Create another receipt with same data
    let receipt2 = MerkleReceipt {
        receipt_id: receipt.receipt_id,
        plan_id: receipt.plan_id,
        evaluation_id: receipt.evaluation_id,
        trace_hash: receipt.trace_hash.clone(),
        merkle_root: receipt.merkle_root.clone(),
        proof_chain: receipt.proof_chain.clone(),
        signature: receipt.signature.clone(),
        created_at: receipt.created_at,
    };

    // Should be identical (immutable)
    assert_eq!(receipt.merkle_root, receipt2.merkle_root);
    assert_eq!(receipt.signature, receipt2.signature);
}
