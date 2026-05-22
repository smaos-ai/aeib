use serde_json::json;
use siss_graph_db::repo::rce_checkpoint_repo;
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
async fn test_decision_webhook_records_audit_trail() {
    let (_container, pool) = setup_postgres().await;

    let workflow_id = Uuid::new_v4();

    // Simulate decision webhook recording an approval
    let audit_id = rce_checkpoint_repo::append_audit_event(
        &pool,
        workflow_id,
        "human_decision",
        Some("Approve"),
        Some("operator@acme.com"),
        None,
        &json!({"decision": "approve"}),
    )
    .await
    .expect("append audit");

    assert!(!audit_id.to_string().is_empty());

    // Fetch audit trail to verify
    let trail = rce_checkpoint_repo::fetch_audit_trail(&pool, workflow_id)
        .await
        .expect("fetch trail");

    assert_eq!(trail.len(), 1);
    assert_eq!(trail[0].1, "human_decision");
    assert_eq!(trail[0].2, Some("Approve".to_string()));
    assert_eq!(trail[0].3, Some("operator@acme.com".to_string()));
}

#[tokio::test]
async fn test_checkpoint_deletion_on_reject() {
    let (_container, pool) = setup_postgres().await;

    let workflow_id = Uuid::new_v4();

    // Save checkpoint
    let checkpoint_state = json!({
        "workflow_id": workflow_id,
        "state": "Paused"
    });

    rce_checkpoint_repo::save_checkpoint(
        &pool,
        workflow_id,
        0,
        &checkpoint_state,
        "checksum_abc",
        1,
        "threat_detected",
        "High",
    )
    .await
    .expect("save checkpoint");

    // Verify it exists
    let exists = rce_checkpoint_repo::checkpoint_exists(&pool, workflow_id)
        .await
        .expect("exists check");
    assert!(exists);

    // Simulate reject decision: delete checkpoint
    let deleted = rce_checkpoint_repo::delete_checkpoint(&pool, workflow_id)
        .await
        .expect("delete");
    assert!(deleted);

    // Verify checkpoint is gone
    let loaded = rce_checkpoint_repo::load_checkpoint(&pool, workflow_id)
        .await
        .expect("load");
    assert!(loaded.is_none());
}

#[tokio::test]
async fn test_checkpoint_handler_persists_and_loads() {
    let (_container, pool) = setup_postgres().await;

    let workflow_id = Uuid::new_v4();

    // Simulate handler: save checkpoint
    let state_json = json!({
        "workflow_id": workflow_id,
        "step_index": 2,
        "plan_size": 3,
        "state_snapshot_size": 1024
    });

    let checkpoint_id = rce_checkpoint_repo::save_checkpoint(
        &pool,
        workflow_id,
        2,
        &state_json,
        "sha256_checkpoint_hash",
        1,
        "threat_anticipation",
        "High",
    )
    .await
    .expect("save via handler");

    assert!(!checkpoint_id.to_string().is_empty());

    // Simulate handler: load checkpoint on GET /checkpoint
    let loaded = rce_checkpoint_repo::load_checkpoint(&pool, workflow_id)
        .await
        .expect("load")
        .expect("checkpoint exists");

    assert_eq!(loaded.0, checkpoint_id);
    assert_eq!(loaded.1, 2); // step_index
    assert_eq!(loaded.2, state_json); // state
    assert_eq!(loaded.3, "sha256_checkpoint_hash"); // checksum
}

#[tokio::test]
async fn test_audit_trail_recorded_for_all_decisions() {
    let (_container, pool) = setup_postgres().await;

    let workflow_id = Uuid::new_v4();

    // Record multiple decision events
    rce_checkpoint_repo::append_audit_event(
        &pool,
        workflow_id,
        "workflow_paused",
        None,
        None,
        Some("threat detected"),
        &json!({"severity": "High"}),
    )
    .await
    .expect("pause event");

    rce_checkpoint_repo::append_audit_event(
        &pool,
        workflow_id,
        "human_decision",
        Some("Approve"),
        Some("operator@acme.com"),
        None,
        &json!({"decision": "approve"}),
    )
    .await
    .expect("approval event");

    // Fetch full trail
    let trail = rce_checkpoint_repo::fetch_audit_trail(&pool, workflow_id)
        .await
        .expect("fetch trail");

    assert_eq!(trail.len(), 2);
    assert_eq!(trail[0].1, "workflow_paused");
    assert_eq!(trail[1].1, "human_decision");
    assert_eq!(trail[1].2, Some("Approve".to_string()));
}

#[tokio::test]
async fn test_checkpoint_version_updated_on_resave() {
    let (_container, pool) = setup_postgres().await;

    let workflow_id = Uuid::new_v4();

    // Save checkpoint v1
    rce_checkpoint_repo::save_checkpoint(
        &pool,
        workflow_id,
        0,
        &json!({"state": "paused_v1"}),
        "checksum_v1",
        1,
        "reason_v1",
        "High",
    )
    .await
    .expect("save v1");

    // Resave as v2 (upsert)
    rce_checkpoint_repo::save_checkpoint(
        &pool,
        workflow_id,
        1,
        &json!({"state": "paused_v2"}),
        "checksum_v2",
        2,
        "reason_v2",
        "Critical",
    )
    .await
    .expect("save v2");

    // Load and verify latest
    let loaded = rce_checkpoint_repo::load_checkpoint(&pool, workflow_id)
        .await
        .expect("load")
        .expect("checkpoint exists");

    assert_eq!(loaded.1, 1); // step_index from v2
    assert_eq!(loaded.4, 2); // version is now 2
    assert_eq!(loaded.2, json!({"state": "paused_v2"}));
    assert_eq!(loaded.3, "checksum_v2");
}
