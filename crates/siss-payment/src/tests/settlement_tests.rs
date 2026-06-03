#[cfg(test)]
mod settlement_tests {
    use crate::ledger::*;
    use uuid::Uuid;

    #[test]
    fn test_settlement_splits_99_1() {
        let ledger = AP2Ledger::new();
        let creator_id = Uuid::new_v4();
        let settlement = ledger.settle(creator_id, 10000);

        assert_eq!(settlement.platform_fee_cents, 100, "Platform should get 1%");
        assert_eq!(settlement.creator_payout_cents, 9900, "Creator should get 99%");
        assert_eq!(settlement.amount_cents, 10000, "Total should be input");
    }

    #[test]
    fn test_merkle_root_changes_on_settlement() {
        let ledger = AP2Ledger::new();
        let root1 = ledger.get_merkle_root();

        let creator_id = Uuid::new_v4();
        ledger.settle(creator_id, 10000);

        let root2 = ledger.get_merkle_root();
        assert_ne!(root1, root2, "Merkle root must change after settlement");
    }

    #[test]
    fn test_batch_settlements_accumulate() {
        let ledger = AP2Ledger::new();
        let creator_id = Uuid::new_v4();

        for i in 0..10 {
            ledger.settle(creator_id, 5000 + i as i64);
        }

        let balance = ledger.get_creator_balance(creator_id);
        assert!(balance > 49000, "Creator balance should accumulate 99% of all settlements");
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
