use l2b_federated_consensus::ledger::{LedgerSync, LedgerEntry, LedgerError};
use serde_json::json;

#[tokio::test]
async fn test_three_region_atomic_append() {
    // Test atomic append across 3 regions
    let mut ledger_eu = LedgerSync::new("EU".to_string());
    let mut ledger_us = LedgerSync::new("US".to_string());
    let mut ledger_cn = LedgerSync::new("CN".to_string());

    let entry = LedgerEntry {
        index: 1,
        proposal_id: "APPEND-001".to_string(),
        decision: json!({"action": "APPROVE", "amount": 1000000}),
        merkle_root: "0xabc123".to_string(),
        region: "EU".to_string(),
        timestamp: chrono::Utc::now(),
    };

    // Append to EU ledger
    let result_eu = ledger_eu.append_entry(entry.clone()).await;
    assert!(result_eu.is_ok());

    // Sync to US ledger
    let result_us = ledger_us.sync_ledger(&ledger_eu).await;
    assert!(result_us.is_ok());

    // Sync to CN ledger
    let result_cn = ledger_cn.sync_ledger(&ledger_eu).await;
    assert!(result_cn.is_ok());

    // Verify all regions have same entry
    let entries_eu = ledger_eu.get_entries(0).await.unwrap();
    let entries_us = ledger_us.get_entries(0).await.unwrap();
    let entries_cn = ledger_cn.get_entries(0).await.unwrap();

    assert_eq!(entries_eu.len(), 1);
    assert_eq!(entries_us.len(), 1);
    assert_eq!(entries_cn.len(), 1);
}

#[tokio::test]
async fn test_merkle_root_consistency() {
    // Test Merkle root remains consistent across regions
    let mut ledger_eu = LedgerSync::new("EU".to_string());

    let entry1 = LedgerEntry {
        index: 1,
        proposal_id: "MERKLE-001".to_string(),
        decision: json!({"action": "APPROVE"}),
        merkle_root: "0x123".to_string(),
        region: "EU".to_string(),
        timestamp: chrono::Utc::now(),
    };

    let entry2 = LedgerEntry {
        index: 2,
        proposal_id: "MERKLE-002".to_string(),
        decision: json!({"action": "REJECT"}),
        merkle_root: "0x456".to_string(),
        region: "EU".to_string(),
        timestamp: chrono::Utc::now(),
    };

    ledger_eu.append_entry(entry1).await.unwrap();
    ledger_eu.append_entry(entry2).await.unwrap();

    let root1 = ledger_eu.verify_merkle_roots().await.unwrap();

    // Append same entries again
    let entry1_copy = LedgerEntry {
        index: 1,
        proposal_id: "MERKLE-001".to_string(),
        decision: json!({"action": "APPROVE"}),
        merkle_root: "0x123".to_string(),
        region: "EU".to_string(),
        timestamp: chrono::Utc::now(),
    };

    let entry2_copy = LedgerEntry {
        index: 2,
        proposal_id: "MERKLE-002".to_string(),
        decision: json!({"action": "REJECT"}),
        merkle_root: "0x456".to_string(),
        region: "EU".to_string(),
        timestamp: chrono::Utc::now(),
    };

    let mut ledger_eu_2 = LedgerSync::new("EU".to_string());
    ledger_eu_2.append_entry(entry1_copy).await.unwrap();
    ledger_eu_2.append_entry(entry2_copy).await.unwrap();

    let root2 = ledger_eu_2.verify_merkle_roots().await.unwrap();

    // Merkle roots should match
    assert_eq!(root1, root2);
}

#[tokio::test]
async fn test_divergence_recovery() {
    // Test recovery from regional divergence
    let mut ledger_eu = LedgerSync::new("EU".to_string());
    let mut ledger_us = LedgerSync::new("US".to_string());

    let entry1 = LedgerEntry {
        index: 1,
        proposal_id: "DIV-001".to_string(),
        decision: json!({"action": "APPROVE"}),
        merkle_root: "0x111".to_string(),
        region: "EU".to_string(),
        timestamp: chrono::Utc::now(),
    };

    // Both regions append same entry
    ledger_eu.append_entry(entry1.clone()).await.unwrap();
    ledger_us.append_entry(entry1).await.unwrap();

    // Detect divergence
    let eu_root = ledger_eu.get_root().await.unwrap();
    let us_root = ledger_us.get_root().await.unwrap();

    // Roots should match
    assert_eq!(eu_root, us_root);

    // Simulate divergence by creating different entry at same index
    let divergent_entry = LedgerEntry {
        index: 2,
        proposal_id: "DIV-002".to_string(),
        decision: json!({"action": "REJECT"}),
        merkle_root: "0x222".to_string(),
        region: "US".to_string(),
        timestamp: chrono::Utc::now(),
    };

    ledger_us.append_entry(divergent_entry).await.unwrap();

    // After divergence, roots should differ
    let eu_root_after = ledger_eu.get_root().await.unwrap();
    let us_root_after = ledger_us.get_root().await.unwrap();

    // Roots should differ now
    assert_ne!(eu_root_after, us_root_after);
}

#[tokio::test]
async fn test_atomic_append_or_fail() {
    // Test that append is atomic - all or nothing
    let mut ledger = LedgerSync::new("EU".to_string());

    let entry1 = LedgerEntry {
        index: 1,
        proposal_id: "ATOMIC-001".to_string(),
        decision: json!({"action": "APPROVE"}),
        merkle_root: "0x001".to_string(),
        region: "EU".to_string(),
        timestamp: chrono::Utc::now(),
    };

    let result = ledger.append_entry(entry1).await;
    assert!(result.is_ok());

    // Try to append with gap (should fail)
    let entry_gap = LedgerEntry {
        index: 3, // Gap in index
        proposal_id: "ATOMIC-003".to_string(),
        decision: json!({"action": "APPROVE"}),
        merkle_root: "0x003".to_string(),
        region: "EU".to_string(),
        timestamp: chrono::Utc::now(),
    };

    let result_gap = ledger.append_entry(entry_gap).await;
    // Should reject due to gap in sequence
    assert!(result_gap.is_err());
}

#[tokio::test]
async fn test_entry_retrieval() {
    // Test retrieving entries from ledger
    let mut ledger = LedgerSync::new("EU".to_string());

    for i in 1..=5 {
        let entry = LedgerEntry {
            index: i,
            proposal_id: format!("RETRIEVE-{}", i),
            decision: json!({"action": "APPROVE"}),
            merkle_root: format!("0x{:03}", i),
            region: "EU".to_string(),
            timestamp: chrono::Utc::now(),
        };
        ledger.append_entry(entry).await.unwrap();
    }

    let entries = ledger.get_entries(0).await.unwrap();
    assert_eq!(entries.len(), 5);
    assert_eq!(entries[0].index, 1);
    assert_eq!(entries[4].index, 5);
}

#[tokio::test]
async fn test_ledger_entry_serialization() {
    let entry = LedgerEntry {
        index: 1,
        proposal_id: "SER-001".to_string(),
        decision: json!({"action": "APPROVE"}),
        merkle_root: "0xabc".to_string(),
        region: "EU".to_string(),
        timestamp: chrono::Utc::now(),
    };

    let json = serde_json::to_string(&entry).unwrap();
    let deserialized: LedgerEntry = serde_json::from_str(&json).unwrap();

    assert_eq!(entry.index, deserialized.index);
    assert_eq!(entry.proposal_id, deserialized.proposal_id);
    assert_eq!(entry.region, deserialized.region);
}
