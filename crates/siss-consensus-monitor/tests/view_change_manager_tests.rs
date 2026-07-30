use siss_consensus_monitor::ViewChangeManager;
use std::time::Duration;

#[test]
fn test_trigger_view_change_on_timeout() {
    let manager = ViewChangeManager::new(
        "node-1".to_string(),
        vec!["node-1".to_string(), "node-2".to_string(), "node-3".to_string()],
        Duration::from_secs(2),
    );

    manager.set_leader("node-2".to_string());
    assert!(!manager.is_view_change_needed());

    // Simulate timeout - manually advance time
    manager.simulate_timeout();
    assert!(manager.is_view_change_needed());
}

#[test]
fn test_view_change_state_machine() {
    let manager = ViewChangeManager::new(
        "node-1".to_string(),
        vec!["node-1".to_string(), "node-2".to_string(), "node-3".to_string()],
        Duration::from_secs(2),
    );

    assert_eq!(manager.current_view(), 0);

    manager.initiate_view_change();
    let new_view = manager.current_view();
    assert!(new_view > 0);

    // State transitions
    let state = manager.view_change_state();
    assert!(state == "started" || state == "in_progress");
}

#[test]
fn test_new_leader_elected_after_view_change() {
    let manager = ViewChangeManager::new(
        "node-1".to_string(),
        vec!["node-1".to_string(), "node-2".to_string(), "node-3".to_string()],
        Duration::from_secs(2),
    );

    manager.set_leader("node-2".to_string());
    manager.initiate_view_change();

    // Elect new leader
    manager.elect_new_leader("node-1".to_string());
    assert_eq!(manager.current_leader(), Some("node-1".to_string()));
}

#[test]
fn test_old_leader_isolation() {
    let manager = ViewChangeManager::new(
        "node-1".to_string(),
        vec!["node-1".to_string(), "node-2".to_string(), "node-3".to_string()],
        Duration::from_secs(2),
    );

    manager.set_leader("node-2".to_string());
    manager.initiate_view_change();

    // Old leader should be isolated
    assert!(manager.is_node_isolated("node-2"));
}

#[test]
fn test_view_change_quorum_validation() {
    let manager = ViewChangeManager::new(
        "node-1".to_string(),
        vec!["node-1".to_string(), "node-2".to_string(), "node-3".to_string()],
        Duration::from_secs(2),
    );

    manager.initiate_view_change();

    // Simulate quorum acknowledgment
    manager.acknowledge_view_change("node-1".to_string());
    manager.acknowledge_view_change("node-2".to_string());

    // 2 out of 3 = sufficient quorum
    assert!(manager.has_quorum_for_view_change());
}

#[test]
fn test_cascading_view_changes() {
    let manager = ViewChangeManager::new(
        "node-1".to_string(),
        vec![
            "node-1".to_string(),
            "node-2".to_string(),
            "node-3".to_string(),
            "node-4".to_string(),
            "node-5".to_string(),
        ],
        Duration::from_secs(2),
    );

    // First view change
    manager.initiate_view_change();
    let view_1 = manager.current_view();

    // Simulate another leader failure
    manager.simulate_timeout();
    manager.initiate_view_change();
    let view_2 = manager.current_view();

    assert!(view_2 > view_1);
    assert_eq!(view_2 - view_1, 1);
}
