/// Phase 39: RCE Durable Pause/Resume with OCC Integration Tests
///
/// Tests operationalize cognitive interrupts: RCE workflows can be safely paused,
/// validated by human operators, and resumed deterministically with full OCC protection
/// against concurrent writes and checksum-verified state restoration.
///
/// All tests use testcontainers Postgres 16 with Phase 38 migrations applied.

use serde_json::json;
use siss_graph_db::{rce::*, repo::rce_checkpoint_repo};
use sqlx::PgPool;
use testcontainers::runners::AsyncRunner;
use testcontainers::{core::WaitFor, GenericImage, ImageExt};
use uuid::Uuid;

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

#[tokio::test]
async fn test_pause_stores_snapshot_hex_in_db() {
    let (_container, pool) = setup_postgres().await;
    let mut rce = ResumableCognitiveExecution::new(Uuid::new_v4());

    let plan = vec![Step {
        id: Uuid::new_v4(),
        name: "step_1".to_string(),
        timeout_ms: 1000,
        ..Default::default()
    }];

    rce.start_workflow(plan).expect("start");
    rce.execute_next_step().expect("execute");

    let state_bytes = vec![0x01, 0x02, 0x03, 0x04];
    let interrupt = InterruptSignal {
        interrupt_type: "threat_detected".to_string(),
        severity: "High".to_string(),
        reason: "Blast radius exceeded".to_string(),
        ..Default::default()
    };

    rce.pause_workflow_with_persistence(&interrupt, state_bytes.clone(), &pool)
        .await
        .expect("pause with persistence");

    // Load from DB and verify snapshot_hex is stored
    let loaded = rce_checkpoint_repo::load_checkpoint(&pool, rce.workflow_id)
        .await
        .expect("load")
        .expect("checkpoint exists");

    let state_json = loaded.2;
    let snapshot_hex = state_json["snapshot_hex"]
        .as_str()
        .expect("snapshot_hex present in JSONB");

    // Verify hex encoding is correct
    let decoded = hex::decode(snapshot_hex).expect("valid hex");
    assert_eq!(decoded, state_bytes);
}

#[tokio::test]
async fn test_resume_from_db_validates_checksum_correctly() {
    let (_container, pool) = setup_postgres().await;
    let mut rce = ResumableCognitiveExecution::new(Uuid::new_v4());

    let plan = vec![Step {
        id: Uuid::new_v4(),
        name: "step_1".to_string(),
        timeout_ms: 1000,
        ..Default::default()
    }];

    rce.start_workflow(plan).expect("start");
    rce.execute_next_step().expect("execute");

    let state_bytes = vec![0xAA, 0xBB, 0xCC];
    let interrupt = InterruptSignal {
        interrupt_type: "threat".to_string(),
        severity: "High".to_string(),
        reason: "Test pause".to_string(),
        ..Default::default()
    };

    rce.pause_workflow_with_persistence(&interrupt, state_bytes, &pool)
        .await
        .expect("pause");

    // Clear in-memory checkpoint to force DB hydration
    let mut rce2 = ResumableCognitiveExecution::new(rce.workflow_id);
    rce2.start_workflow(vec![Step {
        id: Uuid::new_v4(),
        name: "step_1".to_string(),
        timeout_ms: 1000,
        ..Default::default()
    }])
    .expect("start");
    rce2.execute_next_step().expect("execute");

    // Transition to Paused manually so resume() works
    let checkpoint = rce.checkpoint.take().expect("has checkpoint");
    rce2.state = ExecutionState::Paused;
    rce2.checkpoint = Some(checkpoint);
    rce2.history.clear(); // Clear history to avoid conflicts

    // Resume from DB should succeed (checksum valid)
    rce2.resume_workflow_approve_with_persistence(&pool)
        .await
        .expect("resume from DB succeeds");

    assert_eq!(rce2.state, ExecutionState::Resumed);
}

#[tokio::test]
async fn test_resume_fails_closed_on_corrupted_db_checksum() {
    let (_container, pool) = setup_postgres().await;
    let mut rce = ResumableCognitiveExecution::new(Uuid::new_v4());

    let plan = vec![Step {
        id: Uuid::new_v4(),
        name: "step_1".to_string(),
        timeout_ms: 1000,
        ..Default::default()
    }];

    rce.start_workflow(plan).expect("start");
    rce.execute_next_step().expect("execute");

    let state_bytes = vec![0x11, 0x22];
    let interrupt = InterruptSignal {
        interrupt_type: "threat".to_string(),
        severity: "High".to_string(),
        reason: "Test pause".to_string(),
        ..Default::default()
    };

    rce.pause_workflow_with_persistence(&interrupt, state_bytes, &pool)
        .await
        .expect("pause");

    // Corrupt the checksum in the DB via raw SQL
    sqlx::query("UPDATE rce_checkpoints SET checksum = 'corrupted_hash' WHERE workflow_id = $1")
        .bind(rce.workflow_id)
        .execute(&pool)
        .await
        .expect("update checksum");

    // Attempt resume from DB should fail
    let mut rce2 = ResumableCognitiveExecution::new(rce.workflow_id);
    rce2.start_workflow(vec![Step {
        id: Uuid::new_v4(),
        name: "step_1".to_string(),
        timeout_ms: 1000,
        ..Default::default()
    }])
    .expect("start");
    rce2.execute_next_step().expect("execute");
    rce2.state = ExecutionState::Paused;

    let result = rce2.resume_workflow_approve_with_persistence(&pool).await;
    assert!(result.is_err());
    assert!(result
        .unwrap_err()
        .contains("checksum mismatch"));
}

#[tokio::test]
async fn test_repause_uses_occ_and_increments_version() {
    let (_container, pool) = setup_postgres().await;
    let mut rce = ResumableCognitiveExecution::new(Uuid::new_v4());

    let plan = vec![Step {
        id: Uuid::new_v4(),
        name: "step_1".to_string(),
        timeout_ms: 1000,
        ..Default::default()
    }];

    rce.start_workflow(plan.clone()).expect("start");
    rce.execute_next_step().expect("execute");

    // First pause
    let interrupt1 = InterruptSignal {
        interrupt_type: "threat".to_string(),
        severity: "High".to_string(),
        reason: "First pause".to_string(),
        ..Default::default()
    };
    rce.pause_workflow_with_persistence(&interrupt1, vec![0x01], &pool)
        .await
        .expect("first pause");

    let loaded1 = rce_checkpoint_repo::load_checkpoint(&pool, rce.workflow_id)
        .await
        .expect("load")
        .expect("exists");
    assert_eq!(loaded1.4, 1); // DB version = 1

    // Simulate resume: clear in-memory state
    rce.state = ExecutionState::Idle;
    rce.checkpoint = None;

    // Prepare to pause again: recreate from scratch
    let mut rce2 = ResumableCognitiveExecution::new(rce.workflow_id);
    rce2.start_workflow(plan.clone()).expect("start");
    rce2.execute_next_step().expect("execute");
    rce2.state = ExecutionState::Perform; // Set back to Perform for second pause

    // Second pause (should use OCC with version 1→2)
    let interrupt2 = InterruptSignal {
        interrupt_type: "threat".to_string(),
        severity: "High".to_string(),
        reason: "Second pause".to_string(),
        ..Default::default()
    };
    rce2.pause_workflow_with_persistence(&interrupt2, vec![0x02], &pool)
        .await
        .expect("second pause with OCC");

    let loaded2 = rce_checkpoint_repo::load_checkpoint(&pool, rce.workflow_id)
        .await
        .expect("load")
        .expect("exists");
    assert_eq!(loaded2.4, 2); // DB version = 2 (incremented via OCC)
}

#[tokio::test]
async fn test_full_durable_lifecycle_pause_approve_resume() {
    let (_container, pool) = setup_postgres().await;
    let mut rce = ResumableCognitiveExecution::new(Uuid::new_v4());

    let plan = vec![
        Step {
            id: Uuid::new_v4(),
            name: "step_1".to_string(),
            timeout_ms: 1000,
            ..Default::default()
        },
        Step {
            id: Uuid::new_v4(),
            name: "step_2".to_string(),
            timeout_ms: 1000,
            ..Default::default()
        },
    ];

    // Start and execute first step
    rce.start_workflow(plan).expect("start");
    assert_eq!(rce.state, ExecutionState::Perform);
    rce.execute_next_step().expect("execute");
    assert_eq!(rce.get_current_step_index(), 1);

    // Pause with persistence
    let interrupt = InterruptSignal {
        interrupt_type: "threat".to_string(),
        severity: "Critical".to_string(),
        reason: "Blast radius too high".to_string(),
        ..Default::default()
    };
    rce.pause_workflow_with_persistence(&interrupt, vec![0xAA, 0xBB], &pool)
        .await
        .expect("pause");

    assert_eq!(rce.state, ExecutionState::Paused);

    // Verify checkpoint in DB
    let checkpoint = rce_checkpoint_repo::load_checkpoint(&pool, rce.workflow_id)
        .await
        .expect("load")
        .expect("exists");
    assert_eq!(checkpoint.1, 1); // step_index preserved

    // Simulate operator approval and resume
    let mut rce_resumed = ResumableCognitiveExecution::new(rce.workflow_id);
    // Hydrate from DB
    rce_resumed.resume_workflow_approve_with_persistence(&pool)
        .await
        .expect("resume");

    assert_eq!(rce_resumed.state, ExecutionState::Resumed);
    assert_eq!(rce_resumed.get_current_step_index(), 1);
}

#[tokio::test]
async fn test_chaos_concurrent_pause_occ_prevents_split_brain() {
    let (_container, pool) = setup_postgres().await;
    let workflow_id = Uuid::new_v4();

    // Initial pause (version = 1)
    let _saved = rce_checkpoint_repo::save_checkpoint(
        &pool,
        workflow_id,
        0,
        &json!({"initial": true}),
        "initial_checksum",
        1,
        "initial_pause",
        "High",
    )
    .await
    .expect("initial save");

    // Spawn two concurrent tasks trying to update with OCC (both hold expected_version=1)
    let task1 = {
        let pool_clone = pool.clone();
        tokio::spawn(async move {
            rce_checkpoint_repo::update_checkpoint_occ(
                &pool_clone,
                workflow_id,
                1, // expected version
                1,
                &json!({"from": "task1"}),
                "task1_checksum",
                2, // new version
                "task1_pause",
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
                1, // expected version (stale after task1 updates)
                1,
                &json!({"from": "task2"}),
                "task2_checksum",
                2, // new version
                "task2_pause",
                "High",
            )
            .await
        })
    };

    let result1 = task1.await.expect("task1").expect("task1 execute");
    let result2 = task2.await.expect("task2").expect("task2 execute");

    // Exactly one should succeed, one should fail
    let success_count = (if result1 { 1 } else { 0 }) + (if result2 { 1 } else { 0 });
    assert_eq!(success_count, 1);

    // Verify final DB state: version = 2 (not corrupted)
    let final_checkpoint = rce_checkpoint_repo::load_checkpoint(&pool, workflow_id)
        .await
        .expect("load")
        .expect("exists");
    assert_eq!(final_checkpoint.4, 2); // Version is 2, not corrupted
}
