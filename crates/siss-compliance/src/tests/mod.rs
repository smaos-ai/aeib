#[cfg(test)]
mod tests {
    use chrono::Utc;
    use uuid::Uuid;

    use crate::{
        consent::{ConsentRecord, PurposeBasis},
        eu_ai_act::{AuditLogEntry, HumanOversightGate, RiskLevel, RiskManagementRecord},
        hipaa::{BusinessAssociateAgreement, PhiClassification},
        retention::RetentionPolicy,
    };

    /// test_consent_record_valid: ensures ConsentRecord::is_valid() returns true for active consent
    #[test]
    fn test_consent_record_valid() {
        let cr = ConsentRecord {
            data_subject_id: Uuid::new_v4(),
            purpose: PurposeBasis::Consent,
            scope: vec!["health_data".to_string()],
            granted_at: Utc::now(),
            expires_at: None,
            withdrawn_at: None,
        };
        assert!(cr.is_valid());
    }

    /// test_consent_withdrawal: ensures right_to_erasure() withdraws consent
    #[test]
    fn test_consent_withdrawal() {
        let mut cr = ConsentRecord {
            data_subject_id: Uuid::new_v4(),
            purpose: PurposeBasis::Consent,
            scope: vec!["genome".to_string()],
            granted_at: Utc::now(),
            expires_at: None,
            withdrawn_at: None,
        };
        assert!(cr.is_valid());
        cr.right_to_erasure();
        assert!(!cr.is_valid());
    }

    /// test_audit_log_expiration: ensures AuditLogEntry tracks 180-day expiration
    #[test]
    fn test_audit_log_expiration() {
        let entry = AuditLogEntry::new(
            Uuid::new_v4(),
            "decision".to_string(),
            serde_json::json!({"action": "classify_health_data"}),
        );
        // Just created, should NOT be expired
        assert!(!entry.is_expired());
        // Verify expires_at is ~180 days in future
        let diff_days = (entry.expires_at - entry.created_at).num_days();
        assert!(diff_days >= 179 && diff_days <= 181);
    }

    /// test_human_oversight_gate_approval: ensures grant_approval() marks decision as approved
    #[test]
    fn test_human_oversight_gate_approval() {
        let mut gate = HumanOversightGate {
            system_id: Uuid::new_v4(),
            requires_human_approval: true,
            approval_timeout_seconds: 900,
            approved_at: None,
            approved_by: None,
        };
        assert!(!gate.is_approved());
        let operator = Uuid::new_v4();
        gate.grant_approval(operator);
        assert!(gate.is_approved());
        assert_eq!(gate.approved_by, Some(operator));
    }

    /// test_human_oversight_gate_timeout: ensures is_approved() returns false after timeout
    #[test]
    fn test_human_oversight_gate_timeout() {
        let gate = HumanOversightGate {
            system_id: Uuid::new_v4(),
            requires_human_approval: true,
            approval_timeout_seconds: 1, // 1 second timeout
            approved_at: Some(Utc::now() - chrono::Duration::seconds(5)),
            approved_by: Some(Uuid::new_v4()),
        };
        assert!(!gate.is_approved()); // Timeout exceeded
    }

    /// test_retention_policy_default: ensures default retention is 180 days minimum
    #[test]
    fn test_retention_policy_default() {
        let policy = RetentionPolicy::default();
        assert_eq!(policy.min_days, 180);
    }

    /// test_retention_policy_enforcement: ensures can_delete() respects 180-day floor
    #[test]
    fn test_retention_policy_enforcement() {
        let policy = RetentionPolicy::default();
        let created_at = Utc::now() - chrono::Duration::days(100); // 100 days ago
        assert!(!policy.can_delete(created_at)); // Still within retention
    }

    /// test_count_floor_blocks_at_boundary: ensures can_delete_by_count() enforces count floor
    #[test]
    fn test_count_floor_blocks_at_boundary() {
        let policy = RetentionPolicy {
            min_days: 180,
            max_days: 2555,
            count_floor: 5,
        };
        assert!(!policy.can_delete_by_count(5)); // at floor → blocked
        assert!(policy.can_delete_by_count(6)); // above floor → allowed
    }

    /// test_count_floor_default_is_ten: ensures default count_floor is 10
    #[test]
    fn test_count_floor_default_is_ten() {
        let policy = RetentionPolicy::default();
        assert_eq!(policy.count_floor, 10);
        assert!(!policy.can_delete_by_count(10)); // at floor → blocked
        assert!(policy.can_delete_by_count(11)); // above floor → allowed
    }

    /// test_phi_classification: ensures PhiClassification enum values are valid
    #[test]
    fn test_phi_classification() {
        let phi = PhiClassification::Genetic;
        assert_eq!(phi, PhiClassification::Genetic);
    }

    /// test_baa_construction: ensures BusinessAssociateAgreement constructs with phi_types
    #[test]
    fn test_baa_construction() {
        let baa = BusinessAssociateAgreement {
            baa_id: Uuid::new_v4(),
            covered_entity: "Hospital-X".to_string(),
            business_associate: "SMAOS-Health".to_string(),
            phi_types: vec![
                PhiClassification::MedicalRecord,
                PhiClassification::Biometric,
            ],
            safeguards_implemented: vec!["AES-256-GCM".to_string(), "Ed25519-signing".to_string()],
            breach_notification_days: 30,
        };
        assert_eq!(baa.phi_types.len(), 2);
    }

    /// test_transparency_record: ensures TransparencyRecord holds system metadata
    #[test]
    fn test_transparency_record() {
        use crate::eu_ai_act::TransparencyRecord;
        let tr = TransparencyRecord {
            system_id: Uuid::new_v4(),
            capabilities: vec!["glucose-prediction".to_string()],
            limitations: vec!["requires-recent-cgm-data".to_string()],
            data_sources: vec!["dexcom".to_string()],
            human_oversight_mechanism: "Ed25519-approval-gate".to_string(),
        };
        assert!(!tr.capabilities.is_empty());
    }

    /// test_risk_management_record: ensures RiskManagementRecord tracks risk level and mitigations
    #[test]
    fn test_risk_management_record() {
        let rmr = RiskManagementRecord {
            system_id: Uuid::new_v4(),
            risk_level: RiskLevel::High,
            identified_risks: vec!["bias-in-prediction".to_string()],
            mitigation_steps: vec!["monthly-fairness-audit".to_string()],
            last_assessment: Utc::now(),
        };
        assert_eq!(rmr.risk_level, RiskLevel::High);
        assert!(!rmr.identified_risks.is_empty());
    }
}
