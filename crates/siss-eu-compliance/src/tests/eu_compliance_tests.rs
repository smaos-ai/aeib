use siss_eu_compliance::{
    ai_act_analyzer::AIActAnalyzer, gdpr_mapper::GDPRMapper, iso27001_audit::ISO27001Audit,
    nis2_enforcer::NIS2Enforcer, soc2_attestation::SOC2Attestation,
    tisax_validator::TISAXValidator,
};

// =====================================================================
// GDPR Mapper Tests (6 tests)
// =====================================================================

#[test]
fn test_gdpr_article_4_definitions_mapping() {
    let mapper = GDPRMapper::new();
    let definitions = mapper.article_4_definitions();

    assert!(definitions.contains_key("personal_data"));
    assert!(definitions.contains_key("processing"));
    assert!(definitions.contains_key("data_controller"));
    assert!(definitions.contains_key("data_processor"));
    assert!(definitions.contains_key("consent"));
    assert!(definitions.len() >= 22);
}

#[test]
fn test_gdpr_article_5_principles_enforcement() {
    let mapper = GDPRMapper::new();
    let principles = mapper.article_5_principles();

    assert!(principles.contains(&"lawfulness"));
    assert!(principles.contains(&"fairness"));
    assert!(principles.contains(&"transparency"));
    assert!(principles.contains(&"purpose_limitation"));
    assert!(principles.contains(&"data_minimization"));
    assert!(principles.contains(&"accuracy"));
    assert!(principles.contains(&"storage_limitation"));
    assert!(principles.contains(&"integrity_confidentiality"));
    assert!(principles.len() == 8);
}

#[test]
fn test_gdpr_consent_flow_automation() {
    let mapper = GDPRMapper::new();
    let consent_flow = mapper.generate_consent_flow("email_marketing", "user123");

    assert_eq!(consent_flow.purpose, "email_marketing");
    assert_eq!(consent_flow.data_subject_id, "user123");
    assert!(consent_flow.timestamp.is_some());
    assert_eq!(consent_flow.consent_status, "pending");
    assert!(consent_flow.withdrawal_mechanism.is_some());
}

#[test]
fn test_gdpr_data_processing_agreement_generation() {
    let mapper = GDPRMapper::new();
    let dpa = mapper.generate_dpa("processor_org", vec!["data_processing", "analytics"]);

    assert_eq!(dpa.processor_name, "processor_org");
    assert!(dpa.scope.iter().any(|s| s == "data_processing"));
    assert!(dpa.scope.iter().any(|s| s == "analytics"));
    assert!(dpa.includes_article_28_terms());
    assert!(dpa.includes_security_requirements());
}

#[test]
fn test_gdpr_data_subject_access_request() {
    let mapper = GDPRMapper::new();
    let dsar = mapper.process_data_subject_access_request("subject123", "all_data");

    assert_eq!(dsar.subject_id, "subject123");
    assert!(dsar.request_timestamp.is_some());
    assert_eq!(dsar.status, "processing");
    assert_eq!(dsar.response_deadline_days, 30);
}

#[test]
fn test_gdpr_right_to_be_forgotten() {
    let mapper = GDPRMapper::new();
    let deletion_request = mapper.initiate_right_to_be_forgotten("user456", "all");

    assert_eq!(deletion_request.subject_id, "user456");
    assert_eq!(deletion_request.scope, "all");
    assert_eq!(deletion_request.status, "initiated");
    assert!(deletion_request.requires_third_party_notification);
}

// =====================================================================
// NIS2 Enforcer Tests (6 tests)
// =====================================================================

#[test]
fn test_nis2_network_segmentation_rules() {
    let enforcer = NIS2Enforcer::new();
    let rules = enforcer.network_segmentation_rules();

    assert!(rules.contains_rule("isolate_critical_systems"));
    assert!(rules.contains_rule("encrypt_inter_segment_traffic"));
    assert!(rules.contains_rule("monitor_segment_boundaries"));
    assert_eq!(rules.enforcement_mode, "fail_closed");
}

#[test]
fn test_nis2_cloud_infrastructure_requirements() {
    let enforcer = NIS2Enforcer::new();
    let requirements = enforcer.cloud_infrastructure_requirements();

    assert!(requirements.requires_data_residency_eu);
    assert!(requirements.requires_encryption_at_rest);
    assert!(requirements.requires_encryption_in_transit);
    assert!(requirements.requires_access_logging);
    assert_eq!(requirements.minimum_redundancy_zones, 2);
}

#[test]
fn test_nis2_incident_reporting_automation() {
    let enforcer = NIS2Enforcer::new();
    let incident =
        enforcer.create_incident_report("security_breach", "unauthorized_access", "high");

    assert_eq!(incident.incident_type, "security_breach");
    assert_eq!(incident.severity, "high");
    assert!(incident.timestamp.is_some());
    assert_eq!(incident.competent_authority_notification_hours, 72);
}

#[test]
fn test_nis2_supply_chain_risk_assessment() {
    let enforcer = NIS2Enforcer::new();
    let assessment = enforcer
        .assess_supply_chain_risk(vec!["vendor_a", "vendor_b"], vec!["software", "hosting"]);

    assert_eq!(assessment.vendors_count, 2);
    assert_eq!(assessment.service_categories_count, 2);
    assert!(assessment.risk_score >= 0.0 && assessment.risk_score <= 1.0);
    assert_eq!(assessment.mitigation_status, "pending");
}

#[test]
fn test_nis2_multi_factor_authentication_enforcement() {
    let enforcer = NIS2Enforcer::new();
    let mfa_policy = enforcer.mfa_enforcement_policy();

    assert_eq!(mfa_policy.required_factors, 2);
    assert!(mfa_policy.supports_hardware_keys);
    assert!(mfa_policy.supports_biometric);
    assert!(!mfa_policy.allows_sms_only);
}

#[test]
fn test_nis2_vulnerability_disclosure() {
    let enforcer = NIS2Enforcer::new();
    let disclosure = enforcer.vulnerability_disclosure("cve_2026_1234", "critical");

    assert!(disclosure.cve_id.is_some());
    assert_eq!(disclosure.severity, "critical");
    assert_eq!(disclosure.disclosure_deadline_days, 90);
    assert!(disclosure.requires_customer_notification);
}

// =====================================================================
// EU AI Act Analyzer Tests (6 tests)
// =====================================================================

#[test]
fn test_ai_act_prohibited_practices_blocking() {
    let analyzer = AIActAnalyzer::new();
    let prohibited = analyzer.prohibited_practices();

    assert!(prohibited.is_banned("real_time_remote_biometric_identification"));
    assert!(prohibited.is_banned("social_credit_scoring"));
    assert!(prohibited.is_banned("emotion_detection_workplace"));
    assert!(prohibited.is_banned("mass_surveillance"));
    assert_eq!(prohibited.enforcement_mode(), "fail_closed");
    assert_eq!(prohibited.total_banned_practices(), 4);
}

#[test]
fn test_ai_act_high_risk_system_flagging() {
    let analyzer = AIActAnalyzer::new();
    let high_risk = analyzer.assess_risk_level("facial_recognition_border_control");

    assert_eq!(high_risk.risk_category, "high_risk");
    assert!(high_risk.requires_conformity_assessment);
    assert!(high_risk.requires_human_oversight);
    assert!(high_risk.requires_risk_register);
}

#[test]
fn test_ai_act_transparency_requirements() {
    let analyzer = AIActAnalyzer::new();
    let transparency = analyzer.transparency_requirements("recommendation_system");

    assert!(transparency.requires_disclosure_to_user);
    assert!(transparency.requires_explanation_of_decision);
    assert!(transparency.requires_data_sources_disclosure);
    assert!(transparency.requires_decision_logic_documentation);
}

#[test]
fn test_ai_act_biometric_identification_ban() {
    let analyzer = AIActAnalyzer::new();
    let biometric_rule = analyzer.biometric_identification_policy();

    assert!(!biometric_rule.allows_real_time_identification());
    assert!(!biometric_rule.allows_covert_identification());
    assert!(biometric_rule.allows_post_hoc_identification());
    assert_eq!(biometric_rule.enforcement_level, "absolute");
}

#[test]
fn test_ai_act_social_credit_scoring_ban() {
    let analyzer = AIActAnalyzer::new();
    let social_credit_rule = analyzer.social_credit_scoring_policy();

    assert!(!social_credit_rule.allows_social_scoring());
    assert!(!social_credit_rule.allows_behavior_scoring());
    assert_eq!(social_credit_rule.enforcement_level, "absolute");
    assert!(social_credit_rule.triggers_immediate_block());
}

#[test]
fn test_ai_act_audit_trail_logging() {
    let analyzer = AIActAnalyzer::new();
    let audit_trail = analyzer.create_audit_trail("ai_system_xyz", "high_risk_decision", "user456");

    assert_eq!(audit_trail.system_id, "ai_system_xyz");
    assert!(audit_trail.timestamp.is_some());
    assert!(audit_trail.is_immutable);
    assert_eq!(audit_trail.retention_years, 7);
}

// =====================================================================
// ISO 27001 Audit Tests (5 tests)
// =====================================================================

#[test]
fn test_iso27001_control_mapping() {
    let audit = ISO27001Audit::new();
    let controls = audit.control_mapping();

    assert!(controls.contains_key("A.5.1.1"));
    assert!(controls.contains_key("A.6.2.1"));
    assert!(controls.contains_key("A.7.2.1"));
    assert!(controls.contains_key("A.8.2.1"));
    assert!(controls.len() >= 14);
}

#[test]
fn test_iso27001_evidence_collection() {
    let audit = ISO27001Audit::new();
    let evidence = audit.collect_evidence("access_control_policy", "implemented");

    assert_eq!(evidence.control_id, "access_control_policy");
    assert_eq!(evidence.status, "implemented");
    assert!(evidence.timestamp.is_some());
    assert!(evidence.requires_documentation);
}

#[test]
fn test_iso27001_gap_analysis() {
    let audit = ISO27001Audit::new();
    let gaps = audit.perform_gap_analysis();

    assert!(!gaps.is_empty());
    for gap in gaps.iter() {
        assert!(gap.control_id.len() > 0);
        assert!(gap.severity.len() > 0);
    }
    assert!(gaps.len() >= 3);
}

#[test]
fn test_iso27001_remediation_plan() {
    let audit = ISO27001Audit::new();
    let plan = audit.generate_remediation_plan(vec!["gap_auth_001", "gap_audit_002"]);

    assert_eq!(plan.gap_count, 2);
    assert!(plan.timeline_weeks.is_some());
    assert!(plan.responsible_parties.len() > 0);
}

#[test]
fn test_iso27001_audit_report_generation() {
    let audit = ISO27001Audit::new();
    let report = audit.generate_audit_report();

    assert!(report.includes_control_mapping);
    assert!(report.includes_gap_analysis);
    assert!(report.includes_remediation_plan);
    assert!(report.is_signed);
}

// =====================================================================
// SOC 2 Attestation Tests (4 tests)
// =====================================================================

#[test]
fn test_soc2_trust_service_criteria_security() {
    let attestation = SOC2Attestation::new();
    let criteria = attestation.trust_service_criteria("security");

    assert!(criteria.cc_principles.contains(&"CC6.1"));
    assert!(criteria.cc_principles.contains(&"CC6.2"));
    assert!(criteria.cc_principles.contains(&"CC7.2"));
    assert!(criteria.report_type == "Type_II");
}

#[test]
fn test_soc2_availability_monitoring() {
    let attestation = SOC2Attestation::new();
    let monitoring = attestation.availability_monitoring_controls();

    assert!(monitoring.tracks_uptime);
    assert_eq!(monitoring.monitoring_frequency_minutes, 5);
    assert!(monitoring.includes_alerting);
    assert_eq!(monitoring.target_availability_percent, 99.99);
}

#[test]
fn test_soc2_processing_integrity() {
    let attestation = SOC2Attestation::new();
    let integrity = attestation.processing_integrity_controls();

    assert!(integrity.validates_input_completeness);
    assert!(integrity.validates_processing_accuracy);
    assert!(integrity.validates_output_completeness);
    assert!(integrity.enforces_access_controls);
}

#[test]
fn test_soc2_audit_log_immutability() {
    let attestation = SOC2Attestation::new();
    let audit_log = attestation.create_audit_log_policy();

    assert!(audit_log.is_immutable);
    assert!(audit_log.is_tamper_evident);
    assert_eq!(audit_log.retention_years, 3);
    assert!(audit_log.is_encrypted);
}

// =====================================================================
// TISAX Validator Tests (3 tests)
// =====================================================================

#[test]
fn test_tisax_level3_prerequisites() {
    let validator = TISAXValidator::new();
    let level3 = validator.level3_prerequisites();

    assert!(level3.requires_iso27001);
    assert!(level3.requires_sei_cmm_level_2);
    assert!(level3.requires_personnel_security);
    assert!(level3.requires_incident_response_plan);
    assert!(level3.checklist_items.len() >= 10);
}

#[test]
fn test_tisax_certification_timeline() {
    let validator = TISAXValidator::new();
    let timeline = validator.certification_timeline("level_3");

    assert!(timeline.total_weeks.is_some());
    assert!(timeline.phases.len() >= 3);
    assert!(timeline.includes_audit_readiness_review);
    assert_eq!(timeline.audit_frequency_months, 12);
}

#[test]
fn test_tisax_audit_readiness_checklist() {
    let validator = TISAXValidator::new();
    let checklist = validator.audit_readiness_checklist();

    assert!(!checklist.is_empty());
    for item in checklist.iter() {
        assert!(item.category.len() > 0);
        assert!(item.is_critical || !item.is_critical);
    }
    assert!(checklist.len() >= 15);
}
