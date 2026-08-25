// CJIS Compliance Tests - TDD First Approach
// All tests initially fail, implementation follows

use crate::*;
use chrono::Utc;

#[test]
fn test_cjis_gateway_creation() {
    let gateway = CJISGateway::new("test-gateway");
    assert_eq!(gateway.gateway_id(), "test-gateway");
    assert!(gateway.is_operational());
}

#[test]
fn test_cjis_compliance_level_hierarchy() {
    assert!(CJISComplianceLevel::Minimal < CJISComplianceLevel::Standard);
    assert!(CJISComplianceLevel::Standard < CJISComplianceLevel::Enhanced);
}

#[test]
fn test_cjis_control_registration() {
    let mut gateway = CJISGateway::new("test");
    let control = CJISControl {
        id: "AC-1".to_string(),
        category: ControlCategory::AccessControl,
        title: "Access Control Policy".to_string(),
        description: "Organization enforces CJIS access control requirements".to_string(),
    };
    gateway.register_control(control);
    assert!(gateway.has_control("AC-1"));
}

#[test]
fn test_sensitive_data_classification() {
    let level = SensitivityLevel::CJISRestricted;
    assert!(level.requires_encryption());
    assert!(level.requires_audit_log());
    assert_eq!(level.minimum_classification(), "Restricted");
}

#[test]
fn test_audit_log_creation() {
    let mut gateway = CJISGateway::new("test");
    let event = AuditEvent {
        timestamp: Utc::now(),
        user_id: "user-001".to_string(),
        action: "data_access".to_string(),
        resource: "cjis_database".to_string(),
        result: AuditResult::Success,
    };
    gateway.log_event(event);
    assert_eq!(gateway.audit_log_size(), 1);
}

#[test]
fn test_encryption_policy_enforcement() {
    let policy = EncryptionPolicy::new("AES-256");
    assert_eq!(policy.algorithm(), "AES-256");
    assert!(policy.is_valid());
    assert_eq!(policy.key_length(), 256);
}

#[test]
fn test_criminal_justice_information_protection() {
    let handler = DataHandler::new(SensitivityLevel::CJISRestricted);
    assert!(handler.requires_criminal_justice_safeguards());
    assert!(handler.enforces_need_to_know());
}

#[test]
fn test_access_log_completeness() {
    let mut gateway = CJISGateway::new("test");
    let event = AuditEvent {
        timestamp: Utc::now(),
        user_id: "user-001".to_string(),
        action: "cjis_record_access".to_string(),
        resource: "criminal_records".to_string(),
        result: AuditResult::Success,
    };
    gateway.log_event(event);
    let logs = gateway.get_audit_logs("user-001");
    assert!(!logs.is_empty());
}

#[test]
fn test_multi_factor_authentication_requirement() {
    let gateway = CJISGateway::new("test");
    assert!(gateway.requires_mfa_for_cjis_access());
    assert_eq!(gateway.mfa_methods().len(), 2); // min 2 factors
}

#[test]
fn test_transmission_security_controls() {
    let gateway = CJISGateway::new("test");
    assert!(gateway.enforces_tls_13_minimum());
    assert!(gateway.validates_certificate_pinning());
}

#[test]
fn test_access_control_by_agency() {
    let mut gateway = CJISGateway::new("test");
    gateway.restrict_access_to_agency("law-enforcement-agency-01");
    assert!(gateway.can_access_for_agency("law-enforcement-agency-01"));
    assert!(!gateway.can_access_for_agency("unauthorized-agency"));
}

#[test]
fn test_audit_log_immutability() {
    let mut gateway = CJISGateway::new("test");
    let event = AuditEvent {
        timestamp: Utc::now(),
        user_id: "user-001".to_string(),
        action: "data_access".to_string(),
        resource: "resource-001".to_string(),
        result: AuditResult::Success,
    };
    gateway.log_event(event);
    assert!(gateway.audit_log_is_immutable());
}

#[test]
fn test_access_request_denial_logging() {
    let mut gateway = CJISGateway::new("test");
    let event = AuditEvent {
        timestamp: Utc::now(),
        user_id: "unauthorized-user".to_string(),
        action: "unauthorized_access_attempt".to_string(),
        resource: "cjis_data".to_string(),
        result: AuditResult::Failure,
    };
    gateway.log_event(event);
    assert_eq!(gateway.denied_access_count(), 1);
}

#[test]
fn test_data_retention_policy() {
    let gateway = CJISGateway::new("test");
    assert_eq!(gateway.audit_retention_days(), 180); // CJIS minimum
    assert!(gateway.enforces_data_retention());
}

#[test]
fn test_compliance_assessment_generation() {
    let gateway = CJISGateway::new("test");
    let report = gateway.generate_compliance_report();
    assert!(!report.gateway_id.is_empty());
    assert_eq!(report.compliance_level, CJISComplianceLevel::Standard);
}

#[test]
fn test_incident_response_procedures() {
    let mut gateway = CJISGateway::new("test");
    let incident = SecurityIncident {
        id: "INC-CJIS-001".to_string(),
        severity: IncidentSeverity::Critical,
        affected_data: "criminal_records".to_string(),
        timestamp: Utc::now(),
    };
    gateway.register_incident(incident);
    assert_eq!(gateway.active_incidents(), 1);
    assert!(gateway.has_incident_response_plan("INC-CJIS-001"));
}

#[test]
fn test_biometric_data_handling() {
    let handler = DataHandler::new(SensitivityLevel::CJISRestricted);
    assert!(handler.supports_biometric_data_protection());
    assert!(handler.enforces_biometric_encryption());
}

#[test]
fn test_audit_trail_completeness_validation() {
    let gateway = CJISGateway::new("test");
    let validation = gateway.validate_audit_trail_completeness();
    assert!(validation.is_complete());
    assert!(validation.all_required_fields_present());
}
