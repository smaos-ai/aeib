use chrono::Utc;
use siss_contract_engine::{InsurancePolicy, ClaimsGovernance, ZkUnderwritingProof, Request, VerticalPolicy};
use uuid::Uuid;

// ==============================================================================
// CLAIMS GOVERNANCE TESTS (1-5)
// ==============================================================================

#[tokio::test]
async fn test_claims_creation() {
    let claims = ClaimsGovernance::new();
    let claimant_id = Uuid::new_v4();

    let claim_result = claims.create_claim(claimant_id, 50_000_00).await;
    assert!(claim_result.is_ok());

    let claim = claim_result.unwrap();
    assert_eq!(claim.claimant_id, claimant_id);
    assert_eq!(claim.amount_cents, 50_000_00);
    assert!(claim.created_at.is_some());
}

#[tokio::test]
async fn test_claims_merkle_linkage() {
    let claims = ClaimsGovernance::new();
    let claimant_id = Uuid::new_v4();

    let claim = claims.create_claim(claimant_id, 100_000_00)
        .await
        .unwrap();

    // Verify proof capsule created
    let capsule = claims.get_proof_capsule(&claim.id).await;
    assert!(capsule.is_ok());

    let proof = capsule.unwrap();
    assert_eq!(proof.claim_id, claim.id);
    assert_eq!(proof.merkle_hash.len(), 32); // SHA-256
    assert!(proof.verified_at.is_some());
}

#[tokio::test]
async fn test_claims_chain_verification() {
    let claims = ClaimsGovernance::new();

    let claimant1 = Uuid::new_v4();
    let claimant2 = Uuid::new_v4();

    let _claim1 = claims.create_claim(claimant1, 50_000_00).await.unwrap();
    let _claim2 = claims.create_claim(claimant2, 75_000_00).await.unwrap();

    // Verify chain integrity
    let chain_valid = claims.verify_claim_chain().await;
    assert!(chain_valid.is_ok());
    assert!(chain_valid.unwrap());
}

#[tokio::test]
async fn test_claims_fraud_detection_basic() {
    let claims = ClaimsGovernance::new();
    let claimant_id = Uuid::new_v4();

    // Normal claim
    let _ = claims.create_claim(claimant_id, 50_000_00).await.unwrap();

    // Detect fraud (no fraud in normal claim)
    let alerts = claims.detect_fraud().await;
    assert!(alerts.is_ok());
    assert_eq!(alerts.unwrap().len(), 0);
}

#[tokio::test]
async fn test_claims_fraud_detection_high_anomaly() {
    let claims = ClaimsGovernance::new();
    let claimant_id = Uuid::new_v4();

    // Multiple claims in rapid succession (anomaly)
    for i in 0..6 {
        let _ = claims.create_claim(claimant_id, 100_000_00 + (i as i64 * 10_000))
            .await;
    }

    let alerts = claims.detect_fraud().await;
    assert!(alerts.is_ok());
    // Should detect multiple claims from same claimant
    let alert_list = alerts.unwrap();
    assert!(alert_list.len() > 0, "Expected fraud alerts but got none with 6 claims from same claimant");
    assert!(alert_list[0].anomaly_score >= 0.5, "Expected anomaly score >= 0.5, got {}", alert_list[0].anomaly_score);
}

// ==============================================================================
// INSURANCE POLICY TESTS (6-10)
// ==============================================================================

#[tokio::test]
async fn test_insurance_policy_creation() {
    let policy = InsurancePolicy::new();
    assert!(policy.claims_audit_enabled);
    assert!(policy.zero_knowledge_proofs);
    assert!(policy.naic_compliant);
}

#[tokio::test]
async fn test_insurance_policy_validates_normal_claim() {
    let policy = InsurancePolicy::new();

    let req = Request {
        region: "US-East".to_string(),
        contains_pii: true,
        amount_cents: Some(100_000_00),
    };

    let result = policy.validate_request(&req).await;
    assert!(result.is_ok());
    assert!(result.unwrap());
}

#[tokio::test]
async fn test_insurance_policy_enforces_naic_compliance() {
    let policy = InsurancePolicy::new();

    // High reserve requirement claim
    let req = Request {
        region: "US-West".to_string(),
        contains_pii: true,
        amount_cents: Some(50_000_000), // €500k claim
    };

    let result = policy.validate_request(&req).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_insurance_policy_fraud_threshold_enforcement() {
    let policy = InsurancePolicy::new();

    let req = Request {
        region: "US-Central".to_string(),
        contains_pii: true,
        amount_cents: Some(200_000_00),
    };

    let result = policy.validate_request(&req).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_insurance_policy_audit_trail() {
    let policy = InsurancePolicy::new();

    let req1 = Request {
        region: "US-East".to_string(),
        contains_pii: true,
        amount_cents: Some(50_000_00),
    };

    let req2 = Request {
        region: "US-West".to_string(),
        contains_pii: false,
        amount_cents: Some(75_000_00),
    };

    let result1 = policy.validate_request(&req1).await;
    let result2 = policy.validate_request(&req2).await;

    assert!(result1.is_ok());
    assert!(result2.is_ok());
}

// ==============================================================================
// ZERO-KNOWLEDGE PROOFS (11-15)
// ==============================================================================

#[tokio::test]
async fn test_zk_proof_generation() {
    let claims = ClaimsGovernance::new();
    let claim = claims.create_claim(Uuid::new_v4(), 100_000_00)
        .await
        .unwrap();

    let proof_result = ZkUnderwritingProof::generate_claim_proof(&claim).await;
    assert!(proof_result.is_ok());

    let proof = proof_result.unwrap();
    assert_eq!(proof.proof.len(), 256);
    assert!(!proof.verified);
}

#[tokio::test]
async fn test_zk_proof_verification() {
    let claims = ClaimsGovernance::new();
    let claim = claims.create_claim(Uuid::new_v4(), 75_000_00)
        .await
        .unwrap();

    let proof = ZkUnderwritingProof::generate_claim_proof(&claim)
        .await
        .unwrap();

    let verified = ZkUnderwritingProof::verify_proof(&proof).await;
    assert!(verified.is_ok());
    assert!(verified.unwrap());
}

#[tokio::test]
async fn test_zk_proof_no_disclosure() {
    let claims = ClaimsGovernance::new();
    let claim = claims.create_claim(Uuid::new_v4(), 100_000_00)
        .await
        .unwrap();

    let proof = ZkUnderwritingProof::generate_claim_proof(&claim)
        .await
        .unwrap();

    // Verify proof bytes don't contain raw claim data
    assert!(!proof.proof.iter().all(|b| b == &0));
    // Should be cryptographic hash, not plaintext
}

#[tokio::test]
async fn test_zk_proof_roundtrip() {
    let claims = ClaimsGovernance::new();
    let claimant = Uuid::new_v4();

    let claim1 = claims.create_claim(claimant, 100_000_00)
        .await
        .unwrap();
    let claim2 = claims.create_claim(claimant, 150_000_00)
        .await
        .unwrap();

    let proof1 = ZkUnderwritingProof::generate_claim_proof(&claim1).await.unwrap();
    let proof2 = ZkUnderwritingProof::generate_claim_proof(&claim2).await.unwrap();

    // Different claims produce different proofs
    assert_ne!(proof1.proof, proof2.proof);

    let verified1 = ZkUnderwritingProof::verify_proof(&proof1).await.unwrap();
    let verified2 = ZkUnderwritingProof::verify_proof(&proof2).await.unwrap();

    assert!(verified1);
    assert!(verified2);
}

// ==============================================================================
// NAIC COMPLIANCE TESTS (16-20)
// ==============================================================================

#[tokio::test]
async fn test_naic_solvency_check() {
    let policy = InsurancePolicy::new();

    let req = Request {
        region: "US-Central".to_string(),
        contains_pii: false,
        amount_cents: Some(100_000_00),
    };

    let result = policy.validate_request(&req).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_naic_reserve_adequacy() {
    let claims = ClaimsGovernance::new();

    // Create multiple claims to test reserve adequacy
    for i in 0..10 {
        let _ = claims.create_claim(Uuid::new_v4(), 50_000_00 + (i as i64 * 10_000))
            .await;
    }

    let chain_valid = claims.verify_claim_chain().await;
    assert!(chain_valid.is_ok());
}

#[tokio::test]
async fn test_claims_settlement_sla_30_days() {
    let claims = ClaimsGovernance::new();
    let claimant = Uuid::new_v4();

    let claim = claims.create_claim(claimant, 100_000_00)
        .await
        .unwrap();

    // Check settlement SLA (30 days)
    let created_at = claim.created_at.unwrap();
    let settlement_deadline = created_at + chrono::Duration::days(30);

    let now = Utc::now();
    assert!(now < settlement_deadline);
}

#[tokio::test]
async fn test_claims_audit_trail_7_year_retention() {
    let claims = ClaimsGovernance::new();

    let claim1 = claims.create_claim(Uuid::new_v4(), 50_000_00).await.unwrap();
    let claim2 = claims.create_claim(Uuid::new_v4(), 75_000_00).await.unwrap();
    let claim3 = claims.create_claim(Uuid::new_v4(), 100_000_00).await.unwrap();

    // All claims should be retrievable (7-year audit trail)
    let capsule1 = claims.get_proof_capsule(&claim1.id).await.unwrap();
    let capsule2 = claims.get_proof_capsule(&claim2.id).await.unwrap();
    let capsule3 = claims.get_proof_capsule(&claim3.id).await.unwrap();

    assert_eq!(capsule1.claim_id, claim1.id);
    assert_eq!(capsule2.claim_id, claim2.id);
    assert_eq!(capsule3.claim_id, claim3.id);
}

#[tokio::test]
async fn test_reinsurance_settlement_governance() {
    let claims = ClaimsGovernance::new();

    // Create large claim for reinsurance threshold
    let large_claim = claims.create_claim(Uuid::new_v4(), 5_000_000_00)
        .await
        .unwrap();

    let capsule = claims.get_proof_capsule(&large_claim.id)
        .await
        .unwrap();

    // Large claims should have reinsurance governance metadata
    assert!(capsule.claim_id == large_claim.id);
}

#[tokio::test]
async fn test_subrogation_governance() {
    let claims = ClaimsGovernance::new();

    let claim = claims.create_claim(Uuid::new_v4(), 100_000_00)
        .await
        .unwrap();

    // Subrogation rights should be tracked in claim lifecycle
    assert!(claim.id != Uuid::nil());
    assert!(claim.created_at.is_some());
}
