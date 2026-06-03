use sha2::{Digest, Sha256};
use std::sync::Arc;
use uuid::Uuid;
use dashmap::DashMap;
use parking_lot::RwLock;

#[derive(Debug, Clone, Copy)]
pub struct Settlement {
    pub creator_id: Uuid,
    pub amount_cents: i64,
    pub platform_fee_cents: i64,
    pub creator_payout_cents: i64,
    pub merkle_root: [u8; 32],
    pub timestamp_nanos: u64,
}

pub struct AP2Ledger {
    settlements: Arc<DashMap<Uuid, Vec<Settlement>>>,
    merkle_root: Arc<RwLock<[u8; 32]>>,
}

impl AP2Ledger {
    pub fn new() -> Self {
        Self {
            settlements: Arc::new(DashMap::new()),
            merkle_root: Arc::new(RwLock::new([0u8; 32])),
        }
    }

    pub fn settle(&self, creator_id: Uuid, amount_cents: i64) -> Settlement {
        let platform_fee = (amount_cents + 99) / 100;
        let creator_payout = amount_cents - platform_fee;

        let settlement = Settlement {
            creator_id,
            amount_cents,
            platform_fee_cents: platform_fee,
            creator_payout_cents: creator_payout,
            merkle_root: self.compute_merkle(&[creator_id.as_bytes()]),
            timestamp_nanos: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos() as u64,
        };

        self.settlements
            .entry(creator_id)
            .or_insert_with(Vec::new)
            .push(settlement);

        self.update_merkle_root();

        settlement
    }

    fn compute_merkle(&self, data: &[&[u8]]) -> [u8; 32] {
        let mut hasher = Sha256::new();
        for d in data {
            hasher.update(d);
        }
        let result = hasher.finalize();
        let mut root = [0u8; 32];
        root.copy_from_slice(&result);
        root
    }

    fn update_merkle_root(&self) {
        let mut all_data = Vec::new();
        for entry in self.settlements.iter() {
            for settlement in entry.value() {
                all_data.extend_from_slice(&settlement.merkle_root);
            }
        }
        let new_root = self.compute_merkle(&[all_data.as_slice()]);
        *self.merkle_root.write() = new_root;
    }

    pub fn get_merkle_root(&self) -> [u8; 32] {
        *self.merkle_root.read()
    }

    pub fn get_creator_balance(&self, creator_id: Uuid) -> i64 {
        self.settlements
            .get(&creator_id)
            .map(|settlements| {
                settlements.iter().map(|s| s.creator_payout_cents).sum()
            })
            .unwrap_or(0)
    }

    pub fn get_platform_balance(&self) -> i64 {
        self.settlements
            .iter()
            .flat_map(|entry| {
                entry
                    .value()
                    .iter()
                    .map(|s| s.platform_fee_cents)
                    .collect::<Vec<_>>()
            })
            .sum()
    }

    pub fn settlement_count(&self) -> usize {
        self.settlements.iter().map(|e| e.value().len()).sum()
    }
}

impl Default for AP2Ledger {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_settlement_splits_99_1() {
        let ledger = AP2Ledger::new();
        let creator_id = Uuid::new_v4();

        let settlement = ledger.settle(creator_id, 10000);

        assert_eq!(settlement.platform_fee_cents, 100);
        assert_eq!(settlement.creator_payout_cents, 9900);
        assert_eq!(settlement.amount_cents, 10000);
    }

    #[test]
    fn test_settlement_merkle_root_changes() {
        let ledger = AP2Ledger::new();
        let root1 = ledger.get_merkle_root();

        let creator_id = Uuid::new_v4();
        ledger.settle(creator_id, 10000);

        let root2 = ledger.get_merkle_root();
        assert_ne!(root1, root2, "Merkle root should change after settlement");
    }

    #[test]
    fn test_creator_balance_accumulates() {
        let ledger = AP2Ledger::new();
        let creator_id = Uuid::new_v4();

        ledger.settle(creator_id, 10000);
        ledger.settle(creator_id, 5000);

        let balance = ledger.get_creator_balance(creator_id);
        assert_eq!(balance, 14850);
    }

    #[test]
    fn test_multiple_creators_independent() {
        let ledger = AP2Ledger::new();
        let creator1 = Uuid::new_v4();
        let creator2 = Uuid::new_v4();

        ledger.settle(creator1, 10000);
        ledger.settle(creator2, 10000);

        assert_eq!(ledger.get_creator_balance(creator1), 9900);
        assert_eq!(ledger.get_creator_balance(creator2), 9900);
    }

    #[test]
    fn test_platform_balance_tracks_fees() {
        let ledger = AP2Ledger::new();
        let creator1 = Uuid::new_v4();
        let creator2 = Uuid::new_v4();

        ledger.settle(creator1, 10000);
        ledger.settle(creator2, 10000);

        let platform_balance = ledger.get_platform_balance();
        assert_eq!(platform_balance, 200); // 100 + 100
    }

    #[test]
    fn test_settlement_count() {
        let ledger = AP2Ledger::new();
        let creator_id = Uuid::new_v4();

        assert_eq!(ledger.settlement_count(), 0);

        ledger.settle(creator_id, 10000);
        assert_eq!(ledger.settlement_count(), 1);

        ledger.settle(creator_id, 5000);
        assert_eq!(ledger.settlement_count(), 2);
    }

    #[test]
    fn test_settlement_latency_reasonable() {
        let ledger = AP2Ledger::new();
        let creator_id = Uuid::new_v4();

        // Test single settlement is fast
        let start = std::time::Instant::now();
        ledger.settle(creator_id, 10000);
        let single_elapsed = start.elapsed();
        assert!(single_elapsed.as_millis() < 50, "Single settlement: {:?}", single_elapsed);

        // Test batch of 100 is reasonable (should be <1s)
        let start = std::time::Instant::now();
        for i in 0..100 {
            ledger.settle(creator_id, 10000 + i);
        }
        let batch_elapsed = start.elapsed();
        assert!(batch_elapsed.as_secs() < 2, "Batch of 100: {:?}", batch_elapsed);
    }

    #[test]
    fn test_settlement_splits_99_1_new() {
        let ledger = AP2Ledger::new();
        let creator_id = Uuid::new_v4();
        let settlement = ledger.settle(creator_id, 10000);

        assert_eq!(settlement.platform_fee_cents, 100, "Platform should get 1%");
        assert_eq!(settlement.creator_payout_cents, 9900, "Creator should get 99%");
        assert_eq!(settlement.amount_cents, 10000, "Total should be input");
    }

    #[test]
    fn test_platform_fee_enforces_floor() {
        let ledger = AP2Ledger::new();
        let creator_id = Uuid::new_v4();

        // Small amount: $0.50 should give platform $0.01 (ceiling)
        let settlement = ledger.settle(creator_id, 50);
        assert!(settlement.platform_fee_cents >= 1, "Platform must get at least 1 cent");
    }

    #[test]
    fn test_creator_never_cheated() {
        let ledger = AP2Ledger::new();
        let creator_id = Uuid::new_v4();
        let amount = 10000;

        let settlement = ledger.settle(creator_id, amount);

        let total = settlement.platform_fee_cents + settlement.creator_payout_cents;
        assert_eq!(total, amount, "Sum of fee + payout must equal original amount");
        assert!(settlement.creator_payout_cents >= (amount * 99) / 100, "Creator must get >=99%");
    }
}
