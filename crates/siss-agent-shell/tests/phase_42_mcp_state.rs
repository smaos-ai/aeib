use siss_agent_shell::swarm_mcp_client::SwarmMcpClient;
/// Phase 42 MCP Integration Tests
/// - Concurrency: 100 parallel updates with same idempotency_key
/// - Retry Idempotency: repeated calls don't duplicate state
/// - Latency: <2ms per operation target
/// - Flat-file ban: STATE.md / MEMORY.md rejected
use siss_agent_shell::swarm_mcp_server::{GlobalStateFilter, SwarmMcpServer, SwarmStatePayload};
use std::sync::Arc;
use uuid::Uuid;

#[tokio::test]
async fn test_i3_idempotency_concurrent_updates() {
    let server = SwarmMcpServer::new("sqlite::memory:").await.unwrap();
    let server = Arc::new(server);
    let idempotency_key = Uuid::new_v4().to_string();
    let mut handles = vec![];

    // Fire 100 concurrent requests with the SAME idempotency key
    for i in 0..100 {
        let server = Arc::clone(&server);
        let key = idempotency_key.clone();

        let handle = tokio::spawn(async move {
            let req = SwarmStatePayload {
                idempotency_key: key,
                agent_id: format!("agent-{}", i % 5),
                phase: "PHASE_42".to_string(),
                status: "RUNNING".to_string(),
                payload_json: None,
            };
            server.update_swarm_state(req).await
        });

        handles.push(handle);
    }

    // Await all tasks
    for handle in handles {
        let result = handle.await;
        assert!(result.is_ok());
        assert!(result.unwrap().is_ok());
    }

    // Verify exactly ONE entry exists (idempotent via PRIMARY KEY)
    let state = server
        .get_global_state(GlobalStateFilter { phase_filter: None })
        .await
        .unwrap();
    assert_eq!(
        state.len(),
        1,
        "State should be deduplicated despite 100 concurrent updates"
    );
    assert_eq!(state[0].idempotency_key, idempotency_key);
}

#[tokio::test]
async fn test_i4_latency_benchmark() {
    let server = SwarmMcpServer::new("sqlite::memory:").await.unwrap();

    let req = SwarmStatePayload {
        idempotency_key: Uuid::new_v4().to_string(),
        agent_id: "latency_tester".into(),
        phase: "BENCH".into(),
        status: "RUNNING".into(),
        payload_json: None,
    };

    let start = std::time::Instant::now();
    for _ in 0..1000 {
        server.update_swarm_state(req.clone()).await.unwrap();
    }
    let duration = start.elapsed();
    let avg_micros = duration.as_micros() / 1000;

    // Target: < 2ms per call (in-memory SQLite with WAL)
    // Allowing 5ms per call for CI headroom
    assert!(
        avg_micros < 5000,
        "Latency threshold breached: {} microseconds per call",
        avg_micros
    );
}

#[tokio::test]
async fn test_i7_degraded_mode_graceful_fallback() {
    let client = SwarmMcpClient::new("/tmp/nonexistent_socket.sock");

    let req = SwarmStatePayload {
        idempotency_key: Uuid::new_v4().to_string(),
        agent_id: "agent-1".into(),
        phase: "PHASE_42".into(),
        status: "RUNNING".into(),
        payload_json: None,
    };

    // Should NOT return error, should buffer locally
    let result = client.update_swarm_state(req.clone()).await;
    assert!(
        result.is_ok(),
        "Client must degrade gracefully without crashing the agent"
    );

    // Fetch from degraded mode buffer
    let state = client
        .get_global_state(GlobalStateFilter { phase_filter: None })
        .await
        .unwrap();
    assert_eq!(state.len(), 1);
    assert_eq!(state[0].idempotency_key, req.idempotency_key);
}

#[test]
fn test_i1_flat_file_write_ban() {
    let client = SwarmMcpClient::new("/tmp/smaos.sock");

    // STATE.md should be rejected
    assert!(
        client.block_flat_file_writes("project/STATE.md").is_err(),
        "STATE.md writes must be rejected"
    );

    // MEMORY.md should be rejected
    assert!(
        client.block_flat_file_writes("project/MEMORY.md").is_err(),
        "MEMORY.md writes must be rejected"
    );

    // Source code should be allowed
    assert!(
        client.block_flat_file_writes("project/src/main.rs").is_ok(),
        "Code writes must be allowed"
    );
}

#[tokio::test]
async fn test_phase_filter_in_global_state() {
    let server = SwarmMcpServer::new("sqlite::memory:").await.unwrap();

    // Insert states for different phases
    for phase in &["PHASE_40", "PHASE_41", "PHASE_42"] {
        let req = SwarmStatePayload {
            idempotency_key: Uuid::new_v4().to_string(),
            agent_id: "agent-1".into(),
            phase: phase.to_string(),
            status: "RUNNING".into(),
            payload_json: None,
        };
        server.update_swarm_state(req).await.unwrap();
    }

    // Filter by phase
    let phase_42_only = server
        .get_global_state(GlobalStateFilter {
            phase_filter: Some("PHASE_42".into()),
        })
        .await
        .unwrap();
    assert_eq!(phase_42_only.len(), 1);
    assert_eq!(phase_42_only[0].phase, "PHASE_42");

    // No filter returns all
    let all = server
        .get_global_state(GlobalStateFilter { phase_filter: None })
        .await
        .unwrap();
    assert_eq!(all.len(), 3);
}
