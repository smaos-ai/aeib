use uuid::Uuid;
use siss_swarm_coordinator::SwarmCoordinator;

#[test]
fn test_delegate_successful() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());
    let agent_a = Uuid::new_v4();
    let agent_b = Uuid::new_v4();
    
    coordinator.register_agent(agent_a, [1u8; 32]).unwrap();
    coordinator.register_agent(agent_b, [2u8; 32]).unwrap();
    
    let result = coordinator.delegate(agent_a, agent_b);
    assert!(result.is_ok());
}

#[test]
fn test_self_delegation_fails() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());
    let agent_id = Uuid::new_v4();
    
    coordinator.register_agent(agent_id, [1u8; 32]).unwrap();
    let result = coordinator.delegate(agent_id, agent_id);
    
    assert!(result.is_err());
}

#[test]
fn test_cycle_detection_a_to_b_to_a() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());
    let agent_a = Uuid::new_v4();
    let agent_b = Uuid::new_v4();
    
    coordinator.register_agent(agent_a, [1u8; 32]).unwrap();
    coordinator.register_agent(agent_b, [2u8; 32]).unwrap();
    
    coordinator.delegate(agent_a, agent_b).unwrap();
    let result = coordinator.delegate(agent_b, agent_a);
    
    assert!(result.is_err());
}

#[test]
fn test_depth_limit_enforced() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());
    let agents: Vec<_> = (0..5).map(|i| {
        let agent_id = Uuid::new_v4();
        coordinator.register_agent(agent_id, [i as u8 + 1; 32]).unwrap();
        agent_id
    }).collect();
    
    // Chain: 0 → 1 → 2 → 3 → 4 (depth would be 4, exceeds limit of 3)
    coordinator.delegate(agents[0], agents[1]).unwrap();
    coordinator.delegate(agents[1], agents[2]).unwrap();
    coordinator.delegate(agents[2], agents[3]).unwrap();
    let result = coordinator.delegate(agents[3], agents[4]);
    
    assert!(result.is_err());
}

#[test]
fn test_max_delegation_count_enforced() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());
    let agent_0 = Uuid::new_v4();
    let agents: Vec<_> = (0..6).map(|i| {
        let agent_id = Uuid::new_v4();
        coordinator.register_agent(agent_id, [i as u8 + 1; 32]).unwrap();
        agent_id
    }).collect();
    
    coordinator.register_agent(agent_0, [0u8; 32]).unwrap();
    
    // Delegate to 5 agents (should succeed)
    for i in 0..5 {
        let result = coordinator.delegate(agent_0, agents[i]);
        assert!(result.is_ok(), "Delegation {}->{} should succeed", 0, i);
    }
    
    // Try 6th delegation (should fail, limit is 5)
    let result = coordinator.delegate(agent_0, agents[5]);
    assert!(result.is_err());
}

#[test]
fn test_get_bounds_returns_monge_info() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());
    let agent_id = Uuid::new_v4();
    
    coordinator.register_agent(agent_id, [1u8; 32]).unwrap();
    let bounds = coordinator.get_bounds(agent_id);
    
    assert!(bounds.is_ok());
}
