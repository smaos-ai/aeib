use crate::a2a_protocol::A2AMessage;

pub enum ConflictStrategy {
    HighestHash,
    VectorClock,
}

pub struct ConflictResolver {
    pub strategy: ConflictStrategy,
}

impl ConflictResolver {
    pub fn new(strategy: ConflictStrategy) -> Self {
        Self { strategy }
    }

    pub fn resolve(&self, entry1: &A2AMessage, entry2: &A2AMessage) -> A2AMessage {
        match self.strategy {
            ConflictStrategy::HighestHash => {
                if bytes_to_u256(&entry2.merkle_hash) >= bytes_to_u256(&entry1.merkle_hash) {
                    entry2.clone()
                } else {
                    entry1.clone()
                }
            }
            ConflictStrategy::VectorClock => {
                if entry2.timestamp > entry1.timestamp {
                    entry2.clone()
                } else {
                    entry1.clone()
                }
            }
        }
    }
}

fn bytes_to_u256(bytes: &[u8; 32]) -> u128 {
    let mut result = 0u128;
    for byte in bytes.iter().take(16) {
        result = (result << 8) | (*byte as u128);
    }
    result
}
