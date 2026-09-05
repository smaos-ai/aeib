/// Track D: Unit Tests for Cryptographic Handoff & Task State Validation

#[cfg(test)]
mod handoff_validation_tests {
    use crate::handoff::{CryptographicHandoff, TaskState, TraceEntry};
    use crate::protocol::{A2AEnvelope, A2AMessage, MessageType};
    use chrono::Utc;
    use uuid::Uuid;

    #[test]
    fn test_task_state_creation() {
        // GIVEN: task state parameters
        let task_id = Uuid::new_v4().to_string();
        let intent = serde_json::json!({"action": "approve", "amount": 1000});

        // WHEN: we create a task state
        let state = TaskState::new(task_id.clone(), intent.clone());

        // THEN: state is properly initialized
        assert_eq!(state.task_id, task_id);
        assert_eq!(state.intent, intent);
        assert_eq!(state.trace.len(), 0);
        assert!(state.checkpoint.is_none());
    }

    #[test]
    fn test_task_state_serialization() {
        // GIVEN: a task state
        let intent = serde_json::json!({"test": "data"});
        let state = TaskState::new(Uuid::new_v4().to_string(), intent);

        // WHEN: we serialize and deserialize
        let bytes = state.to_bytes().expect("serialize");
        let restored = TaskState::from_bytes(&bytes).expect("deserialize");

        // THEN: state is preserved
        assert_eq!(restored.task_id, state.task_id);
        assert_eq!(restored.intent, state.intent);
    }

    #[test]
    fn test_task_state_digest_consistency() {
        // GIVEN: identical task states
        let intent = serde_json::json!({"amount": 5000});
        let state1 = TaskState::new("task-1".to_string(), intent.clone());
        let state2 = TaskState::new("task-1".to_string(), intent);

        // WHEN: we compute content digests (excludes timestamp)
        let digest1 = state1.content_digest().expect("digest1");
        let digest2 = state2.content_digest().expect("digest2");

        // THEN: digests are identical
        assert_eq!(digest1, digest2);
    }

    #[test]
    fn test_task_state_digest_uniqueness() {
        // GIVEN: different task states
        let state1 = TaskState::new("task-1".to_string(), serde_json::json!({"amount": 1000}));
        let state2 = TaskState::new("task-2".to_string(), serde_json::json!({"amount": 1000}));

        // WHEN: we compute digests
        let digest1 = state1.digest().expect("digest1");
        let digest2 = state2.digest().expect("digest2");

        // THEN: digests are different
        assert_ne!(digest1, digest2);
    }

    #[test]
    fn test_trace_entry_creation() {
        // GIVEN: trace entry parameters
        let agent = "agent-1".to_string();
        let action = "evaluate".to_string();
        let result = "approved".to_string();

        // WHEN: we create a trace entry
        let entry = TraceEntry::new(agent.clone(), action.clone(), result.clone());

        // THEN: entry is properly initialized
        assert_eq!(entry.agent, agent);
        assert_eq!(entry.action, action);
        assert_eq!(entry.result, result);
        assert!(!entry.id.is_empty());
    }

    #[test]
    fn test_task_state_trace_building() {
        // GIVEN: a task state and multiple trace entries
        let mut state = TaskState::new(Uuid::new_v4().to_string(), serde_json::json!({}));
        let entry1 = TraceEntry::new("agent-1".to_string(), "plan".to_string(), "success".to_string());
        let entry2 = TraceEntry::new("agent-2".to_string(), "evaluate".to_string(), "veto".to_string());

        // WHEN: we add trace entries
        state.add_trace(entry1);
        state.add_trace(entry2);

        // THEN: trace is preserved
        assert_eq!(state.trace.len(), 2);
        assert_eq!(state.trace[0].agent, "agent-1");
        assert_eq!(state.trace[1].agent, "agent-2");
    }

    #[test]
    fn test_cryptographic_handoff_creation() {
        // GIVEN: a handoff manager
        let handoff = CryptographicHandoff::new("agent-1".to_string()).expect("create");

        // THEN: manager has valid public key
        let pubkey = handoff.public_key();
        assert!(!pubkey.is_empty());
        assert_eq!(pubkey.len(), 64); // 32 bytes = 64 hex chars
    }

    #[test]
    fn test_envelope_signing() {
        // GIVEN: a handoff manager and envelope
        let handoff = CryptographicHandoff::new("agent-1".to_string()).expect("create");
        let msg = A2AMessage::new(
            MessageType::HandoffRequest,
            "agent-1".to_string(),
            Some("agent-2".to_string()),
            serde_json::json!({"test": "payload"}),
        );

        // WHEN: we sign the envelope
        let envelope = A2AEnvelope::new(msg);
        let signed = handoff.sign_envelope(envelope).expect("sign");

        // THEN: signature is present and valid
        assert!(signed.signature.starts_with("ed25519:"));
        assert!(!signed.signer_pubkey.is_empty());
        assert_eq!(signed.signer_pubkey, handoff.public_key());
    }

    #[test]
    fn test_envelope_signature_verification() {
        // GIVEN: a signed envelope
        let handoff = CryptographicHandoff::new("agent-1".to_string()).expect("create");
        let msg = A2AMessage::new(
            MessageType::HandoffRequest,
            "agent-1".to_string(),
            Some("agent-2".to_string()),
            serde_json::json!({"test": "payload"}),
        );

        let envelope = A2AEnvelope::new(msg);
        let signed = handoff.sign_envelope(envelope).expect("sign");

        // WHEN: we verify the signature
        let is_valid = handoff.verify_envelope(&signed).expect("verify");

        // THEN: signature is valid
        assert!(is_valid);
    }

    #[test]
    fn test_handoff_request_preparation() {
        // GIVEN: a handoff manager and task state
        let handoff = CryptographicHandoff::new("agent-1".to_string()).expect("create");
        let task_state = TaskState::new(Uuid::new_v4().to_string(), serde_json::json!({"test": "state"}));

        // WHEN: we prepare handoff
        let envelope = handoff
            .prepare_handoff("agent-2".to_string(), task_state)
            .expect("prepare");

        // THEN: envelope is properly formatted and signed
        assert_eq!(envelope.message.msg_type, MessageType::HandoffRequest);
        assert!(envelope.signature.starts_with("ed25519:"));
        assert!(envelope.verify_signature().expect("verify"));
    }

    #[test]
    fn test_handoff_acceptance() {
        // GIVEN: a handoff manager
        let handoff = CryptographicHandoff::new("agent-2".to_string()).expect("create");

        // WHEN: we generate acceptance
        let envelope = handoff
            .accept_handoff("agent-1".to_string(), "task-123".to_string())
            .expect("accept");

        // THEN: acceptance message is signed
        assert_eq!(envelope.message.msg_type, MessageType::HandoffAccept);
        assert!(envelope.verify_signature().expect("verify"));
        assert_eq!(
            envelope.message.to_agent,
            Some("agent-1".to_string())
        );
    }

    #[test]
    fn test_handoff_rejection() {
        // GIVEN: a handoff manager
        let handoff = CryptographicHandoff::new("agent-2".to_string()).expect("create");

        // WHEN: we generate rejection
        let envelope = handoff
            .reject_handoff(
                "agent-1".to_string(),
                "task-123".to_string(),
                "resource unavailable".to_string(),
            )
            .expect("reject");

        // THEN: rejection message is signed
        assert_eq!(envelope.message.msg_type, MessageType::HandoffAbort);
        assert!(envelope.verify_signature().expect("verify"));
        assert_eq!(
            envelope.message.to_agent,
            Some("agent-1".to_string())
        );
    }

    #[test]
    fn test_multi_agent_key_uniqueness() {
        // GIVEN: multiple handoff managers
        let handoff1 = CryptographicHandoff::new("agent-1".to_string()).expect("create");
        let handoff2 = CryptographicHandoff::new("agent-2".to_string()).expect("create");
        let handoff3 = CryptographicHandoff::new("agent-3".to_string()).expect("create");

        // WHEN: we get their public keys
        let key1 = handoff1.public_key();
        let key2 = handoff2.public_key();
        let key3 = handoff3.public_key();

        // THEN: keys are all unique
        assert_ne!(key1, key2);
        assert_ne!(key2, key3);
        assert_ne!(key1, key3);
    }

    #[test]
    fn test_concurrent_handoff_preparation() {
        // GIVEN: 10 handoff managers
        let handoffs: Vec<_> = (0..10)
            .map(|i| CryptographicHandoff::new(format!("agent-{}", i)).expect("create"))
            .collect();

        // WHEN: we prepare handoffs concurrently
        let mut handles = vec![];
        for (i, handoff) in handoffs.into_iter().enumerate() {
            let handle = std::thread::spawn(move || {
                let task_state = TaskState::new(
                    format!("task-{}", i),
                    serde_json::json!({"index": i}),
                );
                handoff
                    .prepare_handoff(format!("target-{}", i), task_state)
                    .expect("prepare")
            });
            handles.push(handle);
        }

        // THEN: all handoffs succeed
        let envelopes: Vec<_> = handles
            .into_iter()
            .map(|h| h.join().expect("join"))
            .collect();

        assert_eq!(envelopes.len(), 10);
        for envelope in envelopes {
            assert!(envelope.verify_signature().expect("verify"));
        }
    }

    #[test]
    fn test_handoff_state_preservation() {
        // GIVEN: a task state with trace and checkpoint
        let mut state = TaskState::new(
            Uuid::new_v4().to_string(),
            serde_json::json!({"intent": "test"}),
        );
        state.add_trace(TraceEntry::new(
            "agent-1".to_string(),
            "plan".to_string(),
            "success".to_string(),
        ));
        state.checkpoint = Some("checkpoint-1".to_string());

        // WHEN: we serialize
        let bytes = state.to_bytes().expect("serialize");
        let restored = TaskState::from_bytes(&bytes).expect("deserialize");

        // THEN: all state is preserved
        assert_eq!(restored.trace.len(), 1);
        assert_eq!(restored.checkpoint, Some("checkpoint-1".to_string()));
    }
}
