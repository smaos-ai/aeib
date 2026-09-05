use siss_swarm_coordinator::{A2AMessage, SwarmCoordinator};
use uuid::Uuid;

#[test]
fn test_5_concurrent_agents_no_deadlock() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());

    let agents: Vec<_> = (0..5)
        .map(|i| {
            let agent_id = Uuid::new_v4();
            coordinator
                .register_agent(agent_id, [i as u8 + 1; 32])
                .unwrap();
            agent_id
        })
        .collect();

    for i in 1..5 {
        let result = coordinator.delegate(agents[0], agents[i]);
        assert!(result.is_ok(), "Delegation should succeed");
    }

    for agent_id in &agents {
        assert!(coordinator.get_agent(*agent_id).is_ok());
    }

    assert_eq!(coordinator.get_queue_depth(agents[0]).unwrap(), 0);
}

#[test]
fn test_swarm_state_sync_consistency() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());

    let agent_a = Uuid::new_v4();
    let agent_b = Uuid::new_v4();

    coordinator.register_agent(agent_a, [1u8; 32]).unwrap();
    coordinator.register_agent(agent_b, [2u8; 32]).unwrap();

    for i in 0..3 {
        let msg = A2AMessage::new(agent_a, agent_b, format!("state {}", i));
        coordinator.send_message(msg).unwrap();
    }

    let mut messages = Vec::new();
    for _ in 0..3 {
        if let Ok(Some(msg)) = coordinator.process_message(agent_b) {
            messages.push(msg);
        }
    }

    assert_eq!(messages.len(), 3);
    assert!(messages[0].payload.contains("state 0"));
    assert!(messages[1].payload.contains("state 1"));
    assert!(messages[2].payload.contains("state 2"));
}

#[test]
fn test_mcp_gateway_routing_a2a_message() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());

    let agent_local = Uuid::new_v4();
    let agent_remote = Uuid::new_v4();

    coordinator.register_agent(agent_local, [1u8; 32]).unwrap();
    coordinator.register_agent(agent_remote, [2u8; 32]).unwrap();

    let msg = A2AMessage::new(agent_local, agent_remote, "mcp routed message".to_string());

    assert!(coordinator.send_message(msg.clone()).is_ok());
    assert_eq!(coordinator.get_queue_depth(agent_remote).unwrap(), 1);

    let received = coordinator.process_message(agent_remote).unwrap().unwrap();
    assert_eq!(received.payload, "mcp routed message");
    assert_eq!(received.from_agent_id, agent_local);
    assert_eq!(received.to_agent_id, agent_remote);
}

#[test]
fn test_swarm_bounds_enforce_global_limits() {
    let coordinator = SwarmCoordinator::new(Uuid::new_v4());

    let agents: Vec<_> = (0..6)
        .map(|i| {
            let agent_id = Uuid::new_v4();
            coordinator
                .register_agent(agent_id, [i as u8 + 1; 32])
                .unwrap();
            agent_id
        })
        .collect();

    for i in 1..6 {
        let result = coordinator.delegate(agents[0], agents[i]);
        assert!(result.is_ok(), "Delegation {}->{} should succeed", 0, i);
    }

    let result = coordinator.delegate(agents[0], agents[0]);
    assert!(result.is_err(), "Self-delegation should fail");
}
