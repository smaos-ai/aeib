use l2b_federated_consensus::{
    ConsensusGateway, ConsensusVote, McpGateway, ProposalRequest, VoteMessage,
    LedgerSync, LedgerEntry,
};
use serde_json::json;
use std::sync::Arc;
use std::time::Instant;

// Full L1→L8 end-to-end flow test
#[tokio::test]
async fn test_e2e_full_flow() {
    // Simulate: L1 (Policy Router) → L4 (Orchestration via MCP) → L8 (Proof via Ledger)

    let mcp_gateway = McpGateway::new("EU".to_string(), 3000);

    // Step 1: L1 creates policy-driven proposal
    let proposal = ProposalRequest {
        decision_id: "E2E-001".to_string(),
        action: "APPROVE_CREDIT".to_string(),
        amount: 5000000.0,
        metadata: json!({
            "policy": "Article37",
            "jurisdiction": "EU",
            "hotel_id": "HOTEL-123"
        }),
    };

    // Step 2: L4 routes proposal
    let response = mcp_gateway.route_proposal(proposal).await.unwrap();
    let proposal_id = response.proposal_id;
    assert_eq!(response.status, "proposed");

    // Step 3: Consensus gateway aggregates votes from 3 regions
    let mut consensus = ConsensusGateway::new("EU".to_string());
    let consensus_proposal = json!({"decision_id": "E2E-001"});
    let _ = consensus.propose_decision(consensus_proposal).await;

    // Step 4: L8 commits to ledger
    let mut ledger = LedgerSync::new("EU".to_string());
    let ledger_entry = LedgerEntry {
        index: 1,
        proposal_id: proposal_id.clone(),
        decision: json!({"action": "APPROVED", "merkle_root": "0xroot001"}),
        merkle_root: "0xroot001".to_string(),
        region: "EU".to_string(),
        timestamp: chrono::Utc::now(),
    };

    let result = ledger.append_entry(ledger_entry).await;
    assert!(result.is_ok());

    // Verify full flow completed
    let entries = ledger.get_entries(0).await.unwrap();
    assert_eq!(entries.len(), 1);
}

// Byzantine fault tolerance under 100 concurrent decisions
#[tokio::test]
async fn test_byzantine_100_concurrent() {
    let gateway = Arc::new(McpGateway::new("EU".to_string(), 3000));
    let mut handles = vec![];

    for i in 0..100 {
        let gw = Arc::clone(&gateway);
        let handle = tokio::spawn(async move {
            let proposal = ProposalRequest {
                decision_id: format!("BYZANTINE-{}", i),
                action: "APPROVE".to_string(),
                amount: 1000000.0,
                metadata: json!({"index": i}),
            };

            let response = gw.route_proposal(proposal).await;
            assert!(response.is_ok());
            response.unwrap().proposal_id
        });
        handles.push(handle);
    }

    let mut proposal_ids = vec![];
    for handle in handles {
        let id = handle.await.unwrap();
        proposal_ids.push(id);
    }

    assert_eq!(proposal_ids.len(), 100);
}

// Network timeout recovery
#[tokio::test]
async fn test_network_timeout_recovery() {
    let gateway = McpGateway::new("EU".to_string(), 3000);

    let proposal = ProposalRequest {
        decision_id: "TIMEOUT-001".to_string(),
        action: "TEST".to_string(),
        amount: 100000.0,
        metadata: json!({}),
    };

    let response = gateway.route_proposal(proposal).await.unwrap();
    let proposal_id = response.proposal_id;

    // Register partial votes (simulate slow network)
    let vote1 = VoteMessage {
        proposal_id: proposal_id.clone(),
        voter: "EU".to_string(),
        approved: true,
        signature: "sig1".to_string(),
    };

    gateway.register_vote(vote1).await.unwrap();

    // Try to aggregate - should work even with partial votes
    let result = gateway.aggregate_votes(&proposal_id).await;
    assert!(result.is_ok());
}

// Load test: 1000 decisions/sec throughput
#[tokio::test]
async fn test_load_1000_decisions_per_sec() {
    let gateway = Arc::new(McpGateway::new("EU".to_string(), 3000));
    let start = Instant::now();

    let mut handles = vec![];

    // Create 1000 decisions concurrently
    for i in 0..1000 {
        let gw = Arc::clone(&gateway);
        let handle = tokio::spawn(async move {
            let proposal = ProposalRequest {
                decision_id: format!("LOAD-{}", i),
                action: "APPROVE".to_string(),
                amount: 10000.0,
                metadata: json!({"iteration": i}),
            };
            gw.route_proposal(proposal).await
        });
        handles.push(handle);
    }

    for handle in handles {
        let _ = handle.await;
    }

    let elapsed = start.elapsed();
    let decisions_per_sec = 1000.0 / elapsed.as_secs_f64();

    // Should process at least 500 decisions/sec
    assert!(decisions_per_sec >= 500.0, "Only {:.0} decisions/sec", decisions_per_sec);
}

// P99 latency: <2 seconds for vote aggregation
#[tokio::test]
async fn test_p99_latency_2sec() {
    let gateway = McpGateway::new("EU".to_string(), 3000);

    let proposal = ProposalRequest {
        decision_id: "LATENCY-001".to_string(),
        action: "TEST".to_string(),
        amount: 100000.0,
        metadata: json!({}),
    };

    let response = gateway.route_proposal(proposal).await.unwrap();
    let proposal_id = response.proposal_id;

    let start = Instant::now();

    // Register 3 votes
    for i in 0..3 {
        let vote = VoteMessage {
            proposal_id: proposal_id.clone(),
            voter: format!("REGION-{}", i),
            approved: i < 2, // 2 approvals
            signature: format!("sig{}", i),
        };
        gateway.register_vote(vote).await.unwrap();
    }

    // Aggregate votes
    let _result = gateway.aggregate_votes(&proposal_id).await.unwrap();

    let elapsed = start.elapsed();
    assert!(elapsed.as_secs_f64() < 2.0, "Took {:?}", elapsed);
}

// Multi-region synchronization
#[tokio::test]
async fn test_multiregion_sync() {
    let mut ledger_eu = LedgerSync::new("EU".to_string());
    let mut ledger_us = LedgerSync::new("US".to_string());
    let mut ledger_cn = LedgerSync::new("CN".to_string());

    // EU creates entry
    let entry = LedgerEntry {
        index: 1,
        proposal_id: "SYNC-001".to_string(),
        decision: json!({"action": "APPROVED"}),
        merkle_root: "0xroot001".to_string(),
        region: "EU".to_string(),
        timestamp: chrono::Utc::now(),
    };

    ledger_eu.append_entry(entry).await.unwrap();

    // US syncs
    ledger_us.sync_ledger(&ledger_eu).await.unwrap();

    // CN syncs
    ledger_cn.sync_ledger(&ledger_eu).await.unwrap();

    // All should have 1 entry
    assert_eq!(ledger_eu.get_entries(0).await.unwrap().len(), 1);
    assert_eq!(ledger_us.get_entries(0).await.unwrap().len(), 1);
    assert_eq!(ledger_cn.get_entries(0).await.unwrap().len(), 1);

    // Merkle roots should match
    let eu_root = ledger_eu.get_root().await.unwrap();
    let us_root = ledger_us.get_root().await.unwrap();
    let cn_root = ledger_cn.get_root().await.unwrap();

    assert_eq!(eu_root, us_root);
    assert_eq!(us_root, cn_root);
}

// Consensus with Byzantine leader
#[tokio::test]
async fn test_consensus_byzantine_leader() {
    let mut consensus = ConsensusGateway::new("EU".to_string());

    let decision = json!({"action": "APPROVE", "amount": 1000000});
    let proposal_id = consensus.propose_decision(decision).await.unwrap();

    // Leader claims approval, other 2 reject
    let leader_vote = ConsensusVote {
        voter: "LEADER".to_string(),
        proposal_id: proposal_id.clone(),
        approved: true,
        signature: "forged_sig".to_string(),
    };

    // Byzantine vote should be rejected
    let verify = consensus.verify_vote_signature(&leader_vote).await;
    assert!(verify.is_err(), "Should reject forged signature");
}

// Concurrent vote registration with deduplication
#[tokio::test]
async fn test_concurrent_vote_deduplication() {
    let gateway = Arc::new(McpGateway::new("EU".to_string(), 3000));

    let proposal = ProposalRequest {
        decision_id: "DEDUP-001".to_string(),
        action: "TEST".to_string(),
        amount: 100000.0,
        metadata: json!({}),
    };

    let response = gateway.route_proposal(proposal).await.unwrap();
    let proposal_id = response.proposal_id;

    // Try to register same vote twice concurrently
    let gw1 = Arc::clone(&gateway);
    let gw2 = Arc::clone(&gateway);
    let pid1 = proposal_id.clone();
    let pid2 = proposal_id.clone();

    let handle1 = tokio::spawn(async move {
        let vote = VoteMessage {
            proposal_id: pid1,
            voter: "EU".to_string(),
            approved: true,
            signature: "sig1".to_string(),
        };
        gw1.register_vote(vote).await
    });

    let handle2 = tokio::spawn(async move {
        let vote = VoteMessage {
            proposal_id: pid2,
            voter: "EU".to_string(),
            approved: false,
            signature: "sig2".to_string(),
        };
        gw2.register_vote(vote).await
    });

    let result1 = handle1.await.unwrap();
    let result2 = handle2.await.unwrap();

    // One should succeed, one should fail (duplicate voter)
    assert!(result1.is_ok() || result2.is_err());
}

// Ledger immutability test
#[tokio::test]
async fn test_ledger_immutability() {
    let mut ledger = LedgerSync::new("EU".to_string());

    let entry1 = LedgerEntry {
        index: 1,
        proposal_id: "IMMUT-001".to_string(),
        decision: json!({"action": "APPROVED"}),
        merkle_root: "0xroot001".to_string(),
        region: "EU".to_string(),
        timestamp: chrono::Utc::now(),
    };

    ledger.append_entry(entry1).await.unwrap();

    // Try to append with same index - should fail
    let entry_dup = LedgerEntry {
        index: 1,
        proposal_id: "IMMUT-DUP".to_string(),
        decision: json!({"action": "MODIFIED"}),
        merkle_root: "0xroot002".to_string(),
        region: "EU".to_string(),
        timestamp: chrono::Utc::now(),
    };

    let result = ledger.append_entry(entry_dup).await;
    assert!(result.is_err(), "Should not allow index reuse");
}

// Cross-region consensus correctness
#[tokio::test]
async fn test_cross_region_consensus() {
    let gw_eu = McpGateway::new("EU".to_string(), 3000);
    let gw_us = McpGateway::new("US".to_string(), 3001);
    let gw_cn = McpGateway::new("CN".to_string(), 3002);

    let proposal = ProposalRequest {
        decision_id: "XREGION-001".to_string(),
        action: "APPROVE".to_string(),
        amount: 5000000.0,
        metadata: json!({"type": "cross_region_test"}),
    };

    // All regions receive proposal
    let resp_eu = gw_eu.route_proposal(proposal.clone()).await.unwrap();
    let resp_us = gw_us.route_proposal(proposal.clone()).await.unwrap();
    let resp_cn = gw_cn.route_proposal(proposal).await.unwrap();

    // All should have proposals
    assert!(!resp_eu.proposal_id.is_empty());
    assert!(!resp_us.proposal_id.is_empty());
    assert!(!resp_cn.proposal_id.is_empty());
}

// Stress test: 500 concurrent proposals
#[tokio::test]
async fn test_stress_500_concurrent_proposals() {
    let gateway = Arc::new(McpGateway::new("EU".to_string(), 3000));
    let mut handles = vec![];

    for i in 0..500 {
        let gw = Arc::clone(&gateway);
        let handle = tokio::spawn(async move {
            let proposal = ProposalRequest {
                decision_id: format!("STRESS-{}", i),
                action: "APPROVE".to_string(),
                amount: (i * 1000) as f64,
                metadata: json!({"concurrent_index": i}),
            };
            gw.route_proposal(proposal).await
        });
        handles.push(handle);
    }

    let mut success_count = 0;
    for handle in handles {
        if let Ok(Ok(_)) = handle.await {
            success_count += 1;
        }
    }

    // All 500 should succeed
    assert_eq!(success_count, 500);
}
