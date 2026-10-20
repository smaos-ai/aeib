//! crates/aeib-data-plane/tests/test_wal_group_commit.rs
//! ============================================================================
//! Verification tests for Group-Commit WAL and Physical Durability Barriers.
//! Tests batching, static ring buffer rollover, and recovery.
//! ============================================================================

use aeib_data_plane::wal::{GroupCommitWal, WalStatus};
use std::path::PathBuf;

fn create_temp_wal_path(test_name: &str) -> PathBuf {
    let mut path = std::env::temp_dir();
    let epoch_ns = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    path.push(format!("aeib_wal_{}_{}.log", test_name, epoch_ns));
    path
}

#[test]
fn test_wal_batch_group_commit_and_recovery() {
    let wal_path = create_temp_wal_path("batch_commit");
    let mut wal = GroupCommitWal::open(&wal_path, 16).expect("Failed to open WAL");

    assert_eq!(wal.unflushed_count(), 0);
    assert_eq!(wal.next_seq(), 1);

    // Append 5 pre-dispatch intents
    for i in 1..=5 {
        let op_id = format!("op-wal-batch-{}", i);
        let caid = [i as u8; 32];
        let seq = wal
            .append_intent(&op_id, &caid, WalStatus::LatchedPreDispatch, 1700000000000 + i)
            .expect("Append failed");
        assert_eq!(seq, i as u64);
    }

    assert_eq!(wal.unflushed_count(), 5);

    // Execute physical group-commit flush
    let metrics = wal.flush_group().expect("Flush failed");
    assert_eq!(metrics.flushed_slots, 5);
    assert_eq!(metrics.end_seq, 5);
    assert_eq!(wal.unflushed_count(), 0);

    // Verify recovery by reading all entries back
    let entries = wal.read_all_persisted_entries().expect("Read entries failed");
    assert_eq!(entries.len(), 5);

    for (idx, entry) in entries.iter().enumerate() {
        let expected_i = (idx + 1) as u64;
        assert_eq!(entry.seq, expected_i);
        assert_eq!(entry.operation_id, format!("op-wal-batch-{}", expected_i));
        assert_eq!(entry.action_caid, [expected_i as u8; 32]);
        assert_eq!(entry.status, WalStatus::LatchedPreDispatch);
        assert!(entry.committed);
    }

    // Clean up temporary file
    let _ = std::fs::remove_file(&wal_path);
}

#[test]
fn test_wal_ring_buffer_auto_flush_on_capacity() {
    let wal_path = create_temp_wal_path("auto_flush");
    // Ring capacity of 4 slots
    let mut wal = GroupCommitWal::open(&wal_path, 4).expect("Failed to open WAL");

    // Fill 4 slots
    for i in 1..=4 {
        wal.append_intent(
            &format!("op-fill-{}", i),
            &[i as u8; 32],
            WalStatus::LatchedPreDispatch,
            1700000000 + i,
        )
        .expect("Append failed");
    }
    assert_eq!(wal.unflushed_count(), 4);

    // Appending 5th slot must trigger auto-flush
    let seq5 = wal
        .append_intent(
            "op-fill-5",
            &[5u8; 32],
            WalStatus::EffectIndeterminate,
            1700000005,
        )
        .expect("Append 5th slot failed");
    assert_eq!(seq5, 5);
    assert_eq!(wal.unflushed_count(), 1);

    // Flush remaining
    wal.flush_group().expect("Final flush failed");
    assert_eq!(wal.unflushed_count(), 0);

    let entries = wal.read_all_persisted_entries().expect("Read entries failed");
    assert_eq!(entries.len(), 5);
    assert_eq!(entries[4].status, WalStatus::EffectIndeterminate);

    let _ = std::fs::remove_file(&wal_path);
}

#[tokio::test]
async fn test_direct_io_wal_lifecycle() {
    let wal_path = create_temp_wal_path("direct_io");
    let mut wal = aeib_data_plane::wal::DirectIoWal::open(&wal_path)
        .await
        .expect("Failed to open DirectIoWal");

    assert_eq!(wal.offset(), 0);

    // Prepare 4096-byte sector-aligned buffer
    let mut buffer = vec![0u8; 4096];
    let payload = b"DIRECT_IO_SECTOR_ALIGNED_FRAME_PAYLOAD";
    buffer[..payload.len()].copy_from_slice(payload);

    wal.append_aligned_frame(buffer)
        .await
        .expect("Failed to append aligned frame");

    assert_eq!(wal.offset(), 4096);

    // Verify written content on disk
    let file_bytes = std::fs::read(&wal_path).expect("Failed to read file");
    assert_eq!(file_bytes.len(), 4096);
    assert_eq!(&file_bytes[..payload.len()], payload);

    let _ = std::fs::remove_file(&wal_path);
}
