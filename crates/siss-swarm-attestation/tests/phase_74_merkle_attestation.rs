use chrono::Utc;
use ed25519_dalek::SigningKey;
use rand::rngs::OsRng;
use siss_swarm_attestation::mcp::{
    MerkleSwarmState, compute_merkle_root, sign_state, verify_peer_attestation,
};

#[test]
fn test_compute_deterministic_merkle_root() {
    let states = vec![
        MerkleSwarmState {
            idempotency_key: "a".into(),
            status: "COMPLETE".into(),
            phase: "test".into(),
            payload_json: None,
            created_at: Utc::now(),
            updated_at: Utc::now(),
            merkle_root: None,
            attestation_sig: None,
            node_id: "node1".into(),
        },
        MerkleSwarmState {
            idempotency_key: "b".into(),
            status: "RUNNING".into(),
            phase: "test".into(),
            payload_json: None,
            created_at: Utc::now(),
            updated_at: Utc::now(),
            merkle_root: None,
            attestation_sig: None,
            node_id: "node1".into(),
        },
    ];
    let root1 = compute_merkle_root(&states);
    let root2 = compute_merkle_root(&states);
    assert_eq!(root1, root2, "Merkle root must be deterministic");
}

#[test]
fn test_sign_and_verify_attestation() {
    let mut csprng = OsRng;
    let signing_key = SigningKey::generate(&mut csprng);
    let verifying_key = signing_key.verifying_key();

    let state = MerkleSwarmState {
        idempotency_key: "test".into(),
        status: "COMPLETE".into(),
        phase: "phase74".into(),
        payload_json: None,
        created_at: Utc::now(),
        updated_at: Utc::now(),
        merkle_root: Some("abc123".into()),
        attestation_sig: None,
        node_id: "node1".into(),
    };

    let sig = sign_state(&state, &signing_key).expect("signing failed");
    let valid = verify_peer_attestation("node1", "abc123", &sig, &verifying_key)
        .expect("verification failed");
    assert!(valid, "Attestation must verify");
}

#[test]
fn test_reject_tampered_attestation() {
    let mut csprng = OsRng;
    let signing_key = SigningKey::generate(&mut csprng);
    let verifying_key = signing_key.verifying_key();

    let state = MerkleSwarmState {
        idempotency_key: "test".into(),
        status: "COMPLETE".into(),
        phase: "phase74".into(),
        payload_json: None,
        created_at: Utc::now(),
        updated_at: Utc::now(),
        merkle_root: Some("abc123".into()),
        attestation_sig: None,
        node_id: "node1".into(),
    };

    let sig = sign_state(&state, &signing_key).expect("signing failed");
    // Tamper with merkle_root
    let valid = verify_peer_attestation("node1", "xyz789", &sig, &verifying_key)
        .expect("verification check failed");
    assert!(!valid, "Tampered attestation must fail");
}
