use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Current snapshot of a creator's repository
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RepoSnapshot {
    pub id: Uuid,
    pub creator_id: Uuid,
    pub repo_url: String,
    pub repo_host: RepoHost,

    // Git state
    pub latest_sha: String,
    pub previous_sha: Option<String>,
    pub last_checked: DateTime<Utc>,
    pub fetch_latency_ms: u32,

    // Governance
    pub governance_status: GovernanceStatus,
    pub policy_violations: Vec<PolicyViolation>,
    pub creator_flagged: bool,

    // Metadata
    pub default_branch: String,
    pub is_private: bool,
    pub last_commit_message: Option<String>,
    pub last_commit_author: Option<String>,
    pub commit_count_since_last_check: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum RepoHost {
    GitHub,
    GitLab,
    Gitea,
    Gitpod,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum GovernanceStatus {
    Compliant,
    Flagged,
    Violation,
    UnderReview,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolicyViolation {
    pub policy_id: Uuid,
    pub rule_name: String,
    pub violation_type: String,
    pub severity: ViolationSeverity,
    pub detected_at: DateTime<Utc>,
    pub resolved_at: Option<DateTime<Utc>>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
pub enum ViolationSeverity {
    Low,
    Medium,
    High,
    Critical,
}

/// Atomic change record for a repository
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeltaEvent {
    pub id: Uuid,
    pub repo_id: Uuid,
    pub prev_sha: String,
    pub new_sha: String,
    pub timestamp: DateTime<Utc>,
    pub commit_count: u32,
    pub commit_log: Vec<CommitInfo>,
    pub files_changed: u32,
    pub bytes_added: u32,
    pub bytes_deleted: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CommitInfo {
    pub sha: String,
    pub message: String,
    pub author: String,
    pub timestamp: DateTime<Utc>,
}

/// Result of delta detection
#[derive(Debug)]
pub struct DeltaDetectionResult {
    pub repo_id: Uuid,
    pub changed: bool,
    pub prev_sha: String,
    pub new_sha: String,
    pub detection_latency_ms: u32,
}

// Cache key patterns
pub const CACHE_KEY_SHA: &str = "radar:repo:{repo_id}:sha";
pub const CACHE_KEY_CHECKED: &str = "radar:repo:{repo_id}:last_checked";
pub const CACHE_KEY_STATUS: &str = "radar:repo:{repo_id}:gov_status";

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_repo_snapshot_creation() {
        let snapshot = RepoSnapshot {
            id: Uuid::new_v4(),
            creator_id: Uuid::new_v4(),
            repo_url: "https://github.com/test/repo".to_string(),
            repo_host: RepoHost::GitHub,
            latest_sha: "abc123def456".to_string(),
            previous_sha: Some("xyz789abc123".to_string()),
            last_checked: Utc::now(),
            fetch_latency_ms: 150,
            governance_status: GovernanceStatus::Compliant,
            policy_violations: vec![],
            creator_flagged: false,
            default_branch: "main".to_string(),
            is_private: false,
            last_commit_message: Some("Fix: update readme".to_string()),
            last_commit_author: Some("dev@example.com".to_string()),
            commit_count_since_last_check: 3,
        };

        assert_eq!(snapshot.repo_host, RepoHost::GitHub);
        assert_eq!(snapshot.governance_status, GovernanceStatus::Compliant);
        assert!(!snapshot.creator_flagged);
    }

    #[test]
    fn test_violation_severity_ordering() {
        assert!(ViolationSeverity::Low < ViolationSeverity::Medium);
        assert!(ViolationSeverity::Medium < ViolationSeverity::High);
        assert!(ViolationSeverity::High < ViolationSeverity::Critical);
    }

    #[test]
    fn test_delta_event_creation() {
        let delta = DeltaEvent {
            id: Uuid::new_v4(),
            repo_id: Uuid::new_v4(),
            prev_sha: "prev_sha".to_string(),
            new_sha: "new_sha".to_string(),
            timestamp: Utc::now(),
            commit_count: 5,
            commit_log: vec![],
            files_changed: 10,
            bytes_added: 1024,
            bytes_deleted: 512,
        };

        assert_eq!(delta.commit_count, 5);
        assert_eq!(delta.files_changed, 10);
    }
}
