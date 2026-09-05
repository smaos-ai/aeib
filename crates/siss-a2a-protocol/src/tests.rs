/// Phase 2B Part 2 Testing Scaffolding
///
/// Test Categories:
/// 1. Protocol Conformance (200 LOC)
/// 2. Handoff Stress (100 LOC)
/// 3. Cryptographic Verification (100 LOC)

#[cfg(test)]
mod protocol_conformance {
    use crate::protocol::{A2AMessage, A2AEnvelope, MessageType, MessageStatus};
    use crate::handoff::CryptographicHandoff;
    use crate::discovery::{PeerDiscovery, PeerManifest, PeerCapability};
    use chrono::Utc;

    #[test]
    fn test_message_creation_and_serialization() {
        let payload = serde_json::json!({"intent": "classify_hotel"});
        let msg = A2AMessage::new(
            MessageType::TaskIntent,
            "planner-1".to_string(),
            Some("compliance-1".to_string()),
            payload,
        );

        assert_eq!(msg.msg_type, MessageType::TaskIntent);
        assert_eq!(msg.status, MessageStatus::Success);

        let bytes = msg.to_cbor().expect("serialize");
        let restored = A2AMessage::from_cbor(&bytes).expect("deserialize");
        assert_eq!(restored.from_agent, "planner-1");
    }

    #[test]
    fn test_envelope_lifecycle() {
        let payload = serde_json::json!({"test": "data"});
        let msg = A2AMessage::new(
            MessageType::DiscoveryRequest,
            "agent-a".to_string(),
            Some("agent-b".to_string()),
            payload,
        );

        let envelope = A2AEnvelope::new(msg);
        assert!(envelope.signature.is_empty()); // Unsigned

        let bytes = envelope.to_bytes().expect("serialize");
        let restored = A2AEnvelope::from_bytes(&bytes).expect("deserialize");
        assert_eq!(restored.message.from_agent, "agent-a");
    }

    #[test]
    fn test_peer_capability_discovery() {
        use crate::integration::AgentRegistry;
        let registry = std::sync::Arc::new(AgentRegistry::new());
        let mut discovery = PeerDiscovery::new(registry);

        let manifest = PeerManifest {
            agent_id: "compliance-1".to_string(),
            uri: "http://localhost:9001".to_string(),
            pubkey: "key1234567890abcdef".to_string(),
            capabilities: vec![
                PeerCapability {
                    name: "veto".to_string(),
                    version: "1.0".to_string(),
                    available: true,
                },
                PeerCapability {
                    name: "classify".to_string(),
                    version: "2.0".to_string(),
                    available: false, // Unavailable
                },
            ],
            updated_at: Utc::now(),
            ttl_secs: 3600,
            cert_chain: None,
        };

        discovery.cache_peer(manifest);
        let peers = discovery.discover_by_capability("veto");
        assert_eq!(peers.len(), 1);
        assert_eq!(peers[0].agent_id, "compliance-1");

        // Classify should not be discovered (unavailable)
        let classify_peers = discovery.discover_by_capability("classify");
        assert!(classify_peers.is_empty());
    }

    #[test]
    fn test_message_status_codes() {
        assert_eq!(MessageStatus::Success as i32, 200);
        assert_eq!(MessageStatus::Accepted as i32, 202);
        assert_eq!(MessageStatus::BadRequest as i32, 400);
        assert_eq!(MessageStatus::Unauthorized as i32, 401);
        assert_eq!(MessageStatus::Forbidden as i32, 403);
        assert_eq!(MessageStatus::Conflict as i32, 409);
        assert_eq!(MessageStatus::InternalError as i32, 500);
        assert_eq!(MessageStatus::ServiceUnavailable as i32, 503);
    }
}

#[cfg(test)]
mod cryptographic_verification {
    use crate::protocol::{A2AMessage, A2AEnvelope, MessageType};
    use crate::handoff::CryptographicHandoff;

    #[test]
    fn test_signature_generation_and_verification() {
        let handoff = CryptographicHandoff::new("agent-1".to_string()).expect("create");
        let pubkey = handoff.public_key();
        assert_eq!(pubkey.len(), 64); // 32 bytes hex

        let payload = serde_json::json!({"task": "test"});
        let msg = A2AMessage::new(
            MessageType::TaskIntent,
            "agent-1".to_string(),
            Some("agent-2".to_string()),
            payload,
        );

        let envelope = A2AEnvelope::new(msg);
        let signed = handoff.sign_envelope(envelope).expect("sign");

        assert!(signed.signature.starts_with("ed25519:"));
        assert_eq!(signed.signer_pubkey, pubkey);
        assert!(signed.verify_signature().expect("verify"));
    }

    #[test]
    fn test_signature_tampering_detection() {
        let handoff = CryptographicHandoff::new("agent-1".to_string()).expect("create");

        let payload = serde_json::json!({"secret": "data"});
        let msg = A2AMessage::new(
            MessageType::TaskIntent,
            "agent-1".to_string(),
            None,
            payload,
        );

        let envelope = A2AEnvelope::new(msg);
        let mut signed = handoff.sign_envelope(envelope).expect("sign");

        // Tamper with payload
        signed.message.payload = serde_json::json!({"secret": "modified"});

        // Signature verification should fail
        assert!(!signed.verify_signature().expect("verify"));
    }

    #[test]
    fn test_handoff_acceptance_signature() {
        let handoff = CryptographicHandoff::new("agent-2".to_string()).expect("create");

        let accept_envelope = handoff
            .accept_handoff("agent-1".to_string(), "task-123".to_string())
            .expect("accept");

        assert_eq!(
            accept_envelope.message.msg_type,
            crate::protocol::MessageType::HandoffAccept
        );
        assert!(accept_envelope.verify_signature().expect("verify"));
    }

    #[test]
    fn test_handoff_rejection_signature() {
        let handoff = CryptographicHandoff::new("agent-2".to_string()).expect("create");

        let reject_envelope = handoff
            .reject_handoff(
                "agent-1".to_string(),
                "task-123".to_string(),
                "resource unavailable".to_string(),
            )
            .expect("reject");

        assert_eq!(
            reject_envelope.message.msg_type,
            crate::protocol::MessageType::HandoffAbort
        );
        assert!(reject_envelope.verify_signature().expect("verify"));
    }
}

#[cfg(test)]
mod handoff_stress {
    use crate::handoff::{CryptographicHandoff, TaskState};
    use std::sync::Arc;
    use std::sync::atomic::{AtomicUsize, Ordering};

    #[test]
    fn test_concurrent_handoff_preparation() {
        // Stress test: 10 concurrent handoffs from different agents
        let handoff_count = Arc::new(AtomicUsize::new(0));

        let mut handles = vec![];

        for i in 0..10 {
            let count = Arc::clone(&handoff_count);
            let handle = std::thread::spawn(move || {
                let handoff = CryptographicHandoff::new(format!("agent-{}", i)).expect("create");
                let task_state =
                    TaskState::new(format!("task-{}", i), serde_json::json!({}));

                let _envelope = handoff
                    .prepare_handoff(format!("agent-{}", (i + 1) % 10), task_state)
                    .expect("prepare");

                count.fetch_add(1, Ordering::SeqCst);
            });
            handles.push(handle);
        }

        for handle in handles {
            handle.join().expect("join");
        }

        assert_eq!(handoff_count.load(Ordering::SeqCst), 10);
    }

    #[test]
    fn test_task_state_digest_consistency() {
        let intent = serde_json::json!({"amount": 1000000, "currency": "CZK"});
        let state1 = TaskState::new("task-1".to_string(), intent.clone());
        let state2 = TaskState::new("task-1".to_string(), intent);

        let digest1 = state1.content_digest().expect("digest");
        let digest2 = state2.content_digest().expect("digest");

        // Same task state should produce same content digest
        assert_eq!(digest1, digest2);
    }

    #[test]
    fn test_multiple_agent_key_pairs() {
        // Verify that different agents have different keys
        let mut keys = vec![];

        for i in 0..5 {
            let handoff =
                CryptographicHandoff::new(format!("agent-{}", i)).expect("create");
            keys.push(handoff.public_key());
        }

        // All keys should be unique
        for i in 0..keys.len() {
            for j in (i + 1)..keys.len() {
                assert_ne!(keys[i], keys[j]);
            }
        }
    }
}

#[cfg(test)]
mod ledger_anchoring {
    use crate::ledger::{JointLedger, LedgerEntry, LedgerAnchor};

    #[test]
    fn test_ledger_append_and_chain_integrity() {
        let mut ledger = JointLedger::new();

        for i in 0..5 {
            let entry = LedgerEntry::new(
                format!("msg-{}", i),
                "agent-a".to_string(),
                "agent-b".to_string(),
                format!("digest-{}", i),
            );
            ledger.append(entry);
        }

        assert_eq!(ledger.len(), 5);
        assert!(ledger.verify_integrity());
    }

    #[test]
    fn test_ledger_anchor_creation() {
        let mut anchor = LedgerAnchor::new(
            "abc123def456".to_string(),
            "merkle_root_xyz".to_string(),
            42,
        );

        assert!(!anchor.is_valid()); // No signature

        anchor.sign("sig_xyz".to_string());
        assert!(anchor.is_valid());

        let bytes = anchor.to_bytes().expect("serialize");
        let restored = LedgerAnchor::from_bytes(&bytes).expect("deserialize");
        assert_eq!(restored.entry_count, 42);
    }
}
