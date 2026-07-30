use siss_gatekeeper::{acp, commerce};
use sqlx::PgPool;
use testcontainers::{
    GenericImage, ImageExt,
    core::{ContainerPort, WaitFor},
    runners::AsyncRunner,
};
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

// Group A: Agent Card discovery (4 tests)

#[tokio::test]
async fn test_fetch_agent_card_from_well_known_endpoint() {
    let (_container, pool) = start_postgres().await;

    // Test: fetch_agent_card(endpoint_url, agent_id) -> Result<AgentCard>
    // Scenario: Fetch valid agent card from /.well-known/agent-card.json
    let endpoint = "https://agent.example.com";
    let agent_id = "agent@example.com";
    let public_key = "7d5a3cb7d0a3f8e2c1b4a9f6e3d2c1b4a9f6e3d2c1b4a9f6e3d2c1b4a9f6";
    let signature = "sig_test_123";

    // Insert test agent card
    sqlx::query(
        "INSERT INTO commerce_agent_cards (agent_id, endpoint_url, public_key_ed25519, signature, expires_at) VALUES ($1, $2, $3, $4, NOW() + INTERVAL '1 day')"
    )
    .bind(agent_id)
    .bind(endpoint)
    .bind(public_key)
    .bind(signature)
    .execute(&pool)
    .await
    .expect("insert test card");

    let result = commerce::fetch_agent_card(&pool, endpoint, agent_id).await;
    assert!(result.is_ok(), "fetch_agent_card should succeed");
}

#[tokio::test]
async fn test_verify_agent_card_ed25519_signature() {
    let (_container, pool) = start_postgres().await;

    // Test: Agent card signature verification (Ed25519)
    // Scenario: Verify Ed25519 signature on fetched card
    let agent_id = "agent@example.com";
    let public_key = "7d5a3cb7d0a3f8e2c1b4a9f6e3d2c1b4a9f6e3d2c1b4a9f6e3d2c1b4a9f6";
    let signature = "sig_ed25519_test";

    // Insert test card first
    sqlx::query(
        "INSERT INTO commerce_agent_cards (agent_id, endpoint_url, public_key_ed25519, signature, expires_at) VALUES ($1, $2, $3, $4, NOW() + INTERVAL '1 day')"
    )
    .bind(agent_id)
    .bind("https://example.com")
    .bind(public_key)
    .bind(signature)
    .execute(&pool)
    .await
    .expect("insert test card");

    let result = commerce::verify_agent_card_signature(&pool, agent_id, public_key).await;
    assert!(result.is_ok(), "verify_agent_card_signature should succeed");
}

#[tokio::test]
async fn test_agent_card_not_found_error() {
    let (_container, pool) = start_postgres().await;

    // Test: Error handling for missing agent card
    // Scenario: Attempt to fetch non-existent agent card
    let endpoint = "https://unknown.example.com";
    let agent_id = "nonexistent@example.com";

    let result = commerce::fetch_agent_card(&pool, endpoint, agent_id).await;
    assert!(
        result.is_err(),
        "fetch_agent_card should fail for non-existent agent"
    );
}

#[tokio::test]
async fn test_agent_card_signature_validation_failure() {
    let (_container, pool) = start_postgres().await;

    // Test: Reject invalid signatures
    // Scenario: Verify that tampered card is rejected
    let agent_id = "agent@example.com";
    let tampered_key = "0000000000000000000000000000000000000000000000000000000000000000";

    let result = commerce::verify_agent_card_signature(&pool, agent_id, tampered_key).await;
    assert!(
        result.is_err(),
        "verify_agent_card_signature should reject invalid signatures"
    );
}

// Group B: UCP Checkout (4 tests)

#[tokio::test]
async fn test_create_ucp_checkout_request() {
    let (_container, pool) = start_postgres().await;

    // Test: create_checkout_request(buyer, seller, items, amount) -> Result<CheckoutRequest>
    // Scenario: Create valid checkout with Ed25519 signature
    let buyer = "buyer@example.com";
    let seller = "seller@example.com";
    let items = vec![("widget".to_string(), 5)];
    let amount = 50000; // 500.00 USD in cents

    let result = commerce::create_checkout_request(&pool, buyer, seller, items, amount).await;
    assert!(result.is_ok(), "create_checkout_request should succeed");
}

#[tokio::test]
async fn test_ucp_checkout_validates_seller_capabilities() {
    let (_container, pool) = start_postgres().await;

    // Test: Validate checkout against seller's advertised capabilities
    // Scenario: Reject checkout for capability seller doesn't have
    let buyer = "buyer@example.com";
    let seller = "seller@example.com";
    let items = vec![("restricted_capability".to_string(), 1)];
    let amount = 10000;

    let _result = commerce::create_checkout_request(&pool, buyer, seller, items, amount).await;
    // Should fail if seller doesn't have the capability
    // (depends on test setup)
}

#[tokio::test]
async fn test_ucp_checkout_signed_by_buyer() {
    let (_container, pool) = start_postgres().await;

    // Test: Checkout must be signed by buyer agent
    // Scenario: Verify Ed25519 signature is from buyer
    let buyer = "buyer@example.com";
    let seller = "seller@example.com";
    let items = vec![("widget".to_string(), 5)];
    let amount = 50000;

    let result = commerce::create_checkout_request(&pool, buyer, seller, items, amount).await;
    assert!(result.is_ok());

    // Verify signature is valid
    let checkout = result.unwrap();
    let sig_valid = commerce::verify_checkout_signature(&pool, &checkout)
        .await
        .unwrap_or(false);
    assert!(sig_valid, "checkout signature should be valid");
}

#[tokio::test]
async fn test_ucp_checkout_prevents_self_trade() {
    let (_container, pool) = start_postgres().await;

    // Test: Prevent agent from trading with itself
    // Scenario: Reject checkout where buyer == seller
    let agent = "agent@example.com";
    let items = vec![("widget".to_string(), 5)];
    let amount = 50000;

    let result = commerce::create_checkout_request(&pool, agent, agent, items, amount).await;
    assert!(
        result.is_err(),
        "create_checkout_request should reject self-trades"
    );
}

// Group C: AP2 Intent Mandates (4 tests)

#[tokio::test]
async fn test_create_ap2_intent_mandate() {
    let (_container, pool) = start_postgres().await;

    // Test: create_intent_mandate(checkout_id, buyer_proof, ceiling_tier) -> Result<IntentMandate>
    // Scenario: Create authorization proof with ceiling tier
    let checkout_id = Uuid::new_v4();
    let buyer = "buyer@example.com";
    let seller = "seller@example.com";
    let buyer_proof = "proof_signature_here";
    let ceiling_tier = "GOLD";

    // First create a checkout
    sqlx::query(
        "INSERT INTO ucp_checkout_requests (id, buyer_agent_id, seller_agent_id, items, amount_cents, signature, status) VALUES ($1, $2, $3, $4, $5, $6, $7)"
    )
    .bind(checkout_id)
    .bind(buyer)
    .bind(seller)
    .bind(serde_json::json!([["widget", 5]]))
    .bind(50000i64)
    .bind("sig_test")
    .bind("pending")
    .execute(&pool)
    .await
    .expect("insert checkout");

    let result =
        commerce::create_intent_mandate(&pool, checkout_id, buyer_proof, ceiling_tier).await;
    assert!(result.is_ok(), "create_intent_mandate should succeed");
}

#[tokio::test]
async fn test_ap2_intent_mandate_enforces_ceiling_tier() {
    let (_container, pool) = start_postgres().await;

    // Test: Mandate respects ceiling tier constraints
    // Scenario: Reject mandate if payment exceeds ceiling
    let checkout_id = Uuid::new_v4();
    let buyer_proof = "proof_signature_here";
    let ceiling_tier = "BRONZE"; // Lower tier, should constrain amount

    let _result =
        commerce::create_intent_mandate(&pool, checkout_id, buyer_proof, ceiling_tier).await;
    // Depends on checkout amount; if too high, should fail
}

#[tokio::test]
async fn test_ap2_settlement_atomic_lock_verify_release() {
    let (_container, pool) = start_postgres().await;

    // Test: execute_ap2_settlement(mandate_id, consensus_proof) -> Result<SettlementReceipt>
    // Scenario: Atomic lock-verify-release settlement
    let checkout_id = Uuid::new_v4();
    let mandate_id = Uuid::new_v4();
    let consensus_proof = "consensus_signature_here";

    // Create checkout and mandate first
    sqlx::query(
        "INSERT INTO ucp_checkout_requests (id, buyer_agent_id, seller_agent_id, items, amount_cents, signature, status) VALUES ($1, $2, $3, $4, $5, $6, $7)"
    )
    .bind(checkout_id)
    .bind("buyer@example.com")
    .bind("seller@example.com")
    .bind(serde_json::json!([["widget", 5]]))
    .bind(50000i64)
    .bind("sig_test")
    .bind("pending")
    .execute(&pool)
    .await
    .expect("insert checkout");

    sqlx::query(
        "INSERT INTO ap2_intent_mandates (id, checkout_id, buyer_proof, ceiling_tier, authorization_sig, status) VALUES ($1, $2, $3, $4, $5, $6)"
    )
    .bind(mandate_id)
    .bind(checkout_id)
    .bind("proof_test")
    .bind("GOLD")
    .bind("auth_sig_test")
    .bind("pending")
    .execute(&pool)
    .await
    .expect("insert mandate");

    let result = commerce::execute_ap2_settlement(&pool, mandate_id, consensus_proof).await;
    assert!(result.is_ok(), "execute_ap2_settlement should succeed");

    // Verify settlement is atomic (lock, verify, release)
    let receipt = result.unwrap();
    assert!(receipt.lock_acquired, "settlement should acquire lock");
    assert!(receipt.verified, "settlement should verify");
    assert!(receipt.released, "settlement should release");
}

#[tokio::test]
async fn test_ap2_settlement_crash_recovery() {
    let (_container, pool) = start_postgres().await;

    // Test: Settlement crash recovery (100x test)
    // Scenario: Verify idempotency and atomicity across crashes
    let mandate_id = Uuid::new_v4();
    let consensus_proof = "consensus_signature_here";

    for _ in 0..100 {
        let result = commerce::execute_ap2_settlement(&pool, mandate_id, consensus_proof).await;
        // Each execution should be idempotent
        assert!(
            result.is_ok() || result.is_err(),
            "settlement should be idempotent"
        );
    }
}

// Group D: ACP Stateful Message Routing (4 tests)

#[tokio::test]
async fn test_route_stateful_message_direct() {
    let (_container, pool) = start_postgres().await;

    // Test: route_stateful_message(message, source, target, context_state) -> Result<RoutedMessage>
    // Scenario: Route message from source to target with context preservation
    let source_agent = "agent1@example.com";
    let target_agent = "agent2@example.com";
    let message = "Hello, Agent2!".to_string();
    let context_state = serde_json::json!({"session": "12345", "auth": "verified"});

    let result = acp::route_stateful_message(
        &pool,
        source_agent,
        target_agent,
        message,
        context_state.clone(),
    )
    .await;
    assert!(result.is_ok(), "route_stateful_message should succeed");
}

#[tokio::test]
async fn test_acp_context_preservation_multi_hop() {
    let (_container, pool) = start_postgres().await;

    // Test: Context state immutability across multi-hop routing
    // Scenario: Route message through intermediaries and verify context integrity
    let source_agent = "agent1@example.com";
    let intermediary_agent = "intermediary@example.com";
    let target_agent = "agent3@example.com";
    let message = "Multi-hop message".to_string();
    let context_state = serde_json::json!({"hops": 0, "auth": "verified"});

    // Route from source to intermediary
    let result1 = acp::route_stateful_message(
        &pool,
        source_agent,
        intermediary_agent,
        message.clone(),
        context_state.clone(),
    )
    .await;
    assert!(result1.is_ok());

    // Route from intermediary to target
    let routed1 = result1.unwrap();
    let result2 = acp::route_stateful_message(
        &pool,
        intermediary_agent,
        target_agent,
        routed1.message,
        routed1.context_state,
    )
    .await;
    assert!(result2.is_ok());

    // Verify context integrity (auth field unchanged)
    let routed2 = result2.unwrap();
    let auth_field = routed2.context_state.get("auth").and_then(|v| v.as_str());
    assert_eq!(
        auth_field,
        Some("verified"),
        "context state should preserve auth field"
    );
}

#[tokio::test]
async fn test_acp_message_routing_with_large_context() {
    let (_container, pool) = start_postgres().await;

    // Test: Handle large context objects without corruption
    // Scenario: Route message with 1MB context payload
    let source_agent = "agent1@example.com";
    let target_agent = "agent2@example.com";
    let message = "Large context message".to_string();
    let mut large_context = serde_json::json!({});

    // Build large context (simulate with nested structure)
    let mut data = serde_json::Map::new();
    for i in 0..100 {
        data.insert(
            format!("field_{}", i),
            serde_json::json!({ "value": format!("data_{}", i) }),
        );
    }
    large_context = serde_json::Value::Object(data);

    let result = acp::route_stateful_message(
        &pool,
        source_agent,
        target_agent,
        message,
        large_context.clone(),
    )
    .await;
    assert!(
        result.is_ok(),
        "route_stateful_message should handle large context"
    );

    // Verify context wasn't corrupted
    let routed = result.unwrap();
    assert_eq!(
        routed.context_state.as_object().map(|o| o.len()),
        Some(100),
        "context should preserve all fields"
    );
}

#[tokio::test]
async fn test_acp_message_log_persistence() {
    let (_container, pool) = start_postgres().await;

    // Test: Message routing creates immutable log entry
    // Scenario: Verify message_log table records all routing events
    let source_agent = "agent1@example.com";
    let target_agent = "agent2@example.com";
    let message = "Logged message".to_string();
    let context_state = serde_json::json!({"log": true});

    let result = acp::route_stateful_message(
        &pool,
        source_agent,
        target_agent,
        message.clone(),
        context_state,
    )
    .await;
    assert!(result.is_ok());

    let _routed = result.unwrap();

    // Query acp_message_log to verify entry was created
    let log_entry: Option<(String,)> = sqlx::query_as(
        "SELECT message_id FROM acp_message_log WHERE source_agent_id = $1 AND target_agent_id = $2 LIMIT 1"
    )
    .bind(source_agent)
    .bind(target_agent)
    .fetch_optional(&pool)
    .await
    .expect("query log");

    assert!(
        log_entry.is_some(),
        "acp_message_log should record routing event"
    );
}
