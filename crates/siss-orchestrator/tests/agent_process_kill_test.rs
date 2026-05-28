use siss_orchestrator::failure::{AgentBinaryTree, AgentProcessRegistry, AgentHealth, IsolationError};
use uuid::Uuid;
use std::process::Command;
use std::thread;
use std::time::Duration;

#[test]
fn test_kill_nonexistent_pid_returns_error() {
    let mut registry = AgentProcessRegistry::new();
    let agent_id = Uuid::new_v4();

    let result = registry.kill_agent_process(agent_id);
    assert!(matches!(result, Err(IsolationError::ProcessNotFound)));
}

#[test]
fn test_register_and_kill_spawned_sleep_process() {
    let mut registry = AgentProcessRegistry::new();
    let agent_id = Uuid::new_v4();

    let child = Command::new("sleep")
        .arg("60")
        .spawn()
        .expect("Failed to spawn sleep process");

    let pid = child.id();
    registry.register_agent_pid(agent_id, pid);

    let result = registry.kill_agent_process(agent_id);
    assert!(result.is_ok(), "Should successfully kill process");

    thread::sleep(Duration::from_millis(100));

    let check_alive = Command::new("kill")
        .args(&["-0", &pid.to_string()])
        .output();

    assert!(check_alive.is_err() || !check_alive.unwrap().status.success(),
        "Process should be dead after kill");
}

#[test]
fn test_isolate_and_kill_logs_correct_agent() {
    let mut tree = AgentBinaryTree::new();
    let mut registry = AgentProcessRegistry::new();

    let agent_id = Uuid::new_v4();
    let health = AgentHealth {
        agent_id,
        is_healthy: true,
        last_probe_ms: 50,
    };
    tree.insert_agent(agent_id, health).unwrap();

    let child = Command::new("sleep")
        .arg("60")
        .spawn()
        .expect("Failed to spawn sleep process");

    let pid = child.id();
    registry.register_agent_pid(agent_id, pid);

    let result = tree.isolate_and_kill("test_symptom", &mut registry);
    assert!(result.is_ok(), "isolate_and_kill should succeed");
    assert_eq!(result.unwrap(), agent_id, "Should isolate and kill correct agent");
}
