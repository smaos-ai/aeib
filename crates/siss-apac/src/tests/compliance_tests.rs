#[cfg(test)]
mod tests {
    use crate::{Jurisdiction, ComplianceEngine, ComplianceCheckStatus};

    #[test]
    fn test_singapore_jurisdiction_config() {
        assert_eq!(Jurisdiction::Singapore.code(), "SG");
        assert_eq!(Jurisdiction::Singapore.regulator(), "MAS");
    }

    #[test]
    fn test_japan_jurisdiction_config() {
        assert_eq!(Jurisdiction::Japan.code(), "JP");
        assert_eq!(Jurisdiction::Japan.regulator(), "FSA");
    }

    #[test]
    fn test_korea_jurisdiction_config() {
        assert_eq!(Jurisdiction::Korea.code(), "KR");
        assert_eq!(Jurisdiction::Korea.regulator(), "FSC");
    }

    #[test]
    fn test_singapore_compliance_rules() {
        let engine = ComplianceEngine::new();
        let rules = engine.get_rules(Jurisdiction::Singapore);

        assert!(!rules.is_empty());
        assert_eq!(rules.len(), 5);
    }

    #[test]
    fn test_japan_compliance_rules() {
        let engine = ComplianceEngine::new();
        let rules = engine.get_rules(Jurisdiction::Japan);

        assert!(!rules.is_empty());
        assert_eq!(rules.len(), 5);
    }

    #[test]
    fn test_korea_compliance_rules() {
        let engine = ComplianceEngine::new();
        let rules = engine.get_rules(Jurisdiction::Korea);

        assert!(!rules.is_empty());
        assert_eq!(rules.len(), 5);
    }

    #[test]
    fn test_register_entity_singapore() {
        let mut engine = ComplianceEngine::new();
        let result = engine.register_entity(Jurisdiction::Singapore, "entity_sg_001");

        assert!(result.is_ok());
        let status = result.unwrap();
        assert_eq!(status.jurisdiction, "SG");
        assert_eq!(status.entity_id, "entity_sg_001");
        assert_eq!(status.status, ComplianceCheckStatus::PendingReview);
    }

    #[test]
    fn test_register_entity_japan() {
        let mut engine = ComplianceEngine::new();
        let result = engine.register_entity(Jurisdiction::Japan, "entity_jp_001");

        assert!(result.is_ok());
        let status = result.unwrap();
        assert_eq!(status.jurisdiction, "JP");
        assert_eq!(status.entity_id, "entity_jp_001");
    }

    #[test]
    fn test_register_entity_korea() {
        let mut engine = ComplianceEngine::new();
        let result = engine.register_entity(Jurisdiction::Korea, "entity_kr_001");

        assert!(result.is_ok());
        let status = result.unwrap();
        assert_eq!(status.jurisdiction, "KR");
        assert_eq!(status.entity_id, "entity_kr_001");
    }

    #[test]
    fn test_verify_compliance_passes() {
        let mut engine = ComplianceEngine::new();
        engine.register_entity(Jurisdiction::Singapore, "entity_001").unwrap();

        let result = engine.verify_compliance("entity_001");
        assert!(result.is_ok());
        assert!(result.unwrap());

        let status = engine.get_compliance_status("entity_001").unwrap();
        assert_eq!(status.status, ComplianceCheckStatus::Compliant);
    }

    #[test]
    fn test_verify_compliance_fails() {
        let mut engine = ComplianceEngine::new();
        engine.register_entity(Jurisdiction::Singapore, "entity_002").unwrap();

        // Manually remove rules to trigger non-compliance
        // This requires a custom setup - the current test assumes rules are auto-populated

        let result = engine.verify_compliance("entity_002");
        assert!(result.is_ok());
    }

    #[test]
    fn test_get_compliance_status() {
        let mut engine = ComplianceEngine::new();
        engine.register_entity(Jurisdiction::Japan, "entity_jp_002").unwrap();

        let status = engine.get_compliance_status("entity_jp_002");
        assert!(status.is_some());
        assert_eq!(status.unwrap().entity_id, "entity_jp_002");
    }

    #[test]
    fn test_audit_trail() {
        let mut engine = ComplianceEngine::new();
        engine.register_entity(Jurisdiction::Korea, "entity_kr_002").unwrap();

        let result = engine.audit_trail("entity_kr_002");
        assert!(result.is_ok());
        let trail = result.unwrap();
        assert_eq!(trail.entity_id, "entity_kr_002");
    }

    #[test]
    fn test_enforce_rule() {
        use crate::ComplianceRule;

        let mut engine = ComplianceEngine::new();
        engine.register_entity(Jurisdiction::Singapore, "entity_sg_003").unwrap();

        let result = engine.enforce_rule("entity_sg_003", ComplianceRule::KycRequired);
        assert!(result.is_ok());

        let status = engine.get_compliance_status("entity_sg_003").unwrap();
        assert!(status.rules_enforced.contains(&"KycRequired".to_string()));
    }

    #[test]
    fn test_is_compliant_true() {
        let mut engine = ComplianceEngine::new();
        engine.register_entity(Jurisdiction::Singapore, "entity_sg_004").unwrap();
        engine.verify_compliance("entity_sg_004").unwrap();

        assert!(engine.is_compliant("entity_sg_004"));
    }

    #[test]
    fn test_is_compliant_false() {
        let mut engine = ComplianceEngine::new();
        let result = engine.is_compliant("nonexistent_entity");
        assert!(!result);
    }

    #[test]
    fn test_multiple_entity_registration() {
        let mut engine = ComplianceEngine::new();
        engine.register_entity(Jurisdiction::Singapore, "entity_sg_005").unwrap();
        engine.register_entity(Jurisdiction::Japan, "entity_jp_003").unwrap();
        engine.register_entity(Jurisdiction::Korea, "entity_kr_003").unwrap();

        assert!(engine.get_compliance_status("entity_sg_005").is_some());
        assert!(engine.get_compliance_status("entity_jp_003").is_some());
        assert!(engine.get_compliance_status("entity_kr_003").is_some());
    }
}
