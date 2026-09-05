/// Phase 2B Part 1: Integration tests for A2A IPC layer
use chrono::Utc;
use ed25519_dalek::{SigningKey, Signer};
use siss_a2a_ipc::{A2AMessage, IPCConfig, MessageType};
use std::path::PathBuf;
use uuid::Uuid;

#[test]
fn test_a2a_message_serialization_deserialization() {
    let msg = A2AMessage {
        agent_id: Uuid::new_v4(),
        message_type: MessageType::HealthCheck,
        payload: serde_json::json!({"status": "healthy"}),
        timestamp: Utc::now(),
        signature: "test_signature".to_string(),
    };

    let json = serde_json::to_string(&msg).expect("serialization failed");
    let deserialized: A2AMessage =
        serde_json::from_str(&json).expect("deserialization failed");

    assert_eq!(msg.agent_id, deserialized.agent_id);
    assert_eq!(msg.message_type, deserialized.message_type);
    assert_eq!(msg.signature, deserialized.signature);
}

#[test]
fn test_message_type_enum_all_variants() {
    let types = vec![
        MessageType::PlannerToCompliance,
        MessageType::ComplianceToEvidence,
        MessageType::EvidenceToLedger,
        MessageType::HealthCheck,
        MessageType::Ack,
        MessageType::Nack,
    ];

    for msg_type in types {
        let json = serde_json::to_string(&msg_type).expect("serialization failed");
        let deserialized: MessageType =
            serde_json::from_str(&json).expect("deserialization failed");
        assert_eq!(msg_type, deserialized);
    }
}

#[test]
fn test_ipc_config_defaults() {
    let config = IPCConfig::default();
    assert_eq!(config.max_message_size, 16 * 1024 * 1024);
    assert_eq!(config.timeout_secs, 30);
    assert_eq!(config.socket_path, PathBuf::from("/tmp/siss-a2a.sock"));
}

#[test]
fn test_ipc_config_custom() {
    let config = IPCConfig {
        socket_path: PathBuf::from("/custom/path.sock"),
        max_message_size: 32 * 1024 * 1024,
        timeout_secs: 60,
    };

    assert_eq!(config.socket_path, PathBuf::from("/custom/path.sock"));
    assert_eq!(config.max_message_size, 32 * 1024 * 1024);
    assert_eq!(config.timeout_secs, 60);
}

#[tokio::test]
async fn test_signing_key_generation() {
    let secret_bytes1: [u8; 32] = rand::random();
    let key1 = SigningKey::from_bytes(&secret_bytes1);
    let secret_bytes2: [u8; 32] = rand::random();
    let key2 = SigningKey::from_bytes(&secret_bytes2);

    // Keys should be different
    let bytes1 = key1.to_bytes();
    let bytes2 = key2.to_bytes();
    assert_ne!(bytes1, bytes2);
}

#[test]
fn test_message_signature_hex_encoding() {
    let secret_bytes: [u8; 32] = rand::random();
    let signing_key = SigningKey::from_bytes(&secret_bytes);
    let payload = b"test payload";
    let signature = signing_key.sign(payload);
    let sig_hex = hex::encode(signature.to_bytes());

    // Hex encoding should be valid
    assert_eq!(sig_hex.len(), 128); // 64 bytes * 2 (hex)
    assert!(sig_hex.chars().all(|c| c.is_ascii_hexdigit()));
}
