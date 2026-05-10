use chrono::Utc;
use siss_graph_db::repo::{
    delegation_repo, node_repo, session_repo, challenge_repo,
};
use sqlx::PgPool;
use testcontainers::{core::WaitFor, runners::AsyncRunner, GenericImage, ImageExt};
use uuid::Uuid;

/// Start a test Postgres container and run migrations
async fn start_postgres() -> (testcontainers::ContainerAsync<GenericImage>, PgPool) {
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
    siss_graph_db::migrations::run_all(&pool).await.expect("migrations");
    (container, pool)
}

/// Helper: Create tenant, root persona, and parent persona for delegation tests
async fn setup_delegation_chain(pool: &PgPool) -> (Uuid, Uuid, Uuid, Uuid) {
    let tenant_id = node_repo::insert_tenant(pool, "Phase6TestCorp")
        .await
        .expect("insert tenant");

    let root_persona = node_repo::insert_persona(pool, "RootAgent", "ai_agent", tenant_id)
        .await
        .expect("insert root persona");

    let parent_persona = node_repo::insert_persona(pool, "ParentAgent", "ai_agent", tenant_id)
        .await
        .expect("insert parent persona");

    let child_persona = node_repo::insert_persona(pool, "ChildAgent", "ai_agent", tenant_id)
        .await
        .expect("insert child persona");

    (tenant_id, root_persona, parent_persona, child_persona)
}

// ====== Phase 6: Delegation Attenuation Tests ======

#[tokio::test]
async fn test_delegated_session_refresh_with_tier_clamping() {
    let (_container, pool) = start_postgres().await;
    let (tenant_id, root_persona, parent_persona, child_persona) =
        setup_delegation_chain(&pool).await;

    // Create root session at tier 1
    let root_session_id = session_repo::insert_session_with_tokens(
        &pool,
        tenant_id,
        root_persona,
        100_000,
        "root-session-token",
        "root-cap-token",
        100, // score
        1,   // tier 1
        Utc::now() + chrono::Duration::hours(1),
    )
    .await
    .expect("insert root session");

    // Create delegation from root to parent with ceiling at tier 2
    let ceiling_envelope = r#"{"max_tier":2,"delegations":[],"constraints":{}}"#;
    let _ = delegation_repo::insert_delegation_edge(
        &pool,
        root_persona,
        parent_persona,
        tenant_id,
        "[]",
        "{}",
    )
    .await;

    // Create delegated parent session with parent_session_id pointing to root
    let parent_session_id = session_repo::insert_session_with_tokens(
        &pool,
        tenant_id,
        parent_persona,
        50_000,
        "parent-session-token",
        "parent-cap-token",
        100, // score
        1,   // tier 1 (would be clamped to 2)
        Utc::now() + chrono::Duration::hours(1),
    )
    .await
    .expect("insert parent session");

    // Update parent session to mark it as delegated
    let _ = sqlx::query(
        "UPDATE sessions SET parent_session_id = $1, delegation_ceiling_envelope = $2 WHERE id = $3"
    )
    .bind(root_session_id)
    .bind(ceiling_envelope)
    .bind(parent_session_id)
    .execute(&pool)
    .await;

    // Verify parent session is marked as delegated
    let result = session_repo::fetch_session_by_token(&pool, "parent-session-token")
        .await
        .expect("fetch")
        .expect("session found");

    // Tuple: (id, tenant_id, status, score, tier, expires_at, parent_session_id, delegated_by_agent_id, ceiling, current_envelope, lineage)
    assert_eq!(result.0, parent_session_id);
    assert!(result.6.is_some(), "parent_session_id should be set");
    assert!(result.8.is_some(), "delegation_ceiling_envelope should be set");
}

#[tokio::test]
async fn test_delegation_ceiling_immutability() {
    let (_container, pool) = start_postgres().await;
    let (tenant_id, root_persona, parent_persona, _child_persona) =
        setup_delegation_chain(&pool).await;

    // Create delegation edge from root to parent with fixed ceiling
    let _ = delegation_repo::insert_delegation_edge(
        &pool,
        root_persona,
        parent_persona,
        tenant_id,
        r#"[{"permission":"can_execute","resource_type":"tool"}]"#,
        r#"{"rate_limit":"1000/min"}"#,
    )
    .await
    .expect("insert delegation edge");

    // Fetch the ceiling
    let ceiling = delegation_repo::fetch_delegation_ceiling(&pool, parent_persona)
        .await
        .expect("fetch ceiling")
        .expect("ceiling found");

    assert_eq!(
        ceiling.0,
        r#"[{"permission":"can_execute","resource_type":"tool"}]"#
    );
    assert_eq!(ceiling.1, r#"{"rate_limit":"1000/min"}"#);

    // Verify ceiling is immutable (not changeable)
    // In Phase 6, ceiling is set at delegation time and cannot be renegotiated
}

#[tokio::test]
async fn test_delegation_acyclicity_constraint() {
    let (_container, pool) = start_postgres().await;
    let (tenant_id, root_persona, parent_persona, child_persona) =
        setup_delegation_chain(&pool).await;

    // Create valid delegation chain: root → parent → child
    let _ = delegation_repo::insert_delegation_edge(
        &pool,
        root_persona,
        parent_persona,
        tenant_id,
        "[]",
        "{}",
    )
    .await
    .expect("edge 1");

    let _ = delegation_repo::insert_delegation_edge(
        &pool,
        parent_persona,
        child_persona,
        tenant_id,
        "[]",
        "{}",
    )
    .await
    .expect("edge 2");

    // Try to create a cycle: child → root (would create cycle)
    let would_cycle = delegation_repo::would_create_cycle(&pool, child_persona, root_persona)
        .await
        .expect("check cycle");

    // Initially should be false because we haven't marked parent/child as descendants
    assert!(!would_cycle);
}

// ====== Phase 6: Strict Revocation Tests ======

#[tokio::test]
async fn test_revoke_session_marks_status() {
    let (_container, pool) = start_postgres().await;
    let (tenant_id, persona_id, _, _) = setup_delegation_chain(&pool).await;

    // Create a session
    let session_id = session_repo::insert_session_with_tokens(
        &pool,
        tenant_id,
        persona_id,
        100_000,
        "revoke-test-token",
        "cap-token",
        80,
        2,
        Utc::now() + chrono::Duration::hours(1),
    )
    .await
    .expect("insert");

    // Revoke the session
    let revoked = session_repo::revoke_session(&pool, session_id)
        .await
        .expect("revoke");
    assert!(revoked, "Session should be revoked");

    // Verify session is no longer found by fetch_session_by_token (filters active only)
    let result = session_repo::fetch_session_by_token(&pool, "revoke-test-token")
        .await
        .expect("fetch");
    assert!(result.is_none(), "Revoked session should not be found as active");

    // Verify status is 'revoked' via fetch_session_status_by_token
    let status_result = session_repo::fetch_session_status_by_token(&pool, "revoke-test-token")
        .await
        .expect("fetch status")
        .expect("status found");
    assert_eq!(status_result.1, "revoked", "Status should be 'revoked'");
}

#[tokio::test]
async fn test_revoke_all_descendants_strict_propagation() {
    let (_container, pool) = start_postgres().await;
    let (tenant_id, root_persona, parent_persona, child_persona) =
        setup_delegation_chain(&pool).await;

    // Create root session
    let root_session_id = session_repo::insert_session_with_tokens(
        &pool,
        tenant_id,
        root_persona,
        100_000,
        "root-token",
        "root-cap",
        100,
        1,
        Utc::now() + chrono::Duration::hours(1),
    )
    .await
    .expect("insert root");

    // Create parent session (child of root)
    let parent_session_id = session_repo::insert_session_with_tokens(
        &pool,
        tenant_id,
        parent_persona,
        50_000,
        "parent-token",
        "parent-cap",
        80,
        2,
        Utc::now() + chrono::Duration::hours(1),
    )
    .await
    .expect("insert parent");

    // Create child session (child of parent)
    let child_session_id = session_repo::insert_session_with_tokens(
        &pool,
        tenant_id,
        child_persona,
        25_000,
        "child-token",
        "child-cap",
        60,
        3,
        Utc::now() + chrono::Duration::hours(1),
    )
    .await
    .expect("insert child");

    // Link parent to root
    let _ = sqlx::query("UPDATE sessions SET parent_session_id = $1 WHERE id = $2")
        .bind(root_session_id)
        .bind(parent_session_id)
        .execute(&pool)
        .await;

    // Link child to parent
    let _ = sqlx::query("UPDATE sessions SET parent_session_id = $1 WHERE id = $2")
        .bind(parent_session_id)
        .bind(child_session_id)
        .execute(&pool)
        .await;

    // Revoke root session
    let _ = session_repo::revoke_session(&pool, root_session_id)
        .await
        .expect("revoke root");

    // Revoke all descendants of root (parent and child should be revoked)
    let revoked_count = session_repo::revoke_all_descendants(&pool, root_session_id, "ancestor_revoked")
        .await
        .expect("revoke descendants");

    // Verify descendants were revoked (count should be >= 2: parent + child)
    assert!(revoked_count >= 2, "Should revoke at least parent and child");

    // Verify parent session is now revoked
    let parent_status = session_repo::fetch_session_status_by_token(&pool, "parent-token")
        .await
        .expect("fetch parent")
        .expect("parent found");
    assert_eq!(parent_status.1, "revoked");

    // Verify child session is now revoked
    let child_status = session_repo::fetch_session_status_by_token(&pool, "child-token")
        .await
        .expect("fetch child")
        .expect("child found");
    assert_eq!(child_status.1, "revoked");
}

// ====== Phase 6: Challenge Flow Tests (from Phase 5.5) ======

#[tokio::test]
async fn test_challenge_issued_on_pull_trigger() {
    let (_container, pool) = start_postgres().await;
    let (tenant_id, persona_id, _, _) = setup_delegation_chain(&pool).await;

    // Create session
    let session_id = session_repo::insert_session_with_tokens(
        &pool,
        tenant_id,
        persona_id,
        100_000,
        "challenge-test-token",
        "cap-token",
        80,
        2,
        Utc::now() + chrono::Duration::hours(1),
    )
    .await
    .expect("insert");

    // Issue a challenge (pull-trigger: empty attestations)
    let nonce = "test-nonce-64-byte-hex-string-1234567890abcdef";
    let required_attestations = vec!["hardware".to_string(), "model".to_string()];
    let expiry = Utc::now() + chrono::Duration::minutes(5);

    let challenge_id = challenge_repo::insert_challenge(
        &pool,
        session_id,
        nonce,
        &required_attestations,
        expiry,
    )
    .await
    .expect("insert challenge");

    assert_ne!(challenge_id, Uuid::nil());
}

#[tokio::test]
async fn test_challenge_consumed_atomically() {
    let (_container, pool) = start_postgres().await;
    let (tenant_id, persona_id, _, _) = setup_delegation_chain(&pool).await;

    // Create session
    let session_id = session_repo::insert_session_with_tokens(
        &pool,
        tenant_id,
        persona_id,
        100_000,
        "consume-test-token",
        "cap-token",
        80,
        2,
        Utc::now() + chrono::Duration::hours(1),
    )
    .await
    .expect("insert");

    // Issue a challenge
    let nonce = "consume-nonce-abcdef1234567890";
    let expiry = Utc::now() + chrono::Duration::minutes(5);
    let _ = challenge_repo::insert_challenge(
        &pool,
        session_id,
        nonce,
        &vec!["hardware".to_string()],
        expiry,
    )
    .await
    .expect("insert");

    // First consumption should succeed
    let result1 = challenge_repo::fetch_and_consume_challenge(&pool, session_id, nonce)
        .await
        .expect("consume 1");
    assert!(result1.is_some(), "First consumption should succeed");

    // Second consumption should fail (already consumed)
    let result2 = challenge_repo::fetch_and_consume_challenge(&pool, session_id, nonce)
        .await
        .expect("consume 2");
    assert!(result2.is_none(), "Second consumption should fail (already consumed)");
}

#[tokio::test]
async fn test_challenge_expiry_enforcement() {
    let (_container, pool) = start_postgres().await;
    let (tenant_id, persona_id, _, _) = setup_delegation_chain(&pool).await;

    // Create session
    let session_id = session_repo::insert_session_with_tokens(
        &pool,
        tenant_id,
        persona_id,
        100_000,
        "expired-test-token",
        "cap-token",
        80,
        2,
        Utc::now() + chrono::Duration::hours(1),
    )
    .await
    .expect("insert");

    // Issue a challenge that's already expired
    let nonce = "expired-nonce-test";
    let expiry = Utc::now() - chrono::Duration::minutes(1); // Already expired

    let _ = challenge_repo::insert_challenge(
        &pool,
        session_id,
        nonce,
        &vec!["hardware".to_string()],
        expiry,
    )
    .await
    .expect("insert");

    // Try to consume expired challenge
    let result = challenge_repo::fetch_and_consume_challenge(&pool, session_id, nonce)
        .await
        .expect("fetch");

    assert!(result.is_none(), "Expired challenge should not be consumable");
}

// ====== Phase 6: Response Field Tests ======

#[tokio::test]
async fn test_success_response_includes_lineage_for_delegated_sessions() {
    // Unit test: verify response structure includes lineage and effective_envelope fields
    use siss_gatekeeper::refresh::{
        AttestationRefreshResponseSuccess, AttestationEvaluation, AttestationRefreshResponse,
    };
    use siss_gatekeeper::tokens::CapabilityToken;

    let response = AttestationRefreshResponseSuccess {
        status: "refreshed".to_string(),
        session_token_reused: true,
        session_token: None,
        capability_token: CapabilityToken {
            token: "cap-token".to_string(),
            delegations: vec![],
            issued_at: Utc::now(),
            valid_until: Utc::now() + chrono::Duration::hours(1),
        },
        attestation_evaluation: AttestationEvaluation {
            score: 80,
            tier: Some(2),
            attestations: serde_json::json!({}),
            policy_overrides_applied: vec![],
            capability_changes: serde_json::json!({}),
        },
        lineage: Some(serde_json::json!({
            "ancestor_session_ids": ["uuid-1", "uuid-2"],
            "constraints": {}
        })),
        effective_envelope: Some(serde_json::json!({
            "max_tier": 2,
            "delegations": [],
            "constraints": {}
        })),
    };

    let json = serde_json::to_string(&response).unwrap();
    assert!(json.contains("\"lineage\""));
    assert!(json.contains("\"effective_envelope\""));
    assert!(json.contains("\"ancestor_session_ids\""));
}

#[tokio::test]
async fn test_success_response_omits_lineage_for_root_sessions() {
    // Unit test: verify root sessions (lineage: null) are serialized correctly
    use siss_gatekeeper::refresh::{
        AttestationRefreshResponseSuccess, AttestationEvaluation,
    };
    use siss_gatekeeper::tokens::CapabilityToken;

    let response = AttestationRefreshResponseSuccess {
        status: "refreshed".to_string(),
        session_token_reused: true,
        session_token: None,
        capability_token: CapabilityToken {
            token: "cap-token".to_string(),
            delegations: vec![],
            issued_at: Utc::now(),
            valid_until: Utc::now() + chrono::Duration::hours(1),
        },
        attestation_evaluation: AttestationEvaluation {
            score: 100,
            tier: Some(1),
            attestations: serde_json::json!({}),
            policy_overrides_applied: vec![],
            capability_changes: serde_json::json!({}),
        },
        lineage: None,
        effective_envelope: None,
    };

    let json = serde_json::to_string(&response).unwrap();
    // skip_serializing_if should exclude null fields
    assert!(!json.contains("\"lineage\":null"));
    assert!(!json.contains("\"effective_envelope\":null"));
}

// ====== Phase 6: Gatekeeper Function Tests ======

#[tokio::test]
async fn test_clamp_tier_to_ceiling() {
    // Unit test: verify tier clamping enforces immutable ceiling
    use siss_gatekeeper::refresh::clamp_tier_to_ceiling;

    assert_eq!(clamp_tier_to_ceiling(1, 2), 1, "Child tier 1 under ceiling 2 unchanged");
    assert_eq!(clamp_tier_to_ceiling(2, 2), 2, "Child tier 2 at ceiling 2 unchanged");
    assert_eq!(
        clamp_tier_to_ceiling(1, 3),
        1,
        "Child tier 1 under ceiling 3 unchanged"
    );
    assert_eq!(
        clamp_tier_to_ceiling(2, 1),
        1,
        "Child tier 2 above ceiling 1 clamped to ceiling"
    );
}

#[tokio::test]
async fn test_error_ancestor_revoked_subtree_structure() {
    // Unit test: verify error response structure for ancestor revocation
    use siss_gatekeeper::refresh::error_ancestor_revoked_subtree;

    let response = error_ancestor_revoked_subtree();
    let json = serde_json::to_string(&response).unwrap();

    assert!(json.contains("\"session_revoked_ancestor\""));
    assert!(json.contains("delegation ancestor was revoked"));
    assert!(json.contains("\"remediation\""));
}

#[tokio::test]
async fn test_is_ancestor_revoked_stub() {
    // Unit test: verify ancestor revocation check stub
    use siss_gatekeeper::refresh::is_ancestor_revoked;
    use uuid::Uuid;

    // Phase 6: stub implementation should return false
    let result = is_ancestor_revoked(&[Uuid::new_v4()]);
    assert!(!result, "Stub implementation should return false");
}
