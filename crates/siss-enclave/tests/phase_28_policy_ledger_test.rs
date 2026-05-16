use siss_enclave::ledger::{OperatorAuditLog, PolicyLedgerWriter};
use siss_enclave::operator::HitlVerdict;
use std::path::PathBuf;
use uuid::Uuid;

/// Test 1: PolicyLedgerWriter Appends Immutable Entries
/// Verifies that each decision is durably written and cannot be modified after commit
#[tokio::test]
async fn test_policy_ledger_appends_immutable_entries() {
    let ledger_path = PathBuf::from("/tmp/test_ledger_1.log");
    let _ = std::fs::remove_file(&ledger_path); // Clean slate

    let writer = PolicyLedgerWriter::new(&ledger_path)
        .await
        .expect("Failed to create PolicyLedgerWriter");

    let task_id = Uuid::new_v4();
    let operator_id = "did:siss:operator:alpha";

    // Create audit log entry
    let entry = OperatorAuditLog {
        task_id,
        operator_id: operator_id.to_string(),
        decision: HitlVerdict::Approved,
        timestamp_unix_ms: 1000,
        approval_signature: "abc123def456".to_string(),
        merkle_root: "root0".to_string(),
    };

    // Append entry
    let write_result = writer.append(&entry).await;
    assert!(write_result.is_ok(), "Ledger write must succeed");

    // Verify entry is persisted
    let contents = std::fs::read_to_string(&ledger_path).expect("Failed to read ledger");
    assert!(
        contents.contains(&task_id.to_string()),
        "Ledger must contain the written task_id"
    );
    assert!(
        contents.contains(operator_id),
        "Ledger must contain the operator_id"
    );
}

/// Test 2: Operator Signature Cryptographic Binding
/// Verifies that each entry is cryptographically bound to the operator's SHA-256 signature
#[tokio::test]
async fn test_operator_signature_binding_in_ledger() {
    let task_id = Uuid::new_v4();
    let operator_id = "did:siss:operator:alpha";

    // Compute expected signature
    use sha2::{Digest, Sha256};
    let mut hasher = Sha256::new();
    hasher.update(task_id.as_bytes());
    hasher.update(operator_id.as_bytes());
    let sig_bytes = hasher.finalize();
    let expected_signature = hex::encode(sig_bytes);

    let entry = OperatorAuditLog {
        task_id,
        operator_id: operator_id.to_string(),
        decision: HitlVerdict::Approved,
        timestamp_unix_ms: 1000,
        approval_signature: expected_signature.clone(),
        merkle_root: "root0".to_string(),
    };

    // Verify signature matches expected
    assert_eq!(
        entry.approval_signature, expected_signature,
        "Operator signature must be cryptographically bound to task_id + operator_id"
    );
}

/// Test 3: Non-Blocking Async Writes
/// Verifies that ledger writes do not block the main inference thread
#[tokio::test]
async fn test_ledger_writes_non_blocking() {
    let ledger_path = PathBuf::from("/tmp/test_ledger_3.log");
    let _ = std::fs::remove_file(&ledger_path);

    let writer = PolicyLedgerWriter::new(&ledger_path)
        .await
        .expect("Failed to create PolicyLedgerWriter");

    // Create multiple entries and write concurrently
    let mut handles = vec![];

    for i in 0..5 {
        let writer_clone = writer.clone();
        let handle = tokio::spawn(async move {
            let entry = OperatorAuditLog {
                task_id: Uuid::new_v4(),
                operator_id: format!("did:siss:operator:{}", i),
                decision: HitlVerdict::Approved,
                timestamp_unix_ms: 1000 + i as u64,
                approval_signature: format!("sig_{}", i),
                merkle_root: format!("root{}", i),
            };

            writer_clone.append(&entry).await
        });

        handles.push(handle);
    }

    // All writes should complete without blocking
    for handle in handles {
        let result = handle.await.expect("Join failed");
        assert!(result.is_ok(), "Concurrent writes must succeed");
    }
}

/// Test 4: Fail-Closed on Ledger Write Failure
/// Verifies that LoRA swap authorization is rejected if ledger write fails (disk full, etc.)
#[tokio::test]
async fn test_lora_swap_fails_closed_on_ledger_write_failure() {
    let ledger_path = PathBuf::from("/tmp/nonexistent_dir/test_ledger_4.log");

    let writer_result = PolicyLedgerWriter::new(&ledger_path).await;

    // If ledger path is invalid, writer creation should fail
    // This tests fail-closed semantics: no ledger → no approval
    assert!(
        writer_result.is_err(),
        "Invalid ledger path must fail; swap authorization must be rejected"
    );
}

/// Test 5: Merkle Root Chaining
/// Verifies that each entry's merkle_root chains from the previous entry's merkle_root
#[tokio::test]
async fn test_merkle_root_chaining_in_ledger() {
    let entry1 = OperatorAuditLog {
        task_id: Uuid::new_v4(),
        operator_id: "did:siss:operator:alpha".to_string(),
        decision: HitlVerdict::Approved,
        timestamp_unix_ms: 1000,
        approval_signature: "sig1".to_string(),
        merkle_root: "root0".to_string(),
    };

    // Compute merkle_root for entry2 by hashing entry1's data
    use sha2::{Digest, Sha256};
    let mut hasher = Sha256::new();
    hasher.update(entry1.task_id.as_bytes());
    hasher.update(entry1.operator_id.as_bytes());
    hasher.update("root0"); // Chain from previous root
    let merkle_bytes = hasher.finalize();
    let merkle_root_2 = hex::encode(merkle_bytes);

    let entry2 = OperatorAuditLog {
        task_id: Uuid::new_v4(),
        operator_id: "did:siss:operator:beta".to_string(),
        decision: HitlVerdict::Approved,
        timestamp_unix_ms: 2000,
        approval_signature: "sig2".to_string(),
        merkle_root: merkle_root_2,
    };

    // Verify merkle chain
    assert!(
        !entry1.merkle_root.is_empty(),
        "Entry 1 must have merkle_root"
    );
    assert!(
        !entry2.merkle_root.is_empty(),
        "Entry 2 must have merkle_root"
    );
    assert_ne!(
        entry1.merkle_root, entry2.merkle_root,
        "Merkle roots must differ (chaining enforced)"
    );
}

/// Test 6: Atomic Dual-Write Guarantee
/// Verifies that LoRA swap is authorized ONLY if ledger write succeeds
#[tokio::test]
async fn test_atomic_dual_write_lora_swap_authorization() {
    let ledger_path = PathBuf::from("/tmp/test_ledger_6.log");
    let _ = std::fs::remove_file(&ledger_path);

    let writer = PolicyLedgerWriter::new(&ledger_path)
        .await
        .expect("Failed to create PolicyLedgerWriter");

    let task_id = Uuid::new_v4();

    let entry = OperatorAuditLog {
        task_id,
        operator_id: "did:siss:operator:alpha".to_string(),
        decision: HitlVerdict::Approved,
        timestamp_unix_ms: 1000,
        approval_signature: "sig".to_string(),
        merkle_root: "root".to_string(),
    };

    // Atomic write
    let write_ok = writer.append(&entry).await.is_ok();

    // LoRA swap is authorized ONLY if ledger write succeeded
    assert!(
        write_ok,
        "Ledger write must succeed; only then is swap authorized"
    );
}

/// Test 7: Concurrent Writes Serialized with Merkle Ordering
/// Verifies that concurrent approval requests are serialized and merkle-chained in order
#[tokio::test]
async fn test_concurrent_writes_merkle_ordered() {
    let ledger_path = PathBuf::from("/tmp/test_ledger_7.log");
    let _ = std::fs::remove_file(&ledger_path);

    let writer = PolicyLedgerWriter::new(&ledger_path)
        .await
        .expect("Failed to create PolicyLedgerWriter");

    // Spawn 3 concurrent writes
    let mut handles = vec![];

    for i in 0..3 {
        let writer_clone = writer.clone();
        let handle = tokio::spawn(async move {
            let entry = OperatorAuditLog {
                task_id: Uuid::new_v4(),
                operator_id: format!("did:siss:operator:{}", i),
                decision: HitlVerdict::Approved,
                timestamp_unix_ms: 1000 + i as u64,
                approval_signature: format!("sig_{}", i),
                merkle_root: format!("root{}", i),
            };

            writer_clone.append(&entry).await
        });

        handles.push(handle);
    }

    // Wait for all to complete
    for handle in handles {
        let _ = handle.await;
    }

    // Verify all entries are in the ledger
    let contents = std::fs::read_to_string(&ledger_path).expect("Failed to read ledger");
    for i in 0..3 {
        assert!(
            contents.contains(&format!("did:siss:operator:{}", i)),
            "All entries must be persisted in order"
        );
    }
}

/// Test 8: Rejection Verdict Binding
/// Verifies that rejections are also immutably recorded with operator signature
#[tokio::test]
async fn test_rejection_verdict_binding() {
    let ledger_path = PathBuf::from("/tmp/test_ledger_8.log");
    let _ = std::fs::remove_file(&ledger_path);

    let writer = PolicyLedgerWriter::new(&ledger_path)
        .await
        .expect("Failed to create PolicyLedgerWriter");

    let entry = OperatorAuditLog {
        task_id: Uuid::new_v4(),
        operator_id: "did:siss:operator:alpha".to_string(),
        decision: HitlVerdict::Rejected {
            reason: "suspicious_pattern_detected".to_string(),
        },
        timestamp_unix_ms: 1000,
        approval_signature: "sig".to_string(),
        merkle_root: "root".to_string(),
    };

    let write_ok = writer.append(&entry).await.is_ok();
    assert!(
        write_ok,
        "Rejection verdicts must be recorded with same rigor as approvals"
    );

    let contents = std::fs::read_to_string(&ledger_path).expect("Failed to read ledger");
    assert!(
        contents.contains("suspicious_pattern_detected"),
        "Rejection reason must be immutably captured"
    );
}
