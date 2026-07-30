use siss_swarm_consensus::{
    BftEngine, BftConsensusError, Proposal, Vote, VoteType, ConsensusProof, Agent,
};
use uuid::Uuid;

// ============================================================================
// Tests 1-5: BFT Consensus (f < n/3 failures tolerated)
// ============================================================================

#[tokio::test]
async fn test_bft_consensus_basic_3_agents() {
    let engine = BftEngine::new(3, 2.0 / 3.0).unwrap();

    // Register 3 agents
    for _ in 0..3 {
        let agent_id = Uuid::new_v4();
        engine.register_agent(agent_id, [0u8; 32]).unwrap();
    }

    // Create proposal
    let proposer = Uuid::new_v4();
    let proposal = Proposal::new(vec![1, 2, 3], proposer);

    // Register votes from all agents
    let agents: Vec<_> = engine
        .get_proposal_votes(proposal.id)
        .iter()
        .map(|v| v.voter_id)
        .collect();

    for i in 0..3 {
        let agent_id = Uuid::new_v4();
        engine.register_agent(agent_id, [0u8; 32]).unwrap();

        let vote = Vote::new(agent_id, proposal.id, VoteType::Commit, vec![1, 2, 3]);
        engine.register_vote(vote).unwrap();
    }

    // Reach consensus (3 commits needed)
    let result = engine.reach_consensus(proposal).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_bft_consensus_7_agents_with_2_failures() {
    let engine = BftEngine::new(7, 2.0 / 3.0).unwrap();

    // Register 7 agents
    let mut agent_ids = Vec::new();
    for _ in 0..7 {
        let agent_id = Uuid::new_v4();
        engine.register_agent(agent_id, [0u8; 32]).unwrap();
        agent_ids.push(agent_id);
    }

    // Create proposal
    let proposer = Uuid::new_v4();
    let proposal = Proposal::new(vec![4, 5, 6], proposer);

    // Register 5 commit votes (2 failures tolerated in BFT 7/3 = 2)
    for i in 0..5 {
        let vote = Vote::new(agent_ids[i], proposal.id, VoteType::Commit, vec![1, 2, 3]);
        engine.register_vote(vote).unwrap();
    }

    // Should reach consensus with 5 commits (requires 5 for 7 agents)
    let result = engine.reach_consensus(proposal).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_bft_consensus_insufficient_votes() {
    let engine = BftEngine::new(7, 2.0 / 3.0).unwrap();

    // Register 7 agents
    let mut agent_ids = Vec::new();
    for _ in 0..7 {
        let agent_id = Uuid::new_v4();
        engine.register_agent(agent_id, [0u8; 32]).unwrap();
        agent_ids.push(agent_id);
    }

    // Create proposal
    let proposer = Uuid::new_v4();
    let proposal = Proposal::new(vec![7, 8, 9], proposer);

    // Register only 2 votes (insufficient)
    for i in 0..2 {
        let vote = Vote::new(agent_ids[i], proposal.id, VoteType::Commit, vec![1, 2, 3]);
        engine.register_vote(vote).unwrap();
    }

    // Should fail due to insufficient votes
    let result = engine.reach_consensus(proposal).await;
    assert!(result.is_err());
}

#[tokio::test]
async fn test_bft_consensus_empty_proposal() {
    let engine = BftEngine::new(3, 2.0 / 3.0).unwrap();

    // Create empty proposal
    let proposer = Uuid::new_v4();
    let proposal = Proposal::new(vec![], proposer);

    let result = engine.reach_consensus(proposal).await;
    assert!(result.is_err());
}

#[tokio::test]
async fn test_bft_tolerance_3_agents() {
    let engine = BftEngine::new(3, 2.0 / 3.0).unwrap();

    // 3 agents can tolerate 0 failures (3 - 1 / 3 = 0)
    assert_eq!(engine.max_tolerated_failures(), 0);
    assert!(engine.tolerate_byzantine_failures(0).is_ok());
    assert!(engine.tolerate_byzantine_failures(1).is_err());
}

// ============================================================================
// Tests 6-10: Multi-Agent Voting & Quorum Validation
// ============================================================================

#[test]
fn test_voting_single_vote() {
    let engine = BftEngine::new(7, 2.0 / 3.0).unwrap();

    let agent_id = Uuid::new_v4();
    engine.register_agent(agent_id, [0u8; 32]).unwrap();

    let proposal_id = Uuid::new_v4();
    let vote = Vote::new(agent_id, proposal_id, VoteType::Commit, vec![1, 2, 3]);
    engine.register_vote(vote).unwrap();

    let votes = engine.get_proposal_votes(proposal_id);
    assert_eq!(votes.len(), 1);
    assert_eq!(votes[0].vote_type, VoteType::Commit);
}

#[test]
fn test_voting_duplicate_prevention() {
    let engine = BftEngine::new(7, 2.0 / 3.0).unwrap();

    let agent_id = Uuid::new_v4();
    engine.register_agent(agent_id, [0u8; 32]).unwrap();

    let proposal_id = Uuid::new_v4();
    let vote = Vote::new(agent_id, proposal_id, VoteType::Commit, vec![1, 2, 3]);
    engine.register_vote(vote).unwrap();

    // Try to register duplicate vote
    let vote2 = Vote::new(agent_id, proposal_id, VoteType::Abort, vec![1, 2, 3]);
    let result = engine.register_vote(vote2);

    assert!(result.is_err());
}

#[test]
fn test_quorum_required_commits_standard() {
    let engine = BftEngine::new(7, 2.0 / 3.0).unwrap();

    // BFT requires 2/3 + 1 = 5 commits for 7 agents
    assert_eq!(engine.required_quorum(), 5);
}

#[test]
fn test_quorum_required_commits_3_agents() {
    let engine = BftEngine::new(3, 2.0 / 3.0).unwrap();

    // 3 agents: 2/3 + 1 = 3
    assert_eq!(engine.required_quorum(), 3);
}

#[test]
fn test_quorum_required_commits_4_agents() {
    let engine = BftEngine::new(4, 2.0 / 3.0).unwrap();

    // 4 agents: floor(2*4/3) + 1 = 2 + 1 = 3
    assert_eq!(engine.required_quorum(), 3);
}

// ============================================================================
// Tests 11-15: Byzantine Failure Injection & Recovery
// ============================================================================

#[tokio::test]
async fn test_byzantine_failure_detection() {
    let engine = BftEngine::new(7, 2.0 / 3.0).unwrap();

    // Register 7 agents
    let mut agent_ids = Vec::new();
    for _ in 0..7 {
        let agent_id = Uuid::new_v4();
        engine.register_agent(agent_id, [0u8; 32]).unwrap();
        agent_ids.push(agent_id);
    }

    let proposal = Proposal::new(vec![10, 11, 12], Uuid::new_v4());

    // Register mixed votes (5 commits, 2 aborts - still passes BFT)
    for i in 0..5 {
        let vote = Vote::new(agent_ids[i], proposal.id, VoteType::Commit, vec![1, 2, 3]);
        engine.register_vote(vote).unwrap();
    }

    for i in 5..7 {
        let vote = Vote::new(agent_ids[i], proposal.id, VoteType::Abort, vec![1, 2, 3]);
        engine.register_vote(vote).unwrap();
    }

    let result = engine.reach_consensus(proposal).await;
    assert!(result.is_ok()); // Still passes with 5 commits
}

#[tokio::test]
async fn test_byzantine_failure_exceeds_tolerance() {
    let engine = BftEngine::new(7, 2.0 / 3.0).unwrap();

    // 7 agents can tolerate at most 2 failures
    assert!(engine.tolerate_byzantine_failures(3).is_err());
}

#[tokio::test]
async fn test_byzantine_recovery_recount() {
    let engine = BftEngine::new(7, 2.0 / 3.0).unwrap();

    let mut agent_ids = Vec::new();
    for _ in 0..7 {
        let agent_id = Uuid::new_v4();
        engine.register_agent(agent_id, [0u8; 32]).unwrap();
        agent_ids.push(agent_id);
    }

    let proposal = Proposal::new(vec![13, 14, 15], Uuid::new_v4());

    // Register 4 commits (insufficient)
    for i in 0..4 {
        let vote = Vote::new(agent_ids[i], proposal.id, VoteType::Commit, vec![1, 2, 3]);
        engine.register_vote(vote).unwrap();
    }

    let result = engine.reach_consensus(proposal.clone()).await;
    assert!(result.is_err());

    // Now add 1 more commit
    let vote = Vote::new(agent_ids[4], proposal.id, VoteType::Commit, vec![1, 2, 3]);
    engine.register_vote(vote).unwrap();

    let result = engine.reach_consensus(proposal).await;
    assert!(result.is_ok());
}

#[test]
fn test_byzantine_agent_state() {
    let engine = BftEngine::new(3, 2.0 / 3.0).unwrap();

    let agent_id = Uuid::new_v4();
    engine.register_agent(agent_id, [0u8; 32]).unwrap();

    let agent = engine.get_agent(agent_id).unwrap();
    assert!(!agent.is_byzantine);
}

#[test]
fn test_byzantine_tolerance_boundary() {
    let engine = BftEngine::new(7, 2.0 / 3.0).unwrap();

    // Exactly at tolerance
    assert!(engine.tolerate_byzantine_failures(2).is_ok());

    // Just over tolerance
    assert!(engine.tolerate_byzantine_failures(3).is_err());
}

// ============================================================================
// Tests 16-20: Merkle Commitment Consistency & Audit Trail
// ============================================================================

#[test]
fn test_merkle_root_computation() {
    let agent_id = Uuid::new_v4();
    let proposal_id = Uuid::new_v4();

    let votes = vec![
        Vote::new(agent_id, proposal_id, VoteType::Commit, vec![1, 2, 3]),
        Vote::new(Uuid::new_v4(), proposal_id, VoteType::Commit, vec![4, 5, 6]),
    ];

    let proof = ConsensusProof::new(proposal_id, votes);
    assert!(!proof.merkle_root.is_empty());
    assert_eq!(proof.merkle_root.len(), 32);
}

#[test]
fn test_merkle_root_consistency() {
    let agent_id = Uuid::new_v4();
    let proposal_id = Uuid::new_v4();

    let votes = vec![
        Vote::new(agent_id, proposal_id, VoteType::Commit, vec![1, 2, 3]),
        Vote::new(Uuid::new_v4(), proposal_id, VoteType::Commit, vec![4, 5, 6]),
    ];

    let proof1 = ConsensusProof::new(proposal_id, votes.clone());
    let proof2 = ConsensusProof::new(proposal_id, votes);

    assert_eq!(proof1.merkle_root, proof2.merkle_root);
}

#[test]
fn test_merkle_verification_valid() {
    let votes = vec![
        Vote::new(Uuid::new_v4(), Uuid::new_v4(), VoteType::Commit, vec![1, 2, 3]),
        Vote::new(Uuid::new_v4(), Uuid::new_v4(), VoteType::Commit, vec![4, 5, 6]),
    ];

    let proof = ConsensusProof::new(Uuid::new_v4(), votes);
    assert!(proof.verify_merkle_root());
}

#[test]
fn test_merkle_verification_empty_votes() {
    let proof = ConsensusProof::new(Uuid::new_v4(), vec![]);
    assert!(proof.verify_merkle_root());
}

#[test]
fn test_consensus_proof_audit_trail() {
    let agent_ids: Vec<_> = (0..5).map(|_| Uuid::new_v4()).collect();
    let proposal_id = Uuid::new_v4();

    let votes: Vec<_> = agent_ids
        .iter()
        .map(|&id| Vote::new(id, proposal_id, VoteType::Commit, vec![1, 2, 3]))
        .collect();

    let proof = ConsensusProof::new(proposal_id, votes);

    // Verify audit trail
    assert_eq!(proof.votes.len(), 5);
    assert_eq!(proof.proposal_id, proposal_id);
    assert!(proof.verify_merkle_root());

    // Check all voters are recorded
    for (i, voter_id) in agent_ids.iter().enumerate() {
        assert_eq!(proof.votes[i].voter_id, *voter_id);
    }
}

// ============================================================================
// Additional Edge Cases & Integration Tests
// ============================================================================

#[tokio::test]
async fn test_multiple_proposals_independent() {
    let engine = BftEngine::new(5, 2.0 / 3.0).unwrap();

    for _ in 0..5 {
        let agent_id = Uuid::new_v4();
        engine.register_agent(agent_id, [0u8; 32]).unwrap();
    }

    // Create 2 proposals
    let prop1 = Proposal::new(vec![1], Uuid::new_v4());
    let prop2 = Proposal::new(vec![2], Uuid::new_v4());

    // Vote differently on each
    let agent1 = Uuid::new_v4();
    let agent2 = Uuid::new_v4();
    let agent3 = Uuid::new_v4();
    let agent4 = Uuid::new_v4();

    for &aid in &[agent1, agent2, agent3, agent4] {
        engine.register_agent(aid, [0u8; 32]).unwrap();
    }

    // Votes for prop1
    let vote1 = Vote::new(agent1, prop1.id, VoteType::Commit, vec![1]);
    engine.register_vote(vote1).unwrap();
    let vote2 = Vote::new(agent2, prop1.id, VoteType::Commit, vec![1]);
    engine.register_vote(vote2).unwrap();
    let vote3 = Vote::new(agent3, prop1.id, VoteType::Commit, vec![1]);
    engine.register_vote(vote3).unwrap();

    // Votes for prop2
    let vote4 = Vote::new(agent4, prop2.id, VoteType::Commit, vec![1]);
    engine.register_vote(vote4).unwrap();

    let votes_prop1 = engine.get_proposal_votes(prop1.id);
    assert_eq!(votes_prop1.len(), 3);

    let votes_prop2 = engine.get_proposal_votes(prop2.id);
    assert_eq!(votes_prop2.len(), 1);
}

#[test]
fn test_invalid_voter_registration() {
    let engine = BftEngine::new(3, 2.0 / 3.0).unwrap();

    let agent_id = Uuid::new_v4();
    let proposal_id = Uuid::new_v4();

    // Try to vote without registering agent
    let vote = Vote::new(agent_id, proposal_id, VoteType::Commit, vec![1, 2, 3]);
    let result = engine.register_vote(vote);

    assert!(result.is_err());
}

#[test]
fn test_clearing_proposal_votes() {
    let engine = BftEngine::new(3, 2.0 / 3.0).unwrap();

    let agent_id = Uuid::new_v4();
    engine.register_agent(agent_id, [0u8; 32]).unwrap();

    let proposal_id = Uuid::new_v4();
    let vote = Vote::new(agent_id, proposal_id, VoteType::Commit, vec![1, 2, 3]);
    engine.register_vote(vote).unwrap();

    assert_eq!(engine.get_proposal_votes(proposal_id).len(), 1);

    engine.clear_proposal(proposal_id);

    assert_eq!(engine.get_proposal_votes(proposal_id).len(), 0);
}
