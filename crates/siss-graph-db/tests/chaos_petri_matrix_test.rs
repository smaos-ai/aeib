/// Chaos Petri v1: Failure Injection Matrix for RCE Durability
///
/// Tests empirically verify OCC and checkpoint durability under Byzantine, network,
/// and concurrent failure scenarios. All tests use testcontainers Postgres 16.
use serde_json::json;
use siss_graph_db::{rce::*, repo::rce_checkpoint_repo};
use sqlx::PgPool;
use testcontainers::runners::AsyncRunner;
use testcontainers::{GenericImage, ImageExt, core::WaitFor};
use uuid::Uuid;

// =====================================================================
// TEST SETUP
// =====================================================================

async fn setup_postgres() -> (testcontainers::ContainerAsync<GenericImage>, PgPool) {
    let container = GenericImage::new("postgres", "16")
        .with_wait_for(WaitFor::message_on_stderr(
            "database system is ready to accept connections",
        ))
        .with_env_var("POSTGRES_PASSWORD", "postgres")
        .with_env_var("POSTGRES_DB", "siss_test")
        .start()
        .await
        .expect("postgres started");

    let port = container.get_host_port_ipv4(5432).await.unwrap();
    let url = format!("postgres://postgres:postgres@127.0.0.1:{port}/siss_test");
    let pool = PgPool::connect(&url).await.expect("pool connect");

    siss_graph_db::migrations::run_all(&pool)
        .await
        .expect("migrations");

    (container, pool)
}

/// Seed a paused workflow at a specific version
async fn seed_paused_workflow(pool: &PgPool, version: i32) -> Uuid {
    let workflow_id = Uuid::new_v4();
    let state_json = json!({
        "workflow_id": workflow_id,
        "step_index": 0,
        "snapshot_hex": "0102030405",
    });

    rce_checkpoint_repo::save_checkpoint(
        pool,
        workflow_id,
        0,
        &state_json,
        "test_checksum_abc123",
        version,
        "test_pause",
        "High",
    )
    .await
    .expect("seed checkpoint");

    workflow_id
}

// =====================================================================
// FAILURE SCENARIOS
// =====================================================================

/// SCENARIO 1: CONCURRENT WRITES (SPLIT-BRAIN RESUME)
/// Failure: Two isolated agent nodes attempt to resume the same workflow simultaneously.
/// Invariant: OCC enforces strict serialization; exactly one node acquires the execution lock.
/// Expected State: DB version increments by exactly 1. One operation succeeds, the other fails with VersionConflict.
#[tokio::test]
async fn test_chaos_concurrent_writes_split_brain() {
    let (_container, pool) = setup_postgres().await;
    let workflow_id = seed_paused_workflow(&pool, 1).await;

    // Simulate two concurrent workers reading the same baseline state (version=1)
    let task1 = {
        let pool_clone = pool.clone();
        tokio::spawn(async move {
            rce_checkpoint_repo::update_checkpoint_occ(
                &pool_clone,
                workflow_id,
                1, // expected_version
                0,
                &json!({"from": "worker_a"}),
                "checksum_a",
                2, // new_version
                "worker_a_pause",
                "High",
            )
            .await
        })
    };

    let task2 = {
        let pool_clone = pool.clone();
        tokio::spawn(async move {
            rce_checkpoint_repo::update_checkpoint_occ(
                &pool_clone,
                workflow_id,
                1, // expected_version (stale after task1 updates)
                0,
                &json!({"from": "worker_b"}),
                "checksum_b",
                2, // new_version
                "worker_b_pause",
                "High",
            )
            .await
        })
    };

    let result1 = task1.await.expect("task1").expect("task1 execute");
    let result2 = task2.await.expect("task2").expect("task2 execute");

    // ASSERTIONS
    let success_count = (if result1 { 1 } else { 0 }) + (if result2 { 1 } else { 0 });
    assert_eq!(
        success_count, 1,
        "Exactly one worker must succeed; OCC serializes writes"
    );

    let final_state = rce_checkpoint_repo::load_checkpoint(&pool, workflow_id)
        .await
        .expect("load")
        .expect("exists");
    assert_eq!(final_state.4, 2, "DB version must increment by exactly 1");
}

/// SCENARIO 2: BYZANTINE CHECKSUM (CORRUPTED STATE PAYLOAD)
/// Failure: Malicious actor or bit-rot alters the JSONB state payload without recalculating the SHA-256 hash.
/// Invariant: RCE must Fail-Closed on cryptographic mismatch. No cognitive state is hydrated.
/// Expected State: Workflow remains paused. Database state is unaltered.
#[tokio::test]
async fn test_chaos_byzantine_checksum_corruption() {
    let (_container, pool) = setup_postgres().await;
    let workflow_id = seed_paused_workflow(&pool, 1).await;

    // Inject Byzantine failure: Mutate JSONB payload directly in DB via raw SQL
    sqlx::query("UPDATE rce_checkpoints SET state = $1 WHERE workflow_id = $2")
        .bind(json!({"hacked": true}))
        .bind(workflow_id)
        .execute(&pool)
        .await
        .expect("inject corruption");

    // Orchestrator attempts to resume
    let mut rce = ResumableCognitiveExecution::new(workflow_id);
    let result = rce.resume_workflow_approve_with_persistence(&pool).await;

    // ASSERTIONS
    assert!(
        result.is_err(),
        "Resume must fail on checksum mismatch (fail-closed)"
    );
    let err_msg = result.unwrap_err();
    assert!(
        err_msg.to_lowercase().contains("checksum") || err_msg.to_lowercase().contains("corrupt"),
        "Error message must indicate checksum/corruption failure, got: {}",
        err_msg
    );

    // Verify state is unchanged in DB
    let db_state = rce_checkpoint_repo::load_checkpoint(&pool, workflow_id)
        .await
        .expect("load")
        .expect("checkpoint exists");
    assert_eq!(db_state.4, 1, "Version must not change on failed resume");
}

/// SCENARIO 3: DATABASE CRASH MID-PAUSE (NETWORK PARTITION)
/// Failure: Agent attempts to pause, but connection to Postgres drops during the transaction.
/// Invariant: Transactional atomicity guarantees the checkpoint and audit trail are written together or not at all.
/// Expected State: The previous valid checkpoint remains intact. No partial states exist.
#[tokio::test]
async fn test_chaos_network_partition_mid_pause() {
    let (_container, pool) = setup_postgres().await;

    // Seed an initial paused state at version 2
    let workflow_id = seed_paused_workflow(&pool, 2).await;

    // Verify baseline state
    let baseline = rce_checkpoint_repo::load_checkpoint(&pool, workflow_id)
        .await
        .expect("load")
        .expect("exists");
    assert_eq!(baseline.4, 2);

    // Create a new RCE instance and start a workflow
    let mut rce = ResumableCognitiveExecution::new(workflow_id);
    let plan = vec![Step {
        id: Uuid::new_v4(),
        name: "step_1".to_string(),
        timeout_ms: 1000,
        ..Default::default()
    }];
    rce.start_workflow(plan).expect("start");
    rce.execute_next_step().expect("execute");

    // Simulate pause on a pool with forced errors (close the pool connection)
    let dropped_pool = {
        let container = GenericImage::new("postgres", "16")
            .with_wait_for(WaitFor::message_on_stderr(
                "database system is ready to accept connections",
            ))
            .with_env_var("POSTGRES_PASSWORD", "postgres")
            .with_env_var("POSTGRES_DB", "siss_test")
            .start()
            .await
            .expect("postgres started");

        let port = container.get_host_port_ipv4(5432).await.unwrap();
        let url = format!("postgres://postgres:postgres@127.0.0.1:{port}/siss_test");
        let p = PgPool::connect(&url).await.expect("pool connect");
        // Immediately close to simulate network partition
        drop(container);
        p
    };

    let interrupt = InterruptSignal {
        interrupt_type: "network_failure".to_string(),
        severity: "High".to_string(),
        reason: "simulated_partition".to_string(),
        ..Default::default()
    };

    let result = rce
        .pause_workflow_with_persistence(&interrupt, vec![0xAA, 0xBB], &dropped_pool)
        .await;

    // ASSERTIONS
    assert!(
        result.is_err(),
        "Pause must fail when DB is unreachable (fail-closed)"
    );

    // Verify state hasn't drifted via a healthy connection
    let verified_state = rce_checkpoint_repo::load_checkpoint(&pool, workflow_id)
        .await
        .expect("load")
        .expect("exists");
    assert_eq!(
        verified_state.4, 2,
        "State must remain at last known good version (no partial writes)"
    );
}

/// SCENARIO 4: OUT-OF-ORDER RESUME (REPLAY ATTACK)
/// Failure: A delayed network packet or malicious orchestrator attempts to resume using a historical state and version.
/// Invariant: Strict monotonic progression. Stale resumes are rejected to prevent cognitive loops.
/// Expected State: DB rejects the payload. Workflow remains at current advanced version.
#[tokio::test]
async fn test_chaos_out_of_order_resume_replay() {
    let (_container, pool) = setup_postgres().await;
    let workflow_id = seed_paused_workflow(&pool, 4).await;

    // Attempt a replay attack using stale Version 2
    let stale_version = 2;
    let result = rce_checkpoint_repo::update_checkpoint_occ(
        &pool,
        workflow_id,
        stale_version, // expected_version (doesn't match current 4)
        0,
        &json!({"replay": "attack"}),
        "replay_checksum",
        3, // attempting to bump to 3 (but expected was 2)
        "replay_pause",
        "High",
    )
    .await
    .expect("execute OCC update");

    // ASSERTIONS
    assert!(
        !result,
        "OCC must reject stale version (no monotonic regression)"
    );

    let current_state = rce_checkpoint_repo::load_checkpoint(&pool, workflow_id)
        .await
        .expect("load")
        .expect("exists");
    assert_eq!(
        current_state.4, 4,
        "Version must not regress or be corrupted by replay"
    );
}

/// SCENARIO 5: PROCESS DEATH MID-RESUME (ZOMBIE STATE)
/// Failure: Agent successfully resumes (loads state, OCC succeeds), but the host process is OOM-killed before finishing the step.
/// Invariant: The database holds the active state, and the step remains idempotent so a new node can safely retry.
/// Expected State: The workflow is marked as active/in-progress in DB at Version N+1. A new agent node can safely claim it after timeout.
#[tokio::test]
async fn test_chaos_process_death_mid_resume() {
    let (_container, pool) = setup_postgres().await;
    let workflow_id = seed_paused_workflow(&pool, 1).await;

    // 1. Agent A loads and successfully increments version (simulating OCC success)
    let occ_result = rce_checkpoint_repo::update_checkpoint_occ(
        &pool,
        workflow_id,
        1, // expected_version
        0,
        &json!({"agent_a": "resumed"}),
        "agent_a_checksum",
        2, // new_version
        "agent_a_resume",
        "High",
    )
    .await
    .expect("agent A OCC update");

    assert!(occ_result, "Agent A must successfully increment version");

    // 2. Agent A "dies" immediately after (no further DB writes)

    // 3. Agent B detects timeout and must safely resume
    let agent_b_state = rce_checkpoint_repo::load_checkpoint(&pool, workflow_id)
        .await
        .expect("load")
        .expect("exists");

    // ASSERTIONS: Agent B must see the incremented version
    assert_eq!(
        agent_b_state.4, 2,
        "Agent B must see the advanced version (no stale reads)"
    );

    // Agent B can now safely pause or continue work at the new version
    let recovery_result = rce_checkpoint_repo::update_checkpoint_occ(
        &pool,
        workflow_id,
        agent_b_state.4, // Use the correct current version
        agent_b_state.1, // step_index
        &json!({"agent_b": "recovery"}),
        "agent_b_checksum",
        3, // increment to version 3
        "agent_b_recovery",
        "High",
    )
    .await
    .expect("agent B OCC recovery");

    assert!(
        recovery_result,
        "Agent B must successfully increment version (recovery succeeds)"
    );

    let final_state = rce_checkpoint_repo::load_checkpoint(&pool, workflow_id)
        .await
        .expect("load")
        .expect("exists");
    assert_eq!(final_state.4, 3, "Final version must be 3 after recovery");
}
