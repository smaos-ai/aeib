use crate::models::{
    DeltaEvent, GovernanceStatus, PolicyViolation, RepoSnapshot, ViolationSeverity,
};
use anyhow::Result;
use chrono::Utc;
use uuid::Uuid;

/// Governance engine for enforcement of repository policies
pub struct GovernanceEngine {
    policies: Vec<Policy>,
}

/// A governance policy rule
#[derive(Debug, Clone)]
pub struct Policy {
    pub id: Uuid,
    pub name: String,
    pub rule_type: RuleType,
    pub severity: ViolationSeverity,
    pub enabled: bool,
}

/// Types of governance rules
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RuleType {
    RequireSignedCommits,
    NoUnencryptedSecrets,
    NoLargeFiles,
    RestrictBranch,
    RequireApprovals,
}

/// Audit integration for governance rule enforcement
pub struct AuditIntegration {
    engine: GovernanceEngine,
    logs: Vec<AuditLog>,
}

/// Immutable audit log entry
#[derive(Debug, Clone)]
pub struct AuditLog {
    pub id: Uuid,
    pub repo_id: Uuid,
    pub event_type: AuditEventType,
    pub violation: Option<PolicyViolation>,
    pub timestamp: chrono::DateTime<chrono::Utc>,
}

/// Types of audit events
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum AuditEventType {
    ViolationDetected,
    ViolationResolved,
    RuleMatched,
    AlertGenerated,
    ComplianceAchieved,
}

impl GovernanceEngine {
    pub fn new() -> Self {
        Self {
            policies: vec![
                Policy {
                    id: Uuid::new_v4(),
                    name: "require_signed_commits".to_string(),
                    rule_type: RuleType::RequireSignedCommits,
                    severity: ViolationSeverity::High,
                    enabled: true,
                },
                Policy {
                    id: Uuid::new_v4(),
                    name: "no_unencrypted_secrets".to_string(),
                    rule_type: RuleType::NoUnencryptedSecrets,
                    severity: ViolationSeverity::Critical,
                    enabled: true,
                },
                Policy {
                    id: Uuid::new_v4(),
                    name: "no_large_files".to_string(),
                    rule_type: RuleType::NoLargeFiles,
                    severity: ViolationSeverity::Medium,
                    enabled: true,
                },
            ],
        }
    }

    /// Match delta against governance rules
    pub fn evaluate_delta(&self, delta: &DeltaEvent) -> Vec<PolicyViolation> {
        let mut violations = vec![];

        for policy in &self.policies {
            if !policy.enabled {
                continue;
            }

            // Simulate rule matching (simplified for demo)
            if policy.rule_type == RuleType::NoLargeFiles && delta.bytes_added > 5_000_000 {
                violations.push(PolicyViolation {
                    policy_id: policy.id,
                    rule_name: policy.name.clone(),
                    violation_type: "large_file_detected".to_string(),
                    severity: policy.severity.clone(),
                    detected_at: Utc::now(),
                    resolved_at: None,
                });
            }
        }

        violations
    }

    /// Get all enabled policies
    pub fn list_policies(&self) -> &[Policy] {
        &self.policies
    }

    /// Enable a policy by name
    pub fn enable_policy(&mut self, name: &str) {
        if let Some(policy) = self.policies.iter_mut().find(|p| p.name == name) {
            policy.enabled = true;
        }
    }

    /// Disable a policy by name
    pub fn disable_policy(&mut self, name: &str) {
        if let Some(policy) = self.policies.iter_mut().find(|p| p.name == name) {
            policy.enabled = false;
        }
    }

    /// Update policy enabled status
    pub fn set_policy_enabled(&mut self, name: &str, enabled: bool) {
        if let Some(policy) = self.policies.iter_mut().find(|p| p.name == name) {
            policy.enabled = enabled;
        }
    }
}

impl Default for GovernanceEngine {
    fn default() -> Self {
        Self::new()
    }
}

impl AuditIntegration {
    pub fn new(engine: GovernanceEngine) -> Self {
        Self {
            engine,
            logs: vec![],
        }
    }

    /// Process delta through governance rules and generate audit log
    pub fn process_delta(&mut self, delta: &DeltaEvent) -> Result<Vec<PolicyViolation>> {
        let violations = self.engine.evaluate_delta(delta);

        // Log violations
        for violation in &violations {
            self.append_log(AuditLog {
                id: Uuid::new_v4(),
                repo_id: delta.repo_id,
                event_type: AuditEventType::ViolationDetected,
                violation: Some(violation.clone()),
                timestamp: Utc::now(),
            });
        }

        Ok(violations)
    }

    /// Append to immutable audit log
    pub fn append_log(&mut self, log: AuditLog) {
        self.logs.push(log);
    }

    /// Get all audit logs (immutable view)
    pub fn get_logs(&self) -> &[AuditLog] {
        &self.logs
    }

    /// Filter logs by event type
    pub fn filter_logs(&self, event_type: AuditEventType) -> Vec<&AuditLog> {
        self.logs
            .iter()
            .filter(|log| log.event_type == event_type)
            .collect()
    }

    /// Filter logs by severity level (for user access control)
    pub fn filter_by_severity(&self, min_severity: &ViolationSeverity) -> Vec<&AuditLog> {
        self.logs
            .iter()
            .filter(|log| {
                if let Some(violation) = &log.violation {
                    &violation.severity >= min_severity
                } else {
                    false
                }
            })
            .collect()
    }

    /// Evaluate snapshot and update governance status
    pub fn evaluate_snapshot(&mut self, snapshot: &mut RepoSnapshot) -> Result<()> {
        // Check for critical violations
        let has_critical = snapshot
            .policy_violations
            .iter()
            .any(|v| v.severity == ViolationSeverity::Critical);

        let has_high = snapshot
            .policy_violations
            .iter()
            .any(|v| v.severity == ViolationSeverity::High);

        if has_critical {
            snapshot.governance_status = GovernanceStatus::Violation;
            snapshot.creator_flagged = true;
        } else if has_high {
            snapshot.governance_status = GovernanceStatus::Flagged;
        } else if snapshot.policy_violations.is_empty() {
            snapshot.governance_status = GovernanceStatus::Compliant;
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_governance_engine_creation() {
        let engine = GovernanceEngine::new();
        assert!(!engine.list_policies().is_empty());
    }

    #[test]
    fn test_policy_enable_disable() {
        let mut engine = GovernanceEngine::new();
        let initial_enabled = engine.list_policies().iter().filter(|p| p.enabled).count();

        engine.disable_policy("require_signed_commits");
        let after_disable = engine.list_policies().iter().filter(|p| p.enabled).count();

        assert_eq!(after_disable, initial_enabled - 1);

        engine.enable_policy("require_signed_commits");
        let after_enable = engine.list_policies().iter().filter(|p| p.enabled).count();

        assert_eq!(after_enable, initial_enabled);
    }

    #[test]
    fn test_audit_log_append() {
        let engine = GovernanceEngine::new();
        let mut audit = AuditIntegration::new(engine);

        let log = AuditLog {
            id: Uuid::new_v4(),
            repo_id: Uuid::new_v4(),
            event_type: AuditEventType::ComplianceAchieved,
            violation: None,
            timestamp: Utc::now(),
        };

        audit.append_log(log);
        assert_eq!(audit.get_logs().len(), 1);
    }

    #[test]
    fn test_audit_log_filtering() {
        let engine = GovernanceEngine::new();
        let mut audit = AuditIntegration::new(engine);
        let repo_id = Uuid::new_v4();

        for _i in 0..3 {
            audit.append_log(AuditLog {
                id: Uuid::new_v4(),
                repo_id,
                event_type: AuditEventType::ComplianceAchieved,
                violation: None,
                timestamp: Utc::now(),
            });
        }

        for _ in 0..2 {
            audit.append_log(AuditLog {
                id: Uuid::new_v4(),
                repo_id,
                event_type: AuditEventType::ViolationDetected,
                violation: None,
                timestamp: Utc::now(),
            });
        }

        let filtered = audit.filter_logs(AuditEventType::ComplianceAchieved);
        assert_eq!(filtered.len(), 3);
    }
}
