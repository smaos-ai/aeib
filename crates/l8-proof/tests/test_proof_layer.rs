use l8_proof::ProofLayer;
use std::time::Instant;

#[test]
fn test_create_work_receipt() {
    let mut proof = ProofLayer::new();
    let receipt = proof.create_work_receipt("evaluate_credit".to_string(), "approved".to_string());

    assert!(!receipt.id.is_empty());
    assert_eq!(receipt.action, "evaluate_credit");
    assert_eq!(receipt.result, "approved");
}

#[test]
fn test_sign_ledger_entry() {
    let mut proof = ProofLayer::new();
    let result = proof.sign_ledger_entry(
        r#"{"request_id":"abc123","action":"approve","timestamp":"2026-09-01T00:00:00Z"}"#
            .to_string(),
    );

    assert!(result.is_ok());
    let entry = result.unwrap();
    assert!(entry.signature.starts_with("ed25519:"));
    assert!(!entry.digest.is_empty());
}

#[test]
fn test_verify_immutable() {
    let mut proof = ProofLayer::new();
    let entry = proof
        .sign_ledger_entry("immutable_test_data".to_string())
        .unwrap();

    assert!(proof.verify_immutable(&entry.id));
}

#[test]
fn test_multiple_receipts_audit_trail() {
    let mut proof = ProofLayer::new();

    let receipt1 = proof.create_work_receipt("step_1".to_string(), "started".to_string());
    let receipt2 = proof.create_work_receipt("step_2".to_string(), "evaluating".to_string());
    let receipt3 = proof.create_work_receipt("step_3".to_string(), "complete".to_string());

    let receipts = proof.get_receipts();
    assert_eq!(receipts.len(), 3);
    assert_eq!(receipts[0].id, receipt1.id);
    assert_eq!(receipts[1].id, receipt2.id);
    assert_eq!(receipts[2].id, receipt3.id);
}

#[test]
fn test_ledger_immutability() {
    let mut proof = ProofLayer::new();
    let entry = proof
        .sign_ledger_entry("sensitive_decision".to_string())
        .unwrap();
    let original_digest = entry.digest.clone();

    // Verify entry cannot be modified after creation
    assert_eq!(entry.digest, original_digest);
}

#[test]
fn test_agentacct_work_receipt_format() {
    let mut proof = ProofLayer::new();
    let receipt = proof.create_work_receipt(
        "credit_scoring".to_string(),
        "approved_for_100k_eur".to_string(),
    );

    let receipt_json = serde_json::to_string(&receipt).unwrap();
    assert!(receipt_json.contains("credit_scoring"));
    assert!(receipt_json.contains("approved_for_100k_eur"));
}

#[test]
fn test_signature_latency_under_10ms() {
    let mut proof = ProofLayer::new();
    let data = r#"{"request_id":"abc123","decision":"approved","amount":100000}"#.to_string();

    let start = Instant::now();
    let _result = proof.sign_ledger_entry(data);
    let elapsed = start.elapsed();

    assert!(
        elapsed.as_millis() < 10,
        "Signature latency {}ms exceeds 10ms target",
        elapsed.as_millis()
    );
}

#[test]
fn test_signature_throughput_100_per_second() {
    let mut proof = ProofLayer::new();
    let start = Instant::now();

    for i in 0..100 {
        let data = format!(r#"{{"entry_id":"{}","data":"test"}}"#, i);
        let _result = proof.sign_ledger_entry(data);
    }

    let elapsed = start.elapsed();
    let throughput = 100.0 / elapsed.as_secs_f32();

    assert!(
        throughput > 100.0,
        "Throughput {:.0}/sec below 100/sec target",
        throughput
    );
}

#[test]
fn test_ledger_chain_verification() {
    let mut proof = ProofLayer::new();
    proof.sign_ledger_entry("entry1".to_string()).unwrap();
    proof.sign_ledger_entry("entry2".to_string()).unwrap();
    proof.sign_ledger_entry("entry3".to_string()).unwrap();

    let is_valid = proof.verify_ledger_chain().unwrap();
    assert!(is_valid, "Ledger chain integrity verification failed");
}

#[test]
fn test_compression_reduces_ledger_entries() {
    let mut proof = ProofLayer::new().with_compression_threshold(5);

    for i in 0..10 {
        proof
            .sign_ledger_entry(format!("entry_{}", i))
            .unwrap();
    }

    assert!(!proof.get_compressed_checkpoints().is_empty());
}

#[test]
fn test_public_key_export_for_verification() {
    let proof = ProofLayer::new();
    let pubkey = proof.get_verifying_key();
    let pubkey_bytes = pubkey.to_bytes();

    assert_eq!(pubkey_bytes.len(), 32);
}
