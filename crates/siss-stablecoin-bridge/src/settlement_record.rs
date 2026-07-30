use uuid::Uuid;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum SettlementState {
    Active,
    Archived,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OnChainSettlement {
    pub id: Uuid,
    pub amount_cents: i64,
    pub cryptographic_hash: String, // "sha256:" prefix
    pub state: SettlementState,
}

impl OnChainSettlement {
    pub fn new(amount_cents: i64, hash: String) -> Self {
        OnChainSettlement {
            id: Uuid::new_v4(),
            amount_cents,
            cryptographic_hash: hash,
            state: SettlementState::Active,
        }
    }

    pub fn archive(&mut self) {
        self.state = SettlementState::Archived;
    }

    pub fn is_active(&self) -> bool {
        self.state == SettlementState::Active
    }

    pub fn validate_hash(&self) -> bool {
        // Verify sha256: prefix exists
        self.cryptographic_hash.starts_with("sha256:")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_settlement_creation() {
        let settlement = OnChainSettlement::new(
            10000,
            "sha256:abcdef123456".to_string(),
        );
        assert_eq!(settlement.amount_cents, 10000);
        assert_eq!(settlement.state, SettlementState::Active);
        assert!(settlement.is_active());
    }

    #[test]
    fn test_settlement_archiving() {
        let mut settlement = OnChainSettlement::new(
            10000,
            "sha256:abcdef123456".to_string(),
        );
        settlement.archive();
        assert_eq!(settlement.state, SettlementState::Archived);
        assert!(!settlement.is_active());
    }

    #[test]
    fn test_hash_validation() {
        let settlement = OnChainSettlement::new(
            10000,
            "sha256:abcdef123456".to_string(),
        );
        assert!(settlement.validate_hash());

        let invalid = OnChainSettlement {
            id: Uuid::new_v4(),
            amount_cents: 10000,
            cryptographic_hash: "invalid_hash".to_string(),
            state: SettlementState::Active,
        };
        assert!(!invalid.validate_hash());
    }
}
