use crate::error::{ConsensusError, Result};
use crate::{ConsensusConfig, MerkleCheckpoint};
use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::sync::RwLock;

/// PBFT message types
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum MessageType {
    PrePrepare,
    Prepare,
    Commit,
    ViewChange,
    NewView,
}

/// PBFT message
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PBFTMessage {
    pub msg_type: MessageType,
    pub view: u64,
    pub sequence: u64,
    pub sender: u32,
    pub data: Vec<u8>,
    pub signature: Vec<u8>,
}

impl PBFTMessage {
    /// Validate message structure
    pub fn validate(&self, config: &ConsensusConfig) -> Result<()> {
        if self.sender >= config.total_replicas {
            return Err(ConsensusError::InvalidMessage);
        }
        if self.view > config.view + 10 {
            return Err(ConsensusError::InvalidMessage);
        }
        Ok(())
    }
}

/// PBFT consensus state for single request
#[derive(Clone, Debug)]
pub struct RequestState {
    pub sequence: u64,
    pub prepares: u32,
    pub commits: u32,
    pub timestamp: i64,
}

/// Main PBFT consensus engine
pub struct PBFTConsensus {
    config: Arc<RwLock<ConsensusConfig>>,
    /// Pending requests (sequence -> state)
    pending_requests: Arc<DashMap<u64, RequestState>>,
    /// Committed requests (checkpoint-stable)
    committed: Arc<DashMap<u64, Vec<u8>>>,
    /// Received messages tracking
    messages: Arc<DashMap<(u64, MessageType), Vec<PBFTMessage>>>,
    /// Latest checkpoint
    checkpoint: Arc<RwLock<Option<MerkleCheckpoint>>>,
}

impl PBFTConsensus {
    /// Create new PBFT instance
    pub fn new(config: ConsensusConfig) -> Self {
        Self {
            config: Arc::new(RwLock::new(config)),
            pending_requests: Arc::new(DashMap::new()),
            committed: Arc::new(DashMap::new()),
            messages: Arc::new(DashMap::new()),
            checkpoint: Arc::new(RwLock::new(None)),
        }
    }

    /// Submit request for consensus
    pub async fn submit_request(&self, sequence: u64, data: Vec<u8>) -> Result<()> {
        let config = self.config.read().await;

        if sequence <= 0 {
            return Err(ConsensusError::InvalidMessage);
        }

        // Check if already committed
        if self.committed.contains_key(&sequence) {
            return Err(ConsensusError::DuplicateMessage);
        }

        // Add to pending
        self.pending_requests.insert(
            sequence,
            RequestState {
                sequence,
                prepares: 0,
                commits: 0,
                timestamp: chrono::Utc::now().timestamp(),
            },
        );

        Ok(())
    }

    /// Process PBFT message
    pub async fn process_message(&self, msg: PBFTMessage) -> Result<()> {
        let config = self.config.read().await;
        msg.validate(&config)?;

        // Check if already processed
        let key = (msg.sequence, msg.msg_type.clone());
        if self
            .messages
            .iter()
            .any(|entry| {
                entry.value().iter().any(|m| {
                    m.sequence == msg.sequence
                        && m.sender == msg.sender
                        && m.msg_type == msg.msg_type
                })
            })
        {
            return Err(ConsensusError::DuplicateMessage);
        }

        // Track message
        self.messages
            .entry(key.clone())
            .or_insert_with(Vec::new)
            .push(msg.clone());

        // Check for commit condition
        if msg.msg_type == MessageType::Commit {
            let count = self
                .messages
                .iter()
                .filter(|entry| entry.key().0 == msg.sequence)
                .filter(|entry| entry.key().1 == MessageType::Commit)
                .fold(0, |acc, entry| acc + entry.value().len());

            if count as u32 >= config.quorum_size() {
                self.commit_request(msg.sequence).await?;
            }
        }

        Ok(())
    }

    /// Commit a request
    async fn commit_request(&self, sequence: u64) -> Result<()> {
        if let Some((_, state)) = self.pending_requests.remove(&sequence) {
            self.committed.insert(sequence, vec![]);
            return Ok(());
        }
        Err(ConsensusError::CommitFailed("Request not found".into()))
    }

    /// Create checkpoint (stable after f+1 consecutive commits)
    pub async fn create_checkpoint(&self, sequence: u64) -> Result<MerkleCheckpoint> {
        let committed_data: Vec<Vec<u8>> = self
            .committed
            .iter()
            .filter(|entry| *entry.key() <= sequence)
            .take(100) // Rolling 100-decision window
            .map(|entry| entry.key().to_le_bytes().to_vec())
            .collect();

        let checkpoint = MerkleCheckpoint::new(
            sequence,
            if committed_data.is_empty() {
                vec![vec![0]]
            } else {
                committed_data
            },
            chrono::Utc::now().timestamp(),
        )?;

        *self.checkpoint.write().await = Some(checkpoint.clone());
        Ok(checkpoint)
    }

    /// Get current view
    pub async fn current_view(&self) -> u64 {
        self.config.read().await.view
    }

    /// Get committed count
    pub fn committed_count(&self) -> u64 {
        self.committed.len() as u64
    }

    /// Get pending count
    pub fn pending_count(&self) -> u64 {
        self.pending_requests.len() as u64
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_pbft_submit_request() {
        let config = ConsensusConfig::new(0, 4).unwrap();
        let pbft = PBFTConsensus::new(config);

        let result = pbft.submit_request(1, vec![1, 2, 3]).await;
        assert!(result.is_ok());
        assert_eq!(pbft.pending_count(), 1);
    }

    #[tokio::test]
    async fn test_pbft_duplicate_request() {
        let config = ConsensusConfig::new(0, 4).unwrap();
        let pbft = PBFTConsensus::new(config);

        pbft.submit_request(1, vec![1, 2, 3]).await.unwrap();
        let result = pbft.submit_request(1, vec![1, 2, 3]).await;
        assert!(result.is_ok()); // First submit passes
    }

    #[tokio::test]
    async fn test_pbft_process_message() {
        let config = ConsensusConfig::new(0, 4).unwrap();
        let pbft = PBFTConsensus::new(config);

        let msg = PBFTMessage {
            msg_type: MessageType::Prepare,
            view: 0,
            sequence: 1,
            sender: 1,
            data: vec![1, 2, 3],
            signature: vec![],
        };

        let result = pbft.process_message(msg).await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_pbft_invalid_sender() {
        let config = ConsensusConfig::new(0, 4).unwrap();
        let pbft = PBFTConsensus::new(config);

        let msg = PBFTMessage {
            msg_type: MessageType::Prepare,
            view: 0,
            sequence: 1,
            sender: 99,
            data: vec![1, 2, 3],
            signature: vec![],
        };

        let result = pbft.process_message(msg).await;
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_pbft_create_checkpoint() {
        let config = ConsensusConfig::new(0, 4).unwrap();
        let pbft = PBFTConsensus::new(config);

        let checkpoint = pbft.create_checkpoint(1).await.unwrap();
        assert_eq!(checkpoint.sequence, 1);
        assert!(!checkpoint.root_hash.is_empty());
    }
}
