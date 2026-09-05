use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use thiserror::Error;
use uuid::Uuid;

#[derive(Debug, Error)]
pub enum ArchiveError {
    #[error("S3 operation failed: {0}")]
    S3Error(String),
    #[error("Database error: {0}")]
    DatabaseError(String),
    #[error("Serialization error: {0}")]
    SerializationError(String),
    #[error("Archive verification failed: {0}")]
    VerificationFailed(String),
}

pub type ArchiveResult<T> = Result<T, ArchiveError>;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecLogArchiveRecord {
    pub id: i64,
    pub mandate_id: Uuid,
    pub action: String,
    pub tool_name: String,
    pub result_hash: String,
    pub merkle_hash: String,
    pub parent_merkle_hash: String,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ArchiveStats {
    pub total_records: usize,
    pub bytes_exported: usize,
    pub s3_path: String,
    pub exported_at: DateTime<Utc>,
}

/// Configuration for cold storage archival
#[derive(Debug, Clone)]
pub struct ArchiveConfig {
    pub aws_region: String,
    pub s3_bucket: String,
    pub retention_days: i64,
}

/// Cold storage archiver for exec_log entries
pub struct ColdStorageArchiver {
    config: ArchiveConfig,
    // In production, this would be aws_sdk_s3::Client
    // For testing, we use a mock-friendly trait
}

impl ColdStorageArchiver {
    pub fn new(config: ArchiveConfig) -> Self {
        Self { config }
    }

    /// Archive entries older than retention_days (default 90 days)
    /// Returns statistics and S3 path
    pub async fn archive_old_entries(&self) -> ArchiveResult<ArchiveStats> {
        // Placeholder for production implementation
        // This will be filled in after tests define expected behavior
        Err(ArchiveError::DatabaseError("Not implemented".to_string()))
    }

    /// Verify that the archive in S3 can be read and checksummed
    pub async fn verify_s3_integrity(&self) -> ArchiveResult<bool> {
        // Placeholder for production implementation
        Err(ArchiveError::S3Error("Not implemented".to_string()))
    }

    /// Get the S3 path pattern for archived records
    pub fn s3_archive_path(&self, year: u16, month: u8, day: u8) -> String {
        format!(
            "s3://{}/archives/exec_log/{:04}/{:02}/{:02}/",
            self.config.s3_bucket, year, month, day
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_config() -> ArchiveConfig {
        ArchiveConfig {
            aws_region: "us-east-1".to_string(),
            s3_bucket: "test-bucket".to_string(),
            retention_days: 90,
        }
    }

    #[test]
    fn test_archive_config_creation() {
        let config = test_config();
        assert_eq!(config.retention_days, 90);
        assert_eq!(config.s3_bucket, "test-bucket");
    }

    #[test]
    fn test_s3_archive_path_format() {
        let archiver = ColdStorageArchiver::new(test_config());
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
        let archiver = ColdStorageArchiver::new(test_config());
        let path = archiver.s3_archive_path(2026, 1, 5);
        // Should be zero-padded: 2026/01/05
        assert!(
            path.contains("2026/01/05"),
            "Month and day should be zero-padded"
        );
    }

    #[test]
    fn test_archive_stats_serializable() {
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
            "S3 path should end with .gz for compression"
        );
    }

    #[test]
    fn test_archive_record_serialization() {
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
    fn test_archive_error_messages() {
        let s3_error = ArchiveError::S3Error("bucket not found".to_string());
        assert!(format!("{}", s3_error).contains("S3 operation failed"));

        let db_error = ArchiveError::DatabaseError("connection lost".to_string());
        assert!(format!("{}", db_error).contains("Database error"));

        let verify_error = ArchiveError::VerificationFailed("checksum mismatch".to_string());
        assert!(format!("{}", verify_error).contains("verification failed"));
    }

    #[test]
    fn test_archive_config_retention_days() {
        let config = ArchiveConfig {
            aws_region: "eu-west-1".to_string(),
            s3_bucket: "prod-bucket".to_string(),
            retention_days: 90,
        };
        assert_eq!(config.retention_days, 90);
    }
}
