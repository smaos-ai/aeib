use proptest::prelude::*;
use siss_governance::{DecisionRecord, DecisionStore};
use siss_governance::decision_store::{DecisionDb, DecisionDbConfig};

fn arb_decision_record() -> impl Strategy<Value = DecisionRecord> {
    (
        "[a-z]{3,20}",
        "[a-z ]{10,50}",
        "[a-z ]{10,50}",
    )
        .prop_map(|(cat, ctx, dec)| DecisionRecord {
            category: cat.to_string(),
            context: ctx.to_string(),
            decision: dec.to_string(),
        })
}

proptest! {
    #[test]
    fn prop_record_query_roundtrip(rec in arb_decision_record()) {
        let db = DecisionDb::new(None).expect("db creation");
        let id = db.record(rec.clone()).expect("record");
        let active = db.query_active().expect("query");

        prop_assert!(!active.is_empty());
        prop_assert!(active.iter().any(|d| d.id == id));
        prop_assert!(active.iter().all(|d| d.status == "ACTIVE"));
    }

    #[test]
    fn prop_chain_integrity_after_n_records(_n in 1usize..20, recs in prop::collection::vec(arb_decision_record(), 1..20)) {
        let db = DecisionDb::new(None).expect("db creation");

        for rec in &recs {
            db.record(rec.clone()).expect("record");
        }

        let valid = db.verify_chain().expect("verify");
        prop_assert!(valid);
    }

    #[test]
    fn prop_merkle_hash_deterministic(rec in arb_decision_record()) {
        let h1 = siss_governance::compute_merkle_hash(None, "id1", &rec.context, &rec.decision);
        let h2 = siss_governance::compute_merkle_hash(None, "id1", &rec.context, &rec.decision);
        prop_assert_eq!(h1, h2);
    }

    #[test]
    fn prop_query_by_category_filters_correctly(recs in prop::collection::vec(arb_decision_record(), 1..20)) {
        let db = DecisionDb::new(None).expect("db creation");

        for rec in &recs {
            db.record(rec.clone()).expect("record");
        }

        let categories: std::collections::HashSet<_> = recs.iter().map(|r| r.category.clone()).collect();

        for cat in categories {
            let matching = db.query_by_category(&cat).expect("query");
            prop_assert!(matching.iter().all(|d| d.category == cat));
            prop_assert!(!matching.is_empty());
        }
    }

    #[test]
    fn prop_retention_floor_blocks_delete_at_boundary(n in 1u64..=10u64) {
        let floor = 5u64;
        let cfg = DecisionDbConfig { retention_floor: floor };
        let db = DecisionDb::with_config(None, cfg).expect("db creation");

        // Insert floor + n records
        let num_to_insert = floor + n;
        let mut ids = Vec::new();
        for _ in 0..num_to_insert {
            let rec = DecisionRecord {
                category: "test".into(),
                context: "test context".into(),
                decision: "test decision".into(),
            };
            let id = db.record(rec).expect("record");
            ids.push(id);
        }

        // Attempt to delete all records; should succeed until count <= floor
        let mut delete_count = 0;
        for id in ids {
            match db.delete(&id) {
                Ok(()) => delete_count += 1,
                Err(siss_governance::decision_store::StoreError::RetentionFloorViolation { floor: _, current }) => {
                    // Delete blocked; verify count is at or below floor
                    prop_assert!(current <= floor);
                    break;
                }
                Err(e) => prop_assert!(false, "Unexpected error: {:?}", e),
            }
        }

        // We should have deleted exactly (num_to_insert - floor) records
        prop_assert_eq!(delete_count, n);
    }

    #[test]
    fn prop_insert_unaffected_by_floor(recs in prop::collection::vec(arb_decision_record(), 1..20)) {
        let cfg = DecisionDbConfig { retention_floor: 100 };
        let db = DecisionDb::with_config(None, cfg).expect("db creation");

        // All inserts should succeed regardless of floor
        for rec in &recs {
            let _id = db.record(rec.clone()).expect("insert should always succeed");
        }

        let active = db.query_active().expect("query");
        prop_assert_eq!(active.len(), recs.len());
    }

    #[test]
    fn prop_chain_intact_after_revoke(n in 2usize..=15usize) {
        let db = DecisionDb::new(None).expect("db creation");
        let mut ids = Vec::new();

        // Insert n records
        for _ in 0..n {
            let rec = DecisionRecord {
                category: "test".into(),
                context: "test context".into(),
                decision: "test decision".into(),
            };
            let id = db.record(rec).expect("record");
            ids.push(id);
        }

        // Revoke a middle record (not first or last, if n > 2)
        if n > 2 {
            let revoke_idx = n / 2;
            let revoke_id = &ids[revoke_idx];
            db.delete(revoke_id).expect("delete succeeds");
        }

        // Chain should still be valid (soft-delete preserves Merkle integrity)
        let valid = db.verify_chain().expect("verify");
        prop_assert!(valid);
    }
}

#[cfg(test)]
mod unit_tests {
    use super::*;

    #[test]
    fn test_fixture_decisions() {
        let db = DecisionDb::new(None).expect("db creation");
        let fixture = siss_governance::decision_store::fixture_decisions();

        for rec in fixture {
            let id = db.record(rec).expect("record");
            assert!(!id.is_empty());
        }

        let active = db.query_active().expect("query");
        assert_eq!(active.len(), 3);
    }

    #[test]
    fn test_verify_chain_valid() {
        let db = DecisionDb::new(None).expect("db creation");
        let rec = DecisionRecord {
            category: "test".into(),
            context: "test context".into(),
            decision: "test decision".into(),
        };
        db.record(rec).expect("record");
        let valid = db.verify_chain().expect("verify");
        assert!(valid);
    }

    #[test]
    fn test_empty_chain_is_valid() {
        let db = DecisionDb::new(None).expect("db creation");
        let valid = db.verify_chain().expect("verify");
        assert!(valid);
    }
}
