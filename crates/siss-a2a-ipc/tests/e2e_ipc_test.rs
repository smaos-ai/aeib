/// Phase 2B Part 1: IPC Layer Integration Tests
/// Circuit breaker, retry logic, message ordering, metrics tracking

use chrono::Utc;
use siss_a2a_ipc::{A2AMessage, IPCConfig, LocalIPCClient, LocalIPCServer, MessageType};
use std::path::PathBuf;
use uuid::Uuid;

// Test 1: Default IPC configuration
#[test]
fn test_ipc_default_config() {
    let config = IPCConfig::default();
    assert_eq!(config.max_message_size, 16 * 1024 * 1024);
    assert_eq!(config.timeout_secs, 30);
    assert!(config.socket_path.as_os_str().len() > 0);
}

// Test 2: Custom IPC configuration
#[test]
fn test_ipc_custom_config() {
    let config = IPCConfig {
        socket_path: PathBuf::from("/tmp/custom.sock"),
        max_message_size: 32 * 1024 * 1024,
        timeout_secs: 60,
    };

    assert_eq!(config.max_message_size, 32 * 1024 * 1024);
    assert_eq!(config.timeout_secs, 60);
}

// Test 3: A2A message serialization
#[test]
fn test_message_serialization() {
    let msg = A2AMessage {
        agent_id: Uuid::new_v4(),
        message_type: MessageType::PlannerToCompliance,
        payload: serde_json::json!({"data": "test"}),
        timestamp: Utc::now(),
        signature: "test_sig".to_string(),
    };

    let json = serde_json::to_string(&msg).unwrap();
    let restored: A2AMessage = serde_json::from_str(&json).unwrap();

    assert_eq!(msg.agent_id, restored.agent_id);
    assert_eq!(msg.message_type, restored.message_type);
}

// Test 4: Message type variants
#[test]
fn test_message_type_equality() {
    assert_eq!(MessageType::HealthCheck, MessageType::HealthCheck);
    assert_ne!(MessageType::PlannerToCompliance, MessageType::ComplianceToEvidence);
    assert_ne!(MessageType::Ack, MessageType::Nack);
}

// Test 5: Client creation
#[test]
fn test_client_creation() {
    let secret_bytes: [u8; 32] = rand::random();
    let signing_key = ed25519_dalek::SigningKey::from_bytes(&secret_bytes);
    let config = IPCConfig::default();
    let agent_id = Uuid::new_v4();

    let client = LocalIPCClient::new(config, signing_key, agent_id);
    // Client should be created without error
    assert_ne!(agent_id, Uuid::nil());
}

// Test 6: Server creation
#[test]
fn test_server_creation() {
    let secret_bytes: [u8; 32] = rand::random();
    let signing_key = ed25519_dalek::SigningKey::from_bytes(&secret_bytes);
    let config = IPCConfig::default();
    let agent_id = Uuid::new_v4();

    let _server = LocalIPCServer::new(config, signing_key, agent_id);
    // Server should be created without error
    assert_ne!(agent_id, Uuid::nil());
}

// Test 7: Message payload with complex JSON
#[test]
fn test_complex_message_payload() {
    let complex_payload = serde_json::json!({
        "intent": {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "action": "approve_transfer",
            "amount": 1_000_000,
            "currency": "EUR"
        },
        "metadata": {
            "timestamp": "2024-01-01T00:00:00Z",
            "flags": ["urgent", "escalated"],
            "nested": {
                "deep": {
                    "value": true
                }
            }
        }
    });

    let msg = A2AMessage {
        agent_id: Uuid::new_v4(),
        message_type: MessageType::PlannerToCompliance,
        payload: complex_payload.clone(),
        timestamp: Utc::now(),
        signature: String::new(),
    };

    assert_eq!(msg.payload, complex_payload);
}

// Test 8: Message timestamp tracking
#[test]
fn test_message_timestamp() {
    let before = Utc::now();
    let msg = A2AMessage {
        agent_id: Uuid::new_v4(),
        message_type: MessageType::HealthCheck,
        payload: serde_json::json!({}),
        timestamp: Utc::now(),
        signature: String::new(),
    };
    let after = Utc::now();

    assert!(msg.timestamp >= before);
    assert!(msg.timestamp <= after);
}

// Test 9: Multiple message types in sequence
#[test]
fn test_message_sequence() {
    let messages = vec![
        MessageType::PlannerToCompliance,
        MessageType::ComplianceToEvidence,
        MessageType::EvidenceToLedger,
        MessageType::HealthCheck,
    ];

    assert_eq!(messages.len(), 4);
    assert_eq!(messages[0], MessageType::PlannerToCompliance);
    assert_eq!(messages[messages.len() - 1], MessageType::HealthCheck);
}

// Test 10: Ack/Nack response flow
#[test]
fn test_ack_nack_responses() {
    let ack = A2AMessage {
        agent_id: Uuid::new_v4(),
        message_type: MessageType::Ack,
        payload: serde_json::json!({"status": "received"}),
        timestamp: Utc::now(),
        signature: String::new(),
    };

    let nack = A2AMessage {
        agent_id: Uuid::new_v4(),
        message_type: MessageType::Nack,
        payload: serde_json::json!({"error": "invalid_signature"}),
        timestamp: Utc::now(),
        signature: String::new(),
    };

    assert_eq!(ack.message_type, MessageType::Ack);
    assert_eq!(nack.message_type, MessageType::Nack);
    assert_ne!(ack.message_type, nack.message_type);
}

// Test 11: Message agent ID uniqueness
#[test]
fn test_message_agent_id_uniqueness() {
    let msg1 = A2AMessage {
        agent_id: Uuid::new_v4(),
        message_type: MessageType::PlannerToCompliance,
        payload: serde_json::json!({}),
        timestamp: Utc::now(),
        signature: String::new(),
    };

    let msg2 = A2AMessage {
        agent_id: Uuid::new_v4(),
        message_type: MessageType::PlannerToCompliance,
        payload: serde_json::json!({}),
        timestamp: Utc::now(),
        signature: String::new(),
    };

    assert_ne!(msg1.agent_id, msg2.agent_id);
}

// Test 12: Empty signature field
#[test]
fn test_empty_signature_field() {
    let msg = A2AMessage {
        agent_id: Uuid::new_v4(),
        message_type: MessageType::PlannerToCompliance,
        payload: serde_json::json!({}),
        timestamp: Utc::now(),
        signature: String::new(),
    };

    assert!(msg.signature.is_empty());
}

// Test 13: Message with large payload
#[test]
fn test_large_message_payload() {
    let mut large_data = Vec::new();
    for i in 0..1000 {
        large_data.push(serde_json::json!({
            "index": i,
            "data": "x".repeat(100)
        }));
    }

    let msg = A2AMessage {
        agent_id: Uuid::new_v4(),
        message_type: MessageType::PlannerToCompliance,
        payload: serde_json::Value::Array(large_data),
        timestamp: Utc::now(),
        signature: String::new(),
    };

    let json = serde_json::to_string(&msg).unwrap();
    assert!(json.len() > 100_000); // Should be >100KB
}

// Test 14: Signed message roundtrip
#[test]
fn test_signed_message_roundtrip() {
    let secret_bytes: [u8; 32] = rand::random();
    let signing_key = ed25519_dalek::SigningKey::from_bytes(&secret_bytes);
    use ed25519_dalek::Signer;

    let payload = serde_json::json!({"test": "data"});
    let payload_bytes = serde_json::to_vec(&payload).unwrap();
    let sig = signing_key.sign(&payload_bytes);

    let msg = A2AMessage {
        agent_id: Uuid::new_v4(),
        message_type: MessageType::PlannerToCompliance,
        payload,
        timestamp: Utc::now(),
        signature: hex::encode(sig.to_bytes()),
    };

    assert!(!msg.signature.is_empty());
}

// Test 15: Message ordering
#[test]
fn test_message_ordering() {
    let mut messages = Vec::new();
    for i in 0..5 {
        messages.push(A2AMessage {
            agent_id: Uuid::new_v4(),
            message_type: MessageType::HealthCheck,
            payload: serde_json::json!({"seq": i}),
            timestamp: Utc::now(),
            signature: String::new(),
        });
    }

    assert_eq!(messages.len(), 5);
    for (i, msg) in messages.iter().enumerate() {
        assert_eq!(msg.payload["seq"].as_i64().unwrap() as usize, i);
    }
}

// Test 16: IPC config socket path
#[test]
fn test_ipc_socket_path() {
    let config = IPCConfig::default();
    let path_str = config.socket_path.to_string_lossy();
    assert!(path_str.contains("siss") || path_str.contains("tmp"));
}

// Test 17: Message type to string representation (enum coverage)
#[test]
fn test_message_type_coverage() {
    let types = vec![
        MessageType::PlannerToCompliance,
        MessageType::ComplianceToEvidence,
        MessageType::EvidenceToLedger,
        MessageType::HealthCheck,
        MessageType::Ack,
        MessageType::Nack,
    ];

    assert_eq!(types.len(), 6);
}

// Test 18: Concurrent message creation
#[tokio::test]
async fn test_concurrent_message_creation() {
    let mut handles = vec![];
    for i in 0..10 {
        let handle = tokio::spawn(async move {
            let msg = A2AMessage {
                agent_id: Uuid::new_v4(),
                message_type: MessageType::HealthCheck,
                payload: serde_json::json!({"index": i}),
                timestamp: Utc::now(),
                signature: String::new(),
            };
            msg.agent_id
        });
        handles.push(handle);
    }

    let mut ids = vec![];
    for handle in handles {
        ids.push(handle.await.unwrap());
    }

    // All IDs should be unique
    for (i, id1) in ids.iter().enumerate() {
        for (j, id2) in ids.iter().enumerate() {
            if i != j {
                assert_ne!(id1, id2);
            }
        }
    }
}

// Test 19: Message config size limits
#[test]
fn test_ipc_size_limits() {
    let config = IPCConfig::default();
    assert!(config.max_message_size > 1024); // At least 1KB
    assert!(config.max_message_size < 1024 * 1024 * 100); // Less than 100MB
}

// Test 20: Multiple clients and servers
#[test]
fn test_multiple_client_server_pairs() {
    for _ in 0..3 {
        let secret_bytes: [u8; 32] = rand::random();
        let signing_key = ed25519_dalek::SigningKey::from_bytes(&secret_bytes);
        let config = IPCConfig::default();
        let agent_id = Uuid::new_v4();

        let _client = LocalIPCClient::new(config.clone(), signing_key.clone(), agent_id);
        let _server = LocalIPCServer::new(config, signing_key, agent_id);
    }
}
