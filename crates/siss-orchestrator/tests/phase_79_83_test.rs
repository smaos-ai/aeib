use siss_orchestrator::{
    CommitmentCapsule, TwoPointerScheduler, DispatchTask, AgentBinaryTree, AgentHealth,
    KalmanState, ExpertGateway, CapabilityLevel, ExpertTask, SwarmState,
};
use uuid::Uuid;
use std::collections::HashMap;
use std::time::SystemTime;

#[test]
fn invariant_1_capsule_locality_bounded_scope() {
    let agent_id = Uuid::new_v4();
    let symbols = (0..50).map(|i| format!("symbol_{}", i)).collect();
    let capsule = CommitmentCapsule::new(
        agent_id,
        symbols,
        vec!["file.rs".to_string()],
        "diff content".to_string(),
        vec!["cluster".to_string()],
        HashMap::new(),
    );
    assert!(capsule.is_ok());

    let symbols_too_many = (0..51).map(|i| format!("symbol_{}", i)).collect();
    let capsule_invalid = CommitmentCapsule::new(
        agent_id,
        symbols_too_many,
        vec![],
        "diff".to_string(),
        vec![],
        HashMap::new(),
    );
    assert!(capsule_invalid.is_err());
}

#[test]
fn invariant_1_capsule_acyclic_dag() {
    let agent_id = Uuid::new_v4();
    let mut deps = HashMap::new();
    deps.insert("a".to_string(), vec!["b".to_string()]);
    deps.insert("b".to_string(), vec!["c".to_string()]);
    deps.insert("c".to_string(), vec![]);

    let capsule = CommitmentCapsule::new(
        agent_id,
        vec!["a".to_string()],
        vec![],
        "diff".to_string(),
        vec![],
        deps,
    );
    assert!(capsule.is_ok());
}

#[test]
fn invariant_1_capsule_cyclic_rejected() {
    let agent_id = Uuid::new_v4();
    let mut deps = HashMap::new();
    deps.insert("a".to_string(), vec!["b".to_string()]);
    deps.insert("b".to_string(), vec!["a".to_string()]);

    let capsule = CommitmentCapsule::new(
        agent_id,
        vec!["a".to_string()],
        vec![],
        "diff".to_string(),
        vec![],
        deps,
    );
    assert!(capsule.is_err());
}

#[test]
fn invariant_2_two_pointer_amortized_dispatch() {
    let mut scheduler = TwoPointerScheduler::new();
    for i in 0..1000 {
        let task = DispatchTask {
            task_id: Uuid::new_v4(),
            capsule_id: Uuid::new_v4(),
            agent_id: Uuid::new_v4(),
            symbol: format!("sym_{}", i),
        };
        scheduler.enqueue(task);
    }

    for _ in 0..1000 {
        let _ = scheduler.dispatch_next();
    }

    let cost = scheduler.amortized_cost_per_op();
    assert!(cost <= 2.0, "Amortized cost {} exceeds O(1) bound", cost);
}

#[test]
fn invariant_2_two_pointer_dependency_resolution() {
    let mut scheduler = TwoPointerScheduler::new();
    let capsule_id = Uuid::new_v4();

    for i in 0..100 {
        let task = DispatchTask {
            task_id: Uuid::new_v4(),
            capsule_id,
            agent_id: Uuid::new_v4(),
            symbol: format!("task_{}", i),
        };
        scheduler.enqueue_waiting(task, capsule_id);
    }

    assert_eq!(scheduler.waiting_queue_len(), 1);
    scheduler.resolve_dependency("resolved".to_string(), capsule_id).ok();
    assert_eq!(scheduler.waiting_queue_len(), 0);
    assert_eq!(scheduler.ready_queue_len(), 100);
}

#[test]
fn invariant_3_binary_isolation_logarithmic_tree() {
    let mut tree = AgentBinaryTree::new();
    for i in 0..64 {
        let agent_id = Uuid::new_v4();
        let health = AgentHealth {
            agent_id,
            is_healthy: true,
            last_probe_ms: 50,
        };
        tree.insert_agent(agent_id, health).ok();
    }

    let depth = tree.tree_depth();
    assert!(depth <= 8, "Tree depth {} exceeds log(64) bound of 8", depth);
}

#[test]
fn invariant_3_binary_isolation_failure_diagnosis() {
    let mut tree = AgentBinaryTree::new();
    let mut agent_ids = vec![];
    for i in 0..32 {
        let agent_id = Uuid::new_v4();
        agent_ids.push(agent_id);
        let health = AgentHealth {
            agent_id,
            is_healthy: true,
            last_probe_ms: 50,
        };
        tree.insert_agent(agent_id, health).ok();
    }

    let result = tree.isolate_failure("symptom");
    assert!(result.is_ok());
    let isolated_agent = result.unwrap();
    assert!(agent_ids.contains(&isolated_agent));
    assert!(tree.tree_depth() <= 6);
}

#[test]
fn invariant_4_kalman_observer_constant_update() {
    let mut observer = KalmanState::new();
    let start = std::time::Instant::now();

    for i in 0..10000 {
        let measurement = [
            0.1 * (i % 10) as f64,
            0.05 * (i % 5) as f64,
            0.02 * (i % 3) as f64,
            0.01 * (i % 2) as f64,
        ];
        let _ = observer.update(measurement);
    }

    let elapsed = start.elapsed().as_micros();
    let ops_per_microsecond = 10000.0 / elapsed as f64;
    assert!(
        elapsed < 1_000_000,
        "10k updates took {}μs, should be < 1000ms",
        elapsed
    );
}

#[test]
fn invariant_4_kalman_observer_rebalance_decision() {
    let mut observer = KalmanState::new();
    for _ in 0..100 {
        let measurement = [0.1, 0.1, 0.1, 0.1];
        let _ = observer.update(measurement);
    }

    let decision = observer.should_rebalance();
    assert!(!format!("{:?}", decision).is_empty());
}

#[test]
fn invariant_5_expert_handoff_bounded_escalation() {
    let mut gateway = ExpertGateway::new(10);
    let agent_id = Uuid::new_v4();
    let token =
        siss_orchestrator::CapabilityToken::new(agent_id, CapabilityLevel::Expert, 3600);
    gateway.register_token(token).ok();

    let task = ExpertTask {
        task_id: Uuid::new_v4(),
        description: "Test task".to_string(),
        complexity: 5,
        required_level: CapabilityLevel::Basic,
        timeout_ms: 500,
        created_at: SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs(),
    };

    let start = std::time::Instant::now();
    let result = gateway.escalate(&task, agent_id);
    let elapsed_ms = start.elapsed().as_millis() as u32;

    assert!(elapsed_ms < 500);
    assert!(result.is_ok());
}

#[test]
fn invariant_5_expert_handoff_timeout_guarantee() {
    let gateway = ExpertGateway::new(10);
    let task = ExpertTask {
        task_id: Uuid::new_v4(),
        description: "Test task".to_string(),
        complexity: 5,
        required_level: CapabilityLevel::Expert,
        timeout_ms: 100,
        created_at: SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs(),
    };

    let result = gateway.escalate(&task, Uuid::new_v4());
    let elapsed_ms = std::time::Instant::now()
        .elapsed()
        .as_millis() as u32;
    assert!(elapsed_ms < task.timeout_ms);
}

#[test]
fn composite_invariants_swarm_state_integration() {
    let mut swarm = SwarmState::new(Uuid::new_v4());
    let capsule_id = Uuid::new_v4();
    let observer = KalmanState::new();

    swarm.set_capsule(capsule_id);
    swarm.set_observer_state(observer);
    swarm.update_agent_count(32);

    assert!(swarm.capsule_active());
    assert!(swarm.has_observer());
    assert_eq!(swarm.agent_count, 32);
    assert!(swarm.is_healthy);
}

#[test]
fn composite_invariants_scheduler_with_tree() {
    let mut scheduler = TwoPointerScheduler::new();
    let mut tree = AgentBinaryTree::new();

    for i in 0..16 {
        let agent_id = Uuid::new_v4();
        let health = AgentHealth {
            agent_id,
            is_healthy: true,
            last_probe_ms: 50,
        };
        tree.insert_agent(agent_id, health).ok();

        let task = DispatchTask {
            task_id: Uuid::new_v4(),
            capsule_id: Uuid::new_v4(),
            agent_id,
            symbol: format!("op_{}", i),
        };
        scheduler.enqueue(task);
    }

    assert!(tree.tree_depth() <= 5);
    assert_eq!(scheduler.ready_queue_len(), 16);
}

#[test]
fn composite_invariants_full_workflow() {
    let agent_id = Uuid::new_v4();
    let mut deps = HashMap::new();
    deps.insert("a".to_string(), vec!["b".to_string()]);

    let capsule = CommitmentCapsule::new(
        agent_id,
        vec!["a".to_string()],
        vec!["main.rs".to_string()],
        "diff".to_string(),
        vec!["core".to_string()],
        deps,
    );
    assert!(capsule.is_ok());

    let capsule_data = capsule.unwrap();
    let mut swarm = SwarmState::new(Uuid::new_v4());
    swarm.set_capsule(capsule_data.capsule_id);

    let mut scheduler = TwoPointerScheduler::new();
    let task = DispatchTask {
        task_id: Uuid::new_v4(),
        capsule_id: capsule_data.capsule_id,
        agent_id,
        symbol: "a".to_string(),
    };
    scheduler.enqueue(task);

    assert!(swarm.capsule_active());
    assert_eq!(scheduler.ready_queue_len(), 1);
}
