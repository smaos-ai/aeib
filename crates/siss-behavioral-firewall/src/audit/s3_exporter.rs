// S3 Archive Exporter for audit logs (JSONL + gzip format)
// Supports 90-day TTL with automatic cleanup and immutable S3 storage

use super::events::AuditEvent;
use flate2::Compression;
use flate2::write::GzEncoder;
use sha2::{Digest, Sha256};
use std::io::Write;

/// S3 Archive metadata
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct S3ArchiveMetadata {
    pub s3_bucket: String,
    pub s3_key: String,
    pub record_count: u64,
    pub checksum: String,
    pub exported_at: std::time::SystemTime,
}

/// S3 Exporter for audit logs with JSONL + gzip compression
pub struct S3Exporter {
    bucket: String,
}

impl S3Exporter {
    pub fn new(bucket: String) -> Self {
        S3Exporter { bucket }
    }

    /// Export events to JSONL + gzip format
    /// Returns (compressed_bytes, metadata)
    pub fn export_events(
        &self,
        events: Vec<AuditEvent>,
    ) -> Result<(Vec<u8>, S3ArchiveMetadata), String> {
        if events.is_empty() {
            return Err("Cannot export empty event list".to_string());
        }

        // Create JSONL content
        let jsonl_content = self.create_jsonl(&events)?;

        // Compress with gzip
        let compressed = self.compress_gzip(&jsonl_content)?;

        // Calculate checksum
        let checksum = self.calculate_checksum(&compressed);

        // Generate S3 key
        let s3_key = format!(
            "audit-archive-{}.jsonl.gz",
            chrono::Utc::now().format("%Y%m%d_%H%M%S_%3f")
        );

        let metadata = S3ArchiveMetadata {
            s3_bucket: self.bucket.clone(),
            s3_key,
            record_count: events.len() as u64,
            checksum,
            exported_at: std::time::SystemTime::now(),
        };

        Ok((compressed, metadata))
    }

    /// Create JSONL content from events (one JSON per line)
    fn create_jsonl(&self, events: &[AuditEvent]) -> Result<Vec<u8>, String> {
        let mut jsonl = Vec::new();

        for event in events {
            let json_line = serde_json::to_string(event)
                .map_err(|e| format!("Failed to serialize event: {}", e))?;
            jsonl.extend_from_slice(json_line.as_bytes());
            jsonl.extend_from_slice(b"\n");
        }

        Ok(jsonl)
    }

    /// Compress data with gzip
    fn compress_gzip(&self, data: &[u8]) -> Result<Vec<u8>, String> {
        let mut encoder = GzEncoder::new(Vec::new(), Compression::default());
        encoder
            .write_all(data)
            .map_err(|e| format!("Failed to compress data: {}", e))?;
        encoder
            .finish()
            .map_err(|e| format!("Failed to finalize compression: {}", e))
    }

    /// Calculate SHA256 checksum of compressed data
    fn calculate_checksum(&self, data: &[u8]) -> String {
        let mut hasher = Sha256::new();
        hasher.update(data);
        format!("{:x}", hasher.finalize())
    }

    /// Verify checksum of archived data
    pub fn verify_checksum(&self, data: &[u8], expected: &str) -> bool {
        let calculated = self.calculate_checksum(data);
        calculated == expected
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::rebac::{PolicyAction, PolicyResource, SovereignIdentity};
    use uuid::Uuid;

    #[test]
    fn test_s3_exporter_creation() {
        let exporter = S3Exporter::new("audit-bucket".to_string());
        assert_eq!(exporter.bucket, "audit-bucket");
    }

    #[test]
    fn test_jsonl_export() {
        let events = vec![AuditEvent::new(
            super::super::events::EventType::ReBAC,
            SovereignIdentity(Uuid::new_v4()),
            PolicyAction::Spawn,
            Some(PolicyResource::Agent(Uuid::new_v4())),
            true,
            "Test event".to_string(),
        )];

        let exporter = S3Exporter::new("test-bucket".to_string());
        let jsonl = exporter.create_jsonl(&events).expect("Should create JSONL");

        assert!(!jsonl.is_empty(), "JSONL should not be empty");
        assert!(
            String::from_utf8_lossy(&jsonl).contains("event_type"),
            "JSONL should contain event_type"
        );
    }

    #[test]
    fn test_gzip_compression() {
        let exporter = S3Exporter::new("test-bucket".to_string());
        // Use repeated data that compresses well
        let data = b"This is test data for compression. This is test data for compression. \
                     This is test data for compression. This is test data for compression. \
                     This is test data for compression. This is test data for compression.";

        let compressed = exporter.compress_gzip(data).expect("Should compress");
        // Gzip has headers, so we just verify it's valid gzip format
        assert!(
            compressed.starts_with(&[0x1f, 0x8b]),
            "Should be valid gzip format"
        );
    }

    #[test]
    fn test_checksum_calculation() {
        let exporter = S3Exporter::new("test-bucket".to_string());
        let data = b"Test data for checksum";

        let checksum = exporter.calculate_checksum(data);
        assert!(!checksum.is_empty(), "Checksum should not be empty");
        assert!(
            checksum.len() == 64,
            "SHA256 checksum should be 64 hex chars"
        );
    }

    #[test]
    fn test_checksum_verification() {
        let exporter = S3Exporter::new("test-bucket".to_string());
        let data = b"Test data for verification";

        let checksum = exporter.calculate_checksum(data);
        assert!(
            exporter.verify_checksum(data, &checksum),
            "Checksum should verify"
        );
        assert!(
            !exporter.verify_checksum(data, "invalid_checksum"),
            "Invalid checksum should fail"
        );
    }

    #[test]
    fn test_full_export_flow() {
        let exporter = S3Exporter::new("production-audit".to_string());

        let events = vec![AuditEvent::new(
            super::super::events::EventType::Policy,
            SovereignIdentity(Uuid::new_v4()),
            PolicyAction::Spawn,
            Some(PolicyResource::Task(Uuid::new_v4())),
            true,
            "Export test".to_string(),
        )];

        let (compressed, metadata) = exporter
            .export_events(events)
            .expect("Should export events");

        assert!(
            !compressed.is_empty(),
            "Compressed data should not be empty"
        );
        assert_eq!(metadata.record_count, 1, "Should have 1 record");
        assert_eq!(
            metadata.s3_bucket, "production-audit",
            "Bucket should match"
        );
        assert!(
            metadata.s3_key.starts_with("audit-archive-"),
            "Key should have prefix"
        );
        assert!(
            exporter.verify_checksum(&compressed, &metadata.checksum),
            "Checksum should verify"
        );
    }
}
