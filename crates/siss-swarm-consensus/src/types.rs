use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use uuid::Uuid;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub struct Proposal {
    pub id: Uuid,
    pub content: Vec<u8>,
    pub proposer: Uuid,
    pub timestamp: DateTime<Utc>,
    pub nonce: u64,
}

impl Proposal {
    pub fn new(content: Vec<u8>, proposer: Uuid) -> Self {
        Self {
            id: Uuid::new_v4(),
            content,
            proposer,
            timestamp: Utc::now(),
            nonce: 0,
        }
    }

    pub fn hash(&self) -> Vec<u8> {
        let mut hasher = Sha256::new();
        hasher.update(self.id.as_bytes());
        hasher.update(&self.content);
        hasher.update(self.proposer.as_bytes());
        hasher.update(self.timestamp.to_rfc3339().as_bytes());
        hasher.update(self.nonce.to_le_bytes());
        hasher.finalize().to_vec()
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum VoteType {
    Commit,
    Abort,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub struct Vote {
    pub voter_id: Uuid,
    pub proposal_id: Uuid,
    pub vote_type: VoteType,
    pub timestamp: DateTime<Utc>,
    pub signature: Vec<u8>,
}

impl Vote {
    pub fn new(voter_id: Uuid, proposal_id: Uuid, vote_type: VoteType, signature: Vec<u8>) -> Self {
        Self {
            voter_id,
            proposal_id,
            vote_type,
            timestamp: Utc::now(),
            signature,
        }
    }

    pub fn hash(&self) -> Vec<u8> {
        let mut hasher = Sha256::new();
        hasher.update(self.voter_id.as_bytes());
        hasher.update(self.proposal_id.as_bytes());
        hasher.update(format!("{:?}", self.vote_type).as_bytes());
        hasher.update(self.timestamp.to_rfc3339().as_bytes());
        hasher.update(&self.signature);
        hasher.finalize().to_vec()
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ConsensusProof {
    pub proposal_id: Uuid,
    pub votes: Vec<Vote>,
    pub merkle_root: Vec<u8>,
    pub timestamp: DateTime<Utc>,
}

impl ConsensusProof {
    pub fn new(proposal_id: Uuid, votes: Vec<Vote>) -> Self {
        let merkle_root = Self::compute_merkle_root(&votes);
        Self {
            proposal_id,
            votes,
            merkle_root,
            timestamp: Utc::now(),
        }
    }

    pub fn compute_merkle_root(votes: &[Vote]) -> Vec<u8> {
        if votes.is_empty() {
            return vec![0u8; 32];
        }

        let mut hashes: Vec<Vec<u8>> = votes.iter().map(|v| v.hash()).collect();

        while hashes.len() > 1 {
            let mut next_level = Vec::new();
            for chunk in hashes.chunks(2) {
                let mut hasher = Sha256::new();
                hasher.update(&chunk[0]);
                if chunk.len() > 1 {
                    hasher.update(&chunk[1]);
                }
                next_level.push(hasher.finalize().to_vec());
            }
            hashes = next_level;
        }

        hashes.into_iter().next().unwrap_or_else(|| vec![0u8; 32])
    }

    pub fn verify_merkle_root(&self) -> bool {
        let computed_root = Self::compute_merkle_root(&self.votes);
        computed_root == self.merkle_root
    }
}

#[derive(Clone, Debug)]
pub struct Agent {
    pub id: Uuid,
    pub public_key: [u8; 32],
    pub is_byzantine: bool,
}

impl Agent {
    pub fn new(id: Uuid, public_key: [u8; 32]) -> Self {
        Self {
            id,
            public_key,
            is_byzantine: false,
        }
    }
}
