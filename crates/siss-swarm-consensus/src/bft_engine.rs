use crate::errors::BftConsensusError;
use crate::types::{Agent, ConsensusProof, Proposal, Vote};
use crate::voting::VotingEngine;
use crate::quorum::QuorumValidator;
use dashmap::DashMap;
use std::sync::Arc;
use uuid::Uuid;

pub struct BftEngine {
    agents: Arc<DashMap<Uuid, Agent>>,
    voting_engine: Arc<VotingEngine>,
    quorum_validator: Arc<QuorumValidator>,
}

impl BftEngine {
    pub fn new(
        total_agents: usize,
        consensus_threshold: f64,
    ) -> Result<Self, BftConsensusError> {
        let quorum_validator = QuorumValidator::new(total_agents, consensus_threshold)?;

        Ok(Self {
            agents: Arc::new(DashMap::new()),
            voting_engine: Arc::new(VotingEngine::new()),
            quorum_validator: Arc::new(quorum_validator),
        })
    }

    pub fn register_agent(&self, agent_id: Uuid, public_key: [u8; 32]) -> Result<(), BftConsensusError> {
        if self.agents.contains_key(&agent_id) {
            return Err(BftConsensusError::AgentNotFound(
                "Agent already registered".to_string(),
            ));
        }
        let agent = Agent::new(agent_id, public_key);
        self.agents.insert(agent_id, agent);
        Ok(())
    }

    pub fn get_agent(&self, agent_id: Uuid) -> Result<Agent, BftConsensusError> {
        self.agents
            .get(&agent_id)
            .map(|entry| entry.clone())
            .ok_or_else(|| BftConsensusError::AgentNotFound(agent_id.to_string()))
    }

    pub fn agent_count(&self) -> usize {
        self.agents.len()
    }

    pub fn register_vote(&self, vote: Vote) -> Result<(), BftConsensusError> {
        if !self.agents.contains_key(&vote.voter_id) {
            return Err(BftConsensusError::AgentNotFound(
                format!("Voter {} not registered", vote.voter_id),
            ));
        }
        self.voting_engine.register_vote(vote)
    }

    pub async fn reach_consensus(&self, proposal: Proposal) -> Result<ConsensusProof, BftConsensusError> {
        if proposal.content.is_empty() {
            return Err(BftConsensusError::InvalidProposal(
                "Proposal content cannot be empty".to_string(),
            ));
        }

        let votes = self.voting_engine.get_votes(proposal.id);

        if votes.is_empty() {
            return Err(BftConsensusError::InsufficientQuorum {
                got: 0,
                required: self.quorum_validator.required_for_bft(),
            });
        }

        let commits = self.voting_engine.count_commits(proposal.id);
        let required = self.quorum_validator.required_for_bft();

        if !self.quorum_validator.is_bft_quorum_reached(commits) {
            return Err(BftConsensusError::InsufficientQuorum {
                got: commits,
                required,
            });
        }

        let proof = ConsensusProof::new(proposal.id, votes);

        if !proof.verify_merkle_root() {
            return Err(BftConsensusError::MerkleCommitmentMismatch);
        }

        Ok(proof)
    }

    pub fn tolerate_byzantine_failures(&self, failures: usize) -> Result<bool, BftConsensusError> {
        self.quorum_validator.can_tolerate_failures(failures)?;
        Ok(true)
    }

    pub fn required_quorum(&self) -> usize {
        self.quorum_validator.required_for_bft()
    }

    pub fn max_tolerated_failures(&self) -> usize {
        self.quorum_validator.max_tolerated_failures()
    }

    pub fn get_proposal_votes(&self, proposal_id: Uuid) -> Vec<Vote> {
        self.voting_engine.get_votes(proposal_id)
    }

    pub fn clear_proposal(&self, proposal_id: Uuid) {
        self.voting_engine.clear_votes(proposal_id);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_engine_creation() {
        let engine = BftEngine::new(7, 2.0 / 3.0).unwrap();
        assert_eq!(engine.agent_count(), 0);
    }

    #[test]
    fn test_register_agent() {
        let engine = BftEngine::new(7, 2.0 / 3.0).unwrap();
        let agent_id = Uuid::new_v4();
        let public_key = [0u8; 32];

        engine.register_agent(agent_id, public_key).unwrap();
        assert_eq!(engine.agent_count(), 1);
    }

    #[test]
    fn test_register_duplicate_agent() {
        let engine = BftEngine::new(7, 2.0 / 3.0).unwrap();
        let agent_id = Uuid::new_v4();
        let public_key = [0u8; 32];

        engine.register_agent(agent_id, public_key).unwrap();
        let result = engine.register_agent(agent_id, public_key);
        assert!(result.is_err());
    }

    #[test]
    fn test_max_tolerated_failures_bft() {
        let engine = BftEngine::new(7, 2.0 / 3.0).unwrap();
        assert_eq!(engine.max_tolerated_failures(), 2);
    }
}
