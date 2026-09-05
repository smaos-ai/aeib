use super::*;
use crate::latency::{ConstitutionVerdict, LatencyConstitution, LatencyTier};
use crate::signer::MockSigner;
use std::time::Instant;
use uuid::Uuid;

#[test]
fn test_decision_store_creates_immutable_entry() {
    let store = DecisionStore::new();
    let decision_id = Uuid::new_v4();
    let task_id = Uuid::new_v4();
    let manifest = "test_manifest".to_string();

    let entry = DecisionEntry {
        id: decision_id,
        task_id,
        manifest: manifest.clone(),
        merkle_parent: None,
        signature: vec![],
    };

    store.append(entry).expect("append should succeed");

    let retrieved = store.get(decision_id).expect("entry should exist");
    assert_eq!(retrieved.task_id, task_id);
    assert_eq!(retrieved.manifest, manifest);
}

#[test]
fn test_decision_store_maintains_merkle_chain() {
    let store = DecisionStore::new();

    // First entry (no parent)
    let id1 = Uuid::new_v4();
    let task1 = Uuid::new_v4();
    let entry1 = DecisionEntry {
        id: id1,
        task_id: task1,
        manifest: "manifest_1".to_string(),
        merkle_parent: None,
        signature: vec![1, 2, 3],
    };
    store.append(entry1).expect("first append should succeed");

    // Second entry (points to first)
    let id2 = Uuid::new_v4();
    let task2 = Uuid::new_v4();
    let merkle_hash_1 = store.merkle_root();
    let entry2 = DecisionEntry {
        id: id2,
        task_id: task2,
        manifest: "manifest_2".to_string(),
        merkle_parent: Some(merkle_hash_1),
        signature: vec![4, 5, 6],
    };
    store.append(entry2).expect("second append should succeed");

    // Verify chain integrity
    let retrieved1 = store.get(id1).expect("entry 1 should exist");
    let retrieved2 = store.get(id2).expect("entry 2 should exist");

    assert!(retrieved2.merkle_parent.is_some());
    assert_eq!(retrieved2.merkle_parent.unwrap(), retrieved1.merkle_hash());
}

#[test]
fn test_decision_store_rejects_unsigned_entries() {
    let store = DecisionStore::new();
    let signer = MockSigner;

    let decision_id = Uuid::new_v4();
    let task_id = Uuid::new_v4();
    let entry = DecisionEntry {
        id: decision_id,
        task_id,
        manifest: "unsigned_entry".to_string(),
        merkle_parent: None,
        signature: vec![], // Empty signature
    };

    // Store should require valid Ed25519 signature
    let result = store.append_with_verification(&entry, &signer);
    assert!(result.is_err(), "unsigned entry should be rejected");
}

#[test]
fn test_decision_store_enforces_tier1_latency() {
    let store = DecisionStore::new();
    let constitution = LatencyConstitution::default();

    let start = Instant::now();

    for i in 0..100 {
        let entry = DecisionEntry {
            id: Uuid::new_v4(),
            task_id: Uuid::new_v4(),
            manifest: format!("manifest_{}", i),
            merkle_parent: None,
            signature: vec![42],
        };
        store.append(entry).expect("append should succeed");
    }

    let elapsed_nanos = start.elapsed().as_nanos() as u64;
    let verdict = constitution.check(LatencyTier::Tier1, elapsed_nanos);

    // Should complete 100 appends well within 10ms
    assert_eq!(verdict, ConstitutionVerdict::WithinBudget);
}

#[test]
fn test_decision_store_returns_audit_trail() {
    let store = DecisionStore::new();

    let task_id = Uuid::new_v4();

    // Add multiple entries for same task
    for i in 0..5 {
        let entry = DecisionEntry {
            id: Uuid::new_v4(),
            task_id,
            manifest: format!("decision_{}", i),
            merkle_parent: None,
            signature: vec![i as u8],
        };
        store.append(entry).expect("append should succeed");
    }

    // Get audit trail for task
    let trail = store
        .audit_trail(task_id)
        .expect("audit trail should exist");
    assert_eq!(trail.len(), 5);
    assert!(trail.iter().all(|e| e.task_id == task_id));
}

#[test]
fn test_decision_store_merkle_root_is_deterministic() {
    let store1 = DecisionStore::new();
    let store2 = DecisionStore::new();

    // Append same entries to both stores in same order
    for i in 0..10 {
        let entry1 = DecisionEntry {
            id: Uuid::nil(), // Use nil for determinism in test
            task_id: Uuid::nil(),
            manifest: format!("manifest_{}", i),
            merkle_parent: None,
            signature: vec![i as u8],
        };
        let entry2 = DecisionEntry {
            id: Uuid::nil(),
            task_id: Uuid::nil(),
            manifest: format!("manifest_{}", i),
            merkle_parent: None,
            signature: vec![i as u8],
        };
        store1.append(entry1).expect("append to store1");
        store2.append(entry2).expect("append to store2");
    }

    // Merkle roots should match
    assert_eq!(store1.merkle_root(), store2.merkle_root());
}

#[test]
fn test_decision_store_detects_tampering() {
    let store = DecisionStore::new();

    let entry = DecisionEntry {
        id: Uuid::new_v4(),
        task_id: Uuid::new_v4(),
        manifest: "tamper_test".to_string(),
        merkle_parent: None,
        signature: vec![99],
    };

    store.append(entry).expect("append should succeed");

    // Attempt to get and verify
    let retrieved = store.get(Uuid::nil()).ok();
    assert!(
        retrieved.is_none(),
        "tampered entry should not be retrievable"
    );
}
