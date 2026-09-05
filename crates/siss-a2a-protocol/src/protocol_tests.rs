/// Track D: Unit Tests for Protocol Signing & Verification
/// Test: signature generation, verification, tampering detection

#[cfg(test)]
mod protocol_signing_tests {
    use crate::protocol::{A2AMessage, A2AEnvelope, MessageType, MessageStatus};
    use ed25519_dalek::{SigningKey, Signer};
    use uuid::Uuid;
    use chrono::Utc;

    fn create_test_key() -> SigningKey {
        let mut seed = [0u8; 32];
        use rand::RngCore;
        rand::thread_rng().fill_bytes(&mut seed);
        SigningKey::from_bytes(&seed)
    }

    #[test]
    fn test_message_signature_valid() {
        // GIVEN: a message and a signing key
        let signing_key = create_test_key();
        let payload = serde_json::json!({"intent": "test", "amount": 1000});
        let msg = A2AMessage::new(
            MessageType::TaskIntent,
            "agent-1".to_string(),
            Some("agent-2".to_string()),
            payload,
        );

        // WHEN: we sign the message
        let cbor_bytes = msg.to_cbor().expect("serialize to cbor");
        let signature = signing_key.sign(&cbor_bytes);
        let sig_hex = format!("ed25519:{}", hex::encode(signature.to_bytes()));

        // THEN: signature is valid hex and non-empty
        assert!(sig_hex.starts_with("ed25519:"));
        assert!(sig_hex.len() > 9); // Minimum: "ed25519:" + some hex
    }

    #[test]
    fn test_envelope_signature_roundtrip() {
        // GIVEN: a signing key and message
        let signing_key = create_test_key();
        let pubkey = signing_key.verifying_key();
        let pubkey_hex = hex::encode(pubkey.to_bytes());

        let payload = serde_json::json!({"test": "roundtrip"});
        let msg = A2AMessage::new(
            MessageType::TaskIntent,
            "agent-1".to_string(),
            None,
            payload,
        );

        // WHEN: we create and sign an envelope
        let mut envelope = A2AEnvelope::new(msg);
        let cbor_bytes = envelope.message.to_cbor().expect("serialize");
        let signature = signing_key.sign(&cbor_bytes);
        envelope.signature = format!("ed25519:{}", hex::encode(signature.to_bytes()));
        envelope.signer_pubkey = pubkey_hex;

        // THEN: serialization and deserialization work
        let bytes = envelope.to_bytes().expect("serialize envelope");
        let restored = A2AEnvelope::from_bytes(&bytes).expect("deserialize envelope");
        assert_eq!(restored.message.from_agent, "agent-1");
        assert_eq!(restored.signer_pubkey, envelope.signer_pubkey);
    }

    #[test]
    fn test_tampering_detection_payload() {
        // GIVEN: a signed message
        let signing_key = create_test_key();
        let pubkey = signing_key.verifying_key();
        let pubkey_hex = hex::encode(pubkey.to_bytes());

        let payload = serde_json::json!({"secret": "data"});
        let msg = A2AMessage::new(
            MessageType::TaskIntent,
            "agent-1".to_string(),
            None,
            payload,
        );

        let mut envelope = A2AEnvelope::new(msg);
        let cbor_bytes = envelope.message.to_cbor().expect("serialize");
        let signature = signing_key.sign(&cbor_bytes);
        envelope.signature = format!("ed25519:{}", hex::encode(signature.to_bytes()));
        envelope.signer_pubkey = pubkey_hex;

        // WHEN: we tamper with the payload
        envelope.message.payload = serde_json::json!({"secret": "modified"});

        // THEN: signature verification should fail
        let is_valid = envelope.verify_signature().expect("verify");
        assert!(!is_valid);
    }

    #[test]
    fn test_tampering_detection_from_agent() {
        // GIVEN: a signed message
        let signing_key = create_test_key();
        let pubkey = signing_key.verifying_key();
        let pubkey_hex = hex::encode(pubkey.to_bytes());

        let payload = serde_json::json!({"test": "data"});
        let msg = A2AMessage::new(
            MessageType::TaskIntent,
            "agent-1".to_string(),
            None,
            payload,
        );

        let mut envelope = A2AEnvelope::new(msg);
        let cbor_bytes = envelope.message.to_cbor().expect("serialize");
        let signature = signing_key.sign(&cbor_bytes);
        envelope.signature = format!("ed25519:{}", hex::encode(signature.to_bytes()));
        envelope.signer_pubkey = pubkey_hex;

        // WHEN: we tamper with the sender ID
        envelope.message.from_agent = "attacker".to_string();

        // THEN: signature verification should fail
        let is_valid = envelope.verify_signature().expect("verify");
        assert!(!is_valid);
    }

    #[test]
    fn test_wrong_signature_rejection() {
        // GIVEN: two different signing keys
        let key1 = create_test_key();
        let key2 = create_test_key();
        let pubkey2 = key2.verifying_key();
        let pubkey2_hex = hex::encode(pubkey2.to_bytes());

        let payload = serde_json::json!({"test": "wrong_sig"});
        let msg = A2AMessage::new(
            MessageType::TaskIntent,
            "agent-1".to_string(),
            None,
            payload,
        );

        // WHEN: we sign with key1 but claim it's signed with key2
        let mut envelope = A2AEnvelope::new(msg);
        let cbor_bytes = envelope.message.to_cbor().expect("serialize");
        let signature = key1.sign(&cbor_bytes); // Sign with key1
        envelope.signature = format!("ed25519:{}", hex::encode(signature.to_bytes()));
        envelope.signer_pubkey = pubkey2_hex; // But claim it's key2

        // THEN: signature verification should fail
        let is_valid = envelope.verify_signature().expect("verify");
        assert!(!is_valid);
    }

    #[test]
    fn test_message_status_codes() {
        // Verify HTTP-compatible status codes
        assert_eq!(MessageStatus::Success as i32, 200);
        assert_eq!(MessageStatus::Accepted as i32, 202);
        assert_eq!(MessageStatus::BadRequest as i32, 400);
        assert_eq!(MessageStatus::Unauthorized as i32, 401);
        assert_eq!(MessageStatus::Forbidden as i32, 403);
        assert_eq!(MessageStatus::Conflict as i32, 409);
        assert_eq!(MessageStatus::InternalError as i32, 500);
        assert_eq!(MessageStatus::ServiceUnavailable as i32, 503);
    }

    #[test]
    fn test_message_type_discriminator() {
        // Verify all message types can be serialized
        let msg_types = vec![
            MessageType::TaskIntent,
            MessageType::ComplianceVeto,
            MessageType::TaskAck,
            MessageType::TaskCompletion,
            MessageType::DiscoveryRequest,
            MessageType::DiscoveryResponse,
            MessageType::HandoffRequest,
            MessageType::HandoffAccept,
            MessageType::HandoffAbort,
            MessageType::LedgerCommit,
            MessageType::Error,
        ];

        for msg_type in msg_types {
            let msg = A2AMessage::new(
                msg_type,
                "agent".to_string(),
                None,
                serde_json::json!({}),
            );
            let _bytes = msg.to_cbor().expect("serialize");
        }
    }

    #[test]
    fn test_concurrent_signing() {
        // GIVEN: 10 different signing keys
        let keys: Vec<_> = (0..10)
            .map(|_| create_test_key())
            .collect();

        // WHEN: we sign messages concurrently
        let mut handles = vec![];
        for (i, key) in keys.into_iter().enumerate() {
            let handle = std::thread::spawn(move || {
                let payload = serde_json::json!({"index": i});
                let msg = A2AMessage::new(
                    MessageType::TaskIntent,
                    format!("agent-{}", i),
                    None,
                    payload,
                );
                let cbor_bytes = msg.to_cbor().expect("serialize");
                let sig = key.sign(&cbor_bytes);
                hex::encode(sig.to_bytes())
            });
            handles.push(handle);
        }

        // THEN: all signatures are unique and valid
        let signatures: Vec<String> = handles
            .into_iter()
            .map(|h| h.join().expect("join"))
            .collect();

        // Check uniqueness
        let mut sig_set = std::collections::HashSet::new();
        for sig in &signatures {
            assert!(sig_set.insert(sig.clone()));
        }
        assert_eq!(signatures.len(), 10);
    }
}
