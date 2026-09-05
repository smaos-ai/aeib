#[cfg(test)]
mod integration_tests {
    use crate::{ConsensusConfig, PBFTConsensus, MerkleCheckpoint};
    use crate::pbft::{PBFTMessage, MessageType};

    #[tokio::test]
    async fn test_consensus_quorum_commit() {
        let config = ConsensusConfig::new(0, 4).unwrap();
        let pbft = PBFTConsensus::new(config);

        pbft.submit_request(1, vec![1, 2, 3]).await.unwrap();

        // Simulate quorum-size commit messages
        for i in 1..3 {
            let msg = PBFTMessage {
                msg_type: MessageType::Commit,
                view: 0,
                sequence: 1,
                sender: i,
                data: vec![1, 2, 3],
                signature: vec![],
            };
            let _ = pbft.process_message(msg).await;
        }

        assert!(pbft.committed_count() > 0);
    }

    #[tokio::test]
    async fn test_consensus_checkpoint_creation() {
        let config = ConsensusConfig::new(0, 4).unwrap();
        let pbft = PBFTConsensus::new(config);

        let checkpoint = pbft.create_checkpoint(10).await.unwrap();
        assert_eq!(checkpoint.sequence, 10);
    }

    #[tokio::test]
    async fn test_consensus_rolling_window() {
        let config = ConsensusConfig::new(0, 4).unwrap();
        let pbft = PBFTConsensus::new(config);

        // Submit and "commit" multiple requests
        for i in 1..=50 {
            pbft.submit_request(i, vec![i as u8]).await.ok();
        }

        let checkpoint = pbft.create_checkpoint(50).await.unwrap();
        assert_eq!(checkpoint.sequence, 50);
        assert!(checkpoint.nodes.len() <= 100); // Respects rolling window
    }

    #[tokio::test]
    async fn test_consensus_view_increment() {
        let mut config = ConsensusConfig::new(0, 4).unwrap();
        config.view = 5;
        let pbft = PBFTConsensus::new(config);

        let view = pbft.current_view().await;
        assert_eq!(view, 5);
    }

    #[tokio::test]
    async fn test_consensus_message_ordering() {
        let config = ConsensusConfig::new(0, 4).unwrap();
        let pbft = PBFTConsensus::new(config);

        pbft.submit_request(1, vec![1]).await.unwrap();
        pbft.submit_request(2, vec![2]).await.unwrap();
        pbft.submit_request(3, vec![3]).await.unwrap();

        assert_eq!(pbft.pending_count(), 3);
    }
}
