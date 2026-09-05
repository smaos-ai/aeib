use l2b_federated_consensus::consensus::{ConsensusVote, ConsensusGateway};
use serde_json::json;

#[tokio::test]
async fn test_three_region_voting() {
    // Test Byzantine consensus: 3 regions must achieve 2/3 majority
    let mut gateway = ConsensusGateway::new("EU".to_string());

    let decision = json!({
        "decision_id": "HOTEL-001",
        "action": "APPROVE_CREDIT",
        "amount": 1000000
    });

    // Propose decision
    let proposal_id = gateway.propose_decision(decision.clone()).await.unwrap();
    assert!(!proposal_id.is_empty());

    // Collect votes from 3 regions
    let vote_eu = ConsensusVote {
        voter: "EU".to_string(),
        proposal_id: proposal_id.clone(),
        approved: true,
        signature: "sig_eu".to_string(),
    };

    let vote_us = ConsensusVote {
        voter: "US".to_string(),
        proposal_id: proposal_id.clone(),
        approved: true,
        signature: "sig_us".to_string(),
    };

    let vote_cn = ConsensusVote {
        voter: "CN".to_string(),
        proposal_id: proposal_id.clone(),
        approved: false,
        signature: "sig_cn".to_string(),
    };

    gateway.register_vote(vote_eu).await.unwrap();
    gateway.register_vote(vote_us).await.unwrap();
    gateway.register_vote(vote_cn).await.unwrap();

    // Aggregate votes - should succeed with 2/3 majority (2 approved)
    let result = gateway.aggregate_votes(&proposal_id).await.unwrap();
    assert!(result.approved);
    assert_eq!(result.total_votes, 3);
    assert_eq!(result.approved_votes, 2);
}

#[tokio::test]
async fn test_two_thirds_majority_required() {
    // Test that Byzantine consensus requires 2/3 majority
    let mut gateway = ConsensusGateway::new("EU".to_string());

    let decision = json!({"decision_id": "TEST-001", "action": "TEST"});
    let proposal_id = gateway.propose_decision(decision).await.unwrap();

    // 3 regions: 1 approve, 2 reject - should fail
    gateway.register_vote(ConsensusVote {
        voter: "EU".to_string(),
        proposal_id: proposal_id.clone(),
        approved: true,
        signature: "sig_eu".to_string(),
    }).await.unwrap();

    gateway.register_vote(ConsensusVote {
        voter: "US".to_string(),
        proposal_id: proposal_id.clone(),
        approved: false,
        signature: "sig_us".to_string(),
    }).await.unwrap();

    gateway.register_vote(ConsensusVote {
        voter: "CN".to_string(),
        proposal_id: proposal_id.clone(),
        approved: false,
        signature: "sig_cn".to_string(),
    }).await.unwrap();

    let result = gateway.aggregate_votes(&proposal_id).await.unwrap();
    assert!(!result.approved);
    assert_eq!(result.total_votes, 3);
    assert_eq!(result.approved_votes, 1);
}

#[tokio::test]
async fn test_byzantine_leader_failure() {
    // Test that a Byzantine (malicious) leader vote is detected
    let mut gateway = ConsensusGateway::new("EU".to_string());

    let decision = json!({"decision_id": "BYZANTINE-001", "action": "MALICIOUS"});
    let proposal_id = gateway.propose_decision(decision).await.unwrap();

    // Byzantine leader tries to force approval despite majority rejection
    let malicious_vote = ConsensusVote {
        voter: "LEADER".to_string(),
        proposal_id: proposal_id.clone(),
        approved: true,
        signature: "forged_sig".to_string(),
    };

    // This should be detected and handled
    let verify_result = gateway.verify_vote_signature(&malicious_vote).await;
    // Should fail or handle gracefully
    assert!(verify_result.is_err() || !verify_result.unwrap());
}

#[tokio::test]
async fn test_timeout_recovery() {
    // Test recovery from timeout during consensus
    let mut gateway = ConsensusGateway::new("EU".to_string());

    let decision = json!({"decision_id": "TIMEOUT-001", "action": "TEST"});
    let proposal_id = gateway.propose_decision(decision).await.unwrap();

    // Simulate partial votes (only 1 of 3 regions responded)
    gateway.register_vote(ConsensusVote {
        voter: "EU".to_string(),
        proposal_id: proposal_id.clone(),
        approved: true,
        signature: "sig_eu".to_string(),
    }).await.unwrap();

    // Try to aggregate with insufficient votes
    let result = gateway.aggregate_votes(&proposal_id).await;

    // Should handle gracefully (either error or incomplete result)
    match result {
        Ok(agg) => {
            // If it returns partial result, votes should be < 3
            assert!(agg.total_votes < 3);
        }
        Err(_) => {
            // Or it returns an error which is also acceptable
        }
    }
}

#[tokio::test]
async fn test_merkle_root_consistency() {
    // Test that Merkle root remains consistent across regions
    let mut gateway = ConsensusGateway::new("EU".to_string());

    let decision = json!({"decision_id": "MERKLE-001", "action": "TEST"});
    let proposal_id = gateway.propose_decision(decision).await.unwrap();

    // Register votes and build Merkle tree
    gateway.register_vote(ConsensusVote {
        voter: "EU".to_string(),
        proposal_id: proposal_id.clone(),
        approved: true,
        signature: "sig_eu".to_string(),
    }).await.unwrap();

    gateway.register_vote(ConsensusVote {
        voter: "US".to_string(),
        proposal_id: proposal_id.clone(),
        approved: true,
        signature: "sig_us".to_string(),
    }).await.unwrap();

    let merkle_root = gateway.build_merkle_root(&proposal_id).await.unwrap();
    assert!(!merkle_root.is_empty());

    // Build again with same votes - should produce same root
    let merkle_root_2 = gateway.build_merkle_root(&proposal_id).await.unwrap();
    assert_eq!(merkle_root, merkle_root_2);
}

#[test]
fn test_consensus_vote_serialization() {
    let vote = ConsensusVote {
        voter: "EU".to_string(),
        proposal_id: "PROP-001".to_string(),
        approved: true,
        signature: "sig_test".to_string(),
    };

    let json = serde_json::to_string(&vote).unwrap();
    let deserialized: ConsensusVote = serde_json::from_str(&json).unwrap();

    assert_eq!(vote.voter, deserialized.voter);
    assert_eq!(vote.proposal_id, deserialized.proposal_id);
    assert_eq!(vote.approved, deserialized.approved);
}
