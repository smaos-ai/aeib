use uuid::Uuid;
use siss_swarm_coordinator::{SwarmCoordinator, A2AMessage};

#[test]
fn test_a2a_message_creation() {
    let from_agent_id = Uuid::new_v4();
    let to_agent_id = Uuid::new_v4();

    let msg = A2AMessage::new(
        from_agent_id,
        to_agent_id,
        "test payload".to_string(),
    );

    assert_eq!(msg.from_agent_id, from_agent_id);
    assert_eq!(msg.to_agent_id, to_agent_id);
    assert_eq!(msg.payload, "test payload");
    assert!(!msg.signature.is_empty());
}

#[test]
fn test_a2a_message_send_to_valid_peer() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());

    let from_agent_id = Uuid::new_v4();
    let to_agent_id = Uuid::new_v4();

    coordinator.register_agent(from_agent_id, [1u8; 32]).unwrap();
    coordinator.register_agent(to_agent_id, [2u8; 32]).unwrap();

    let msg = A2AMessage::new(
        from_agent_id,
        to_agent_id,
        "test message".to_string(),
    );

    let result = coordinator.send_message(msg);
    assert!(result.is_ok());
}

#[test]
fn test_a2a_message_send_to_invalid_peer() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());

    let from_agent_id = Uuid::new_v4();
    let to_agent_id = Uuid::new_v4();

    coordinator.register_agent(from_agent_id, [1u8; 32]).unwrap();
    // Don't register to_agent_id

    let msg = A2AMessage::new(
        from_agent_id,
        to_agent_id,
        "test message".to_string(),
    );

    let result = coordinator.send_message(msg);
    assert!(result.is_err());
}

#[test]
fn test_a2a_queue_bounded_1000() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());

    let from_agent_id = Uuid::new_v4();
    let to_agent_id = Uuid::new_v4();

    coordinator.register_agent(from_agent_id, [1u8; 32]).unwrap();
    coordinator.register_agent(to_agent_id, [2u8; 32]).unwrap();

    // Send 1100 messages (should auto-drop oldest when > 1000)
    for i in 0..1100 {
        let msg = A2AMessage::new(
            from_agent_id,
            to_agent_id,
            format!("message {}", i),
        );
        let _ = coordinator.send_message(msg);
    }

    // Queue should be bounded at 1000
    let queue_depth = coordinator.get_queue_depth(to_agent_id).unwrap();
    assert_eq!(queue_depth, 1000);
}

#[test]
fn test_a2a_message_process_fifo() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());

    let from_agent_id = Uuid::new_v4();
    let to_agent_id = Uuid::new_v4();

    coordinator.register_agent(from_agent_id, [1u8; 32]).unwrap();
    coordinator.register_agent(to_agent_id, [2u8; 32]).unwrap();

    // Send 3 messages
    for i in 0..3 {
        let msg = A2AMessage::new(
            from_agent_id,
            to_agent_id,
            format!("message {}", i),
        );
        coordinator.send_message(msg).unwrap();
    }

    // Process messages in order
    let msg1 = coordinator.process_message(to_agent_id).unwrap().unwrap();
    assert!(msg1.payload.contains("message 0"));

    let msg2 = coordinator.process_message(to_agent_id).unwrap().unwrap();
    assert!(msg2.payload.contains("message 1"));

    let msg3 = coordinator.process_message(to_agent_id).unwrap().unwrap();
    assert!(msg3.payload.contains("message 2"));
}

#[test]
fn test_a2a_signature_verification() {
    let from_agent_id = Uuid::new_v4();
    let to_agent_id = Uuid::new_v4();

    let msg = A2AMessage::new(
        from_agent_id,
        to_agent_id,
        "test payload".to_string(),
    );

    // Message should have a valid signature
    assert!(!msg.signature.is_empty());
    assert!(msg.verify_signature().is_ok());
}

#[test]
fn test_a2a_payload_preserves_context() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());

    let from_agent_id = Uuid::new_v4();
    let to_agent_id = Uuid::new_v4();

    coordinator.register_agent(from_agent_id, [1u8; 32]).unwrap();
    coordinator.register_agent(to_agent_id, [2u8; 32]).unwrap();

    let payload = "test context data";
    let msg = A2AMessage::new(
        from_agent_id,
        to_agent_id,
        payload.to_string(),
    );

    coordinator.send_message(msg).unwrap();

    let received = coordinator.process_message(to_agent_id).unwrap().unwrap();
    assert_eq!(received.payload, payload);
}
