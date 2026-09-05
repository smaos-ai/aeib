use siss_vertical_compliance::defense::policy_templates::{
    check_export_control, defense_role_template, DefenseAttributes, DefenseRole, FedRAMPAuditContext,
};
use siss_vertical_compliance::defense::test_harness::{DefensePilot, PilotScenario, PilotResult};
use siss_vertical_compliance::shared::contracts::defense_pilot_agreement;
use uuid::Uuid;

/// Test 1: ReBAC role evaluation - SecurityOfficer has full access
#[test]
fn test_rebac_security_officer_full_access() {
    let role = defense_role_template(DefenseRole::SecurityOfficer);
    assert_eq!(role.name, "FedRAMP Security Officer");
    assert!(role.can_delegate);
    assert!(role.audit_log_access);
    assert_eq!(role.can_access_classifications.len(), 4);
    assert!(role.can_access_classifications.contains(&"TopSecret".to_string()));
}

/// Test 2: ReBAC role evaluation - Analyst has limited access only
#[test]
fn test_rebac_analyst_limited_access() {
    let role = defense_role_template(DefenseRole::Analyst);
    assert_eq!(role.name, "FedRAMP Analyst");
    assert!(!role.can_delegate);
    assert!(!role.audit_log_access);
    assert_eq!(role.can_access_classifications.len(), 1);
    assert_eq!(role.can_access_classifications[0], "Unclassified");
}

/// Test 3: Export control blocks non-allied countries
#[test]
fn test_export_control_blocks_non_allies() {
    let result = check_export_control("CN", "Unclassified");
    assert!(result.is_err());
    assert!(result.unwrap_err().contains("blocked by FedRAMP export control"));
}

/// Test 4: Export control allows Five Eyes countries
#[test]
fn test_export_control_allows_five_eyes() {
    let result = check_export_control("AU", "Unclassified");
    assert!(result.is_ok());
}

/// Test 5: Export control blocks TopSecret re-export to non-US
#[test]
fn test_export_control_blocks_topsecret_outside_us() {
    let result = check_export_control("CA", "TopSecret");
    assert!(result.is_err());
    assert!(result.unwrap_err().contains("cannot be exported"));
}

/// Test 6: Export control allows TopSecret within US
#[test]
fn test_export_control_allows_topsecret_us() {
    let result = check_export_control("US", "TopSecret");
    assert!(result.is_ok());
}

/// Test 7: Pilot simulator validates facility tier enforcement
#[test]
fn test_pilot_facility_tier_enforcement() {
    let scenario = PilotScenario {
        name: "Facility Tier T1 Access Test".to_string(),
        requester_role: DefenseRole::Auditor,
        target_facility: "T1".to_string(),
        requested_classification: "Secret".to_string(),
    };

    let pilot = DefensePilot::new("Test Defense Customer");
    let result = pilot.evaluate_access(&scenario);

    // Auditor can access T1 facility with Secret classification
    assert_eq!(result.decision, "Allow");
    assert!(result.audit_trail.contains("Auditor"));
}

/// Test 8: Pilot simulator blocks facility tier mismatch
#[test]
fn test_pilot_facility_tier_mismatch() {
    let scenario = PilotScenario {
        name: "Facility Tier Mismatch Test".to_string(),
        requester_role: DefenseRole::Analyst,
        target_facility: "T1".to_string(), // Analyst can only access T3
        requested_classification: "Unclassified".to_string(),
    };

    let pilot = DefensePilot::new("Test Defense Customer");
    let result = pilot.evaluate_access(&scenario);

    assert_eq!(result.decision, "Deny");
    assert!(result.reason.contains("facility tier"));
}

/// Test 9: Audit trail captures all decisions with timestamps
#[test]
fn test_audit_trail_captures_decisions() {
    let scenario = PilotScenario {
        name: "Audit Trail Test".to_string(),
        requester_role: DefenseRole::SecurityOfficer,
        target_facility: "T1".to_string(),
        requested_classification: "TopSecret".to_string(),
    };

    let pilot = DefensePilot::new("Test Defense Customer");
    let result = pilot.evaluate_access(&scenario);

    assert!(!result.timestamp.is_empty());
    assert!(result.audit_trail.len() > 0);
    assert!(result.audit_trail.contains("SecurityOfficer"));
    assert!(result.audit_trail.contains("TopSecret"));
}

/// Test 10: Classification level enforcement (role-based access)
#[test]
fn test_classification_level_enforcement() {
    let role = defense_role_template(DefenseRole::Auditor);

    // Auditor can access Secret
    assert!(role.can_access_classifications.contains(&"Secret".to_string()));

    // But check that SecurityOfficer can access TopSecret
    let sec_officer_role = defense_role_template(DefenseRole::SecurityOfficer);
    assert!(sec_officer_role.can_access_classifications.contains(&"TopSecret".to_string()));
}

/// Test 11: Pilot agreement structure validation
#[test]
fn test_defense_pilot_agreement_structure() {
    let agreement = defense_pilot_agreement();
    assert_eq!(agreement.pilot_duration_days, 90);
    assert_eq!(agreement.pilot_fee_eur, 120_000);
    assert_eq!(agreement.scope_of_work.len(), 3);
    assert_eq!(agreement.success_criteria.len(), 3);
}

/// Test 12: FedRAMP audit context serialization
#[test]
fn test_fedramp_audit_context_serialization() {
    let context = FedRAMPAuditContext {
        requester_id: Uuid::new_v4(),
        requester_role: DefenseRole::SecurityOfficer,
        action: "data_export".to_string(),
        classification_level: "Secret".to_string(),
        facility: "T1".to_string(),
        authorization_source: "DCID 6/4".to_string(),
    };

    let json = serde_json::to_string(&context).unwrap();
    let deserialized: FedRAMPAuditContext = serde_json::from_str(&json).unwrap();

    assert_eq!(deserialized.action, "data_export");
    assert_eq!(deserialized.classification_level, "Secret");
}

/// Test 13: Defense attributes validation
#[test]
fn test_defense_attributes_validation() {
    let attrs = DefenseAttributes {
        clearance_level: "Secret".to_string(),
        facility_tier: "T1".to_string(),
        program_authorization: vec!["Project Alpha".to_string()],
        country_authorized: vec!["US".to_string(), "CA".to_string()],
        is_us_citizen: true,
    };

    assert!(attrs.is_us_citizen);
    assert!(attrs.country_authorized.contains(&"US".to_string()));
    assert_eq!(attrs.clearance_level, "Secret");
}

/// Test 14: Pilot result contains required fields for compliance audit
#[test]
fn test_pilot_result_contains_audit_fields() {
    let scenario = PilotScenario {
        name: "Audit Fields Test".to_string(),
        requester_role: DefenseRole::Auditor,
        target_facility: "T1".to_string(),
        requested_classification: "Secret".to_string(),
    };

    let pilot = DefensePilot::new("Test Customer");
    let result = pilot.evaluate_access(&scenario);

    // Verify all required audit fields are present
    assert!(!result.decision.is_empty());
    assert!(!result.timestamp.is_empty());
    assert!(!result.audit_trail.is_empty());
    assert!(result.decision == "Allow" || result.decision == "Deny");
}

/// Test 15: Multiple role scenarios in sequence (audit trail continuity)
#[test]
fn test_multiple_role_scenarios_sequence() {
    let pilot = DefensePilot::new("Test Customer");

    let scenario1 = PilotScenario {
        name: "First Request".to_string(),
        requester_role: DefenseRole::Analyst,
        target_facility: "T3".to_string(),
        requested_classification: "Unclassified".to_string(),
    };

    let scenario2 = PilotScenario {
        name: "Second Request".to_string(),
        requester_role: DefenseRole::SecurityOfficer,
        target_facility: "T1".to_string(),
        requested_classification: "TopSecret".to_string(),
    };

    let result1 = pilot.evaluate_access(&scenario1);
    let result2 = pilot.evaluate_access(&scenario2);

    // Both should complete without errors
    assert!(!result1.decision.is_empty());
    assert!(!result2.decision.is_empty());

    // Different timestamps indicate separate audit trail entries
    assert_ne!(result1.timestamp, result2.timestamp);
}
