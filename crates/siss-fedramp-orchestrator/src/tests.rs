// FedRAMP Compliance Tests - TDD First Approach
// All tests initially fail, implementation follows

use crate::*;
use std::collections::HashMap;
use chrono::Utc;

#[test]
fn test_fedramp_orchestrator_creation() {
    let orchestrator = FedRAMPOrchestrator::new("test-system");
    assert_eq!(orchestrator.system_name(), "test-system");
    assert!(orchestrator.controls().is_empty());
}

#[test]
fn test_fedramp_level_hierarchy() {
    assert!(FedRAMPLevel::Low < FedRAMPLevel::Moderate);
    assert!(FedRAMPLevel::Moderate < FedRAMPLevel::High);
}

#[test]
fn test_register_control_with_evidence() {
    let mut orchestrator = FedRAMPOrchestrator::new("test-system");
    let evidence = ControlEvidence {
        control_id: "AC-2".to_string(),
        implementation_path: "siss-gatekeeper/src/policy.rs".to_string(),
        timestamp: Utc::now(),
        validated: true,
    };
    orchestrator.register_control("AC-2", evidence);
    assert!(orchestrator.has_control("AC-2"));
}

#[test]
fn test_control_family_classification() {
    assert_eq!(ControlFamily::AccessControl.code(), "AC");
    assert_eq!(ControlFamily::AuditAndAccountability.code(), "AU");
    assert_eq!(ControlFamily::IdentificationAndAuthentication.code(), "IA");
}

#[test]
fn test_data_classification_levels() {
    let data = DataClassification::HighImpact;
    assert!(data.requires_encryption());
    assert!(data.requires_audit());
}

#[test]
fn test_access_policy_enforcement() {
    let policy = AccessPolicy::new("admin", "AC-2");
    assert_eq!(policy.role(), "admin");
    assert!(policy.is_valid());
}

#[test]
fn test_control_validation_with_nist_mapping() {
    let orchestrator = FedRAMPOrchestrator::new("test");
    let control = FedRAMPControl {
        id: "AC-2".to_string(),
        family: ControlFamily::AccessControl,
        title: "Account Management".to_string(),
        description: "The organization manages information system accounts".to_string(),
    };
    assert!(orchestrator.validate_control(&control));
}

#[test]
fn test_control_enhancement_tracking() {
    let mut orchestrator = FedRAMPOrchestrator::new("test");
    let enhancement = "AC-2(1)".to_string();
    orchestrator.add_control_enhancement(enhancement.clone());
    assert!(orchestrator.has_enhancement("AC-2(1)"));
}

#[test]
fn test_fedramp_low_baseline_completeness() {
    let orchestrator = FedRAMPOrchestrator::new_with_baseline("test", FedRAMPLevel::Low);
    assert!(orchestrator.control_count() > 0);
    assert_eq!(orchestrator.level(), FedRAMPLevel::Low);
}

#[test]
fn test_fedramp_moderate_baseline_completeness() {
    let orchestrator = FedRAMPOrchestrator::new_with_baseline("test", FedRAMPLevel::Moderate);
    assert!(orchestrator.control_count() > orchestrator.new_with_baseline("test", FedRAMPLevel::Low).control_count());
    assert_eq!(orchestrator.level(), FedRAMPLevel::Moderate);
}

#[test]
fn test_fedramp_high_baseline_completeness() {
    let orchestrator = FedRAMPOrchestrator::new_with_baseline("test", FedRAMPLevel::High);
    assert!(orchestrator.control_count() > orchestrator.new_with_baseline("test", FedRAMPLevel::Moderate).control_count());
    assert_eq!(orchestrator.level(), FedRAMPLevel::High);
}

#[test]
fn test_compliance_assessment_generation() {
    let orchestrator = FedRAMPOrchestrator::new("test");
    let report = orchestrator.generate_assessment_report();
    assert!(!report.system_name.is_empty());
    assert!(report.assessment_date > chrono::DateTime::<Utc>::default());
}

#[test]
fn test_control_inheritance_tracking() {
    let mut orchestrator = FedRAMPOrchestrator::new("test");
    orchestrator.mark_control_as_inherited("IA-2", "parent-system");
    assert!(orchestrator.is_control_inherited("IA-2"));
    assert_eq!(orchestrator.inherited_from("IA-2"), Some("parent-system".to_string()));
}

#[test]
fn test_remediation_plan_tracking() {
    let mut orchestrator = FedRAMPOrchestrator::new("test");
    let plan = RemediationPlan {
        control_id: "AC-5".to_string(),
        target_date: Utc::now() + chrono::Duration::days(30),
        description: "Implement principle of least privilege".to_string(),
        status: RemediationStatus::InProgress,
    };
    orchestrator.add_remediation_plan(plan);
    assert!(orchestrator.has_remediation("AC-5"));
}

#[test]
fn test_authorization_boundary_definition() {
    let mut orchestrator = FedRAMPOrchestrator::new("test");
    orchestrator.set_authorization_boundary(vec![
        "siss-gatekeeper".to_string(),
        "siss-enclave".to_string(),
    ]);
    assert!(orchestrator.in_boundary("siss-gatekeeper"));
    assert!(!orchestrator.in_boundary("external-service"));
}

#[test]
fn test_continuous_monitoring_integration() {
    let orchestrator = FedRAMPOrchestrator::new("test");
    assert!(orchestrator.supports_continuous_monitoring());
    let monitors = orchestrator.active_monitors();
    assert!(!monitors.is_empty());
}

#[test]
fn test_incident_response_coordination() {
    let mut orchestrator = FedRAMPOrchestrator::new("test");
    let incident = SecurityIncident {
        id: "INC-001".to_string(),
        severity: IncidentSeverity::High,
        description: "Unauthorized access attempt".to_string(),
        timestamp: Utc::now(),
    };
    orchestrator.log_incident(incident);
    assert_eq!(orchestrator.incident_count(), 1);
}
