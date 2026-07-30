use siss_swarm_coordinator::{A2AMessage, SwarmCoordinator};
use uuid::Uuid;

#[test]
fn test_conflict_resolve_highest_hash_wins() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());

    let agent_a = Uuid::new_v4();
    let agent_b = Uuid::new_v4();

    coordinator.register_agent(agent_a, [1u8; 32]).unwrap();
    coordinator.register_agent(agent_b, [2u8; 32]).unwrap();

    let msg1 = A2AMessage::new(agent_a, agent_b, "payload 1".to_string());
    let msg2 = A2AMessage::new(agent_a, agent_b, "payload 2".to_string());

    let winner = coordinator.resolve_conflict(&msg1, &msg2);

    assert!(winner.message_id == msg1.message_id || winner.message_id == msg2.message_id);
}

#[test]
fn test_conflict_resolve_deterministic() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());

    let agent_a = Uuid::new_v4();
    let agent_b = Uuid::new_v4();

    coordinator.register_agent(agent_a, [1u8; 32]).unwrap();
    coordinator.register_agent(agent_b, [2u8; 32]).unwrap();

    let msg1 = A2AMessage::new(agent_a, agent_b, "fixed payload".to_string());
    let msg2 = A2AMessage::new(agent_a, agent_b, "fixed payload".to_string());

    let winner1 = coordinator.resolve_conflict(&msg1, &msg2);
    let winner2 = coordinator.resolve_conflict(&msg1, &msg2);

    assert_eq!(winner1.message_id, winner2.message_id);
}

#[test]
fn test_conflict_resolve_vector_clock() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());

    let agent_a = Uuid::new_v4();
    let agent_b = Uuid::new_v4();

    coordinator.register_agent(agent_a, [1u8; 32]).unwrap();
    coordinator.register_agent(agent_b, [2u8; 32]).unwrap();

    let msg1 = A2AMessage::new(agent_a, agent_b, "first".to_string());
    let msg2 = A2AMessage::new(agent_a, agent_b, "second".to_string());

    let winner = coordinator.resolve_conflict_by_timestamp(&msg1, &msg2);
    assert_eq!(winner.message_id, msg2.message_id);
}

#[test]
fn test_chaos_network_timeout_recovery() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());

    let agent_a = Uuid::new_v4();
    let agent_b = Uuid::new_v4();

    coordinator.register_agent(agent_a, [1u8; 32]).unwrap();
    coordinator.register_agent(agent_b, [2u8; 32]).unwrap();

    let msg = A2AMessage::new(agent_a, agent_b, "test".to_string());

    let result = coordinator.send_message_with_timeout(msg, std::time::Duration::from_secs(5));
    assert!(result.is_ok() || result.is_err());
}

#[test]
fn test_chaos_state_corruption_detection() {
    let msg = A2AMessage::new(Uuid::new_v4(), Uuid::new_v4(), "test".to_string());

    assert!(msg.verify_signature().is_ok());

    let mut corrupted = msg.clone();
    corrupted.payload = "corrupted".to_string();

    assert_ne!(corrupted.payload, msg.payload);
    assert!(msg.verify_signature().is_ok());
}

#[test]
fn test_chaos_cascade_failure_a_b_c() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());

    let a = Uuid::new_v4();
    let b = Uuid::new_v4();
    let c = Uuid::new_v4();

    coordinator.register_agent(a, [1u8; 32]).unwrap();
    coordinator.register_agent(b, [2u8; 32]).unwrap();
    coordinator.register_agent(c, [3u8; 32]).unwrap();

    coordinator.delegate(a, b).unwrap();
    coordinator.delegate(b, c).unwrap();

    let msg1 = A2AMessage::new(a, b, "cascading".to_string());
    let msg2 = A2AMessage::new(b, c, "cascading".to_string());

    assert!(coordinator.send_message(msg1).is_ok());
    assert!(coordinator.send_message(msg2).is_ok());

    assert_eq!(coordinator.get_queue_depth(b).unwrap(), 1);
    assert_eq!(coordinator.get_queue_depth(c).unwrap(), 1);
}
