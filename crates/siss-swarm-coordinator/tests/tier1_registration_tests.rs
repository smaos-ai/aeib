use uuid::Uuid;
use siss_swarm_coordinator::{SwarmCoordinator, MongeGapBound};

#[test]
fn test_swarm_coordinator_new() {
    let agent_id = Uuid::new_v4();
    let coordinator = SwarmCoordinator::new(agent_id);
    assert_eq!(coordinator.local_agent_id(), agent_id);
}

#[test]
fn test_agent_registration_valid() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());
    let agent_id = Uuid::new_v4();
    let public_key = [1u8; 32];

    let result = coordinator.register_agent(agent_id, public_key);
    assert!(result.is_ok());

    let metadata = coordinator.get_agent(agent_id).unwrap();
    assert_eq!(metadata.agent_id, agent_id);
    assert_eq!(metadata.public_key, public_key);
}

#[test]
fn test_agent_registration_duplicate_id() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());
    let agent_id = Uuid::new_v4();
    let public_key = [1u8; 32];

    coordinator.register_agent(agent_id, public_key).unwrap();
    let result = coordinator.register_agent(agent_id, public_key);
    assert!(result.is_err());
}

#[test]
fn test_monge_bound_initialization() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());
    let agent_id = Uuid::new_v4();
    let public_key = [1u8; 32];

    coordinator.register_agent(agent_id, public_key).unwrap();
    let bound = coordinator.get_bounds(agent_id).unwrap();

    assert_eq!(bound.current_depth, 0);
    assert_eq!(bound.delegation_count, 0);
    assert_eq!(bound.parent_hash, [0u8; 32]);
}

#[test]
fn test_monge_bound_is_within_bounds() {
    let bound = MongeGapBound::new(Uuid::new_v4());
    assert!(bound.is_within_bounds());
    assert_eq!(bound.max_depth, 3);
    assert_eq!(bound.max_agents, 5);
}
