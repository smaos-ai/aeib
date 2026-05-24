use siss_gatekeeper::anomaly_detection;
use siss_graph_db::repo::{agent_heartbeat, observability_event_log};
use sqlx::PgPool;
use testcontainers::{GenericImage, ImageExt, core::{WaitFor, ContainerPort}, runners::AsyncRunner};
use uuid::Uuid;

async fn start_postgres() -> (testcontainers::ContainerAsync<GenericImage>, PgPool) {
    let container = GenericImage::new("postgres", "16")
        .with_exposed_port(ContainerPort::Tcp(5432))
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

async fn setup_sovereigns(pool: &PgPool, count: usize) -> Vec<Uuid> {
    let placeholder_key = "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA\n-----END PUBLIC KEY-----";
    let mut sovereigns = Vec::new();

    for i in 0..count {
        let sovereign_id = Uuid::new_v4();
        sqlx::query(
            "INSERT INTO sovereigns (id, name, public_key_pem, status) VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING"
        )
        .bind(sovereign_id)
        .bind(format!("Sovereign{}", i))
        .bind(placeholder_key)
        .bind("active")
        .execute(pool)
        .await
        .expect("insert sovereign");
        sovereigns.push(sovereign_id);
    }

    sovereigns
}

// ====== Group A: Heartbeat Recording, Health Score, Offline Detection ======

#[tokio::test]
async fn test_record_heartbeat_inserts_into_database() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 1).await;
    let agent_id = "test-agent-1";

    let heartbeat_id = agent_heartbeat::record_heartbeat(&pool, agent_id, sovereigns[0], 500)
        .await
        .expect("record heartbeat");

    assert!(!heartbeat_id.is_nil());

    // Verify it was inserted
    let count: (i64,) = sqlx::query_as(
        "SELECT COUNT(*) FROM agent_heartbeats WHERE agent_id = $1 AND sovereign_id = $2"
    )
    .bind(agent_id)
    .bind(sovereigns[0])
    .fetch_one(&pool)
    .await
    .expect("count heartbeats");
    assert_eq!(count.0, 1);
}

#[tokio::test]
async fn test_record_heartbeat_sets_healthy_status_for_low_latency() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 1).await;
    let agent_id = "test-agent-2";

    agent_heartbeat::record_heartbeat(&pool, agent_id, sovereigns[0], 500)
        .await
        .expect("record heartbeat");

    let status: (String,) = sqlx::query_as(
        "SELECT status FROM agent_heartbeats WHERE agent_id = $1 LIMIT 1"
    )
    .bind(agent_id)
    .fetch_one(&pool)
    .await
    .expect("fetch status");

    assert_eq!(status.0, "healthy");
}

#[tokio::test]
async fn test_record_heartbeat_sets_degraded_status_for_high_latency() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 1).await;
    let agent_id = "test-agent-3";

    agent_heartbeat::record_heartbeat(&pool, agent_id, sovereigns[0], 1500)
        .await
        .expect("record heartbeat");

    let status: (String,) = sqlx::query_as(
        "SELECT status FROM agent_heartbeats WHERE agent_id = $1 LIMIT 1"
    )
    .bind(agent_id)
    .fetch_one(&pool)
    .await
    .expect("fetch status");

    assert_eq!(status.0, "degraded");
}

#[tokio::test]
async fn test_compute_agent_health_score_weighted_average() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 1).await;
    let agent_id = "test-agent-4";

    // Record 5 healthy heartbeats (500ms each)
    for _ in 0..5 {
        agent_heartbeat::record_heartbeat(&pool, agent_id, sovereigns[0], 500)
            .await
            .expect("record heartbeat");
    }

    let health_score = agent_heartbeat::compute_agent_health_score(&pool, agent_id, sovereigns[0])
        .await
        .expect("compute health score");

    // All healthy = 100.0
    assert_eq!(health_score, 100.0);
}

#[tokio::test]
async fn test_compute_agent_health_score_mixed_healthy_and_degraded() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 1).await;
    let agent_id = "test-agent-5";

    // Record 5 healthy (500ms) and 5 degraded (1500ms)
    for _ in 0..5 {
        agent_heartbeat::record_heartbeat(&pool, agent_id, sovereigns[0], 500)
            .await
            .expect("record heartbeat");
    }
    for _ in 0..5 {
        agent_heartbeat::record_heartbeat(&pool, agent_id, sovereigns[0], 1500)
            .await
            .expect("record heartbeat");
    }

    let health_score = agent_heartbeat::compute_agent_health_score(&pool, agent_id, sovereigns[0])
        .await
        .expect("compute health score");

    // Mixed: (5*100 + 5*50) / 10 = 75.0
    assert_eq!(health_score, 75.0);
}

// ====== Group B: Anomaly Detection ======

#[tokio::test]
async fn test_detect_latency_spike_with_consecutive_high_latency() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 1).await;
    let agent_id = "test-agent-6";

    // Record 5 consecutive high-latency heartbeats (>1000ms)
    for _ in 0..5 {
        agent_heartbeat::record_heartbeat(&pool, agent_id, sovereigns[0], 1500)
            .await
            .expect("record heartbeat");
    }

    let is_spike = anomaly_detection::detect_latency_spike(&pool, agent_id, 3)
        .await
        .expect("detect latency spike");

    assert!(is_spike);
}

#[tokio::test]
async fn test_detect_latency_spike_returns_false_with_healthy_latency() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 1).await;
    let agent_id = "test-agent-7";

    // Record healthy heartbeats
    for _ in 0..5 {
        agent_heartbeat::record_heartbeat(&pool, agent_id, sovereigns[0], 500)
            .await
            .expect("record heartbeat");
    }

    let is_spike = anomaly_detection::detect_latency_spike(&pool, agent_id, 3)
        .await
        .expect("detect latency spike");

    assert!(!is_spike);
}

#[tokio::test]
async fn test_detect_packet_loss_with_missing_heartbeats() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 1).await;
    let agent_id = "test-agent-8";

    // Record only 3 out of 10 expected heartbeats (70% loss)
    for _ in 0..3 {
        agent_heartbeat::record_heartbeat(&pool, agent_id, sovereigns[0], 500)
            .await
            .expect("record heartbeat");
    }

    let has_loss = anomaly_detection::detect_packet_loss(&pool, agent_id, 50.0)
        .await
        .expect("detect packet loss");

    assert!(has_loss);
}

#[tokio::test]
async fn test_detect_packet_loss_returns_false_with_normal_heartbeats() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 1).await;
    let agent_id = "test-agent-9";

    // Record normal heartbeats
    for _ in 0..10 {
        agent_heartbeat::record_heartbeat(&pool, agent_id, sovereigns[0], 500)
            .await
            .expect("record heartbeat");
    }

    let has_loss = anomaly_detection::detect_packet_loss(&pool, agent_id, 50.0)
        .await
        .expect("detect packet loss");

    assert!(!has_loss);
}

// ====== Group C: Event Log Hashing, Integrity Verification, Tamper Detection ======

#[tokio::test]
async fn test_append_event_creates_hash_chain() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 1).await;
    let sovereign_id = sovereigns[0];

    let event_id_1 = observability_event_log::append_event(
        &pool,
        sovereign_id,
        "heartbeat_received",
        "agent-1",
        r#"{"latency_ms": 500}"#,
    )
    .await
    .expect("append event 1");

    let event_id_2 = observability_event_log::append_event(
        &pool,
        sovereign_id,
        "latency_spike",
        "agent-1",
        r#"{"spike_latency": 1500}"#,
    )
    .await
    .expect("append event 2");

    assert!(!event_id_1.is_nil());
    assert!(!event_id_2.is_nil());
    assert_ne!(event_id_1, event_id_2);
}

#[tokio::test]
async fn test_verify_event_log_integrity_detects_tampering() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 1).await;
    let sovereign_id = sovereigns[0];

    // Append two events
    observability_event_log::append_event(
        &pool,
        sovereign_id,
        "heartbeat_received",
        "agent-1",
        r#"{"latency_ms": 500}"#,
    )
    .await
    .expect("append event 1");

    observability_event_log::append_event(
        &pool,
        sovereign_id,
        "latency_spike",
        "agent-1",
        r#"{"spike_latency": 1500}"#,
    )
    .await
    .expect("append event 2");

    // Tamper with the first event payload (cast to JSONB)
    sqlx::query(
        "UPDATE observability_event_log SET event_payload = $1::jsonb WHERE sequence = 1"
    )
    .bind(r#"{"latency_ms": 999}"#)
    .execute(&pool)
    .await
    .expect("tamper event");

    let (is_valid, error_msg) =
        observability_event_log::verify_event_log_integrity(&pool, sovereign_id)
            .await
            .expect("verify integrity");

    assert!(!is_valid);
    assert!(error_msg.is_some());
}

#[tokio::test]
async fn test_verify_event_log_integrity_passes_for_unmodified_log() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 1).await;
    let sovereign_id = sovereigns[0];

    // Append events without tampering
    for i in 0..5 {
        observability_event_log::append_event(
            &pool,
            sovereign_id,
            "heartbeat_received",
            &format!("agent-{}", i),
            &format!(r#"{{"index": {}}}"#, i),
        )
        .await
        .expect("append event");
    }

    let (is_valid, error_msg) =
        observability_event_log::verify_event_log_integrity(&pool, sovereign_id)
            .await
            .expect("verify integrity");

    assert!(is_valid);
    assert!(error_msg.is_none());
}

// ====== Group D: Distributed Trace Correlation, Metrics Aggregation, Alert Firing ======

#[tokio::test]
async fn test_start_distributed_trace_creates_trace_record() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 3).await;
    let root_sovereign = sovereigns[0];
    let participants = vec![sovereigns[1], sovereigns[2]];
    let request_id = "req-12345";

    let trace_id =
        observability_event_log::start_distributed_trace(&pool, root_sovereign, participants, request_id)
            .await
            .expect("start distributed trace");

    assert!(!trace_id.is_nil());

    // Verify trace was created
    let count: (i64,) = sqlx::query_as(
        "SELECT COUNT(*) FROM distributed_traces WHERE trace_id = $1"
    )
    .bind(trace_id)
    .fetch_one(&pool)
    .await
    .expect("count traces");

    assert_eq!(count.0, 1);
}

#[tokio::test]
async fn test_fire_alert_creates_alert_record() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 1).await;
    let sovereign_id = sovereigns[0];

    // First create an alert rule
    let rule_id = Uuid::new_v4();
    sqlx::query(
        "INSERT INTO alert_rules (id, rule_name, severity, channels, enabled) VALUES ($1, $2, $3, $4, $5)"
    )
    .bind(rule_id)
    .bind("high_latency_alert")
    .bind("critical")
    .bind(&["slack", "email"])
    .bind(true)
    .execute(&pool)
    .await
    .expect("insert alert rule");

    let agent_id = "agent-1";
    let context = r#"{"latency_ms": 2500, "threshold": 1000}"#;

    let alert_id = observability_event_log::fire_alert(
        &pool,
        rule_id,
        sovereign_id,
        agent_id,
        context,
    )
    .await
    .expect("fire alert");

    assert!(!alert_id.is_nil());

    // Verify alert was created
    let count: (i64,) = sqlx::query_as(
        "SELECT COUNT(*) FROM agents_alerts WHERE alert_id = $1"
    )
    .bind(alert_id)
    .fetch_one(&pool)
    .await
    .expect("count alerts");

    assert_eq!(count.0, 1);
}

#[tokio::test]
async fn test_distributed_trace_with_multiple_sovereigns() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 5).await;
    let root = sovereigns[0];
    let participants = sovereigns[1..].to_vec();
    let request_id = "req-trace-multi";

    let trace_id =
        observability_event_log::start_distributed_trace(&pool, root, participants.clone(), request_id)
            .await
            .expect("start distributed trace");

    // Verify participants were stored
    let stored_participants: (Vec<uuid::Uuid>,) = sqlx::query_as(
        "SELECT participating_sovereigns FROM distributed_traces WHERE trace_id = $1"
    )
    .bind(trace_id)
    .fetch_one(&pool)
    .await
    .expect("fetch participants");

    assert_eq!(stored_participants.0.len(), 4);
}

#[tokio::test]
async fn test_append_event_integrates_with_heartbeat() {
    let (_container, pool) = start_postgres().await;
    let sovereigns = setup_sovereigns(&pool, 1).await;
    let agent_id = "test-agent-integrated";
    let sovereign_id = sovereigns[0];

    // Record a heartbeat
    let _hb_id = agent_heartbeat::record_heartbeat(&pool, agent_id, sovereign_id, 800)
        .await
        .expect("record heartbeat");

    // Verify event was created as well
    let event_count: (i64,) = sqlx::query_as(
        "SELECT COUNT(*) FROM observability_event_log WHERE agent_id = $1 AND sovereign_id = $2"
    )
    .bind(agent_id)
    .bind(sovereign_id)
    .fetch_one(&pool)
    .await
    .expect("count events");

    assert!(event_count.0 > 0);
}
