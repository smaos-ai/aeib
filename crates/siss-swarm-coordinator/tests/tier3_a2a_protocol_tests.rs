use uuid::Uuid;
use siss_swarm_coordinator::{SwarmCoordinator, A2AMessage};

#[test]
fn test_create_a2a_message() {
    let from_id = Uuid::new_v4();
    let to_id = Uuid::new_v4();
    let msg = A2AMessage::new(from_id, to_id, "test payload".to_string());
    
    assert_eq!(msg.from_agent_id, from_id);
    assert_eq!(msg.to_agent_id, to_id);
    assert_eq!(msg.payload, "test payload");
}

#[test]
fn test_message_has_merkle_hash() {
    let msg = A2AMessage::new(Uuid::new_v4(), Uuid::new_v4(), "test".to_string());
    assert_eq!(msg.merkle_hash.len(), 32);
}

#[test]
fn test_send_message_to_registered_agent() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());
    let agent_a = Uuid::new_v4();
    let agent_b = Uuid::new_v4();
    
    coordinator.register_agent(agent_a, [1u8; 32]).unwrap();
    coordinator.register_agent(agent_b, [2u8; 32]).unwrap();
    
    let msg = A2AMessage::new(agent_a, agent_b, "hello".to_string());
    let result = coordinator.send_message(msg);
    
    assert!(result.is_ok());
}

#[test]
fn test_send_message_from_unregistered_sender_fails() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());
    let agent_b = Uuid::new_v4();
    
    coordinator.register_agent(agent_b, [2u8; 32]).unwrap();
    
    let msg = A2AMessage::new(Uuid::new_v4(), agent_b, "hello".to_string());
    let result = coordinator.send_message(msg);
    
    assert!(result.is_err());
}

#[test]
fn test_send_message_to_unregistered_recipient_fails() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());
    let agent_a = Uuid::new_v4();
    
    coordinator.register_agent(agent_a, [1u8; 32]).unwrap();
    
    let msg = A2AMessage::new(agent_a, Uuid::new_v4(), "hello".to_string());
    let result = coordinator.send_message(msg);
    
    assert!(result.is_err());
}

#[test]
fn test_process_message_dequeues_first() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());
    let agent_a = Uuid::new_v4();
    let agent_b = Uuid::new_v4();
    
    coordinator.register_agent(agent_a, [1u8; 32]).unwrap();
    coordinator.register_agent(agent_b, [2u8; 32]).unwrap();
    
    let msg = A2AMessage::new(agent_a, agent_b, "test".to_string());
    coordinator.send_message(msg).unwrap();
    
    let received = coordinator.process_message(agent_b).unwrap();
    assert!(received.is_some());
    assert_eq!(received.unwrap().payload, "test");
}

#[test]
fn test_process_message_returns_none_when_empty() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());
    let agent_id = Uuid::new_v4();
    
    coordinator.register_agent(agent_id, [1u8; 32]).unwrap();
    let result = coordinator.process_message(agent_id).unwrap();
    
    assert!(result.is_none());
}
