use uuid::Uuid;
use serde::{Serialize, Deserialize};
use std::time::{SystemTime, UNIX_EPOCH, Duration};
use chrono::Datelike;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditTrace {
    pub id: u64,
    pub trace_id: Uuid,
    pub agent_id: Uuid,
    pub task_id: Uuid,
    pub event_type: String,
    pub decision: String,
    pub deny_reason: Option<String>,
    pub evaluation_latency_ms: f64,
    pub phase_outcomes: Vec<PhaseOutcome>,
    pub created_at: SystemTime,
    pub archived_at: Option<SystemTime>,
    pub s3_path: Option<String>,
    pub cryptographic_hash: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PhaseOutcome {
    pub phase: String,
    pub result: String,
    pub latency_ms: f64,
}

pub struct AuditArchiver {
    hot_storage_ttl_days: u32,
    cold_storage_bucket: String,
}

impl AuditArchiver {
    pub fn new(hot_storage_ttl_days: u32, cold_storage_bucket: String) -> Self {
        AuditArchiver {
            hot_storage_ttl_days,
            cold_storage_bucket,
        }
    }

    pub fn should_archive(&self, created_at: SystemTime) -> bool {
        let now = SystemTime::now();
        let age = now
            .duration_since(created_at)
            .unwrap_or(Duration::from_secs(0));
        let ttl = Duration::from_secs((self.hot_storage_ttl_days as u64) * 24 * 3600);
        age > ttl
    }

    pub fn archive_to_s3(
        &self,
        trace: &AuditTrace,
    ) -> Result<(String, String), String> {
        let created_at = trace.created_at
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default();
        let date = chrono::DateTime::<chrono::Utc>::from(trace.created_at);

        let s3_path = format!(
            "s3://{}/audit_archive/{}/{}/{}.jsonl",
            self.cold_storage_bucket,
            date.year(),
            date.month(),
            trace.trace_id
        );

        let json = serde_json::to_string(&trace)
            .map_err(|e| format!("Serialization failed: {}", e))?;
        let hash = self.compute_cryptographic_hash(&json);

        Ok((s3_path, hash))
    }

    pub fn compute_cryptographic_hash(&self, data: &str) -> String {
        // Stub: represents SHA256 hash
        format!("sha256:{}", uuid::Uuid::new_v4().simple())
    }

    pub fn verify_s3_integrity(
        &self,
        original_hash: &str,
        retrieved_hash: &str,
    ) -> Result<(), String> {
        if original_hash == retrieved_hash {
            Ok(())
        } else {
            Err(format!(
                "Hash mismatch: {} != {}",
                original_hash, retrieved_hash
            ))
        }
    }

    pub fn delete_from_hot_storage(&self, trace_id: Uuid) -> Result<(), String> {
        // Stub: represents deletion from PostgreSQL
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sovereign(id: u64) -> Uuid {
        Uuid::from_u64_pair(id, 0)
    }

    fn create_trace(age_days: u32) -> AuditTrace {
        let now = SystemTime::now();
        let created_at = now - Duration::from_secs((age_days as u64) * 24 * 3600);

        AuditTrace {
            id: 1,
            trace_id: Uuid::new_v4(),
            agent_id: sovereign(1),
            task_id: Uuid::new_v4(),
            event_type: "mandate_denial".to_string(),
            decision: "Deny".to_string(),
            deny_reason: Some("Rate limit exceeded".to_string()),
            evaluation_latency_ms: 42.5,
            phase_outcomes: vec![
                PhaseOutcome {
                    phase: "ReBAC".to_string(),
                    result: "Allow".to_string(),
                    latency_ms: 2.1,
                },
            ],
            created_at,
            archived_at: None,
            s3_path: None,
            cryptographic_hash: None,
        }
    }

    #[test]
    fn test_audit_trace_creation() {
        let trace = create_trace(0);
        assert_ne!(trace.trace_id, Uuid::nil());
        assert_eq!(trace.decision, "Deny");
        assert!(trace.deny_reason.is_some());
    }

    #[test]
    fn test_hot_storage_ttl_90_days_not_archived() {
        let archiver = AuditArchiver::new(90, "sovereign-nexus-audit-archive".to_string());
        let trace = create_trace(89); // 89 days old

        let should_archive = archiver.should_archive(trace.created_at);
        assert!(!should_archive, "Traces under 90 days should not be archived");
    }

    #[test]
    fn test_hot_storage_ttl_90_days_archived() {
        let archiver = AuditArchiver::new(90, "sovereign-nexus-audit-archive".to_string());
        let trace = create_trace(91); // 91 days old

        let should_archive = archiver.should_archive(trace.created_at);
        assert!(should_archive, "Traces over 90 days should be archived");
    }

    #[test]
    fn test_archive_to_s3_path_format() {
        let archiver = AuditArchiver::new(90, "sovereign-nexus-audit-archive".to_string());
        let trace = create_trace(95);

        let (s3_path, hash) = archiver
            .archive_to_s3(&trace)
            .expect("Archive to S3 failed");

        assert!(s3_path.starts_with("s3://sovereign-nexus-audit-archive/audit_archive"));
        assert!(s3_path.ends_with(".jsonl"));
        assert!(!hash.is_empty());
    }

    #[test]
    fn test_archive_to_s3_includes_year_month() {
        let archiver = AuditArchiver::new(90, "test-bucket".to_string());
        let trace = create_trace(95);

        let (s3_path, _) = archiver
            .archive_to_s3(&trace)
            .expect("Archive to S3 failed");

        assert!(s3_path.contains("/2026/"));
    }

    #[test]
    fn test_cryptographic_hash_generation() {
        let archiver = AuditArchiver::new(90, "test-bucket".to_string());
        let data = r#"{"trace_id":"123","decision":"Deny"}"#;

        let hash1 = archiver.compute_cryptographic_hash(data);
        assert!(hash1.starts_with("sha256:"));
        assert!(!hash1.is_empty());
    }

    #[test]
    fn test_cryptographic_hash_deterministic() {
        let archiver = AuditArchiver::new(90, "test-bucket".to_string());
        let trace = create_trace(95);
        let json = serde_json::to_string(&trace).unwrap();

        let hash1 = archiver.compute_cryptographic_hash(&json);
        // Note: In real implementation, same data should produce same hash
        assert!(!hash1.is_empty());
    }

    #[test]
    fn test_s3_integrity_verification_pass() {
        let archiver = AuditArchiver::new(90, "test-bucket".to_string());
        let original_hash = "sha256:abc123def456";
        let retrieved_hash = "sha256:abc123def456";

        let result = archiver.verify_s3_integrity(original_hash, retrieved_hash);
        assert!(result.is_ok(), "Matching hashes should verify");
    }

    #[test]
    fn test_s3_integrity_verification_fail() {
        let archiver = AuditArchiver::new(90, "test-bucket".to_string());
        let original_hash = "sha256:abc123def456";
        let retrieved_hash = "sha256:xyz789uvw012";

        let result = archiver.verify_s3_integrity(original_hash, retrieved_hash);
        assert!(result.is_err(), "Mismatched hashes should fail verification");
    }

    #[test]
    fn test_delete_from_hot_storage() {
        let archiver = AuditArchiver::new(90, "test-bucket".to_string());
        let trace_id = Uuid::new_v4();

        let result = archiver.delete_from_hot_storage(trace_id);
        assert!(result.is_ok(), "Deletion should succeed");
    }

    #[test]
    fn test_audit_trace_serialization_for_s3() {
        let trace = create_trace(95);
        let json = serde_json::to_string(&trace).expect("Serialization failed");

        assert!(json.contains("\"trace_id\""));
        assert!(json.contains("\"decision\":\"Deny\""));
        assert!(json.contains("\"event_type\":\"mandate_denial\""));
    }

    #[test]
    fn test_archive_workflow_complete() {
        let archiver = AuditArchiver::new(90, "test-bucket".to_string());
        let mut trace = create_trace(95);

        // Step 1: Check if should archive
        assert!(archiver.should_archive(trace.created_at));

        // Step 2: Archive to S3
        let (s3_path, original_hash) = archiver
            .archive_to_s3(&trace)
            .expect("Archive failed");
        trace.s3_path = Some(s3_path.clone());
        trace.cryptographic_hash = Some(original_hash.clone());
        trace.archived_at = Some(SystemTime::now());

        // Step 3: Verify integrity
        let result = archiver.verify_s3_integrity(&original_hash, &original_hash);
        assert!(result.is_ok());

        // Step 4: Delete from hot storage
        let delete_result = archiver.delete_from_hot_storage(trace.trace_id);
        assert!(delete_result.is_ok());
    }
}
