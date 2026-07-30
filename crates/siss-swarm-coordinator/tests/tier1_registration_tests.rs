use siss_swarm_coordinator::SwarmCoordinator;
use uuid::Uuid;

#[test]
fn test_register_single_agent() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());
    let agent_id = Uuid::new_v4();

    let result = coordinator.register_agent(agent_id, [1u8; 32]);
    assert!(result.is_ok());
}

#[test]
fn test_register_multiple_agents() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());

    for i in 0..5 {
        let agent_id = Uuid::new_v4();
        let result = coordinator.register_agent(agent_id, [i as u8 + 1; 32]);
        assert!(result.is_ok());
    }
}

#[test]
fn test_duplicate_agent_registration_fails() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());
    let agent_id = Uuid::new_v4();

    coordinator.register_agent(agent_id, [1u8; 32]).unwrap();
    let result = coordinator.register_agent(agent_id, [2u8; 32]);

    assert!(result.is_err());
}

#[test]
fn test_get_registered_agent() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());
    let agent_id = Uuid::new_v4();

    coordinator.register_agent(agent_id, [42u8; 32]).unwrap();
    let agent = coordinator.get_agent(agent_id);

    assert!(agent.is_ok());
}

#[test]
fn test_get_unregistered_agent_fails() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());
    let agent_id = Uuid::new_v4();

    let result = coordinator.get_agent(agent_id);
    assert!(result.is_err());
}
