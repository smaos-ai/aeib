use anyhow::Result;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use thiserror::Error;
use uuid::Uuid;

use crate::consensus::{ConsensusGateway, ConsensusVote, AggregatedVotes};

#[derive(Error, Debug)]
pub enum McpError {
    #[error("Proposal not found")]
    ProposalNotFound,

    #[error("Duplicate vote")]
    DuplicateVote,

    #[error("Invalid proposal")]
    InvalidProposal,

    #[error("Internal error: {0}")]
    Internal(String),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProposalRequest {
    pub decision_id: String,
    pub action: String,
    pub amount: f64,
    pub metadata: Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProposalResponse {
    pub proposal_id: String,
    pub status: String,
    pub timestamp: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VoteMessage {
    pub proposal_id: String,
    pub voter: String,
    pub approved: bool,
    pub signature: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CommitMessage {
    pub proposal_id: String,
    pub merkle_root: String,
    pub ledger_index: u64,
    pub timestamp: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CommitResponse {
    pub proposal_id: String,
    pub status: String,
    pub ledger_index: u64,
    pub timestamp: DateTime<Utc>,
}

#[derive(Debug, Clone)]
pub struct VoteAggregation {
    pub proposal_id: String,
    pub total_votes: usize,
    pub approved_votes: usize,
    pub approved: bool,
}

pub struct McpGateway {
    region: String,
    port: u16,
    consensus: Arc<RwLock<ConsensusGateway>>,
    proposals: Arc<RwLock<HashMap<String, ProposalRequest>>>,
    votes: Arc<RwLock<HashMap<String, Vec<VoteMessage>>>>,
    ledger: Arc<RwLock<Vec<CommitMessage>>>,
    tls_enabled: bool,
}

impl McpGateway {
    pub fn new(region: String, port: u16) -> Self {
        Self {
            region: region.clone(),
            port,
            consensus: Arc::new(RwLock::new(ConsensusGateway::new(region))),
            proposals: Arc::new(RwLock::new(HashMap::new())),
            votes: Arc::new(RwLock::new(HashMap::new())),
            ledger: Arc::new(RwLock::new(Vec::new())),
            tls_enabled: true,
        }
    }

    pub async fn route_proposal(&self, proposal: ProposalRequest) -> Result<ProposalResponse, McpError> {
        let proposal_id = Uuid::new_v4().to_string();

        let mut proposals = self.proposals.write().await;
        proposals.insert(proposal_id.clone(), proposal);

        let mut votes = self.votes.write().await;
        votes.insert(proposal_id.clone(), Vec::new());

        Ok(ProposalResponse {
            proposal_id,
            status: "proposed".to_string(),
            timestamp: Utc::now(),
        })
    }

    pub async fn register_vote(&self, vote: VoteMessage) -> Result<(), McpError> {
        let mut votes = self.votes.write().await;

        let vote_list = votes
            .get_mut(&vote.proposal_id)
            .ok_or(McpError::ProposalNotFound)?;

        // Check for duplicate votes from same voter
        if vote_list.iter().any(|v| v.voter == vote.voter) {
            return Err(McpError::DuplicateVote);
        }

        vote_list.push(vote);
        Ok(())
    }

    pub async fn aggregate_votes(&self, proposal_id: &str) -> Result<VoteAggregation, McpError> {
        let votes = self.votes.read().await;

        let vote_list = votes
            .get(proposal_id)
            .ok_or(McpError::ProposalNotFound)?;

        if vote_list.is_empty() {
            return Err(McpError::InvalidProposal);
        }

        let approved_votes = vote_list.iter().filter(|v| v.approved).count();
        let total_votes = vote_list.len();

        // Byzantine consensus: require 2/3 majority
        let approved = approved_votes * 3 >= total_votes * 2;

        Ok(VoteAggregation {
            proposal_id: proposal_id.to_string(),
            total_votes,
            approved_votes,
            approved,
        })
    }

    pub async fn finalize_commit(&self, commit: CommitMessage) -> Result<CommitResponse, McpError> {
        let mut ledger = self.ledger.write().await;

        let ledger_index = (ledger.len() + 1) as u64;

        ledger.push(commit.clone());

        Ok(CommitResponse {
            proposal_id: commit.proposal_id,
            status: "committed".to_string(),
            ledger_index,
            timestamp: Utc::now(),
        })
    }

    pub fn supports_tls(&self) -> bool {
        self.tls_enabled
    }
}

impl Clone for McpGateway {
    fn clone(&self) -> Self {
        Self {
            region: self.region.clone(),
            port: self.port,
            consensus: Arc::clone(&self.consensus),
            proposals: Arc::clone(&self.proposals),
            votes: Arc::clone(&self.votes),
            ledger: Arc::clone(&self.ledger),
            tls_enabled: self.tls_enabled,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_gateway_creation() {
        let gateway = McpGateway::new("EU".to_string(), 3000);
        assert_eq!(gateway.region, "EU");
        assert_eq!(gateway.port, 3000);
        assert!(gateway.tls_enabled);
    }
}
