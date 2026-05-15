/// Phase 38: PostgreSQL Checkpoint Durability — Integration Tests
///
/// Tests checkpoint persistence with ACID guarantees and audit immutability.
/// All tests use testcontainers Postgres 16 with migrations applied.
///
/// Expected: All 8 tests FAIL until repo implementation is complete.

use chrono::Utc;
use serde_json::json;
use siss_graph_db::repo::rce_checkpoint_repo;
use sqlx::PgPool;
use testcontainers::runners::AsyncRunner;
use testcontainers::{core::WaitFor, GenericImage, ImageExt};
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

    // Run all migrations including Phase 38
    siss_graph_db::migrations::run_all(&pool)
        .await
        .expect("migrations");

    (container, pool)
}

// =====================================================================
// TESTS
// =====================================================================

#[tokio::test]
async fn test_save_and_load_checkpoint() {
    let (_container, pool) = setup_postgres().await;

    let workflow_id = Uuid::new_v4();
    let step_index = 2;
    let state_json = json!({
        "workflow_id": workflow_id,
        "state": "Paused",
        "step_index": step_index,
        "plan_size": 3
    });
    let checksum = "abc123def456";
    let version = 1;
    let reason = "threat_anticipation_blast_radius_high";
    let severity = "High";

    // Save checkpoint
    let saved_id = rce_checkpoint_repo::save_checkpoint(
        &pool,
        workflow_id,
        step_index,
        &state_json,
        checksum,
        version,
        reason,
        severity,
    )
    .await
    .expect("save_checkpoint failed");

    assert!(!saved_id.to_string().is_empty());

    // Load checkpoint
    let loaded = rce_checkpoint_repo::load_checkpoint(&pool, workflow_id)
        .await
        .expect("load_checkpoint failed");

    assert!(loaded.is_some());
    let (id, loaded_step_index, loaded_state, loaded_checksum, loaded_version, loaded_reason) =
        loaded.unwrap();

    assert_eq!(id, saved_id);
    assert_eq!(loaded_step_index, step_index);
    assert_eq!(loaded_state, state_json);
    assert_eq!(loaded_checksum, checksum);
    assert_eq!(loaded_version, version);
    assert_eq!(loaded_reason, reason);
}

#[tokio::test]
async fn test_checkpoint_overwrite_on_repause() {
    let (_container, pool) = setup_postgres().await;

    let workflow_id = Uuid::new_v4();

    // Save first checkpoint
    let id1 = rce_checkpoint_repo::save_checkpoint(
        &pool,
        workflow_id,
        0,
        &json!({"attempt": 1}),
        "checksum1",
        1,
        "pause_1",
        "High",
    )
    .await
    .expect("first save");

    // Save second checkpoint (upsert)
    let id2 = rce_checkpoint_repo::save_checkpoint(
        &pool,
        workflow_id,
        1,
        &json!({"attempt": 2}),
        "checksum2",
        1,
        "pause_2",
        "Critical",
    )
    .await
    .expect("second save");

    // IDs should differ (new row or same)
    // Load should return the latest
    let loaded = rce_checkpoint_repo::load_checkpoint(&pool, workflow_id)
        .await
        .expect("load_checkpoint")
        .expect("checkpoint exists");

    assert_eq!(loaded.1, 1); // step_index from second save
    assert_eq!(loaded.2, json!({"attempt": 2}));
    assert_eq!(loaded.3, "checksum2");
}

#[tokio::test]
async fn test_delete_checkpoint_on_reject() {
    let (_container, pool) = setup_postgres().await;

    let workflow_id = Uuid::new_v4();

    // Save checkpoint
    rce_checkpoint_repo::save_checkpoint(
        &pool,
        workflow_id,
        0,
        &json!({"state": "paused"}),
        "abc123",
        1,
        "test",
        "High",
    )
    .await
    .expect("save");

    // Verify it exists
    let exists = rce_checkpoint_repo::checkpoint_exists(&pool, workflow_id)
        .await
        .expect("exists check");
    assert!(exists);

    // Delete checkpoint
    let deleted = rce_checkpoint_repo::delete_checkpoint(&pool, workflow_id)
        .await
        .expect("delete");
    assert!(deleted);

    // Verify it's gone
    let loaded = rce_checkpoint_repo::load_checkpoint(&pool, workflow_id)
        .await
        .expect("load");
    assert!(loaded.is_none());
}

#[tokio::test]
async fn test_checkpoint_exists_returns_correct_bool() {
    let (_container, pool) = setup_postgres().await;

    let workflow_id = Uuid::new_v4();

    // Should not exist initially
    let exists = rce_checkpoint_repo::checkpoint_exists(&pool, workflow_id)
        .await
        .expect("exists check");
    assert!(!exists);

    // Save checkpoint
    rce_checkpoint_repo::save_checkpoint(
        &pool,
        workflow_id,
        0,
        &json!({}),
        "checksum",
        1,
        "reason",
        "High",
    )
    .await
    .expect("save");

    // Should exist now
    let exists = rce_checkpoint_repo::checkpoint_exists(&pool, workflow_id)
        .await
        .expect("exists check");
    assert!(exists);
}

#[tokio::test]
async fn test_checksum_stored_and_retrieved() {
    let (_container, pool) = setup_postgres().await;

    let workflow_id = Uuid::new_v4();
    let checksum = "sha256_abcdef123456";

    rce_checkpoint_repo::save_checkpoint(
        &pool,
        workflow_id,
        0,
        &json!({}),
        checksum,
        1,
        "reason",
        "High",
    )
    .await
    .expect("save");

    let loaded = rce_checkpoint_repo::load_checkpoint(&pool, workflow_id)
        .await
        .expect("load")
        .expect("checkpoint exists");

    assert_eq!(loaded.3, checksum);
}

#[tokio::test]
async fn test_audit_trail_append_only() {
    let (_container, pool) = setup_postgres().await;

    let workflow_id = Uuid::new_v4();

    // Append 3 events
    let id1 = rce_checkpoint_repo::append_audit_event(
        &pool,
        workflow_id,
        "workflow_paused",
        None,
        None,
        Some("threat detected"),
        &json!({"severity": "High"}),
    )
    .await
    .expect("append 1");

    let id2 = rce_checkpoint_repo::append_audit_event(
        &pool,
        workflow_id,
        "human_decision",
        Some("Approve"),
        Some("operator@acme.com"),
        None,
        &json!({}),
    )
    .await
    .expect("append 2");

    let id3 = rce_checkpoint_repo::append_audit_event(
        &pool,
        workflow_id,
        "workflow_resumed",
        None,
        None,
        None,
        &json!({}),
    )
    .await
    .expect("append 3");

    // Fetch all
    let trail = rce_checkpoint_repo::fetch_audit_trail(&pool, workflow_id)
        .await
        .expect("fetch");

    assert_eq!(trail.len(), 3);
    assert_eq!(trail[0].0, id1);
    assert_eq!(trail[1].0, id2);
    assert_eq!(trail[2].0, id3);

    // Verify event types
    assert_eq!(trail[0].1, "workflow_paused");
    assert_eq!(trail[1].1, "human_decision");
    assert_eq!(trail[2].1, "workflow_resumed");

    // Verify decision field
    assert_eq!(trail[1].2, Some("Approve".to_string()));
}

#[tokio::test]
async fn test_full_pause_persist_resume_cycle() {
    let (_container, pool) = setup_postgres().await;

    let workflow_id = Uuid::new_v4();

    // Step 1: Workflow is paused
    let checkpoint_state = json!({
        "workflow_id": workflow_id,
        "state": "Paused",
        "step_index": 1,
        "plan": ["step_1", "step_2", "step_3"],
        "checkpoint": {
            "snapshot": [1, 2, 3, 4, 5],
            "timestamp": "2026-05-15T10:30:50Z"
        }
    });

    let checkpoint_id = rce_checkpoint_repo::save_checkpoint(
        &pool,
        workflow_id,
        1,
        &checkpoint_state,
        "sha256_checkpoint_hash",
        1,
        "threat_anticipation_blast_radius_high",
        "High",
    )
    .await
    .expect("save checkpoint");

    // Step 2: Operator approves
    rce_checkpoint_repo::append_audit_event(
        &pool,
        workflow_id,
        "workflow_paused",
        None,
        None,
        Some("threat detected"),
        &json!({"tokens_at_risk": 600000}),
    )
    .await
    .expect("audit pause");

    rce_checkpoint_repo::append_audit_event(
        &pool,
        workflow_id,
        "human_decision",
        Some("Approve"),
        Some("operator@acme.com"),
        None,
        &json!({}),
    )
    .await
    .expect("audit approval");

    // Step 3: Resume — load checkpoint
    let loaded = rce_checkpoint_repo::load_checkpoint(&pool, workflow_id)
        .await
        .expect("load")
        .expect("has checkpoint");

    assert_eq!(loaded.0, checkpoint_id);
    assert_eq!(loaded.1, 1); // step_index restored
    assert_eq!(loaded.4, 1); // version restored
    assert_eq!(loaded.2, checkpoint_state); // state restored

    // Step 4: Verify audit trail
    let trail = rce_checkpoint_repo::fetch_audit_trail(&pool, workflow_id)
        .await
        .expect("fetch trail");

    assert_eq!(trail.len(), 2);
    assert_eq!(trail[0].1, "workflow_paused");
    assert_eq!(trail[1].1, "human_decision");
    assert_eq!(trail[1].2, Some("Approve".to_string()));
}

#[tokio::test]
async fn test_checkpoint_version_persisted() {
    let (_container, pool) = setup_postgres().await;

    let workflow_id = Uuid::new_v4();
    let version = 1;

    rce_checkpoint_repo::save_checkpoint(
        &pool,
        workflow_id,
        0,
        &json!({}),
        "checksum",
        version,
        "reason",
        "High",
    )
    .await
    .expect("save");

    let loaded = rce_checkpoint_repo::load_checkpoint(&pool, workflow_id)
        .await
        .expect("load")
        .expect("checkpoint exists");

    assert_eq!(loaded.4, version);
}

#[tokio::test]
async fn test_occ_update_succeeds_when_version_matches() {
    let (_container, pool) = setup_postgres().await;
    let workflow_id = Uuid::new_v4();

    // Initial save via blind upsert
    rce_checkpoint_repo::save_checkpoint(
        &pool,
        workflow_id,
        0,
        &json!({"v": 1}),
        "cs1",
        1,
        "reason",
        "High",
    )
    .await
    .unwrap();

    // OCC update with correct expected_version=1 → new_version=2
    let ok = rce_checkpoint_repo::update_checkpoint_occ(
        &pool,
        workflow_id,
        1,
        1,
        &json!({"v": 2}),
        "cs2",
        2,
        "reason",
        "High",
    )
    .await
    .unwrap();

    assert!(ok); // succeeded
    let loaded = rce_checkpoint_repo::load_checkpoint(&pool, workflow_id)
        .await
        .unwrap()
        .unwrap();
    assert_eq!(loaded.4, 2); // version advanced
    assert_eq!(loaded.2, json!({"v": 2}));
}

#[tokio::test]
async fn test_occ_update_fails_when_version_mismatch() {
    let (_container, pool) = setup_postgres().await;
    let workflow_id = Uuid::new_v4();

    // Initial save — version=1
    rce_checkpoint_repo::save_checkpoint(
        &pool,
        workflow_id,
        0,
        &json!({}),
        "cs1",
        1,
        "reason",
        "High",
    )
    .await
    .unwrap();

    // Simulate concurrent writer: bump version to 2
    rce_checkpoint_repo::update_checkpoint_occ(
        &pool,
        workflow_id,
        1,
        1,
        &json!({"concurrent": true}),
        "cs2",
        2,
        "r",
        "High",
    )
    .await
    .unwrap();

    // Late writer still holds expected_version=1 → must fail
    let ok = rce_checkpoint_repo::update_checkpoint_occ(
        &pool,
        workflow_id,
        1,
        2,
        &json!({"stale": true}),
        "cs3",
        2,
        "r",
        "High",
    )
    .await
    .unwrap();

    assert!(!ok); // rejected — stale version
                 // State must still reflect the concurrent writer's update
    let loaded = rce_checkpoint_repo::load_checkpoint(&pool, workflow_id)
        .await
        .unwrap()
        .unwrap();
    assert_eq!(loaded.4, 2);
    assert_eq!(loaded.2, json!({"concurrent": true}));
}
