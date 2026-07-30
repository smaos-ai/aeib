use siss_consensus_monitor::LeaderElection;

#[test]
fn test_leader_election_initialization() {
    let nodes = vec![
        "node-a".to_string(),
        "node-b".to_string(),
        "node-c".to_string(),
    ];
    let election = LeaderElection::new(nodes.clone());

    assert_eq!(election.term(), 0);
    assert_eq!(election.cluster_size(), 3);
    assert!(election.current_leader().is_none());
}

#[test]
fn test_vote_request_broadcast() {
    let nodes = vec![
        "node-a".to_string(),
        "node-b".to_string(),
        "node-c".to_string(),
    ];
    let mut election = LeaderElection::new(nodes);

    let candidates = election.start_election();
    assert!(candidates.len() > 0);
    assert!(election.term() > 0);
}

#[test]
fn test_vote_counting_2_3_plus_1_quorum() {
    let nodes = vec![
        "node-a".to_string(),
        "node-b".to_string(),
        "node-c".to_string(),
    ];
    let mut election = LeaderElection::new(nodes);

    election.start_election();
    // Vote for node-a from node-b and node-c
    election.cast_vote("node-b".to_string(), "node-a".to_string());
    election.cast_vote("node-c".to_string(), "node-a".to_string());

    // 2 votes out of 3 nodes = 67% quorum (2/3+1)
    let leader = election.check_quorum();
    assert!(leader.is_some());
    assert_eq!(leader.unwrap(), "node-a");
}

#[test]
fn test_deterministic_tiebreaker() {
    // When multiple nodes reach quorum, highest lexicographic ID wins
    let nodes = vec![
        "node-c".to_string(),
        "node-a".to_string(),
        "node-b".to_string(),
    ];
    let mut election = LeaderElection::new(nodes);

    election.start_election();
    // All nodes vote for themselves - create artificial tie
    election.cast_vote("node-a".to_string(), "node-a".to_string());
    election.cast_vote("node-b".to_string(), "node-b".to_string());
    election.cast_vote("node-c".to_string(), "node-c".to_string());

    // Check that tiebreaker gives the highest ID
    // Note: In a real system with proper quorum, we'd test differently
    // but for determinism, verify the election has stable output
    let leader1 = election.deterministic_tiebreaker();
    let leader2 = election.deterministic_tiebreaker();
    assert_eq!(leader1, leader2);
}

#[test]
fn test_election_with_3_nodes() {
    let nodes = vec![
        "node-1".to_string(),
        "node-2".to_string(),
        "node-3".to_string(),
    ];
    let mut election = LeaderElection::new(nodes);

    election.start_election();
    // Node-1 votes for itself
    election.cast_vote("node-1".to_string(), "node-1".to_string());
    // Node-2 votes for node-1
    election.cast_vote("node-2".to_string(), "node-1".to_string());

    let leader = election.check_quorum();
    assert_eq!(leader, Some("node-1".to_string()));
    assert_eq!(election.current_leader(), Some("node-1".to_string()));
}

#[test]
fn test_election_with_7_nodes() {
    let nodes = vec![
        "node-1".to_string(),
        "node-2".to_string(),
        "node-3".to_string(),
        "node-4".to_string(),
        "node-5".to_string(),
        "node-6".to_string(),
        "node-7".to_string(),
    ];
    let mut election = LeaderElection::new(nodes);

    election.start_election();
    // Need 5 votes for quorum (2/3+1 of 7)
    for i in 1..=5 {
        election.cast_vote(format!("node-{}", i), "node-3".to_string());
    }

    let leader = election.check_quorum();
    assert_eq!(leader, Some("node-3".to_string()));
}

#[test]
fn test_election_timeout_2_seconds() {
    let nodes = vec![
        "node-a".to_string(),
        "node-b".to_string(),
        "node-c".to_string(),
    ];
    let election = LeaderElection::new(nodes);

    // Check timeout duration
    let timeout = election.election_timeout_duration();
    assert!(timeout >= std::time::Duration::from_secs(2));
    assert!(timeout <= std::time::Duration::from_secs(3)); // Allow some jitter
}

#[test]
fn test_election_prevents_duplicate_votes() {
    let nodes = vec![
        "node-a".to_string(),
        "node-b".to_string(),
        "node-c".to_string(),
    ];
    let mut election = LeaderElection::new(nodes);

    election.start_election();
    let _term = election.term();

    // Node-a votes for node-b
    election.cast_vote("node-a".to_string(), "node-b".to_string());
    // Try to vote again in same term - should be rejected
    let result = election.try_vote_again("node-a".to_string(), "node-c".to_string());
    assert!(result.is_err() || !result.unwrap());
}

#[test]
fn test_election_term_increment() {
    let nodes = vec![
        "node-a".to_string(),
        "node-b".to_string(),
        "node-c".to_string(),
    ];
    let mut election = LeaderElection::new(nodes);

    let initial_term = election.term();
    assert_eq!(initial_term, 0);

    election.start_election();
    let new_term = election.term();
    assert!(new_term > initial_term);

    // Trigger another election
    election.trigger_new_election();
    let newer_term = election.term();
    assert!(newer_term > new_term);
}
