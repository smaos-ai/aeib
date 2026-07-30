use crate::errors::BftConsensusError;
use crate::types::{Vote, VoteType};
use dashmap::DashMap;
use std::sync::Arc;
use uuid::Uuid;

pub struct VotingEngine {
    votes: Arc<DashMap<Uuid, Vec<Vote>>>,
}

impl VotingEngine {
    pub fn new() -> Self {
        Self {
            votes: Arc::new(DashMap::new()),
        }
    }

    pub fn register_vote(&self, vote: Vote) -> Result<(), BftConsensusError> {
        if vote.signature.is_empty() {
            return Err(BftConsensusError::VoteValidationFailed(
                "Invalid signature".to_string(),
            ));
        }

        let mut votes = self.votes.entry(vote.proposal_id).or_default();

        // Prevent duplicate votes from same voter
        if votes.iter().any(|v| v.voter_id == vote.voter_id) {
            return Err(BftConsensusError::VoteValidationFailed(
                "Duplicate vote from voter".to_string(),
            ));
        }

        votes.push(vote);
        Ok(())
    }

    pub fn get_votes(&self, proposal_id: Uuid) -> Vec<Vote> {
        self.votes
            .get(&proposal_id)
            .map(|entry| entry.clone())
            .unwrap_or_default()
    }

    pub fn count_commits(&self, proposal_id: Uuid) -> usize {
        self.votes
            .get(&proposal_id)
            .map(|entry| {
                entry
                    .iter()
                    .filter(|v| v.vote_type == VoteType::Commit)
                    .count()
            })
            .unwrap_or(0)
    }

    pub fn count_aborts(&self, proposal_id: Uuid) -> usize {
        self.votes
            .get(&proposal_id)
            .map(|entry| {
                entry
                    .iter()
                    .filter(|v| v.vote_type == VoteType::Abort)
                    .count()
            })
            .unwrap_or(0)
    }

    pub fn total_votes(&self, proposal_id: Uuid) -> usize {
        self.votes
            .get(&proposal_id)
            .map(|entry| entry.len())
            .unwrap_or(0)
    }

    pub fn clear_votes(&self, proposal_id: Uuid) {
        self.votes.remove(&proposal_id);
    }
}

impl Default for VotingEngine {
    fn default() -> Self {
        Self::new()
    }
}
