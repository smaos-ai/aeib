use chrono::Utc;
use uuid::Uuid;

use crate::models::{DeltaDetectionResult, DeltaEvent};

/// O(1) delta detection using SHA comparison
pub struct DeltaDetector;

impl DeltaDetector {
    /// Detect if repository has changed (O(1) operation)
    ///
    /// # Arguments
    /// * `repo_id` - Repository UUID
    /// * `prev_sha` - Previously cached SHA (or None if first check)
    /// * `current_sha` - Current HEAD SHA from git
    /// * `detection_latency_ms` - Time taken to fetch SHA
    ///
    /// # Returns
    /// DeltaDetectionResult with change status and timing
    pub fn detect(
        repo_id: Uuid,
        prev_sha: Option<String>,
        current_sha: String,
        detection_latency_ms: u32,
    ) -> DeltaDetectionResult {
        let changed = if let Some(ref prev) = prev_sha {
            prev != &current_sha
        } else {
            // First check always counts as change
            true
        };

        DeltaDetectionResult {
            repo_id,
            changed,
            prev_sha: prev_sha.unwrap_or_else(|| "initial".to_string()),
            new_sha: current_sha,
            detection_latency_ms,
        }
    }

    /// Create a delta event from detection result
    pub fn create_delta_event(
        detection: DeltaDetectionResult,
        commit_count: u32,
        files_changed: u32,
        bytes_added: u32,
        bytes_deleted: u32,
    ) -> DeltaEvent {
        DeltaEvent {
            id: Uuid::new_v4(),
            repo_id: detection.repo_id,
            prev_sha: detection.prev_sha,
            new_sha: detection.new_sha,
            timestamp: Utc::now(),
            commit_count,
            commit_log: vec![],
            files_changed,
            bytes_added,
            bytes_deleted,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_delta_detection_with_change() {
        let repo_id = Uuid::new_v4();
        let prev_sha = Some("abc123".to_string());
        let current_sha = "def456".to_string();

        let result = DeltaDetector::detect(repo_id, prev_sha, current_sha, 150);

        assert!(result.changed);
        assert_eq!(result.detection_latency_ms, 150);
    }

    #[test]
    fn test_delta_detection_no_change() {
        let repo_id = Uuid::new_v4();
        let sha = "abc123".to_string();

        let result = DeltaDetector::detect(repo_id, Some(sha.clone()), sha, 100);

        assert!(!result.changed);
    }

    #[test]
    fn test_delta_detection_first_check() {
        let repo_id = Uuid::new_v4();

        let result = DeltaDetector::detect(repo_id, None, "initial_sha".to_string(), 200);

        // First check should always be considered a change
        assert!(result.changed);
        assert_eq!(result.prev_sha, "initial");
    }

    #[test]
    fn test_create_delta_event() {
        let repo_id = Uuid::new_v4();
        let detection = DeltaDetectionResult {
            repo_id,
            changed: true,
            prev_sha: "prev".to_string(),
            new_sha: "new".to_string(),
            detection_latency_ms: 150,
        };

        let delta = DeltaDetector::create_delta_event(detection, 5, 10, 1024, 512);

        assert_eq!(delta.repo_id, repo_id);
        assert_eq!(delta.commit_count, 5);
        assert_eq!(delta.files_changed, 10);
        assert_eq!(delta.bytes_added, 1024);
        assert_eq!(delta.bytes_deleted, 512);
    }

    #[test]
    fn test_delta_detection_latency_tracking() {
        let repo_id = Uuid::new_v4();
        let latencies = vec![50, 100, 150, 200, 250];

        for latency in latencies {
            let result =
                DeltaDetector::detect(repo_id, Some("old".to_string()), "new".to_string(), latency);

            assert_eq!(result.detection_latency_ms, latency);
        }
    }

    #[test]
    fn test_delta_multiple_scenarios() {
        let test_cases = vec![
            (Some("a".to_string()), "b".to_string(), true),
            (Some("a".to_string()), "a".to_string(), false),
            (None, "a".to_string(), true),
            (Some("x".to_string()), "x".to_string(), false),
        ];

        for (prev, current, expected_change) in test_cases {
            let result = DeltaDetector::detect(Uuid::new_v4(), prev, current, 100);
            assert_eq!(result.changed, expected_change);
        }
    }
}
