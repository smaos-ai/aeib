use crate::models::{DeltaEvent, RepoSnapshot};
use anyhow::Result;
use chrono::{DateTime, Duration, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Daily brief for a creator, in JSON-LD format
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserBrief {
    #[serde(rename = "@context")]
    pub context: String,
    #[serde(rename = "@type")]
    pub brief_type: String,
    pub id: String,
    pub creator_id: String,
    pub date: DateTime<Utc>,
    pub repos_monitored: u32,
    pub deltas_detected: u32,
    pub violations_detected: u32,
    pub compliance_score: f64,
    pub summary: String,
    pub key_events: Vec<BriefEvent>,
    pub next_delivery: DateTime<Utc>,
}

/// Individual event in a brief
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BriefEvent {
    pub id: String,
    pub repo_url: String,
    pub event_type: String,
    pub description: String,
    pub severity: String,
    pub timestamp: DateTime<Utc>,
}

/// Generator for daily user briefs
pub struct BriefGenerator {
    #[allow(dead_code)]
    batch_size: usize,
}

/// Scheduling info for brief delivery
#[derive(Debug, Clone)]
pub struct DeliverySchedule {
    pub user_id: Uuid,
    pub last_delivery: Option<DateTime<Utc>>,
    pub next_delivery: DateTime<Utc>,
    pub timezone: String,
    pub preferred_time: String, // HH:MM format
}

impl BriefGenerator {
    pub fn new() -> Self {
        Self { batch_size: 1000 }
    }

    pub fn with_batch_size(batch_size: usize) -> Self {
        Self { batch_size }
    }

    /// Generate a brief for a creator from snapshots and deltas
    pub fn generate_brief(
        creator_id: Uuid,
        snapshots: &[RepoSnapshot],
        deltas: &[DeltaEvent],
    ) -> Result<UserBrief> {
        let now = Utc::now();

        // Calculate metrics
        let repos_monitored = snapshots.len() as u32;
        let deltas_detected = deltas.len() as u32;
        let violations_detected =
            snapshots.iter().flat_map(|s| &s.policy_violations).count() as u32;

        // Calculate compliance score (0-100)
        let compliant_repos = snapshots
            .iter()
            .filter(|s| s.policy_violations.is_empty())
            .count();
        let compliance_score = if repos_monitored > 0 {
            (compliant_repos as f64 / f64::from(repos_monitored)) * 100.0
        } else {
            100.0
        };

        // Generate summary
        let summary = format!(
            "Daily briefing for {} repository(s): {} change(s) detected, {} violation(s) identified, {:.1}% compliant",
            repos_monitored, deltas_detected, violations_detected, compliance_score
        );

        // Extract key events
        let key_events = Self::extract_key_events(snapshots, deltas);

        // Schedule next delivery (24 hours from now)
        let next_delivery = now + Duration::hours(24);

        Ok(UserBrief {
            context: "https://schema.org".to_string(),
            brief_type: "DailyBrief".to_string(),
            id: Uuid::new_v4().to_string(),
            creator_id: creator_id.to_string(),
            date: now,
            repos_monitored,
            deltas_detected,
            violations_detected,
            compliance_score,
            summary,
            key_events,
            next_delivery,
        })
    }

    /// Extract high-priority events from snapshots and deltas
    fn extract_key_events(snapshots: &[RepoSnapshot], deltas: &[DeltaEvent]) -> Vec<BriefEvent> {
        let mut events = vec![];

        // Add violation events from snapshots
        for snapshot in snapshots {
            for violation in &snapshot.policy_violations {
                events.push(BriefEvent {
                    id: Uuid::new_v4().to_string(),
                    repo_url: snapshot.repo_url.clone(),
                    event_type: "violation_detected".to_string(),
                    description: format!("{}: {}", violation.rule_name, violation.violation_type),
                    severity: format!("{:?}", violation.severity),
                    timestamp: violation.detected_at,
                });
            }
        }

        // Add high-activity delta events (commits > 5)
        for delta in deltas {
            if delta.commit_count > 5 {
                events.push(BriefEvent {
                    id: Uuid::new_v4().to_string(),
                    repo_url: format!("repo:{}", delta.repo_id),
                    event_type: "high_activity".to_string(),
                    description: format!("{} commits detected", delta.commit_count),
                    severity: "info".to_string(),
                    timestamp: delta.timestamp,
                });
            }
        }

        // Sort by timestamp descending (newest first)
        events.sort_by_key(|e| std::cmp::Reverse(e.timestamp));
        events.truncate(10); // Keep top 10 events

        events
    }

    /// Generate briefs for batch of creators
    #[allow(dead_code)]
    pub fn generate_batch(
        &self,
        creator_snapshots: &[(Uuid, Vec<RepoSnapshot>, Vec<DeltaEvent>)],
    ) -> Result<Vec<UserBrief>> {
        let briefs = creator_snapshots
            .iter()
            .map(|(creator_id, snapshots, deltas)| {
                Self::generate_brief(*creator_id, snapshots, deltas)
            })
            .collect::<Result<Vec<_>, _>>()?;

        Ok(briefs)
    }

    /// Schedule brief delivery for a user
    pub fn schedule_delivery(
        user_id: Uuid,
        last_delivery: Option<DateTime<Utc>>,
        timezone: &str,
        preferred_time: &str,
    ) -> DeliverySchedule {
        let now = Utc::now();

        // Calculate next delivery (24 hours from last, or now if no prior delivery)
        let next_delivery = if let Some(last) = last_delivery {
            let next = last + Duration::hours(24);
            if next <= now { now } else { next }
        } else {
            now
        };

        DeliverySchedule {
            user_id,
            last_delivery,
            next_delivery,
            timezone: timezone.to_string(),
            preferred_time: preferred_time.to_string(),
        }
    }

    /// Check if a brief is due for delivery
    pub fn is_delivery_due(schedule: &DeliverySchedule) -> bool {
        Utc::now() >= schedule.next_delivery
    }

    /// Format brief as JSON-LD string
    pub fn to_json_ld(&self, brief: &UserBrief) -> Result<String> {
        Ok(serde_json::to_string_pretty(brief)?)
    }
}

impl Default for BriefGenerator {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::{GovernanceStatus, PolicyViolation, RepoHost, ViolationSeverity};

    fn create_test_snapshot(creator_id: Uuid, violations: bool) -> RepoSnapshot {
        RepoSnapshot {
            id: Uuid::new_v4(),
            creator_id,
            repo_url: "https://github.com/test/repo".to_string(),
            repo_host: RepoHost::GitHub,
            latest_sha: "abc123".to_string(),
            previous_sha: Some("xyz789".to_string()),
            last_checked: Utc::now(),
            fetch_latency_ms: 100,
            governance_status: if violations {
                GovernanceStatus::Violation
            } else {
                GovernanceStatus::Compliant
            },
            policy_violations: if violations {
                vec![PolicyViolation {
                    policy_id: Uuid::new_v4(),
                    rule_name: "test_rule".to_string(),
                    violation_type: "test_violation".to_string(),
                    severity: ViolationSeverity::Medium,
                    detected_at: Utc::now(),
                    resolved_at: None,
                }]
            } else {
                vec![]
            },
            creator_flagged: violations,
            default_branch: "main".to_string(),
            is_private: false,
            last_commit_message: Some("Update".to_string()),
            last_commit_author: Some("dev@test.com".to_string()),
            commit_count_since_last_check: 1,
        }
    }

    fn create_test_delta(repo_id: Uuid, commits: u32) -> DeltaEvent {
        DeltaEvent {
            id: Uuid::new_v4(),
            repo_id,
            prev_sha: "prev".to_string(),
            new_sha: "new".to_string(),
            timestamp: Utc::now(),
            commit_count: commits,
            commit_log: vec![],
            files_changed: 5,
            bytes_added: 1000,
            bytes_deleted: 500,
        }
    }

    #[test]
    fn test_generate_brief_basic() {
        let creator_id = Uuid::new_v4();
        let snapshots = vec![create_test_snapshot(creator_id, false)];
        let deltas = vec![];

        let brief = BriefGenerator::generate_brief(creator_id, &snapshots, &deltas).unwrap();

        assert_eq!(brief.creator_id, creator_id.to_string());
        assert_eq!(brief.repos_monitored, 1);
        assert_eq!(brief.compliance_score, 100.0);
    }

    #[test]
    fn test_generate_brief_with_violations() {
        let creator_id = Uuid::new_v4();
        let snapshots = vec![
            create_test_snapshot(creator_id, false),
            create_test_snapshot(creator_id, true),
        ];
        let deltas = vec![];

        let brief = BriefGenerator::generate_brief(creator_id, &snapshots, &deltas).unwrap();

        assert_eq!(brief.repos_monitored, 2);
        assert_eq!(brief.violations_detected, 1);
        assert_eq!(brief.compliance_score, 50.0);
    }

    #[test]
    fn test_extract_key_events() {
        let creator_id = Uuid::new_v4();
        let repo_id = Uuid::new_v4();
        let snapshots = vec![create_test_snapshot(creator_id, true)];
        let deltas = vec![create_test_delta(repo_id, 10)];

        let events = BriefGenerator::extract_key_events(&snapshots, &deltas);

        assert!(!events.is_empty());
    }

    #[test]
    fn test_schedule_delivery_first_time() {
        let user_id = Uuid::new_v4();
        let schedule = BriefGenerator::schedule_delivery(user_id, None, "UTC", "08:00");

        assert!(BriefGenerator::is_delivery_due(&schedule));
    }

    #[test]
    fn test_schedule_delivery_future() {
        let user_id = Uuid::new_v4();
        let last_delivery = Utc::now();
        let schedule =
            BriefGenerator::schedule_delivery(user_id, Some(last_delivery), "UTC", "08:00");

        // Next delivery is in 24 hours, so not due yet
        assert!(!BriefGenerator::is_delivery_due(&schedule));
    }

    #[test]
    fn test_json_ld_serialization() {
        let creator_id = Uuid::new_v4();
        let snapshots = vec![create_test_snapshot(creator_id, false)];
        let deltas = vec![];

        let brief = BriefGenerator::generate_brief(creator_id, &snapshots, &deltas).unwrap();
        let generator = BriefGenerator::new();
        let json = generator.to_json_ld(&brief).unwrap();

        assert!(json.contains("@context"));
        assert!(json.contains("@type"));
        assert!(json.contains("DailyBrief"));
    }

    #[test]
    fn test_compliance_score_calculation() {
        let creator_id = Uuid::new_v4();
        let snapshots = vec![
            create_test_snapshot(creator_id, false),
            create_test_snapshot(creator_id, false),
            create_test_snapshot(creator_id, true),
        ];
        let deltas = vec![];

        let brief = BriefGenerator::generate_brief(creator_id, &snapshots, &deltas).unwrap();

        // 2 compliant out of 3 = 66.666...%
        assert!((brief.compliance_score - 66.666).abs() < 0.1);
    }
}
