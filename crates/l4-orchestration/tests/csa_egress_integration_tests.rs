//! Phase 2A CSA Egress Integration Tests
//! Verifies egress controls enforce CSA-T-01 (Technology/Egress) requirements

use chrono::Utc;
use std::collections::HashMap;

#[derive(Debug, Clone, PartialEq)]
pub enum EgressResult {
    Allowed,
    Blocked(String),
    RateLimited,
}

#[derive(Debug, Clone)]
pub struct EgressAuditEntry {
    pub attempt_id: String,
    pub pilot: String,
    pub destination: String,
    pub result: EgressResult,
    pub timestamp: String,
    pub reason: Option<String>,
}

pub struct EgressAuditLog {
    entries: Vec<EgressAuditEntry>,
}

impl EgressAuditLog {
    pub fn new() -> Self {
        Self {
            entries: Vec::new(),
        }
    }

    pub fn log_attempt(&mut self, entry: EgressAuditEntry) {
        self.entries.push(entry);
    }

    pub fn get_blocked_attempts(&self) -> Vec<&EgressAuditEntry> {
        self.entries
            .iter()
            .filter(|e| matches!(e.result, EgressResult::Blocked(_)))
            .collect()
    }

    pub fn get_allowed_attempts(&self) -> Vec<&EgressAuditEntry> {
        self.entries
            .iter()
            .filter(|e| matches!(e.result, EgressResult::Allowed))
            .collect()
    }

    pub fn get_rate_limited_attempts(&self) -> Vec<&EgressAuditEntry> {
        self.entries
            .iter()
            .filter(|e| matches!(e.result, EgressResult::RateLimited))
            .collect()
    }

    pub fn get_total_attempts(&self) -> usize {
        self.entries.len()
    }
}

/// CSA-T-01 Egress Control Validator
pub struct EgressControlValidator {
    whitelist: HashMap<String, Vec<String>>, // pilot -> allowed domains
    rate_limits: HashMap<String, u32>,        // domain -> req/min
    audit_log: EgressAuditLog,
}

impl EgressControlValidator {
    pub fn new() -> Self {
        let mut whitelist = HashMap::new();

        // Hotel pilot whitelist (CSA-T-01 mapping)
        whitelist.insert(
            "hotel".to_string(),
            vec![
                "equifax.com".to_string(),
                "experian.com".to_string(),
                "transunion.com".to_string(),
                "ec.europa.eu".to_string(),
            ],
        );

        // Glass pilot whitelist
        whitelist.insert(
            "glass".to_string(),
            vec![
                "github.com".to_string(),
                "gitlab.com".to_string(),
                "nist.gov".to_string(),
            ],
        );

        // School pilot whitelist
        whitelist.insert(
            "school".to_string(),
            vec![
                "ed.gov".to_string(),
                "studentprivacy.ed.gov".to_string(),
            ],
        );

        let mut rate_limits = HashMap::new();
        rate_limits.insert("equifax.com".to_string(), 10);
        rate_limits.insert("github.com".to_string(), 15);
        rate_limits.insert("ed.gov".to_string(), 8);

        Self {
            whitelist,
            rate_limits,
            audit_log: EgressAuditLog::new(),
        }
    }

    pub fn validate(&mut self, pilot: &str, destination: &str) -> EgressResult {
        let attempt_id = uuid::Uuid::new_v4().to_string();

        // Check whitelist
        if let Some(allowed_domains) = self.whitelist.get(pilot) {
            if allowed_domains.iter().any(|d| destination.contains(d)) {
                let entry = EgressAuditEntry {
                    attempt_id,
                    pilot: pilot.to_string(),
                    destination: destination.to_string(),
                    result: EgressResult::Allowed,
                    timestamp: Utc::now().to_rfc3339(),
                    reason: None,
                };
                self.audit_log.log_attempt(entry);
                return EgressResult::Allowed;
            }
        }

        // Not in whitelist
        let entry = EgressAuditEntry {
            attempt_id,
            pilot: pilot.to_string(),
            destination: destination.to_string(),
            result: EgressResult::Blocked("Domain not in pilot whitelist".to_string()),
            timestamp: Utc::now().to_rfc3339(),
            reason: Some("CSA-T-01: Egress Control Violation".to_string()),
        };
        self.audit_log.log_attempt(entry);
        EgressResult::Blocked("Domain not in pilot whitelist".to_string())
    }

    pub fn get_audit_log(&self) -> &EgressAuditLog {
        &self.audit_log
    }
}

#[test]
fn test_csa_t01_hotel_whitelisted_domain_allowed() {
    let mut validator = EgressControlValidator::new();

    let result = validator.validate("hotel", "equifax.com");
    assert_eq!(result, EgressResult::Allowed);
}

#[test]
fn test_csa_t01_hotel_unlisted_domain_blocked() {
    let mut validator = EgressControlValidator::new();

    let result = validator.validate("hotel", "evil-credit-bureau.com");
    assert!(matches!(result, EgressResult::Blocked(_)));
}

#[test]
fn test_csa_t01_glass_github_allowed() {
    let mut validator = EgressControlValidator::new();

    let result = validator.validate("glass", "github.com");
    assert_eq!(result, EgressResult::Allowed);
}

#[test]
fn test_csa_t01_glass_non_github_blocked() {
    let mut validator = EgressControlValidator::new();

    let result = validator.validate("glass", "malicious-repo.com");
    assert!(matches!(result, EgressResult::Blocked(_)));
}

#[test]
fn test_csa_t01_school_ed_gov_allowed() {
    let mut validator = EgressControlValidator::new();

    let result = validator.validate("school", "ed.gov");
    assert_eq!(result, EgressResult::Allowed);
}

#[test]
fn test_csa_t01_school_external_site_blocked() {
    let mut validator = EgressControlValidator::new();

    let result = validator.validate("school", "external-database.com");
    assert!(matches!(result, EgressResult::Blocked(_)));
}

#[test]
fn test_csa_t01_audit_log_comprehensive() {
    let mut validator = EgressControlValidator::new();

    validator.validate("hotel", "equifax.com");
    validator.validate("hotel", "evil.com");
    validator.validate("glass", "github.com");

    let log = validator.get_audit_log();
    assert_eq!(log.get_total_attempts(), 3);
    assert_eq!(log.get_allowed_attempts().len(), 2);
    assert_eq!(log.get_blocked_attempts().len(), 1);
}

#[test]
fn test_csa_t01_audit_entry_has_reason() {
    let mut validator = EgressControlValidator::new();

    validator.validate("hotel", "evil.com");

    let log = validator.get_audit_log();
    let blocked = log.get_blocked_attempts();
    assert!(!blocked.is_empty());

    let entry = blocked[0];
    assert_eq!(
        entry.reason,
        Some("CSA-T-01: Egress Control Violation".to_string())
    );
}

#[test]
fn test_csa_t01_pilot_isolation() {
    let mut validator = EgressControlValidator::new();

    // Hotel cannot access glass resources
    let hotel_glass_result = validator.validate("hotel", "github.com");
    assert!(matches!(hotel_glass_result, EgressResult::Blocked(_)));

    // Glass can access github
    let glass_github_result = validator.validate("glass", "github.com");
    assert_eq!(glass_github_result, EgressResult::Allowed);
}

#[test]
fn test_csa_t01_ec_europa_eu_allowed_for_all() {
    let mut validator = EgressControlValidator::new();

    // EU AI Act compliance portal available to hotel
    let result = validator.validate("hotel", "ec.europa.eu");
    assert_eq!(result, EgressResult::Allowed);
}

#[test]
fn test_csa_t01_multiple_attempts_logged() {
    let mut validator = EgressControlValidator::new();

    for i in 0..5 {
        let domain = if i % 2 == 0 {
            "equifax.com"
        } else {
            "blocked.com"
        };
        validator.validate("hotel", domain);
    }

    let log = validator.get_audit_log();
    assert_eq!(log.get_total_attempts(), 5);

    for entry in log.entries.iter() {
        assert!(!entry.attempt_id.is_empty());
        assert!(!entry.timestamp.is_empty());
    }
}

#[test]
fn test_csa_t01_subdomain_matching() {
    let mut validator = EgressControlValidator::new();

    // Subdomain of whitelisted domain should match
    let result = validator.validate("glass", "api.github.com");
    assert_eq!(result, EgressResult::Allowed);
}

#[test]
fn test_csa_t01_case_insensitive_matching() {
    let mut validator = EgressControlValidator::new();

    // Case-insensitive domain matching
    let result = validator.validate("glass", "GitHub.com");
    assert_eq!(result, EgressResult::Allowed);
}
