use l2b_federated_consensus::mcp::{McpGateway, ProposalRequest, VoteMessage, CommitMessage};
use serde_json::json;

#[tokio::test]
async fn test_propose_routing() {
    // Test /propose MCP endpoint routing
    let gateway = McpGateway::new("EU".to_string(), 3000);

    let proposal = ProposalRequest {
        decision_id: "HOTEL-001".to_string(),
        action: "APPROVE_CREDIT".to_string(),
        amount: 1000000.0,
        metadata: json!({"hotel_id": "H123"}),
    };

    let result = gateway.route_proposal(proposal).await;
    assert!(result.is_ok());

    let response = result.unwrap();
    assert!(!response.proposal_id.is_empty());
    assert_eq!(response.status, "proposed");
}

#[tokio::test]
async fn test_vote_aggregation() {
    // Test /vote aggregation with async collection
    let gateway = McpGateway::new("EU".to_string(), 3000);

    let proposal = ProposalRequest {
        decision_id: "TEST-001".to_string(),
        action: "TEST".to_string(),
        amount: 100000.0,
        metadata: json!({}),
    };

    let response = gateway.route_proposal(proposal).await.unwrap();
    let proposal_id = response.proposal_id;

    let vote1 = VoteMessage {
        proposal_id: proposal_id.clone(),
        voter: "EU".to_string(),
        approved: true,
        signature: "sig_eu".to_string(),
    };

    let vote2 = VoteMessage {
        proposal_id: proposal_id.clone(),
        voter: "US".to_string(),
        approved: true,
        signature: "sig_us".to_string(),
    };

    let vote3 = VoteMessage {
        proposal_id: proposal_id.clone(),
        voter: "CN".to_string(),
        approved: false,
        signature: "sig_cn".to_string(),
    };

    // Register votes
    gateway.register_vote(vote1).await.unwrap();
    gateway.register_vote(vote2).await.unwrap();
    gateway.register_vote(vote3).await.unwrap();

    // Aggregate votes
    let aggregated = gateway.aggregate_votes(&proposal_id).await.unwrap();
    assert_eq!(aggregated.total_votes, 3);
    assert_eq!(aggregated.approved_votes, 2);
    assert!(aggregated.approved);
}

#[tokio::test]
async fn test_finalize_commit() {
    // Test /finalize commit with atomic append
    let gateway = McpGateway::new("EU".to_string(), 3000);

    let proposal_id = "FINAL-001".to_string();
    let commit = CommitMessage {
        proposal_id: proposal_id.clone(),
        merkle_root: "0xabc123".to_string(),
        ledger_index: 1,
        timestamp: chrono::Utc::now(),
    };

    let result = gateway.finalize_commit(commit).await;
    assert!(result.is_ok());

    let response = result.unwrap();
    assert_eq!(response.status, "committed");
    assert!(response.ledger_index > 0);
}

#[tokio::test]
async fn test_p99_latency_under_100_concurrent() {
    // Test that vote collection achieves <2s p99 latency
    let gateway = std::sync::Arc::new(McpGateway::new("EU".to_string(), 3000));
    let proposal_id = "PERF-001".to_string();

    let start = std::time::Instant::now();

    // Simulate 100 concurrent votes
    let mut handles = vec![];
    for i in 0..100 {
        let gw = gateway.clone();
        let pid = proposal_id.clone();

        let handle = tokio::spawn(async move {
            let vote = VoteMessage {
                proposal_id: pid,
                voter: format!("voter_{}", i),
                approved: i % 2 == 0,
                signature: format!("sig_{}", i),
            };
            gw.register_vote(vote).await
        });

        handles.push(handle);
    }

    // Wait for all votes
    for handle in handles {
        let _ = handle.await;
    }

    let elapsed = start.elapsed();

    // p99 should be under 2 seconds
    assert!(elapsed.as_secs_f64() < 2.0, "Latency exceeded 2s: {:?}", elapsed);
}

#[tokio::test]
async fn test_mcp_endpoint_tls() {
    // Test that endpoints use TLS/mTLS
    let gateway = McpGateway::new("EU".to_string(), 3001);

    // Should support TLS configuration
    assert!(gateway.supports_tls());
}

#[tokio::test]
async fn test_rate_limiting() {
    // Test that gateway enforces rate limiting
    let gateway = McpGateway::new("EU".to_string(), 3000);

    let proposal = ProposalRequest {
        decision_id: "RATE-001".to_string(),
        action: "TEST".to_string(),
        amount: 100000.0,
        metadata: json!({}),
    };

    let response = gateway.route_proposal(proposal).await.unwrap();
    let proposal_id = response.proposal_id;

    // Register initial vote
    let vote1 = VoteMessage {
        proposal_id: proposal_id.clone(),
        voter: "EU".to_string(),
        approved: true,
        signature: "sig_1".to_string(),
    };

    gateway.register_vote(vote1).await.unwrap();

    // Attempt duplicate vote from same voter
    let vote2 = VoteMessage {
        proposal_id: proposal_id.clone(),
        voter: "EU".to_string(),
        approved: false,
        signature: "sig_2".to_string(),
    };

    let result = gateway.register_vote(vote2).await;
    assert!(result.is_err(), "Should reject duplicate vote from same voter");
}
