use parking_lot::RwLock;
use std::collections::{HashMap, HashSet};
use std::sync::Arc;
use std::time::Duration;

pub struct LeaderElection {
    node_ids: Vec<String>,
    term: Arc<RwLock<u64>>,
    current_leader: Arc<RwLock<Option<String>>>,
    votes: Arc<RwLock<HashMap<String, String>>>, // voter_id -> candidate_id
    voted_in_term: Arc<RwLock<HashSet<String>>>,
}

impl LeaderElection {
    pub fn new(node_ids: Vec<String>) -> Self {
        Self {
            node_ids,
            term: Arc::new(RwLock::new(0)),
            current_leader: Arc::new(RwLock::new(None)),
            votes: Arc::new(RwLock::new(HashMap::new())),
            voted_in_term: Arc::new(RwLock::new(HashSet::new())),
        }
    }

    pub fn term(&self) -> u64 {
        *self.term.read()
    }

    pub fn cluster_size(&self) -> usize {
        self.node_ids.len()
    }

    pub fn current_leader(&self) -> Option<String> {
        self.current_leader.read().clone()
    }

    pub fn start_election(&mut self) -> Vec<String> {
        let mut term = self.term.write();
        *term += 1;

        let mut voted = self.voted_in_term.write();
        voted.clear();

        self.node_ids.clone()
    }

    pub fn cast_vote(&mut self, voter_id: String, candidate_id: String) {
        let mut votes = self.votes.write();
        votes.insert(voter_id.clone(), candidate_id);
        drop(votes);

        let mut voted = self.voted_in_term.write();
        voted.insert(voter_id);
    }

    pub fn check_quorum(&mut self) -> Option<String> {
        let votes = self.votes.read();
        let mut vote_counts: HashMap<String, usize> = HashMap::new();

        for candidate in votes.values() {
            *vote_counts.entry(candidate.clone()).or_insert(0) += 1;
        }

        // Raft-style quorum: simple majority (ceil(n/2))
        // For 3 nodes: 2 votes
        // For 7 nodes: 4 votes
        let quorum_needed = (self.cluster_size() / 2) + 1;

        let mut candidates_with_quorum: Vec<(String, usize)> = vote_counts
            .iter()
            .filter(|(_, count)| **count >= quorum_needed)
            .map(|(c, count)| (c.clone(), *count))
            .collect();

        // Sort by count descending, then by candidate ID ascending (deterministic tiebreaker)
        candidates_with_quorum.sort_by(|a, b| {
            match b.1.cmp(&a.1) {
                std::cmp::Ordering::Equal => a.0.cmp(&b.0),
                other => other,
            }
        });

        if let Some((ref candidate, _)) = candidates_with_quorum.first() {
            let mut leader = self.current_leader.write();
            *leader = Some(candidate.clone());
            return Some(candidate.clone());
        }

        None
    }

    pub fn deterministic_tiebreaker(&self) -> Option<String> {
        let mut sorted_nodes = self.node_ids.clone();
        sorted_nodes.sort();
        sorted_nodes.last().cloned()
    }

    pub fn try_vote_again(&self, voter_id: String, _candidate_id: String) -> crate::Result<bool> {
        let voted = self.voted_in_term.read();
        if voted.contains(&voter_id) {
            Err(crate::errors::Error::InvalidTerm)
        } else {
            Ok(true)
        }
    }

    pub fn trigger_new_election(&mut self) {
        let mut term = self.term.write();
        *term += 1;

        let mut voted = self.voted_in_term.write();
        voted.clear();

        let mut votes = self.votes.write();
        votes.clear();

        let mut leader = self.current_leader.write();
        *leader = None;
    }

    pub fn election_timeout_duration(&self) -> Duration {
        Duration::from_secs(2)
    }
}
