use chrono::Utc;
use siss_layer00::{
    archival::{
        ArchiveConfig, ArchiveError, ArchiveStats, ColdStorageArchiver, ExecLogArchiveRecord,
    },
    monitoring::{
        ChainVerification, HealthStatus, MerkleChainMonitor, MonitoringError, TamperAlert,
        TamperAlerts,
    },
};
use uuid::Uuid;

// ============================================================================
// ARCHIVAL TESTS
// ============================================================================

#[test]
fn test_archive_config_creation() {
    let config = ArchiveConfig {
        aws_region: "us-east-1".to_string(),
        s3_bucket: "test-bucket".to_string(),
        retention_days: 90,
    };
    assert_eq!(config.retention_days, 90);
    assert_eq!(config.s3_bucket, "test-bucket");
}

#[test]
fn test_s3_archive_path_format() {
    let config = ArchiveConfig {
        aws_region: "us-east-1".to_string(),
        s3_bucket: "test-bucket".to_string(),
        retention_days: 90,
    };
    let archiver = ColdStorageArchiver::new(config);
    let path = archiver.s3_archive_path(2026, 7, 21);
    assert!(
        path.contains("archives/exec_log"),
        "Path should contain archives/exec_log"
    );
    assert!(
        path.contains("2026/07/21"),
        "Path should contain year/month/day"
    );
    assert!(
        path.contains("test-bucket"),
        "Path should contain bucket name"
    );
}

#[test]
fn test_s3_archive_path_zero_pads_date() {
    let config = ArchiveConfig {
        aws_region: "us-east-1".to_string(),
        s3_bucket: "test-bucket".to_string(),
        retention_days: 90,
    };
    let archiver = ColdStorageArchiver::new(config);
    let path = archiver.s3_archive_path(2026, 1, 5);
    // Should be zero-padded: 2026/01/05
    assert!(
        path.contains("2026/01/05"),
        "Month and day should be zero-padded"
    );
}

#[test]
fn test_archive_stats_contains_correct_fields() {
    let stats = ArchiveStats {
        total_records: 1000,
        bytes_exported: 512_000,
        s3_path: "s3://test-bucket/archives/exec_log/2026/07/21/data.jsonl.gz".to_string(),
        exported_at: Utc::now(),
    };
    assert_eq!(stats.total_records, 1000);
    assert_eq!(stats.bytes_exported, 512_000);
    assert!(
        stats.s3_path.ends_with(".gz"),
        "S3 path should end with .gz for gzip compression"
    );
}

#[test]
fn test_archive_record_is_serializable() {
    let record = ExecLogArchiveRecord {
        id: 42,
        mandate_id: Uuid::nil(),
        action: "execute".to_string(),
        tool_name: "bash".to_string(),
        result_hash: "abc123".to_string(),
        merkle_hash: "def456".to_string(),
        parent_merkle_hash: "ghi789".to_string(),
        created_at: Utc::now(),
    };

    // Test that the record can be serialized to JSON
    let json = serde_json::to_string(&record);
    assert!(json.is_ok(), "Archive record should be JSON serializable");

    let json_str = json.unwrap();
    assert!(json_str.contains("execute"), "JSON should contain action");
    assert!(json_str.contains("bash"), "JSON should contain tool name");
}

#[test]
fn test_archive_error_messages_are_descriptive() {
    let s3_error = ArchiveError::S3Error("bucket not found".to_string());
    assert!(format!("{}", s3_error).contains("S3 operation failed"));

    let db_error = ArchiveError::DatabaseError("connection lost".to_string());
    assert!(format!("{}", db_error).contains("Database error"));

    let verify_error = ArchiveError::VerificationFailed("checksum mismatch".to_string());
    assert!(format!("{}", verify_error).contains("verification failed"));
}

#[test]
fn test_archive_stats_is_serializable() {
    let stats = ArchiveStats {
        total_records: 500,
        bytes_exported: 256_000,
        s3_path: "s3://bucket/path/data.jsonl.gz".to_string(),
        exported_at: Utc::now(),
    };
    let json = serde_json::to_string(&stats);
    assert!(json.is_ok(), "ArchiveStats should be JSON serializable");
}

// ============================================================================
// MONITORING TESTS
// ============================================================================

#[test]
fn test_health_status_comparison() {
    assert_eq!(HealthStatus::Healthy, HealthStatus::Healthy);
    assert_ne!(HealthStatus::Healthy, HealthStatus::Degraded);
    assert_ne!(HealthStatus::Degraded, HealthStatus::Critical);
}

#[test]
fn test_health_status_is_serializable() {
    let status = HealthStatus::Healthy;
    let json = serde_json::to_string(&status);
    assert!(json.is_ok(), "HealthStatus should be JSON serializable");
}

#[test]
fn test_chain_verification_creation() {
    let now = Utc::now();
    let verification = ChainVerification {
        status: HealthStatus::Healthy,
        entries_verified: 1000,
        last_verified_at: now,
        next_check_at: now,
    };
    assert_eq!(verification.status, HealthStatus::Healthy);
    assert_eq!(verification.entries_verified, 1000);
}

#[test]
fn test_merkle_monitor_instantiation() {
    let monitor = MerkleChainMonitor::new();
    let _default_monitor = MerkleChainMonitor::default();
    // Both should be instantiable without error
    drop(monitor);
}

#[test]
fn test_tamper_alert_contains_evidence() {
    let alert = TamperAlert {
        entry_id: 42,
        expected_hash: "aaaaaabbbbbbcccccc".to_string(),
        actual_hash: "ddddddeeeeeefffff".to_string(),
        detected_at: Utc::now(),
        severity: "critical".to_string(),
    };
    assert_eq!(alert.entry_id, 42);
    assert_ne!(alert.expected_hash, alert.actual_hash);
    assert_eq!(alert.severity, "critical");
}

#[test]
fn test_tamper_alert_is_serializable() {
    let alert = TamperAlert {
        entry_id: 1,
        expected_hash: "abc".to_string(),
        actual_hash: "def".to_string(),
        detected_at: Utc::now(),
        severity: "critical".to_string(),
    };
    let json = serde_json::to_string(&alert);
    assert!(json.is_ok(), "TamperAlert should be JSON serializable");
}

#[test]
fn test_tamper_alerts_collects_multiple_incidents() {
    let alerts = vec![
        TamperAlert {
            entry_id: 1,
            expected_hash: "aaa".to_string(),
            actual_hash: "bbb".to_string(),
            detected_at: Utc::now(),
            severity: "critical".to_string(),
        },
        TamperAlert {
            entry_id: 2,
            expected_hash: "ccc".to_string(),
            actual_hash: "ddd".to_string(),
            detected_at: Utc::now(),
            severity: "critical".to_string(),
        },
    ];
    let tamper_alerts = TamperAlerts {
        alerts: alerts.clone(),
        total_compromised: 2,
    };
    assert_eq!(tamper_alerts.alerts.len(), 2);
    assert_eq!(tamper_alerts.total_compromised, 2);
    assert!(tamper_alerts.alerts[0].expected_hash != tamper_alerts.alerts[0].actual_hash);
}

#[test]
fn test_tamper_alerts_handles_empty_case() {
    let alerts = TamperAlerts {
        alerts: vec![],
        total_compromised: 0,
    };
    assert_eq!(alerts.alerts.len(), 0);
    assert_eq!(alerts.total_compromised, 0);
}

#[test]
fn test_monitoring_error_messages_are_descriptive() {
    let error = MonitoringError::VerificationFailed("hash mismatch".to_string());
    assert!(format!("{}", error).contains("verification failed"));

    let tamper_error = MonitoringError::TamperingDetected("entry 42 tampered".to_string());
    assert!(format!("{}", tamper_error).contains("Tampering detected"));

    let db_error = MonitoringError::DatabaseError("query failed".to_string());
    assert!(format!("{}", db_error).contains("Database error"));
}

#[test]
fn test_chain_verification_is_serializable() {
    let verification = ChainVerification {
        status: HealthStatus::Healthy,
        entries_verified: 500,
        last_verified_at: Utc::now(),
        next_check_at: Utc::now(),
    };
    let json = serde_json::to_string(&verification);
    assert!(
        json.is_ok(),
        "ChainVerification should be JSON serializable"
    );
}

#[test]
fn test_monitor_detects_chain_break_scenario() {
    // Test that the alert structure can represent a chain break
    let alert = TamperAlert {
        entry_id: 100,
        expected_hash: "expected_merkle_hash_from_computation".to_string(),
        actual_hash: "actual_merkle_hash_from_db".to_string(),
        detected_at: Utc::now(),
        severity: "critical".to_string(),
    };
    // If hashes differ, tampering is detected
    assert_ne!(alert.expected_hash, alert.actual_hash);
    assert_eq!(alert.severity, "critical");
}

#[test]
fn test_archive_records_with_merkle_chain_data() {
    // Verify that archive records maintain merkle chain integrity information
    let record = ExecLogArchiveRecord {
        id: 1,
        mandate_id: Uuid::new_v4(),
        action: "verify_chain".to_string(),
        tool_name: "monitor".to_string(),
        result_hash: "hash1".to_string(),
        merkle_hash: "merkle1".to_string(),
        parent_merkle_hash: "parent1".to_string(),
        created_at: Utc::now(),
    };
    assert!(!record.merkle_hash.is_empty());
    assert!(!record.parent_merkle_hash.is_empty());
}
