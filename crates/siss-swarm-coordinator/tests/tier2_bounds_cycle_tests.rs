use uuid::Uuid;
use siss_swarm_coordinator::SwarmCoordinator;

#[test]
fn test_monge_gap_depth_limit_3() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());

    let a_id = Uuid::new_v4();
    let b_id = Uuid::new_v4();
    let c_id = Uuid::new_v4();
    let d_id = Uuid::new_v4();

    coordinator.register_agent(a_id, [1u8; 32]).unwrap();
    coordinator.register_agent(b_id, [2u8; 32]).unwrap();
    coordinator.register_agent(c_id, [3u8; 32]).unwrap();
    coordinator.register_agent(d_id, [4u8; 32]).unwrap();

    // A delegates to B (depth 1)
    coordinator.delegate(a_id, b_id).unwrap();

    // B delegates to C (depth 2)
    coordinator.delegate(b_id, c_id).unwrap();

    // C delegates to D (depth 3, max allowed)
    let result_depth_3 = coordinator.delegate(c_id, d_id);
    assert!(result_depth_3.is_ok());

    // Try to delegate from D (would be depth 4, should fail)
    let e_id = Uuid::new_v4();
    coordinator.register_agent(e_id, [5u8; 32]).unwrap();
    let result_depth_4 = coordinator.delegate(d_id, e_id);
    assert!(result_depth_4.is_err());
}

#[test]
fn test_monge_gap_agent_limit_5() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());

    let a_id = Uuid::new_v4();
    coordinator.register_agent(a_id, [1u8; 32]).unwrap();

    // Register 5 agents to delegate to
    for i in 0..5 {
        let agent_id = Uuid::new_v4();
        coordinator.register_agent(agent_id, [i as u8 + 2; 32]).unwrap();
        let result = coordinator.delegate(a_id, agent_id);
        assert!(result.is_ok(), "Agent {} delegation should succeed", i);
    }

    // Try to delegate to 6th agent (should fail)
    let sixth_agent_id = Uuid::new_v4();
    coordinator.register_agent(sixth_agent_id, [7u8; 32]).unwrap();
    let result = coordinator.delegate(a_id, sixth_agent_id);
    assert!(result.is_err(), "6th delegation should fail");
}

#[test]
fn test_cycle_detection_self_reference() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());
    let agent_id = Uuid::new_v4();

    coordinator.register_agent(agent_id, [1u8; 32]).unwrap();

    // Agent cannot delegate to itself
    let result = coordinator.delegate(agent_id, agent_id);
    assert!(result.is_err());
}

#[test]
fn test_cycle_detection_chain_a_b_c() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());

    let a_id = Uuid::new_v4();
    let b_id = Uuid::new_v4();
    let c_id = Uuid::new_v4();

    coordinator.register_agent(a_id, [1u8; 32]).unwrap();
    coordinator.register_agent(b_id, [2u8; 32]).unwrap();
    coordinator.register_agent(c_id, [3u8; 32]).unwrap();

    // A → B → C → A (cycle)
    coordinator.delegate(a_id, b_id).unwrap();
    coordinator.delegate(b_id, c_id).unwrap();

    // Trying to create C → A should fail (would create cycle)
    let result = coordinator.delegate(c_id, a_id);
    assert!(result.is_err());
}

#[test]
fn test_cycle_detection_depth_3_max() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());

    let a_id = Uuid::new_v4();
    let b_id = Uuid::new_v4();
    let c_id = Uuid::new_v4();

    coordinator.register_agent(a_id, [1u8; 32]).unwrap();
    coordinator.register_agent(b_id, [2u8; 32]).unwrap();
    coordinator.register_agent(c_id, [3u8; 32]).unwrap();

    // A → B → C is depth 2, should work
    coordinator.delegate(a_id, b_id).unwrap();
    let result = coordinator.delegate(b_id, c_id);
    assert!(result.is_ok());
}

#[test]
fn test_cycle_detection_depth_4_forbidden() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());

    let agents: Vec<_> = (0..4).map(|_| Uuid::new_v4()).collect();
    for (i, agent_id) in agents.iter().enumerate() {
        coordinator.register_agent(*agent_id, [i as u8 + 1; 32]).unwrap();
    }

    // A → B → C (depth 2, ok)
    coordinator.delegate(agents[0], agents[1]).unwrap();
    coordinator.delegate(agents[1], agents[2]).unwrap();

    // C → D (depth 3, ok)
    coordinator.delegate(agents[2], agents[3]).unwrap();

    // Try D → A (would be depth 4, should fail)
    let result = coordinator.delegate(agents[3], agents[0]);
    assert!(result.is_err());
}
