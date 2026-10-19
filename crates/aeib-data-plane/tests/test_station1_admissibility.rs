//! crates/aeib-data-plane/tests/test_station1_admissibility.rs
//! ============================================================================
//! Verification tests for Station 1 Constant-Time Admissibility Gate.
//! Tests positive admissibility and 6 fail-closed negative vectors.
//! ============================================================================

use aeib_data_plane::{
    AdmissibilityRejectionCode, AdmissibilityVerdict, PreDispatchIntent, Station1Gate,
    Station1GateConfig,
};
use ed25519_dalek::{Signer, SigningKey};
use rand::rngs::OsRng;
use sha2::{Digest, Sha256};

fn compute_test_caid(payload: &str) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(payload.as_bytes());
    let mut out = [0u8; 32];
    out.copy_from_slice(&hasher.finalize());
    out
}

#[test]
fn test_station1_positive_admissibility() {
    let mut csprng = OsRng;
    let authority_privkey = SigningKey::generate(&mut csprng);
    let authority_pubkey = authority_privkey.verifying_key();

    let harness_digest = [0x42u8; 32];
    let action_caid = compute_test_caid(r#"{"action":"refund","amount":99900}"#);
    let target_contract_id = "urn:aeib:contract:refund:v1".to_string();
    let policy_epoch = 10u64;
    let operation_id = "op-2026-test-pos-001".to_string();

    let commitment = Station1Gate::compute_tuple_commitment(
        &operation_id,
        &target_contract_id,
        policy_epoch,
        &harness_digest,
        &action_caid,
    );
    let signature = authority_privkey.sign(&commitment);
    let signature_hex = hex::encode(signature.to_bytes());

    let config = Station1GateConfig {
        expected_target_contract_id: target_contract_id.clone(),
        min_policy_epoch: 10,
        expected_harness_digest: harness_digest,
        authority_verifying_key: authority_pubkey,
    };
    let gate = Station1Gate::new(config);

    let intent = PreDispatchIntent {
        operation_id: operation_id.clone(),
        target_contract_id,
        policy_epoch,
        harness_digest,
        action_caid,
        authority_signature_hex: signature_hex,
    };

    let verdict = gate.evaluate(&intent, &action_caid);
    assert_eq!(
        verdict,
        AdmissibilityVerdict::Admitted {
            operation_id,
            commitment_digest: commitment,
            policy_epoch: 10,
        }
    );
}

#[test]
fn test_station1_negative_vector_contract_mismatch() {
    let mut csprng = OsRng;
    let authority_privkey = SigningKey::generate(&mut csprng);
    let authority_pubkey = authority_privkey.verifying_key();

    let harness_digest = [0x42u8; 32];
    let action_caid = compute_test_caid(r#"{"action":"refund"}"#);

    let config = Station1GateConfig {
        expected_target_contract_id: "urn:aeib:contract:refund:v1".to_string(),
        min_policy_epoch: 10,
        expected_harness_digest: harness_digest,
        authority_verifying_key: authority_pubkey,
    };
    let gate = Station1Gate::new(config);

    let intent = PreDispatchIntent {
        operation_id: "op-neg-1".to_string(),
        target_contract_id: "urn:aeib:contract:unauthorized:v1".to_string(),
        policy_epoch: 10,
        harness_digest,
        action_caid,
        authority_signature_hex: hex::encode([0u8; 64]),
    };

    let verdict = gate.evaluate(&intent, &action_caid);
    match verdict {
        AdmissibilityVerdict::Rejected { rejection_code, .. } => {
            assert_eq!(
                rejection_code,
                AdmissibilityRejectionCode::TargetContractMismatch
            );
        }
        _ => panic!("Expected rejection on target contract mismatch"),
    }
}

#[test]
fn test_station1_negative_vector_stale_policy_epoch() {
    let mut csprng = OsRng;
    let authority_privkey = SigningKey::generate(&mut csprng);
    let authority_pubkey = authority_privkey.verifying_key();

    let harness_digest = [0x42u8; 32];
    let action_caid = compute_test_caid(r#"{"action":"refund"}"#);

    let config = Station1GateConfig {
        expected_target_contract_id: "urn:aeib:contract:refund:v1".to_string(),
        min_policy_epoch: 15,
        expected_harness_digest: harness_digest,
        authority_verifying_key: authority_pubkey,
    };
    let gate = Station1Gate::new(config);

    let intent = PreDispatchIntent {
        operation_id: "op-neg-2".to_string(),
        target_contract_id: "urn:aeib:contract:refund:v1".to_string(),
        policy_epoch: 14, // Stale!
        harness_digest,
        action_caid,
        authority_signature_hex: hex::encode([0u8; 64]),
    };

    let verdict = gate.evaluate(&intent, &action_caid);
    match verdict {
        AdmissibilityVerdict::Rejected { rejection_code, .. } => {
            assert_eq!(rejection_code, AdmissibilityRejectionCode::StalePolicyEpoch);
        }
        _ => panic!("Expected rejection on stale policy epoch"),
    }
}

#[test]
fn test_station1_negative_vector_harness_digest_mismatch() {
    let mut csprng = OsRng;
    let authority_privkey = SigningKey::generate(&mut csprng);
    let authority_pubkey = authority_privkey.verifying_key();

    let expected_harness = [0x11u8; 32];
    let tampered_harness = [0x22u8; 32];
    let action_caid = compute_test_caid(r#"{"action":"refund"}"#);

    let config = Station1GateConfig {
        expected_target_contract_id: "urn:aeib:contract:refund:v1".to_string(),
        min_policy_epoch: 10,
        expected_harness_digest: expected_harness,
        authority_verifying_key: authority_pubkey,
    };
    let gate = Station1Gate::new(config);

    let intent = PreDispatchIntent {
        operation_id: "op-neg-3".to_string(),
        target_contract_id: "urn:aeib:contract:refund:v1".to_string(),
        policy_epoch: 10,
        harness_digest: tampered_harness,
        action_caid,
        authority_signature_hex: hex::encode([0u8; 64]),
    };

    let verdict = gate.evaluate(&intent, &action_caid);
    match verdict {
        AdmissibilityVerdict::Rejected { rejection_code, .. } => {
            assert_eq!(
                rejection_code,
                AdmissibilityRejectionCode::HarnessDigestMismatch
            );
        }
        _ => panic!("Expected rejection on harness digest mismatch"),
    }
}

#[test]
fn test_station1_negative_vector_action_caid_mismatch() {
    let mut csprng = OsRng;
    let authority_privkey = SigningKey::generate(&mut csprng);
    let authority_pubkey = authority_privkey.verifying_key();

    let harness_digest = [0x11u8; 32];
    let claimed_caid = compute_test_caid(r#"{"action":"refund","amount":100}"#);
    let actual_wire_caid = compute_test_caid(r#"{"action":"refund","amount":9999}"#); // Wire payload mutated!

    let config = Station1GateConfig {
        expected_target_contract_id: "urn:aeib:contract:refund:v1".to_string(),
        min_policy_epoch: 10,
        expected_harness_digest: harness_digest,
        authority_verifying_key: authority_pubkey,
    };
    let gate = Station1Gate::new(config);

    let intent = PreDispatchIntent {
        operation_id: "op-neg-4".to_string(),
        target_contract_id: "urn:aeib:contract:refund:v1".to_string(),
        policy_epoch: 10,
        harness_digest,
        action_caid: claimed_caid,
        authority_signature_hex: hex::encode([0u8; 64]),
    };

    let verdict = gate.evaluate(&intent, &actual_wire_caid);
    match verdict {
        AdmissibilityVerdict::Rejected { rejection_code, .. } => {
            assert_eq!(
                rejection_code,
                AdmissibilityRejectionCode::ActionCaidMismatch
            );
        }
        _ => panic!("Expected rejection on action CAID mismatch"),
    }
}

#[test]
fn test_station1_negative_vector_invalid_authority_signature() {
    let mut csprng = OsRng;
    let authority_privkey = SigningKey::generate(&mut csprng);
    let authority_pubkey = authority_privkey.verifying_key();
    let attacker_privkey = SigningKey::generate(&mut csprng); // Forger key!

    let harness_digest = [0x11u8; 32];
    let action_caid = compute_test_caid(r#"{"action":"refund"}"#);
    let target_contract_id = "urn:aeib:contract:refund:v1".to_string();
    let policy_epoch = 10u64;
    let operation_id = "op-neg-5".to_string();

    let commitment = Station1Gate::compute_tuple_commitment(
        &operation_id,
        &target_contract_id,
        policy_epoch,
        &harness_digest,
        &action_caid,
    );
    let forged_signature = attacker_privkey.sign(&commitment);

    let config = Station1GateConfig {
        expected_target_contract_id: target_contract_id.clone(),
        min_policy_epoch: 10,
        expected_harness_digest: harness_digest,
        authority_verifying_key: authority_pubkey,
    };
    let gate = Station1Gate::new(config);

    let intent = PreDispatchIntent {
        operation_id,
        target_contract_id,
        policy_epoch,
        harness_digest,
        action_caid,
        authority_signature_hex: hex::encode(forged_signature.to_bytes()),
    };

    let verdict = gate.evaluate(&intent, &action_caid);
    match verdict {
        AdmissibilityVerdict::Rejected { rejection_code, .. } => {
            assert_eq!(
                rejection_code,
                AdmissibilityRejectionCode::InvalidAuthoritySignature
            );
        }
        _ => panic!("Expected rejection on forged authority signature"),
    }
}
